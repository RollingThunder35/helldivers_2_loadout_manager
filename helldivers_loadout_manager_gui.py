import environment_setup
from utils import focus_hd2_win, validate_loadout_files, validate_loadout_data, ConfigurationError
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import time
from thefuzz import fuzz
from loadout_selection import wait_for_lobby, apply_loadout, LoadoutManager
import logging


# noinspection PyTypeChecker
class LoadoutGUI:
    def __init__(self, manager):
        self.loadout_map = None
        self.current_loadout_data = None
        self.manager = manager
        self.is_watching = False
        self.button_pressed = None

        validate_loadout_files(os.path.join(self.manager.config.basepath, "loadouts"))

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
        db_folder = os.path.join(self.manager.config.basepath,"item_databases")  # Your new subfolder
        for db_key, filename in self.db_configs.items():
            # Join the path so it checks ./item_databases/primary_db.json
            full_path = os.path.join(db_folder, filename)

            exists = os.path.exists(full_path)
            color = "#27ae60" if exists else "#e74c3c"
            self.map_buttons[db_key].config(bg=color)

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
            for cat in ["primary", "secondary", "grenade", "armor", "helmet"]:
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
        creator = tk.Toplevel(self.root)
        creator.title("EDIT LOADOUT" if edit_data else "LOADOUT ARCHITECT")
        creator.geometry("600x900")
        creator.configure(bg="#1a1a1a")  # Deep charcoal/black

        # Local storage for this session
        selections = {}

        # Track UI variables
        draft_name = tk.StringVar(value="New Loadout")
        draft_factions = tk.StringVar(value="TERMINIDS")

        # --- PRE-FILL LOGIC ---
        if edit_data:
            # IN case the input is the file name rather than the actual contained data
            if isinstance(edit_data, str):
                with open(edit_data, 'r') as f:
                    edit_data = json.load(f)
            # Fill the Entry widgets
            draft_name.set(edit_data.get("name", ""))
            draft_factions.set(", ".join(edit_data.get("factions", [])))

            # Map existing numbered stratagems back into the 'stratagems' list
            strat_list = []
            for i in range(1, 5):
                s_key = f"stratagem_{i}"
                if s_key in edit_data:
                    strat_list.append(edit_data[s_key])

            if strat_list:
                selections["stratagems"] = strat_list

            # Add boosters and other items to the internal dictionary
            for k, v in edit_data.items():
                if k not in ["name", "factions", "stratagem_1", "stratagem_2", "stratagem_3", "stratagem_4"]:
                    selections[k] = v

        # --- HEADER ---
        tk.Label(creator, text="LOADOUT NAME:", bg="#1a1a1a", fg="#ffe81f", font=("Courier", 10, "bold")).pack(
            pady=(10, 0))
        tk.Entry(creator, textvariable=draft_name, bg="#2a2a2a", fg="white", insertbackground="white").pack(fill="x",
                                                                                                            padx=40,
                                                                                                            pady=5)

        tk.Label(creator, text="FACTIONS (Comma Separated):", bg="#1a1a1a", fg="#ffe81f",
                 font=("Courier", 10, "bold")).pack(pady=(10, 0))
        tk.Entry(creator, textvariable=draft_factions, bg="#2a2a2a", fg="white", insertbackground="white").pack(
            fill="x", padx=40, pady=5)

        # --- CATEGORY SELECTION ---
        tk.Label(creator, text="1. SELECT CATEGORY", bg="#1a1a1a", fg="white", font=("Courier", 10, "bold")).pack(
            pady=(15, 0))

        cat_options = list(self.manager.dbs.keys())
        # The widget will automatically pick up the "TCombobox" style defined above
        cat_var = ttk.Combobox(creator, values=cat_options, state="readonly")
        cat_var.pack(fill="x", padx=40, pady=5)

        # --- SEARCH & RESULTS ---
        tk.Label(creator, text="2. SEARCH & SELECT ITEM", bg="#1a1a1a", fg="white").pack(pady=(10, 0))
        search_entry = tk.Entry(creator, bg="#2a2a2a", fg="white", insertbackground="white")
        search_entry.pack(fill="x", padx=40, pady=5)

        results_list = tk.Listbox(creator, bg="#000000", fg="#2ecc71", selectbackground="#333", font=("Consolas", 10))
        results_list.pack(fill="both", expand=True, padx=40, pady=10)
        results_list.bind("<<ListboxSelect>>", lambda e: update_selection_display())

        # --- CURRENT STATUS DISPLAY ---
        status_frame = tk.LabelFrame(creator, text="CURRENT SELECTIONS", bg="#1a1a1a", fg="#ffe81f", padx=10, pady=10)
        status_frame.pack(fill="x", padx=20, pady=5)
        selection_display = tk.Label(status_frame, text="Empty Loadout", justify="left", bg="#1a1a1a", fg="#aaa",
                                     font=("Courier", 8))
        selection_display.pack()
        local_manager.update_dbs()

        # --- INNER LOGIC FUNCTIONS ---
        def update_search(event=None):
            query = search_entry.get().upper()
            db_key = cat_var.get()
            results_list.delete(0, tk.END)

            # Determine which database to look in
            search_db = "stratagems" if "stratagem_" in db_key else db_key

            if search_db in self.manager.dbs:
                db_content = self.manager.dbs[search_db]
                matches = []

                for item_name, details in db_content.items():
                    # Default text for display
                    display_text = item_name
                    search_haystack = item_name.upper()

                    # --- ARMOR SPECIAL HANDLING ---
                    # If it's armor, append the metadata for searching and display
                    if search_db == "armor" and isinstance(details, dict):
                        passive = details.get("passive", "UNKNOWN").upper()
                        armor_type = details.get("cat", "").upper()  # e.g., Light, Medium, Heavy

                        # Format: NAME (TYPE PASSIVE)
                        display_text = f"{item_name} ({armor_type} {passive})"
                        search_haystack = display_text.upper()

                    # --- FUZZY MATCHING ---
                    # We search against the full haystack (Name + Passive)
                    score = fuzz.partial_ratio(query, search_haystack)

                    if query == "" or score > 70:
                        matches.append((display_text, score))

                # Sort by highest score, then alphabetically
                matches.sort(key=lambda x: (-x[1], x[0]))

                for text, score in matches:
                    results_list.insert(tk.END, text)

        def update_selection_display():
            """Formats the dictionary into a readable manifest with counters."""
            summary = []

            # Sort keys to keep the list organized
            for sel_keys in sorted(selections.keys()):
                val = selections[sel_keys]

                # 1. If the value is a LIST (Boosters or Stratagems)
                if isinstance(val, list):
                    count = len(val)
                    # This only joins if it's a list of strings
                    items_str = ", ".join(val)
                    summary.append(f"{sel_keys.upper()} ({count}/4): {items_str}")

                # 2. If the value is a STRING (Armor, Primary, etc.)
                else:
                    summary.append(f"{sel_keys.upper()}: {val}")

            display_text = "\n".join(summary) if summary else "Empty Loadout"
            selection_display.config(text=display_text, fg="#2ecc71")

        def add_item():
            category = cat_var.get()
            selection_idx = results_list.curselection()

            if not category or not selection_idx:
                return

            selection = results_list.get(selection_idx)

            # Standardize the key (Boosters/Stratagems)
            list_key = "boosters" if category == "booster" else "stratagems" if category == "stratagem" else category

            # Logic for List-based selections
            if list_key in ["stratagems", "boosters"]:
                if list_key not in selections:
                    selections[list_key] = []

                if selection in selections[list_key]:
                    messagebox.showinfo("Note", f"This {category} is already selected.")
                    return

                if len(selections[list_key]) >= 4:
                    # Trigger the Swap Dialog instead of showing a warning
                    open_swap_dialog(list_key, selection)
                else:
                    selections[list_key].append(selection)
                    update_selection_display()

            # Logic for Single-slot selections
            else:
                selections[category] = selection
                update_selection_display()

        def open_swap_dialog(list_key, new_item):
            """Creates a popup to let the user choose which item to replace."""
            swap_win = tk.Toplevel(creator)
            swap_win.title("SLOT LIMIT REACHED")
            swap_win.geometry("400x300")
            swap_win.grab_set()  # Forces user to interact with this window

            tk.Label(swap_win, text=f"Select an item to replace with:\n{new_item}",
                     pady=10, font=("Courier", 10, "bold")).pack()

            def replace(rep_index):
                selections[list_key][rep_index] = new_item
                update_selection_display()
                swap_win.destroy()

            # Create a button for each currently equipped item
            for index, current_item in enumerate(selections[list_key]):
                btn_text = f"REPLACE: {current_item}"
                tk.Button(swap_win, text=btn_text, width=40, pady=5,
                          command=lambda idx=index: replace(idx)).pack(pady=2)

            tk.Button(swap_win, text="CANCEL", command=swap_win.destroy, fg="red").pack(pady=10)

        def save_loadout():
            # Create a copy to avoid messing with the live draft
            data_to_save = {
                "name": draft_name.get(),
                "factions": [faction_name.strip().upper() for faction_name in draft_factions.get().split(",") if faction_name.strip()],
                **{key: values for key, values in selections.items() if key != "stratagems"}  # Copy everything except the list
            }

            # Convert the 'stratagems' list back to 'stratagem_1', etc. for the automation script
            if "stratagems" in selections:
                for idx, strat in enumerate(selections["stratagems"], 1):
                    data_to_save[f"stratagem_{idx}"] = strat

            # Validate using your shared function
            is_valid, error_msg = validate_loadout_data(data_to_save)

            if not is_valid:
                messagebox.showerror("Validation Failed", error_msg)
                return

            if edit_data and draft_name.get() == edit_data['name']:
                # If the name is the same, we are overwriting
                confirm = messagebox.askyesno("Confirm", f"Overwrite existing loadout '{draft_name.get()}'?")
                if not confirm: return

            # Success path
            clean_filename = "".join(c for c in data_to_save["name"].lower() if c.isalnum() or c in (' ', '_')).replace(' ',
                                                                                                              '_').lower()
            save_path = os.path.join(self.manager.config.basepath,"loadouts", f"{clean_filename}.json")

            try:
                with open(save_path, 'w') as file:
                    json.dump(data_to_save, file, indent=4)
                messagebox.showinfo("Success", f"Loadout '{data_to_save['name']}' saved!")
                creator.destroy()
                self.refresh_loadouts()  # Update main GUI list
            except Exception as e:
                messagebox.showerror("File Error", f"Could not save file: {e}")

        # --- CONTROLS ---
        search_entry.bind("<KeyRelease>", update_search)
        cat_var.bind("<<ComboboxSelected>>", update_search)

        btn_frame = tk.Frame(creator, bg="#1a1a1a")
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="ADD ITEM", width=15, bg="#3498db", fg="white", command=add_item).pack(side="left",
                                                                                                         padx=5)
        tk.Button(btn_frame, text="SAVE & VALIDATE", width=15, bg="#2ecc71", fg="white", command=save_loadout).pack(
            side="left", padx=5)

def patched_print(*args, **kwargs):
    """Overrides the built-in print to use logging instead."""
    msg = " ".join(map(str, args))
    logging.info(msg)

if __name__ == '__main__':
    local_manager = LoadoutManager()
    app = LoadoutGUI(local_manager)
    app.root.mainloop()

