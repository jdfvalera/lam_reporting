"""
Google Drive entry point for the LAM Reporting Pipeline.

Default short-interval poll:
    python drive_poller/run_drive_agent.py

Manual run-now:
    python drive_poller/run_drive_agent.py --once
"""

import logging
import sys
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv:
    load_dotenv()

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from drive_poller.drive_watcher import main  # noqa: E402


if __name__ == "__main__":
    main()
