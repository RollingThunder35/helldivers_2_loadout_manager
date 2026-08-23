import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from thefuzz import fuzz


class LoadoutCreator:
    def __init__(self, parent, manager, refresh_callback, edit_data=None):
        self.parent = parent
        self.manager = manager
        self.refresh_callback = refresh_callback
        self.edit_data = edit_data
        self.selections = {}

        self.creator = tk.Toplevel(parent)
        self.creator.title("EDIT LOADOUT" if edit_data else "LOADOUT ARCHITECT")
        self.creator.geometry("600x900")
        self.creator.configure(bg="#1a1a1a")

        self.draft_name = tk.StringVar(value="New Loadout")
        self.draft_factions = tk.StringVar(value="TERMINIDS")
        self._prefill_edit_data()
        self._build_ui()

    def _prefill_edit_data(self):
        if not self.edit_data:
            return

        if isinstance(self.edit_data, str):
            with open(self.edit_data, 'r') as loadout_file:
                self.edit_data = json.load(loadout_file)

        for key, value in self.edit_data.items():
            if key == "name":
                self.draft_name.set(value)
            elif key == "factions":
                self.draft_factions.set(", ".join(value))
            elif key.startswith("stratagem"):
                self.selections.setdefault("stratagems", []).append(value)
            else:
                self.selections[key] = value

    def _build_ui(self):
        tk.Label(self.creator, text="LOADOUT NAME:", bg="#1a1a1a", fg="#ffe81f",
                 font=("Courier", 10, "bold")).pack(pady=(10, 0))
        tk.Entry(self.creator, textvariable=self.draft_name, bg="#2a2a2a", fg="white",
                 insertbackground="white").pack(fill="x", padx=40, pady=5)

        tk.Label(self.creator, text="FACTIONS (Comma Separated):", bg="#1a1a1a", fg="#ffe81f",
                 font=("Courier", 10, "bold")).pack(pady=(10, 0))
        tk.Entry(self.creator, textvariable=self.draft_factions, bg="#2a2a2a", fg="white",
                 insertbackground="white").pack(fill="x", padx=40, pady=5)

        tk.Label(self.creator, text="1. SELECT CATEGORY", bg="#1a1a1a", fg="white",
                 font=("Courier", 10, "bold")).pack(pady=(15, 0))

        self.cat_var = ttk.Combobox(self.creator, values=list(self.manager.dbs.keys()), state="readonly")
        self.cat_var.pack(fill="x", padx=40, pady=5)

        tk.Label(self.creator, text="2. SEARCH & SELECT ITEM", bg="#1a1a1a", fg="white").pack(pady=(10, 0))
        self.search_entry = tk.Entry(self.creator, bg="#2a2a2a", fg="white", insertbackground="white")
        self.search_entry.pack(fill="x", padx=40, pady=5)

        self.results_list = tk.Listbox(self.creator, bg="#000000", fg="#2ecc71", selectbackground="#333",
                                       font=("Consolas", 10))
        self.results_list.pack(fill="both", expand=True, padx=40, pady=10)
        self.results_list.bind("<<ListboxSelect>>", lambda event: self.update_selection_display())

        status_frame = tk.LabelFrame(self.creator, text="CURRENT SELECTIONS", bg="#1a1a1a", fg="#ffe81f",
                                     padx=10, pady=10)
        status_frame.pack(fill="x", padx=20, pady=5)
        self.selection_display = tk.Label(status_frame, text="Empty Loadout", justify="left", bg="#1a1a1a",
                                          fg="#aaa", font=("Courier", 8))
        self.selection_display.pack()
        self.manager.update_dbs()

        self.search_entry.bind("<KeyRelease>", self.update_search)
        self.cat_var.bind("<<ComboboxSelected>>", self.update_search)

        button_frame = tk.Frame(self.creator, bg="#1a1a1a")
        button_frame.pack(pady=20)
        tk.Button(button_frame, text="ADD ITEM", width=15, bg="#3498db", fg="white",
                  command=self.add_item).pack(side="left", padx=5)
        self.capture_button = tk.Button(button_frame, text="READ CURRENT LOADOUT", width=22, bg="#9b59b6",
                                        fg="white", command=self.capture_current_loadout)
        self.capture_button.pack(side="left", padx=5)
        tk.Button(button_frame, text="SAVE & VALIDATE", width=15, bg="#2ecc71", fg="white",
                  command=self.save_loadout).pack(side="left", padx=5)

        self.update_selection_display()

    def update_search(self, event=None):
        query = self.search_entry.get().upper()
        category = self.cat_var.get()
        self.results_list.delete(0, tk.END)
        search_db = "stratagems" if "stratagem_" in category else category

        if search_db not in self.manager.dbs:
            return

        matches = []
        for item_name, details in self.manager.dbs[search_db].items():
            display_text = item_name
            search_haystack = item_name.upper()

            if search_db == "armor" and isinstance(details, dict):
                passive = details.get("passive", "UNKNOWN").upper()
                armor_type = details.get("cat", "").upper()
                display_text = f"{item_name} ({armor_type} {passive})"
                search_haystack = display_text.upper()

            score = fuzz.partial_ratio(query, search_haystack)
            if query == "" or score > 70:
                matches.append((display_text, score))

        matches.sort(key=lambda item: (-item[1], item[0]))
        for display_text, _ in matches:
            self.results_list.insert(tk.END, display_text)

    def update_selection_display(self):
        summary = []
        for selection_key in sorted(self.selections.keys()):
            value = self.selections[selection_key]
            if isinstance(value, list):
                summary.append(f"{selection_key.upper()} ({len(value)}/4): {', '.join(value)}")
            else:
                summary.append(f"{selection_key.upper()}: {value}")

        display_text = "\n".join(summary) if summary else "Empty Loadout"
        self.selection_display.config(text=display_text, fg="#2ecc71")

    def add_item(self):
        category = self.cat_var.get()
        selection_indexes = self.results_list.curselection()
        if not category or not selection_indexes:
            return

        selection = self.results_list.get(selection_indexes[0])
        list_key = "boosters" if category == "booster" else "stratagems" if category == "stratagem" else category

        if list_key in ["stratagems", "boosters"]:
            if list_key not in self.selections:
                self.selections[list_key] = []

            if selection in self.selections[list_key]:
                messagebox.showinfo("Note", f"This {category} is already selected.")
                return

            if len(self.selections[list_key]) >= 4:
                self.open_swap_dialog(list_key, selection)
            else:
                self.selections[list_key].append(selection)
                self.update_selection_display()
        else:
            self.selections[category] = selection
            self.update_selection_display()

    def open_swap_dialog(self, list_key, new_item):
        swap_window = tk.Toplevel(self.creator)
        swap_window.title("SLOT LIMIT REACHED")
        swap_window.geometry("400x300")
        swap_window.grab_set()

        tk.Label(swap_window, text=f"Select an item to replace with:\n{new_item}",
                 pady=10, font=("Courier", 10, "bold")).pack()

        def replace(replace_index):
            self.selections[list_key][replace_index] = new_item
            self.update_selection_display()
            swap_window.destroy()

        for index, current_item in enumerate(self.selections[list_key]):
            tk.Button(swap_window, text=f"REPLACE: {current_item}", width=40, pady=5,
                      command=lambda replace_index=index: replace(replace_index)).pack(pady=2)

        tk.Button(swap_window, text="CANCEL", command=swap_window.destroy, fg="red").pack(pady=10)

    def save_loadout(self):
        data_to_save = {
            "name": self.draft_name.get(),
            "factions": [faction.strip().upper() for faction in self.draft_factions.get().split(",") if faction.strip()],
            **{key: value for key, value in self.selections.items() if key != "stratagems"}
        }

        for index, stratagem in enumerate(self.selections.get("stratagems", []), 1):
            data_to_save[f"stratagem_{index}"] = stratagem

        from utils import validate_loadout_data
        is_valid, error_message = validate_loadout_data(data_to_save)
        if not is_valid:
            messagebox.showerror("Validation Failed", error_message)
            return

        if self.edit_data and self.draft_name.get() == self.edit_data["name"]:
            if not messagebox.askyesno("Confirm", f"Overwrite existing loadout '{self.draft_name.get()}'?"):
                return

        clean_filename = "".join(
            character for character in data_to_save["name"].lower() if character.isalnum() or character in (' ', '_')
        ).replace(' ', '_')
        save_path = os.path.join(self.manager.config.basepath, "loadouts", f"{clean_filename}.json")

        try:
            with open(save_path, 'w') as loadout_file:
                json.dump(data_to_save, loadout_file, indent=4)
            messagebox.showinfo("Success", f"Loadout '{data_to_save['name']}' saved!")
            self.creator.destroy()
            self.refresh_callback()
        except Exception as error:
            messagebox.showerror("File Error", f"Could not save file: {error}")

    def capture_current_loadout(self):

        def read_in_game():
            try:
                captured = self.manager.read_current_loadout()
                self.creator.after(0, self.apply_captured_loadout, captured)
            except Exception as error:
                self.creator.after(0, lambda: messagebox.showerror("Read Error", str(error)))
                self.creator.after(0, lambda: self.capture_button.config(
                    state="normal", text="READ CURRENT LOADOUT"
                ))

        instructions = (
            "--- READ CURRENT LOADOUT ---\n\n"
            "1. Highlight the first strategem in the Hellpod Loadout screen.\n"
            "2. When ready, click the OK button.\n"
            "3. Hands off mouse/keyboard until reading finishes.\n\n"
            "Read-in the currently selected loadout?"
        )
        if messagebox.askokcancel("Read Current Loadout", instructions):
            self.capture_button.config(state="disabled", text="READING IN-GAME LOADOUT...")
            threading.Thread(target=read_in_game, daemon=True).start()

    def apply_captured_loadout(self, captured):
        self.selections.update({
            key: value for key, value in captured.items() if key not in ("stratagems", "boosters")
        })
        self.selections["stratagems"] = captured["stratagems"]
        self.selections["boosters"] = captured["boosters"]
        self.update_selection_display()
        self.capture_button.config(state="normal", text="READ CURRENT LOADOUT")
        messagebox.showinfo("Loadout Read", "Current equipment & stratagems added to this loadout.")