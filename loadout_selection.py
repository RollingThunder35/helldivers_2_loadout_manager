import json
import os
import re
from tkinter import messagebox

import pydirectinput
import time

from thefuzz import fuzz

from utils import ConfigManager, focus_hd2_win, STRAT_CATS, ARMOR_CATS, GRENADE_CATS, SECONDARY_CATS, PRIMARY_CATS, \
    ConfigurationError
from database_mapper import ocr_from_screen, map_categorized_grid, map_flat_grid


class LoadoutManager:
    def __init__(self):
        self.config = ConfigManager()
        # Load all your hard-earned JSON databases
        self.dbs = {
            "primary": self._load_json(os.path.join(self.config.basepath,"item_databases","primary_db.json")),
            "secondary": self._load_json(os.path.join(self.config.basepath,"item_databases","secondary_db.json")),
            "armor": self._load_json(os.path.join(self.config.basepath,"item_databases","armor_db.json")),
            "stratagems": self._load_json(os.path.join(self.config.basepath,"item_databases","stratagem_db.json")),
            "booster": self._load_json(os.path.join(self.config.basepath,"item_databases","booster_db.json")),
            "helmet": self._load_json(os.path.join(self.config.basepath,"item_databases","helmet_db.json")),
            "grenade": self._load_json(os.path.join(self.config.basepath,"item_databases","grenade_db.json")),
            "cape": self._load_json(os.path.join(self.config.basepath,"item_databases","cape_db.json"))
        }
        self.degraded_dbs = set()
        # Track the 'virtual' cursor for each menu
        self.current_pos = [0, 0]
        self.last_loaded = None # Track last loadout and only apply everything if it's needed
        self.required_only = False

    @staticmethod
    def _find_best_match(target_name, db_keys):
        """
        Enhanced search: Handles 'FRAG' -> 'G-6 FRAG' and
        strips row-col suffixes for cleaner comparison.
        """
        best_match = None
        highest_score = 0

        target_clean = target_name.upper().strip()

        for key in db_keys:
            # 1. Clean the DB key (Remove the (row-col) suffix for the match check)
            # This prevents '(0-0)' from lowering your fuzzy score
            clean_key = key.split('(')[0].strip().upper()

            # 2. Use WRatio for better partial/shorthand matching
            # WRatio handles case-insensitivity and partials 'FRAG' in 'G-6 FRAG'
            score = fuzz.WRatio(target_clean, clean_key)

            # 3. Check for exact partial (If 'FRAG' is literally IN the key)
            # We give a small boost if the shorthand is an exact substring
            if target_clean in clean_key:
                score += 5

            if score > highest_score:
                highest_score = score
                best_match = key

        return best_match, highest_score

    @staticmethod
    def _load_json(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: {filename} not found.")
            return {}

    def _align_category(self, target_cat, cat_roi, category_list):
        """Navigates tabs and updates virtual row position."""
        print(f"Aligning Category: Moving to {target_cat}...")

        for _ in range(len(category_list) * 2):
            current_cat_text = ocr_from_screen(cat_roi)

            if fuzz.ratio(target_cat.upper(), current_cat_text.upper()) > 95:
                print(f"√ Category Confirmed: {target_cat}")
                return True
            else:
                print(f"Want {target_cat.upper()} but have {current_cat_text.upper()}.")

            pydirectinput.press(self.config.get_control("MENU TAB RIGHT","c"))  # Tab Right
            time.sleep(0.4)

            # Tab switching resets Row to 0, but Column stays!
            self.current_pos[0] = 0

        return False

    def update_dbs(self):
        self.dbs = {
            "primary": self._load_json(os.path.join(self.config.basepath,"item_databases","primary_db.json")),
            "secondary": self._load_json(os.path.join(self.config.basepath,"item_databases","secondary_db.json")),
            "armor": self._load_json(os.path.join(self.config.basepath,"item_databases","armor_db.json")),
            "stratagems": self._load_json(os.path.join(self.config.basepath,"item_databases","stratagem_db.json")),
            "booster": self._load_json(os.path.join(self.config.basepath,"item_databases","booster_db.json")),
            "helmet": self._load_json(os.path.join(self.config.basepath,"item_databases","helmet_db.json")),
            "grenade": self._load_json(os.path.join(self.config.basepath,"item_databases","grenade_db.json")),
            "cape": self._load_json(os.path.join(self.config.basepath,"item_databases","cape_db.json"))
        }

    def run_mapper_by_key(self,db_key):
        """
        Dynamically fetches constants and routes to the mapper.
        Example: 'primary' -> fetches PRIMARY_ITEM_ROI, PRIMARY_CAT_ROI, etc.
        """
        # 1. Standardize the root file_path (e.g., 'primary' -> 'PRIMARY')
        # Note: If your constants use 'STRAT' instead of 'STRATAGEM',
        # you can add a small override dictionary.
        root = db_key.upper()
        if root == "STRATAGEMS":
            root = "STRAT"
            db_key = "stratagem"

        # 2. Dynamically fetch the variables from your global scope
        # globals() returns a dictionary of all variables defined in your script
        item_roi = self.config.get_roi(f"{root}_ITEM_ROI", (0,0,0,0))
        cat_roi = self.config.get_roi(f"{root}_CAT_ROI", (0,0,0,0))
        perk_roi = self.config.get_roi(f"{root}_PERK_ROI", (0,0,0,0))
        cats = globals().get(f"{root}_CATS", [])

        # Add a catch to make sure we didn't fail here
        if not item_roi:
            print(f"Warning: {root} ROIs not found.")
            return None

        # 3. Handle the filename
        filename = f"{db_key}_db"

        # Check if we have categories; if not, call the standard grid mapper
        if cats:
            success = map_categorized_grid(filename, item_roi, cat_roi, cats, perk_roi)
        else:
            success =  map_flat_grid(filename, item_roi)
        self.update_dbs()
        return success

    def navigate_to(self, target_name, db_key, item_roi, cat_roi=None, category_list=None):
        db = self.dbs.get(db_key)
        retry_counter = 2

        while retry_counter > 0:
            # 1. FIND TARGET DATA (Fuzzy Search)
            best_match_key, match_score = self._find_best_match(target_name, list(db.keys()))
            if match_score < 80:
                print(f"X No match for '{target_name}. Closest match: {best_match_key} at {match_score}'")
                return False
            else:
                print(f"'{best_match_key}' matched '{target_name}' at {match_score}%")

            target_data = db[best_match_key]
            target_pos = target_data["pos"]
            target_cat = target_data.get("cat")

            # 2. ALIGN CATEGORY (Same as before)
            if target_cat and category_list:
                if not self._align_category(target_cat, cat_roi, category_list):
                    retry_counter = retry_counter - 1
                    print(f"Unable to find the {target_cat} category. Retrying {retry_counter} more times...")
                    continue

            # 3. STATE-AWARE POSITION FINDING
            # Read what we are actually hovering over right now
            current_screen_text = ocr_from_screen(item_roi)

            # Reverse lookup: Where are we?
            current_match_key, current_score = self._find_best_match(current_screen_text, list(db.keys()))

            if current_score > 70:
                self.current_pos = db[current_match_key]["pos"]
                print(f"I am currently at {current_match_key} {self.current_pos}")
            else:
                # FALLBACK: If we can't identify where we are, bail out
                ocr_from_screen(cat_roi, f"positioning_alignment_{current_match_key}")
                retry_counter = retry_counter - 1
                print(f"Verification failed. {current_match_key} not a valid location. Retry {retry_counter} more times.")
                continue

            # 4. CALCULATE DELTA & MOVE
            delta_row = target_pos[0] - self.current_pos[0]
            delta_col = target_pos[1] - self.current_pos[1]

            print(f"Moving to {best_match_key} (Delta: {delta_row}R, {delta_col}C)")
            self._move_cursor(delta_row, delta_col)

            # 5. FINAL VERIFICATION
            time.sleep(0.3)
            ver_value = ocr_from_screen(item_roi).upper()
            if fuzz.partial_ratio(best_match_key.upper(), ver_value) > 75:
                pydirectinput.press(self.config.get_control("ENTER MENU"))
                return True

            retry_counter = retry_counter - 1
            ocr_from_screen(cat_roi, f"ver_alignment_{best_match_key}")
            print(f"Verification failed. Found {ver_value} instead. Retry {retry_counter} more times.")
        print("All verification failed. Terminating Search...")
        return False

    @staticmethod
    def _move_cursor(dr, dc):
        # Handle Rows
        row_key = 's' if dr > 0 else 'w'
        for _ in range(abs(dr)):
            pydirectinput.press(row_key)
            time.sleep(0.1)

        # Handle Columns
        col_key = 'd' if dc > 0 else 'a'
        for _ in range(abs(dc)):
            pydirectinput.press(col_key)
            time.sleep(0.1)

    def apply_booster_priority(self, priority_list, db_key, item_roi):
        """
        Iterates through priorities. If navigate_to fails (Verification Mismatch),
        it assumes the booster was greyed out/taken and tries the next one.
        """
        print(f"--- Initiating Booster Priority Sequence ---")

        for booster_name in priority_list:
            print(f"Attempting to secure: {booster_name}")

            # We reuse your existing navigation method.
            success = self.navigate_to(
                target_name=booster_name,
                db_key=db_key,
                item_roi=item_roi
            )

            occupied = ocr_from_screen(item_roi)

            if success and fuzz.ratio(occupied,booster_name) < 75:
                # If successful, the 'space'/selection was pressed in navigate_to.
                # We are now kicked back to the main loadout menu.
                print(f"SUCCESS: {booster_name} equipped.")
                return True

            print(f"NOTICE: {booster_name} unavailable or navigation failed. Trying next...")
            # Since your navigate_to presses 'escape' on failure, we might need
            # to re-enter the booster menu here if your flow requires it.
            # pydirectinput.press(self.config.get_control("ENTER MENU"))  # Re-open booster menu for next attempt
            time.sleep(0.3)

        print("CRITICAL: All priority boosters are unavailable.")
        pydirectinput.press('escape')  # Close menu and give up
        return False

def wait_for_lobby(ready_roi, gui_instance):
    """
    ready_roi: The screen region to monitor.
    gui_instance: The LoadoutGUI object so we can check gui_instance.is_watching.
    """
    print("Watcher: Monitoring for Ready-Up screen...")

    while gui_instance.is_watching:
        # Perform the actual screen check
        text = ocr_from_screen(ready_roi)

        if any(word in text for word in ["READY", "UP", "PREPARE"]):
            return True

        # Short sleep to prevent CPU spiking
        time.sleep(0.7)

    # If gui_instance.is_watching becomes False, the loop exits here
    return False

def apply_loadout(manager, loadout, progress_callback=None):
    """
    Main automation loop to apply a Helldivers 2 loadout.
    Uses a progress_callback(message, percentage) to update the GUI.
    """

    # Sanity check to prevent users from running without loading all DBs
    if any(len(db) == 0 for db in manager.dbs.values()):
        print("Empty database escape triggered.")
        messagebox.showwarning("Empty Database", "An empty database was detected. "
                                                 "Please ensure all databases are populated. Unpopulated databases "
                                                 "have red buttons on the right.")
        return

    def update_progress(total_pct):
        if progress_callback:
            progress_callback(total_pct)

    try:
        print(f"Loading Helldivers 2 loadout: {loadout["name"]}...")
        update_progress(5)
        # Ensure focus_hd2_win() is imported/defined in your scope
        focus_hd2_win()

        # --- 1. STRATAGEMS (0% -> 25%) ---
        update_progress(10)
        pydirectinput.press(manager.config.get_control("ENTER MENU", "space"))
        time.sleep(0.3)

        for strat_num in range(1, 5):
            strat_key = f"stratagem_{strat_num}"
            update_progress(10 + (strat_num * 3))

            success = manager.navigate_to(
                loadout[strat_key],
                "stratagems",
                manager.config.get_roi("STRAT_ITEM_ROI", (0, 0, 0, 0)),
                manager.config.get_roi("STRAT_CAT_ROI", (0, 0, 0, 0)),
                # Ensure STRAT_CATS is accessible
                STRAT_CATS
            )
            if not success:
                manager.degraded_dbs.add("stratagems")

        # --- 2. BOOSTERS (25% -> 35%) ---
        update_progress(30)
        pydirectinput.press(manager.config.get_control("RIGHT", "d"))
        pydirectinput.press(manager.config.get_control("ENTER MENU", "space"))
        time.sleep(0.3)

        if not manager.apply_booster_priority(
                loadout["boosters"],
                "booster",
                manager.config.get_roi("BOOSTER_ITEM_ROI", (0, 0, 0, 0))
        ):
            pydirectinput.press('escape')
            manager.degraded_dbs.add("booster")

        # --- 3. EQUIPMENT TAB (35% -> 70%) ---
        if manager.required_only:
            print("Required only detected. Finishing loadout...")
            update_progress(100)
            manager.last_loaded = loadout["name"]
            return

        update_progress(40)
        pydirectinput.press(manager.config.get_control("SWITCH", "q"))
        time.sleep(0.5)

        def handle_equipment(target, db_key, item_roi, cat_roi=None, cat_list=None):
            # Inner helper for repetitive equipment navigation
            pydirectinput.press(manager.config.get_control("ENTER MENU", "space"))
            time.sleep(0.3)

            success = manager.navigate_to(target, db_key, item_roi, cat_roi, cat_list)

            # Equipment sub-menus require a manual escape
            pydirectinput.press('escape')
            time.sleep(0.3)
            if not success:
                manager.degraded_dbs.add(db_key)

        # HELMET
        update_progress(45)
        handle_equipment(
            loadout["helmet"],
            "helmet",
            manager.config.get_roi("HELMET_ITEM_ROI", (0, 0, 0, 0))
        )

        # ARMOR
        update_progress(55)
        pydirectinput.press(manager.config.get_control("RIGHT", "d"))
        # Clean the armor name from any trailing info like "(Heavy)"
        clean_armor = re.sub(r'\s*\(.*?\)$', '', loadout["armor"]).strip()
        handle_equipment(
            clean_armor,
            "armor",
            manager.config.get_roi("ARMOR_ITEM_ROI", (0, 0, 0, 0)),
            manager.config.get_roi("ARMOR_CAT_ROI", (0, 0, 0, 0)),
            ARMOR_CATS
        )

        # CAPE
        update_progress(65)
        pydirectinput.press(manager.config.get_control("RIGHT", "d"))
        handle_equipment(
            loadout["cape"],
            "cape",
            manager.config.get_roi("CAPE_ITEM_ROI", (0, 0, 0, 0))
        )

        # --- 4. WEAPONRY (Lower Row) (70% -> 100%) ---
        update_progress(70)
        pydirectinput.press(manager.config.get_control("DOWN", "s"))

        # GRENADE
        update_progress(75)
        pydirectinput.press(manager.config.get_control("ENTER MENU", "space"))
        handle_equipment(
            loadout["grenade"],
            "grenade",
            manager.config.get_roi("GRENADE_ITEM_ROI", (0, 0, 0, 0)),
            manager.config.get_roi("GRENADE_CAT_ROI", (0, 0, 0, 0)),
            GRENADE_CATS
        )

        # SECONDARY
        update_progress(85)
        pydirectinput.press(manager.config.get_control("LEFT", "a"))
        pydirectinput.press(manager.config.get_control("ENTER MENU", "space"))
        handle_equipment(
            loadout["secondary"],
            "secondary",
            manager.config.get_roi("SECONDARY_ITEM_ROI", (0, 0, 0, 0)),
            manager.config.get_roi("SECONDARY_CAT_ROI", (0, 0, 0, 0)),
            SECONDARY_CATS
        )

        # PRIMARY
        update_progress(95)
        pydirectinput.press(manager.config.get_control("LEFT", "a"))
        pydirectinput.press(manager.config.get_control("ENTER MENU", "space"))
        handle_equipment(
            loadout["primary"],
            "primary",
            manager.config.get_roi("PRIMARY_ITEM_ROI", (0, 0, 0, 0)),
            manager.config.get_roi("PRIMARY_CAT_ROI", (0, 0, 0, 0)),
            PRIMARY_CATS
        )

        # Final Cleanup
        update_progress(100)
        pydirectinput.press(manager.config.get_control("SWITCH", "q"))
        manager.last_loaded = loadout["name"]

    except ConfigurationError as e:
        # This re-raises the error to be caught by the GUI thread
        update_progress(0)
        raise e
    except Exception as e:
        update_progress(0)
        raise e