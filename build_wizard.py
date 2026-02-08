import PyInstaller.__main__
import os

# Configuration
ENTRY_POINT = 'setup_wizard.py'
APP_NAME = 'SEAF_Setup_Wizard'
ICON_PATH = 'D:\Python Projects\helldivers_2_loadout_manager\helldivers_super_earth_logo.ico' # Ensure you converted your PNG to ICO

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