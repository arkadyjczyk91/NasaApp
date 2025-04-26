import pygame
from constants import API_PANEL_BG, BLUE, WHITE

class ApiPanel:
    def __init__(self, fonts, x, y, w, h):
        self.fonts = fonts
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.log = None

    def set_log(self, log):
        self.log = log

    def draw(self, screen):
        pygame.draw.rect(screen, API_PANEL_BG, (self.x, self.y, self.w, self.h), border_radius=12)
        pygame.draw.rect(screen, BLUE, (self.x, self.y, self.w, self.h), 2, border_radius=12)
        title = self.fonts["gallery_label"].render("API - Response", True, BLUE)
        screen.blit(title, (self.x + 12, self.y + 8))
        if not self.log:
            msg = self.fonts["api"].render("No API data.", True, WHITE)
            screen.blit(msg, (self.x + 20, self.y + 40))
            return
        # Display log details, params, and response snippet
        pass