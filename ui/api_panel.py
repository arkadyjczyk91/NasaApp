import pygame
from constants import API_PANEL_BG, BLUE, WHITE

class ApiPanel:
    def __init__(self, fonts, x, y, w, h):
        self.fonts = fonts
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def draw(self, screen, api_log):
        pygame.draw.rect(screen, API_PANEL_BG, (self.x, self.y, self.w, self.h), border_radius=12)
        pygame.draw.rect(screen, BLUE, (self.x, self.y, self.w, self.h), 2, border_radius=12)
        title = self.fonts["gallery_label"].render("API - Odpowiedź", True, BLUE)
        screen.blit(title, (self.x + 12, self.y + 8))
        if not api_log:
            msg = self.fonts["api"].render("Brak danych z API.", True, WHITE)
            screen.blit(msg, (self.x + 20, self.y + 40))
            return
        log = api_log
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
        max_lines = (self.h - 40) // 18
        for i, line in enumerate(all_lines[:max_lines]):
            txt = self.fonts["api"].render(line, True, WHITE)
            screen.blit(txt, (self.x + 18, self.y + 40 + i * 18))