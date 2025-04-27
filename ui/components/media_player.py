import math
import threading
import time

import pygame

from app.config import BLUE, WHITE


class MediaPlayer:
    """A unified media player component for both audio and video."""

    def __init__(self, screen, fonts, audio_player=None, video_player=None):
        self.screen = screen
        self.fonts = fonts
        self.audio_player = audio_player
        self.video_player = video_player

        # Player state
        self.media_url = None
        self.media_type = None  # "audio" or "video"
        self.is_playing = False
        self.is_dragging_scrubber = False
        self.drag_position = 0.0
        self.is_dragging_volume = False
        self.is_fullscreen = False
        self.previous_volume = 0.85
        self.is_muted = False
        self.volume = 0.85  # 0.0 to 1.0
        self.last_interaction_time = 0
        self.controls_visible = True
        self.controls_fade_time = 3.0  # Seconds before controls fade
        self.hover_control = None
        self.last_update_time = 0  # For timer updates

        # UI elements
        self.video_area = pygame.Rect(0, 0, 100, 100)  # Will be resized
        self.control_bar_height = 40
        self.time_width = 70
        self.button_size = 32
        self.control_spacing = 10
        self.hover_alpha = 0  # For fading controls

        # Video dimensions for proper scaling
        self.video_width = 640
        self.video_height = 360

        # Control rects (will be set in draw_controls)
        self.controls = {
            'play': pygame.Rect(0, 0, self.button_size, self.button_size),
            'scrubber': pygame.Rect(0, 0, 100, 10),
            'volume': pygame.Rect(0, 0, 80, 10),
            'mute': pygame.Rect(0, 0, self.button_size, self.button_size),
            'fullscreen': pygame.Rect(0, 0, self.button_size, self.button_size)
        }

        # Start update timer
        self.timer_thread = threading.Thread(target=self._update_timer, daemon=True)
        self.timer_thread.start()

    def _update_timer(self):
        """Background thread that triggers updates for the player timer."""
        while True:
            # Post a custom user event to trigger a redraw
            if self.is_playing:
                pygame.event.post(pygame.event.Event(pygame.USEREVENT + 1, {'action': 'media_timer_tick'}))
            time.sleep(0.25)  # Update 4 times per second for smoother visuals

    def play(self, url, media_type):
        """Play media from the given URL."""
        self.media_url = url
        self.media_type = media_type
        self.is_playing = True
        self.last_interaction_time = time.time()
        self.controls_visible = True

        if media_type == "audio" and self.audio_player:
            if self.audio_player.play(url):
                # Success
                return True
            else:
                self.is_playing = False
                return False
        elif media_type == "video" and self.video_player:
            if self.video_player.play(url):
                # Success
                return True
            else:
                self.is_playing = False
                return False

        return False

    def update(self):
        """Update player state."""
        current_time = time.time()

        # Update the timer display at least once per second
        if current_time - self.last_update_time >= 1.0:
            self.last_update_time = current_time

        # Check if controls should be hidden (for video)
        if self.media_type == "video" and current_time - self.last_interaction_time > self.controls_fade_time:
            self.controls_visible = False

        # Check if media has ended
        if self.media_type == "audio" and self.audio_player:
            if self.audio_player.playing and self.audio_player.get_position() >= 0.99:
                # Audio has finished
                self.is_playing = False
        elif self.media_type == "video" and self.video_player:
            if self.video_player.is_playing and self.video_player.get_position() >= 0.99:
                # Video has finished
                self.is_playing = False

    def handle_event(self, event):
        """Handle user input events."""
        if event.type == pygame.MOUSEMOTION:
            self.last_interaction_time = time.time()
            self.controls_visible = True
            self._check_hover(event.pos)

            # Handle scrubber dragging
            if self.is_dragging_scrubber:
                relative_x = self._get_relative_scrubber_position(event.pos[0])
                self.drag_position = max(0.0, min(1.0, relative_x))
                return True

            # Handle volume dragging
            if self.is_dragging_volume:
                rel_vol = self._get_relative_volume_position(event.pos[0])
                self.volume = max(0.0, min(1.0, rel_vol))
                self._update_volume()
                return True

        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.last_interaction_time = time.time()
            self.controls_visible = True

            # Check if clicked on any controls
            if self.controls['play'].collidepoint(event.pos):
                self._toggle_playback()
                return True
            elif self.controls['scrubber'].collidepoint(event.pos):
                self.is_dragging_scrubber = True
                relative_x = self._get_relative_scrubber_position(event.pos[0])
                self.drag_position = max(0.0, min(1.0, relative_x))
                return True
            elif self.controls['mute'].collidepoint(event.pos):
                self._toggle_mute()
                return True
            elif self.controls['volume'].collidepoint(event.pos):
                self.is_dragging_volume = True
                rel_vol = self._get_relative_volume_position(event.pos[0])
                self.volume = max(0.0, min(1.0, rel_vol))
                self._update_volume()
                return True
            elif self.controls['fullscreen'].collidepoint(event.pos):
                self._toggle_fullscreen()
                return True
            # Check if clicked on video area
            elif self.video_area.collidepoint(event.pos) and self.media_type == "video":
                self._toggle_playback()
                return True

        elif event.type == pygame.MOUSEBUTTONUP:
            # If was dragging scrubber, seek to that position
            if self.is_dragging_scrubber:
                if self.media_type == "audio" and self.audio_player:
                    self.audio_player.set_position(self.drag_position)
                elif self.media_type == "video" and self.video_player:
                    self.video_player.set_position(self.drag_position)
                self.is_dragging_scrubber = False
                return True

            # If was dragging volume, apply volume
            if self.is_dragging_volume:
                self._update_volume()
                self.is_dragging_volume = False
                return True

        elif event.type == pygame.KEYDOWN:
            self.last_interaction_time = time.time()
            self.controls_visible = True

            # Space to toggle play/pause
            if event.key == pygame.K_SPACE:
                self._toggle_playback()
                return True
            # Left/Right for seeking
            elif event.key == pygame.K_RIGHT:
                self._seek_relative(0.05)  # Forward 5%
                return True
            elif event.key == pygame.K_LEFT:
                self._seek_relative(-0.05)  # Back 5%
                return True
            # Up/Down for volume
            elif event.key == pygame.K_UP:
                self.volume = min(1.0, self.volume + 0.05)
                self._update_volume()
                return True
            elif event.key == pygame.K_DOWN:
                self.volume = max(0.0, self.volume - 0.05)
                self._update_volume()
                return True
            # M for mute toggle
            elif event.key == pygame.K_m:
                self._toggle_mute()
                return True
            # F for fullscreen toggle
            elif event.key == pygame.K_f:
                self._toggle_fullscreen()
                return True
            # Escape to exit fullscreen or stop
            elif event.key == pygame.K_ESCAPE:
                if self.is_fullscreen:
                    self.is_fullscreen = False
                    return True
                else:
                    self._stop_playback()
                    return True

        # Handle timer update event
        elif event.type == pygame.USEREVENT + 1 and event.dict.get('action') == 'media_timer_tick':
            # Force an update of the display
            return True

        return False

    def _check_hover(self, pos):
        """Check if mouse is hovering over a control."""
        for control, rect in self.controls.items():
            if rect.collidepoint(pos):
                self.hover_control = control
                return
        self.hover_control = None

    def _toggle_playback(self):
        """Toggle between play and pause."""
        if self.media_type == "audio" and self.audio_player:
            if self.audio_player.paused:
                self.audio_player.resume()
                self.is_playing = True
            else:
                self.audio_player.pause()
                self.is_playing = False
        elif self.media_type == "video" and self.video_player:
            if not self.video_player.is_playing:
                self.video_player.resume()
                self.is_playing = True
            else:
                self.video_player.pause()
                self.is_playing = False

    def _stop_playback(self):
        """Stop playback completely."""
        if self.media_type == "audio" and self.audio_player:
            self.audio_player.stop()
            self.is_playing = False
        elif self.media_type == "video" and self.video_player:
            self.video_player.stop()
            self.is_playing = False

    def _seek_relative(self, amount):
        """Seek by a relative amount (-1.0 to 1.0)."""
        current_pos = 0.0

        if self.media_type == "audio" and self.audio_player:
            current_pos = self.audio_player.get_position()
            new_pos = max(0.0, min(1.0, current_pos + amount))
            self.audio_player.set_position(new_pos)
        elif self.media_type == "video" and self.video_player:
            current_pos = self.video_player.get_position()
            new_pos = max(0.0, min(1.0, current_pos + amount))
            self.video_player.set_position(new_pos)

    def _toggle_mute(self):
        """Toggle mute state."""
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.previous_volume = self.volume
            self.volume = 0.0
        else:
            self.volume = self.previous_volume
        self._update_volume()

    def _update_volume(self):
        """Update volume across all players."""
        # Set volume for pygame mixer (audio)
        pygame.mixer.music.set_volume(self.volume)

        # Set volume for video if supported
        if self.video_player and hasattr(self.video_player, 'set_volume'):
            self.video_player.set_volume(self.volume)

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        self.is_fullscreen = not self.is_fullscreen
        # Your fullscreen implementation will depend on how your app handles screen modes

    def _get_relative_scrubber_position(self, x):
        """Convert screen X coordinate to relative scrubber position."""
        scrubber = self.controls['scrubber']
        if scrubber.width <= 0:
            return 0
        rel_x = (x - scrubber.left) / float(scrubber.width)
        return max(0.0, min(1.0, rel_x))

    def _get_relative_volume_position(self, x):
        """Convert screen X coordinate to relative volume position."""
        volume_rect = self.controls['volume']
        if volume_rect.width <= 0:
            return 0
        rel_x = (x - volume_rect.left) / float(volume_rect.width)
        return max(0.0, min(1.0, rel_x))

    def draw(self, area):
        """Draw the media player within the specified area."""
        self.video_area = area
        self.update()

        # Draw the media content
        if self.media_type == "video" and self.video_player and self.video_player.is_playing:
            # Draw video frame using in-memory VLC surface
            video_surf = self.video_player.get_surface()
            scaled = pygame.transform.smoothscale(video_surf, (area.width, area.height - self.control_bar_height))
            self.screen.blit(scaled, (area.x, area.y))
        elif self.media_type == "audio":
            # For audio, draw a visualizer
            self._draw_audio_visualizer(area)
        else:
            # Draw placeholder
            pygame.draw.rect(self.screen, (0, 0, 0), area)

            # Draw play button in center
            center_icon_size = min(area.width, area.height) // 4
            center_play = pygame.Rect(
                area.centerx - center_icon_size // 2,
                area.centery - center_icon_size // 2,
                center_icon_size,
                center_icon_size
            )

            # Draw triangle play icon
            if not self.is_playing:
                points = [
                    (area.centerx - center_icon_size // 4, area.centery - center_icon_size // 2),
                    (area.centerx - center_icon_size // 4, area.centery + center_icon_size // 2),
                    (area.centerx + center_icon_size // 2, area.centery)
                ]
                pygame.draw.polygon(self.screen, (200, 200, 200, 150), points)

        # Draw controls if visible
        if self.controls_visible:
            self._draw_controls(area)


    def _draw_controls(self, area):
        """Draw the player controls."""
        # Control bar background
        control_bg_height = self.control_bar_height + 20
        control_bg = pygame.Rect(
            area.x,
            area.bottom - control_bg_height,
            area.width,
            control_bg_height
        )

        # Create semi-transparent surface for controls background
        ctrl_surf = pygame.Surface((control_bg.width, control_bg.height), pygame.SRCALPHA)
        ctrl_surf.fill((0, 0, 0, 180))  # RGBA with alpha for transparency
        self.screen.blit(ctrl_surf, (control_bg.x, control_bg.y))

        # Calculate control positions
        controls_y = area.bottom - self.control_bar_height + 10
        current_x = area.x + 10

        # Play/Pause button
        play_rect = pygame.Rect(current_x, controls_y, self.button_size, self.button_size)
        pygame.draw.rect(self.screen, (60, 60, 60), play_rect, border_radius=4)

        if self.is_playing:
            # Draw pause icon (two rectangles)
            pause_w = self.button_size // 3
            spacing = self.button_size // 6
            pygame.draw.rect(self.screen, WHITE,
                             (play_rect.x + (self.button_size - 2 * pause_w - spacing) // 2,
                              play_rect.y + self.button_size // 4,
                              pause_w, self.button_size // 2))
            pygame.draw.rect(self.screen, WHITE,
                             (play_rect.x + (self.button_size - 2 * pause_w - spacing) // 2 + pause_w + spacing,
                              play_rect.y + self.button_size // 4,
                              pause_w, self.button_size // 2))
        else:
            # Draw play icon (triangle)
            play_points = [
                (play_rect.x + self.button_size // 4, play_rect.y + self.button_size // 4),
                (play_rect.x + self.button_size // 4, play_rect.y + 3 * self.button_size // 4),
                (play_rect.x + 3 * self.button_size // 4, play_rect.y + self.button_size // 2)
            ]
            pygame.draw.polygon(self.screen, WHITE, play_points)

        self.controls['play'] = play_rect
        current_x += self.button_size + self.control_spacing

        # Current time text
        current_time_str = self._format_time(self._get_current_time())
        time_surf = self.fonts["small"].render(current_time_str, True, WHITE)
        self.screen.blit(time_surf, (current_x, controls_y + self.button_size // 2 - time_surf.get_height() // 2))
        current_x += self.time_width

        # Calculate scrubber width based on remaining space
        right_controls_width = self.time_width + self.button_size * 2 + self.control_spacing * 4 + 80  # For volume
        scrubber_width = area.width - current_x - right_controls_width - 20

        # Scrubber/progress bar
        scrubber_rect = pygame.Rect(
            current_x,
            controls_y + self.button_size // 2 - 5,
            scrubber_width,
            10
        )
        pygame.draw.rect(self.screen, (60, 60, 60), scrubber_rect, border_radius=5)

        # Draw buffered part if available
        buffered_width = scrubber_width * self._get_buffered_fraction()
        if buffered_width > 0:
            buffered_rect = pygame.Rect(
                current_x,
                controls_y + self.button_size // 2 - 5,
                buffered_width,
                10
            )
            pygame.draw.rect(self.screen, (100, 100, 100), buffered_rect, border_radius=5)

        # Draw progress part
        progress = self.drag_position if self.is_dragging_scrubber else self._get_current_position()
        progress_width = scrubber_width * progress
        if progress_width > 0:
            progress_rect = pygame.Rect(
                current_x,
                controls_y + self.button_size // 2 - 5,
                progress_width,
                10
            )
            pygame.draw.rect(self.screen, BLUE, progress_rect, border_radius=5)

        # Draw scrubber handle
        handle_x = current_x + progress_width - 6
        handle_rect = pygame.Rect(handle_x, controls_y + self.button_size // 2 - 9, 12, 18)
        pygame.draw.rect(self.screen, (200, 200, 255), handle_rect, border_radius=6)

        self.controls['scrubber'] = scrubber_rect
        current_x += scrubber_width + self.control_spacing

        # Total duration text
        total_time_str = self._format_time(self._get_total_time())
        total_surf = self.fonts["small"].render(total_time_str, True, WHITE)
        self.screen.blit(total_surf, (current_x, controls_y + self.button_size // 2 - total_surf.get_height() // 2))
        current_x += self.time_width + self.control_spacing

        # Mute button
        mute_rect = pygame.Rect(current_x, controls_y, self.button_size, self.button_size)
        pygame.draw.rect(self.screen, (60, 60, 60), mute_rect, border_radius=4)

        # Draw volume icon
        if self.is_muted or self.volume < 0.01:
            # Draw muted speaker icon
            self._draw_speaker_icon(mute_rect, muted=True)
        else:
            self._draw_speaker_icon(mute_rect, muted=False)

        self.controls['mute'] = mute_rect
        current_x += self.button_size + self.control_spacing

        # Volume slider
        volume_rect = pygame.Rect(
            current_x,
            controls_y + self.button_size // 2 - 5,
            80,
            10
        )
        pygame.draw.rect(self.screen, (60, 60, 60), volume_rect, border_radius=5)

        # Volume level
        vol_width = 80 * self.volume
        if vol_width > 0:
            vol_level_rect = pygame.Rect(
                current_x,
                controls_y + self.button_size // 2 - 5,
                vol_width,
                10
            )
            pygame.draw.rect(self.screen, (100, 180, 255), vol_level_rect, border_radius=5)

        # Volume handle
        vol_handle_x = current_x + vol_width - 6
        vol_handle_rect = pygame.Rect(vol_handle_x, controls_y + self.button_size // 2 - 9, 12, 18)
        pygame.draw.rect(self.screen, (200, 200, 255), vol_handle_rect, border_radius=6)

        self.controls['volume'] = volume_rect
        current_x += 80 + self.control_spacing

        # Fullscreen button
        fs_rect = pygame.Rect(area.right - self.button_size - 10, controls_y, self.button_size, self.button_size)
        pygame.draw.rect(self.screen, (60, 60, 60), fs_rect, border_radius=4)

        # Draw fullscreen icon
        self._draw_fullscreen_icon(fs_rect)

        self.controls['fullscreen'] = fs_rect

    def _draw_speaker_icon(self, rect, muted=False):
        """Draw a speaker icon for volume control."""
        # Draw speaker base
        speaker_w = rect.width // 3
        speaker_h = rect.height // 2
        speaker_x = rect.x + rect.width // 4
        speaker_y = rect.y + (rect.height - speaker_h) // 2

        pygame.draw.rect(self.screen, WHITE, (speaker_x, speaker_y, speaker_w, speaker_h))

        # Draw speaker cone
        cone_points = [
            (speaker_x + speaker_w, speaker_y),
            (speaker_x + speaker_w, speaker_y + speaker_h),
            (speaker_x + speaker_w + speaker_w // 2, speaker_y + speaker_h + speaker_h // 2),
            (speaker_x + speaker_w + speaker_w // 2, speaker_y - speaker_h // 2)
        ]
        pygame.draw.polygon(self.screen, WHITE, cone_points)

        if muted:
            # Draw X for muted
            x1 = rect.x + rect.width * 0.6
            y1 = rect.y + rect.height * 0.3
            x2 = rect.x + rect.width * 0.9
            y2 = rect.y + rect.height * 0.7
            pygame.draw.line(self.screen, (255, 100, 100), (x1, y1), (x2, y2), 2)
            pygame.draw.line(self.screen, (255, 100, 100), (x1, y2), (x2, y1), 2)

    def _draw_fullscreen_icon(self, rect):
        """Draw fullscreen button icon."""
        # Draw corner arrows
        margin = rect.width // 5
        size = rect.width // 3

        # Top-left corner
        pygame.draw.line(self.screen, WHITE,
                         (rect.x + margin, rect.y + margin + size // 2),
                         (rect.x + margin, rect.y + margin), 2)
        pygame.draw.line(self.screen, WHITE,
                         (rect.x + margin, rect.y + margin),
                         (rect.x + margin + size // 2, rect.y + margin), 2)

        # Top-right corner
        pygame.draw.line(self.screen, WHITE,
                         (rect.right - margin, rect.y + margin + size // 2),
                         (rect.right - margin, rect.y + margin), 2)
        pygame.draw.line(self.screen, WHITE,
                         (rect.right - margin, rect.y + margin),
                         (rect.right - margin - size // 2, rect.y + margin), 2)

        # Bottom-left corner
        pygame.draw.line(self.screen, WHITE,
                         (rect.x + margin, rect.bottom - margin - size // 2),
                         (rect.x + margin, rect.bottom - margin), 2)
        pygame.draw.line(self.screen, WHITE,
                         (rect.x + margin, rect.bottom - margin),
                         (rect.x + margin + size // 2, rect.bottom - margin), 2)

        # Bottom-right corner
        pygame.draw.line(self.screen, WHITE,
                         (rect.right - margin, rect.bottom - margin - size // 2),
                         (rect.right - margin, rect.bottom - margin), 2)
        pygame.draw.line(self.screen, WHITE,
                         (rect.right - margin, rect.bottom - margin),
                         (rect.right - margin - size // 2, rect.bottom - margin), 2)

    def _draw_audio_visualizer(self, area):
        """Draw audio visualizer when playing audio."""
        # Draw background
        pygame.draw.rect(self.screen, (14, 18, 24), area, border_radius=12)
        pygame.draw.rect(self.screen, BLUE, area, 2, border_radius=12)

        # Draw audio visualization
        position = self._get_current_position()

        # Parameters for visualization
        bar_count = 32
        max_height = area.height * 0.6

        # Start position for bars
        start_x = area.x + 30
        bar_width = (area.width - 60) / bar_count
        start_y = area.centery + 40

        # Draw each bar with height based on sin wave and position
        for i in range(bar_count):
            if not self.is_playing or (self.media_type == "audio" and self.audio_player and self.audio_player.paused):
                # Static bars when paused
                height = max_height * 0.2 * abs(((i % 5) / 5) - 0.5)
            else:
                # Animated bars when playing
                phase = position * 10 + i / bar_count
                height = max_height * 0.3 * (0.6 + 0.4 * abs(math.sin(phase * math.pi * 2)))

            bar_rect = pygame.Rect(
                start_x + i * bar_width + 2,
                start_y - height,
                bar_width - 4,
                height
            )

            # Color gradient based on position
            color_intensity = 150 + int(100 * (i / bar_count))
            bar_color = (60, min(255, color_intensity), min(255, color_intensity + 50))

            pygame.draw.rect(self.screen, bar_color, bar_rect, border_radius=3)

        # Draw audio title if available
        if self.media_url:
            filename = self.media_url.split('/')[-1]
            name_surf = self.fonts["medium"].render(filename, True, BLUE)
            self.screen.blit(name_surf, (area.centerx - name_surf.get_width() // 2, area.y + 30))

            # Status text
            status = "PLAYING" if self.is_playing else "PAUSED"
            status_surf = self.fonts["medium"].render(status, True,
                                                      (100, 255, 100) if self.is_playing else (255, 200, 100))
            self.screen.blit(status_surf, (area.centerx - status_surf.get_width() // 2, area.centery - 20))

    def _get_current_position(self):
        """Get current playback position (0.0-1.0)."""
        if not self.is_playing:
            return 0.0

        if self.media_type == "audio" and self.audio_player:
            return self.audio_player.get_position()
        elif self.media_type == "video" and self.video_player:
            return self.video_player.get_position()

        return 0.0

    def _get_buffered_fraction(self):
        """Get how much of the media is buffered (0.0-1.0)."""
        # For audio, we could check how much of the file is downloaded
        # For video, we'd get this from the video player
        if self.media_type == "audio" and self.audio_player and hasattr(self.audio_player, 'get_buffered'):
            return self.audio_player.get_buffered()
        elif self.media_type == "video" and self.video_player and hasattr(self.video_player, 'get_buffered'):
            return self.video_player.get_buffered()

        # Default value if no buffering info available
        return 0.2  # 20% buffered

    def _get_current_time(self):
        """Get current playback time in seconds."""
        position = self._get_current_position()
        total = self._get_total_time()
        return position * total

    def _get_total_time(self):
        """Get total media time in seconds."""
        if self.media_type == "audio" and self.audio_player and hasattr(self.audio_player, 'duration'):
            return max(1.0, self.audio_player.duration)  # Ensure at least 1 second

        # For video, try to get duration
        if self.media_type == "video" and self.video_player and hasattr(self.video_player, 'duration'):
            return max(1.0, self.video_player.duration)

        # Default duration if unknown
        return 60.0  # 1 minute default

    def _format_time(self, seconds):
        """Format time in seconds to MM:SS or HH:MM:SS."""
        if seconds is None:
            return "00:00"

        seconds = max(0, int(seconds))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"