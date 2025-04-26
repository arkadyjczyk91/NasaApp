import threading
import time
from io import BytesIO

import pygame
import requests
from PIL import Image

from constants import *
from media.audio_player import AudioPlayer
from media.video_player import VideoPlayer
from services.detail_feacher import DetailFetcher
from services.image_cache import ImageCache
from services.nasa_api import NasaApiService
from ui.detail_view import DetailView
from ui.gallery import Gallery


class NasaImageExplorer:
    def __init__(self):
        # Initialize Pygame
        pygame.init()
        pygame.key.set_repeat(400, 50)
        pygame.display.set_caption("NASA Image Explorer")

        # Window settings
        self.fullscreen = True
        self.default_size = DEFAULT_WINDOW_SIZE
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.WIDTH, self.HEIGHT = self.screen.get_size()

        # Initialize fonts
        self.fonts = {
            "default": pygame.font.SysFont("Arial", 28),
            "small": pygame.font.SysFont("Consolas", 17),
            "gallery_label": pygame.font.SysFont("Arial", 20, bold=True),
            "gallery_meta": pygame.font.SysFont("Consolas", 15),
            "medium": pygame.font.SysFont("Arial", 22, bold=True),
            "title": pygame.font.SysFont("Arial", 36, bold=True),
            "api": pygame.font.SysFont("Consolas", 16),
            "detail_asset": pygame.font.SysFont("Consolas", 15),
            "label": pygame.font.SysFont("Arial", 18, bold=True)
        }

        # Input fields state
        self.input_keyword = ""
        self.input_count = ""
        self.inputs = ["media_type", "keyword", "count", "gallery", "pager"]
        self.active_control = 1

        # Application state
        self.status = "Ready"
        self.images = []
        self.images_json = []
        self.api_log = None
        self.current_page = 0
        self.selected_idx = 0
        self.loading = False
        self.lock = threading.Lock()
        self.media_types = ["all", "image", "video", "audio", "album"]
        self.selected_media_type = 1

        # Gallery settings
        self.thumbnail_size = THUMBNAIL_SIZE
        self.images_per_page = 16
        self.last_pager_key = None

        # Thumbnails
        self.thumb_urls = []
        self.thumb_loaded = set()

        # Search tracking
        self.last_keyword = ""
        self.last_keyword_change = time.time()
        self.fetch_delay = 0.5
        self.last_fetch_keyword = ""
        self.last_fetch_count = ""
        self.last_fetch_media_type = self.selected_media_type

        # Detail view state
        self.detail_mode = False

        # Services and components
        self.image_cache = ImageCache()
        self.audio_player = AudioPlayer()
        self.video_player = VideoPlayer()
        self.nasa_api = NasaApiService(self.on_search_results, self.on_search_error)

        # Initialize UI components
        self.gallery = Gallery(
            pygame.Rect(40, 110, int(self.WIDTH * 0.62), int(self.HEIGHT * 0.75)),
            self.thumbnail_size,
            self.fonts["small"],
            self.fonts["gallery_meta"]
        )

        self.detail_view = DetailView(
            self.WIDTH,
            self.HEIGHT,
            self.fonts,
            self.image_cache,
            self.audio_player,
            self.video_player
        )

        # Run the application
        self.run()

    def on_search_results(self, items, api_log):
        """Callback for when search results are received."""
        with self.lock:
            self.images_json = items
            self.images = items
            self.current_page = 0
            self.selected_idx = 0
            self.status = f"Found {len(self.images_json)} assets for query '{self.input_keyword}'."
            self.api_log = api_log
            self.thumb_urls = []
            self.thumb_loaded = set()

            # Get thumbnail URLs from items
            for item in self.images:
                image_url = None
                if "links" in item:
                    for link in item["links"]:
                        if link.get("rel") == "preview" and "href" in link:
                            image_url = link["href"]
                            break
                self.thumb_urls.append(image_url)

                # Start fetching thumbnails in the background
                if image_url and self.image_cache.get(image_url) is None:
                    t = threading.Thread(target=self._fetch_and_notify_thumb,
                                         args=(image_url, len(self.thumb_urls) - 1))
                    t.daemon = True
                    t.start()

        self.loading = False

    def on_search_error(self, error_message, api_log):
        """Callback for when a search error occurs."""
        with self.lock:
            self.images_json = []
            self.images = []
            self.status = error_message
            self.api_log = api_log
            self.thumb_urls = []
            self.thumb_loaded = set()

        self.loading = False

    def _fetch_and_notify_thumb(self, url, idx):
        """Fetch a thumbnail in the background and notify when done."""
        surf = self.fetch_image_surface(url, self.thumbnail_size)
        self.thumb_loaded.add(idx)
        pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))

    def fetch_image_surface(self, url, thumb_size):
        """Fetch and process an image from a URL."""
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

    def start_search(self):
        """Start a search with the current parameters."""
        keyword = self.input_keyword.strip()
        count_str = self.input_count.strip()
        media_type = self.media_types[self.selected_media_type]

        if not keyword:
            self.status = "Enter a keyword"
            return

        count = None
        if count_str:
            try:
                count = int(count_str)
                if count <= 0:
                    self.status = "Asset limit must be positive"
                    return
            except ValueError:
                self.status = "Asset limit must be a number"
                return

        self.loading = True
        self.status = "Searching..."

        if media_type == "album":
            self.nasa_api.search_album(keyword, count)
        else:
            self.nasa_api.search_images(keyword, count, media_type)

        self.last_fetch_keyword = keyword
        self.last_fetch_count = count_str
        self.last_fetch_media_type = self.selected_media_type

    def enter_detail(self, item):
        """Enter detail view for an item."""
        self.detail_mode = True

        # Get item data
        d = item.get("data", [{}])[0]
        nasa_id = d.get("nasa_id")
        is_video = (d.get("media_type") == "video")

        # Create callbacks for fetchers
        def on_asset(asset):
            self.detail_view.detail_asset = asset
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))

        def on_metadata(metadata):
            self.detail_view.detail_metadata = metadata
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))

        def on_captions(captions):
            self.detail_view.detail_captions = captions
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))

        # Initialize detail view with the item
        self.detail_view.load_asset(item, {}, {}, {})

        # Start fetching detailed information
        DetailFetcher(nasa_id, is_video, on_asset, on_metadata, on_captions).start()

    def handle_key(self, event):
        """Handle keyboard input."""
        if event.type == pygame.VIDEORESIZE:
            self.resize(event.w, event.h)
            return

        # Toggle fullscreen
        if event.key == pygame.K_F11:
            self.toggle_fullscreen()
            return

        # Reset to windowed mode
        if event.key == pygame.K_F12:
            self.set_windowed()
            return

        # Handle zoom in windowed mode
        if event.key == pygame.K_PLUS or (event.mod & pygame.KMOD_CTRL and event.key == pygame.K_EQUALS):
            if not self.fullscreen:
                self.resize_by_scale(1.1)
            return

        if event.key == pygame.K_MINUS or (event.mod & pygame.KMOD_CTRL and event.key == pygame.K_MINUS):
            if not self.fullscreen:
                self.resize_by_scale(0.9)
            return

        # If in detail mode, delegate to detail view
        if self.detail_mode:
            result = self.detail_view.handle_key(event, pygame)
            if result == "exit":
                self.detail_mode = False
            return

        # Handle regular UI navigation
        focus = self.inputs[self.active_control]

        # Media type selector
        if focus == "media_type":
            if event.key == pygame.K_LEFT:
                self.selected_media_type = (self.selected_media_type - 1) % len(self.media_types)
                self.last_fetch_keyword = ""  # Force fetch with new media type
            elif event.key == pygame.K_RIGHT:
                self.selected_media_type = (self.selected_media_type + 1) % len(self.media_types)
                self.last_fetch_keyword = ""  # Force fetch with new media type
            elif event.key == pygame.K_TAB:
                self.active_control = (self.active_control + 1) % len(self.inputs)
            elif event.key == pygame.K_DOWN:
                self.active_control = (self.active_control + 1) % len(self.inputs)
            elif event.key == pygame.K_UP:
                self.active_control = (self.active_control - 1) % len(self.inputs)
            return

        # Tab navigation
        if event.key == pygame.K_TAB and not (event.mod & pygame.KMOD_SHIFT):
            self.active_control = (self.active_control + 1) % len(self.inputs)
            self.last_pager_key = None
            return
        elif event.key == pygame.K_TAB and (event.mod & pygame.KMOD_SHIFT):
            self.active_control = (self.active_control - 1) % len(self.inputs)
            self.last_pager_key = None
            return

        # Keyword input field
        if focus == "keyword":
            if event.key == pygame.K_RETURN:
                self.start_search()
            elif event.key == pygame.K_BACKSPACE:
                self.input_keyword = self.input_keyword[:-1]
            elif event.key == pygame.K_DOWN:
                self.active_control = 2
            elif event.key == pygame.K_UP:
                self.active_control = 0
            elif event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT:
                self.active_control = 0
            elif event.unicode and len(self.input_keyword) < 40 and event.key != pygame.K_TAB:
                self.input_keyword += event.unicode

        # Count input field
        elif focus == "count":
            if event.key == pygame.K_RETURN:
                self.start_search()
            elif event.key == pygame.K_BACKSPACE:
                self.input_count = self.input_count[:-1]
            elif event.key == pygame.K_UP:
                self.active_control = 1
            elif event.key == pygame.K_DOWN:
                self.active_control = 3
            elif event.unicode and len(self.input_count) < 6 and event.unicode.isdigit():
                self.input_count += event.unicode

        # Gallery navigation
        elif focus == "gallery":
            count = min(self.images_per_page, len(self.images) - self.current_page * self.images_per_page)
            gallery_cols = max(1, (int(self.WIDTH * 0.62) + 24) // (self.thumbnail_size + 28))

            if event.key == pygame.K_RIGHT:
                self.selected_idx = (self.selected_idx + 1) % count
            elif event.key == pygame.K_LEFT:
                self.selected_idx = (self.selected_idx - 1) % count
            elif event.key == pygame.K_DOWN:
                next_idx = self.selected_idx + gallery_cols
                if next_idx < count:
                    self.selected_idx = next_idx
            elif event.key == pygame.K_UP:
                if self.selected_idx >= gallery_cols:
                    self.selected_idx -= gallery_cols
            elif event.key == pygame.K_RETURN:
                if 0 <= self.selected_idx < count:
                    idx = self.current_page * self.images_per_page + self.selected_idx
                    self.enter_detail(self.images[idx])
            elif event.key == pygame.K_PAGEUP:
                self.prev_page()
            elif event.key == pygame.K_PAGEDOWN:
                self.next_page()