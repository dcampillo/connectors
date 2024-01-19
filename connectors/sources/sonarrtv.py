"""SonnarrTV data source connector v0.1
"""
import requests
import json
from connectors.source import BaseDataSource, ConfigurableFieldValueError
import aiohttp
import asyncio

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
    def __init__(self, host:str, apikey:str) -> None:
        self.host = host
        self.apikey = apikey
        self.series_api = f"{host}/api/v3/series"
        self.episodes_api = f"{host}/api/v3/episode"
        self.api_header = {"X-api-key": self.apikey}
        print("alive")
    


    async def get_all(self):
        
        episodes_collection = []

        tv_series = await self.__get_series()
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for serie in tv_series:
                task = asyncio.create_task(self.__get_episodes(serie, session))
                tasks.append(task)
            res = await asyncio.gather(*tasks)

            
            for eps in res:
                
                for episode in eps["episodes"]:
                    episode_detail = {
                    "_id" : episode["id"],
                    "seasonNumber" : episode["seasonNumber"],
                    "episodeNumber" : episode["episodeNumber"],
                    "title" : episode["title"],
                    "overview" : episode["overview"] if "overview" in episode else "",
                    "seriesId" : episode["id"],
                    "serieTitle" : eps["serieTitle"],
                    "hasFile" : episode["hasFile"]
                }

                    yield episode_detail, None

    async def __get_series(self):
        series = requests.get(self.series_api, headers=self.api_header)
        return json.loads(series.content)

    async def __get_episodes(self, serie, Session:aiohttp.ClientSession):
        serie_id = serie["id"]
        serie_title = serie["title"]
        endpoint = self.episodes_api + f"/?seriesId={serie_id}"
        headers = { "X-api-key": self.apikey}
        async with Session.get(endpoint, headers=self.api_header) as r:
            episodes = await r.json()
        
            return {"id": serie_id, "serieTitle": serie_title, "episodes" : episodes}


