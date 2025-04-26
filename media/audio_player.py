import os
import tempfile
import pygame
import requests
import time

class AudioPlayer:
    def __init__(self):
        pygame.mixer.init()
        self.playing = False
        self.current_file = None
        self.temp_dir = tempfile.mkdtemp()
    def play(self, url):
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
            print(f"Błąd odtwarzania audio: {str(e)}")
            return False
    def stop(self):
        if self.playing:
            pygame.mixer.music.stop()
            self.playing = False
    def cleanup(self):
        self.stop()
        try:
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)
        except:
            pass