from gui.app import App
import logging
import sys
import os
import platform
from pathlib import Path

def get_log_file() -> Path:
    if platform.system() == "Windows":
        local_appdata = os.getenv('LOCALAPPDATA')
        log_dir = Path(local_appdata) if local_appdata else Path.home()
    elif platform.system() == "Darwin":
        log_dir = Path.home() / "Library" / "Logs" / "YouSync"
    else:
        log_dir = Path.home() / ".cache" / "yousync"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "yousync.log"

log_file = get_log_file()

if os.path.exists(log_file):
    os.remove(log_file)

# Configure logging
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filemode='w'
)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        logging.error(f"Exception occurred: {e}")
