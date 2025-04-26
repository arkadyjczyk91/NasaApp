import threading
import requests

class DetailFetcher(threading.Thread):
    """Thread class for fetching detailed asset information from NASA API."""

    def __init__(self, nasa_id, is_video, on_asset, on_metadata, on_captions):
        """Initialize the fetcher with callbacks for when data is received."""
        super().__init__(daemon=True)
        self.nasa_id = nasa_id
        self.is_video = is_video
        self.on_asset = on_asset
        self.on_metadata = on_metadata
        self.on_captions = on_captions

    def run(self):
        """Execute the fetching process in a separate thread."""
        # Fetch asset data
        try:
            r = requests.get(f"https://images-api.nasa.gov/asset/{self.nasa_id}", timeout=10)
            self.on_asset(r.json() if r.ok else {})
        except Exception:
            self.on_asset({})

        # Fetch metadata
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

        # Fetch captions for videos
        if self.is_video:
            try:
                r = requests.get(f"https://images-api.nasa.gov/captions/{self.nasa_id}", timeout=10)
                self.on_captions(r.json() if r.ok else {})
            except Exception:
                self.on_captions({})
        else:
            self.on_captions({})