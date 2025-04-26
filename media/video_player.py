import os
import sys
import tempfile
import subprocess
import requests
import time

class VideoPlayer:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
    def play(self, url):
        try:
            response = requests.get(url)
            temp_file = os.path.join(self.temp_dir, f"temp_video_{int(time.time())}.mp4")
            with open(temp_file, "wb") as f:
                f.write(response.content)
            if sys.platform == "win32":
                os.startfile(temp_file)
            elif sys.platform == "darwin":
                subprocess.call(("open", temp_file))
            else:
                subprocess.call(("xdg-open", temp_file))
            return True
        except Exception as e:
            print(f"Błąd odtwarzania wideo: {str(e)}")
            return False
    def cleanup(self):
        try:
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)
        except:
            pass