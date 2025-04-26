import pygame
from constants import BLUE, WHITE

class InputPanel:
    def __init__(self, fonts, x, y, media_types, get_active, set_active, get_keyword, set_keyword, get_count, set_count, get_selected_media_type, set_selected_media_type):
        self.fonts = fonts
        self.x = x
        self.y = y
        self.media_types = media_types
        self.get_active = get_active
        self.set_active = set_active
        self.get_keyword = get_keyword
        self.set_keyword = set_keyword
        self.get_count = get_count
        self.set_count = set_count
        self.get_selected_media_type = get_selected_media_type
        self.set_selected_media_type = set_selected_media_type

    def draw(self, screen):
        x = self.x
        y = self.y
        # Media type selector
        label_surf = self.fonts['label'].render("Typ mediów:", True, BLUE)
        screen.blit(label_surf, (x, y))
        x += label_surf.get_width() + 16
        for i, mt in enumerate(self.media_types):
            col = BLUE if i == self.get_selected_media_type() else (120, 180, 220)
            mt_surf = self.fonts['label'].render(mt.upper(), True, col)
            bg_rect = pygame.Rect(x - 4, y - 2, mt_surf.get_width() + 8, mt_surf.get_height() + 4)
            if self.get_active() == 0 and i == self.get_selected_media_type():
                pygame.draw.rect(screen, (20, 30, 50), bg_rect, border_radius=6)
                pygame.draw.rect(screen, BLUE, bg_rect, 2, border_radius=6)
            else:
                pygame.draw.rect(screen, (10, 16, 28), bg_rect, border_radius=6)
            screen.blit(mt_surf, (x, y))
            x += mt_surf.get_width() + 16

        # Keyword input
        x = self.x
        y += 34
        kw_label = self.fonts['label'].render("Słowo kluczowe:", True, BLUE)
        screen.blit(kw_label, (x, y))
        x += kw_label.get_width() + 10
        kw_box = pygame.Rect(x, y, 260, 32)
        pygame.draw.rect(screen, (20, 26, 36), kw_box, border_radius=6)
        pygame.draw.rect(screen, BLUE if self.get_active() == 1 else (80, 120, 160), kw_box, 2, border_radius=6)
        kw_text = self.fonts['small'].render(self.get_keyword(), True, WHITE)
        screen.blit(kw_text, (kw_box.x + 6, kw_box.y + 6))

        x += 270
        # Count input
        count_label = self.fonts['label'].render("Limit:", True, BLUE)
        screen.blit(count_label, (x, y))
        x += count_label.get_width() + 10
        count_box = pygame.Rect(x, y, 72, 32)
        pygame.draw.rect(screen, (20, 26, 36), count_box, border_radius=6)
        pygame.draw.rect(screen, BLUE if self.get_active() == 2 else (80, 120, 160), count_box, 2, border_radius=6)
        count_text = self.fonts['small'].render(self.get_count(), True, WHITE)
        screen.blit(count_text, (count_box.x + 6, count_box.y + 6))

    def handle_event(self, event):
        active = self.get_active()
        if event.type != pygame.KEYDOWN:
            return None
        if active == 0:  # media_type
            if event.key == pygame.K_LEFT:
                self.set_selected_media_type((self.get_selected_media_type() - 1) % len(self.media_types))
            elif event.key == pygame.K_RIGHT:
                self.set_selected_media_type((self.get_selected_media_type() + 1) % len(self.media_types))
            elif event.key == pygame.K_TAB or event.key == pygame.K_DOWN:
                self.set_active(1)
            elif event.key == pygame.K_UP:
                self.set_active(2)
        elif active == 1:  # keyword
            if event.key == pygame.K_RETURN:
                return "submit"
            elif event.key == pygame.K_BACKSPACE:
                self.set_keyword(self.get_keyword()[:-1])
            elif event.unicode and len(self.get_keyword()) < 40 and event.key != pygame.K_TAB:
                self.set_keyword(self.get_keyword() + event.unicode)
            elif event.key == pygame.K_DOWN or event.key == pygame.K_TAB:
                self.set_active(2)
            elif event.key == pygame.K_UP:
                self.set_active(0)
        elif active == 2:  # count
            if event.key == pygame.K_RETURN:
                return "submit"
            elif event.key == pygame.K_BACKSPACE:
                self.set_count(self.get_count()[:-1])
            elif event.unicode and len(self.get_count()) < 6 and event.unicode.isdigit():
                self.set_count(self.get_count() + event.unicode)
            elif event.key == pygame.K_UP:
                self.set_active(1)
            elif event.key == pygame.K_DOWN or event.key == pygame.K_TAB:
                self.set_active(0)
        return None