#!/usr/bin/env python3
"""
NASA Media Explorer
An application for browsing NASA's image and media API.

Requirements:
- pygame
- requests
- pillow (PIL)
- opencv-python (cv2) - for video thumbnail extraction
- python-vlc - for in-app video playback
"""

from app.nasa_app import NasaApp

if __name__ == "__main__":
    app = NasaApp()
    app.run()