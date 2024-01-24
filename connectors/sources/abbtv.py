"""ABBTV data source connector v0.1
"""
import requests
import json
from connectors.source import BaseDataSource, ConfigurableFieldValueError
import time
import aiohttp
from datetime import datetime
import html

class ABBTVDataSource(BaseDataSource):
    """ABBTV"""
    name = "ABBTV"
    service_type = "abbtv"
    advanced_rules_enabled = True
    incremental_sync_enabled = False

    def __init__(self, configuration):
        super().__init__(configuration=configuration)

        client_params = {}
        self.configuration = configuration

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
    
    # Commented for future use
    # async def get_docs_incrementally(self, sync_cursor, filtering=None):
    #     print(sync_cursor)
    #     wpc = WPConnector(self.configuration["endpoint"], self.configuration["username"], self.configuration["password"], timestamp_id=self.configuration["timestampid"], page_size=self.configuration["pagesize"])
    #     async for doc in wpc.get_all(incremental=True):
    #         yield doc

class WPConnector():
    ISO_ZULU_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, endpoint:str, username:str, password:str, timestamp_id=None, page_size=100) -> None:
        self.endpoint = endpoint
        self.page_size=page_size
        self.timestamp_id = timestamp_id

        # Get bearer and set auth header
        self.bearer = self.__get_bearer(username, password)
        self.authorization_headers = {"Authorization": f"Bearer {self.bearer}", "User-Agent" : "PostmanRuntime/7.35.0" }

        
        # Get list of categories and tags to remap values when creating doc for ES
        print("Loading tags...")
        self.tags = self.__get_tags()
        print(f"Tags loaded: {len(self.tags)}")
        
        print("Loading categories...")
        self.categories = self.__get_categories()
        print(f"Categories loaded: {len(self.categories)}")

        print("Loading authors...")
        self.authors = self.__get_users()
        print(f"Authors loaded: {len(self.categories)}")

    
    def __get_bearer(self,username, password):
        print("Getting bearer")
        auth_endpoint = self.endpoint + f"/wp-json/jwt-auth/v1/token?username={username}&password={password}"

        _header = { "User-Agent" : "PostmanRuntime/7.35.0"}
        req = requests.post(auth_endpoint, headers=_header)
        
        if req.status_code == 200:
            content = json.loads(req.content)
            return content["token"]
        else:
            raise Exception(f"Unable to get Authorization Token : HTTP {req.status_code}")

    def __get_categories(self):
        stop_retrieving_results = False
        current_page = 1

        categories_dict = {}
        categories_dict[1] = "Uncategorized"
        while stop_retrieving_results == False:
            categories_endpoint = self.endpoint + f"/wp-json/wp/v2/categories?_fields=id,name&per_page={self.page_size}&page={current_page}"
            try:
                response = requests.get(categories_endpoint, headers=self.authorization_headers)
            except requests.exceptions.RequestException as e:  # This is the correct syntax
                raise Exception(e)
            
            if response.status_code != 200:
                raise Exception(f"Unable to fetch categories : HTTP {response.status_code} {categories_endpoint}")
            
            categories = json.loads(response.content)

            if categories:
                for category in categories:
                    categories_dict[category["id"]] = category["name"]
                current_page += 1
                print(".", end='', flush=True)
            else:
                stop_retrieving_results=True

        return categories_dict
    
    def __get_tags(self):
        stop_retrieving_results = False
        current_page = 1
        tags_dict = {}
    
        while stop_retrieving_results == False:
            tags_endpoint = self.endpoint + f"/wp-json/wp/v2/tags?_fields=id,name&per_page={self.page_size}&page={current_page}"
            try:
                response = requests.get(tags_endpoint, headers=self.authorization_headers)
            except requests.exceptions.RequestException as e:  # This is the correct syntax
                raise Exception(e)
            if response.status_code != 200:
                raise Exception(f"Unable to fetch tags : HTTP {response.status_code} {tags_endpoint}")
            tags = json.loads(response.content)
            
            if tags:
                for tag in tags:
                    tags_dict[tag["id"]] = tag["name"]
                current_page += 1
                print(".", end='', flush=True)
            else:
                stop_retrieving_results=True

        return tags_dict

    def __get_users(self):
        stop_retrieving_results = False
        current_page = 1
        users_dict = {}
    
        while stop_retrieving_results == False:
            users_endpoint = self.endpoint + f"/wp-json/wp/v2/users?_fields=id,name,link&per_page={self.page_size}&page={current_page}"
            try:
                response = requests.get(users_endpoint, headers=self.authorization_headers)
            except requests.exceptions.RequestException as e:  # This is the correct syntax
                raise Exception(e)
            if response.status_code != 200:
                raise Exception(f"Unable to fetch tags : HTTP {response.status_code} {users_endpoint}")
            users = json.loads(response.content)
            
            if users:
                for user in users:
                    user_info = {}
                    user_info["id"] = user["id"]
                    user_info["name"] = user["name"]
                    user_info["link"] = user["link"]

                    users_dict[user["id"]] = user_info
                current_page += 1
                print(".", end='', flush=True)
            else:
                stop_retrieving_results=True

        return users_dict
    
    async def get_all(self):
        stop_retrieving_results = False
        current_page = 1
        
        while stop_retrieving_results == False:
            try:
                wp_posts = await self.__get_posts(page_size=self.page_size, page=current_page)
            except requests.exceptions.RequestException as e:  # This is the correct syntax
                raise Exception(e)
            if wp_posts: 
                for wp_post in wp_posts:
                    serialized_doc = await self.__serialize_document(wp_post)
                    yield serialized_doc, None
                    
                current_page += 1
                
            else:
                stop_retrieving_results = True

    async def __get_posts(self, page_size=100, page=1):
        posts_endpoint = self.endpoint + f"/wp-json/wp/v2/posts?_fields=id,title,excerpt,author,{self.timestamp_id},link,content,tags,categories&per_page={page_size}&page={page}"
        
        posts = requests.get(posts_endpoint, headers=self.authorization_headers)
        if posts.status_code == 200:
            return json.loads(posts.content)
        else:
            return None

    async def __serialize_document(self, data):
        doc = {}
        _timestamp = datetime.strptime(data[self.timestamp_id], '%Y-%m-%dT%H:%M:%S')
            
        doc["_id"] = str(data["id"])
        doc["title"] = html.unescape(data["title"]["rendered"])
        doc["timestamp"] = _timestamp.strftime(self.ISO_ZULU_TIMESTAMP_FORMAT)
        doc["body_content"] = data["content"]["rendered"]
        doc["meta_description"] = data["excerpt"]["rendered"]
        doc["url"] = data["link"]
        doc["tags"] = data["tags"]
        doc["categories"] = data["categories"]
        doc["author"] = data["author"]
        
        author_infos = self.authors.get(data["author"])
        if author_infos:
            doc["author_name"] = author_infos.get("name")
            doc["author_link"] = author_infos.get("link")

        if "tags" in data:
            doc["tags_unwrapped"] = await self.map_tags(data["tags"])
        
        if "categories" in data:
            doc["categories_unwrapped"] = await self.map_categories(data["categories"])

        return doc
    
    async def map_tags(self, tags):
        tags_name = []

        for tag in tags:
            tag_name = self.tags.get(tag)
            if tag_name:
                tags_name.append(html.unescape(tag_name))
            else:
                tags_name.append(tag)
        return tags_name
    
    async def map_categories(self, categories):
        categories_name = []

        for category in categories:
            category_name = self.categories.get(category)
            if category_name:
                categories_name.append(html.unescape(category_name))
            else:
                categories_name.append(category)

        return categories_name
    
