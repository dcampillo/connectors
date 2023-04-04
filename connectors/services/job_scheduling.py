#
# Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
# or more contributor license agreements. Licensed under the Elastic License 2.0;
# you may not use this file except in compliance with the Elastic License 2.0.
#
"""
Event loop

- polls for work by calling Elasticsearch on a regular basis
- instantiates connector plugins
- mirrors an Elasticsearch index with a collection of documents
"""
from connectors.byoc import (
    SYNC_DISABLED,
    ConnectorIndex,
    ConnectorUpdateError,
    DataSourceError,
    ServiceTypeNotConfiguredError,
    ServiceTypeNotSupportedError,
    Status,
    SyncJobIndex,
)
from connectors.logger import logger
from connectors.services.base import BaseService
from connectors.source import get_source_klass_dict


class JobSchedulingService(BaseService):
    name = "schedule"

    def __init__(self, config):
        super().__init__(config)
        self.idling = self.service_config["idling"]
        self.heartbeat_interval = self.service_config["heartbeat"]
        self.source_klass_dict = get_source_klass_dict(config)
        self.connector_index = None
        self.sync_job_index = None

    async def _schedule(self, connector):
        if self.running is False:
            logger.debug(
                f"Skipping run for {connector.id} because service is terminating"
            )
            return

        if connector.native:
            logger.debug(f"Connector {connector.id} natively supported")

        try:
            await connector.prepare(self.config)
        except ServiceTypeNotConfiguredError:
            logger.error(
                f"Service type is not configured for connector {self.config['connector_id']}"
            )
            return
        except ConnectorUpdateError as e:
            logger.error(e)
            return
        except ServiceTypeNotSupportedError:
            logger.debug(f"Can't handle source of type {connector.service_type}")
            return
        except DataSourceError as e:
            await connector.error(e)
            logger.critical(e, exc_info=True)
            raise

        # the heartbeat is always triggered
        await connector.heartbeat(self.heartbeat_interval)

        logger.debug(f"Connector status is {connector.status}")

        # we trigger a sync
        if connector.status == Status.CREATED:
            logger.info(
                f'Connector for {connector.service_type}(id: "{connector.id}") has just been created and cannot sync. Wait for Kibana to initialise connector correctly before proceeding.'
            )
            return

        if connector.status == Status.NEEDS_CONFIGURATION:
            logger.info(
                f'Connector for {connector.service_type}(id: "{connector.id}") is not configured yet. Finish connector configuration in Kibana to make it possible to run a sync.'
            )
            return

        if connector.service_type not in self.source_klass_dict:
            raise DataSourceError(
                f"Couldn't find data source class for {connector.service_type}"
            )

        source_klass = self.source_klass_dict[connector.service_type]
        if connector.features.sync_rules_enabled():
            await connector.validate_filtering(
                validator=source_klass(connector.configuration)
            )

        if not await self._should_sync(connector):
            return

        await self.sync_job_index.create(connector)
        if connector.sync_now:
            await connector.reset_sync_now_flag()

    async def _run(self):
        """Main event loop."""
        self.connector_index = ConnectorIndex(self.es_config)
        self.sync_job_index = SyncJobIndex(self.es_config)

        native_service_types = self.config.get("native_service_types", [])
        logger.debug(f"Native support for {', '.join(native_service_types)}")

        # TODO: we can support multiple connectors but Ruby can't so let's use a
        # single id
        # connector_ids = self.config.get("connector_ids", [])
        if "connector_id" in self.config:
            connector_ids = [self.config.get("connector_id")]
        else:
            connector_ids = []

        logger.info(
            f"Service started, listening to events from {self.es_config['host']}"
        )

        try:
            while self.running:
                try:
                    logger.debug(f"Polling every {self.idling} seconds")
                    async for connector in self.connector_index.supported_connectors(
                        native_service_types=native_service_types,
                        connector_ids=connector_ids,
                    ):
                        await self._schedule(connector)
                except Exception as e:
                    logger.critical(e, exc_info=True)
                    self.raise_if_spurious(e)

                # Immediately break instead of sleeping
                if not self.running:
                    break
                await self._sleeps.sleep(self.idling)
        finally:
            if self.connector_index is not None:
                self.connector_index.stop_waiting()
                await self.connector_index.close()
            if self.sync_job_index is not None:
                self.sync_job_index.stop_waiting()
                await self.sync_job_index.close()
        return 0

    async def _should_sync(self, connector):
        try:
            next_sync = connector.next_sync()
            # First we check if sync is disabled, and it terminates all other conditions
            if next_sync == SYNC_DISABLED:
                logger.debug(f"Scheduling is disabled for connector {connector.id}")
                return False
            # And only then we check if we need to run sync right now or not
            if next_sync - self.idling > 0:
                logger.debug(
                    f"Next sync for connector {connector.id} due in {int(next_sync)} seconds"
                )
                return False
            return True
        except Exception as e:
            logger.critical(e, exc_info=True)
            await connector.error(str(e))
            return False