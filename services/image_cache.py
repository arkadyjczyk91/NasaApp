import time

class ImageCache:
    """Cache for storing and retrieving images to avoid repeated downloads."""

    def __init__(self, max_size=100):
        """Initialize the image cache with a maximum size limit."""
        self.cache = {}
        self.max_size = max_size

    def get(self, url):
        """Get an image from the cache if it exists and update its access time."""
        if url in self.cache:
            self.cache[url] = (time.time(), self.cache[url][1])
            return self.cache[url][1]
        return None

    def put(self, url, image):
        """Add an image to the cache, removing oldest entries if max size reached."""
        if len(self.cache) >= self.max_size:
            oldest_url = min(self.cache.items(), key=lambda x: x[1][0])[0]
            del self.cache[oldest_url]
        self.cache[url] = (time.time(), image)