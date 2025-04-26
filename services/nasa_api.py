import threading
import requests
import json

class NasaApiService:
    def __init__(self, on_result_callback, on_error_callback):
        self.on_result = on_result_callback
        self.on_error = on_error_callback

    def search_images(self, keyword, count=None, media_type="image"):
        thread = threading.Thread(
            target=self._execute_search,
            args=(keyword, count, media_type, False)
        )
        thread.daemon = True
        thread.start()
        return thread

    def search_album(self, album_name, count=None):
        thread = threading.Thread(
            target=self._execute_search,
            args=(album_name, count, None, True)
        )
        thread.daemon = True
        thread.start()
        return thread

    def _execute_search(self, keyword, count, media_type, is_album):
        try:
            if is_album:
                base_url = f"https://images-api.nasa.gov/album/{keyword}"
                params = {}
            else:
                base_url = "https://images-api.nasa.gov/search"
                params = {"q": keyword}
                if media_type and media_type != "all":
                    params["media_type"] = media_type
            if count:
                params["page_size"] = count

            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            items = []
            if "collection" in data and "items" in data["collection"]:
                items = data["collection"]["items"]
            items = items[:count] if count else items

            api_log = {
                "url": response.url,
                "method": "GET",
                "status": response.status_code,
                "params": params,
                "response_snippet": json.dumps(data, indent=2)[:400]
            }
            self.on_result(items, api_log)

        except Exception as e:
            error_message = f"Error fetching {'album' if is_album else 'images'}: {str(e)}"
            api_log = {
                "url": base_url if 'base_url' in locals() else "",
                "method": "GET",
                "status": "-",
                "params": params if 'params' in locals() else {},
                "response_snippet": str(e)
            }
            self.on_error(error_message, api_log)