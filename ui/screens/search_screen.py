import pygame
import math
from app.config import BLACK, BLUE, WHITE, API_PANEL_BG
from ui.rendering import render_text_lines


class SearchScreen:
    """Screen for searching NASA media."""

    def __init__(self, screen, width, height, fonts, image_service, on_enter_detail):
        self.screen = screen
        self.WIDTH = width
        self.HEIGHT = height
        self.fonts = fonts
        self.image_service = image_service
        self.on_enter_detail = on_enter_detail

        # Search parameters
        self.input_keyword = ""
        self.input_count = ""
        self.media_types = ["all", "image", "video", "audio", "album"]
        self.selected_media_type = 1

        # UI state
        self.inputs = ["media_type", "keyword", "count", "gallery", "pager"]
        self.active_control = 1
        self.images = []
        self.images_json = []
        self.api_log = None
        self.current_page = 0
        self.selected_idx = 0
        self.last_pager_key = None
        self.loading = False
        self.thumbnail_size = 110
        self.images_per_page = 16
        self.status = "Ready"
        self.thumb_urls = []
        self.thumb_loaded = set()
        self.rects_ui = {}

        # Tracking for auto-search
        self.last_keyword = ""
        self.last_keyword_change = 0
        self.last_fetch_keyword = ""
        self.last_fetch_count = ""
        self.last_fetch_media_type = 0
        self.fetch_delay = 0.8  # seconds

    def update_dimensions(self, width, height):
        """Update screen dimensions."""
        self.WIDTH = width
        self.HEIGHT = height

    def set_search_results(self, items, api_log, error=None):
        """Set search results."""
        self.images_json = items
        self.images = items
        self.current_page = 0
        self.selected_idx = 0
        self.api_log = api_log

        if error:
            self.status = f"Error fetching: {error}"
            self.loading = False
            return

        self.status = f"Found {len(self.images_json)} assets for keyword '{self.input_keyword}'."
        self.thumb_urls = []
        self.thumb_loaded = set()

        for idx, item in enumerate(self.images):
            image_url = None
            if "links" in item:
                for link in item["links"]:
                    if link.get("rel") == "preview" and "href" in link:
                        image_url = link["href"]
                        break
            self.thumb_urls.append(image_url)
            if image_url:
                if self.image_service.image_cache.get(image_url) is None:
                    self.image_service.fetch_and_notify_thumb(image_url, idx)

        self.loading = False

    def handle_input(self, event):
        """Handle input events for the search screen."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return True
            elif event.key == pygame.K_F11:
                pygame.event.post(pygame.event.Event(pygame.USEREVENT, {"action": "toggle_fullscreen"}))
                return True

            focus = self.inputs[self.active_control]

            # Tab navigation
            if event.key == pygame.K_TAB and not (event.mod & pygame.KMOD_SHIFT):
                self.active_control = (self.active_control + 1) % len(self.inputs)
                self.last_pager_key = None
                return True
            elif event.key == pygame.K_TAB and (event.mod & pygame.KMOD_SHIFT):
                self.active_control = (self.active_control - 1) % len(self.inputs)
                self.last_pager_key = None
                return True

            # Media type selector
            if focus == "media_type":
                if event.key == pygame.K_LEFT:
                    self.selected_media_type = (self.selected_media_type - 1) % len(self.media_types)
                    self.last_fetch_keyword = ""  # Force fetch with new media type
                elif event.key == pygame.K_RIGHT:
                    self.selected_media_type = (self.selected_media_type + 1) % len(self.media_types)
                    self.last_fetch_keyword = ""  # Force fetch with new media type
                elif event.key == pygame.K_DOWN:
                    self.active_control = (self.active_control + 1) % len(self.inputs)
                elif event.key == pygame.K_UP:
                    self.active_control = (self.active_control - 1) % len(self.inputs)

            # Keyword input
            elif focus == "keyword":
                if event.key == pygame.K_RETURN:
                    return "search"
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

            # Count input
            elif focus == "count":
                if event.key == pygame.K_RETURN:
                    return "search"
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
                        return "detail", self.images[idx]
                elif event.key == pygame.K_PAGEUP:
                    self.prev_page()
                elif event.key == pygame.K_PAGEDOWN:
                    self.next_page()
                elif event.key == pygame.K_TAB:
                    self.active_control = 4
                elif event.key == pygame.K_BACKSPACE:
                    self.active_control = 2

            # Pager navigation
            elif focus == "pager":
                if event.key == pygame.K_LEFT or event.key == pygame.K_PAGEUP:
                    self.prev_page()
                    self.last_pager_key = "left"
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_PAGEDOWN:
                    self.next_page()
                    self.last_pager_key = "right"
                elif event.key == pygame.K_UP:
                    self.active_control = 3
                elif event.key == pygame.K_DOWN:
                    self.active_control = 0
                elif event.key == pygame.K_TAB:
                    self.active_control = 0
                elif event.key == pygame.K_RETURN:
                    if self.last_pager_key == "left":
                        self.prev_page()
                    elif self.last_pager_key == "right":
                        self.next_page()

        return None

    def prev_page(self):
        """Go to previous page of results."""
        if self.current_page > 0:
            self.current_page -= 1
            self.selected_idx = 0

    def next_page(self):
        """Go to next page of results."""
        total_pages = max(1, math.ceil(len(self.images) / self.images_per_page))
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.selected_idx = 0

    def draw(self):
        """Draw the search screen."""
        self.screen.fill(BLACK)

        # Draw navigation info and controls
        top_y = 10
        self.draw_nav_info(top_y)
        top_y += 24
        self.draw_media_type_selector(top_y)
        top_y += 34
        input_y = self.draw_input_boxes(top_y)

        # Calculate layout
        gallery_top = input_y + 7
        gallery_h = int(self.HEIGHT * 0.75)
        gallery_w = int(self.WIDTH * 0.62)
        api_panel_x = gallery_w + 60
        api_panel_w = self.WIDTH - api_panel_x - 25
        api_panel_h = gallery_h

        # Draw main components
        self.draw_gallery(40, gallery_top, gallery_w, gallery_h)
        self.draw_api_panel(api_panel_x, gallery_top, api_panel_w, api_panel_h)
        page_nav_y = gallery_top + gallery_h + 10
        self.draw_page_nav(page_nav_y)
        self.draw_status_bar(self.HEIGHT - 38)

    def draw_gallery(self, x, y, w, h):
        """Draw the gallery of search results."""
        pygame.draw.rect(self.screen, (14, 24, 38), (x, y, w, h), border_radius=15)
        pygame.draw.rect(self.screen, BLUE, (x, y, w, h), 2, border_radius=15)

        thumb = self.thumbnail_size
        spacing_x = 28
        spacing_y = 30
        grid_cols = max(1, (w - spacing_x) // (thumb + spacing_x))
        item_height = thumb + 45
        grid_rows = max(1, (h - spacing_y) // (item_height + spacing_y))

        self.images_per_page = grid_cols * grid_rows
        start_idx = self.current_page * self.images_per_page
        end_idx = min(start_idx + self.images_per_page, len(self.images))

        self.rects_ui["gallery_grid"] = []

        for i, item_idx in enumerate(range(start_idx, end_idx)):
            item = self.images[item_idx]
            row, col = divmod(i, grid_cols)
            cx = x + spacing_x + col * (thumb + spacing_x)
            cy = y + spacing_y + row * (item_height + spacing_y)

            thumb_rect = pygame.Rect(cx, cy, thumb, thumb)
            self.rects_ui["gallery_grid"].append(thumb_rect)

            if (self.inputs[self.active_control] == "gallery" and i == self.selected_idx):
                pygame.draw.rect(self.screen, BLUE, thumb_rect.inflate(8, 8), 0, border_radius=9)

            pygame.draw.rect(self.screen, (14, 24, 38), thumb_rect, border_radius=9)
            pygame.draw.rect(self.screen, BLUE, thumb_rect, 2, border_radius=9)

            image_url = self.thumb_urls[item_idx] if item_idx < len(self.thumb_urls) else None

            if image_url:
                surf = self.image_service.image_cache.get(image_url)
                if surf is None:
                    loading_surf = self.fonts["small"].render("Loading...", True, BLUE)
                    self.screen.blit(loading_surf, (cx + (thumb - loading_surf.get_width()) // 2,
                                                    cy + (thumb - loading_surf.get_height()) // 2))
                else:
                    self.screen.blit(surf, (cx, cy))
            else:
                box = pygame.Rect(cx + 7, cy + 7, thumb - 14, thumb - 14)
                pygame.draw.rect(self.screen, (24, 40, 65), box, border_radius=6)
                no_img = self.fonts["small"].render("No image", True, BLUE)
                self.screen.blit(no_img, (cx + (thumb - no_img.get_width()) // 2,
                                          cy + (thumb - no_img.get_height()) // 2))

            # Draw item metadata
            title = "No title"
            center = ""
            date = ""

            if "data" in item and item["data"]:
                d = item["data"][0]
                if "title" in d:
                    title = d["title"]
                if "center" in d:
                    center = d["center"]
                if "date_created" in d:
                    date = d["date_created"][:10]

            title_max_width = thumb - 8
            title_lines = render_text_lines(title, self.fonts["small"], BLUE, title_max_width, max_lines=2)

            for j, surf in enumerate(title_lines):
                self.screen.blit(surf, (cx + 4, cy + thumb + 4 + j * 16))

            meta = f"{center} {date}"
            meta_surf = self.fonts["gallery_meta"].render(meta, True, (110, 190, 255))

            if meta_surf.get_width() > title_max_width:
                meta_max_len = len(meta) * title_max_width // meta_surf.get_width() - 3
                meta = meta[:meta_max_len] + "..."
                meta_surf = self.fonts["gallery_meta"].render(meta, True, (110, 190, 255))

            self.screen.blit(meta_surf, (cx + 4, cy + thumb + 4 + len(title_lines) * 16))

    def draw_api_panel(self, x, y, w, h):
        """Draw the API response panel."""
        pygame.draw.rect(self.screen, API_PANEL_BG, (x, y, w, h), border_radius=12)
        pygame.draw.rect(self.screen, BLUE, (x, y, w, h), 2, border_radius=12)

        title = self.fonts["gallery_label"].render("API - Response", True, BLUE)
        self.screen.blit(title, (x + 12, y + 8))

        if not self.api_log:
            msg = self.fonts["api"].render("No API data available.", True, WHITE)
            self.screen.blit(msg, (x + 20, y + 40))
            return

        log = self.api_log
        log_lines = [
            f"URL: {log.get('url', '')}",
            f"Method: {log.get('method', '')}",
            f"Status: {log.get('status', '')}",
            f"Params: {log.get('params', '')}",
            "Response (fragment):"
        ]

        response_snippet = log.get("response_snippet", "")
        snippet_lines = response_snippet.split('\n')
        all_lines = log_lines + snippet_lines

        max_lines = (h - 40) // 18
        for i, line in enumerate(all_lines[:max_lines]):
            txt = self.fonts["api"].render(line, True, WHITE)
            self.screen.blit(txt, (x + 18, y + 40 + i * 18))

    def draw_input_boxes(self, y):
        """Draw input boxes for search parameters."""
        x = 40

        # Draw "Keyword" input
        kw_label = self.fonts["label"].render("Keyword:", True, BLUE)
        self.screen.blit(kw_label, (x, y))
        x += kw_label.get_width() + 10

        kw_box = pygame.Rect(x, y, 260, 32)
        pygame.draw.rect(self.screen, (20, 26, 36), kw_box, border_radius=6)
        pygame.draw.rect(self.screen, BLUE if self.inputs[self.active_control] == "keyword" else (80, 120, 160),
                         kw_box, 2, border_radius=6)

        kw_text = self.fonts["small"].render(self.input_keyword, True, WHITE)
        self.screen.blit(kw_text, (kw_box.x + 6, kw_box.y + 6))
        x += 270

        # Draw "Count" input
        count_label = self.fonts["label"].render("Limit:", True, BLUE)
        self.screen.blit(count_label, (x, y))
        x += count_label.get_width() + 10

        count_box = pygame.Rect(x, y, 72, 32)
        pygame.draw.rect(self.screen, (20, 26, 36), count_box, border_radius=6)
        pygame.draw.rect(self.screen, BLUE if self.inputs[self.active_control] == "count" else (80, 120, 160),
                         count_box, 2, border_radius=6)

        count_text = self.fonts["small"].render(self.input_count, True, WHITE)
        self.screen.blit(count_text, (count_box.x + 6, count_box.y + 6))

        # Return the new Y coordinate for further drawing
        return y + 40

    def draw_page_nav(self, y):
        """Draw pagination navigation."""
        total_pages = max(1, (len(self.images) + self.images_per_page - 1) // self.images_per_page)
        page_text = f"Page: {self.current_page + 1} of {total_pages}"
        page_surf = self.fonts["medium"].render(page_text, True, BLUE)
        x = 40
        self.screen.blit(page_surf, (x, y))

        # Draw navigation arrows
        arrow_size = 32
        margin = 20
        left_rect = pygame.Rect(x + page_surf.get_width() + margin, y, arrow_size, arrow_size)
        right_rect = pygame.Rect(left_rect.right + margin, y, arrow_size, arrow_size)

        pygame.draw.rect(self.screen, (20, 36, 60), left_rect, border_radius=8)
        pygame.draw.rect(self.screen, (20, 36, 60), right_rect, border_radius=8)

        # Left arrow
        pygame.draw.polygon(self.screen, BLUE, [
            (left_rect.left + 8, left_rect.centery),
            (left_rect.right - 8, left_rect.top + 8),
            (left_rect.right - 8, left_rect.bottom - 8)
        ])

        # Right arrow
        pygame.draw.polygon(self.screen, BLUE, [
            (right_rect.right - 8, right_rect.centery),
            (right_rect.left + 8, right_rect.top + 8),
            (right_rect.left + 8, right_rect.bottom - 8)
        ])

    def draw_media_type_selector(self, y):
        """Draw media type selector."""
        x = 40
        label_surf = self.fonts["label"].render("Media type:", True, BLUE)
        self.screen.blit(label_surf, (x, y))
        x += label_surf.get_width() + 16

        for i, mt in enumerate(self.media_types):
            col = BLUE if i == self.selected_media_type else (120, 180, 220)
            mt_surf = self.fonts["label"].render(mt.upper(), True, col)
            bg_rect = pygame.Rect(x - 4, y - 2, mt_surf.get_width() + 8, mt_surf.get_height() + 4)

            if self.inputs[self.active_control] == "media_type" and i == self.selected_media_type:
                pygame.draw.rect(self.screen, (20, 30, 50), bg_rect, border_radius=6)
                pygame.draw.rect(self.screen, BLUE, bg_rect, 2, border_radius=6)
            else:
                pygame.draw.rect(self.screen, (10, 16, 28), bg_rect, border_radius=6)

            self.screen.blit(mt_surf, (x, y))
            x += mt_surf.get_width() + 16

    def draw_status_bar(self, y):
        """Draw status bar at the bottom of the screen."""
        bar_rect = pygame.Rect(0, y, self.WIDTH, 38)
        pygame.draw.rect(self.screen, (20, 30, 40), bar_rect)
        pygame.draw.line(self.screen, BLUE, (0, y), (self.WIDTH, y), 2)

        status_text = self.status if hasattr(self, 'status') else ""
        status_surf = self.fonts["small"].render(status_text, True, BLUE)
        self.screen.blit(status_surf, (18, y + (38 - status_surf.get_height()) // 2))

    def draw_nav_info(self, y):
        """Draw navigation help info."""
        nav_text = "F11 - fullscreen | F12 - windowed | Tab - next field | Enter - search/select | Esc - exit"
        nav_surf = self.fonts["small"].render(nav_text, True, (120, 180, 255))
        self.screen.blit(nav_surf, (self.WIDTH // 2 - nav_surf.get_width() // 2, y))