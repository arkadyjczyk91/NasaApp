import os
import time
import tempfile
import threading
import pygame
import requests

try:
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


class AudioCache:
    """Cache for storing downloaded audio files."""

    def __init__(self, max_size=20):
        self.cache = {}  # Maps URL to (timestamp, file_path)
        self.max_size = max_size
        self.temp_dir = tempfile.mkdtemp()

    def get(self, url):
        """Get a cached audio file path if it exists."""
        if url in self.cache:
            self.cache[url] = (time.time(), self.cache[url][1])  # Update timestamp
            return self.cache[url][1]
        return None

    def put(self, url, file_path):
        """Add an audio file path to the cache."""
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_url = min(self.cache.items(), key=lambda x: x[1][0])[0]
            old_path = self.cache[oldest_url][1]
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except:
                    pass
            del self.cache[oldest_url]

        self.cache[url] = (time.time(), file_path)

    def cleanup(self):
        """Clean up all cached files."""
        for url, (_, path) in self.cache.items():
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


class AudioPlayer:
    """Service for playing audio files with streaming support."""

    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        self.temp_dir = tempfile.mkdtemp()
        self.playing = False
        self.paused = False
        self.current_file = None
        self.current_url = None
        self.download_thread = None
        self.stream_chunk_size = 1024 * 32  # 32KB chunks for streaming
        self.play_lock = threading.Lock()
        self.is_loading = False
        self.last_play_time = 0  # For debouncing
        self.audio_cache = AudioCache()
        self.duration = 0  # Estimated duration in seconds

        # For tracking playback position
        self.start_time = 0
        self.pause_time = 0
        self.position_tracker = threading.Thread(target=self._track_position, daemon=True)
        self.position_tracker.start()

    def _track_position(self):
        """Background thread to track playback position."""
        while True:
            time.sleep(0.1)  # Update 10 times per second

    def stop(self):
        """Stop the currently playing audio."""
        if self.playing:
            pygame.mixer.music.stop()
            self.playing = False
            self.paused = False

    def pause(self):
        """Pause audio playback."""
        if self.playing and not self.paused:
            pygame.mixer.music.pause()
            self.paused = True
            self.pause_time = time.time()

    def resume(self):
        """Resume audio playback."""
        if self.playing and self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
            # Adjust start_time to account for pause duration
            self.start_time += time.time() - self.pause_time

    def play(self, url):
        """Stream and play an audio file from the given URL."""
        # Debounce mechanism - prevent rapid repeated play requests
        current_time = time.time()
        if current_time - self.last_play_time < 1.0:  # 1 second debounce
            return False

        self.last_play_time = current_time

        # Check if audio is already in cache
        cached_file = self.audio_cache.get(url)
        if cached_file and os.path.exists(cached_file):
            try:
                # Play directly from cache
                self.stop()
                pygame.mixer.music.load(cached_file)
                pygame.mixer.music.play()
                self.playing = True
                self.paused = False
                self.current_file = cached_file
                self.current_url = url
                self.start_time = time.time()

                # Try to get duration for cached file
                if MUTAGEN_AVAILABLE:
                    try:
                        audio = MP3(cached_file)
                        self.duration = audio.info.length
                    except:
                        # If mutagen fails, estimate based on file size
                        file_size = os.path.getsize(cached_file)
                        self.duration = file_size / 16000  # Rough approximation
                else:
                    # If mutagen isn't installed, estimate based on file size
                    file_size = os.path.getsize(cached_file)
                    self.duration = file_size / 16000  # Rough approximation

                return True
            except Exception as e:
                print(f"Error playing cached audio: {str(e)}")
                # If there's an error, fall through to redownload

        # Don't start multiple downloads
        with self.play_lock:
            if self.is_loading:
                return False

            self.is_loading = True

        # Stop any current playback
        self.stop()
        self.current_url = url

        # Start a download thread
        self.download_thread = threading.Thread(
            target=self._download_and_play,
            args=(url,)
        )
        self.download_thread.daemon = True
        self.download_thread.start()

        return True

    def get_position(self):
        """Get current playback position as a value from 0.0 to 1.0."""
        if not self.playing:
            return 0.0

        if self.duration <= 0:
            return 0.0

        if self.paused:
            elapsed = self.pause_time - self.start_time
        else:
            elapsed = time.time() - self.start_time

        position = min(1.0, elapsed / self.duration)
        return position

    def set_position(self, position):
        """Set playback position (0.0 to 1.0)."""
        if not self.playing or self.duration <= 0:
            return

        # Calculate new position in seconds
        pos_seconds = position * self.duration

        # Pygame doesn't support seeking directly, so we need to reload and skip
        if self.current_file:
            was_paused = self.paused
            pygame.mixer.music.stop()
            pygame.mixer.music.load(self.current_file)
            pygame.mixer.music.play(start=pos_seconds)

            if was_paused:
                pygame.mixer.music.pause()
                self.paused = True
            else:
                self.paused = False

            # Update timing info
            self.start_time = time.time() - pos_seconds

    def _download_and_play(self, url):
        """Download audio and start playing as soon as possible."""
        try:
            # Unique temp filename based on URL hash
            filename = f"audio_{abs(hash(url))}.mp3"
            temp_file = os.path.join(self.temp_dir, filename)

            # Start streaming
            with requests.get(url, stream=True) as response:
                response.raise_for_status()
                content_length = int(response.headers.get('content-length', 0))

                # Rough estimation of duration based on content length
                if content_length > 0:
                    self.duration = content_length / 16000  # Rough approximation: ~128kbps
                else:
                    self.duration = 0

                # Write the first chunk to start playing quickly
                with open(temp_file, 'wb') as f:
                    downloaded = 0
                    for i, chunk in enumerate(response.iter_content(chunk_size=self.stream_chunk_size)):
                        if chunk:
                            f.write(chunk)
                            f.flush()
                            downloaded += len(chunk)

                            # Update duration estimate as we download
                            if self.duration == 0 and downloaded > 0:
                                self.duration = (content_length / downloaded) * (i + 1) * 0.1

                            # Start playing after we have the first few chunks
                            if i == 2:  # After ~64KB downloaded
                                try:
                                    pygame.mixer.music.load(temp_file)
                                    pygame.mixer.music.play()
                                    self.playing = True
                                    self.paused = False
                                    self.current_file = temp_file
                                    self.start_time = time.time()
                                except Exception as e:
                                    print(f"Error starting playback: {str(e)}")

                            # If an error occurs while downloading the rest, playback will continue with what we have

            # If we didn't start playing yet (small file), play now
            if not self.playing and os.path.exists(temp_file):
                try:
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    self.playing = True
                    self.paused = False
                    self.current_file = temp_file
                    self.start_time = time.time()

                    # Try to get accurate duration for completed file
                    if MUTAGEN_AVAILABLE:
                        try:
                            audio = MP3(temp_file)
                            self.duration = audio.info.length
                        except:
                            pass

                except Exception as e:
                    print(f"Error playing completed download: {str(e)}")

            # Add to cache
            self.audio_cache.put(url, temp_file)

        except Exception as e:
            print(f"Error streaming audio: {str(e)}")
            self.playing = False

        finally:
            self.is_loading = False

    def cleanup(self):
        """Clean up temporary files."""
        self.stop()
        self.audio_cache.cleanup()

        try:
            for file in os.listdir(self.temp_dir):
                try:
                    os.remove(os.path.join(self.temp_dir, file))
                except:
                    pass
            os.rmdir(self.temp_dir)
        except:
            pass