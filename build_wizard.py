import os
import shutil
import subprocess
import sys
from pathlib import Path

ENTRY_POINT: str = 'setup_wizard.py'
APP_NAME: str = 'SEAF_Setup_Wizard'
BASE_DIR: Path = Path(__file__).resolve().parent
BUILD_DIR: Path = BASE_DIR / 'build'
TARGET_DIR: Path = BUILD_DIR / APP_NAME

def run_build() -> None:
    """Builds the SEAF Setup Wizard executable directory using Nuitka.

    Cleans old builds, compiles the setup wizard binary into the build folder,
    and formats the final output directory path.
    """
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)

    command: list[str] = [
        sys.executable,
        '-m',
        'nuitka',
        '--mode=standalone',
        '--assume-yes-for-downloads',
        '--windows-console-mode=disable',
        '--include-windows-runtime-dlls=no',
        '--enable-plugin=tk-inter',
        '--enable-plugin=anti-bloat',
        '--module-parameter=torch-disable-jit=yes',
        # Exclude heavy SciPy submodules
        '--nofollow-import-to=scipy.stats',
        '--nofollow-import-to=scipy.optimize',
        '--nofollow-import-to=scipy.signal',
        '--nofollow-import-to=scipy.integrate',
        '--nofollow-import-to=scipy.fft',
        '--nofollow-import-to=scipy.interpolate',
        '--nofollow-import-to=scipy.cluster',
        '--nofollow-import-to=scipy.io',
        '--nofollow-import-to=scipy.sparse',
        '--nofollow-import-to=scipy.special',
        # Exclude unused PyTorch sub-frameworks
        '--nofollow-import-to=torch.testing',
        '--nofollow-import-to=torch.distributed',
        '--nofollow-import-to=torch.utils.tensorboard',
        '--nofollow-import-to=torch.onnx',
        '--nofollow-import-to=torch.cuda',
        # Exclude Heavy PyTorch dependencies
        '--nofollow-import-to=sympy',
        # Exclude visualization & test suites pulled in by easyocr/opencv
        '--nofollow-import-to=matplotlib',
        '--nofollow-import-to=unittest',
        '--nofollow-import-to=doctest',
        '--low-memory',
        '--jobs=4',
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

    print(f"\n--- {APP_NAME} Build Complete: {TARGET_DIR} ---")

if __name__ == '__main__':
    run_build()