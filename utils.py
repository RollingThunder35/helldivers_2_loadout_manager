import json
import os
from tkinter import messagebox

import pygetwindow as gw
import tkinter as tk
from environment_setup import get_base_path

# Global Category Definitions
STRAT_CATS = ["OFFENSIVE", "SUPPLY", "DEFENSIVE"]
PRIMARY_CATS = ["ASSAULT RIFLE", "MARKSMAN RIFLE", "SUBMACHINE GUN", "SHOTGUN", "EXPLOSIVE", "ENERGY-BASED", "SPECIAL"]
SECONDARY_CATS = ["PISTOL", "MELEE", "SPECIAL"]
GRENADE_CATS = ["STANDARD THROWABLE", "SPECIAL THROWABLE"]
ARMOR_CATS = ["LIGHT", "MEDIUM", "HEAVY"]

# Error exception classes
class ConfigurationError(Exception):
    """Exception raised for missing or invalid ROI coordinates."""
    def __init__(self, message):
        self.message = message
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Configuration Error", self.message)
        super().__init__(self.message)

    pass

def focus_hd2_win():
    print("Switching to Helldivers 2...")

    # Search for any window containing "Google Chrome"
    matches = gw.getWindowsWithTitle('HELLDIVERS™ 2')

    if matches:
        win = matches[0]  # Get the first match
        if win.isMinimized:
            win.restore()  # Restore if it's tucked away in the taskbar
        win.activate()
    else:
        print("No matching window found.")


def validate_loadout_files(loadout_folder):
    """Checks for missing keys or items not present in databases."""

    for filename in os.listdir(loadout_folder):
        if not filename.endswith(".json"): continue

        with open(os.path.join(loadout_folder, filename), 'r') as f:
            data = json.load(f)

        print(f"--- Validating: {filename} ---")

        result, errors = validate_loadout_data(data)

        if not result:
            print(f"--- Errors: {errors} ---")

    print("Validation Complete.")

def validate_loadout_data(data):
    """
    Checks a dictionary of loadout data for integrity.
    Returns (is_valid, error_message)
    """
    required_keys = ["name", "factions", "primary", "secondary", "grenade", "armor",
                     "helmet", "cape", "boosters"]
    errors = []

    # 1. Check for missing keys
    for key in required_keys:
        if key not in data or not data[key]:
            errors.append(f"Missing selection for: {key.upper()}")

    # 2. Check booster format
    if "boosters" in data:
        if not isinstance(data["boosters"], list) or len(data["boosters"]) == 0:
            errors.append("Boosters must be a list with at least 1 item.")

    # 3. Check stratagems (if you've added them to your requirements)
    for i in range(1, 5):
        s_key = f"stratagem_{i}"
        if s_key not in data or not data[s_key]:
            errors.append(f"Missing Stratagem {i}")

    if errors:
        return False, "\n".join(errors)
    return True, "Success"

class ROICalibrator:
    def __init__(self, root, label_text):
        self.root = tk.Toplevel(root)
        self.root.attributes("-alpha", 0.3)  # Transparent overlay
        self.root.attributes("-fullscreen", True)
        self.root.config(cursor="cross")

        self.label = tk.Label(self.root, text=label_text, font=("Courier", 20, "bold"), fg="red", bg="white")
        self.label.pack(pady=50)

        self.start_x = None
        self.start_y = None
        self.rect = None
        self.roi = None
        self.start_y_canvas = None
        self.start_x_canvas = None
        self.start_y_screen = None
        self.start_x_screen = None

        self.canvas = tk.Canvas(self.root, cursor="cross", bg="grey", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

    def on_button_press(self, event):
        # 1. Capture Screen coords for the final DATA
        self.start_x_screen = event.x_root
        self.start_y_screen = event.y_root

        # 2. Capture Canvas coords for the VISUAL rectangle
        self.start_x_canvas = self.canvas.canvasx(event.x)
        self.start_y_canvas = self.canvas.canvasy(event.y)

        # Create the visual rectangle starting at the canvas position
        self.rect = self.canvas.create_rectangle(
            self.start_x_canvas, self.start_y_canvas,
            self.start_x_canvas, self.start_y_canvas,
            outline='red', width=2
        )

    def on_mouse_drag(self, event):
        # Update the visual box using canvas-relative coordinates
        cur_x_canvas = self.canvas.canvasx(event.x)
        cur_y_canvas = self.canvas.canvasy(event.y)

        self.canvas.coords(self.rect, self.start_x_canvas, self.start_y_canvas, cur_x_canvas, cur_y_canvas)

    def on_button_release(self, event):
        # Use the screen-absolute coordinates for the final ROI
        end_x_screen = event.x_root
        end_y_screen = event.y_root

        x = min(self.start_x_screen, end_x_screen)
        y = min(self.start_y_screen, end_y_screen)
        w = abs(self.start_x_screen - end_x_screen)
        h = abs(self.start_y_screen - end_y_screen)

        self.roi = (x, y, w, h)
        self.root.destroy()

class ConfigManager:
    def __init__(self):
        self.basepath = get_base_path()
        self.filepath = os.path.join(self.basepath, "settings.json")
        self.data = self.load_config()

    def load_config(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                return json.load(f)
        return {"controls": {}, "rois": {}}

    def save_config(self, new_data):
        # Update existing data with new values
        if "controls" in new_data:
            self.data["controls"].update(new_data["controls"])
        if "rois" in new_data:
            self.data["rois"].update(new_data["rois"])

        with open(self.filepath, 'w') as f:
            json.dump(self.data, f, indent=4)

    def get_roi(self, key, default):
        # Returns the saved ROI or the hardcoded default if not found
        return tuple(self.data["rois"].get(key, default))

    def get_control(self, key, default=None):
        return str(self.data["controls"].get(key, default))