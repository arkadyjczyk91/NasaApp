import requests
from PIL import Image
from io import BytesIO
import pygame

def fetch_image_surface(url, thumb_size, image_cache):
    cached = image_cache.get(url)
    if cached:
        return cached
    try:
        response = requests.get(url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        img = img.convert("RGBA")
        img.thumbnail((thumb_size, thumb_size))
        mode = img.mode
        size = img.size
        data = img.tobytes()
        surf = pygame.image.fromstring(data, size, mode)
        image_cache.put(url, surf)
        return surf
    except Exception as e:
        print("Błąd ładowania miniatury:", e)
        return None