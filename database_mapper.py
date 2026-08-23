import json
import os.path
import time

import requests

# noinspection PyPackageRequirements
import cv2
import easyocr
import numpy as np
import pyautogui
import pydirectinput
from thefuzz import fuzz

from environment_setup import get_base_path
from utils import ConfigurationError, focus_hd2_win, ConfigManager, ROIOverlay

# Activate failsafe
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

# Initialize the reader once (set gpu=True if you have an NVIDIA GPU)
reader = easyocr.Reader(['en'], gpu=False, verbose=False)

GOLD_DB_FILE = "gold_wiki_db.json"

GOLD_DB_CATEGORIES = {
    "primary_db": "Primary_Weapons",
    "secondary_db": "Secondary_Weapons",
    "grenade_db": "Throwables",
    "stratagem_db": "Stratagems",
    "booster_db": "Boosters",
    "helmet_db": "Helmets",
    "armor_db": ["Light Armor", "Medium Armor", "Heavy Armor"],
    "cape_db": "Capes"
}


def ocr_from_screen(roi_coords, roi_overlay=None):
    """
    roi_coords: (left, top, width, height)
    """

    # 1. Validation Check
    if not roi_coords or any(v <= 0 for v in roi_coords[2:]):
        raise ConfigurationError(f"Invalid ROI: {roi_coords}.")

    if roi_overlay:
        roi_overlay.show_at(roi_coords=roi_coords)

    try:
        # 2. Attempt the screenshot
        screenshot = pyautogui.screenshot(region=roi_coords)
        if screenshot is None:
            raise ConfigurationError(f"Failed to capture screenshot at {roi_coords}.")

        frame = np.array(screenshot)
        if frame.size == 0:
            raise ConfigurationError(f"Captured frame is empty at {roi_coords}.")

        # Begin processing
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Perform OCR on the whole 'frame'
        hd_allowlist = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-&/ "
        results = reader.readtext(frame, detail=0, paragraph=True, allowlist=hd_allowlist)

        # Process Text
        raw_text = " ".join(results) if results else ""
        text = raw_text.upper()

        font_corrections = {
            "HEAUY": "HEAVY", "ADUANCED": "ADVANCED", "CONCUSSIUE": "CONCUSSIVE",
            "SERUICE": "SERVICE", "EUAC": "EVAC", "EUIDENCE": "EVIDENCE",
            "OFFENSIUE": "OFFENSIVE", "DEFENSIUE": "DEFENSIVE", "SERUO": "SERVO",
            "HOUER": "HOVER"
        }

        for error, correction in font_corrections.items():
            text = text.replace(error, correction)

        if roi_overlay:
            roi_overlay.fade_out()

        return text
    finally:
        # Always close the overlay if something fails
        if roi_overlay:
            roi_overlay.fade_out()

def map_categorized_grid(db_name, item_roi, cat_roi, category_list, perk_roi=None, overlay_tool=None):
    """
    Maps menus with tabs (e.g., Offensive, Defensive).
    Assumes starting at (0,0) in the first category.
    """
    master_db = {}
    config = ConfigManager()
    gold_db = load_gold_database()

    if "strat" in db_name:
        fuzzy_threshold = 95
    else:
        fuzzy_threshold = 85

    # Give a waiting period before beginning operations
    print(f"\n--- Initializing {db_name} Mapping ---")
    time.sleep(2)
    focus_hd2_win()
    time.sleep(.5)

    for cat_name in category_list:
        print(f"Mapping Category: {cat_name}")
        cat_counter = 0

        # Ensure we are in the right tab
        while cat_counter < len(category_list)*2:
            current_tab = ocr_from_screen(cat_roi, overlay_tool)
            print(f"Have {current_tab} and want {cat_name}")
            if fuzz.partial_ratio(cat_name.upper(), current_tab.upper()) > fuzzy_threshold:
                cat_counter = -1
                break
            pydirectinput.press(config.get_control("MENU TAB RIGHT","c"))
            time.sleep(config.get_control("CAT SWITCH DELAY",0.4))
            cat_counter += 1

        if cat_counter != -1:
            print(f"Unable to find category {cat_name}. Skipping...")
            continue

        for row in range(35):
            row_anchor = ocr_from_screen(item_roi, overlay_tool)
            col = 0

            while True:
                ocr_item = ocr_from_screen(item_roi, overlay_tool)
                current_item, match_score = canonicalize_item_name(ocr_item, db_name, gold_db)
                if current_item != ocr_item:
                    print(f"Gold match: '{ocr_item}' -> '{current_item}' ({match_score}%)")
                current_passive = ocr_from_screen(perk_roi, overlay_tool) if perk_roi != (0,0,0,0) and perk_roi is not None else None
                if current_item and current_item not in master_db:
                    master_db[current_item] = {"cat": cat_name, "pos": [row, col]}
                    # For armor specifically, we will map the passive to make it easier to search through
                    if current_passive:
                        master_db[current_item]["passive"] = current_passive
                        print(f"Passive found: {current_passive}")
                    print(f"[{cat_name}] Mapped: {current_item} at {row}, {col}")

                pydirectinput.press(config.get_control("RIGHT","d"))
                time.sleep(config.get_control("OCR READ DELAY", 0.3))

                # Have to hardcode the number of columns in the armor table due to the B01s
                if "B-01" not in row_anchor and fuzz.ratio(row_anchor, ocr_from_screen(item_roi, overlay_tool)) > fuzzy_threshold:
                    break
                elif "B-01" in row_anchor and col > 1:
                    break
                col += 1

            pydirectinput.press(config.get_control("DOWN","s"))
            time.sleep(config.get_control("OCR READ DELAY", 0.3))

            # Category Change: If 'S' changes the category
            if fuzz.partial_ratio(cat_name, ocr_from_screen(cat_roi, overlay_tool)) < fuzzy_threshold:
                print("Category change detected. Mapping complete.")
                break

    with open(os.path.join(get_base_path(),"item_databases",f"{db_name}.json"), "w") as f:
        json.dump(master_db, f, indent=4)

    return True

