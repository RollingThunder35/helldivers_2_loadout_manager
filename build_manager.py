from os.path import exists
import os
import shutil
import PyInstaller.__main__

ENTRY_POINT: str = 'helldivers_loadout_manager_gui.py'
APP_NAME: str = 'SEAF_Loadout_Manager'
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
ICON_PATH: str = os.path.join(BASE_DIR, 'helldivers_super_earth_logo.ico')

def run_build() -> None:
    """Builds the SEAF Loadout Manager executable directory.

    Cleans previous build artifacts and passes parameters to disable UPX compression.
    """
    if exists(rf".\dist\{APP_NAME}"):
        shutil.rmtree(rf".\dist\{APP_NAME}")

    params: list[str] = [
        ENTRY_POINT,
        f'--name={APP_NAME}',
        '--onedir',
        '--noconsole',
        '--noupx',
        f'--icon={ICON_PATH}',
        '--clean'
    ]

    PyInstaller.__main__.run(params)
    print(f"\n--- {APP_NAME} Build Complete ---")
    os.mkdir(rf".\dist\{APP_NAME}\item_databases")
    os.mkdir(rf".\dist\{APP_NAME}\loadouts")
    shutil.copy2(r".\loadouts\gl_medic.json", rf".\dist\{APP_NAME}\loadouts")

if __name__ == '__main__':
    run_build()