import asyncio  # NEW: added for pygbag compatibility
import pygame
import pygame.freetype
import random
import sys
import math
import numpy as np  # Ensure you have numpy installed: pip install numpy

pygame.init()

# --------------------
# Configuration Values
# --------------------
# Grid dimensions
GRID_COLS = 6
GRID_ROWS = 12
PANEL_SIZE = 320  # Increased native resolution: Pixel size of one cell (increased for high-res rendering)

# Animation durations (in seconds)
SWAP_DURATION = 0.1
CLEAR_DURATION = 0.8   # increased delay for clearing blocks (allows combo display to persist longer)
BASE_FALL_DELAY = 0.2  # increased delay for falling blocks
FALL_DELAY_MIN = 0.08
FALL_HOLD = 0.1       # time to pause before dropping a cell

# Input timings (in seconds)
INPUT_BUFFER = 0.05
SWAP_LOCKOUT = 0.15

# Chain timing
CHAIN_BASE_DELAY_INIT = 0.3
CHAIN_INCREMENTAL_DELAY_INIT = 0.1
CHAIN_BASE_DELAY_MIN = 0.2

# Colors and Symbols Toggle
ENABLE_FIFTH_SYMBOL = False  # Set to False to disable the 5th block/symbol.

# Colors (using RGB tuples)
PANEL_COLORS = [
    (239, 71, 111),   # Red-ish
    (255, 209, 102),  # Yellow-ish
    (6, 214, 160),    # Green-ish
    (17, 138, 178),   # Blue-ish
    (128, 0, 128)     # Purple-ish (New fifth color)
]
BG_COLOR = (30, 30, 30)
GRID_BG_COLOR = (10, 10, 10)
CURSOR_COLOR = (255, 255, 255)

# NEW: Combo text duration
COMBO_TEXT_DURATION = 0.3  # increased from 0.1 so the combo text lingers a bit longer

# --------------------
# Panel Class
# --------------------
class Panel:
    def __init__(self, color_index, grid_x, grid_y):
        self.color_index = color_index  # index into PANEL_COLORS
        self.state = "idle"  # idle, swapping, falling, or clearing
        self.grid_x = grid_x
        self.grid_y = grid_y
        
        # Animation timers (in seconds)
        self.swap_timer = 0
        self.clear_timer = 0
        self.fall_timer = 0
        self.fall_delay_extended = False  # flag to know if delay has been extended once
        
        # For animation offset (in pixels), used during swap or falling
        self.anim_offset = [0, 0]

    def draw(self, surface, offset_y=0):
        # Determine pixel position based on grid + animation offset, subtracting the rising offset.
        x = round(self.grid_x * PANEL_SIZE + self.anim_offset[0])
        y = round(self.grid_y * PANEL_SIZE + self.anim_offset[1] - offset_y)
        color = PANEL_COLORS[self.color_index]
        
        if self.state == "clearing":
            # Calculate progress of the disappearance animation.
            progress = 1
            if hasattr(self, "anim_elapsed") and hasattr(self, "anim_duration") and self.anim_duration > 0:
                progress = min(self.anim_elapsed / self.anim_duration, 1)
            # Use progress to compute the scale factor (full size when progress==0, gone when progress==1)
            scale_factor = 1 - progress
            new_size = max(1, int(PANEL_SIZE * scale_factor))
            offset = (PANEL_SIZE - new_size) // 2

            alpha = int(255 * scale_factor)
            fade_color = (min(color[0] + (255 - alpha), 255),
                          min(color[1] + (255 - alpha), 255),
                          min(color[2] + (255 - alpha), 255))
            panel_surface = pygame.Surface((new_size, new_size), pygame.SRCALPHA)
            panel_surface.fill(fade_color)
            surface.blit(panel_surface, (x + offset, y + offset))

            # Draw overlay "CLEAR" text if the panel is still large enough.
            if new_size > 10:
                # Scale the font size with PANEL_SIZE: default is 10 when PANEL_SIZE is 40.
                font_size = max(8, int(10 * PANEL_SIZE / 40))
                font = pygame.freetype.SysFont("Arial", font_size, bold=True)
                text_surf, text_rect = font.render("CLEAR", (255, 215, 0))
                text_x = x + (PANEL_SIZE - text_rect.width) // 2
                text_y = y + (PANEL_SIZE - text_rect.height) // 2
                surface.blit(text_surf, (text_x, text_y))
            return
        
        # Draw block background with a darkened color for the edges.
        darkened_color = (
            max(0, int(color[0] * 0.8)),
            max(0, int(color[1] * 0.8)),
            max(0, int(color[2] * 0.8))
        )
        pygame.draw.rect(surface, darkened_color, (x, y, PANEL_SIZE, PANEL_SIZE))

        # Now draw a centered inner rectangle with the full (bright) color,
        # but with a thinner (about half) edge.
        margin = int(PANEL_SIZE * 0.1)         # 10% edge thickness
        inner_size = PANEL_SIZE - 2 * margin      # inner square is 80% of PANEL_SIZE
        pygame.draw.rect(surface, color, (x + margin, y + margin, inner_size, inner_size))
        
        # Draw the symbol using geometry instead of font rendering.
        symbol_type = self.color_index  # 0: heart, 1: star, 2: clover, 3: diamond
        symbol_size = int(PANEL_SIZE * 0.6)
        center = (x + PANEL_SIZE/2, y + PANEL_SIZE/2)
        draw_symbol(surface, symbol_type, center, symbol_size, color=(0,0,0))

