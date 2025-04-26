import time

class ImageCache:
    def __init__(self, max_size=100):
        self.cache = {}
        self.max_size = max_size
    def get(self, url):
        if url in self.cache:
            self.cache[url] = (time.time(), self.cache[url][1])
            return self.cache[url][1]
        return None
    def put(self, url, image):
        if len(self.cache) >= self.max_size:
            oldest_url = min(self.cache.items(), key=lambda x: x[1][0])[0]
            del self.cache[oldest_url]
        self.cache[url] = (time.time(), image)