import json
import threading
import requests


class NasaApiService:
    """Service for interacting with NASA's API."""

    def __init__(self):
        self.base_url = "https://images-api.nasa.gov"
        self.last_response = None

    def search_media(self, keyword, count=None, media_type="image", callback=None):
        """Search for NASA media with the given keyword and media type."""
        thread = threading.Thread(
            target=self._search_media_thread,
            args=(keyword, count, media_type, callback)
        )
        thread.daemon = True
        thread.start()
        return thread

    def _search_media_thread(self, keyword, count, media_type, callback):
        """Thread function for searching media."""
        try:
            params = {"q": keyword}
            if media_type != "all":
                params["media_type"] = media_type
            if count:
                params["page_size"] = count

            response = requests.get(f"{self.base_url}/search", params=params)
            response.raise_for_status()
            data = response.json()

            items = []
            if "collection" in data and "items" in data["collection"]:
                items = data["collection"]["items"]

            # Limit results if count is specified
            if count:
                items = items[:count]

            api_log = {
                "url": response.url,
                "method": "GET",
                "status": response.status_code,
                "params": params,
                "response_snippet": json.dumps(data, indent=2)[:400]
            }

            if callback:
                callback(items, api_log, None)
        except Exception as e:
            if callback:
                callback([], None, str(e))

    def search_album(self, album_name, count=None, callback=None):
        """Search for a NASA album by name."""
        thread = threading.Thread(
            target=self._search_album_thread,
            args=(album_name, count, callback)
        )
        thread.daemon = True
        thread.start()
        return thread

    def _search_album_thread(self, album_name, count, callback):
        """Thread function for searching albums."""
        try:
            params = {}
            if count:
                params["page_size"] = count

            response = requests.get(f"{self.base_url}/album/{album_name}", params=params)
            response.raise_for_status()
            data = response.json()

            items = []
            if "collection" in data and "items" in data["collection"]:
                items = data["collection"]["items"]

            # Limit results if count is specified
            if count:
                items = items[:count]

            api_log = {
                "url": response.url,
                "method": "GET",
                "status": response.status_code,
                "params": params,
                "response_snippet": json.dumps(data, indent=2)[:400]
            }

            if callback:
                callback(items, api_log, None)
        except Exception as e:
            if callback:
                callback([], None, str(e))