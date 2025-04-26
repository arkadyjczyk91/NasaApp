import pygame
from constants import *
from utils.text_renderer import render_text, render_text_lines, shorten_url
from ui.input_panel import InputPanel
from ui.api_panel import ApiPanel
from ui.page_navigator import PageNavigator
from ui.gallery import Gallery
from ui.detail_view import DetailView
from services.image_cache import ImageCache
from services.nasa_api import NasaApiService
from services.detail_feacher import DetailFetcher
from media.audio_player import AudioPlayer
from media.video_player import VideoPlayer

class NasaImageApp:
    def __init__(self):
        pygame.init()
        pygame.key.set_repeat(400, 50)
        self.screen = pygame.display.set_mode(DEFAULT_SIZE, pygame.RESIZABLE)
        self.WIDTH, self.HEIGHT = self.screen.get_size()
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
        # UI State
        self.input_keyword = ""
        self.input_count = ""
        self.active_control = 1
        self.selected_media_type = 1
        self.media_types = ["all", "image", "video", "audio", "album"]
        self.current_page = 0
        self.images = []
        self.thumb_urls = []
        self.selected_idx = 0
        self.images_per_page = 8
        self.api_log = None
        self.status = "Gotowy"
        self.image_cache = ImageCache()
        self.detail_mode = False
        self.audio_player = AudioPlayer()
        self.video_player = VideoPlayer()
        self.image_cache = ImageCache()
        self.detail_view = DetailView(
            self.fonts, self.WIDTH, self.HEIGHT,
            self.image_cache, self.audio_player, self.video_player
        )
        self.nasa_api = NasaApiService(self.on_search_results, self.on_search_error)
        self.input_panel = InputPanel(
            self.fonts, 40, 10, self.media_types,
            get_active=lambda: self.active_control,
            set_active=lambda v: setattr(self, 'active_control', v),
            get_keyword=lambda: self.input_keyword,
            set_keyword=lambda v: setattr(self, 'input_keyword', v),
            get_count=lambda: self.input_count,
            set_count=lambda v: setattr(self, 'input_count', v),
            get_selected_media_type=lambda: self.selected_media_type,
            set_selected_media_type=lambda v: setattr(self, 'selected_media_type', v)
        )
        self.api_panel = ApiPanel(self.fonts, self.WIDTH-400, 80, 360, 300)
        self.page_navigator = PageNavigator(
            self.fonts, 40, self.HEIGHT-60, self.WIDTH-80,
            get_current=lambda: self.current_page,
            set_current=lambda v: setattr(self, 'current_page', v),
            get_total=lambda: max(1, (len(self.images) + self.images_per_page - 1) // self.images_per_page)
        )
        self.gallery = Gallery(self.fonts, THUMBNAIL_SIZE, 40, 80, 800, 400)
        self.run()

    def on_search_results(self, items, api_log):
        self.images = items
        self.thumb_urls = []
        for item in items:
            image_url = None
            if "links" in item:
                for link in item["links"]:
                    if link.get("rel") == "preview" and "href" in link:
                        image_url = link["href"]
                        break
            self.thumb_urls.append(image_url)
        self.api_log = api_log

    def on_search_error(self, error_message, api_log):
        self.images = []
        self.thumb_urls = []
        self.api_log = api_log
        self.status = error_message

    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                elif event.type == pygame.KEYDOWN:
                    result = self.input_panel.handle_event(event)
                    self.page_navigator.handle_event(event)
                    if result == "submit":
                        params = {
                            "keyword": self.input_keyword.strip(),
                            "count": int(self.input_count.strip() or 8),
                            "media_type": self.media_types[self.selected_media_type]
                        }
                        if params["media_type"] == "album":
                            self.nasa_api.search_album(params["keyword"], params["count"])
                        else:
                            self.nasa_api.search_images(params["keyword"], params["count"], params["media_type"])
            self.screen.fill(BLACK)
            self.input_panel.draw(self.screen)
            self.gallery.draw(self.screen, self.images, self.thumb_urls, self.selected_idx, self.image_cache)
            self.api_panel.draw(self.screen, self.api_log)
            self.page_navigator.draw(self.screen)
            pygame.display.flip()
            clock.tick(30)
        pygame.quit()

if __name__ == "__main__":
    NasaImageApp()