import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_ROOT / "logs"
EXPORTS_DIR = Path(tempfile.gettempdir()) / "proxy_api_static"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
