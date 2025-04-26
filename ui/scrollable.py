import pygame
from constants import BLUE, BLACK, SCROLL_COLOR, SCROLL_BG

class ScrollableArea:
    def __init__(self, rect, content_surface, scroll_speed=15):
        self.rect = rect
        self.content = content_surface
        self.scroll_pos = 0
        self.scroll_speed = scroll_speed
        self.max_scroll = max(0, self.content.get_height() - self.rect.height)
        self.scrollbar_width = 8
        self.dragging = False
        self.scrollbar_rect = pygame.Rect(
            self.rect.right - self.scrollbar_width - 2,
            self.rect.top + 2,
            self.scrollbar_width,
            max(20, int(self.rect.height * min(1, self.rect.height / self.content.get_height())))
        )

    def scroll_up(self):
        self.scroll_pos = max(0, self.scroll_pos - self.scroll_speed)
        self._update_scrollbar()

    def scroll_down(self):
        self.scroll_pos = min(self.max_scroll, self.scroll_pos + self.scroll_speed)
        self._update_scrollbar()

    def _update_scrollbar(self):
        if self.max_scroll <= 0:
            return
        scroll_ratio = self.scroll_pos / self.max_scroll
        scrollbar_height = max(20, int(self.rect.height * min(1, self.rect.height / self.content.get_height())))
        scrollable_area = self.rect.height - scrollbar_height - 4
        self.scrollbar_rect.y = self.rect.top + 2 + int(scrollable_area * scroll_ratio)

    def draw(self, screen):
        view_surf = pygame.Surface((self.rect.width - self.scrollbar_width - 4, self.rect.height))
        view_surf.fill(BLACK)
        view_surf.blit(self.content, (0, -self.scroll_pos))
        screen.blit(view_surf, (self.rect.left + 2, self.rect.top))
        if self.max_scroll > 0:
            scrollbar_bg = pygame.Rect(
                self.rect.right - self.scrollbar_width - 2,
                self.rect.top,
                self.scrollbar_width,
                self.rect.height
            )
            pygame.draw.rect(screen, SCROLL_BG, scrollbar_bg)
            pygame.draw.rect(screen, SCROLL_COLOR, self.scrollbar_rect, border_radius=4)
        pygame.draw.rect(screen, BLUE, self.rect, 1)