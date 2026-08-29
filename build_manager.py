import os
import shutil
import subprocess
import sys
from pathlib import Path

ENTRY_POINT: str = 'helldivers_loadout_manager_gui.py'
APP_NAME: str = 'SEAF_Loadout_Manager'
BASE_DIR: Path = Path(__file__).resolve().parent
BUILD_DIR: Path = BASE_DIR / 'build'
TARGET_DIR: Path = BUILD_DIR / APP_NAME

def run_build() -> None:
    """Builds the SEAF Loadout Manager executable directory using Nuitka.

    Cleans previous build artifacts in the build directory, compiles Nuitka output,
    renames the default distribution folder, and sets up asset subdirectories.
    """
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)

    command: list[str] = [
        sys.executable,
        '-m',
        'nuitka',
        '--mode=standalone',
        '--assume-yes-for-downloads',
        '--include-windows-runtime-dlls=no',
        '--windows-console-mode=disable',
        '--enable-plugin=tk-inter',
        '--enable-plugin=anti-bloat',
        '--module-parameter=torch-disable-jit=yes',
        '--low-memory',
        '--jobs=8',
        '--show-progress',
        f'--windows-icon-from-ico={BASE_DIR / "helldivers_super_earth_logo.ico"}',
        f'--output-dir={BUILD_DIR}',
        f'--output-filename={APP_NAME}.exe',
        ENTRY_POINT
    ]

    subprocess.run(command, check=True)

    # Rename default Nuitka output directory inside ./build to the requested APP_NAME
    default_output: Path = BUILD_DIR / f"{Path(ENTRY_POINT).stem}.dist"
    if default_output.exists() and default_output != TARGET_DIR:
        default_output.rename(TARGET_DIR)

    # Populate application subfolders and default files
    (TARGET_DIR / 'item_databases').mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / 'loadouts').mkdir(parents=True, exist_ok=True)
    shutil.copy2(BASE_DIR / 'loadouts' / 'gl_medic.json', TARGET_DIR / 'loadouts')

    print(f"\n--- {APP_NAME} Build Complete: {TARGET_DIR} ---")

if __name__ == '__main__':
    run_build()