"""SonnarrTV data source connector v0.1
"""
import requests
import json
from connectors.source import BaseDataSource, ConfigurableFieldValueError


class SonarrTVDataSource(BaseDataSource):
    """SonarrTV"""
    name = "Sonarr TV"
    service_type = "sonarr_tv"
    advanced_rules_enabled = False

    def __init__(self, configuration):
        super().__init__(configuration=configuration)

        client_params = {}

        host = self.configuration["host"]
        apikey = self.configuration["apikey"]

        if self.configuration["direct_connection"]:
            client_params["directConnection"] = True

    async def ping(self):
       return(True)

    @classmethod
    def get_default_configuration(cls):
        return {
            "host": {
                "label": "Server hostname",
                "order": 1,
                "type": "str",
                "required": True
            },
            "apikey": {
                "label": "API Key",
                "order": 2,
                "required": True,
                "type": "str",
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
        sonarr = SonnarrConnector(self.configuration["host"],  self.configuration["apikey"])
        async for doc in sonarr.get_all():
            yield doc
        # print("Gettings all docs")
        # return sonarr.get_all()

        

class SonnarrConnector():
    def __init__(self, host, apikey) -> None:
        self.host = host
        self.apikey = apikey
        self.series_api = f"{host}/api/v3/series"
        self.episodes_api = f"{host}/api/v3/episode"
        self.api_header = {"X-api-key": self.apikey}
        print("alive")
    


    async def get_all(self):
        
        episodes_collection = []

        tv_series = await self.__get_series()
        print(type(tv_series))

        
        for serie in tv_series:
            episodes = await self.__get_episodes(serie["id"])
            for episode in episodes:
                episode_detail = {
                    "_id" : episode["id"],
                    "seasonNumber" : episode["seasonNumber"],
                    "episodeNumber" : episode["episodeNumber"],
                    "title" : episode["title"],
                    "overview" : episode["overview"] if "overview" in episode else "",
                    "seriesId" : episode["id"],
                    "serieTitle" : serie["title"],
                    "hasFile" : episode["hasFile"]
                }

                yield episode_detail, None
                #episodes_collection.append(episode_detail)

        #return episodes_collection

    async def __get_series(self):
        series = requests.get(self.series_api, headers=self.api_header)
        return json.loads(series.content)

    async def __get_episodes(self, serie_id):
        endpoint = self.episodes_api + f"/?seriesId={serie_id}"
        series = requests.get(endpoint, headers=self.api_header)
        return json.loads(series.content)


