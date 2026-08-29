import environment_setup
from utils import focus_hd2_win, validate_loadout_files, validate_loadout_data, ConfigurationError, ROIOverlay
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import time
from thefuzz import fuzz
from loadout_selection import wait_for_lobby, apply_loadout, LoadoutManager
from database_mapper import construct_gold_db
from loadout_creator import LoadoutCreator
import logging


# noinspection PyTypeChecker
class LoadoutGUI:
    root: tk.Tk
    manager: LoadoutManager
    overlay_tool: ROIOverlay

    def __init__(self):
        # --- Root Configuration ---
        self.root = tk.Tk()
        self.root.title("SEAF Loadout Manager")
        self.root.geometry("1200x900")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.configure(bg="#1a1a1a")
        self.root.option_add("*TCombobox*Listbox*Background", "#2c3e50")
        self.root.option_add("*TCombobox*Listbox*Foreground", "#2ecc71")
        self.root.option_add("*TCombobox*Listbox*Font", ("Courier", 10))
        self.root.option_add("*TCombobox*Listbox*selectBackground", "#2ecc71")
        self.root.option_add("*TCombobox*Listbox*selectForeground", "#2c3e50")

        self.overlay_tool = ROIOverlay(self.root)

        self.loadout_map = None
        self.current_loadout_data = None
        self.manager = LoadoutManager(self.overlay_tool)
        self.is_watching = False
        self.button_pressed = None

        validate_loadout_files(os.path.join(self.manager.config.basepath, "loadouts"))

        # --- GLOBAL STYLE REFINEMENT ---
        style = ttk.Style()
        style.theme_use('clam')

        # Define our dark colors
        DARK_GRAY_BG = "#1a1a1a"  # Very dark gray for inactive
        ACTIVE_BLUE_BG = "#2c3e50"  # The dark blue/gray you like for active fields
        TERMINAL_GREEN = "#2ecc71"

        style.configure("TCombobox",
                        background=ACTIVE_BLUE_BG,
                        foreground=TERMINAL_GREEN,
                        fieldbackground=ACTIVE_BLUE_BG,  # Default background
                        arrowcolor=TERMINAL_GREEN,
                        font=("Courier", 10, "bold"))

        # THIS IS THE FIX:
        # We "map" the background to change based on the widget state.
        style.map("TCombobox",
                  fieldbackground=[("readonly", DARK_GRAY_BG), ("focus", ACTIVE_BLUE_BG)],
                  foreground=[("readonly", TERMINAL_GREEN)],
                  font=[("readonly", ("Courier", 10, "bold"))])

        # --- Header ---
        tk.Label(self.root, text="HELLDIVER TACTICAL ARCHIVE", font=("Courier", 20, "bold"),
                 bg="#1a1a1a", fg="#ffe81f").pack(pady=15)

        # --- Main Layout Container ---
        self.main_container = tk.Frame(self.root, bg="#1a1a1a")
        self.main_container.pack(fill="both", expand=True, padx=20)

        # 1. LEFT COLUMN: Profile List
        self.left_frame = tk.Frame(self.main_container, bg="#1a1a1a")
        self.left_frame.pack(side="left", fill="both", expand=False)

        tk.Label(self.left_frame, text="MISSION PROFILES", bg="#1a1a1a", fg="white", font=("Courier", 10)).pack(
            anchor="w")

        # --- Faction Filter ---
        filter_frame = tk.Frame(self.left_frame, bg="#1a1a1a")
        filter_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(filter_frame, text="FILTER BY FACTION:", bg="#1a1a1a", fg="white", font=("Courier", 8)).pack(
            side="left")

        factions = self.get_unique_factions()
        self.faction_filter = ttk.Combobox(filter_frame, values=factions, state="readonly", font=("Courier", 10, "bold"))
        self.faction_filter.set("ALL")
        self.faction_filter.pack(side="right", fill="x", expand=True, padx=5)
        self.faction_filter.bind("<<ComboboxSelected>>", self.refresh_loadouts)

        self.list_container = tk.Frame(self.left_frame, bg="#1a1a1a")
        self.list_container.pack(fill="both", expand=True)

        self.scrollbar = tk.Scrollbar(self.list_container, orient="vertical")
        self.loadout_listbox = tk.Listbox(self.list_container, bg="#2b2b2b", fg="#ffe81f",
                                          selectbackground="#ffe81f", selectforeground="black",
                                          width=22, height=18, font=("Courier", 11),
                                          yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.loadout_listbox.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.loadout_listbox.pack(side="left", fill="both", expand=True)

        # --- LOADOUT CONTROLS ---
        self.refresh_btn = tk.Button(self.left_frame, text="↻ REFRESH ARCHIVE", command=self.refresh_loadouts,
                                     bg="#333333", fg="white", font=("Courier", 8), bd=0, pady=5)
        self.refresh_btn.pack(fill="x", pady=5)

        self.create_btn = tk.Button(
            self.left_frame,
            text="＋ CREATE NEW LOADOUT",
            command=self.open_loadout_creator,  # Link to the function
            bg="#333333",
            fg="white",
            font=("Courier", 8),
            bd=0,
            pady=5
        )
        self.create_btn.pack(fill="x", pady=5)

        self.edit_btn = tk.Button(
            self.left_frame,
            text="✎ EDIT SELECTED",
            bg="#333333",
            fg="white",
            font=("Courier", 8),
            command=self.open_edit_mode,  # Links to the method above
            bd=0,
            pady=5
        )
        self.edit_btn.pack(fill="x", pady=5)

        self.delete_btn = tk.Button(
            self.left_frame,
            text="🗑 DELETE SELECTED",
            bg="#333333",
            fg="#e74c3c",
            font=("Courier", 8),
            command=self.delete_loadout,
            bd=0,
            pady=5
        )
        self.delete_btn.pack(fill="x", pady=5)

        # 2. MIDDLE COLUMN: Manifest Preview
        self.mid_frame = tk.LabelFrame(self.main_container, text=" MANIFEST PREVIEW ",
                                       bg="#1a1a1a", fg="#ffe81f", font=("Courier", 10, "bold"))
        self.mid_frame.pack(side="left", fill="both", expand=True, padx=15)

        self.preview_text = tk.Label(self.mid_frame, text="Select a profile to analyze...",
                                     justify="left", anchor="nw", bg="#1a1a1a", fg="#00ff00",
                                     font=("Courier", 10), wraplength=0)
        self.preview_text.pack(padx=10, pady=10, fill="both", expand=True)

        # 3. RIGHT COLUMN: Maintenance Panel
        self.right_frame = tk.LabelFrame(self.main_container, text=" DB MAINTENANCE ",
                                         bg="#1a1a1a", fg="#ffe81f", font=("Courier", 10, "bold"))
        self.right_frame.pack(side="right", fill="both", expand=False)

        self.db_configs = {
            "primary": "primary_db.json",
            "secondary": "secondary_db.json",
            "armor": "armor_db.json",
            "helmet": "helmet_db.json",
            "cape": "cape_db.json",
            "grenade": "grenade_db.json",
            "stratagems": "stratagem_db.json",
            "booster": "booster_db.json"
        }

        self.map_buttons = {}
        self.create_mapping_buttons()
        self.create_gold_database_button()

        # --- Footer: Status and Control ---
        # Define the custom "Helldiver" style
        style.configure("Helldiver.Horizontal.TProgressbar",
                        troughcolor='#1a1a1a',  # The "empty" background (Dark Grey/Black)
                        background='#ffe81f',  # The "full" bar (Bright Yellow)
                        thickness=20,  # Height of the bar
                        bordercolor='#333333',  # Subtle border
                        lightcolor='#ffe81f',  # Removes the default "shiny" 3D effect
                        darkcolor='#ffe81f')  # Keeps the color flat and modern

        tk.Label(self.root, text="LOADOUT UPLOAD PROGRESS",
                 font=("Courier", 10, "bold"),
                 bg="#1a1a1a", fg="#ffe81f").pack(anchor="w", padx=20)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100,
                                            style="Helldiver.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", padx=20, pady=5)

        self.status_var = tk.StringVar(value="STATUS: SYSTEM IDLE")
        tk.Label(self.root, textvariable=self.status_var, bg="#1a1a1a", fg="white", font=("Courier", 11)).pack(pady=5)

        self.ctrl_frame = tk.Frame(self.root, bg="#1a1a1a")
        self.ctrl_frame.pack(pady=20)

        self.start_btn0 = tk.Button(self.ctrl_frame, text="PREP LOAD ALL", command=lambda: self.start_watcher(0),
                                   bg="#ffe81f", fg="black", width=20, font=("Courier", 12, "bold"))
        self.start_btn0.pack(side="left", padx=0)

        self.start_btn1 = tk.Button(self.ctrl_frame, text="PREP LOAD REQUIRED", command=lambda: self.start_watcher(1),
                                   bg="#ffe81f", fg="black", width=20, font=("Courier", 12, "bold"))
        self.start_btn1.pack(side="left", padx=10)

        self.stop_btn = tk.Button(self.ctrl_frame, text="STOP", command=self.stop_watcher,
                                  bg="#444444", fg="white", width=10, font=("Courier", 12, "bold"),
                                  state="disabled")
        self.stop_btn.pack(side="left")

        # Final Setup
        self.refresh_loadouts()
        self.loadout_listbox.bind("<<ListboxSelect>>", self.on_select)
        self.root.mainloop()

    def on_closing(self):
        # This ensures the logic thread and the app die together
        logging.info("--- APPLICATION CLOSING ---")
        self.root.destroy()
        os._exit(0)

    def update_gui_progress(self, value):
        self.progress_var.set(value)
        self.root.update_idletasks()  # Forces the GUI to refresh

    def open_edit_mode(self):
        # Get the current selection from your Listbox
        selection = self.loadout_listbox.curselection()
        if not selection:
            messagebox.showwarning("Edit", "Please select a loadout to edit first.")
            return

        loadout_name = self.loadout_listbox.get(selection[0])

        # Pull the data from your manager's dictionary
        loadout_data = self.loadout_map.get(loadout_name)

        if loadout_data:
            # Re-use the creator but pass the data
            self.open_loadout_creator(edit_data=loadout_data)
        else:
            messagebox.showerror("Edit Error", "The selected loadout file could not be found.")

    def delete_loadout(self):
        selection = self.loadout_listbox.curselection()
        if not selection:
            messagebox.showwarning("Delete", "Please select a loadout to delete first.")
            return

        loadout_name = self.loadout_listbox.get(selection[0])
        loadout_path = self.loadout_map.get(loadout_name)
        if not loadout_path:
            messagebox.showerror("Delete Error", "The selected loadout file could not be found.")
            return

        if messagebox.askyesno("Delete Loadout", f"Are you sure you want to delete loadout '{loadout_name}'?", parent=self.root):
            try:
                os.remove(loadout_path)
                self.current_loadout_data = None
                self.refresh_loadouts()
                self.reset_ui()
                messagebox.showinfo("Loadout Deleted", f"Loadout '{loadout_name}' deleted.", parent=self.root)
            except OSError as error:
                messagebox.showerror("Delete Error", f"Could not delete loadout: {error}", parent=self.root)

    # --- Mapping Panel Methods ---
    def create_mapping_buttons(self):
        for db_key in self.db_configs.keys():
            btn = tk.Button(self.right_frame, text=f"MAP {db_key.upper()}",
                            command=lambda k=db_key: self.confirm_mapping(k),
                            fg="white", font=("Courier", 8, "bold"), width=18)
            btn.pack(pady=4, padx=10)
            self.map_buttons[db_key] = btn
        self.refresh_db_button_colors()

    def refresh_db_button_colors(self, event=None):
        db_folder = os.path.join(self.manager.config.basepath, "item_databases")
        for db_key, filename in self.db_configs.items():
            # Join the path so it checks ./item_databases/primary_db.json
            full_path = os.path.join(db_folder, filename)

            exists = os.path.exists(full_path)
            color = "#27ae60" if exists else "#e74c3c"
            self.map_buttons[db_key].config(bg=color)

        # repeat the same for special case wiki db button
        if hasattr(self, "gold_db_button"):
            gold_db_path = os.path.join(db_folder, "gold_wiki_db.json")
            exists = os.path.exists(gold_db_path)
            color = "#27ae60" if exists else "#e74c3c"
            self.gold_db_button.config(bg=color)

        if self.manager.degraded_dbs:
            self.handle_degraded_state()

    def confirm_mapping(self, db_key):
        instructions = (
            f"--- {db_key.upper()} CALIBRATION ---\n\n"
            "1. Navigate to the appropriate menu in the Hellpod Loadout screen.\n"
            "2. Highlight the item in the top left corner with the yellow box (navigate with arrows or WASD, not mouse).\n"
            "3. When ready, click the OK button.\n"
            "4. Hands off mouse/keyboard until calibration finishes.\n\n"
            "Begin mapping sequence?"
        )
        if messagebox.askokcancel("Maintenance", instructions):
            focus_hd2_win() #Alt tab back to the game
            self.status_var.set(f"STATUS: CALIBRATING {db_key.upper()}...")
            threading.Thread(target=self.run_mapping_thread, args=(db_key,), daemon=True).start()

    def run_mapping_thread(self, db_key):
        # This calls the mapping logic you wrote in your Manager
        self.manager.degraded_dbs.discard(db_key) if self.manager.run_mapper_by_key(db_key) else None
        self.root.after(0, self.refresh_db_button_colors, ())
        self.root.after(0, lambda *args: self.status_var.set("STATUS: CALIBRATION COMPLETE"), ())

    # --- Gold Database Methods ---
    def create_gold_database_button(self):
        btn = tk.Button(
            self.right_frame,
            text="FETCH DATABASE",
            command=self.start_gold_db,
            fg="white",
            font=("Courier", 8, "bold"),
            width=18
        )
        btn.pack(side="bottom", fill="x", pady=(12, 4), padx=10)
        self.gold_db_button = btn
        self.refresh_db_button_colors()

    def start_gold_db(self):
        self.status_var.set("STATUS: FETCHING WIKI DATABASE...")
        threading.Thread(target=self.run_gold_db_thread, daemon=True).start()

    def run_gold_db_thread(self):
        try:
            gold_path = construct_gold_db()
            if not os.path.exists(gold_path):
                raise FileNotFoundError(f"Failed to load {gold_path}")
        except Exception as error:
            self.root.after(0, lambda: messagebox.showerror("Wiki Database Error", str(error)))
            self.root.after(0, lambda: self.status_var.set("STATUS: WIKI DATABASE FAILED"))
            return

        self.root.after(0, lambda: self.status_var.set("STATUS: WIKI DATABASE COMPLETE"))

    # --- Loadout Logic Methods ---
    def refresh_loadouts(self, event=None):
        """Filters the loadout_listbox based on dynamically discovered faction tags."""
        self.faction_filter['values'] = self.get_unique_factions()
        selected_filter = self.faction_filter.get()
        self.loadout_listbox.delete(0, tk.END)
        self.loadout_map = {}  # Clear the mapping

        loadout_folder = os.path.join(self.manager.config.basepath, "loadouts")
        for filename in os.listdir(loadout_folder):
            if filename.endswith(".json"):
                path = os.path.join(loadout_folder, filename)
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)

                    # 1. Get the 'Friendly Name' from JSON, fallback to filename
                    display_name = data.get("name").upper()
                    item_factions = [tag.upper() for tag in data.get("factions", [])]

                    # 2. Filtering Logic
                    if selected_filter == "ALL" or selected_filter in item_factions:
                        self.loadout_listbox.insert(tk.END, display_name)
                        # Store the path using the display file_path as the key
                        self.loadout_map[display_name] = path
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

    def on_select(self, *args):
        self.reset_ui()

        selection = self.loadout_listbox.curselection()
        if selection:
            display_name = self.loadout_listbox.get(selection[0])
            # Retrieve the ACTUAL path from our map
            actual_path = self.loadout_map.get(display_name)

            if actual_path:
                self.update_preview(actual_path)

    def update_preview(self, file_path):
        self.reset_ui()

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Store this for the 'ARM' button to use
            self.current_loadout_data = data

            # Build manifest
            manifest = f"--- {data.get("name").upper()} ---\n\n"
            for cat in ["primary", "secondary", "grenade", "armor", "helmet", "cape"]:
                if cat in data:
                    item_val = data[cat].replace("\n", "").strip()
                    manifest += f"{cat.upper():<10}: {item_val}\n"
            # Format boosters specifically
            if "boosters" in data and isinstance(data["boosters"], list):
                manifest += "\nBOOSTER PRIORITY:\n"
                for idx, b in enumerate(data["boosters"], 1):
                    manifest += f"[{idx}] {b}\n"
            manifest += "\nSTRATAGEMS:\n"
            for i in range(1, 5):
                manifest += f"[{i}] {data.get(f'stratagem_{i}', '---')}\n"

            # Just update the config
            self.preview_text.config(text=manifest)

        except Exception as e:
            self.preview_text.config(text=f"Read Error: {e}")

    def trigger_success_timeout(self):
        """Sets a 30-second timer to reset the UI after deployment."""
        # 30,000 milliseconds = 30 seconds
        self.root.after(30000, self.check_and_reset_success, ())

    def check_and_reset_success(self, event=None):
        """Resets UI only if it's still showing the success message."""
        current = self.status_var.get()
        if "SUCCESSFUL" in current:
            self.reset_ui()

    def start_watcher(self, button):
        # 0 is for the load all, 1 is for the required only
        selection = self.loadout_listbox.curselection()
        self.manager.required_only = bool(button)
        self.button_pressed = button
        if not selection: return

        self.is_watching = True
        loadout_data = self.current_loadout_data

        getattr(self, f"start_btn{button}").config(state="disabled", text="WATCHING LOBBY...", bg="#3498db", fg="white")
        getattr(self, f"start_btn{int(not button)}").config(state="disabled", bg="#444444", fg="white")
        self.stop_btn.config(state="normal", bg="#e74c3c")
        self.status_var.set("STATUS: SCANNING FOR READY-UP...")

        threading.Thread(target=self.run_logic_thread, args=(loadout_data,), daemon=True).start()

    def stop_watcher(self):
        self.is_watching = False
        self.status_var.set("STATUS: STOPPED BY USER")
        self.reset_ui()

    def run_logic_thread(self, loadout_data):
        """Main monitoring loop with explicit state updates."""
        while self.is_watching:
            # Stage 1: The Watcher
            # (Ensure wait_for_lobby doesn't block the stop_watcher flag)
            lobby_found = wait_for_lobby(self.manager.config.get_roi("READY_ROI", (0,0,0,0)), self)

            if not self.is_watching:  # Check if user hit STOP during the wait
                break

            if lobby_found:
                # Stage 2: Transitioning to Application
                self.root.after(0, lambda *args: self.status_var.set("STATUS: LOBBY DETECTED!"), ())
                self.root.after(0, lambda *args: getattr(self,f"start_btn{self.button_pressed}").config(
                    text="APPLYING...", bg="#e67e22"), ())

                # Small delay so you can actually read the status change
                time.sleep(0.5)

                # Stage 3: Applying
                self.root.after(0, lambda *args: self.status_var.set("STATUS: TRANSMITTING LOADOUT..."), ())
                try:
                    # Run the application logic
                    # We modify apply_loadout to return a list of failed DBs
                    apply_loadout(self.manager, loadout_data, progress_callback=self.update_gui_progress)

                    if self.manager.degraded_dbs:
                        self.handle_degraded_state()
                    else:
                        self.root.after(0, lambda *args: self.status_var.set("STATUS: DEPLOYMENT SUCCESSFUL"), ())
                        self.root.after(0, lambda *args: getattr(self,f"start_btn{self.button_pressed}").config(
                            text="SUCCESS", bg="#2ecc71"), ())

                        self.trigger_success_timeout()
                        self.is_watching = False
                        break

                except ConfigurationError as e:
                    messagebox.showerror("Error", str(e))
                    self.root.after(0, lambda *args: self.status_var.set(f"STATUS: EXECUTION ERROR"), ())

                self.is_watching = False
                break
            time.sleep(0.5)
            self.root.after(2000, self.reset_ui, ())

    def handle_degraded_state(self):
        """Changes specific DB buttons to a 'Degraded' color (Orange)."""
        failed_keys = self.manager.degraded_dbs
        for key in failed_keys:
            if key in self.map_buttons:
                # Orange indicates the file exists but the data inside is wrong
                self.map_buttons[key].config(bg="#d35400", text=f"FIX {key.upper()}")

        self.status_var.set("WARNING: DATABASE DEGRADED - RE-MAPPING REQUIRED")

    def reset_ui(self):
        self.is_watching = False
        self.refresh_db_button_colors()
        self.start_btn0.config(state="normal", text="PREP LOAD ALL", bg="#ffe81f", fg="black")
        self.start_btn1.config(state="normal", text="PREP LOAD REQUIRED", bg="#ffe81f", fg="black")
        self.stop_btn.config(state="disabled", bg="#444444")
        self.status_var.set("STATUS: SYSTEM IDLE")
        self.update_gui_progress(0)
        self.manager.required_only = False

    def get_unique_factions(self):
        """Scans all JSON files to find every unique faction tag."""
        unique_factions = set()  # Use a set to prevent duplicates
        loadout_folder = os.path.join(self.manager.config.basepath, "loadouts")

        if not os.path.exists(loadout_folder):
            return ["ALL"]

        for filename in os.listdir(loadout_folder):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(loadout_folder, filename), 'r') as f:
                        data = json.load(f)
                        factions = data.get("factions", [])
                        if isinstance(factions, list):
                            for f_tag in factions:
                                unique_factions.add(f_tag.strip().upper())
                except Exception as e:
                    print(f"Error reading {filename} for factions: {e}")

        # Return "ALL" followed by the sorted unique tags
        return ["ALL"] + sorted(list(unique_factions))

    def open_loadout_creator(self, edit_data=None):
        LoadoutCreator(self.root, self.manager, self.refresh_loadouts, edit_data)

def patched_print(*args, **kwargs):
    """Overrides the built-in print to use logging instead."""
    msg = " ".join(map(str, args))
    logging.info(msg)

if __name__ == '__main__':
    app = LoadoutGUI()
    app.root.mainloop()

