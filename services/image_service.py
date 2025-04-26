import time
import threading
import requests
from io import BytesIO
from PIL import Image
import pygame


class ImageCache:
    """Cache for storing loaded images."""

    def __init__(self, max_size=100):
        self.cache = {}
        self.max_size = max_size

    def get(self, url):
        """Get an image from the cache if it exists."""
        if url in self.cache:
            self.cache[url] = (time.time(), self.cache[url][1])
            return self.cache[url][1]
        return None

    def put(self, url, image):
        """Add an image to the cache."""
        if len(self.cache) >= self.max_size:
            oldest_url = min(self.cache.items(), key=lambda x: x[1][0])[0]
            del self.cache[oldest_url]
        self.cache[url] = (time.time(), image)


class ImageService:
    """Service for fetching and processing images."""

    def __init__(self):
        self.image_cache = ImageCache()

    def fetch_image_surface(self, url, thumb_size):
        """Fetch image from URL and convert to Pygame surface."""
        cached = self.image_cache.get(url)
        if cached:
            return cached

        try:
            response = requests.get(url)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            img = img.convert("RGBA")
            img.thumbnail((thumb_size, thumb_size))
            mode = img.mode
            size = img.size
            data = img.tobytes()
            surf = pygame.image.fromstring(data, size, mode)
            self.image_cache.put(url, surf)
            return surf
        except Exception:
            return None

    def fetch_and_notify_thumb(self, url, idx, callback=None):
        """Fetch a thumbnail image and notify when complete."""
        surf = self.fetch_image_surface(url, 110)  # Default thumbnail size
        if callback:
            callback(idx, surf)
        pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))


class DetailFetcher(threading.Thread):
    """Thread for fetching detailed information about a NASA item."""

    def __init__(self, nasa_id, is_video, on_asset, on_metadata, on_captions):
        super().__init__(daemon=True)
        self.nasa_id = nasa_id
        self.is_video = is_video
        self.on_asset = on_asset
        self.on_metadata = on_metadata
        self.on_captions = on_captions

    def run(self):
        try:
            r = requests.get(f"https://images-api.nasa.gov/asset/{self.nasa_id}", timeout=10)
            self.on_asset(r.json() if r.ok else {})
        except Exception:
            self.on_asset({})

        try:
            r = requests.get(f"https://images-api.nasa.gov/metadata/{self.nasa_id}", timeout=10)
            if r.ok:
                if r.headers.get('Content-Type', '').startswith("application/json"):
                    md = r.json()
                else:
                    md = {"raw": r.text}
                self.on_metadata(md)
            else:
                self.on_metadata({})
        except Exception:
            self.on_metadata({})

        if self.is_video:
            try:
                r = requests.get(f"https://images-api.nasa.gov/captions/{self.nasa_id}", timeout=10)
                self.on_captions(r.json() if r.ok else {})
            except Exception:
                self.on_captions({})
        else:
            self.on_captions({})