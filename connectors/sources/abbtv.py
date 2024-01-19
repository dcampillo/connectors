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
                "label": "Endpoint",
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
        
        hygraph = WPConnector(self.configuration["endpoint"],  self.configuration["bearer"])
        async for doc in hygraph.get_all():
            yield doc
        # print("Gettings all docs")
        # return sonarr.get_all()

        

class WPConnector():

    def __init__(self, endpoint, bearer, timestamp_id=None) -> None:
        self.endpoint = endpoint
        self.bearer = bearer
        self.timestamp_id = timestamp_id
        self.authorization_headers = {"Authorization": self.bearer}
        self.categories = self.get_categories()
        self.tags = self.get_tags()
    
    def get_categories(self):
        categories_endpoint = self.endpoint + "/wp-json/wp/v2/categories?_fields=id,name"
        req = requests.get(categories_endpoint, auth=('david', '0xVJ$z!54zi1!AxGjc'), headers=self.authorization_headers)
        categories = json.loads(req.content)

        categories_dict = {}
        categories_dict[1] = "Uncategorized"
        for category in categories:
            categories_dict[category["id"]] = category["name"]


        return categories_dict
    
    def get_tags(self):
        tags_endpoint = self.endpoint + "/wp-json/wp/v2/tags?_fields=id,name"
        req = requests.get(tags_endpoint, auth=('david', '0xVJ$z!54zi1!AxGjc'),headers=self.authorization_headers)
        tags = json.loads(req.content)

        tags_dict = {}
        for tag in tags:
            tags_dict[tag["id"]] = tag["name"]

        return tags_dict

    async def get_all(self):
        
        episodes_collection = []
        dl_all = False
        current_page = 1
        while dl_all == False:
            wp_posts = await self.__get_posts(Page=current_page)
            if wp_posts:
                for wp_post in wp_posts:
                    serialized_doc = await self.__serialize_document(wp_post)
                    yield serialized_doc, None
                current_page += 1
            else:
                dl_all = True
            
            

    async def __get_posts(self, PageSize=100, Page=1):
        posts_endpoint = self.endpoint + f"/wp-json/wp/v2/posts?_fields=id,title,excerpt,modified_gmt,link,content,tags,categories&per_page={PageSize}&page={Page}"
        posts = requests.get(posts_endpoint, auth=('david', '0xVJ$z!54zi1!AxGjc'), headers=self.authorization_headers)
        if posts.status_code == 200:
            return json.loads(posts.content)
        else:
            return None

    async def __serialize_document(self, data):
        doc = {}
        doc["_id"] = data["id"]
        doc["title"] = data["title"]["rendered"]
        doc["_timestamp"] = data["modified_gmt"]
        doc["body_content"] = data["content"]["rendered"]
        doc["body_content"] = data["content"]["rendered"]

        doc["url"] = data["link"]
        
        if "tags" in data:
            doc["tags"] = await self.map_tags(data["tags"])
        
        if "categories" in data:
            doc["categories"] = await self.map_categories(data["categories"])
        
        # for key in data.keys():
        #     if key == "updatedAt":
        #         doc["_timestamp"] = data[key]
        #     elif key == "id":
        #         doc["_id"] = data[key]
        #     elif key == "thumbnail":
        #         doc["thumbnailurl"] = data[key]["url"]
        #     # elif key == "is_internal":
        #     #      bVal = data[key]["is_internal"]
        #     #      doc["is_internal"] = "Yes" if bVal == True else "No"
        #     else:
        #         doc[key] = data[key]

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