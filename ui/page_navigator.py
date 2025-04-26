from constants import BLUE

class PageNavigator:
    def __init__(self, fonts, x, y, width):
        self.fonts = fonts
        self.x = x
        self.y = y
        self.width = width
        self.current_page = 0
        self.total_pages = 1

    def set_pages(self, current, total):
        self.current_page = current
        self.total_pages = total

    def draw(self, screen):
        page_text = f"Page: {self.current_page + 1} of {self.total_pages}"
        page_surf = self.fonts["medium"].render(page_text, True, BLUE)
        screen.blit(page_surf, (self.x, self.y))
        # Draw left/right arrow buttons
        pass

    def handle_event(self, event):
        # Handle clicks or key presses for page navigation
        pass