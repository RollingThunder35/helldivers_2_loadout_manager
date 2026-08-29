import os
import PyInstaller.__main__

ENTRY_POINT: str = 'setup_wizard.py'
APP_NAME: str = 'SEAF_Setup_Wizard'
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
ICON_PATH: str = os.path.join(BASE_DIR, 'helldivers_super_earth_logo.ico')

def run_build() -> None:
    """Builds the SEAF Setup Wizard executable directory.

    Applies non-compressed flags to avoid trigger matching on antivirus scanners.
    """
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

if __name__ == '__main__':
    run_build()