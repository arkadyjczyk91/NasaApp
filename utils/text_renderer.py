import pygame

def render_text(text, font, color, max_width=None):
    """Render text with optional word wrapping."""
    if not max_width:
        return font.render(text, True, color)

    words = text.split(' ')
    lines = []
    curr = ""

    for word in words:
        test = curr + " " + word if curr else word
        if font.size(test)[0] <= max_width:
            curr = test
        else:
            lines.append(curr)
            curr = word

    if curr:
        lines.append(curr)

    h = sum(font.get_height() for _ in lines)
    surf = pygame.Surface((max([font.size(l)[0] for l in lines] + [1]), h), pygame.SRCALPHA)

    y = 0
    for l in lines:
        surf.blit(font.render(l, True, color), (0, y))
        y += font.get_height()

    return surf


def render_text_lines(text, font, color, max_width, max_lines=2):
    """Render text as a list of line surfaces with optional max lines limit."""
    words = text.split(' ')
    lines = []
    line = ""

    for word in words:
        test_line = f"{line} {word}".strip()
        if font.size(test_line)[0] <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word

    if line:
        lines.append(line)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while font.size(last + "...")[0] > max_width and last:
            last = last[:-1]
        lines[-1] = last + "..."

    return [font.render(l, True, color) for l in lines]


def shorten_url(url, maxlen=46):
    """Shorten a URL for display purposes."""
    if len(url) <= maxlen:
        return url
    return url[:maxlen // 2 - 2] + "..." + url[-maxlen // 2 + 2:]