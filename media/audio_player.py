import os
import tempfile
import time
import pygame
import requests

class AudioPlayer:
    """Handles downloading and playing audio files."""

    def __init__(self):
        """Initialize the audio player and mixer."""
        pygame.mixer.init()
        self.playing = False
        self.current_file = None
        self.temp_dir = tempfile.mkdtemp()

    def play(self, url):
        """Download and play audio from URL."""
        try:
            self.stop()
            response = requests.get(url)
            temp_file = os.path.join(self.temp_dir, f"temp_audio_{int(time.time())}.mp3")
            with open(temp_file, "wb") as f:
                f.write(response.content)
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            self.playing = True
            self.current_file = temp_file
            return True
        except Exception as e:
            print(f"Error playing audio: {str(e)}")
            return False

    def stop(self):
        """Stop audio playback."""
        if self.playing:
            pygame.mixer.music.stop()
            self.playing = False

    def cleanup(self):
        """Clean up temporary files."""
        self.stop()
        try:
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)
        except:
            pass