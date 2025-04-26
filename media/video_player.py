import os
import sys
import time
import tempfile
import subprocess
import requests

class VideoPlayer:
    """Handles downloading and playing video files using the system's default player."""

    def __init__(self):
        """Initialize the video player."""
        self.temp_dir = tempfile.mkdtemp()

    def play(self, url):
        """Download and play video from URL using system's default player."""
        try:
            response = requests.get(url)
            temp_file = os.path.join(self.temp_dir, f"temp_video_{int(time.time())}.mp4")
            with open(temp_file, "wb") as f:
                f.write(response.content)

            # Open with appropriate system command
            if sys.platform == "win32":
                os.startfile(temp_file)
            elif sys.platform == "darwin":
                subprocess.call(("open", temp_file))
            else:
                subprocess.call(("xdg-open", temp_file))
            return True
        except Exception as e:
            print(f"Error playing video: {str(e)}")
            return False

    def cleanup(self):
        """Clean up temporary files."""
        try:
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)
        except:
            pass