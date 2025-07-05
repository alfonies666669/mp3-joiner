import os
import json
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.environ.get("LOG_DIR", "./logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

# --- App logger ---
app_logger = logging.getLogger("app")
app_handler = RotatingFileHandler(os.path.join(LOG_DIR, "app.log"), maxBytes=10 * 1024 * 1024, backupCount=5)
app_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
app_handler.setFormatter(app_formatter)
app_logger.addHandler(app_handler)
app_logger.setLevel(logging.INFO)
app_logger.propagate = False


# --- User logger (JSON, only if path set) ---
class JsonFileHandler(logging.FileHandler):
    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.stream.write(log_entry + "\n")
            self.flush()
        except Exception:
            self.handleError(record)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "extra"):
            data.update(record.extra)
        return json.dumps(data, ensure_ascii=False)


def get_user_logger():
    base_path = os.environ.get("USER_LOG_PATH")
    if not base_path:
        return None
    log_file_path = os.path.join(base_path, "user_actions.json") if os.path.isdir(base_path) else base_path
    logger = logging.getLogger("user_actions")
    if not logger.handlers:
        try:
            handler = JsonFileHandler(log_file_path)
            formatter = JsonFormatter()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
        except Exception as e:
            print(f"Failed to setup user logger: {e}")
            return None
    return logger


user_logger = get_user_logger()

if user_logger is not None:
    user_logger.propagate = False
