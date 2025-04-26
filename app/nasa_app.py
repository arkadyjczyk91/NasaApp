import pygame
import sys
import time
import math
import threading
from app.config import BLACK, BLUE, WHITE
from services.api_service import NasaApiService
from services.image_service import ImageService, DetailFetcher
from services.audio_service import AudioPlayer
from services.video_service import VideoPlayer
from ui.screens.search_screen import SearchScreen
from ui.screens.detail_screen import DetailScreen


class NasaApp:
    """Main NASA image search application class."""

    def __init__(self):
        pygame.init()
        pygame.key.set_repeat(400, 50)

        # Display setup
        self.fullscreen = True
        self.default_size = (1280, 800)
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.WIDTH, self.HEIGHT = self.screen.get_size()
        pygame.display.set_caption("NASA Media Explorer")

        # Services
        self.api_service = NasaApiService()
        self.image_service = ImageService()
        self.audio_player = AudioPlayer()
        self.video_player = VideoPlayer()

        # Font setup
        self.fonts = {
            "font": pygame.font.SysFont("Arial", 28),
            "small": pygame.font.SysFont("Consolas", 17),
            "gallery_label": pygame.font.SysFont("Arial", 20, bold=True),
            "gallery_meta": pygame.font.SysFont("Consolas", 15),
            "medium": pygame.font.SysFont("Arial", 22, bold=True),
            "title": pygame.font.SysFont("Arial", 36, bold=True),
            "api": pygame.font.SysFont("Consolas", 16),
            "detail_asset": pygame.font.SysFont("Consolas", 15),
            "label": pygame.font.SysFont("Arial", 18, bold=True)
        }

        # State
        self.lock = threading.Lock()
        self.thread_pool = []
        self.detail_mode = False

        # Screens
        self.search_screen = SearchScreen(self.screen, self.WIDTH, self.HEIGHT, self.fonts,
                                          self.image_service, self.enter_detail)
        self.detail_screen = DetailScreen(self.screen, self.WIDTH, self.HEIGHT, self.fonts,
                                          self.image_service, self.audio_player, self.video_player)

    def enter_detail(self, item):
        """Enter detail view for an item."""
        self.detail_mode = True
        self.detail_screen.set_detail_item(item, DetailFetcher)

    def start_search(self):
        """Start a search with current parameters."""
        keyword = self.search_screen.input_keyword.strip()
        count_str = self.search_screen.input_count.strip()
        media_type = self.search_screen.media_types[self.search_screen.selected_media_type]

        if not keyword:
            self.search_screen.status = "Please enter a keyword"
            return

        count = None
        if count_str:
            try:
                count = int(count_str)
                if count <= 0:
                    self.search_screen.status = "Asset limit must be positive"
                    return
            except ValueError:
                self.search_screen.status = "Asset limit must be a number"
                return

        self.search_screen.loading = True
        self.search_screen.status = "Searching..."

        def on_search_complete(items, api_log, error):
            self.search_screen.set_search_results(items, api_log, error)
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))

        if media_type == "album":
            thread = self.api_service.search_album(keyword, count, on_search_complete)
        else:
            thread = self.api_service.search_media(keyword, count, media_type, on_search_complete)

        self.thread_pool.append(thread)
        self.search_screen.last_fetch_keyword = keyword
        self.search_screen.last_fetch_count = count_str
        self.search_screen.last_fetch_media_type = self.search_screen.selected_media_type

    def resize(self, w, h):
        """Resize the application window."""
        self.WIDTH, self.HEIGHT = w, h
        pygame.display.set_mode((w, h), pygame.RESIZABLE)
        self.search_screen.update_dimensions(w, h)
        self.detail_screen.WIDTH = w
        self.detail_screen.HEIGHT = h

    def handle_common_events(self, event):
        """Handle events common to all screens."""
        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.VIDEORESIZE:
            self.resize(event.w, event.h)
            return True

        if event.type == pygame.KEYDOWN:
            # Toggle fullscreen
            # W metodzie handle_common_events po utworzeniu nowego obiektu screen
            if event.key == pygame.K_F11:
                try:
                    self.fullscreen = not self.fullscreen

                    if self.fullscreen:
                        # Używamy bardziej bezpośredniego podejścia do pełnego ekranu
                        info = pygame.display.Info()
                        self.screen = pygame.display.set_mode(
                            (info.current_w, info.current_h),
                            pygame.FULLSCREEN
                        )
                    else:
                        # Powrót do trybu okienkowego
                        self.screen = pygame.display.set_mode(
                            self.default_size,
                            pygame.RESIZABLE
                        )

                    # Aktualizacja wymiarów i referencji
                    self.WIDTH, self.HEIGHT = self.screen.get_size()

                    # Aktualizacja ekranu w komponentach
                    self.search_screen.screen = self.screen
                    self.search_screen.update_dimensions(self.WIDTH, self.HEIGHT)
                    self.detail_screen.screen = self.screen
                    self.detail_screen.WIDTH = self.WIDTH
                    self.detail_screen.HEIGHT = self.HEIGHT

                    # Wymuszenie aktualizacji ekranu
                    pygame.display.flip()

                    # Krótka pauza dla stabilizacji
                    time.sleep(0.1)

                    return True
                except Exception as e:
                    print(f"Błąd przełączania trybu: {e}")
                    # Awaryjny powrót do trybu okienkowego
                    self.fullscreen = False
                    self.screen = pygame.display.set_mode(self.default_size, pygame.RESIZABLE)
                    self.WIDTH, self.HEIGHT = self.screen.get_size()
                    self.search_screen.screen = self.screen
                    self.search_screen.update_dimensions(self.WIDTH, self.HEIGHT)
                    self.detail_screen.screen = self.screen
                    self.detail_screen.WIDTH = self.HEIGHT
                    return True

            # Force windowed mode
            elif event.key == pygame.K_F12:
                self.fullscreen = False
                self.screen = pygame.display.set_mode(self.default_size, pygame.RESIZABLE)
                self.WIDTH, self.HEIGHT = self.screen.get_size()
                self.search_screen.update_dimensions(self.WIDTH, self.HEIGHT)
                self.detail_screen.WIDTH = self.WIDTH
                self.detail_screen.HEIGHT = self.HEIGHT
                return True

            # Window scaling
            elif event.key in (pygame.K_PLUS, pygame.K_EQUALS) and event.mod & pygame.KMOD_CTRL:
                if not self.fullscreen:
                    w, h = int(self.WIDTH * 1.1), int(self.HEIGHT * 1.1)
                    self.resize(w, h)
                return True
            elif event.key == pygame.K_MINUS and event.mod & pygame.KMOD_CTRL:
                if not self.fullscreen:
                    w, h = int(self.WIDTH / 1.1), int(self.HEIGHT / 1.1)
                    self.resize(w, h)
                return True

        return True

    def run(self):
        """Main application loop."""
        clock = pygame.time.Clock()
        running = True
        redraw = True  # Force initial draw

        # Register a custom event for media playback updates
        MEDIA_TIMER_EVENT = pygame.USEREVENT + 1

        while running:
            # Event handling
            for event in pygame.event.get():
                if not self.handle_common_events(event):
                    running = False
                    break

                # Handle media timer events - always force redraw for these
                if event.type == MEDIA_TIMER_EVENT:
                    redraw = True
                    continue

                if self.detail_mode:
                    result = self.detail_screen.handle_input(event)
                    if result is False:  # Exit detail mode
                        self.detail_mode = False
                    redraw = True
                else:
                    if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                        result = self.search_screen.handle_input(event)
                        if result == "search":
                            self.start_search()
                        elif result and isinstance(result, tuple) and result[0] == "detail":
                            self.enter_detail(result[1])
                        redraw = True
                    elif event.type == pygame.USEREVENT:
                        redraw = True

            # Auto-search handling - make sure this is not removed!
            if not self.detail_mode:
                if (self.search_screen.input_keyword != self.search_screen.last_keyword or
                        self.search_screen.input_count != self.search_screen.last_fetch_count or
                        self.search_screen.selected_media_type != self.search_screen.last_fetch_media_type):

                    self.search_screen.last_keyword = self.search_screen.input_keyword
                    self.search_screen.last_keyword_change = time.time()

                elif (self.search_screen.input_keyword.strip() and
                      (self.search_screen.input_keyword != self.search_screen.last_fetch_keyword or
                       self.search_screen.input_count != self.search_screen.last_fetch_count or
                       self.search_screen.selected_media_type != self.search_screen.last_fetch_media_type)):

                    if time.time() - self.search_screen.last_keyword_change > self.search_screen.fetch_delay:
                        if not self.search_screen.loading:
                            self.start_search()

            # Drawing
            if redraw:
                if self.detail_mode:
                    self.detail_screen.draw()
                else:
                    self.search_screen.draw()

                pygame.display.flip()
                redraw = False  # Reset redraw flag after drawing

            # Cap the frame rate
            clock.tick(30)

        # Cleanup
        self.audio_player.cleanup()
        self.video_player.cleanup()
        pygame.quit()
        sys.exit()
