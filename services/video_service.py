import os
import sys
import time
import tempfile
import threading
import requests
import cv2
import pygame
import numpy as np
from io import BytesIO
from PIL import Image
import ctypes

# For in-app video playback
try:
    import vlc
except ImportError:
    print("VLC Python bindings not found. Please install with: pip install python-vlc")
    vlc = None


class VideoCache:
    """Cache for storing video thumbnails and files."""

    def __init__(self, max_size=50):
        self.cache = {}  # For thumbnails
        self.file_cache = {}  # For video files (url -> path)
        self.max_size = max_size
        self.temp_dir = tempfile.mkdtemp()

    def get(self, url):
        """Get a cached video thumbnail if it exists."""
        if url in self.cache:
            self.cache[url] = (time.time(), self.cache[url][1])
            return self.cache[url][1]
        return None

    def put(self, url, thumbnail):
        """Add a video thumbnail to the cache."""
        if len(self.cache) >= self.max_size:
            oldest_url = min(self.cache.items(), key=lambda x: x[1][0])[0]
            del self.cache[oldest_url]
        self.cache[url] = (time.time(), thumbnail)

    def get_file(self, url):
        """Get a cached video file path if it exists."""
        if url in self.file_cache:
            self.file_cache[url] = (time.time(), self.file_cache[url][1])
            return self.file_cache[url][1]
        return None

    def put_file(self, url, file_path):
        """Add a video file path to the cache."""
        if len(self.file_cache) >= self.max_size // 2:  # Videos take more space, so limit them more
            oldest_url = min(self.file_cache.items(), key=lambda x: x[1][0])[0]
            old_path = self.file_cache[oldest_url][1]
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except:
                    pass
            del self.file_cache[oldest_url]

        self.file_cache[url] = (time.time(), file_path)

    def cleanup(self):
        """Clean up all cached files."""
        for url, (_, path) in self.file_cache.items():
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

        try:
            for file in os.listdir(self.temp_dir):
                try:
                    os.remove(os.path.join(self.temp_dir, file))
                except:
                    pass
            os.rmdir(self.temp_dir)
        except:
            pass


