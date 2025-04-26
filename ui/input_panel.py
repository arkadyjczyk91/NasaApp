class InputPanel:
    def __init__(self, fonts, x, y):
        self.fonts = fonts
        self.x = x
        self.y = y
        self.keyword = ""
        self.count = ""
        self.media_types = ["all", "image", "video", "audio", "album"]
        self.selected_media_type = 1
        self.active_control = 1  # 0: media_type, 1: keyword, 2: count

    def draw(self, screen):
        # Draw media type selector
        # Draw keyword input box
        # Draw count input box
        pass

    def handle_event(self, event):
        # Handle keyboard and mouse events for input fields
        pass

    def get_search_params(self):
        return {
            "keyword": self.keyword.strip(),
            "count": self.count.strip(),
            "media_type": self.media_types[self.selected_media_type]
        }