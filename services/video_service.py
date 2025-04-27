import os
import time
import tempfile
import threading
import requests
import vlc
import pygame
import numpy as np
import cv2
from PIL import Image
import ctypes  # Przeniesione na początek pliku

class VideoCache:
    """Cache for storing video thumbnails and files."""
    def __init__(self, max_size=50):
        self.cache = {}  # For thumbnails
        self.file_cache = {}  # For video files (url -> path)
        self.max_size = max_size
        self.temp_dir = tempfile.mkdtemp()
    def get(self, url):
        if url in self.cache:
            self.cache[url] = (time.time(), self.cache[url][1])
            return self.cache[url][1]
        return None
    def put(self, url, thumbnail):
        if len(self.cache) >= self.max_size:
            oldest_url = min(self.cache.items(), key=lambda x: x[1][0])[0]
            del self.cache[oldest_url]
        self.cache[url] = (time.time(), thumbnail)
    def get_file(self, url):
        if url in self.file_cache:
            self.file_cache[url] = (time.time(), self.file_cache[url][1])
            return self.file_cache[url][1]
        return None
    def put_file(self, url, file_path):
        if len(self.file_cache) >= self.max_size // 2:
            oldest_url = min(self.file_cache.items(), key=lambda x: x[1][0])[0]
            old_path = self.file_cache[oldest_url][1]
            if os.path.exists(old_path):
                try: os.remove(old_path)
                except: pass
            del self.file_cache[oldest_url]
        self.file_cache[url] = (time.time(), file_path)
    def cleanup(self):
        for url, (_, path) in self.file_cache.items():
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        try:
            for file in os.listdir(self.temp_dir):
                try: os.remove(os.path.join(self.temp_dir, file))
                except: pass
            os.rmdir(self.temp_dir)
        except: pass

vlc_args = [
        '--quiet',
        '--no-video-title-show',
        '--no-sub-autodetect-file'
    ]