class VideoPlayer:
    """Service for playing video files and generating thumbnails with in-app playback."""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.video_cache = VideoCache()
        self.is_loading = False
        self.play_lock = threading.Lock()
        self.download_thread = None
        self.last_play_time = 0  # For debouncing
        self.duration = 60.0  # Default duration in seconds
        self.current_file = None  # Path to current video file

        # Player state
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0

        # Surface for rendering video
        self.video_surface = None
        self.video_frame = None

        # VLC player instance
        self.instance = None
        self.player = None
        self.media = None

        # Initialize VLC if available
        if vlc:
            # Use special parameters to get direct rendering
            if sys.platform == "win32":
                self.instance = vlc.Instance("--no-xlib --directx-volume=float --directx-use-sysmem")
            elif sys.platform == "darwin":
                self.instance = vlc.Instance("--no-xlib --vout=macosx")
            else:  # Linux
                self.instance = vlc.Instance("--no-xlib --vout=x11")

            if self.instance:
                self.player = self.instance.media_player_new()

                # Enable event tracking to get position updates
                self.event_manager = self.player.event_manager()
                self.event_manager.event_attach(vlc.EventType.MediaPlayerTimeChanged, self._time_changed)
                self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._end_reached)

    def _time_changed(self, event):
        """Handle VLC time changed event."""
        if self.player:
            self.position = self.player.get_position()

    def _end_reached(self, event):
        """Handle VLC playback end event."""
        self.is_playing = False

    def play(self, url, external=False):
        """Play video either in-app or externally."""
        # Debounce mechanism - prevent rapid repeated play requests
        current_time = time.time()
        if current_time - self.last_play_time < 1.5:  # 1.5 second debounce
            return False

        self.last_play_time = current_time

        # Don't start multiple downloads
        with self.play_lock:
            if self.is_loading:
                return False

            self.is_loading = True

        # We now prioritize in-app playback
        if external or vlc is None:
            # Fallback to system video player if VLC is not available
            self.download_thread = threading.Thread(
                target=self._stream_external_video,
                args=(url,)
            )
            self.download_thread.daemon = True
            self.download_thread.start()
        else:
            # Check if video is already cached
            cached_file = self.video_cache.get_file(url)
            if cached_file and os.path.exists(cached_file):
                self._play_video_file(cached_file)
                self.is_loading = False
                return True
            else:
                # Start streaming
                self.download_thread = threading.Thread(
                    target=self._stream_video,
                    args=(url,)
                )
                self.download_thread.daemon = True
                self.download_thread.start()
                return True

        return False

    def _play_video_file(self, file_path):
        """Play a video file using VLC."""
        if not self.player or vlc is None:
            return False

        # Stop any current playback
        self.stop()

        # Create a new media and play it
        self.media = self.instance.media_new(file_path)
        self.player.set_media(self.media)

        # Get video information
        self.media.parse()
        self.duration = max(1.0, self.media.get_duration() / 1000.0)  # Convert ms to seconds

        # Start playback
        self.player.play()
        self.is_playing = True
        self.is_paused = False
        self.current_file = file_path

        # Reset position
        self.position = 0.0

        return True

    def _stream_video(self, url):
        """Stream a video and play it in-app."""
        try:
            # First check if we need to fetch it or if it's a local URL
            if url.startswith(('http://', 'https://')):
                # Generate a unique filename
                filename = f"stream_{abs(hash(url))}.mp4"
                temp_file = os.path.join(self.temp_dir, filename)

                # We need enough data to start playback
                min_size_before_playing = 1024 * 512  # 512KB is usually enough for headers
                downloaded_size = 0
                file_started = False

                with requests.get(url, stream=True) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get('content-length', 0))

                    with open(temp_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024 * 64):
                            if chunk:
                                f.write(chunk)
                                f.flush()
                                downloaded_size += len(chunk)

                                # Once we have enough data, start playback
                                if not file_started and downloaded_size >= min_size_before_playing:
                                    self._play_video_file(temp_file)
                                    file_started = True

                    # If we didn't start yet (small file), do it now
                    if not file_started and os.path.exists(temp_file):
                        self._play_video_file(temp_file)

                    # Add to cache for future use
                    self.video_cache.put_file(url, temp_file)
            else:
                # It's a local file, play directly
                self._play_video_file(url)

        except Exception as e:
            print(f"Error streaming video: {str(e)}")
            self.is_playing = False

        finally:
            self.is_loading = False

    def _stream_external_video(self, url):
        """Stream a video and play it with the system player. Only used as fallback."""
        try:
            # Generate a unique filename
            filename = f"stream_{abs(hash(url))}.mp4"
            temp_file = os.path.join(self.temp_dir, filename)

            # Create a small status file that we can watch while the download is happening
            status_file = os.path.join(self.temp_dir, f"{filename}.status")

            # We'll start streaming to a file and launch the player once we have enough data
            min_size_before_playing = 1024 * 1024  # 1MB
            downloaded_size = 0

            with requests.get(url, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))

                player_launched = False

                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
                            f.flush()
                            downloaded_size += len(chunk)

                            # Write status file for progress info
                            with open(status_file, 'w') as sf:
                                sf.write(f"{downloaded_size}/{total_size}")

                            # Once we have enough data, launch the player
                            if not player_launched and downloaded_size >= min_size_before_playing:
                                self._launch_external_player(temp_file)
                                player_launched = True

                # If we didn't launch yet (small file), do it now
                if not player_launched and os.path.exists(temp_file):
                    self._launch_external_player(temp_file)

                # Wait a bit to make sure the player has time to read the file
                time.sleep(1)

        except Exception as e:
            print(f"Error streaming video: {str(e)}")

        finally:
            self.is_loading = False

    def _launch_external_player(self, file_path):
        """Launch the system video player with the file."""
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.call(("open", file_path))
            else:
                import subprocess
                subprocess.call(("xdg-open", file_path))
        except Exception as e:
            print(f"Error launching video player: {str(e)}")

    def update_surface(self, width, height):
        """Update the video surface size for rendering."""
        if self.video_surface is None or self.video_surface.get_size() != (width, height):
            self.video_surface = pygame.Surface((width, height))

    def render_to_surface(self, surface):
        """Render the current video frame to the given surface."""
        if not self.player or not self.is_playing:
            return

        # Get the surface dimensions
        width, height = surface.get_size()

        # Set up the rendering based on platform
        if self.player:
            if sys.platform == "win32":
                # Windows - get the video frame directly using VLC's memory access
                # This is more complex and requires direct memory access
                # For simplicity, we'll just draw a placeholder until fully implemented
                pygame.draw.rect(surface, (0, 0, 0), surface.get_rect())

                # Placeholder text for the video
                font = pygame.font.SysFont("Arial", 24)
                text = font.render("Video Playing", True, (200, 200, 200))
                surface.blit(text, (width // 2 - text.get_width() // 2, height // 2 - text.get_height() // 2))

            elif sys.platform == "darwin":
                # macOS - the video drawing is handled by VLC itself
                # Just draw a placeholder
                pygame.draw.rect(surface, (0, 0, 0), surface.get_rect())

                # Placeholder text for the video
                font = pygame.font.SysFont("Arial", 24)
                text = font.render("Video Playing", True, (200, 200, 200))
                surface.blit(text, (width // 2 - text.get_width() // 2, height // 2 - text.get_height() // 2))

            else:  # Linux
                # Linux - similar issue, just draw placeholder
                pygame.draw.rect(surface, (0, 0, 0), surface.get_rect())

                # Placeholder text for the video
                font = pygame.font.SysFont("Arial", 24)
                text = font.render("Video Playing", True, (200, 200, 200))
                surface.blit(text, (width // 2 - text.get_width() // 2, height // 2 - text.get_height() // 2))

    def get_position(self):
        """Get the current playback position (0.0-1.0)."""
        if not self.is_playing or not self.player:
            return 0.0

        return max(0.0, min(1.0, self.position))

    def set_position(self, position):
        """Set the playback position (0.0-1.0)."""
        if not self.is_playing or not self.player:
            return

        position = max(0.0, min(1.0, position))
        self.player.set_position(position)
        self.position = position

    def set_volume(self, volume):
        """Set the volume (0.0-1.0)."""
        if self.player:
            self.player.audio_set_volume(int(volume * 100))

    def pause(self):
        """Pause playback."""
        if self.is_playing and self.player:
            self.player.pause()
            self.is_paused = True

    def resume(self):
        """Resume playback."""
        if self.is_playing and self.player:
            self.player.play()
            self.is_paused = False

    def stop(self):
        """Stop video playback."""
        if self.player:
            self.player.stop()
            self.is_playing = False
            self.is_paused = False

    def get_buffered(self):
        """Get buffer progress (0.0-1.0)."""
        if not self.is_playing or not self.player or not self.media:
            return 0.0

        # VLC doesn't have a direct way to get buffer status
        # Return a simple estimate based on whether we're playing or not
        return 0.8 if self.is_playing else 0.2

    def get_thumbnail(self, url, size=(320, 240)):
        """Generate a thumbnail from a video URL."""
        # Check if thumbnail is already in cache
        cached_thumb = self.video_cache.get(url)
        if cached_thumb:
            return cached_thumb

        # If not in cache, download and generate thumbnail
        try:
            # First try to extract a frame from the video
            temp_file = os.path.join(self.temp_dir, f"temp_video_thumb_{int(time.time())}.mp4")
            response = requests.get(url, stream=True)

            # Download just enough of the file to extract a frame
            chunk_size = 1024 * 1024  # 1MB chunks
            max_size = 5 * 1024 * 1024  # Only download up to 5MB

            with open(temp_file, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded >= max_size:
                            break

            # Use OpenCV to extract a frame
            cap = cv2.VideoCapture(temp_file)

            # Try to extract a frame from 5 seconds in (to avoid black frames)
            cap.set(cv2.CAP_PROP_POS_MSEC, 5000)
            success, frame = cap.read()

            # If not successful at 5 seconds, try at the beginning
            if not success:
                cap.set(cv2.CAP_PROP_POS_MSEC, 0)
                success, frame = cap.read()

            # If we got a frame, convert it to a Pygame surface
            if success:
                # Convert BGR (OpenCV) to RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Resize to desired thumbnail size
                frame = cv2.resize(frame, size)

                # Convert to PIL Image and then to Pygame surface
                img = Image.fromarray(frame)
                mode = img.mode
                size = img.size
                data = img.tobytes()

                surf = pygame.image.fromstring(data, size, mode)

                # Add to cache
                self.video_cache.put(url, surf)

                # Clean up
                cap.release()
                if os.path.exists(temp_file):
                    os.remove(temp_file)

                return surf

            # If frame extraction failed, create a generic video icon
            cap.release()
            if os.path.exists(temp_file):
                os.remove(temp_file)

        except Exception as e:
            print(f"Error generating thumbnail: {str(e)}")

        # If all else fails, create a generic video thumbnail
        surf = self._create_generic_video_thumbnail(size)
        self.video_cache.put(url, surf)
        return surf

    def _create_generic_video_thumbnail(self, size=(320, 240)):
        """Create a generic video thumbnail with play icon."""
        surf = pygame.Surface(size)

        # Fill with dark background
        surf.fill((20, 40, 60))

        # Draw a play button icon
        width, height = size
        icon_size = min(width, height) // 2

        # Draw triangle play icon
        points = [
            (width // 2 - icon_size // 4, height // 2 - icon_size // 2),
            (width // 2 - icon_size // 4, height // 2 + icon_size // 2),
            (width // 2 + icon_size // 2, height // 2)
        ]
        pygame.draw.polygon(surf, (100, 200, 255), points)

        # Draw circle around play button
        pygame.draw.circle(surf, (100, 200, 255), (width // 2, height // 2), icon_size // 2, 3)

        return surf

    def cleanup(self):
        """Clean up temporary files."""
        self.stop()
        self.video_cache.cleanup()

        try:
            for file in os.listdir(self.temp_dir):
                try:
                    os.remove(os.path.join(self.temp_dir, file))
                except:
                    pass
            os.rmdir(self.temp_dir)
        except:
            pass