import os
import sys
import ctypes
import logging

# 1. Custom Redirector Class
class LogRedirector:
    def __init__(self, logger_level):
        self.logger_level = logger_level

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            if line.strip(): # Avoid logging empty lines
                logging.log(self.logger_level, line.rstrip())

    def flush(self):
        pass

def setup_environment():
    # 2. Hide Console (Safety Net for Windows)
    if os.name == 'nt':
        hWnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hWnd:
            # 0 = SW_HIDE
            ctypes.windll.user32.ShowWindow(hWnd, 0)

    # 3. Configure Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler("helldivers_loadout_manager.log", encoding='utf-8')
        ]
    )

    # 4. Redirect Stdout and Stderr
    sys.stdout = LogRedirector(logging.INFO)
    sys.stderr = LogRedirector(logging.ERROR)

    logging.info("--- ENVIRONMENT INITIALIZED ---")

# Run this immediately upon being imported
setup_environment()

# This tells Windows that this app handles its own scaling
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # Windows 8.1+
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware() # Windows 7/8
    except Exception:
        pass # Fallback for non-Windows or older systems

# Determine the directory where the EXE (or script) is located
if getattr(sys, 'frozen', False):
    # We are running in a PyInstaller bundle
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # We are running in a normal Python environment
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# You can even export this so other files can import it
def get_base_path():
    return BASE_DIR