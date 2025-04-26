import textwrap

import pygame
import requests
from io import BytesIO
from PIL import Image
import webbrowser

from constants import BLACK, BLUE
from utils.text_renderer import render_text


class DetailView:
    """Component for displaying detailed information about a NASA asset."""

    def __init__(self, width, height, fonts, image_cache, audio_player, video_player):
        """Initialize the detail view with resources and dependencies."""
        self.width = width
        self.height = height
        self.fonts = fonts
        self.image_cache = image_cache
        self.audio_player = audio_player
        self.video_player = video_player

        # State
        self.detail_item = None
        self.detail_asset = {}
        self.detail_metadata = {}
        self.detail_captions = {}
        self.detail_zoom = 1.0
        self.detail_img_offset = [0, 0]
        self.asset_selected = 0
        self.status = ""

        # Scrollable areas
        self.desc_scroll = None
        self.files_scroll = None
        self.meta_scroll = None

    def get_best_image_url(self):
        """Get the best quality image URL from the asset data."""
        files = self.detail_asset.get("collection", {}).get("items", [])

        # Prefer original, then large, then any jpg/png
        for suffix in ['~orig.jpg', '~orig.png', '~large.jpg', '~large.png']:
            for f in files:
                if f['href'].endswith(suffix):
                    return f['href']

        for f in files:
            if f['href'].endswith(('.jpg', '.png')):
                return f['href']

        return None

    def get_best_audio_url(self):
        """Get the best quality audio URL from the asset data."""
        files = self.detail_asset.get("collection", {}).get("items", [])

        for ext in ['~orig.mp3', '~128k.mp3', '.mp3', '.m4a', '.wav']:
            for f in files:
                if f['href'].endswith(ext):
                    return f['href']

        return None

    def get_best_video_url(self):
        """Get the best quality video URL from the asset data."""
        files = self.detail_asset.get("collection", {}).get("items", [])

        for ext in ['~orig.mp4', '~large.mp4', '.mp4', '.mov', '.avi']:
            for f in files:
                if f['href'].endswith(ext):
                    return f['href']

        return None

    def load_asset(self, item, asset, metadata, captions):
        """Load asset data for display."""
        self.detail_item = item
        self.detail_asset = asset
        self.detail_metadata = metadata
        self.detail_captions = captions
        self.detail_zoom = 1.0
        self.detail_img_offset = [0, 0]
        self.asset_selected = 0

        # Reset scroll areas
        self.desc_scroll = None
        self.files_scroll = None
        self.meta_scroll = None

    def draw(self, screen, scrollable_class):
        """Draw the detail view to the screen."""
        screen.fill(BLACK)

        panel_margin = 30
        panel_width = self.width - 2 * panel_margin
        y = panel_margin

        # Get item data
        d = self.detail_item.get("data", [{}])[0]
        t = d.get("title", "No title")
        nasa_id = d.get("nasa_id", "")
        media_type = d.get("media_type", "")

        # Draw title
        title_surf = render_text(t, self.fonts["title"], BLUE, panel_width)
        screen.blit(title_surf, (panel_margin, y))
        y += title_surf.get_height() + 10

        # Calculate panel dimensions
        left_width = int(panel_width * 0.65)
        right_width = panel_width - left_width - 20
        left_x = panel_margin
        left_h = self.height - y - panel_margin - 40

        # Draw preview area
        preview_area = pygame.Rect(left_x, y, left_width, left_h)
        pygame.draw.rect(screen, (16, 20, 24), preview_area, border_radius=12)
        pygame.draw.rect(screen, BLUE, preview_area, 2, border_radius=12)

        # Draw appropriate content based on media type
        file_url_img = self.get_best_image_url() if media_type == "image" else None
        file_url_audio = self.get_best_audio_url() if media_type == "audio" else None
        file_url_video = self.get_best_video_url() if media_type == "video" else None

        # Handle image display
        if file_url_img:
            self._draw_image_preview(screen, file_url_img, preview_area)
        # Handle audio player
        elif file_url_audio:
            self._draw_audio_player(screen, file_url_audio, preview_area)
        # Handle video player
        elif file_url_video:
            self._draw_video_player(screen, file_url_video, preview_area)
        # No preview available
        else:
            no_img = self.fonts["medium"].render("No preview available", True, BLUE)
            screen.blit(no_img, (preview_area.centerx - no_img.get_width() // 2,
                                 preview_area.centery - no_img.get_height() // 2))

        # Right panel for description and files
        right_x = left_x + left_width + 20
        right_y = y

        # Description section
        self._draw_description_section(screen, d, right_x, right_y, right_width, left_h, scrollable_class)

        # Draw bottom navigation help
        self._draw_navigation_help(screen)

    def _draw_image_preview(self, screen, url, preview_area):
        """Draw the image preview in the detail view."""
        surf = self.image_cache.get(url)
        if not surf:
            try:
                response = requests.get(url)
                img = Image.open(BytesIO(response.content))
                img = img.convert("RGBA")
                w, h = img.size
                scale = min(preview_area.width / w, preview_area.height / h, 1.0) * self.detail_zoom
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                mode = img.mode
                size = img.size
                data = img.tobytes()
                surf = pygame.image.fromstring(data, size, mode)
                self.image_cache.put(url, surf)
            except Exception:
                surf = None

        if surf:
            # Apply offset and center the image
            tx = preview_area.x + (preview_area.width - surf.get_width()) // 2 + self.detail_img_offset[0]
            ty = preview_area.y + (preview_area.height - surf.get_height()) // 2 + self.detail_img_offset[1]
            screen.blit(surf, (tx, ty))
        else:
            loading = self.fonts["medium"].render("Loading preview...", True, BLUE)
            screen.blit(loading, (preview_area.centerx - loading.get_width() // 2,
                                  preview_area.centery - loading.get_height() // 2))

    def _draw_audio_player(self, screen, url, preview_area):
        """Draw the audio player controls."""
        # Audio player box
        box = pygame.Rect(preview_area.x + 60, preview_area.y + preview_area.height // 2 - 46,
                          preview_area.width - 120, 92)
        pygame.draw.rect(screen, (18, 30, 38), box, border_radius=18)
        pygame.draw.rect(screen, BLUE, box, 3, border_radius=18)

        # File name
        name = url.split("/")[-1]
        name_surf = self.fonts["medium"].render(name, True, BLUE)
        screen.blit(name_surf, (box.x + (box.width - name_surf.get_width()) // 2, box.y + 8))

        # Play/Stop buttons
        play_rect = pygame.Rect(box.x + box.width // 2 - 45, box.y + 44, 38, 38)
        stop_rect = pygame.Rect(box.x + box.width // 2 + 15, box.y + 44, 38, 38)
        pygame.draw.rect(screen, (60, 110, 200), play_rect, border_radius=8)
        pygame.draw.rect(screen, (100, 40, 40), stop_rect, border_radius=8)

        ptxt = self.fonts["medium"].render("▶", True, (250, 250, 240))
        stxt = self.fonts["medium"].render("■", True, (250, 250, 240))
        screen.blit(ptxt, (play_rect.centerx - ptxt.get_width() // 2, play_rect.centery - ptxt.get_height() // 2))
        screen.blit(stxt, (stop_rect.centerx - stxt.get_width() // 2, stop_rect.centery - stxt.get_height() // 2))

        # Handle clicks
        mouse = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        if mouse[0]:
            if play_rect.collidepoint(mx, my):
                self.audio_player.play(url)
                self.status = "Playing audio"
            if stop_rect.collidepoint(mx, my):
                self.audio_player.stop()
                self.status = "Audio stopped"

    def _draw_video_player(self, screen, url, preview_area):
        """Draw the video player controls."""
        # Video player box
        box = pygame.Rect(preview_area.x + 60, preview_area.y + preview_area.height // 2 - 46,
                          preview_area.width - 120, 92)
        pygame.draw.rect(screen, (18, 30, 38), box, border_radius=18)
        pygame.draw.rect(screen, BLUE, box, 3, border_radius=18)

        # File name
        name = url.split("/")[-1]
        name_surf = self.fonts["medium"].render(name, True, BLUE)
        screen.blit(name_surf, (box.x + (box.width - name_surf.get_width()) // 2, box.y + 8))

        # Play button
        play_rect = pygame.Rect(box.x + box.width // 2 - 19, box.y + 44, 38, 38)
        pygame.draw.rect(screen, (60, 110, 200), play_rect, border_radius=8)
        ptxt = self.fonts["medium"].render("▶", True, (250, 250, 240))
        screen.blit(ptxt, (play_rect.centerx - ptxt.get_width() // 2, play_rect.centery - ptxt.get_height() // 2))

        # Handle clicks
        mouse = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        if mouse[0]:
            if play_rect.collidepoint(mx, my):
                success = self.video_player.play(url)
                self.status = "Opening video player" if success else "Error playing video"

    def _draw_description_section(self, screen, d, right_x, right_y, right_width, right_h, ScrollableArea):
        """Draw the description, files list, and metadata sections."""
        # Description title
        desc = d.get("description", "No description")
        desc_title = self.fonts["medium"].render("Description:", True, BLUE)
        screen.blit(desc_title, (right_x, right_y))
        right_y += desc_title.get_height() + 5

        # Description area
        desc_height = int(right_h * 0.4)
        desc_rect = pygame.Rect(right_x, right_y, right_width, desc_height)
        pygame.draw.rect(screen, (14, 18, 24), desc_rect, border_radius=8)

        # Render description content
        desc_content = render_text(desc, self.fonts["small"], BLUE, right_width - 20)

        # Create or update scrollable area
        if not self.desc_scroll:
            self.desc_scroll = ScrollableArea(desc_rect, desc_content)
        else:
            self.desc_scroll.rect = desc_rect
            self.desc_scroll.content = desc_content
            self.desc_scroll.max_scroll = max(0, desc_content.get_height() - desc_rect.height)
            self.desc_scroll._update_scrollbar()

        self.desc_scroll.draw(screen)
        right_y += desc_height + 15

        # Files list
        self._draw_files_list(screen, right_x, right_y, right_width, right_h, ScrollableArea)

    def _draw_files_list(self, screen, right_x, right_y, right_width, right_h, ScrollableArea):
        """Draw the files list section."""
        # Files title
        files_title = self.fonts["medium"].render("Asset files:", True, BLUE)
        screen.blit(files_title, (right_x, right_y))
        right_y += files_title.get_height() + 5

        # Files area
        files_height = int(right_h * 0.25)
        files_rect = pygame.Rect(right_x, right_y, right_width, files_height)
        pygame.draw.rect(screen, (14, 18, 24), files_rect, border_radius=8)

        # Get files list
        files = self.detail_asset.get("collection", {}).get("items", [])

        if files:
            # Create files content surface
            files_content_height = len(files) * 20 + 10
            files_content = pygame.Surface((right_width - 20, files_content_height), pygame.SRCALPHA)
            files_content.fill((0, 0, 0, 0))

            # Draw each file entry
            for j, f in enumerate(files):
                url = f.get("href", "")
                filename = url.split("/")[-1] if url else "-"
                color = BLUE if self.asset_selected == j else (180, 220, 255)

                # Highlight selected file
                if self.asset_selected == j:
                    select_rect = pygame.Rect(0, j * 20, right_width - 30, 20)
                    pygame.draw.rect(files_content, (30, 40, 60), select_rect)
                    pygame.draw.rect(files_content, BLUE, select_rect, 1)

                # Draw filename
                file_surf = self.fonts["detail_asset"].render(self._shorten_url(filename, 38), True, color)
                files_content.blit(file_surf, (10, j * 20 + 5))
        else:
            # No files message
            files_content = self.fonts["detail_asset"].render("No files available.", True, BLUE)

        # Create or update scrollable area
        if not self.files_scroll:
            self.files_scroll = ScrollableArea(files_rect, files_content)
        else:
            self.files_scroll.rect = files_rect
            self.files_scroll.content = files_content
            self.files_scroll.max_scroll = max(0, files_content.get_height() - files_rect.height)
            self.files_scroll._update_scrollbar()

        self.files_scroll.draw(screen)
        right_y += files_height + 15

        # Metadata section
        self._draw_metadata(screen, right_x, right_y, right_width, right_h, ScrollableArea)

    def _draw_metadata(self, screen, right_x, right_y, right_width, right_h, ScrollableArea):
        """Draw the metadata section."""
        # Metadata title
        meta_title = self.fonts["medium"].render("Metadata:", True, BLUE)
        screen.blit(meta_title, (right_x, right_y))
        right_y += meta_title.get_height() + 5

        # Metadata area
        meta_height = right_h - (right_y - (self.height - right_h - 40 - 30))
        meta_rect = pygame.Rect(right_x, right_y, right_width, meta_height)
        pygame.draw.rect(screen, (14, 18, 24), meta_rect, border_radius=8)

        # Get metadata
        md = self.detail_metadata if self.detail_metadata else {}

        if md:
            # Relevant metadata keys
            keys = ["center", "nasa_id", "date_created", "secondary_creator", "photographer",
                    "location", "album", "source", "rights", "keywords"]
            metadata_lines = []

            # Collect available metadata
            for k in keys:
                v = md.get(k)
                if v:
                    if isinstance(v, list):
                        v = ", ".join(str(item) for item in v)
                    metadata_lines.append(f"{k}: {v}")

            if not metadata_lines:
                metadata_content = self.fonts["detail_asset"].render("No metadata available.", True, BLUE)
            else:
                # Create metadata content surface
                md_height = len(metadata_lines) * 20 + 10
                metadata_content = pygame.Surface((right_width - 20, md_height), pygame.SRCALPHA)
                metadata_content.fill((0, 0, 0, 0))

                # Draw each metadata line
                line_y = 5
                for i, line in enumerate(metadata_lines):
                    # Wrap long lines
                    wrapped = textwrap.wrap(line, width=right_width // 9)
                    for wrap_line in wrapped:
                        line_surf = self.fonts["detail_asset"].render(wrap_line, True, (180, 220, 255))
                        metadata_content.blit(line_surf, (10, line_y))
                        line_y += 20
        else:
            metadata_content = self.fonts["detail_asset"].render("No metadata available.", True, BLUE)

        # Create or update scrollable area
        if not self.meta_scroll:
            self.meta_scroll = ScrollableArea(meta_rect, metadata_content)
        else:
            self.meta_scroll.rect = meta_rect
            self.meta_scroll.content = metadata_content
            self.meta_scroll.max_scroll = max(0, metadata_content.get_height() - meta_rect.height)
            self.meta_scroll._update_scrollbar()

        self.meta_scroll.draw(screen)

    def _draw_navigation_help(self, screen):
        """Draw help text for navigating the detail view."""
        # Get media type for context-sensitive instructions
        media_type = self.detail_item.get("data", [{}])[0].get("media_type", "")

        # Create navigation help text
        nav_text = "ESC exit | +/- zoom | ←/→/↑/↓ move | ↑/↓ select file | "
        if media_type == "audio":
            nav_text += "P play audio | S stop | "
        elif media_type == "video":
            nav_text += "P play video | "
        nav_text += "Enter open in browser | PageUp/Down scroll description"

        nav_surf = self.fonts["small"].render(nav_text, True, (120, 180, 255))
        nav_width = nav_surf.get_width()

        if nav_width > self.width - 20:  # If text is too wide
            # Split instructions into two lines
            nav_text1 = "ESC exit | +/- zoom | ←/→/↑/↓ move | ↑/↓ select file"
            nav_text2 = "P play media | S stop | Enter open in browser | PageUp/Down scroll description"
            nav_surf1 = self.fonts["small"].render(nav_text1, True, (120, 180, 255))
            nav_surf2 = self.fonts["small"].render(nav_text2, True, (120, 180, 255))
            screen.blit(nav_surf1, (self.width // 2 - nav_surf1.get_width() // 2, self.height - 60))
            screen.blit(nav_surf2, (self.width // 2 - nav_surf2.get_width() // 2, self.height - 38))
        else:
            screen.blit(nav_surf, (self.width // 2 - nav_surf.get_width() // 2, self.height - 38))

    def _shorten_url(self, url, maxlen=46):
        """Shorten a URL for display purposes."""
        if len(url) <= maxlen:
            return url
        return url[:maxlen // 2 - 2] + "..." + url[-maxlen // 2 + 2:]

    def handle_key(self, event, pygame):
        """Handle keyboard input for the detail view."""
        files = self.detail_asset.get("collection", {}).get("items", [])
        media_type = self.detail_item.get("data", [{}])[0].get("media_type", "")

        # Exit detail view
        if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            return "exit"

        # Zoom controls
        if event.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
            self.detail_zoom = min(self.detail_zoom + 0.2, 4.0)
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.detail_zoom = max(self.detail_zoom - 0.2, 0.4)

        # Scrolling controls for description
        elif event.key == pygame.K_PAGEUP and self.desc_scroll:
            self.desc_scroll.scroll_up()
        elif event.key == pygame.K_PAGEDOWN and self.desc_scroll:
            self.desc_scroll.scroll_down()

        # Image movement or file selection
        elif event.key == pygame.K_LEFT:
            self.detail_img_offset[0] -= 40
        elif event.key == pygame.K_RIGHT:
            self.detail_img_offset[0] += 40
        elif event.key == pygame.K_UP:
            if files:
                self.asset_selected = (self.asset_selected - 1) % len(files)
            else:
                self.detail_img_offset[1] -= 40
        elif event.key == pygame.K_DOWN:
            if files:
                self.asset_selected = (self.asset_selected + 1) % len(files)
            else:
                self.detail_img_offset[1] += 40

        # Open in browser
        elif event.key == pygame.K_RETURN and files:
            url = files[self.asset_selected].get("href")
            if url:
                webbrowser.open(url)
                self.status = f"Opened in browser: {url}"

        # Media playback
        elif event.key == pygame.K_p and files:
            url = files[self.asset_selected].get("href")
            if url:
                if media_type == "audio":
                    success = self.audio_player.play(url)
                    self.status = "Playing audio" if success else "Error playing audio"
                elif media_type == "video":
                    success = self.video_player.play(url)
                    self.status = "Opening video player" if success else "Error playing video"

        # Stop audio
        elif event.key == pygame.K_s and media_type == "audio":
            self.audio_player.stop()
            self.status = "Audio stopped"

        # Open captions
        elif event.key == pygame.K_n and media_type == "video":
            captloc = self.detail_captions.get("location")
            if captloc:
                webbrowser.open(captloc)
                self.status = f"Opening captions: {captloc}"

        return None