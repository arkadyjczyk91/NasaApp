import pygame
from constants import BLUE
from utils.text_renderer import render_text_lines

class Gallery:
    def __init__(self, fonts, thumb_size, x, y, w, h):
        self.fonts = fonts
        self.thumb_size = thumb_size
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def draw(self, screen, images, thumb_urls, selected_idx, image_cache):
        thumb = self.thumb_size
        spacing_x = 28
        spacing_y = 30
        grid_cols = max(1, (self.w - spacing_x) // (thumb + spacing_x))
        item_height = thumb + 45
        grid_rows = max(1, (self.h - spacing_y) // (item_height + spacing_y))
        images_per_page = grid_cols * grid_rows
        start_idx = 0
        end_idx = min(start_idx + images_per_page, len(images))

        for i, item_idx in enumerate(range(start_idx, end_idx)):
            item = images[item_idx]
            row, col = divmod(i, grid_cols)
            cx = self.x + spacing_x + col * (thumb + spacing_x)
            cy = self.y + spacing_y + row * (item_height + spacing_y)
            thumb_rect = pygame.Rect(cx, cy, thumb, thumb)
            if i == selected_idx:
                pygame.draw.rect(screen, BLUE, thumb_rect.inflate(8,8), 0, border_radius=9)
            pygame.draw.rect(screen, (14,24,38), thumb_rect, border_radius=9)
            pygame.draw.rect(screen, BLUE, thumb_rect, 2, border_radius=9)
            image_url = thumb_urls[item_idx] if item_idx < len(thumb_urls) else None
            if image_url:
                surf = image_cache.get(image_url)
                if surf is None:
                    loading_surf = self.fonts["small"].render("Ładowanie...", True, BLUE)
                    screen.blit(loading_surf, (cx + (thumb - loading_surf.get_width()) // 2,
                                               cy + (thumb - loading_surf.get_height()) // 2))
                else:
                    screen.blit(surf, (cx, cy))
            else:
                box = pygame.Rect(cx+7, cy+7, thumb-14, thumb-14)
                pygame.draw.rect(screen, (24,40,65), box, border_radius=6)
                no_img = self.fonts["small"].render("Brak obrazu", True, BLUE)
                screen.blit(no_img, (cx + (thumb - no_img.get_width()) // 2,
                                     cy + (thumb - no_img.get_height()) // 2))
            title = "Brak tytułu"
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
                screen.blit(surf, (cx + 4, cy + thumb + 4 + j*16))
            meta = f"{center} {date}"
            meta_surf = self.fonts["gallery_meta"].render(meta, True, (110,190,255))
            if meta_surf.get_width() > title_max_width:
                meta_max_len = len(meta) * title_max_width // meta_surf.get_width() - 3
                meta = meta[:meta_max_len] + "..."
                meta_surf = self.fonts["gallery_meta"].render(meta, True, (110,190,255))
            screen.blit(meta_surf, (cx + 4, cy + thumb + 4 + len(title_lines)*16))