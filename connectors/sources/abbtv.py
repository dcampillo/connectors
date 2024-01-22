"""ABBTV data source connector v0.1
"""
import requests
import json
from connectors.source import BaseDataSource, ConfigurableFieldValueError
import time

class ABBTVDataSource(BaseDataSource):
    """ABBTV"""
    name = "ABBTV"
    service_type = "abbtv"
    advanced_rules_enabled = True

    def __init__(self, configuration):
        super().__init__(configuration=configuration)

        client_params = {}

        self.configuration = configuration

        # endpoint = self.configuration["endpoint"]
        # token_username = self.configuration["username"]
        # self.token_password = self.configuration["password"]
        # self.page_size = self.configuration["pagesize"]
        # self.timestamp_id = self.configuration["timestamp_id"]

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
                "type": "int",
                "value": 100
            },
            "timestampid": {
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
        
        wpc = WPConnector(self.configuration["endpoint"], self.configuration["username"], self.configuration["password"], timestamp_id=self.configuration["timestampid"], page_size=self.configuration["pagesize"])
        async for doc in wpc.get_all():
            yield doc

class WPConnector():

    def __init__(self, endpoint:str, username:str, password:str, timestamp_id=None, page_size=100) -> None:
        self.endpoint = endpoint
        self.page_size=page_size
        self.timestamp_id = timestamp_id
        
        # Get bearer and set auth header
        self.bearer = self.__get_bearer(username, password)
        self.authorization_headers = {"Authorization": f"Bearer {self.bearer}"}
        
        # Get list of categories and tags to remap values when creating doc for ES
        # print("Loading tags...")
        # self.tags = self.__get_tags()
        # print(f"Tags loaded: {len(self.tags)}")
        
        # print("Loading categories...")
        # self.categories = self.__get_categories()
        # print(f"Categories loaded: {len(self.categories)}")
    
    def __get_bearer(self,username, password):
        categories_endpoint = self.endpoint + f"/wp-json/jwt-auth/v1/token?username={username}&password={password}"
        req = requests.post(categories_endpoint)
        if req.status_code == 200:
            content = json.loads(req.content)
            return content["token"]
        else:
            return None

    def __get_categories(self):
        current_page = 1
        categories_endpoint = self.endpoint + f"/wp-json/wp/v2/categories?_fields=id,name&per_page={self.page_size}&page={current_page}"
        req = requests.get(categories_endpoint, headers=self.authorization_headers)
        categories = json.loads(req.content)

        categories_dict = {}
        categories_dict[1] = "Uncategorized"
        for category in categories:
            categories_dict[category["id"]] = category["name"]

        return categories_dict
    
    def __get_tags(self):
        stop_retrieving_results = False
        current_page = 1
        tags_dict = {}
        while stop_retrieving_results == False:
            tags_endpoint = self.endpoint + f"/wp-json/wp/v2/tags?_fields=id,name&per_page={self.page_size}&page={current_page}"
            req = requests.get(tags_endpoint, headers=self.authorization_headers)
            tags = json.loads(req.content)
            
            if tags:
                for tag in tags:
                    tags_dict[tag["id"]] = tag["name"]
                current_page += 1
                time.sleep(1)
            else:
                stop_retrieving_results=True

        return tags_dict

    async def get_all(self):
        stop_retrieving_results = False
        current_page = 1
        
        while stop_retrieving_results == False:
            wp_posts = await self.__get_posts(page_size=self.page_size, page=current_page)
            if wp_posts: 
                for wp_post in wp_posts:
                    serialized_doc = await self.__serialize_document(wp_post)
                    yield serialized_doc, None
                current_page += 1
                time.sleep(.2)
            else:
                stop_retrieving_results = True
            
            

    async def __get_posts(self, page_size=100, page=1):
        posts_endpoint = self.endpoint + f"/wp-json/wp/v2/posts?_fields=id,title,excerpt,{self.timestamp_id},link,content,tags,categories&per_page={page_size}&page={page}"
        self.authorization_headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" + str(page)
        self.authorization_headers["Connection"] = "keep-alive"

        posts = requests.get(posts_endpoint, headers=self.authorization_headers)
        if posts.status_code == 200:
            return json.loads(posts.content)
        else:
            return None

    async def __serialize_document(self, data):
        doc = {}
        doc["_id"] = data["id"]
        doc["title"] = data["title"]["rendered"]
        doc["timestamp"] = data[self.timestamp_id]
        doc["body_content"] = data["content"]["rendered"]
        doc["meta_description"] = data["excerpt"]["rendered"]
        doc["url"] = data["link"]
        doc["tags"] = data["categories"]
        doc["categories"] = data["tags"]
        # if "tags" in data:
        #     doc["tags_unwrapped"] = await self.map_tags(data["tags"])
        
        # if "categories" in data:
        #     doc["categories_unwrapped"] = await self.map_categories(data["categories"])

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
    
