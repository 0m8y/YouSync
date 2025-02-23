from gui.app import App
import logging
import sys
import os

local_appdata = os.getenv('LOCALAPPDATA')
log_file = os.path.join(local_appdata, 'yousync.log')

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