def draw_symbol(surface, symbol_type, center, size, color=(0,0,0)):
    """
    Draws a symbol geometry on surface.
    symbol_type: 0=heart, 1=star, 2=clover, 3=diamond, 4=circle (new).
    """
    x, y = center
    if symbol_type == 0:  # Heart
        # Draw heart as two circles and a downward triangle.
        r = size // 4
        left_circle_center = (x - r, y - r//2)
        right_circle_center = (x + r, y - r//2)
        pygame.draw.circle(surface, color, left_circle_center, r)
        pygame.draw.circle(surface, color, right_circle_center, r)
        triangle_points = [(x - 2*r, y - r//2), (x + 2*r, y - r//2), (x, y + r)]
        pygame.draw.polygon(surface, color, triangle_points)
    elif symbol_type == 1:  # Star
        # Draw a 5-pointed star by computing 10 alternating points.
        outer_radius = size // 2
        inner_radius = outer_radius * 0.5
        points = []
        for i in range(10):
            angle = math.radians(i * 36 - 90)  # Rotate so one point is upward.
            rad = outer_radius if i % 2 == 0 else inner_radius
            px = x + rad * math.cos(angle)
            py = y + rad * math.sin(angle)
            points.append((px, py))
        pygame.draw.polygon(surface, color, points)
    elif symbol_type == 2:  # Clover
        # Draw a clover using three circles and an optional stem.
        r = size // 4
        pygame.draw.circle(surface, color, (x, y - r), r)
        pygame.draw.circle(surface, color, (x - r, y + r//2), r)
        pygame.draw.circle(surface, color, (x + r, y + r//2), r)
        stem_width = r // 2
        stem_height = r
        stem_rect = pygame.Rect(x - stem_width//2, y + r, stem_width, stem_height)
        pygame.draw.rect(surface, color, stem_rect)
    elif symbol_type == 3:  # Diamond
        half = size // 2
        diamond_points = [(x, y - half), (x + half, y), (x, y + half), (x - half, y)]
        pygame.draw.polygon(surface, color, diamond_points)
    elif symbol_type == 4:  # Circle (new symbol for fifth block)
        radius = size // 3  # Adjust radius as needed
        pygame.draw.circle(surface, color, (int(x), int(y)), radius)

# --------------------
# Board Class
# --------------------
class Board:
    def __init__(self):
        # Initialize grid: only bottom 8 rows have blocks; top 4 rows are empty.
        self.grid = []
        for x in range(GRID_COLS):
            col_data = []
            for y in range(GRID_ROWS):
                if y < GRID_ROWS - 8:
                    col_data.append(None)
                else:
                    # Choose a color index that avoids immediate vertical/horizontal matches.
                    available_color = random.randrange(len(PANEL_COLORS) if ENABLE_FIFTH_SYMBOL else 4)

                    # Check vertical: if there are at least two panels already in this column.
                    if y >= (GRID_ROWS - 8 + 2):
                        while (col_data[y - 1] is not None and col_data[y - 2] is not None and
                               col_data[y - 1].color_index == available_color and
                               col_data[y - 2].color_index == available_color):
                            available_color = random.randrange(len(PANEL_COLORS) if ENABLE_FIFTH_SYMBOL else 4)

                    # Check horizontal: if there are at least two previously built columns.
                    if x >= 2:
                        # Get the panels from the previous two columns at row y.
                        left_panel = self.grid[x - 1][y] if self.grid[x - 1][y] is not None else None
                        left2_panel = self.grid[x - 2][y] if self.grid[x - 2][y] is not None else None
                        if left_panel is not None and left2_panel is not None:
                            while left_panel.color_index == available_color and left2_panel.color_index == available_color:
                                available_color = random.randrange(len(PANEL_COLORS) if ENABLE_FIFTH_SYMBOL else 4)

                    col_data.append(Panel(available_color, x, y))
            self.grid.append(col_data)

        # Initialize upcoming row for preview (each value is a color index).
        self.upcoming_row = [random.randrange(len(PANEL_COLORS) if ENABLE_FIFTH_SYMBOL else 4) for _ in range(GRID_COLS)]
        # NEW: also store the next upcoming row so that it is visible before spawning.
        self.next_upcoming_row = [random.randrange(len(PANEL_COLORS) if ENABLE_FIFTH_SYMBOL else 4) for _ in range(GRID_COLS)]
        
        self.swap_lockout_timer = 0
        self.score = 0
        self.current_fall_delay = BASE_FALL_DELAY
        self.current_chain_base_delay = CHAIN_BASE_DELAY_INIT
        self.current_chain_incremental_delay = CHAIN_INCREMENTAL_DELAY_INIT

        # Rising Floor Mechanic (smooth rising)
        self.current_rise_delay = 5.0  # seconds for one full cell rise
        self.min_rise_delay = 1      # rising speed will never exceed 1 sec per cell
        self.rise_offset = 0         # current vertical offset (in pixels)
        self.top_row_timer = 0
        self.risen_this_frame = False

        # Timer to pause rising during extensive matches.
        self.chain_pause_timer = 0
        # (No combo chain/timer mechanics anymore)

        # Shared fall offset (in pixels) for each column; used only when blocks are actively falling.
        self.col_fall_offsets = [0 for _ in range(GRID_COLS)]
        # New: match delay timer; after a drop, wait 0.25 seconds before checking for matches.
        self.match_delay_timer = 0

        # Add a flag for match event so that a match only triggers once until the board settles.
        self.match_event_active = False

    def update(self, dt, shift_pressed=False):
        # Update swap lockout timer
        if self.swap_lockout_timer > 0:
            self.swap_lockout_timer -= dt

        # Update panels on board
        for col in range(GRID_COLS):
            for row in range(GRID_ROWS):
                panel = self.grid[col][row]
                if panel is None:
                    continue
                # Update swapping state
                if panel.state == "swapping":
                    panel.swap_timer -= dt
                    progress = 1 - (panel.swap_timer / SWAP_DURATION)
                    if progress >= 1:
                        progress = 1
                        panel.anim_offset[0] = 0
                        panel.state = "idle"
                    else:
                        panel.anim_offset[0] = panel.swap_origin * (1 - progress)
                # Update clearing state
                if panel.state == "clearing":
                    # Stagger the animation using clear_delay.
                    if panel.clear_delay > 0:
                        panel.clear_delay -= dt
                        if panel.clear_delay < 0:
                            # If dt overshoots, add excess time to anim_elapsed.
                            panel.anim_elapsed += -panel.clear_delay
                            panel.clear_delay = 0
                    else:
                        panel.anim_elapsed += dt
                        # Play vanish sound as soon as the animation starts (if not yet played)
                        if not panel.sound_played:
                            if hasattr(self, "vanish_sounds") and self.vanish_sounds:
                                sound_idx = panel.sound_index if hasattr(panel, "sound_index") else 0
                                self.vanish_sounds[sound_idx].play()
                            panel.sound_played = True

                    progress = min(panel.anim_elapsed / panel.anim_duration, 1)
                    if progress >= 1:
                        self.grid[col][row] = None
                    continue

        # Apply gravity for panels that are idle and have empty cells below.
        if self.chain_pause_timer <= 0:
            self.apply_gravity(dt)

        # --- Check for matches with a fixed delay  ---
        # If not already in a match event, look for a match and (if found) set a constant delay.
        if not self.match_event_active:
            matches = self.check_matches()
            if matches:
                self.match_event_active = True
                # If the board is not stable (i.e. some panels are falling or waiting), double the recheck time.
                if not self.board_is_stable():
                    self.match_delay_timer = 0.15 * 2
                else:
                    self.match_delay_timer = 0.15
        else:
            # Match event already active: count down the fixed delay.
            self.match_delay_timer -= dt
            if self.match_delay_timer <= 0:
                # Final check: process the match if still present.
                matches = self.check_matches()
                if matches:
                    match_size = len(matches)
                    # Set freeze time: 0.5 seconds for a 4+ match, 0.25 seconds for a 3-match.
                    freeze_time = 1 if match_size >= 4 else 0.75
                    self.chain_pause_timer = freeze_time
                    if match_size >= 4:
                        if hasattr(self, "chain_sound"):
                            self.chain_sound.play()
                    # Sort matches so that they clear in an order (e.g. top-to-bottom, left-to-right)
                    matches_sorted = sorted(matches, key=lambda pos: (pos[1], pos[0]))
                    # Assign a sound delay for each panel: later ones will have a longer delay.
                    num = len(matches_sorted)
                    for i, (col, row) in enumerate(matches_sorted):
                        panel = self.grid[col][row]
                        if panel and panel.state != "clearing":
                            panel.anim_offset = [0, 0]
                            panel.state = "clearing"
                            # Subtract a small offset (0.05 sec) so that the vanish sound plays a bit earlier.
                            panel.clear_delay = max(0, i * (CLEAR_DURATION / num) - 0.05)
                            panel.anim_duration = CLEAR_DURATION - panel.clear_delay
                            panel.anim_elapsed = 0.0
                            # Retain the vanish sound index as before.
                            panel.sound_index = i if i < 7 else 6
                            panel.sound_played = False
                    self.score += 100 * match_size
                    self.top_row_timer = 0
                # Reset the match event flag so new matches can be detected.
                self.match_event_active = False

        # ------ Gradual Rising Floor Mechanic ------
        self.risen_this_frame = False
        if self.chain_pause_timer > 0:
            self.chain_pause_timer -= dt
            rising_speed = 0
        else:
            effective_delay = self.min_rise_delay if shift_pressed else self.current_rise_delay
            rising_speed = PANEL_SIZE / effective_delay

        # Prevent rising if any block in the top row is present.
        top_occupied = any(self.grid[col][0] is not None for col in range(GRID_COLS))
        if top_occupied:
            rising_speed = 0

        self.rise_offset += rising_speed * dt
        if self.rise_offset >= PANEL_SIZE:
            self.rise_offset -= PANEL_SIZE
            self.rise()  # shift the grid by one full cell upward
            self.risen_this_frame = True
            # Increase rising speed gradually, but not below the minimum.
            self.current_rise_delay = max(self.min_rise_delay, self.current_rise_delay - 0.1)

        # Check for game over: if any block occupies the top row for 3 or more seconds.
        game_over = False
        for col in range(GRID_COLS):
            if self.grid[col][0] is not None:
                # Drawn y = (grid row * PANEL_SIZE) - rise_offset
                drawn_y = 0 * PANEL_SIZE - self.rise_offset
                if drawn_y <= 0:
                    game_over = True
                    break
        if game_over:
            self.top_row_timer += dt
        else:
            self.top_row_timer = 0
        # ------------------------------------------

        # Smooth Falling Animation using a continuously accumulating column offset.
        for col in range(GRID_COLS):
            # Check if the column has any falling panel.
            falling_in_column = False
            for row in range(GRID_ROWS):
                panel = self.grid[col][row]
                if panel is not None and panel.state == "falling":
                    falling_in_column = True
                    break

            if falling_in_column:
                # Increase the column's fall offset continuously.
                # Falling speed: PANEL_SIZE pixels per FALL_HOLD seconds.
                self.col_fall_offsets[col] += (PANEL_SIZE / FALL_HOLD) * dt
            else:
                # Reset offset if nothing is falling.
                self.col_fall_offsets[col] = 0

            # If offset has reached a full cell, snap falling panels one cell at a time.
            while self.col_fall_offsets[col] >= PANEL_SIZE:
                for row in range(GRID_ROWS-1, -1, -1):
                    panel = self.grid[col][row]
                    if panel is not None and panel.state == "falling":
                        target_y = panel.grid_y + 1
                        if target_y < GRID_ROWS and self.grid[col][target_y] is None:
                            self.grid[col][panel.grid_y] = None
                            panel.grid_y = target_y
                            self.grid[col][panel.grid_y] = panel
                            any_drop = True
                        else:
                            panel.state = "idle"
                        panel.anim_offset[1] = 0
                self.col_fall_offsets[col] -= PANEL_SIZE

            # Calculate smooth progress (0 to 1) from the remaining offset.
            progress = self.col_fall_offsets[col] / PANEL_SIZE
            for row in range(GRID_ROWS-1, -1, -1):
                panel = self.grid[col][row]
                if panel is not None and panel.state == "falling":
                    # If the panel is at the bottom or cannot fall further, force offset to 0.
                    if panel.grid_y == GRID_ROWS - 1 or (panel.grid_y < GRID_ROWS - 1 and self.grid[col][panel.grid_y+1] is not None):
                        panel.anim_offset[1] = 0
                    else:
                        panel.anim_offset[1] = progress * PANEL_SIZE

    def apply_gravity(self, dt):
        # Start from second-to-last row upward (bottom row cannot fall)
        FALL_START_DELAY = 0.05  # base delay before a panel starts falling
        for col in range(GRID_COLS):
            for row in range(GRID_ROWS - 2, -1, -1):
                panel = self.grid[col][row]
                if panel is None or panel.state != "idle":
                    continue
                if self.grid[col][row+1] is None:
                    # Set base delay and adjust if chain freeze (match of 4+ blocks) is active.
                    base_delay = FALL_START_DELAY
                    if self.chain_pause_timer > 0:
                        base_delay *= 1.5
                    # If this panel is not already waiting, set the delay.
                    if panel.fall_timer <= 0:
                        panel.fall_timer = base_delay
                        panel.fall_delay_extended = False
                    elif not panel.fall_delay_extended:
                        # If already waiting but not extended yet, extend the delay.
                        panel.fall_timer = base_delay * 2
                        panel.fall_delay_extended = True
                    panel.fall_timer -= dt
                    if panel.fall_timer <= 0:
                        panel.state = "falling"
                        panel.fall_timer = 0
                        panel.fall_delay_extended = False
                else:
                    # If the panel is supported, reset any waiting delay.
                    panel.fall_timer = 0
                    panel.fall_delay_extended = False
        # Cascade falling: if an idle panel has a falling block right beneath it,
        # force the idle panel to fall immediately.
        for col in range(GRID_COLS):
            for row in range(0, GRID_ROWS - 1):
                current = self.grid[col][row]
                below = self.grid[col][row+1]
                if current is not None and current.state == "idle" and below is not None and below.state == "falling":
                    current.state = "falling"

    def get_effective_panel(self, col, row):
        """
        Returns the panel at grid[col][row] for match detection.
        Falling panels (i.e. panels whose state is "falling") are ignored so that they only match when they've landed.
        """
        panel = self.grid[col][row]
        if panel is not None and panel.state == "falling":
            return None
        return panel

    def check_matches(self):
        # Return all matched panels as long as there are at least 3 matches.
        to_clear = set()
        # horizontal matches: allow falling blocks to be matched as long as they aren't clearing.
        for row in range(GRID_ROWS):
            count = 1
            for col in range(1, GRID_COLS):
                curr = self.get_effective_panel(col, row)
                prev = self.get_effective_panel(col - 1, row)
                if (curr and prev and curr.state != "clearing" and prev.state != "clearing"
                        and curr.color_index == prev.color_index):
                    count += 1
                else:
                    if count >= 3:
                        for k in range(count):
                            to_clear.add((col - 1 - k, row))
                    count = 1
            if count >= 3:
                for k in range(count):
                    to_clear.add((GRID_COLS - 1 - k, row))
                    
        # vertical matches: now use the effective panels.
        for col in range(GRID_COLS):
            count = 1
            for row in range(1, GRID_ROWS):
                curr = self.get_effective_panel(col, row)
                prev = self.get_effective_panel(col, row - 1)
                if (curr and prev and curr.state != "clearing" and prev.state != "clearing"
                        and curr.color_index == prev.color_index):
                    count += 1
                else:
                    if count >= 3:
                        for k in range(count):
                            to_clear.add((col, row - 1 - k))
                    count = 1
            if count >= 3:
                for k in range(count):
                    to_clear.add((col, GRID_ROWS - 1 - k))
 
        # Return all matched panels as long as there are at least 3 matches.
        if len(to_clear) >= 3:
            return list(to_clear)
        return []

    def do_swap(self, x, y):
        # Ensure coordinates are within range.
        if x < 0 or x >= GRID_COLS - 1 or y < 0 or y >= GRID_ROWS:
            return
        p1 = self.grid[x][y]
        p2 = self.grid[x+1][y]

        # If both cells are empty, nothing to swap.
        if p1 is None and p2 is None:
            return

        # Only allow swapping if both panels are idle.
        if (p1 is not None and p1.state != "idle") or (p2 is not None and p2.state != "idle"):
            return

        # Initiate swapping animation for panels that exist.
        if p1 is not None:
            p1.state = "swapping"
            p1.swap_timer = SWAP_DURATION
            p1.swap_direction = +1
            # Set the initial offset so that the left panel starts from -PANEL_SIZE.
            p1.swap_origin = -PANEL_SIZE
            p1.anim_offset[0] = p1.swap_origin
        if p2 is not None:
            p2.state = "swapping"
            p2.swap_timer = SWAP_DURATION
            p2.swap_direction = -1
            # The right panel starts from +PANEL_SIZE.
            p2.swap_origin = PANEL_SIZE
            p2.anim_offset[0] = p2.swap_origin

        # Swap positions in the grid.
        self.grid[x][y], self.grid[x+1][y] = p2, p1

        # Safely update grid_x for panels that exist.
        if p1 is not None:
            p1.grid_x = x+1
        if p2 is not None:
            p2.grid_x = x

        # Set swap lockout to a third of the original time.
        self.swap_lockout_timer = SWAP_LOCKOUT / 6

        # Play swap sound effect if available.
        if hasattr(self, "swap_sound"):
            self.swap_sound.play()

    def draw(self, surface):
        # Draw each panel with a vertical shift of rise_offset.
        for col in range(GRID_COLS):
            for row in range(GRID_ROWS):
                panel = self.grid[col][row]
                if panel:
                    panel.draw(surface, offset_y=self.rise_offset)
        # Draw upcoming row preview below the grid.
        self.draw_upcoming(surface)

    def draw_upcoming(self, surface):
        # Compute the base y-position as exactly at the bottom edge of the main grid.
        base_y = GRID_ROWS * PANEL_SIZE

        # Draw the imminent preview row (which will spawn next) at the very bottom of the grid.
        for col in range(GRID_COLS):
            color_index = self.upcoming_row[col]
            color = PANEL_COLORS[color_index]
            preview = pygame.Surface((PANEL_SIZE, PANEL_SIZE), pygame.SRCALPHA)
            preview.fill((0,0,0,0))

            # Draw darkened edge for the preview.
            darkened_color = (
                max(0, int(color[0] * 0.8)),
                max(0, int(color[1] * 0.8)),
                max(0, int(color[2] * 0.8)),
                80
            )
            pygame.draw.rect(preview, darkened_color, (0, 0, PANEL_SIZE, PANEL_SIZE))

            # Draw a centered inner rectangle (brighter center) with a thinner edge.
            margin = int(PANEL_SIZE * 0.1)         # 10% edge thickness
            inner_size = PANEL_SIZE - 2 * margin      # inner square is 80% of PANEL_SIZE
            bright_color = (color[0], color[1], color[2], 80)
            pygame.draw.rect(preview, bright_color, (margin, margin, inner_size, inner_size))

            # Instead of text, draw the symbol geometry.
            symbol_type = color_index  # 0: heart, 1: star, 2: clover, 3: diamond
            symbol_size = int(PANEL_SIZE * 0.6)
            center = (PANEL_SIZE//2, PANEL_SIZE//2)
            draw_symbol(preview, symbol_type, center, symbol_size, color=(0,0,0))

            # Round the positions for smooth, jitter-free placement.
            x = round(col * PANEL_SIZE)
            y = round(base_y - self.rise_offset)
            surface.blit(preview, (x, y))

        # Draw the next preview row (for continuity) exactly one cell below the imminent preview.
        for col in range(GRID_COLS):
            color_index = self.next_upcoming_row[col]
            color = PANEL_COLORS[color_index]
            preview = pygame.Surface((PANEL_SIZE, PANEL_SIZE), pygame.SRCALPHA)
            preview.fill((0,0,0,0))

            # Darkened edge.
            darkened_color = (
                max(0, int(color[0] * 0.8)),
                max(0, int(color[1] * 0.8)),
                max(0, int(color[2] * 0.8)),
                80
            )
            pygame.draw.rect(preview, darkened_color, (0, 0, PANEL_SIZE, PANEL_SIZE))

            # Centered inner rectangle (bright center).
            margin = int(PANEL_SIZE * 0.1)
            inner_size = PANEL_SIZE - 2 * margin
            bright_color = (color[0], color[1], color[2], 80)
            pygame.draw.rect(preview, bright_color, (margin, margin, inner_size, inner_size))

            # Instead of text, draw the symbol geometry.
            symbol_type = color_index  # 0: heart, 1: star, 2: clover, 3: diamond
            symbol_size = int(PANEL_SIZE * 0.6)
            center = (PANEL_SIZE//2, PANEL_SIZE//2)
            draw_symbol(preview, symbol_type, center, symbol_size, color=(0,0,0))

            # Round positions to avoid jitter.
            x = round(col * PANEL_SIZE)
            y = round(base_y - self.rise_offset + PANEL_SIZE)
            surface.blit(preview, (x, y))

    # ---- Added rise method ----
    def rise(self):
        # Shift all panels upward by one full cell.
        for col in range(GRID_COLS):
            self.grid[col].pop(0)
            # Use the color from the upcoming row so that the spawned block matches the preview.
            new_color = self.upcoming_row[col]
            new_panel = Panel(new_color, col, GRID_ROWS - 1)
            self.grid[col].append(new_panel)
        for col in range(GRID_COLS):
            for row in range(GRID_ROWS):
                panel = self.grid[col][row]
                if panel:
                    panel.grid_y = row
        # Update the upcoming row with new random blocks.
        self.upcoming_row = self.next_upcoming_row
        self.next_upcoming_row = [random.randrange(len(PANEL_COLORS) if ENABLE_FIFTH_SYMBOL else 4) for _ in range(GRID_COLS)]

    def board_is_stable(self):
        # Returns True if no panel is falling or waiting to fall (via fall_timer)
        for col in range(GRID_COLS):
            for row in range(GRID_ROWS):
                panel = self.grid[col][row]
                if panel is not None:
                    if panel.state == "falling" or panel.fall_timer > 0:
                        return False
        return True

# --------------------
# Cursor Class
# --------------------
class Cursor:
    def __init__(self):
        # Starts at upper left
        self.x = 0
        self.y = 0

    def move(self, dx, dy):
        # Allow horizontal movement, ensuring the cursor never leaves the board.
        self.x = max(0, min(GRID_COLS - 2, self.x + dx))
        # If moving upward and already at top row, do nothing.
        if dy < 0 and self.y == 0:
            return
        self.y = max(0, min(GRID_ROWS - 1, self.y + dy))

    def draw(self, surface, offset_y=0):
        x = self.x * PANEL_SIZE
        y = self.y * PANEL_SIZE - offset_y
        # Adjust the border margin to scale with PANEL_SIZE (default is 2 when PANEL_SIZE is 40).
        border_margin = max(2, int(PANEL_SIZE / 40 * 2))
        # Ensure the cursor is not drawn off the left edge.
        x = max(x, border_margin)
        # Ensure the cursor is not drawn off the right edge.
        if x + PANEL_SIZE * 2 + border_margin > GRID_COLS * PANEL_SIZE:
            x = GRID_COLS * PANEL_SIZE - PANEL_SIZE * 2 - border_margin
        # Ensure the cursor is not drawn off the top edge.
        y = max(y, border_margin)
        thickness = max(1, int(PANEL_SIZE / 40 * 2))
        pygame.draw.rect(surface, CURSOR_COLOR, (x, y, PANEL_SIZE * 2, PANEL_SIZE), thickness)

# --------------------
# Game Class
# --------------------
class Game:
    def __init__(self):
        pygame.mixer.set_num_channels(16)

        # Load sound effects.
        self.swap_sound = pygame.mixer.Sound("swap.wav")
        self.swap_sound.set_volume(0.2)  # Set swap sound volume to 20%
        self.chain_sound = pygame.mixer.Sound("chain.wav")
        self.chain_sound.set_volume(0.2)  # Set block match (chain) sound to 20% volume

        # NEW: Load a single vanish sound and precompute 7 variants.
        base_vanish = pygame.mixer.Sound("vanish.wav")
        vanish_array = pygame.sndarray.array(base_vanish)
        self.vanish_sounds = []
        # Prepare 7 different pitch factors, e.g. 1.0, 1.1, 1.2, ... 1.6
        pitch_factors = [1.0 + 0.1 * i for i in range(7)]
        for factor in pitch_factors:
            new_array = pitch_shift_sound(vanish_array, factor)
            new_sound = pygame.sndarray.make_sound(new_array)
            new_sound.set_volume(0.1)  # Ensure the pitch-shifted vanish sound is set to 20% volume
            self.vanish_sounds.append(new_sound)

        # Background music tracks.
        self.bg_normal = "bg_normal.ogg"
        self.bg_danger = "bg_danger.ogg"
        self.current_bg = "normal"  # current background flag

        # Start with normal background music.
        pygame.mixer.music.load(self.bg_normal)
        pygame.mixer.music.set_volume(0.2)  # Set background music volume to 20%
        pygame.mixer.music.play(-1)

        self.scale = 1
        # Get current screen resolution for fullscreen.
        info = pygame.display.Info()
        self.native_size = (info.current_w, info.current_h)
        # Create a borderless fullscreen window.
        self.screen = pygame.display.set_mode(self.native_size, pygame.FULLSCREEN | pygame.NOFRAME, vsync=1)
        pygame.display.set_caption("Tetris Attack Clone")
        self.clock = pygame.time.Clock()
        self.board = Board()
        # NEW: Query the desktop refresh rate (requires pygame 2). If not available, default to 60.
        try:
            desktop_mode = pygame.display.get_desktop_display_mode()
            self.refresh_rate = desktop_mode.refresh_rate
        except Exception:
            self.refresh_rate = 144
        print("Using refresh rate:", self.refresh_rate)
        self.board.swap_sound = self.swap_sound
        self.board.chain_sound = self.chain_sound
        # NEW: Provide the precomputed vanish sounds to the board.
        self.board.vanish_sounds = self.vanish_sounds
        self.cursor = Cursor()
        self.native_surface = pygame.Surface(self.native_size)
        self.info_font = pygame.freetype.SysFont("Arial", 28)

        # Timers for falling delay progression & difficulty
        self.difficulty_timer = 0  # increments with game time

        self.total_time = 0  # elapsed game time (in seconds)
        # New background offset for retro diagonal scrolling pattern.
        self.background_offset = 0

    async def run(self):
        running = True
        while running:
            dt = self.clock.tick(self.refresh_rate) / 1000.0  # Ticking at the monitor's refresh rate
            await asyncio.sleep(0)  # NEW: required for pygbag compatibility

            # Check if left Shift is held; if so, set shift_pressed True (rising speed capped to 2 sec per cell).
            keys = pygame.key.get_pressed()
            shift_pressed = keys[pygame.K_LSHIFT]

            self.total_time += dt
            self.difficulty_timer += dt

            # Increase difficulty every 30 seconds
            if self.difficulty_timer >= 30:
                self.difficulty_timer -= 30
                # Decrease falling delay but not below min
                self.board.current_fall_delay = max(FALL_DELAY_MIN, self.board.current_fall_delay - 0.01)
                # Decrease chain delays (base and incremental) with minimum base delay check
                self.board.current_chain_base_delay = max(CHAIN_BASE_DELAY_MIN, self.board.current_chain_base_delay - 0.02)
                self.board.current_chain_incremental_delay = max(0, self.board.current_chain_incremental_delay - 0.01)

            # Event handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif self.board.swap_lockout_timer <= 0:
                        # Move cursor using either arrow keys or WASD
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            self.cursor.move(-1, 0)
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            self.cursor.move(1, 0)
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            self.cursor.move(0, -1)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            self.cursor.move(0, 1)
                        elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                            # When swapping, swap the panel under the cursor with the one to its right
                            self.board.do_swap(self.cursor.x, self.cursor.y)
                elif event.type == pygame.VIDEORESIZE:
                    # Update native_size and reinitialize the display mode with new dimensions.
                    self.native_size = (event.w, event.h)
                    self.screen = pygame.display.set_mode(self.native_size, pygame.RESIZABLE, vsync=1)

            # Update game mechanics
            self.board.update(dt, shift_pressed)
            # If a full cell rise occurred, adjust the cursor upward to follow the blocks.
            if self.board.risen_this_frame:
                self.cursor.y = max(self.cursor.y - 1, 0)

            # Background music switching based on block height.
            # Safe zone: blocks with grid_y >= (GRID_ROWS - 8). Danger if any block has grid_y < (GRID_ROWS - 8).
            danger = False
            for col in range(GRID_COLS):
                for row in range(GRID_ROWS):
                    panel = self.board.grid[col][row]
                    if panel is not None and panel.grid_y < (GRID_ROWS - 8):
                        danger = True
                        break
                if danger:
                    break

            if danger and self.current_bg != "danger":
                pygame.mixer.music.load(self.bg_danger)
                pygame.mixer.music.set_volume(0.2)  # Ensure background music volume is 20%
                pygame.mixer.music.play(-1)
                self.current_bg = "danger"
            elif not danger and self.current_bg != "normal":
                pygame.mixer.music.load(self.bg_normal)
                pygame.mixer.music.set_volume(0.2)  # Ensure background music volume is 20%
                pygame.mixer.music.play(-1)
                self.current_bg = "normal"

            # Check for game over condition: if any panel occupies the top row for 3 or more seconds.
            if self.board.top_row_timer >= 3:
                running = False
                continue

            # Create a separate game surface representing the actual game area.
            # Define native game area dimensions: width = GRID_COLS * PANEL_SIZE,
            # height = GRID_ROWS * PANEL_SIZE + PANEL_SIZE (including the upcoming row preview).
            game_width = GRID_COLS * PANEL_SIZE
            game_height = GRID_ROWS * PANEL_SIZE + PANEL_SIZE
            game_surface = pygame.Surface((game_width, game_height))
            game_surface.fill(BG_COLOR)

            # Draw the game: board, cursor, and score.
            self.board.draw(game_surface)
            self.cursor.draw(game_surface, offset_y=self.board.rise_offset)
            
            # Reserve space for an info panel on the right and controls panel on the left.
            info_panel_width = 200
            vertical_margin = 100
            available_width = self.native_size[0] - info_panel_width
            available_height = self.native_size[1] - vertical_margin
            scale_factor = min(available_width / game_width, available_height / game_height)
            scaled_width = int(game_width * scale_factor)
            scaled_height = int(game_height * scale_factor)
            x_offset = (available_width - scaled_width) // 2
            y_offset = vertical_margin // 2

            self.screen.fill((0, 0, 0))  # Clear the screen.
            # Draw the retro-style scrolling background.
            self.draw_background(self.screen)

            # Scale the game_surface and draw it at computed offset.
            scaled_game_surface = pygame.transform.scale(game_surface, (scaled_width, scaled_height))
            self.screen.blit(scaled_game_surface, (x_offset, y_offset))

            # Draw a border around the gameplay area.
            game_rect = pygame.Rect(x_offset, y_offset, scaled_width, scaled_height)
            pygame.draw.rect(self.screen, (0, 0, 0), game_rect, 5)
            inner_rect = game_rect.inflate(-8, -8)
            pygame.draw.rect(self.screen, (255, 0, 0), inner_rect, 3)

            # Draw the info panel (score and game info) just to the right.
            info_x = x_offset + scaled_width + 10   # 10-pixel padding
            info_y = y_offset
            self.draw_info_panel(self.screen, info_x, info_y)

            # Draw the controls panel on the left side.
            # Move the controls panel further to the left (twice as much as before).
            controls_x = x_offset - 360   # (panel width 200 + 260-pixel padding)
            controls_y = y_offset
            self.draw_controls_panel(self.screen, controls_x, controls_y)

            pygame.display.update()

            # Update background offset for scrolling effect (diagonal speed 30 pixels per second).
            self.background_offset += 30 * dt
            # Wrap around the spacing (here 50 pixels).
            self.background_offset %= 50

        pygame.quit()
        sys.exit()

    def draw_info_panel(self, target_surface, panel_x, panel_y):
        # panel_x and panel_y position the info panel on the right.
        line_spacing = 40
        
        # Render Score
        score_surf, _ = self.info_font.render("Score: " + str(self.board.score), (255,255,255))
        target_surface.blit(score_surf, (panel_x, panel_y))
        panel_y += line_spacing
        
        # Render Time
        time_surf, _ = self.info_font.render("Time: " + f"{self.total_time:.1f}s", (255,255,255))
        target_surface.blit(time_surf, (panel_x, panel_y))
        panel_y += line_spacing
        
        # Render Block Speed as a discrete level from 1 to 10.
        speed_range = BASE_FALL_DELAY - FALL_DELAY_MIN
        if speed_range != 0:
            level = round(((BASE_FALL_DELAY - self.board.current_fall_delay) / speed_range) * 9) + 1
        else:
            level = 10
        level = max(1, min(level, 10))
        speed_text = f"Block Speed: {level} | 10"
        speed_surf, _ = self.info_font.render(speed_text, (255,255,255))
        target_surface.blit(speed_surf, (panel_x, panel_y))
        panel_y += line_spacing
        
        # Render Game Over Countdown (only if active)
        if self.board.top_row_timer > 0:
            countdown = max(0, 3 - self.board.top_row_timer)
            go_surf, _ = self.info_font.render("Game Over in: " + f"{countdown:.1f}s", (255,0,0))
            target_surface.blit(go_surf, (panel_x, panel_y))

    def draw_controls_panel(self, target_surface, panel_x, panel_y):
        # Draw control instructions using the same info font.
        line_spacing = 40
        controls = [
            "Controls:",
            "Arrow Keys / WASD: Move",
            "Enter/Space: Swap Blocks",
            "Left Shift: Fast Rise",
            "Esc: Quit"
        ]
        for line in controls:
            text_surf, _ = self.info_font.render(line, (255,255,255))
            target_surface.blit(text_surf, (panel_x, panel_y))
            panel_y += line_spacing

    def draw_background(self, target_surface):
        """
        Draws a retro-style background with diagonally scrolling lines.
        """
        # Fill the background with a dark base color.
        target_surface.fill((10, 10, 10))
        spacing = 50
        pattern_color = (40, 40, 40)
        # Draw diagonal lines that start from the left and top edges.
        width, height = self.native_size
        # We loop over a range wider than the screen dimensions.
        for i in range(-height, width, spacing):
            start_x = i + int(self.background_offset)
            start_pos = (start_x, 0)
            end_pos = (start_x + height, height)
            pygame.draw.line(target_surface, pattern_color, start_pos, end_pos, 2)

def pitch_shift_sound(sound_array, pitch_factor):
    """
    Resamples the sound_array (a NumPy array) to achieve a pitched-up sound.
    pitch_factor > 1 increases the pitch (and shortens the sound).
    """
    orig_length = sound_array.shape[0]
    new_length = int(orig_length / pitch_factor)
    new_indices = np.linspace(0, orig_length - 1, new_length)
    if sound_array.ndim == 1:
         # Mono sound
         new_sound = np.interp(new_indices, np.arange(orig_length), sound_array).astype(sound_array.dtype)
    else:
         # Stereo or multichannel: process each channel
         new_sound = np.zeros((new_length, sound_array.shape[1]), dtype=sound_array.dtype)
         for channel in range(sound_array.shape[1]):
             new_sound[:, channel] = np.interp(new_indices, np.arange(orig_length), sound_array[:, channel]).astype(sound_array.dtype)
    return new_sound

# --------------------
# Main Loop
# --------------------

async def main():
    # Encapsulate initialization and the game loop in main() for pygbag.
    game = Game()
    await game.run()

asyncio.run(main())  # NEW: run the asynchronous main loop