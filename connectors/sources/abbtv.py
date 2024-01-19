"""SonnarrTV data source connector v0.1
"""
import requests
import json
from connectors.source import BaseDataSource, ConfigurableFieldValueError
import pprint

class ABBTVDataSource(BaseDataSource):
    """ABBTV"""
    name = "ABBTV"
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
                "label": "API Endpoint",
                "tooltip": "The base domain of the application: e.g. https://abbtv.inside.abb.com",
                "order": 1,
                "type": "str",
                "required": True
            },
            "username": {
                "label": "Username",
                "tooltip": "The username used to get the Bearer token",
                "order": 2,
                "required": True,
                "type": "str",
            },
            "password": {
                "label": "Password",
                "tooltip": "The password used to get the Bearer token",
                "order": 3,
                "required": True,
                "sensitive": True,
                "type": "str",
            },
            "pagesize": {
                "label": "Page size",
                "tooltip": "Number of posts to retrieve per page",
                "order": 4,
                "required": True,
                "sensitive": True,
                "type": "int",
                "value": 100
            },
            "timestamp_id": {
                "label": "Timestamp field id",
                "tooltip": "Name of the field to use as timestamp",
                "order": 5,
                "type": "str",
                "required": True,
                "value": "modified_gmt"
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
        
        wpc = WPConnector(self.configuration["endpoint"], self.configuration["username"], self.configuration["password"], timestamp_id=self.configuration["timestamp_id"])
        async for doc in wpc.get_all():
            yield doc

class WPConnector():

    def __init__(self, endpoint:str, username:str, password:str, timestamp_id=None) -> None:
        self.endpoint = endpoint
        self.bearer = self.__get_bearer(username, password)
        self.timestamp_id = timestamp_id
        self.authorization_headers = {"Authorization": self.bearer}
        self.categories = self.__get_categories()
        self.tags = self.__get_tags()
    
    def __get_bearer(self,username, password):
        categories_endpoint = self.endpoint + f"/wp-json/jwt-auth/v1/token?username={username}&password={password}"
        req = requests.post(categories_endpoint)
        if req.status_code == 200:
            content = json.loads(req.content)
            return content["token"]
        else:
            return None

    def __get_categories(self):
        categories_endpoint = self.endpoint + "/wp-json/wp/v2/categories?_fields=id,name"
        req = requests.get(categories_endpoint, headers=self.authorization_headers)
        categories = json.loads(req.content)

        categories_dict = {}
        categories_dict[1] = "Uncategorized"
        for category in categories:
            categories_dict[category["id"]] = category["name"]

        return categories_dict
    
    def __get_tags(self):
        tags_endpoint = self.endpoint + "/wp-json/wp/v2/tags?_fields=id,name"
        req = requests.get(tags_endpoint, headers=self.authorization_headers)
        tags = json.loads(req.content)

        tags_dict = {}
        for tag in tags:
            tags_dict[tag["id"]] = tag["name"]

        return tags_dict

    async def get_all(self):
        stop_retrieving_results = False
        current_page = 1

        while stop_retrieving_results == False:
            wp_posts = await self.__get_posts(Page=current_page)
            if wp_posts: 
                for wp_post in wp_posts:
                    serialized_doc = await self.__serialize_document(wp_post)
                    yield serialized_doc, None
                current_page += 1
            else:
                stop_retrieving_results = True
            
            

    async def __get_posts(self, PageSize=100, Page=1):
        posts_endpoint = self.endpoint + f"/wp-json/wp/v2/posts?_fields=id,title,excerpt,{self.timestamp_id},link,content,tags,categories&per_page={PageSize}&page={Page}"
        posts = requests.get(posts_endpoint, headers=self.authorization_headers)
        if posts.status_code == 200:
            return json.loads(posts.content)
        else:
            return None

    async def __serialize_document(self, data):
        doc = {}
        doc["_id"] = data["id"]
        doc["title"] = data["title"]["rendered"]
        doc["_timestamp"] = data[self.timestamp_id]
        doc["body_content"] = data["content"]["rendered"]
        doc["meta_description"] = data["excerpt"]["rendered"]
        doc["url"] = data["link"]
        
        if "tags" in data:
            doc["tags"] = await self.map_tags(data["tags"])
        
        if "categories" in data:
            doc["categories"] = await self.map_categories(data["categories"])

        return doc
    
    async def map_tags(self, tags):
        tags_name = []

        for tag in tags:
            tags_name.append(self.tags.get(tag))

        return tags_name
    
    async def map_categories(self, categories):
        categories_name = []

        for category in categories:
            categories_name.append(self.categories.get(category))

        return categories_name