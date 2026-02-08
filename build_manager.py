from os.path import exists

import PyInstaller.__main__
import os
import shutil

# Configuration
ENTRY_POINT = 'helldivers_loadout_manager_gui.py'
APP_NAME = 'SEAF_Loadout_Manager'
ICON_PATH = r'D:\Python Projects\helldivers_2_loadout_manager\helldivers_super_earth_logo.ico' # Ensure you converted your PNG to ICO

# Clear out original build
if exists(fr".\dist\{APP_NAME}"):
    shutil.rmtree(fr".\dist\{APP_NAME}")

params = [
    ENTRY_POINT,
    '--name=' + APP_NAME,
    '--onedir',           # Best for performance with EasyOCR
    '--noconsole',        # Silent operation
    '--icon=' + ICON_PATH,
    '--clean'
]

if __name__ == '__main__':
    PyInstaller.__main__.run(params)
    print(f"\n--- {APP_NAME} Build Complete ---")
    os.mkdir(fr".\dist\{APP_NAME}\item_databases")
    os.mkdir(fr".\dist\{APP_NAME}\loadouts")