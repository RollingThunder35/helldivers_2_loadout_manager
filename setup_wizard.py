import os
import tkinter as tk
from tkinter import messagebox

from utils import ROICalibrator, ConfigManager


class SetupWizard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SEAF CALIBRATION PROTOCOL")
        self.root.geometry("500x600")
        self.root.configure(bg="#1a1a1a")
        self.config = ConfigManager()

        # --- HEADER ---
        tk.Label(self.root, text="SYSTEM CALIBRATION", font=("Courier", 18, "bold"),
                 bg="#1a1a1a", fg="#ffe81f").pack(pady=20)

        description = ("Select a module to recalibrate. Settings are saved\n"
                       "automatically to settings.json after each step.")
        tk.Label(self.root, text=description, font=("Courier", 10),
                 bg="#1a1a1a", fg="white", justify="center").pack(pady=10)

        # Buttons for specific categories
        self.add_nav_button("CALIBRATE ROIs", self.run_roi_wizard)
        self.add_nav_button("BIND CONTROLS", self.run_key_wizard)
        self.add_nav_button("EXIT & SAVE", self.root.quit)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        # Optional: Ask for confirmation if they are mid-setup
        print("Cleaning up setup resources...")
        self.root.destroy()
        os._exit(0)  # Ensures the wizard process kills all its sub-tasks

    def add_nav_button(self, text, command):
        tk.Button(self.root, text=text, font=("Courier", 10, "bold"),
                  bg="#2c3e50", fg="#2ecc71", width=25, command=command).pack(pady=5)

    def run_roi_wizard(self):
        # Grouped sequence to minimize menu navigation
        roi_groups = [
            {
                "menu": "STRATAGEMS MENU",
                "instructions": "On the mission's LOADOUT tab, press select to open the stratagem list. You should see "
                                "the stratagem icons on the left and the name if the selected one in the center.",
                "targets": {
                    "STRAT_CAT_ROI": "Draw box over a Stratagem Category (e.g. OFFENSIVE) that is above all the stratagem logos.",
                    "STRAT_ITEM_ROI": "Draw box over a stratagem's name (e.g. ORBITAL PRECISION STRIKE). "
                                      "Include only the name, not description."
                }
            },
            {
                "menu": "BOOSTER MENU",
                "instructions": "Back out of the current selection menu and open the booster selection list.",
                "targets": {
                    "BOOSTER_ITEM_ROI": "Draw box over a booster's name (e.g. VITALITY ENHANCEMENT). "
                                        "Include only the name, not description."
                }
            },
            {
                "menu": "ARMORY: PRIMARY WEAPONS",
                "instructions": "Back out of the current selection menu, switch to the EQUIPMENT view, and select "
                                "the primary weapon picture.",
                "targets": {
                    "PRIMARY_CAT_ROI": "Draw box over a primary category (eg. ASSAULT RIFLE). "
                                       "This is at the top of the menu above their icons.",
                    "PRIMARY_ITEM_ROI": "Draw box over a primary's name (e.g. AR-23 LIBERATOR). "
                                        "Include only the name, not description."
                }
            },
            {
                "menu": "ARMORY: SECONDARY WEAPONS",
                "instructions": "Back out of the current selection menu and select "
                                "the secondary weapon picture.",
                "targets": {
                    "SECONDARY_CAT_ROI": "Draw box over a secondary weapon's category (e.g. PISTOL). "
                                         "This is at the top of the menu above their icons.",
                    "SECONDARY_ITEM_ROI": "Draw box over a secondary weapon's name (e.g. P-2 PEACEMAKER). "
                                          "Include only the name, not description."
                }
            },
            {
                "menu": "ARMORY: GRENADES",
                "instructions": "Back out of the current selection menu and select "
                                "the grenade weapon picture.",
                "targets": {
                    "GRENADE_CAT_ROI": "Draw box over the grenade's category (e.g. STANDARD THROWABLE). "
                                       "This is at the top of the menu above their icons.",
                    "GRENADE_ITEM_ROI": "Draw box over the grenade's name (e.g. TED-63 DYNAMITE). "
                                        "Include only the name, not description."
                }
            },
            {
                "menu": "ARMORY: HELMETS",
                "instructions": "Back out of the current selection menu and select the helmet picture. Before beginning, "
                                "turn your helldiver so their shoulder is facing the text. This reduces the armor shine "
                                "and gives you the best OCR reading.",
                "targets": {
                    "HELMET_ITEM_ROI": "Draw box over a helmet's name (e.g. CW-4 ARCTIC RANGER). "
                                      "Include only the name, not description."
                }
            },
            {
                "menu": "ARMORY: ARMOR",
                "instructions": "Back out of the current selection menu and select the Chest Armor picture.",
                "targets": {
                    "ARMOR_CAT_ROI": "Draw box over a armor category above the armor icons (e.g. LIGHT).",
                    "ARMOR_ITEM_ROI": "Draw box over a armor's name (e.g. FS-37 RAVAGER). Keep in mind that some "
                                      "armor names are longer and your selected area should be able to "
                                      "accommodate the longest one. Select only the name, not description.",
                    "ARMOR_PERK_ROI": "Draw box over a armor passive in the bottom corner (e.g. EXTRA PADDING). "
                                       "Do not include the icon in this area. Include only the name, not description."
                }
            },
            {
                "menu": "ARMORY: CAPE",
                "instructions": "Back out of the current selection menu and select the cape picture.",
                "targets": {
                    "CAPE_ITEM_ROI": "Draw box over a cape's name (e.g. TYRANT HUNTER). "
                                     "Make it long enough for the longest names. Select only the name, not description."
                }
            },
            {
                "menu": "READY UP",
                "instructions": "Back out of all the menus so that you see your helldiver on the mission loadout screen.",
                "targets":{
                    "READY_ROI": "Select the READY UP text below your helldiver and equipment. Do not include any symbols "
                                 "or key icons within this area."
                }
            }
        ]

        # Check the initial confirmation
        start = messagebox.askokcancel("Beginning ROI Calibration",
                                       "We will begin calibrating the regions the manager will look at. "
                                       "Please move the window out of the way of the Helldivers 2 menus. "
                                       "Please set your matchmaking to Invite Only, select any mission, "
                                       "and enter the hellpod. Select the drop zone (it doesn't matter where since you "
                                       "dont actually have to drop) so that the loadout comes up.\n\n"
                                       "NOTE: The regions you draw need to accommodate the largest names that could appear. "
                                       "It may help to select the item with the longest name in each category before pressing OK.")
        if not start:
            return

        for group in roi_groups:
            # Alert the user to switch menus - use askokcancel to allow bailing out
            continue_wizard = messagebox.askokcancel(group["menu"],
                                                     f"{group['instructions']}\n\nClick OK to continue or Cancel to stop.")
            if not continue_wizard:
                return

            for key, prompt in group["targets"].items():
                # Trigger the overlay for drawing
                calibrator = ROICalibrator(self.root, prompt)
                self.root.wait_window(calibrator.root)

                if calibrator.roi:
                    # Save specifically to the 'rois' section of settings.json
                    self.config.save_config({"rois": {key: calibrator.roi}})
                else:
                    # User closed the drawing overlay without selecting an area
                    choice = messagebox.askyesnocancel("Skipped",
                                                       f"No area selected for {key}.\n\n"
                                                       "Yes: Skip this item\n"
                                                       "No: Retry this item\n"
                                                       "Cancel: Exit Wizard Entirely")

                    if choice is None:  # User pressed Cancel
                        return
                    elif not choice:  # User pressed No (Retry)
                        # This is a bit of recursion to retry the specific item
                        self.execute_single_calibration(key, prompt)
                        # If True (Yes), the loop simply continues to the next item

        messagebox.showinfo("Protocol Complete", "All ROIs calibrated and saved to settings.json.")

    def execute_single_calibration(self, key, prompt):
        """Helper to allow retrying a specific ROI without restarting the group."""
        calibrator = ROICalibrator(self.root, prompt)
        self.root.wait_window(calibrator.root)
        if calibrator.roi:
            self.config.save_config({"rois": {key: calibrator.roi}})

    def run_key_wizard(self):
        key_targets = {"UP" : "W",
                       "DOWN": "S",
                       "LEFT": "A",
                       "RIGHT": "D",
                       "MENU TAB LEFT": "Z",
                       "MENU TAB RIGHT": "C",
                       "SWITCH": "R",
                       "ENTER MENU": "SPACE",
                       "LEAVE MENU": "ESC"}

        # Initial confirmation
        if not messagebox.askokcancel("Key Binding",
                                      "We will now bind your movement and menu keys. \n\nClick OK to begin."):
            return

        for action, default in key_targets.items():
            bind_win = tk.Toplevel(self.root)
            bind_win.title("BINDING")
            bind_win.geometry("500x500")  # Slightly larger for the button
            bind_win.configure(bg="#1a1a1a")
            bind_win.grab_set()  # Prevents interaction with main window

            tk.Label(bind_win, text=f"SET KEY FOR: {action} (DEFAULT: {default})",
                     fg="#ffe81f", bg="#1a1a1a", font=("Courier", 14, "bold")).pack(pady=20)

            tk.Label(bind_win, text="Press any key on your keyboard...",
                     fg="white", bg="#1a1a1a", font=("Courier", 10)).pack(pady=10)

            # State tracking
            status = {"captured": None, "cancelled": False}

            def on_keypress(event):
                # Map standard Tkinter keysyms to PyAutoGUI expected strings
                status["captured"] = event.keysym.lower()
                bind_win.destroy()

            def on_cancel():
                status["cancelled"] = True
                bind_win.destroy()

            # Bindings
            bind_win.bind("<Key>", on_keypress)
            bind_win.protocol("WM_DELETE_WINDOW", on_cancel)  # Handles the X button

            # Add a manual Cancel button
            tk.Button(bind_win, text="CANCEL WIZARD", bg="#c0392b", fg="white",
                      font=("Courier", 10, "bold"), command=on_cancel).pack(pady=20)

            bind_win.focus_force()
            self.root.wait_window(bind_win)

            # Check if the user bailed
            if status["cancelled"]:
                if messagebox.askyesno("Exit", "Stop binding keys? (Progress so far is saved)"):
                    return
                else:
                    # If they say No, we restart the current key bind
                    self.run_single_key_bind(action)
                    continue

            if status["captured"]:
                self.config.save_config({"controls": {action: status["captured"]}})

        messagebox.showinfo("Success", "All keys mapped successfully.")

    def run_single_key_bind(self, action):
        """
        Creates a modal popup to capture a single keypress for a specific action.
        Returns the keysym string if captured, or None if canceled.
        """
        bind_win = tk.Toplevel(self.root)
        bind_win.title("INPUT CAPTURE")
        bind_win.geometry("500x500")
        bind_win.configure(bg="#1a1a1a")
        bind_win.grab_set()

        # UI setup
        tk.Label(bind_win, text=f"SET KEY FOR: {action}",
                 fg="#ffe81f", bg="#1a1a1a", font=("Courier", 14, "bold")).pack(pady=20)

        instruction_lbl = tk.Label(bind_win, text="Press the key you wish to use...",
                                   fg="white", bg="#1a1a1a", font=("Courier", 10))
        instruction_lbl.pack(pady=10)

        # Use a list to store the result so it's accessible after the window closes
        result = {"key": None, "cancelled": False}

        def on_keypress(event):
            # We capture the keysym (e.g., 'w', 'Up', 'space')
            result["key"] = event.keysym
            bind_win.destroy()

        def on_cancel():
            result["cancelled"] = True
            bind_win.destroy()

        # Binds
        bind_win.bind("<Key>", on_keypress)
        bind_win.protocol("WM_DELETE_WINDOW", on_cancel)

        tk.Button(bind_win, text="CANCEL", bg="#c0392b", fg="white",
                  font=("Courier", 10, "bold"), width=15, command=on_cancel).pack(pady=20)

        bind_win.focus_force()
        self.root.wait_window(bind_win)

        if result["cancelled"]:
            return None
        return result["key"]

# --- STANDALONE STARTUP ---
if __name__ == "__main__":
    # Initialize the Wizard
    app = SetupWizard()

    # Optional: Check if game is running and warn the user
    # (Using a simple check ensures they don't calibrate against their desktop)
    messagebox.showinfo("PRE-FLIGHT CHECK",
                        "Please ensure Helldivers 2 is running in BORDERLESS WINDOWED mode "
                        "before starting calibration.")

    app.root.mainloop()