class VideoPlayer:
    """VLC-backed in-memory video player for Pygame overlays."""
    def __init__(self, size=(640, 360)):
        self.size = size  # (width, height)
        self.width, self.height = self.size
        self.temp_dir = tempfile.mkdtemp()
        self.video_cache = VideoCache()
        self._surface = pygame.Surface(self.size)
        self._frame = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self._vlc_frame = self._frame.ctypes.data
        self._frame_lock = threading.Lock()
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0
        self.duration = 1.0
        self.current_file = None
        self.instance = vlc.Instance(' '.join(vlc_args)) if vlc else None
        self.player = self.instance.media_player_new() if self.instance else None
        self.media = None
        self._video_ready = threading.Event()
        self._register_vlc_callbacks()

    def _register_vlc_callbacks(self):
        if not self.player:
            return

        # Definiujemy odpowiednie typy callbacków
        lock_cb = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        unlock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        display_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)

        # Inicjalizacja tablicy ramki - upewnij się że jest poprawnego rozmiaru
        self._frame = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        # Implementacje funkcji
        @lock_cb
        def _lock(cb_data, planes):
            self._frame_lock.acquire()
            try:
                arr = self._frame
                pointer = arr.ctypes.data
                planes[0] = pointer
                return pointer
            except Exception as e:
                print(f"Błąd w callback lock: {e}")
                return None

        @unlock_cb
        def _unlock(cb_data, picture, planes):
            try:
                self._frame_lock.release()
            except Exception as e:
                print(f"Błąd w callback unlock: {e}")

        @display_cb
        def _display(cb_data, picture):
            try:
                self._video_ready.set()
            except Exception as e:
                print(f"Błąd w callback display: {e}")

        # Przechowujemy referencje do callbacków
        self._lock_cb = _lock
        self._unlock_cb = _unlock
        self._display_cb = _display

        self.player.video_set_callbacks(_lock, _unlock, _display, None)

        # Wypróbuj inny format niż RV32, który może działać lepiej na Windows
        try:
            self.player.video_set_format("RGBA", self.width, self.height, self.width * 4)
        except Exception:
            # Alternatywnie spróbuj inny format
            try:
                self.player.video_set_format("RV32", self.width, self.height, self.width * 4)
            except Exception as e:
                print(f"Nie można ustawić formatu wideo: {e}")

    def play(self, url):
        """Play video from URL with frame extraction and in-memory rendering."""
        try:
            # Próba pobrania z cache
            file_path = self.video_cache.get_file(url)
            if not file_path:
                # Pobieranie pliku
                file_path = os.path.join(self.temp_dir, os.path.basename(url).replace("~", "_"))
                if not os.path.exists(file_path):
                    try:
                        with requests.get(url, stream=True, timeout=10) as r:
                            if r.status_code != 200:
                                print(f"Błąd pobierania wideo: Status {r.status_code}")
                                return False
                            with open(file_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                    except Exception as e:
                        print(f"Błąd pobierania pliku wideo: {e}")
                        return False
                self.video_cache.put_file(url, file_path)
            self.current_file = file_path

            # Inicjalizacja odtwarzacza
            if not self.instance or not self.player:
                print("VLC nie został prawidłowo zainicjowany")
                return False

            # Dodaj specjalne parametry dla niektórych formatów wideo
            media_opts = []
            self.media = self.instance.media_new(self.current_file, *media_opts)
            if not self.media:
                print("Nie można utworzyć obiektu media")
                return False

            # Ustawienie formatu wideo przed rozpoczęciem odtwarzania
            self.player.video_set_format("RV32", self.width, self.height, self.width * 4)

            self.player.set_media(self.media)
            result = self.player.play()
            if result == -1:
                print("Błąd podczas odtwarzania wideo")
                return False

            self.is_playing = True
            self.is_paused = False
            self._video_ready.clear()

            # Sprawdź czy wideo faktycznie się uruchamia
            success = False
            for _ in range(50):  # Czekaj maksymalnie 0.5s
                time.sleep(0.01)
                self.duration = self.player.get_length() / 1000.0
                if self.player.is_playing() and (self._video_ready.is_set() or self.duration > 0):
                    success = True
                    break

            if not success:
                print("Nie udało się uruchomić wideo")
                self.stop()
                return False

            return True

        except Exception as e:
            print(f"Nieoczekiwany błąd odtwarzania wideo: {e}")
            self.is_playing = False
            return False

    def get_surface(self):
        """Return a pygame.Surface of the current video frame."""
        if not self.is_playing:
            return self._surface

        try:
            with self._frame_lock:
                # Sprawdź czy bufor jest prawidłowy przed użyciem
                if self._frame is not None and self._frame.size > 0:
                    # Sprawdź poprawność wymiarów tablicy przed użyciem
                    if self._frame.shape == (self.height, self.width, 4):
                        pygame.surfarray.blit_array(self._surface, self._frame)
                    else:
                        print(
                            f"Nieprawidłowy wymiar tablicy: {self._frame.shape} zamiast {(self.height, self.width, 4)}")
                        # Przygotuj pustą ramkę
                        self._surface.fill((0, 0, 0))
                else:
                    self._surface.fill((0, 0, 0))
        except Exception as e:
            print(f"Błąd podczas przetwarzania ramki wideo: {e}")
            # Zresetuj powierzchnię w przypadku błędu
            self._surface.fill((0, 0, 0))

        return self._surface

    def pause(self):
        if self.is_playing:
            self.player.pause()
            self.is_paused = not self.is_paused

    def resume(self):
        if self.is_playing and self.is_paused:
            self.player.set_pause(0)
            self.is_paused = False

    def stop(self):
        if self.is_playing:
            self.player.stop()
            self.is_playing = False
            self.is_paused = False

    def get_position(self):
        if self.is_playing:
            try: return self.player.get_position()
            except: return 0.0
        return 0.0

    def set_position(self, position):
        if self.is_playing:
            try: self.player.set_position(float(position))
            except: pass

    def set_volume(self, volume):
        if self.is_playing:
            try: self.player.audio_set_volume(int(volume * 100))
            except: pass

    def get_buffered(self):
        return 1.0 if self.is_playing else 0.0

    def get_thumbnail(self, url, size=(320, 240)):
        cached_thumb = self.video_cache.get(url)
        if cached_thumb:
            return cached_thumb
        try:
            temp_file = os.path.join(self.temp_dir, f"thumb_{os.path.basename(url)}")
            response = requests.get(url, stream=True)
            with open(temp_file, 'wb') as f:
                for i, chunk in enumerate(response.iter_content(chunk_size=1024*1024)):
                    if chunk:
                        f.write(chunk)
                    if i > 2: break
            cap = cv2.VideoCapture(temp_file)
            cap.set(cv2.CAP_PROP_POS_MSEC, 5000)
            success, frame = cap.read()
            if not success:
                cap.set(cv2.CAP_PROP_POS_MSEC, 0)
                success, frame = cap.read()
            if success:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, size)
                img = Image.fromarray(frame)
                surf = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
                self.video_cache.put(url, surf)
                cap.release()
                os.remove(temp_file)
                return surf
        except Exception as e:
            print(f"Error generating thumbnail: {e}")
        surf = pygame.Surface(size)
        surf.fill((20, 40, 60))
        pygame.draw.polygon(surf, (100, 200, 255), [
            (size[0]//2 - size[0]//8, size[1]//2 - size[1]//4),
            (size[0]//2 - size[0]//8, size[1]//2 + size[1]//4),
            (size[0]//2 + size[0]//4, size[1]//2)
        ])
        pygame.draw.circle(surf, (100, 200, 255), (size[0]//2, size[1]//2), min(size)//4, 3)
        self.video_cache.put(url, surf)
        return surf

    def cleanup(self):
        self.stop()
        self.video_cache.cleanup()
        try:
            for file in os.listdir(self.temp_dir):
                try: os.remove(os.path.join(self.temp_dir, file))
                except: pass
            os.rmdir(self.temp_dir)
        except: pass