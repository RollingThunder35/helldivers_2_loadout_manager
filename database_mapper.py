import json
import os.path
import time

# noinspection PyPackageRequirements
import cv2
import easyocr
import numpy as np
import pyautogui
import pydirectinput
from thefuzz import fuzz

from environment_setup import get_base_path
from utils import ConfigurationError, focus_hd2_win, ConfigManager

# Activate failsafe
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

# Initialize the reader once (set gpu=True if you have an NVIDIA GPU)
reader = easyocr.Reader(['en'], gpu=False, verbose=False)


def ocr_from_screen(roi_coords, save_str=None):
    """
    roi_coords: (left, top, width, height)
    """
    # 1. Validation Check
    if not roi_coords or any(v <= 0 for v in roi_coords[2:]):
        raise ConfigurationError(f"Invalid ROI: {roi_coords}. Please re-run the Setup Wizard.")

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
        "OFFENSIUE": "OFFENSIVE", "DEFENSIUE": "DEFENSIVE", "SERUO": "SERVO"
    }

    for error, correction in font_corrections.items():
        text = text.replace(error, correction)

    # DEBUG: Save the frame directly.
    # if save_str:
    #     print(f"Saving saving debug photo {save_str}.")
    #     cv2.imwrite(f"debug_ocr_region_{save_str}.png", frame)

    return text

def map_categorized_grid(db_name, item_roi, cat_roi, category_list, perk_roi=None):
    """
    Maps menus with tabs (e.g., Offensive, Defensive).
    Assumes starting at (0,0) in the first category.
    """
    master_db = {}
    fuzzy_threshold = 95
    config = ConfigManager()

    # Give a waiting period before beginning operations
    print(f"\n--- Initializing {db_name} Mapping ---")
    time.sleep(2)
    focus_hd2_win()
    time.sleep(.5)

    for cat_name in category_list:
        print(f"Mapping Category: {cat_name}")

        # Ensure we are in the right tab
        while True:
            current_tab = ocr_from_screen(cat_roi)
            print(f"Have {current_tab} and want {cat_name}")
            if fuzz.partial_ratio(cat_name.upper(), current_tab.upper()) > fuzzy_threshold:
                break
            pydirectinput.press(config.get_control("MENU TAB RIGHT","c"))
            time.sleep(0.5)

        for row in range(35):
            row_anchor = ocr_from_screen(item_roi)
            col = 0

            while True:
                current_item = ocr_from_screen(item_roi)
                current_passive = ocr_from_screen(perk_roi) if perk_roi != (0,0,0,0) and perk_roi is not None else None
                if current_item and current_item not in master_db:
                    master_db[current_item] = {"cat": cat_name, "pos": [row, col]}
                    # For armor specifically, we will map the passive to make it easier to search through
                    if current_passive:
                        master_db[current_item]["passive"] = current_passive
                        print(f"Passive found: {current_passive}")
                    print(f"[{cat_name}] Mapped: {current_item} at {row}, {col}")

                pydirectinput.press(config.get_control("RIGHT","d"))
                time.sleep(0.5)

                # Have to hardcode the number of columns in the armor table due to the B01s
                if "B-01" not in row_anchor and fuzz.ratio(row_anchor, ocr_from_screen(item_roi)) > fuzzy_threshold:
                    break
                elif "B-01" in row_anchor and col > 1:
                    break
                col += 1

            pydirectinput.press(config.get_control("DOWN","s"))
            time.sleep(0.5)

            # Category Change: If 'S' changes the category
            if fuzz.partial_ratio(cat_name, ocr_from_screen(cat_roi)) < fuzzy_threshold:
                print("Category change detected. Mapping complete.")
                break

    with open(os.path.join(get_base_path(),"item_databases",f"{db_name}.json"), "w") as f:
        json.dump(master_db, f, indent=4)

    return True

def map_flat_grid(db_name, item_roi):
    """
    Maps single-grid menus.
    Assumes starting at (0,0). Includes Vertical Rollover protection.
    """
    master_db = {}
    fuzzy_threshold = 85
    config = ConfigManager()

    # Give a waiting period before beginning operations
    print(f"\n--- Initializing {db_name} Mapping ---")
    time.sleep(2)
    focus_hd2_win()
    time.sleep(.5)

    global_anchor = ocr_from_screen(item_roi)
    print(f"Starting Flat Map. Global Anchor: {global_anchor}")

    for row in range(35):
        row_anchor = ocr_from_screen(item_roi)
        col = 0

        while True:
            current_item = ocr_from_screen(item_roi)
            if current_item and current_item not in master_db:
                master_db[current_item] = {"pos": [row, col]}
                print(f"Mapped: {current_item} at {row}, {col}")

            pydirectinput.press(config.get_control("RIGHT","d"))
            time.sleep(0.5)

            # Have to hardcode the number of columns in the helmet table due to the B01s
            if "B-01" not in row_anchor and fuzz.ratio(row_anchor, ocr_from_screen(item_roi)) > fuzzy_threshold:
                break
            elif "B-01" in row_anchor and col > 1:
                break
            col += 1

        pydirectinput.press(config.get_control("DOWN","s"))
        time.sleep(0.5)

        # Vertical Rollover: Checks if 'S' wrapped us back to the very first item
        if fuzz.ratio(global_anchor, ocr_from_screen(item_roi)) > fuzzy_threshold:
            print("Vertical Rollover detected. Mapping complete.")
            break

    with open(os.path.join(get_base_path(),"item_databases",f"{db_name}.json"), "w") as f:
        json.dump(master_db, f, indent=4)

    return True