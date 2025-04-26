import pygame
import requests
import webbrowser
from io import BytesIO
from PIL import Image
import textwrap

from constants import BLACK, BLUE, WHITE
from utils.text_renderer import render_text, shorten_url
from ui.scrollable import ScrollableArea

class DetailView:
    def __init__(self, fonts, width, height, image_cache, audio_player, video_player):
        self.fonts = fonts
        self.width = width
        self.height = height
        self.image_cache = image_cache
        self.audio_player = audio_player
        self.video_player = video_player

        self.detail_item = None
        self.detail_asset = {}
        self.detail_metadata = {}
        self.detail_captions = {}
        self.detail_desc_scroll = None
        self.detail_files_scroll = None
        self.detail_meta_scroll = None
        self.detail_zoom = 1.0
        self.detail_img_offset = [0, 0]
        self.asset_selected = 0
        self.status = ""
        self.media_type = ""
        self.exit_requested = False

    def load(self, item, asset, metadata, captions):
        self.detail_item = item
        self.detail_asset = asset
        self.detail_metadata = metadata
        self.detail_captions = captions
        self.detail_desc_scroll = None
        self.detail_files_scroll = None
        self.detail_meta_scroll = None
        self.detail_zoom = 1.0
        self.detail_img_offset = [0, 0]
        self.asset_selected = 0
        d = self.detail_item.get("data", [{}])[0]
        self.media_type = d.get("media_type", "")

    def get_best_image_url(self):
        files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []
        for suffix in ['~orig.jpg', '~orig.png', '~large.jpg', '~large.png']:
            for f in files:
                if f['href'].endswith(suffix):
                    return f['href']
        for f in files:
            if f['href'].endswith(('.jpg', '.png')):
                return f['href']
        return None

    def get_best_audio_url(self):
        files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []
        for ext in ['~orig.mp3', '~128k.mp3', '.mp3', '.m4a', '.wav']:
            for f in files:
                if f['href'].endswith(ext):
                    return f['href']
        return None

    def get_best_video_url(self):
        files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []
        for ext in ['~orig.mp4', '~large.mp4', '.mp4', '.mov', '.avi']:
            for f in files:
                if f['href'].endswith(ext):
                    return f['href']
        return None

    def draw(self, screen):
        if not self.detail_item:
            return

        screen.fill(BLACK)
        panel_margin = 30
        panel_width = self.width - 2 * panel_margin
        y = panel_margin
        d = self.detail_item.get("data", [{}])[0]
        t = d.get("title", "Brak tytułu")
        title_surf = render_text(t, self.fonts["title"], BLUE, panel_width)
        screen.blit(title_surf, (panel_margin, y))
        y += title_surf.get_height() + 10

        left_width = int(panel_width * 0.65)
        right_width = panel_width - left_width - 20
        left_x = panel_margin
        left_h = self.height - y - panel_margin - 40
        preview_area = pygame.Rect(left_x, y, left_width, left_h)
        pygame.draw.rect(screen, (16, 20, 24), preview_area, border_radius=12)
        pygame.draw.rect(screen, BLUE, preview_area, 2, border_radius=12)

        file_url_img = self.get_best_image_url() if self.media_type == "image" else None
        file_url_audio = self.get_best_audio_url() if self.media_type == "audio" else None
        file_url_video = self.get_best_video_url() if self.media_type == "video" else None

        if file_url_img:
            surf = self.image_cache.get(file_url_img)
            if not surf:
                try:
                    response = requests.get(file_url_img)
                    img = Image.open(BytesIO(response.content))
                    img = img.convert("RGBA")
                    w, h = img.size
                    scale = min(preview_area.width / w, preview_area.height / h, 1.0) * self.detail_zoom
                    img = img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
                    mode = img.mode
                    size = img.size
                    data = img.tobytes()
                    surf = pygame.image.fromstring(data, size, mode)
                    self.image_cache.put(file_url_img, surf)
                except Exception:
                    surf = None
            if surf:
                tx = preview_area.x + (preview_area.width-surf.get_width())//2 + self.detail_img_offset[0]
                ty = preview_area.y + (preview_area.height-surf.get_height())//2 + self.detail_img_offset[1]
                screen.blit(surf, (tx, ty))
            else:
                loading = self.fonts["medium"].render("Ładowanie podglądu...", True, BLUE)
                screen.blit(loading, (preview_area.centerx - loading.get_width()//2,
                                      preview_area.centery - loading.get_height()//2))
        elif file_url_audio:
            box = pygame.Rect(preview_area.x+60, preview_area.y+preview_area.height//2-46, preview_area.width-120, 92)
            pygame.draw.rect(screen, (18,30,38), box, border_radius=18)
            pygame.draw.rect(screen, BLUE, box, 3, border_radius=18)
            name = file_url_audio.split("/")[-1]
            name_surf = self.fonts["medium"].render(name, True, BLUE)
            screen.blit(name_surf, (box.x + (box.width-name_surf.get_width())//2, box.y+8))
            play_rect = pygame.Rect(box.x+box.width//2-45, box.y+44, 38, 38)
            stop_rect = pygame.Rect(box.x+box.width//2+15, box.y+44, 38, 38)
            pygame.draw.rect(screen, (60,110,200), play_rect, border_radius=8)
            pygame.draw.rect(screen, (100,40,40), stop_rect, border_radius=8)
            ptxt = self.fonts["medium"].render("▶", True, WHITE)
            stxt = self.fonts["medium"].render("■", True, WHITE)
            screen.blit(ptxt, (play_rect.centerx-ptxt.get_width()//2, play_rect.centery-ptxt.get_height()//2))
            screen.blit(stxt, (stop_rect.centerx-stxt.get_width()//2, stop_rect.centery-stxt.get_height()//2))
            mouse = pygame.mouse.get_pressed()
            mx, my = pygame.mouse.get_pos()
            if mouse[0]:
                if play_rect.collidepoint(mx,my):
                    self.audio_player.play(file_url_audio)
                if stop_rect.collidepoint(mx,my):
                    self.audio_player.stop()
        elif file_url_video:
            box = pygame.Rect(preview_area.x+60, preview_area.y+preview_area.height//2-46, preview_area.width-120, 92)
            pygame.draw.rect(screen, (18,30,38), box, border_radius=18)
            pygame.draw.rect(screen, BLUE, box, 3, border_radius=18)
            name = file_url_video.split("/")[-1]
            name_surf = self.fonts["medium"].render(name, True, BLUE)
            screen.blit(name_surf, (box.x + (box.width-name_surf.get_width())//2, box.y+8))
            play_rect = pygame.Rect(box.x+box.width//2-19, box.y+44, 38, 38)
            pygame.draw.rect(screen, (60,110,200), play_rect, border_radius=8)
            ptxt = self.fonts["medium"].render("▶", True, WHITE)
            screen.blit(ptxt, (play_rect.centerx-ptxt.get_width()//2, play_rect.centery-ptxt.get_height()//2))
            mouse = pygame.mouse.get_pressed()
            mx, my = pygame.mouse.get_pos()
            if mouse[0]:
                if play_rect.collidepoint(mx,my):
                    self.video_player.play(file_url_video)
        else:
            no_img = self.fonts["medium"].render("Brak podglądu", True, BLUE)
            screen.blit(no_img, (preview_area.centerx - no_img.get_width()//2,
                                 preview_area.centery - no_img.get_height()//2))

        # Prawy panel - opis i pliki
        right_x = left_x + left_width + 20
        right_y = y
        right_h = left_h

        # Opis
        desc = d.get("description", "Brak opisu")
        desc_title = self.fonts["medium"].render("Opis:", True, BLUE)
        screen.blit(desc_title, (right_x, right_y))
        right_y += desc_title.get_height() + 5
        desc_height = int(right_h * 0.4)
        desc_rect = pygame.Rect(right_x, right_y, right_width, desc_height)
        pygame.draw.rect(screen, (14, 18, 24), desc_rect, border_radius=8)
        desc_content = render_text(desc, self.fonts["small"], BLUE, right_width - 20)
        if not self.detail_desc_scroll:
            self.detail_desc_scroll = ScrollableArea(desc_rect, desc_content)
        else:
            self.detail_desc_scroll.rect = desc_rect
            self.detail_desc_scroll.content = desc_content
            self.detail_desc_scroll.max_scroll = max(0, desc_content.get_height() - desc_rect.height)
            self.detail_desc_scroll._update_scrollbar()
        self.detail_desc_scroll.draw(screen)
        right_y += desc_height + 15

        # Pliki
        files_title = self.fonts["medium"].render("Pliki assetu:", True, BLUE)
        screen.blit(files_title, (right_x, right_y))
        right_y += files_title.get_height() + 5
        files_height = int(right_h * 0.25)
        files_rect = pygame.Rect(right_x, right_y, right_width, files_height)
        pygame.draw.rect(screen, (14, 18, 24), files_rect, border_radius=8)
        files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []
        if files:
            files_content_height = len(files) * 20 + 10
            files_content = pygame.Surface((right_width - 20, files_content_height), pygame.SRCALPHA)
            files_content.fill((0, 0, 0, 0))
            for j, f in enumerate(files):
                url = f.get("href", "")
                filename = url.split("/")[-1] if url else "-"
                color = BLUE if self.asset_selected == j else (180, 220, 255)
                file_surf = self.fonts["detail_asset"].render(shorten_url(filename, 38), True, color)
                files_content.blit(file_surf, (10, j * 20 + 5))
                if self.asset_selected == j:
                    select_rect = pygame.Rect(0, j * 20, right_width - 30, 20)
                    pygame.draw.rect(files_content, (30, 40, 60), select_rect)
                    pygame.draw.rect(files_content, BLUE, select_rect, 1)
                    file_surf = self.fonts["detail_asset"].render(shorten_url(filename, 38), True, BLUE)
                    files_content.blit(file_surf, (10, j * 20 + 5))
        else:
            files_content = self.fonts["detail_asset"].render("Brak plików.", True, BLUE)
        if not self.detail_files_scroll:
            self.detail_files_scroll = ScrollableArea(files_rect, files_content)
        else:
            self.detail_files_scroll.rect = files_rect
            self.detail_files_scroll.content = files_content
            self.detail_files_scroll.max_scroll = max(0, files_content.get_height() - files_rect.height)
            self.detail_files_scroll._update_scrollbar()
        self.detail_files_scroll.draw(screen)
        right_y += files_height + 15

        # Metadane
        meta_title = self.fonts["medium"].render("Metadane:", True, BLUE)
        screen.blit(meta_title, (right_x, right_y))
        right_y += meta_title.get_height() + 5
        meta_height = right_h - (right_y - y)
        meta_rect = pygame.Rect(right_x, right_y, right_width, meta_height)
        pygame.draw.rect(screen, (14, 18, 24), meta_rect, border_radius=8)
        md = self.detail_metadata if self.detail_metadata else {}
        if md:
            keys = ["center", "nasa_id", "date_created", "secondary_creator", "photographer",
                    "location", "album", "source", "rights", "keywords"]
            metadata_lines = []
            for k in keys:
                v = md.get(k)
                if v:
                    if isinstance(v, list):
                        v = ", ".join(str(item) for item in v)
                    metadata_lines.append(f"{k}: {v}")
            if not metadata_lines:
                metadata_content = self.fonts["detail_asset"].render("Brak metadanych.", True, BLUE)
            else:
                md_height = len(metadata_lines) * 20 + 10
                metadata_content = pygame.Surface((right_width - 20, md_height), pygame.SRCALPHA)
                metadata_content.fill((0, 0, 0, 0))
                line_y = 5
                for i, line in enumerate(metadata_lines):
                    wrapped = textwrap.wrap(line, width=right_width // 9)
                    for wrap_line in wrapped:
                        line_surf = self.fonts["detail_asset"].render(wrap_line, True, (180, 220, 255))
                        metadata_content.blit(line_surf, (10, line_y))
                        line_y += 20
        else:
            metadata_content = self.fonts["detail_asset"].render("Brak metadanych.", True, BLUE)
        if not self.detail_meta_scroll:
            self.detail_meta_scroll = ScrollableArea(meta_rect, metadata_content)
        else:
            self.detail_meta_scroll.rect = meta_rect
            self.detail_meta_scroll.content = metadata_content
            self.detail_meta_scroll.max_scroll = max(0, metadata_content.get_height() - meta_rect.height)
            self.detail_meta_scroll._update_scrollbar()
        self.detail_meta_scroll.draw(screen)

        # Instrukcje
        nav_text = "ESC wyjście | +/- powiększ | ←/→/↑/↓ przesuwanie | ↑/↓ wybór pliku | "
        if self.media_type == "audio":
            nav_text += "P odtwórz audio | S stop | "
        elif self.media_type == "video":
            nav_text += "P odtwórz wideo | "
        nav_text += "Enter otwórz w przeglądarce | PageUp/Down przewijanie opisu"
        nav_surf = self.fonts["small"].render(nav_text, True, (120, 180, 255))
        nav_width = nav_surf.get_width()
        if nav_width > self.width - 20:
            nav_text1 = "ESC wyjście | +/- powiększ | ←/→/↑/↓ przesuwanie | ↑/↓ wybór pliku"
            nav_text2 = "P odtwórz media | S stop | Enter otwórz w przeglądarce | PageUp/Down przewijanie opisu"
            nav_surf1 = self.fonts["small"].render(nav_text1, True, (120, 180, 255))
            nav_surf2 = self.fonts["small"].render(nav_text2, True, (120, 180, 255))
            screen.blit(nav_surf1, (self.width // 2 - nav_surf1.get_width() // 2, self.height - 60))
            screen.blit(nav_surf2, (self.width // 2 - nav_surf2.get_width() // 2, self.height - 38))
        else:
            screen.blit(nav_surf, (self.width // 2 - nav_surf.get_width() // 2, self.height - 38))

    def handle_key(self, event):
        files = self.detail_asset.get("collection", {}).get("items", []) if self.detail_asset else []
        # Wyjście z trybu szczegółów
        if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.exit_requested = True
            self.audio_player.stop()
            self.detail_desc_scroll = None
            self.detail_meta_scroll = None
            return
        # Powiększanie/pomniejszanie obrazu
        if event.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
            self.detail_zoom = min(self.detail_zoom + 0.2, 4.0)
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.detail_zoom = max(self.detail_zoom - 0.2, 0.4)
        # Przewijanie opisu i metadanych
        elif event.key == pygame.K_PAGEUP:
            if self.detail_desc_scroll:
                self.detail_desc_scroll.scroll_up()
        elif event.key == pygame.K_PAGEDOWN:
            if self.detail_desc_scroll:
                self.detail_desc_scroll.scroll_down()
        # Przesuwanie obrazu lub wybór pliku
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
        # Otwieranie pliku w przeglądarce
        elif event.key == pygame.K_RETURN and files:
            url = files[self.asset_selected].get("href")
            if url:
                webbrowser.open(url)
                self.status = f"Otwarto w przeglądarce: {url}"
        # Odtwarzanie media
        elif event.key == pygame.K_p and files:
            url = files[self.asset_selected].get("href")
            if url:
                if self.media_type == "audio":
                    self.audio_player.play(url)
                elif self.media_type == "video":
                    self.video_player.play(url)
        elif event.key == pygame.K_s and self.media_type == "audio":
            self.audio_player.stop()