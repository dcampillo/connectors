"""SonnarrTV data source connector v0.1
"""
import requests
import json
from connectors.source import BaseDataSource, ConfigurableFieldValueError


class HygraphDataSource(BaseDataSource):
    """Hygraph"""
    name = "Hygraph"
    service_type = "hygraph"
    advanced_rules_enabled = True

    def __init__(self, configuration):
        super().__init__(configuration=configuration)

        client_params = {}

        endpoint = self.configuration["endpoint"]
        bearer = self.configuration["bearer"]

        if self.configuration["direct_connection"]:
            client_params["directConnection"] = True

    async def ping(self):
       return(True)

    @classmethod
    def get_default_configuration(cls):
        return {
            "endpoint": {
                "label": "Public endpoint",
                "order": 1,
                "type": "str",
                "required": True
            },
            "bearer": {
                "label": "Bearer",
                "order": 2,
                "required": True,
                "sensitive": True,
                "type": "str",
            },
            "timestamp_id": {
                "label": "Timestamp field id",
                "order": 3,
                "type": "str",
                "required": False
            },
            "direct_connection": {
                "display": "toggle",
                "label": "Direct connection",
                "order": 6,
                "type": "bool",
                "value": False,
            },
        }
    
    async def get_docs(self, filtering=None):
        print(filtering)
        hygraph = HygraphConnector(self.configuration["endpoint"],  self.configuration["bearer"])
        async for doc in hygraph.get_all():
            yield doc
        # print("Gettings all docs")
        # return sonarr.get_all()

        

class HygraphConnector():
    
   
    
    def __init__(self, endpoint, bearer, timestamp_id=None) -> None:
        self.endpoint = endpoint
        self.bearer = bearer
        self.timestamp_id = timestamp_id
        self.authorization_headers = {"Authorization": self.bearer}
        
        self.graphql_query =  """
            query QuickLinks {
            quickLinks {
                id
                title
                description
                url
                updatedAt
                locale
                type
                thumbnail {
                url
                }
            }
            }
            """
    


    async def get_all(self):
        
        episodes_collection = []

        hygraph_items = await self.__get_items()
        print(hygraph_items["data"])
        
        for item in hygraph_items["data"]["quickLinks"]:
            serialized_doc = await self.__serialize_document(item)
            yield serialized_doc, None

    async def __get_items(self):
        
        items = requests.post(self.endpoint, json={"query": self.graphql_query}, headers=self.authorization_headers)
        return json.loads(items.content)

    async def __serialize_document(self, data):
        doc = {}
        for key in data.keys():
            if key == "updatedAt":
                doc["timestamp"] = data[key]
            elif key == "id":
                doc["_id"] = data[key]
            elif key == "thumbnail":
                doc["thumbnailurl"] = data[key]["url"]
            else:
                doc[key] = data[key]

        return doc
