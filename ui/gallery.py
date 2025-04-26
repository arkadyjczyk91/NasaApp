import pygame
from constants import BLUE, GALLERY_BG
from utils.text_renderer import render_text_lines


class Gallery:
    """Component for displaying and navigating a grid of image thumbnails."""

    def __init__(self, rect, thumbnail_size, font_small, font_gallery_meta):
        """Initialize the gallery with its dimensions and resources."""
        self.rect = rect
        self.thumbnail_size = thumbnail_size
        self.font_small = font_small
        self.font_gallery_meta = font_gallery_meta
        self.spacing_x = 28
        self.spacing_y = 30
        self.item_height = thumbnail_size + 45
        self.grid_cols = max(1, (rect.width - self.spacing_x) // (thumbnail_size + self.spacing_x))
        self.grid_rows = max(1, (rect.height - self.spacing_y) // (self.item_height + self.spacing_y))
        self.items_per_page = self.grid_cols * self.grid_rows

    def draw(self, screen, images, thumb_urls, current_page, selected_idx, is_active, image_cache):
        """Draw the gallery with its current items and selection state."""
        pygame.draw.rect(screen, GALLERY_BG, self.rect, border_radius=15)
        pygame.draw.rect(screen, BLUE, self.rect, 2, border_radius=15)

        start_idx = current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(images))

        thumb_rects = []

        for i, item_idx in enumerate(range(start_idx, end_idx)):
            item = images[item_idx]
            row, col = divmod(i, self.grid_cols)

            cx = self.rect.x + self.spacing_x + col * (self.thumbnail_size + self.spacing_x)
            cy = self.rect.y + self.spacing_y + row * (self.item_height + self.spacing_y)

            thumb_rect = pygame.Rect(cx, cy, self.thumbnail_size, self.thumbnail_size)
            thumb_rects.append(thumb_rect)

            # Draw selection highlight if this item is selected
            if is_active and i == selected_idx:
                pygame.draw.rect(screen, BLUE, thumb_rect.inflate(8, 8), 0, border_radius=9)

            # Draw thumbnail background
            pygame.draw.rect(screen, GALLERY_BG, thumb_rect, border_radius=9)
            pygame.draw.rect(screen, BLUE, thumb_rect, 2, border_radius=9)

            # Draw the thumbnail image or placeholder
            image_url = thumb_urls[item_idx] if item_idx < len(thumb_urls) else None
            if image_url:
                surf = image_cache.get(image_url)
                if surf is None:
                    loading_surf = self.font_small.render("Loading...", True, BLUE)
                    screen.blit(loading_surf, (cx + (self.thumbnail_size - loading_surf.get_width()) // 2,
                                               cy + (self.thumbnail_size - loading_surf.get_height()) // 2))
                else:
                    screen.blit(surf, (cx, cy))
            else:
                box = pygame.Rect(cx + 7, cy + 7, self.thumbnail_size - 14, self.thumbnail_size - 14)
                pygame.draw.rect(screen, (24, 40, 65), box, border_radius=6)
                no_img = self.font_small.render("No image", True, BLUE)
                screen.blit(no_img, (cx + (self.thumbnail_size - no_img.get_width()) // 2,
                                     cy + (self.thumbnail_size - no_img.get_height()) // 2))

            # Draw title and metadata
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

            # Render title with wrapping
            title_max_width = self.thumbnail_size - 8
            title_lines = render_text_lines(title, self.font_small, BLUE, title_max_width, max_lines=2)

            for j, surf in enumerate(title_lines):
                screen.blit(surf, (cx + 4, cy + self.thumbnail_size + 4 + j * 16))

            # Render metadata
            meta = f"{center} {date}"
            meta_surf = self.font_gallery_meta.render(meta, True, (110, 190, 255))

            if meta_surf.get_width() > title_max_width:
                meta_max_len = len(meta) * title_max_width // meta_surf.get_width() - 3
                meta = meta[:meta_max_len] + "..."
                meta_surf = self.font_gallery_meta.render(meta, True, (110, 190, 255))

            screen.blit(meta_surf, (cx + 4, cy + self.thumbnail_size + 4 + len(title_lines) * 16))

        return thumb_rects