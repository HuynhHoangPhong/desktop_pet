import tkinter as tk
from tkinter import Menu
import pathlib
from pathlib import Path
import sys
import os
import random
import re
import queue
import math
from PIL import Image, ImageTk
import winsound

try:
    from pynput import mouse
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

# --- Configuration ---
SPRITE_FACES_RIGHT_BY_DEFAULT = False
PET_SIZE = 240
HOUSE_SIZE = 220
WALK_SPEED = 2.0
RUN_SPEED = 6.0
DRAG_THRESHOLD = 5
RANDOM_JUMP_MIN_MS = 6000
RANDOM_JUMP_MAX_MS = 15000
DOUBLE_CLICK_ATTACK_CHANCE = 0.6
TARGET_REACHED_DISTANCE = 10
# ---------------------

def get_emotion_dir():
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).resolve().parent
    return base_path / "emotion"

def extract_number(path):
    match = re.search(r'\d+', path.name)
    return int(match.group(0)) if match else 0

class DesktopPet:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        
        self.transparent_color = "black"
        self.root.config(bg=self.transparent_color)
        self.root.wm_attributes("-transparentcolor", self.transparent_color)
        
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        self.pet_width = PET_SIZE
        self.pet_height = PET_SIZE
        
        self.house_x = self.screen_width - HOUSE_SIZE - 20
        self.house_y = self.screen_height - HOUSE_SIZE - 40
        self.is_house_dragging = False
        self.house_click_timer = None
        self.is_house_double_clicking = False
        
        self.house_win = tk.Toplevel(self.root)
        self.house_win.overrideredirect(True)
        self.house_win.wm_attributes("-topmost", True)
        self.house_win.config(bg=self.transparent_color)
        self.house_win.wm_attributes("-transparentcolor", self.transparent_color)
        self.house_win.geometry(f"{HOUSE_SIZE}x{HOUSE_SIZE}+{int(self.house_x)}+{int(self.house_y)}")
        
        self.house_label = tk.Label(self.house_win, bg=self.transparent_color, bd=0, highlightthickness=0)
        self.house_label.pack(side="bottom")
        
        # State: Pet starts hidden internally
        self.cat_inside_house = True
        
        # Starting boundaries tightly coupled to newly generated house location 
        self.x = self.house_x + (HOUSE_SIZE // 2) - (self.pet_width // 2)
        self.y = self.house_y + HOUSE_SIZE - self.pet_height
        self.root.geometry(f"{self.pet_width}x{self.pet_height}+{int(self.x)}+{int(self.y)}")
        
        # Since it starts out trapped, formally hide the Tk root process
        self.root.withdraw()
        
        self.animations = {}
        self.current_action = "idle"
        self.frame_index = 0
        self.facing_right = True
        
        self.animation_speed = 100
        self.paused = False
        self.is_dragging = False
        
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_win_start_x = 0
        self.drag_win_start_y = 0
        
        self.is_double_clicking = False
        self.click_timer = None
        self.random_jump_timer = None
        self.run_timer = None
        
        self.target_position = None
        self.click_queue = queue.Queue()
        
        self.label = tk.Label(self.root, bg=self.transparent_color, bd=0, highlightthickness=0)
        self.label.pack(side="bottom")
        
        self.load_house()
        self.load_animations()
        
        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<Double-Button-1>", self.on_double_click)
        self.label.bind("<Button-3>", self.show_menu)
        
        self.house_label.bind("<ButtonPress-1>", self.on_house_press)
        self.house_label.bind("<B1-Motion>", self.on_house_drag)
        self.house_label.bind("<ButtonRelease-1>", self.on_house_release)
        self.house_label.bind("<Double-Button-1>", self.on_house_double_click)
        
        self.root.bind("<Escape>", lambda e: self.exit_app())
        
        self.menu = Menu(self.root, tearoff=0)
        self.menu.add_command(label="Pause / Resume", command=self.toggle_pause)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.exit_app)
        
        self.is_playing_once = False
        self.set_action("idle")  
        
        if HAS_PYNPUT:
            self.mouse_listener = mouse.Listener(on_click=self.on_global_click)
            self.mouse_listener.daemon = True
            self.mouse_listener.start()
        
        self.schedule_random_jump()
        self.update_frame()
        self.update_movement()
        self.process_global_clicks()

    def load_house(self):
        house_path = get_emotion_dir() / "house.png"
        if house_path.exists():
            try:
                img = Image.open(house_path).convert("RGBA")
                w, h = img.size
                scale = min(HOUSE_SIZE / w, HOUSE_SIZE / h)
                new_w, new_h = int(w * scale), int(h * scale)
                if new_w > 0 and new_h > 0:
                    img = img.resize((new_w, new_h), Image.NEAREST)
                canvas = Image.new("RGBA", (HOUSE_SIZE, HOUSE_SIZE), (0, 0, 0, 0))
                canvas.paste(img, ((HOUSE_SIZE - new_w) // 2, HOUSE_SIZE - new_h))
                self.house_photo = ImageTk.PhotoImage(canvas)
                self.house_label.config(image=self.house_photo)
            except Exception as e:
                print(f"Warning: house.png processing error: {e}")
                
        else:
            print("Warning: house.png not found. House drag operations may fail if UI is empty.")

    def load_animations(self):
        emotion_dir = get_emotion_dir()
        
        actions = ["attack", "hurt", "idle", "jump", "run", "runningjump", "walk"]
        folder_map = {
            "attack": ["attack", "actack"],
            "runningjump": ["runningjump", "runningjum"]
        }
        
        global_max_w = 0
        global_max_h = 0
        valid_files = []
        
        for action in actions:
            action_dir = None
            possible_names = folder_map.get(action, [action])
            
            for name in possible_names:
                path = emotion_dir / name
                if path.exists() and path.is_dir():
                    action_dir = path
                    break
                    
            if action_dir:
                files = sorted([f for f in action_dir.glob("*.png")], key=extract_number)
                for f in files:
                    try:
                        with Image.open(f) as img:
                            w, h = img.size
                            if w > global_max_w: global_max_w = w
                            if h > global_max_h: global_max_h = h
                        valid_files.append((action, f))
                    except Exception:
                        pass
                        
        if not valid_files:
            error_msg = "No animation frames found. Please check emotion folder path and subfolder names."
            print(error_msg)
            
        global_scale = 1.0
        if global_max_w > 0 and global_max_h > 0:
            global_scale = min(PET_SIZE / global_max_w, PET_SIZE / global_max_h)
            
        for action in actions:
            self.animations[action] = {'R': [], 'L': []}
            
        for action, f in valid_files:
            try:
                img = Image.open(f).convert("RGBA")
                w, h = img.size
                
                new_w = int(w * global_scale)
                new_h = int(h * global_scale)
                
                if new_w > 0 and new_h > 0:
                    img = img.resize((new_w, new_h), Image.NEAREST)
                    
                canvas = Image.new("RGBA", (PET_SIZE, PET_SIZE), (0, 0, 0, 0))
                
                paste_x = (PET_SIZE - new_w) // 2
                paste_y = PET_SIZE - new_h
                canvas.paste(img, (paste_x, paste_y))
                
                if SPRITE_FACES_RIGHT_BY_DEFAULT:
                    img_r = canvas
                    img_l = canvas.transpose(Image.FLIP_LEFT_RIGHT)
                else:
                    img_l = canvas
                    img_r = canvas.transpose(Image.FLIP_LEFT_RIGHT)
                    
                img_tk_r = ImageTk.PhotoImage(img_r)
                img_tk_l = ImageTk.PhotoImage(img_l)
                
                self.animations[action]['R'].append(img_tk_r)
                self.animations[action]['L'].append(img_tk_l)
            except Exception:
                pass

    def play_sound(self):
        sound_path = get_emotion_dir() / "sound_meo1.wav"
        if sound_path.exists():
            try:
                winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception as e:
                print(f"Warning: Audio error: {e}")
        else:
            print("Warning: sound_meo1.wav was not found in emotion folder.")

    def on_global_click(self, x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            self.click_queue.put((x, y))

    def process_global_clicks(self):
        while not self.click_queue.empty():
            x, y = self.click_queue.get()
            
            # Ensure pet is exposed and operational to process commands 
            if not self.cat_inside_house and not self.is_dragging and not self.paused and not self.is_playing_once:
                
                # Check for UI overlaps physically skipping commands sent specifically to interact with characters
                if (self.x - 10 <= x <= self.x + self.pet_width + 10) and (self.y - 10 <= y <= self.y + self.pet_height + 10):
                    continue
                if (self.house_x - 10 <= x <= self.house_x + HOUSE_SIZE + 10) and (self.house_y - 10 <= y <= self.house_y + HOUSE_SIZE + 10):
                    continue
                
                self.target_position = (x, y)
                self.set_action("run") 
                
        self.root.after(100, self.process_global_clicks)

    def schedule_random_jump(self):
        delay = random.randint(RANDOM_JUMP_MIN_MS, RANDOM_JUMP_MAX_MS)
        self.random_jump_timer = self.root.after(delay, self.do_random_jump)

    def do_random_jump(self):
        if not self.cat_inside_house and not self.is_dragging and not self.paused and not self.is_playing_once:
            if self.current_action in ["walk", "idle"] and not self.target_position:
                action = random.choice(["jump", "run", "runningjump"])
                
                if action == "run":
                    if "run" in self.animations and len(self.animations["run"]['R']) > 0:
                        self.start_run_behavior()
                    else:
                        self.set_action("walk")
                elif action == "runningjump":
                    if "runningjump" in self.animations and len(self.animations["runningjump"]['R']) > 0:
                        self.play_once("runningjump")
                    else:
                        self.play_once("jump") 
                elif action == "jump":
                    self.play_once("jump")
                    
        self.schedule_random_jump()

    def start_run_behavior(self):
        self.set_action("run")
        duration = random.randint(2000, 5000)
        if self.run_timer:
            self.root.after_cancel(self.run_timer)
        self.run_timer = self.root.after(duration, self.stop_run_behavior)

    def stop_run_behavior(self):
        if self.current_action == "run" and not self.is_dragging and not self.paused:
            self.set_action("walk")

    def set_action(self, action):
        if action in self.animations and len(self.animations[action]['R']) > 0:
            if self.current_action != action:
                self.current_action = action
                self.frame_index = 0
        else:
            if action == "run":
                self.set_action("walk")
            elif action == "walk":
                self.set_action("idle")
            else:
                self.current_action = "idle"
                self.frame_index = 0

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.set_action("idle")
        else:
            self.set_action("walk")
            
    def increase_speed(self):
        global WALK_SPEED, RUN_SPEED
        WALK_SPEED = min(15.0, WALK_SPEED + 1.0)
        RUN_SPEED = min(20.0, RUN_SPEED + 1.0)

    def decrease_speed(self):
        global WALK_SPEED, RUN_SPEED
        WALK_SPEED = max(1.0, WALK_SPEED - 1.0)
        RUN_SPEED = max(2.0, RUN_SPEED - 1.0)

    def play_once(self, action):
        if self.is_dragging:
            return
            
        if action in self.animations and len(self.animations[action]['R']) > 0:
            self.is_playing_once = True
            self.current_action = action
            self.frame_index = 0

    def get_current_frames(self):
        direction = 'R' if self.facing_right else 'L'
        if self.current_action in self.animations and len(self.animations[self.current_action][direction]) > 0:
            return self.animations[self.current_action][direction]
        if "idle" in self.animations and len(self.animations["idle"][direction]) > 0:
            return self.animations["idle"][direction]
        return []

    def update_frame(self):
        frames = self.get_current_frames()
        if frames:
            self.frame_index = self.frame_index % len(frames)
            self.label.config(image=frames[self.frame_index])
            self.frame_index += 1
            
            if self.is_playing_once and self.frame_index >= len(frames):
                self.is_playing_once = False
                self.set_action("idle" if self.cat_inside_house else "walk")
                self.frame_index = 0
                
        self.root.after(self.animation_speed, self.update_frame)

    def update_movement(self):
        if not self.cat_inside_house and not self.is_dragging and not self.paused:
            
            if self.target_position and not self.is_playing_once:
                tx, ty = self.target_position
                dx = tx - (self.x + self.pet_width / 2)
                dy = ty - (self.y + self.pet_height) 
                
                dist = math.hypot(dx, dy)
                
                if dist < TARGET_REACHED_DISTANCE:
                    self.target_position = None
                    self.set_action("walk")
                else:
                    if self.current_action not in ["run", "walk"]:
                        self.set_action("run")
                        
                    current_speed = RUN_SPEED if self.current_action == "run" else WALK_SPEED
                    
                    vx = (dx / dist) * current_speed
                    vy = (dy / dist) * current_speed
                    
                    self.facing_right = vx > 0
                        
                    self.x += vx
                    self.y += vy
                    
                    self.root.geometry(f"{self.pet_width}x{self.pet_height}+{int(self.x)}+{int(self.y)}")
                    
            elif self.current_action in ["walk", "run", "runningjump"]:
                current_speed = RUN_SPEED if self.current_action in ["run", "runningjump"] else WALK_SPEED
                
                if self.facing_right:
                    self.x += current_speed
                    if self.x + self.pet_width >= self.screen_width:
                        self.facing_right = False
                else:
                    self.x -= current_speed
                    if self.x <= 0:
                        self.facing_right = True
                
                self.root.geometry(f"{self.pet_width}x{self.pet_height}+{int(self.x)}+{int(self.y)}")
        
        self.root.after(50, self.update_movement)

    # ------------------
    # CAT DRAG CONTROLS
    # ------------------
    def on_press(self, event):
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.drag_win_start_x = self.x
        self.drag_win_start_y = self.y
        self.is_dragging = False

    def on_drag(self, event):
        dx = event.x_root - self.drag_start_x
        dy = event.y_root - self.drag_start_y
        
        if not self.is_dragging and (abs(dx) > DRAG_THRESHOLD or abs(dy) > DRAG_THRESHOLD):
            self.is_dragging = True
            self.set_action("idle")
            self.is_playing_once = False
            self.target_position = None
            
        if self.is_dragging:
            if self.current_action != "idle":
                self.set_action("idle")
            
            self.x = self.drag_win_start_x + dx
            self.y = self.drag_win_start_y + dy
            
            self.x = max(0, min(self.screen_width - self.pet_width, self.x))
            self.y = max(0, min(self.screen_height - self.pet_height, self.y))
            
            self.root.geometry(f"{self.pet_width}x{self.pet_height}+{int(self.x)}+{int(self.y)}")

    def on_release(self, event):
        if self.is_dragging:
            self.is_dragging = False
            
            # Intersection bounds dropping math 
            cat_rect = (self.x, self.y, self.x + self.pet_width, self.y + self.pet_height)
            house_rect = (self.house_x, self.house_y, self.house_x + HOUSE_SIZE, self.house_y + HOUSE_SIZE)
            
            overlap = not (cat_rect[2] < house_rect[0] or cat_rect[0] > house_rect[2] or 
                           cat_rect[3] < house_rect[1] or cat_rect[1] > house_rect[3])
            
            if overlap:
                self.cat_inside_house = True
                self.target_position = None
                self.set_action("idle")
                self.root.withdraw() # Safely masks standard GUI layers
            else:
                self.cat_inside_house = False
                if not self.paused:
                    self.set_action("walk")
        else:
            if getattr(self, 'is_double_clicking', False):
                self.is_double_clicking = False
                return
            self.click_timer = self.root.after(200, self.do_single_click)

    def do_single_click(self):
        self.click_timer = None
        self.play_sound()

        if "hurt" in self.animations and len(self.animations["hurt"]["R"]) > 0:
            self.play_once("hurt")
        else:
            self.set_action("walk" if not self.cat_inside_house else "idle")

    def on_double_click(self, event):
        self.is_double_clicking = True
        if self.click_timer:
            self.root.after_cancel(self.click_timer)
            self.click_timer = None
            
        if random.random() < DOUBLE_CLICK_ATTACK_CHANCE:
            if "attack" in self.animations and len(self.animations["attack"]['R']) > 0:
                self.play_once("attack")

    # --------------------
    # HOUSE DRAG CONTROLS
    # --------------------
    def on_house_press(self, event):
        self.house_drag_start_x = event.x_root
        self.house_drag_start_y = event.y_root
        self.house_win_start_x = self.house_x
        self.house_win_start_y = self.house_y
        self.is_house_dragging = False

    def on_house_drag(self, event):
        dx = event.x_root - self.house_drag_start_x
        dy = event.y_root - self.house_drag_start_y
        
        if not self.is_house_dragging and (abs(dx) > DRAG_THRESHOLD or abs(dy) > DRAG_THRESHOLD):
            self.is_house_dragging = True
            
        if self.is_house_dragging:
            self.house_x = self.house_win_start_x + dx
            self.house_y = self.house_win_start_y + dy
            self.house_win.geometry(f"{HOUSE_SIZE}x{HOUSE_SIZE}+{int(self.house_x)}+{int(self.house_y)}")
            
            # Secure pet dragging inside the house
            if self.cat_inside_house:
                self.x = self.house_x + (HOUSE_SIZE // 2) - (self.pet_width // 2)
                self.y = self.house_y + HOUSE_SIZE - self.pet_height
                self.root.geometry(f"{self.pet_width}x{self.pet_height}+{int(self.x)}+{int(self.y)}")

    def on_house_release(self, event):
        if self.is_house_dragging:
            self.is_house_dragging = False
        else:
            if getattr(self, "is_house_double_clicking", False):
                self.is_house_double_clicking = False
                return

            if self.house_click_timer:
                self.root.after_cancel(self.house_click_timer)

            self.house_click_timer = self.root.after(200, self.do_house_single_click)

    def do_house_single_click(self):
        self.house_click_timer = None

        if self.cat_inside_house:
            return

        if self.paused or self.is_dragging or self.is_playing_once:
            return

        target_x = self.house_x + HOUSE_SIZE / 2
        target_y = self.house_y + HOUSE_SIZE - 20

        self.target_position = (target_x, target_y)
        self.set_action("run")

    def on_house_double_click(self, event):
        self.is_house_double_clicking = True

        if self.house_click_timer:
            self.root.after_cancel(self.house_click_timer)
            self.house_click_timer = None

        if not self.cat_inside_house:
            return

        self.play_sound()

        self.cat_inside_house = False
        self.target_position = None

        self.root.deiconify()

        self.x = self.house_x + (HOUSE_SIZE // 2) - (self.pet_width // 2)
        self.y = self.house_y + HOUSE_SIZE - self.pet_height

        self.root.geometry(
            f"{self.pet_width}x{self.pet_height}+{int(self.x)}+{int(self.y)}"
        )

        self.set_action("walk")

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def exit_app(self):
        if self.random_jump_timer:
            try:
                self.root.after_cancel(self.random_jump_timer)
            except:
                pass
        if self.run_timer:
            try:
                self.root.after_cancel(self.run_timer)
            except:
                pass
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = DesktopPet(root)
    root.mainloop()
