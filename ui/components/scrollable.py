import pygame
from app.config import BLUE, SCROLL_COLOR, SCROLL_BG, BLACK


class ScrollableArea:
    """A scrollable area for displaying content that exceeds the view area."""

    def __init__(self, rect, content_surface, scroll_speed=15):
        self.rect = rect
        self.content = content_surface
        self.scroll_pos = 0
        self.scroll_speed = scroll_speed
        self.max_scroll = max(0, self.content.get_height() - self.rect.height)
        self.scrollbar_width = 8
        self.dragging = False
        self.drag_start_y = 0
        self.drag_start_scroll = 0

        # Calculate scrollbar height and position
        self._update_scrollbar()

    def _update_scrollbar(self):
        """Update the scrollbar position based on scroll position."""
        if self.max_scroll <= 0:
            # If content fits without scrolling, make a full-height scrollbar
            scrollbar_height = self.rect.height - 4
            self.scrollbar_rect = pygame.Rect(
                self.rect.right - self.scrollbar_width - 2,
                self.rect.top + 2,
                self.scrollbar_width,
                scrollbar_height
            )
            return

        # Calculate scrollbar size (proportional to content vs visible area)
        content_ratio = min(1.0, self.rect.height / self.content.get_height())
        scrollbar_height = max(20, int(self.rect.height * content_ratio))

        # Calculate scrollbar position
        if self.max_scroll > 0:
            scroll_ratio = self.scroll_pos / self.max_scroll
            scrollable_area = self.rect.height - scrollbar_height - 4
            scrollbar_y = self.rect.top + 2 + int(scrollable_area * scroll_ratio)
        else:
            scrollbar_y = self.rect.top + 2

        # Update scrollbar rectangle
        self.scrollbar_rect = pygame.Rect(
            self.rect.right - self.scrollbar_width - 2,
            scrollbar_y,
            self.scrollbar_width,
            scrollbar_height
        )

    def scroll_up(self, amount=None):
        """Scroll the content upward."""
        scroll_amount = amount if amount is not None else self.scroll_speed
        old_pos = self.scroll_pos
        self.scroll_pos = max(0, self.scroll_pos - scroll_amount)
        if old_pos != self.scroll_pos:
            self._update_scrollbar()
            return True
        return False

    def scroll_down(self, amount=None):
        """Scroll the content downward."""
        scroll_amount = amount if amount is not None else self.scroll_speed
        old_pos = self.scroll_pos
        self.scroll_pos = min(self.max_scroll, self.scroll_pos + scroll_amount)
        if old_pos != self.scroll_pos:
            self._update_scrollbar()
            return True
        return False

    def handle_event(self, event):
        """Handle mouse and keyboard events for scrolling."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left mouse button
                # Check if click is on scrollbar
                if self.scrollbar_rect.collidepoint(event.pos):
                    self.dragging = True
                    self.drag_start_y = event.pos[1]
                    self.drag_start_scroll = self.scroll_pos
                    return True
                # Check if click is inside the content area
                elif self.rect.collidepoint(event.pos):
                    return True
            # Mouse wheel scrolling
            elif event.button == 4:  # Wheel up
                return self.scroll_up()
            elif event.button == 5:  # Wheel down
                return self.scroll_down()

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:  # Left mouse button
                self.dragging = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                # Calculate how much to scroll based on mouse movement
                mouse_delta = event.pos[1] - self.drag_start_y
                if self.max_scroll > 0:
                    scroll_ratio = mouse_delta / (self.rect.height - self.scrollbar_rect.height - 4)
                    scroll_amount = int(scroll_ratio * self.max_scroll)
                    new_scroll = min(max(0, self.drag_start_scroll + scroll_amount), self.max_scroll)
                    if new_scroll != self.scroll_pos:
                        self.scroll_pos = new_scroll
                        self._update_scrollbar()
                        return True

        return False

    def draw(self, screen):
        """Draw the scrollable area on the screen."""
        # Create a view surface that will clip the content
        view_surf = pygame.Surface((self.rect.width - self.scrollbar_width - 4, self.rect.height))
        view_surf.fill(BLACK)

        # Draw content offset by scroll position
        view_surf.blit(self.content, (0, -self.scroll_pos))

        # Draw the view on screen
        screen.blit(view_surf, (self.rect.left + 2, self.rect.top))

        # Draw scrollbar background
        scrollbar_bg = pygame.Rect(
            self.rect.right - self.scrollbar_width - 2,
            self.rect.top,
            self.scrollbar_width,
            self.rect.height
        )
        pygame.draw.rect(screen, SCROLL_BG, scrollbar_bg)

        # Draw scrollbar
        if self.max_scroll > 0:
            pygame.draw.rect(screen, SCROLL_COLOR, self.scrollbar_rect, border_radius=4)

        # Draw border around scrollable area
        pygame.draw.rect(screen, BLUE, self.rect, 1)