def map_flat_grid(db_name, item_roi, overlay_tool=None):
    """
    Maps single-grid menus.
    Assumes starting at (0,0). Includes Vertical Rollover protection.
    """
    master_db = {}
    fuzzy_threshold = 85
    config = ConfigManager()
    gold_db = load_gold_database()

    # Give a waiting period before beginning operations
    print(f"\n--- Initializing {db_name} Mapping ---")
    time.sleep(2)
    focus_hd2_win()
    time.sleep(0.5)

    global_anchor = ocr_from_screen(item_roi, overlay_tool)
    print(f"Starting Flat Map. Global Anchor: {global_anchor}")

    for row in range(35):
        row_anchor = ocr_from_screen(item_roi, overlay_tool)
        col = 0

        while True:
            ocr_item = ocr_from_screen(item_roi, overlay_tool)
            current_item, match_score = canonicalize_item_name(ocr_item, db_name, gold_db)
            if current_item != ocr_item:
                print(f"Gold match: '{ocr_item}' -> '{current_item}' ({match_score}%)")
            if current_item and current_item not in master_db:
                master_db[current_item] = {"pos": [row, col]}
                print(f"Mapped: {current_item} at {row}, {col}")

            pydirectinput.press(config.get_control("RIGHT","d"))
            time.sleep(config.get_control("OCR READ DELAY", 0.3))

            # Have to hardcode the number of columns in the helmet table due to the B01s
            if "B-01" not in row_anchor and fuzz.ratio(row_anchor, ocr_from_screen(item_roi, overlay_tool)) > fuzzy_threshold:
                break
            elif "B-01" in row_anchor and col > 1:
                break
            col += 1

        pydirectinput.press(config.get_control("DOWN","s"))
        time.sleep(config.get_control("OCR READ DELAY", 0.3))

        # Vertical Rollover: Checks if 'S' wrapped us back to the very first item
        if fuzz.ratio(global_anchor, ocr_from_screen(item_roi, overlay_tool)) > fuzzy_threshold:
            print("Vertical Rollover detected. Mapping complete.")
            break

    with open(os.path.join(get_base_path(),"item_databases",f"{db_name}.json"), "w") as f:
        json.dump(master_db, f, indent=4)

    return True

def get_items_by_category(category_name):
    url = "https://helldivers.wiki.gg/api.php"
    headers = {
        "User-Agent": "SEAF Loadout Manager"
    }

    items = []
    category_names = category_name if isinstance(category_name, list) else [category_name]
    for current_category in category_names:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{current_category}",
            "cmtype": "page",
            "cmlimit": "100",
            "format": "json"
        }

        while True:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            items.extend(item["title"].upper() for item in data.get("query", {}).get("categorymembers", []))

            continuation = data.get("continue")
            if not continuation:
                break
            params.update(continuation)

    return list(dict.fromkeys(items))


def construct_gold_db():
    # Construct gold database by fetching items from the Helldivers wiki for each category
    gold_db = {
        db_key: get_items_by_category(category_name)
        for db_key, category_name in GOLD_DB_CATEGORIES.items()
    }

    output_folder = os.path.join(get_base_path(), "item_databases")
    os.makedirs(output_folder, exist_ok=True)
    output_path = os.path.join(output_folder, GOLD_DB_FILE)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(gold_db, f, indent=2, ensure_ascii=False)

    return output_path

def load_gold_database():
    gold_path = os.path.join(get_base_path(), "item_databases", GOLD_DB_FILE)
    try:
        with open(gold_path, "r", encoding="utf-8") as gold_file:
            return json.load(gold_file)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Warning: Wiki database not found or invalid: {gold_path}")
        return {}

def canonicalize_item_name(ocr_name, db_name, gold_db, threshold=75):
    """Return the gold database name when OCR produces a close enough match."""
    if not ocr_name:
        return ocr_name, 0

    candidates = gold_db.get(db_name, [])
    if not candidates:
        return ocr_name, 0

    best_name = ocr_name
    best_score = 0
    target = ocr_name.upper().strip()
    for candidate in candidates:
        score = fuzz.WRatio(target, candidate.upper().strip())
        if score > best_score:
            best_name = candidate
            best_score = score

    if best_score < threshold:
        return ocr_name, best_score
    return best_name, best_score