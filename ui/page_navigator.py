import pygame
from constants import BLUE

class PageNavigator:
    def __init__(self, fonts, x, y, width, get_current, set_current, get_total):
        self.fonts = fonts
        self.x = x
        self.y = y
        self.width = width
        self.get_current = get_current
        self.set_current = set_current
        self.get_total = get_total

    def draw(self, screen):
        current = self.get_current()
        total = self.get_total()
        page_text = f"Strona: {current + 1} z {total}"
        page_surf = self.fonts["medium"].render(page_text, True, BLUE)
        x = self.x
        screen.blit(page_surf, (x, self.y))
        arrow_size = 32
        margin = 20
        left_rect = pygame.Rect(x + page_surf.get_width() + margin, self.y, arrow_size, arrow_size)
        right_rect = pygame.Rect(left_rect.right + margin, self.y, arrow_size, arrow_size)
        pygame.draw.rect(screen, (20, 36, 60), left_rect, border_radius=8)
        pygame.draw.rect(screen, (20, 36, 60), right_rect, border_radius=8)
        pygame.draw.polygon(screen, BLUE, [
            (left_rect.left + 8, left_rect.centery),
            (left_rect.right - 8, left_rect.top + 8),
            (left_rect.right - 8, left_rect.bottom - 8)
        ])
        pygame.draw.polygon(screen, BLUE, [
            (right_rect.right - 8, right_rect.centery),
            (right_rect.left + 8, right_rect.top + 8),
            (right_rect.left + 8, right_rect.bottom - 8)
        ])
        self.left_rect = left_rect
        self.right_rect = right_rect

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_LEFT or event.key == pygame.K_PAGEUP:
            if self.get_current() > 0:
                self.set_current(self.get_current() - 1)
        elif event.key == pygame.K_RIGHT or event.key == pygame.K_PAGEDOWN:
            if self.get_current() < self.get_total() - 1:
                self.set_current(self.get_current() + 1)