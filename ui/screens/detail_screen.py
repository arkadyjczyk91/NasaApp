import pygame
import textwrap
import webbrowser
import requests
import math
from io import BytesIO
from PIL import Image
from app.config import BLACK, BLUE, WHITE
from ui.components.scrollable import ScrollableArea
from ui.rendering import render_text
from utils.helpers import shorten_url
from ui.components.media_player import MediaPlayer

class DetailScreen:
    """Screen for displaying detailed information about a NASA item."""

    def __init__(self, screen, width, height, fonts, image_service, audio_player, video_player):
        self.screen = screen
        self.WIDTH = width
        self.HEIGHT = height
        self.fonts = fonts
        self.image_service = image_service
        self.audio_player = audio_player
        self.video_player = video_player

        # Detail view state
        self.detail_item = None
        self.detail_asset = {}
        self.detail_metadata = {}
        self.detail_captions = {}
        self.detail_panel_focus = 0
        self.detail_zoom = 1.0
        self.detail_img_offset = [0, 0]
        self.asset_selected = 0
        self.previous_asset_selected = -1
        self.current_preview_url = None
        self.detail_desc_scroll = None
        self.detail_files_scroll = None
        self.detail_meta_scroll = None
        self.json_scroll = None
        self.status = ""
        self.video_thumbnail = None
        self.preview_loading = False
        self.preview_surface = None

        # Unified media player
        self.media_player = MediaPlayer(screen, fonts, audio_player, video_player)

    def set_detail_item(self, item, detail_fetcher_class):
        """Set the current item for the detail view."""
        self.detail_item = item
        self.detail_asset = {}
        self.detail_metadata = {}
        self.detail_captions = {}
        self.detail_panel_focus = 0
        self.detail_zoom = 1.0
        self.detail_img_offset = [0, 0]
        self.asset_selected = 0
        self.previous_asset_selected = -1
        self.video_thumbnail = None
        self.current_preview_url = None
        self.preview_surface = None
        self.preview_loading = False

        # Reset all scroll areas
        self.detail_desc_scroll = None
        self.detail_files_scroll = None
        self.detail_meta_scroll = None
        self.json_scroll = None

        d = item.get("data", [{}])[0]
        nasa_id = d.get("nasa_id")
        is_video = (d.get("media_type") == "video")

        def on_asset(asset):
            self.detail_asset = asset
            # If this is a video, try to get a thumbnail
            if is_video:
                best_video_url = self.get_best_video_url()
                if best_video_url:
                    self.video_thumbnail = self.video_player.get_thumbnail(best_video_url)
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))

        def on_metadata(metadata):
            self.detail_metadata = metadata
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))

        def on_captions(captions):
            self.detail_captions = captions
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))

        detail_fetcher_class(nasa_id, is_video, on_asset, on_metadata, on_captions).start()


    def _filter_asset_files(self, files):
        """Filter out metadata files from the asset files."""
        if not files:
            return []

        filtered = []
        for file in files:
            url = file.get("href", "")
            filename = url.split("/")[-1].lower()

            # Skip metadata files and other non-content files
            if (filename.endswith(".json") or
                    "metadata" in filename or
                    filename.endswith(".txt") or
                    filename.endswith(".xml")):
                continue

            filtered.append(file)

        return filtered

    def get_best_image_url(self):
        """Get the best available image URL for the current item."""
        best = None
        files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []

        # Prefer original, then large, then any jpg/png
        for suffix in ['~orig.jpg', '~orig.png', '~large.jpg', '~large.png']:
            for f in files:
                if f['href'].endswith(suffix):
                    return f['href']

        for f in files:
            if f['href'].endswith(('.jpg', '.png')):
                best = f['href']

        return best

    def get_file_url_by_index(self, index):
        """Get the URL for a file at the specified index."""
        all_files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []
        files = self._filter_asset_files(all_files)

        if 0 <= index < len(files):
            return files[index].get("href")
        return None

    def get_best_audio_url(self):
        """Get the best available audio URL for the current item."""
        files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []

        for ext in ['~orig.mp3', '~128k.mp3', '.mp3', '.m4a', '.wav']:
            for f in files:
                if f['href'].endswith(ext):
                    return f['href']

        return None

    def get_best_video_url(self):
        """Get the best available video URL for the current item."""
        files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []

        for ext in ['~orig.mp4', '~large.mp4', '.mp4', '.mov', '.avi']:
            for f in files:
                if f['href'].endswith(ext):
                    return f['href']

        return None

    def handle_input(self, event):
        """Handle input events for the detail screen."""
        files = self._filter_asset_files(
            self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else [])

        # Obsługa klawiszy globalnych najpierw
        if event.type == pygame.KEYDOWN:
            # F11 dla trybu pełnoekranowego
            if event.key == pygame.K_F11:
                pygame.event.post(pygame.event.Event(pygame.USEREVENT, {"action": "toggle_fullscreen"}))
                return True

            # Global exit key
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                # If media is playing, stop it instead of exiting
                if self.media_player.is_playing:
                    self.media_player._stop_playback()
                    return True
                return False  # Signal to exit detail mode

        # Handle media player controls
        if self.media_player.handle_event(event):
            return True

        # Obsługa klawiszy nawigacyjnych tylko gdy nie są aktywne media
        if event.type == pygame.KEYDOWN and not self.media_player.is_playing:
            # Zoom controls
            if event.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
                self.detail_zoom = min(self.detail_zoom + 0.2, 4.0)
                return True
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.detail_zoom = max(self.detail_zoom - 0.2, 0.4)
                return True

            # Image panning
            elif event.key == pygame.K_LEFT:
                self.detail_img_offset[0] -= 40
                return True
            elif event.key == pygame.K_RIGHT:
                self.detail_img_offset[0] += 40
                return True

            # File navigation
            elif event.key == pygame.K_UP and files:
                prev_idx = self.asset_selected
                self.asset_selected = (self.asset_selected - 1) % len(files)
                if prev_idx != self.asset_selected:
                    return True
            elif event.key == pygame.K_DOWN and files:
                prev_idx = self.asset_selected
                self.asset_selected = (self.asset_selected + 1) % len(files)
                if prev_idx != self.asset_selected:
                    return True

            # Image position (only if not navigating files)
            elif event.key == pygame.K_UP and not files:
                self.detail_img_offset[1] -= 40
                return True
            elif event.key == pygame.K_DOWN and not files:
                self.detail_img_offset[1] += 40
                return True

            # File actions
            elif event.key == pygame.K_RETURN and files:
                url = files[self.asset_selected].get("href")
                if url:
                    webbrowser.open(url)
                    self.status = f"Opened in browser: {url}"
                return True
            elif event.key == pygame.K_p and files:
                url = files[self.asset_selected].get("href")
                if url:
                    result = self.play_media(url)
                    if result:
                        self.status = result
                return True
            elif event.key == pygame.K_s:
                self.audio_player.stop()
                self.video_player.stop()
                self.status = "Playback stopped"
                return True
            elif event.key == pygame.K_n:
                captloc = self.detail_captions.get("location")
                if captloc:
                    webbrowser.open(captloc)
                    self.status = f"Opening captions: {captloc}"
                return True

        # Handle scrollable area events after keyboard navigation
        if self.detail_desc_scroll and self.detail_desc_scroll.handle_event(event):
            return True
        if self.detail_files_scroll and self.detail_files_scroll.handle_event(event):
            return True
        if self.detail_meta_scroll and self.detail_meta_scroll.handle_event(event):
            return True

        return True  # Stay in detail mode

    def update(self):
        """Update any time-based elements or state changes."""
        files = self._filter_asset_files(
            self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else [])

        # Check if the selected asset changed and needs to be loaded
        if files and self.asset_selected != self.previous_asset_selected:
            self.previous_asset_selected = self.asset_selected

            # Get the URL of the selected file
            url = self.get_file_url_by_index(self.asset_selected)

            if url and url != self.current_preview_url:
                self.current_preview_url = url
                self.preview_surface = None
                self.preview_loading = True

                # Start a new thread to load the preview
                import threading
                thread = threading.Thread(target=self._load_preview_thread, args=(url,))
                thread.daemon = True
                thread.start()

                # Update status
                self.status = f"Loading: {url.split('/')[-1]}"

    def _load_preview_thread(self, url):
        """Thread function to load a preview of the selected asset."""
        try:
            if url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                # Load as image
                self._load_image_preview(url)
            elif url.endswith(('.mp4', '.avi', '.mov', '.webm')):
                # Load as video thumbnail
                self.video_thumbnail = self.video_player.get_thumbnail(url)
            elif url.endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a')):
                # For audio, we just display the player UI
                pass
            else:
                # For other file types, just show file info
                pass

            # Signal that loading is complete
            self.preview_loading = False
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {}))

        except Exception as e:
            print(f"Error loading preview: {str(e)}")
            self.preview_loading = False

    def _load_image_preview(self, url):
        """Load and prepare an image preview."""
        try:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content))
            img = img.convert("RGBA")
            mode = img.mode
            size = img.size
            data = img.tobytes()
            surf = pygame.image.fromstring(data, size, mode)
            self.preview_surface = surf
            self.image_service.image_cache.put(url, surf)
        except Exception as e:
            print(f"Error loading image preview: {str(e)}")

    def play_media(self, url):
        """Play the appropriate media type based on the URL."""
        if url.endswith(('.mp3', '.m4a', '.wav')):
            if self.media_player.play(url, "audio"):
                return f"Playing audio: {url.split('/')[-1]}"
            else:
                return f"Failed to play audio: {url.split('/')[-1]}"
        elif url.endswith(('.mp4', '.mov', '.avi')):
            if self.media_player.play(url, "video"):
                return f"Playing video: {url.split('/')[-1]}"
            else:
                return f"Failed to play video: {url.split('/')[-1]}"
        else:
            return f"Unsupported media type: {url.split('/')[-1]}"

    def draw(self):
        """Draw the detail screen."""
        self.update()
        self.screen.fill(BLACK)
        panel_margin = 30
        panel_width = self.WIDTH - 2 * panel_margin
        y = panel_margin

        # Header with title
        d = self.detail_item.get("data", [{}])[0]
        t = d.get("title", "No title")
        nasa_id = d.get("nasa_id", "")
        media_type = d.get("media_type", "")
        title_surf = render_text(t, self.fonts["title"], BLUE, panel_width)
        self.screen.blit(title_surf, (panel_margin, y))
        y += title_surf.get_height() + 10

        # Layout calculations
        left_width = int(panel_width * 0.65)
        right_width = panel_width - left_width - 20
        left_x = panel_margin
        left_h = self.HEIGHT - y - panel_margin - 40

        # Preview area
        preview_area = pygame.Rect(left_x, y, left_width, left_h)
        pygame.draw.rect(self.screen, (16, 20, 24), preview_area, border_radius=12)
        pygame.draw.rect(self.screen, BLUE, preview_area, 2, border_radius=12)

        # Get files and check if we're viewing a specific file or the main asset
        files = self._filter_asset_files(
            self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else [])
        selected_url = None

        if files and 0 <= self.asset_selected < len(files):
            selected_url = files[self.asset_selected].get("href")

        # Check if media player is currently playing and should overlay the controls
        if self.media_player.is_playing and self.media_player.media_type in ("video", "audio"):
            self.media_player.draw(preview_area)
        elif self.preview_loading:
            loading_text = self.fonts["medium"].render("Loading preview...", True, BLUE)
            self.screen.blit(loading_text, (preview_area.centerx - loading_text.get_width() // 2,
                                            preview_area.centery - loading_text.get_height() // 2))
        elif selected_url and selected_url == self.current_preview_url:
            self._draw_selected_file_preview(selected_url, preview_area)
        else:
            # Default preview (original asset)
            file_url_img = self.get_best_image_url() if media_type == "image" else None
            file_url_audio = self.get_best_audio_url() if media_type == "audio" else None
            file_url_video = self.get_best_video_url() if media_type == "video" else None

            # Display appropriate media type
            if file_url_img:
                self._draw_image_preview(file_url_img, preview_area)
            elif file_url_video:
                self._draw_video_preview(file_url_video, preview_area)
            elif file_url_audio:
                self._draw_audio_player(file_url_audio, preview_area)
            else:
                no_img = self.fonts["medium"].render("No preview available", True, BLUE)
                self.screen.blit(no_img, (preview_area.centerx - no_img.get_width() // 2,
                                          preview_area.centery - no_img.get_height() // 2))

        # Information panels on the right
        right_x = left_x + left_width + 20
        right_y = y
        right_h = left_h

        self._draw_description_panel(right_x, right_y, right_width, right_h * 0.4, d)
        right_y += right_h * 0.4 + 15

        self._draw_files_panel(right_x, right_y, right_width, right_h * 0.25)
        right_y += right_h * 0.25 + 15

        self._draw_metadata_panel(right_x, right_y, right_width, right_h - right_y + y)

        self._draw_navigation_help()

    def _draw_selected_file_preview(self, url, area):
        """Draw a preview of the selected file."""
        if url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            # Image preview
            if self.preview_surface:
                self._draw_surface_in_area(self.preview_surface, area)
            else:
                self._draw_image_preview(url, area)
        elif url.endswith(('.mp4', '.avi', '.mov', '.webm')):
            # Video preview
            if self.video_thumbnail:
                # Calculate position to center the thumbnail
                tx = area.x + (area.width - self.video_thumbnail.get_width()) // 2
                ty = area.y + (area.height - self.video_thumbnail.get_height()) // 2 - 40

                # Draw the thumbnail
                self.screen.blit(self.video_thumbnail, (tx, ty))

                # Draw video info
                video_name = url.split('/')[-1]
                name_surf = self.fonts["medium"].render(video_name, True, BLUE)
                self.screen.blit(name_surf, (area.centerx - name_surf.get_width() // 2,
                                             ty + self.video_thumbnail.get_height() + 10))

                # Draw play button
                play_rect = pygame.Rect(area.centerx - 60, ty + self.video_thumbnail.get_height() + 50, 120, 40)
                pygame.draw.rect(self.screen, (60, 110, 200), play_rect, border_radius=8)
                play_text = self.fonts["medium"].render("Play Video", True, WHITE)
                self.screen.blit(play_text, (play_rect.centerx - play_text.get_width() // 2,
                                             play_rect.centery - play_text.get_height() // 2))

                # Handle clicking the play button
                mouse = pygame.mouse.get_pressed()
                mx, my = pygame.mouse.get_pos()
                if mouse[0]:
                    if play_rect.collidepoint(mx, my):
                        self.video_player.play(url)
            else:
                self._draw_video_player(url, area)
        elif url.endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a')):
            # Audio preview
            self._draw_audio_player(url, area)
        elif url.endswith('.json'):
            # JSON preview (metadata)
            try:
                with requests.get(url) as response:
                    json_data = response.json()
                    json_text = str(json_data)
                    json_surf = render_text(json_text, self.fonts["detail_asset"], BLUE, area.width - 40)

                    # Create scrollable area for JSON content
                    if not self.json_scroll:
                        self.json_scroll = ScrollableArea(area, json_surf)
                    else:
                        self.json_scroll.rect = area
                        self.json_scroll.content = json_surf
                        self.json_scroll.max_scroll = max(0, json_surf.get_height() - area.height)
                        self.json_scroll._update_scrollbar()

                    self.json_scroll.draw(self.screen)
            except Exception:
                no_preview = self.fonts["medium"].render(f"JSON Preview: {url.split('/')[-1]}", True, BLUE)
                self.screen.blit(no_preview, (area.centerx - no_preview.get_width() // 2,
                                              area.centery - no_preview.get_height() // 2))
        else:
            # Generic file info for other types
            file_name = url.split('/')[-1]
            file_ext = file_name.split('.')[-1] if '.' in file_name else "unknown"

            file_info = [
                f"File: {file_name}",
                f"Type: {file_ext.upper()}",
                "No preview available"
            ]

            y_pos = area.centery - 40
            for line in file_info:
                text_surf = self.fonts["medium"].render(line, True, BLUE)
                self.screen.blit(text_surf, (area.centerx - text_surf.get_width() // 2, y_pos))
                y_pos += 30

            # Open button
            open_rect = pygame.Rect(area.centerx - 75, y_pos + 20, 150, 40)
            pygame.draw.rect(self.screen, (60, 110, 200), open_rect, border_radius=8)
            open_text = self.fonts["medium"].render("Open File", True, WHITE)
            self.screen.blit(open_text, (open_rect.centerx - open_text.get_width() // 2,
                                         open_rect.centery - open_text.get_height() // 2))

            # Handle clicking the open button
            mouse = pygame.mouse.get_pressed()
            mx, my = pygame.mouse.get_pos()
            if mouse[0]:
                if open_rect.collidepoint(mx, my):
                    webbrowser.open(url)
                    self.status = f"Opened in browser: {url}"

    def _draw_surface_in_area(self, surface, area):
        """Draw a surface within the provided area with proper scaling."""
        if not surface:
            return

        # Calculate scale to fit within the area while maintaining aspect ratio
        w, h = surface.get_size()
        scale = min(area.width / w, area.height / h, 1.0) * self.detail_zoom

        # Don't scale up tiny images too much
        if scale > 4.0:
            scale = 4.0

        # Calculate new dimensions
        new_w = int(w * scale)
        new_h = int(h * scale)

        # Scale the surface
        try:
            if scale != 1.0:
                scaled_surf = pygame.transform.smoothscale(surface, (new_w, new_h))
            else:
                scaled_surf = surface

            # Calculate position to center in area
            tx = area.x + (area.width - new_w) // 2 + self.detail_img_offset[0]
            ty = area.y + (area.height - new_h) // 2 + self.detail_img_offset[1]

            # Draw
            self.screen.blit(scaled_surf, (tx, ty))

            # Optional: Draw image dimensions
            dim_text = self.fonts["small"].render(f"{w}x{h} ({int(scale * 100)}%)", True, (120, 180, 255))
            self.screen.blit(dim_text, (area.x + 10, area.y + 10))

        except Exception as e:
            print(f"Error scaling image: {str(e)}")

    def _draw_image_preview(self, url, area):
        """Draw the image preview within the given area."""
        surf = self.image_service.image_cache.get(url)
        if not surf:
            try:
                response = requests.get(url)
                img = Image.open(BytesIO(response.content))
                img = img.convert("RGBA")
                mode = img.mode
                size = img.size
                data = img.tobytes()
                surf = pygame.image.fromstring(data, size, mode)
                self.image_service.image_cache.put(url, surf)
            except Exception as e:
                print(f"Error loading image: {str(e)}")
                surf = None

        if surf:
            self._draw_surface_in_area(surf, area)
        else:
            loading = self.fonts["medium"].render("Loading preview...", True, BLUE)
            self.screen.blit(loading, (area.centerx - loading.get_width() // 2,
                                       area.centery - loading.get_height() // 2))

    def _draw_video_preview(self, url, area):
        """Draw a video preview with unified controls."""
        # Check if video is currently playing
        if self.media_player.is_playing and self.media_player.media_type == "video":
            # Video is already playing, draw the player
            self.media_player.draw(area)
        else:
            # Draw video thumbnail with play button
            if self.video_thumbnail:
                # Calculate position to center the thumbnail
                tx = area.x + (area.width - self.video_thumbnail.get_width()) // 2
                ty = area.y + (area.height - self.video_thumbnail.get_height()) // 2 - 40

                # Draw the thumbnail
                self.screen.blit(self.video_thumbnail, (tx, ty))

                # Draw video info
                video_name = url.split('/')[-1]
                name_surf = self.fonts["medium"].render(video_name, True, BLUE)
                self.screen.blit(name_surf, (area.centerx - name_surf.get_width() // 2,
                                             ty + self.video_thumbnail.get_height() + 10))

                # Draw play button
                play_rect = pygame.Rect(area.centerx - 60, ty + self.video_thumbnail.get_height() + 50, 120, 40)
                pygame.draw.rect(self.screen, (60, 110, 200), play_rect, border_radius=8)
                play_text = self.fonts["medium"].render("Play Video", True, WHITE)
                self.screen.blit(play_text, (play_rect.centerx - play_text.get_width() // 2,
                                             play_rect.centery - play_text.get_height() // 2))

                # Handle clicking the play button
                mouse = pygame.mouse.get_pressed()
                mx, my = pygame.mouse.get_pos()
                if mouse[0]:
                    if play_rect.collidepoint(mx, my) and not self.video_player.is_loading:
                        # Start playing the video
                        self.media_player.play(url, "video")
            else:
                # Draw loading or error message
                self._draw_video_player(url, area)

    def _draw_audio_player(self, url, area):
        """Draw audio player with unified controls."""
        # Check if audio is currently playing
        if self.media_player.is_playing and self.media_player.media_type == "audio":
            # Audio is already playing, draw the player
            self.media_player.draw(area)
        else:
            # Draw the standard audio player interface
            box = pygame.Rect(area.x + 60, area.y + area.height // 2 - 46, area.width - 120, 92)
            pygame.draw.rect(self.screen, (18, 30, 38), box, border_radius=18)
            pygame.draw.rect(self.screen, BLUE, box, 3, border_radius=18)

            # File name
            name = url.split("/")[-1]
            name_surf = self.fonts["medium"].render(name, True, BLUE)
            self.screen.blit(name_surf, (box.x + (box.width - name_surf.get_width()) // 2, box.y + 8))

            # Play button with nice styling
            play_rect = pygame.Rect(box.centerx - 30, box.y + 44, 60, 40)
            pygame.draw.rect(self.screen, (60, 110, 200), play_rect, border_radius=8)
            play_text = self.fonts["medium"].render("Play", True, WHITE)
            self.screen.blit(play_text, (play_rect.centerx - play_text.get_width() // 2,
                                         play_rect.centery - play_text.get_height() // 2))

            # Show loading state if applicable
            if self.audio_player.is_loading:
                loading_text = self.fonts["small"].render("Loading...", True, (120, 180, 255))
                self.screen.blit(loading_text, (box.centerx - loading_text.get_width() // 2, box.bottom + 10))

            # Handle clicks
            mouse = pygame.mouse.get_pressed()
            mx, my = pygame.mouse.get_pos()
            if mouse[0]:
                if play_rect.collidepoint(mx, my) and not self.audio_player.is_loading:
                    # Start playing audio with our unified player
                    self.media_player.play(url, "audio")

    def _draw_active_video_player(self, url, area):
        """Draw an active video player with controls."""
        # Draw video frame area
        video_area = pygame.Rect(area.x, area.y, area.width, area.height)  # Używamy wartości z obiektu area
        if self.media_player.media_type == "video" and self.media_player.is_playing:
            self.media_player.draw(video_area)
        pygame.draw.rect(self.screen, (0, 0, 0), video_area)
        pygame.draw.rect(self.screen, BLUE, video_area, 2)

        # Update the video player surface size if needed
        self.video_player.resize(video_area.width, video_area.height)

        # Draw controls area
        controls_y = video_area.bottom + 10
        controls_height = 60
        controls_area = pygame.Rect(area.x + 20, controls_y, area.width - 40, controls_height)
        pygame.draw.rect(self.screen, (18, 30, 38), controls_area, border_radius=8)

        # Play/Pause button
        play_button_size = 40
        play_rect = pygame.Rect(
            controls_area.x + 20,
            controls_area.centery - play_button_size // 2,
            play_button_size,
            play_button_size
        )
        pygame.draw.rect(self.screen, (60, 110, 200), play_rect, border_radius=8)

        # Draw play/pause icon based on state
        if self.video_player.is_playing:
            # Draw pause icon (two vertical bars)
            bar_width = 4
            bar_height = 16
            bar_spacing = 6
            pygame.draw.rect(self.screen, WHITE,
                             (play_rect.centerx - bar_spacing - bar_width // 2,
                              play_rect.centery - bar_height // 2,
                              bar_width, bar_height))
            pygame.draw.rect(self.screen, WHITE,
                             (play_rect.centerx + bar_spacing - bar_width // 2,
                              play_rect.centery - bar_height // 2,
                              bar_width, bar_height))
        else:
            # Draw play icon (triangle)
            points = [
                (play_rect.left + play_rect.width * 0.3, play_rect.top + play_rect.height * 0.2),
                (play_rect.left + play_rect.width * 0.3, play_rect.top + play_rect.height * 0.8),
                (play_rect.left + play_rect.width * 0.8, play_rect.centery)
            ]
            pygame.draw.polygon(self.screen, WHITE, points)

        # Stop button
        stop_rect = pygame.Rect(
            play_rect.right + 15,
            controls_area.centery - play_button_size // 2,
            play_button_size,
            play_button_size
        )
        pygame.draw.rect(self.screen, (180, 40, 40), stop_rect, border_radius=8)

        # Draw stop icon (square)
        stop_icon_size = 14
        pygame.draw.rect(self.screen, WHITE,
                         (stop_rect.centerx - stop_icon_size // 2,
                          stop_rect.centery - stop_icon_size // 2,
                          stop_icon_size, stop_icon_size))

        # Progress bar
        progress_rect = pygame.Rect(
            stop_rect.right + 20,
            controls_area.centery - 6,
            controls_area.right - stop_rect.right - 40,
            12
        )
        pygame.draw.rect(self.screen, (40, 50, 60), progress_rect, border_radius=6)

        # Current progress
        position = self.video_player.get_position()
        if position > 0:
            filled_width = int(progress_rect.width * position)
            progress_filled = pygame.Rect(
                progress_rect.x,
                progress_rect.y,
                filled_width,
                progress_rect.height
            )
            pygame.draw.rect(self.screen, (100, 180, 255), progress_filled, border_radius=6)

        # Handle mouse interaction with controls
        mouse = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        if mouse[0]:
            if play_rect.collidepoint(mx, my):
                if self.video_player.is_playing:
                    self.video_player.pause()
                else:
                    self.video_player.resume()
            elif stop_rect.collidepoint(mx, my):
                self.video_player.stop()
            elif progress_rect.collidepoint(mx, my):
                # Set position based on click
                relative_x = (mx - progress_rect.x) / progress_rect.width
                relative_x = max(0, min(1, relative_x))  # Clamp between 0 and 1
                self.video_player.set_position(relative_x)

    def _draw_active_audio_player(self, url, area):
        """Draw an active audio player with controls."""
        # Draw audio player area with visualizer
        audio_area = pygame.Rect(area.x + 20, area.y + 20, area.width - 40, area.height - 100)
        pygame.draw.rect(self.screen, (14, 18, 24), audio_area, border_radius=12)
        pygame.draw.rect(self.screen, BLUE, audio_area, 2, border_radius=12)

        # Draw audio visualization (simple waveform or spectrum)
        self._draw_audio_visualization(audio_area)

        # Draw file info
        name = url.split("/")[-1]
        name_surf = self.fonts["medium"].render(name, True, BLUE)
        self.screen.blit(name_surf, (audio_area.centerx - name_surf.get_width() // 2, audio_area.y + 30))

        # Status text
        status = "PLAYING" if not self.audio_player.paused else "PAUSED"
        status_surf = self.fonts["medium"].render(status, True,
                                                  (100, 255, 100) if not self.audio_player.paused else (255, 200, 100))
        self.screen.blit(status_surf, (audio_area.centerx - status_surf.get_width() // 2, audio_area.centery - 20))

        # Draw controls area
        controls_y = audio_area.bottom + 10
        controls_height = 60
        controls_area = pygame.Rect(area.x + 20, controls_y, area.width - 40, controls_height)
        pygame.draw.rect(self.screen, (18, 30, 38), controls_area, border_radius=8)

        # Play/Pause button
        play_button_size = 40
        play_rect = pygame.Rect(
            controls_area.x + 20,
            controls_area.centery - play_button_size // 2,
            play_button_size,
            play_button_size
        )
        pygame.draw.rect(self.screen, (60, 110, 200), play_rect, border_radius=8)

        # Draw play/pause icon based on state
        if not self.audio_player.paused:
            # Draw pause icon (two vertical bars)
            bar_width = 4
            bar_height = 16
            bar_spacing = 6
            pygame.draw.rect(self.screen, WHITE,
                             (play_rect.centerx - bar_spacing - bar_width // 2,
                              play_rect.centery - bar_height // 2,
                              bar_width, bar_height))
            pygame.draw.rect(self.screen, WHITE,
                             (play_rect.centerx + bar_spacing - bar_width // 2,
                              play_rect.centery - bar_height // 2,
                              bar_width, bar_height))
        else:
            # Draw play icon (triangle)
            points = [
                (play_rect.left + play_rect.width * 0.3, play_rect.top + play_rect.height * 0.2),
                (play_rect.left + play_rect.width * 0.3, play_rect.top + play_rect.height * 0.8),
                (play_rect.left + play_rect.width * 0.8, play_rect.centery)
            ]
            pygame.draw.polygon(self.screen, WHITE, points)

        # Stop button
        stop_rect = pygame.Rect(
            play_rect.right + 15,
            controls_area.centery - play_button_size // 2,
            play_button_size,
            play_button_size
        )
        pygame.draw.rect(self.screen, (180, 40, 40), stop_rect, border_radius=8)

        # Draw stop icon (square)
        stop_icon_size = 14
        pygame.draw.rect(self.screen, WHITE,
                         (stop_rect.centerx - stop_icon_size // 2,
                          stop_rect.centery - stop_icon_size // 2,
                          stop_icon_size, stop_icon_size))

        # Progress bar
        progress_rect = pygame.Rect(
            stop_rect.right + 20,
            controls_area.centery - 6,
            controls_area.right - stop_rect.right - 40,
            12
        )
        pygame.draw.rect(self.screen, (40, 50, 60), progress_rect, border_radius=6)

        # Current progress
        position = self.audio_player.get_position()
        if position > 0:
            filled_width = int(progress_rect.width * position)
            progress_filled = pygame.Rect(
                progress_rect.x,
                progress_rect.y,
                filled_width,
                progress_rect.height
            )
            pygame.draw.rect(self.screen, (100, 180, 255), progress_filled, border_radius=6)

        # Handle mouse interaction with controls
        mouse = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        if mouse[0]:
            if play_rect.collidepoint(mx, my):
                if self.audio_player.paused:
                    self.audio_player.resume()
                else:
                    self.audio_player.pause()
            elif stop_rect.collidepoint(mx, my):
                self.audio_player.stop()
            elif progress_rect.collidepoint(mx, my):
                # Set position based on click
                relative_x = (mx - progress_rect.x) / progress_rect.width
                relative_x = max(0, min(1, relative_x))  # Clamp between 0 and 1
                self.audio_player.set_position(relative_x)

    def _draw_audio_visualization(self, area):
        """Draw a simple audio visualization based on playback state."""
        # Generate a simple visualization based on playback position
        position = self.audio_player.get_position()

        # Parameters for visualization
        bar_count = 20
        max_height = area.height * 0.6

        # Start position for bars
        start_x = area.x + 30
        bar_width = (area.width - 60) / bar_count
        start_y = area.centery + 40

        # Draw each bar with height based on sin wave and position
        for i in range(bar_count):
            if self.audio_player.paused:
                # Static bars when paused
                height = max_height * 0.2 * abs(((i % 5) / 5) - 0.5)
            else:
                # Animated bars when playing
                phase = position * 10 + i / bar_count
                height = max_height * 0.3 * (0.6 + 0.4 * abs(math.sin(phase * math.pi * 2)))

            bar_rect = pygame.Rect(
                start_x + i * bar_width + 2,
                start_y - height,
                bar_width - 4,
                height
            )

            # Color gradient based on position
            color_intensity = 150 + int(100 * (i / bar_count))
            bar_color = (60, min(255, color_intensity), min(255, color_intensity + 50))

            pygame.draw.rect(self.screen, bar_color, bar_rect, border_radius=3)

    def _draw_video_player(self, url, area):
        """Draw video player controls within the given area."""
        box = pygame.Rect(area.x + 60, area.y + area.height // 2 - 46, area.width - 120, 92)
        pygame.draw.rect(self.screen, (18, 30, 38), box, border_radius=18)
        pygame.draw.rect(self.screen, BLUE, box, 3, border_radius=18)

        # File name
        name = url.split("/")[-1]
        name_surf = self.fonts["medium"].render(name, True, BLUE)
        self.screen.blit(name_surf, (box.x + (box.width - name_surf.get_width()) // 2, box.y + 8))

        # Play button
        play_rect = pygame.Rect(box.x + box.width // 2 - 19, box.y + 44, 38, 38)

        # Show different colors based on loading state
        if self.video_player.is_loading:
            pygame.draw.rect(self.screen, (60, 70, 100), play_rect, border_radius=8)  # Darker when loading
            loading_text = self.fonts["small"].render("Loading video...", True, WHITE)
            self.screen.blit(loading_text, (box.centerx - loading_text.get_width() // 2, box.y + 70))
        else:
            pygame.draw.rect(self.screen, (60, 110, 200), play_rect, border_radius=8)  # Normal color

        ptxt = self.fonts["medium"].render("▶", True, WHITE)
        self.screen.blit(ptxt, (play_rect.centerx - ptxt.get_width() // 2, play_rect.centery - ptxt.get_height() // 2))

        # Loading message for thumbnail
        if url and not self.video_thumbnail:
            loading_text = self.fonts["small"].render("Loading thumbnail...", True, (120, 180, 255))
            self.screen.blit(loading_text, (box.centerx - loading_text.get_width() // 2, box.y - 25))

        # Handle clicks
        mouse = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        if mouse[0]:
            if play_rect.collidepoint(mx, my) and not self.video_player.is_loading:
                self.video_player.play(url)

    def _draw_description_panel(self, x, y, width, height, data):
        """Draw the description panel."""
        desc = data.get("description", "No description available")
        desc_title = self.fonts["medium"].render("Description:", True, BLUE)
        self.screen.blit(desc_title, (x, y))
        y += desc_title.get_height() + 5

        # Description scrollable area
        desc_rect = pygame.Rect(x, y, width, height - desc_title.get_height() - 5)
        pygame.draw.rect(self.screen, (14, 18, 24), desc_rect, border_radius=8)

        # Render description as scrollable text
        desc_content = render_text(desc, self.fonts["small"], BLUE, width - 20)
        if self.detail_desc_scroll is None:
            self.detail_desc_scroll = ScrollableArea(desc_rect, desc_content)
        else:
            self.detail_desc_scroll.rect = desc_rect
            self.detail_desc_scroll.content = desc_content
            self.detail_desc_scroll.max_scroll = max(0, desc_content.get_height() - desc_rect.height)
            self.detail_desc_scroll._update_scrollbar()

        self.detail_desc_scroll.draw(self.screen)

    def _draw_files_panel(self, x, y, width, height):
        """Draw the files panel."""
        files_title = self.fonts["medium"].render("Asset Files:", True, BLUE)
        self.screen.blit(files_title, (x, y))
        y += files_title.get_height() + 5

        # Files scrollable area
        files_rect = pygame.Rect(x, y, width, height - files_title.get_height() - 5)
        pygame.draw.rect(self.screen, (14, 18, 24), files_rect, border_radius=8)

        # Get files and filter out metadata files
        all_files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []
        files = self._filter_asset_files(all_files)

        if files:
            # Create single surface with all files
            files_content_height = max(files_rect.height, len(files) * 20 + 10)
            files_content = pygame.Surface((width - 20, files_content_height), pygame.SRCALPHA)
            files_content.fill((0, 0, 0, 0))

            for j, f in enumerate(files):
                url = f.get("href", "")
                filename = url.split("/")[-1] if url else "-"

                # Determine if this file is being previewed
                is_previewed = url == self.current_preview_url

                # Choose color based on selection and preview state
                if self.asset_selected == j:
                    if is_previewed:
                        color = (100, 255, 100)  # Bright green when selected and previewed
                    else:
                        color = BLUE  # Blue when just selected
                else:
                    if is_previewed:
                        color = (80, 180, 80)  # Darker green when just previewed
                    else:
                        color = (180, 220, 255)  # Default color

                file_surf = self.fonts["detail_asset"].render(shorten_url(filename, 38), True, color)

                # Highlight selected file with background
                if self.asset_selected == j:
                    select_rect = pygame.Rect(0, j * 20, width - 30, 20)
                    pygame.draw.rect(files_content, (30, 40, 60), select_rect)
                    pygame.draw.rect(files_content, BLUE, select_rect, 1)

                files_content.blit(file_surf, (10, j * 20 + 5))
        else:
            files_content = pygame.Surface((width - 20, files_rect.height), pygame.SRCALPHA)
            files_content.fill((0, 0, 0, 0))
            no_files = self.fonts["detail_asset"].render("No files available.", True, BLUE)
            files_content.blit(no_files, (10, 10))

        # Create scrollable area for files
        if self.detail_files_scroll is None:
            self.detail_files_scroll = ScrollableArea(files_rect, files_content)
        else:
            self.detail_files_scroll.rect = files_rect
            self.detail_files_scroll.content = files_content
            self.detail_files_scroll.max_scroll = max(0, files_content.get_height() - files_rect.height)

            # Make sure selected item is visible
            if files and self.asset_selected >= 0:
                item_y = self.asset_selected * 20
                view_top = self.detail_files_scroll.scroll_pos
                view_bottom = view_top + files_rect.height

                if item_y < view_top:
                    # Item is above current view
                    self.detail_files_scroll.scroll_pos = item_y
                    self.detail_files_scroll._update_scrollbar()
                elif item_y + 20 > view_bottom:
                    # Item is below current view
                    self.detail_files_scroll.scroll_pos = item_y + 20 - files_rect.height
                    self.detail_files_scroll._update_scrollbar()

        self.detail_files_scroll.draw(self.screen)

    def _draw_metadata_panel(self, x, y, width, height):
        """Draw the metadata panel."""
        meta_title = self.fonts["medium"].render("Metadata:", True, BLUE)
        self.screen.blit(meta_title, (x, y))
        y += meta_title.get_height() + 5

        # Metadata scrollable area
        meta_rect = pygame.Rect(x, y, width, height - meta_title.get_height() - 5)
        pygame.draw.rect(self.screen, (14, 18, 24), meta_rect, border_radius=8)

        # Render metadata
        md = self.detail_metadata if self.detail_metadata else {}

        # Use data from detail_item if available
        if self.detail_item and "data" in self.detail_item and self.detail_item["data"]:
            item_data = self.detail_item["data"][0]
            # Add any missing metadata from item_data
            for key, value in item_data.items():
                if key not in md and key not in ["title", "description"]:
                    md[key] = value

        if md:
            # Create surface with all metadata
            keys = ["center", "nasa_id", "date_created", "secondary_creator", "photographer",
                    "location", "album", "source", "rights", "keywords"]
            metadata_lines = []

            for k in keys:
                v = md.get(k)
                if v:
                    if isinstance(v, list):
                        v = ", ".join(str(item) for item in v)
                    metadata_lines.append(f"{k}: {v}")

            # Calculate content height based on line wrapping
            total_height = 10  # Initial padding
            for line in metadata_lines:
                wrapped = textwrap.wrap(line, width=width // 9)
                total_height += len(wrapped) * 20

            # Ensure minimum height
            total_height = max(total_height + 10, meta_rect.height)

            if not metadata_lines:
                metadata_content = pygame.Surface((width - 20, meta_rect.height), pygame.SRCALPHA)
                metadata_content.fill((0, 0, 0, 0))
                no_meta = self.fonts["detail_asset"].render("No metadata available.", True, BLUE)
                metadata_content.blit(no_meta, (10, 10))
            else:
                metadata_content = pygame.Surface((width - 20, total_height), pygame.SRCALPHA)
                metadata_content.fill((0, 0, 0, 0))

                y_pos = 5
                for i, line in enumerate(metadata_lines):
                    # Wrap long lines
                    wrapped = textwrap.wrap(line, width=width // 9)
                    for j, wrap_line in enumerate(wrapped):
                        line_surf = self.fonts["detail_asset"].render(wrap_line, True, (180, 220, 255))
                        metadata_content.blit(line_surf, (10, y_pos))
                        y_pos += 20
        else:
            metadata_content = pygame.Surface((width - 20, meta_rect.height), pygame.SRCALPHA)
            metadata_content.fill((0, 0, 0, 0))
            no_meta = self.fonts["detail_asset"].render("No metadata available.", True, BLUE)
            metadata_content.blit(no_meta, (10, 10))

        # Create scrollable area for metadata
        if self.detail_meta_scroll is None:
            self.detail_meta_scroll = ScrollableArea(meta_rect, metadata_content)
        else:
            self.detail_meta_scroll.rect = meta_rect
            self.detail_meta_scroll.content = metadata_content
            self.detail_meta_scroll.max_scroll = max(0, metadata_content.get_height() - meta_rect.height)
            self.detail_meta_scroll._update_scrollbar()

        self.detail_meta_scroll.draw(self.screen)

    def _draw_navigation_help(self):
        """Draw navigation help at the bottom of the screen."""
        d = self.detail_item.get("data", [{}])[0]
        media_type = d.get("media_type", "")

        # Customize help text based on playback state
        if self.video_player.is_playing:
            nav_text = "Space pause/play | ←/→ seek -/+ 10sec | S stop | ESC stop video"
        elif self.audio_player.playing:
            nav_text = "Space pause/play | ←/→ seek -/+ 10sec | S stop | ESC stop audio"
        else:
            nav_text = "ESC exit | +/- zoom | ←/→/↑/↓ navigation | ↑/↓ select file | "
            if media_type == "audio":
                nav_text += "P play audio | S stop | "
            elif media_type == "video":
                nav_text += "P play video | "
            nav_text += "Enter open in browser | PageUp/Down scroll description"

        nav_surf = self.fonts["small"].render(nav_text, True, (120, 180, 255))
        nav_width = nav_surf.get_width()

        if nav_width > self.WIDTH - 20:  # If text is too long
            # Split instructions into two lines
            if self.video_player.is_playing:
                nav_text1 = "Space pause/play | ←/→ seek -/+ 10sec"
                nav_text2 = "S stop | ESC stop video"
            elif self.audio_player.playing:
                nav_text1 = "Space pause/play | ←/→ seek -/+ 10sec"
                nav_text2 = "S stop | ESC stop audio"
            else:
                nav_text1 = "ESC exit | +/- zoom | ←/→/↑/↓ navigation | ↑/↓ select file"
                nav_text2 = "P play media | S stop | Enter open in browser | PageUp/Down scroll description"

            nav_surf1 = self.fonts["small"].render(nav_text1, True, (120, 180, 255))
            nav_surf2 = self.fonts["small"].render(nav_text2, True, (120, 180, 255))
            self.screen.blit(nav_surf1, (self.WIDTH // 2 - nav_surf1.get_width() // 2, self.HEIGHT - 60))
            self.screen.blit(nav_surf2, (self.WIDTH // 2 - nav_surf2.get_width() // 2, self.HEIGHT - 38))
        else:
            self.screen.blit(nav_surf, (self.WIDTH // 2 - nav_surf.get_width() // 2, self.HEIGHT - 38))