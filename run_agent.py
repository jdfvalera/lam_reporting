"""
LAM Reporting Agent
===================
Drop campaign files into the inbox and the agent processes them automatically,
writing outputs into the same campaign folder as the source files.

Folder structure:
    inbox/
      {Brand}/                       ← brand key folder
        {CampaignFolder}/            ← W{N}, W{N}_{CampaignType}, etc.
          weekly.xlsx
          frequency.xlsx
          ft.xlsx
          gs.xlsx                    (Redner's only, optional)

Brand keys:
    USM | Redners | McCaffreys | Bottlemart | Wrays | Repco | Detwilers | Foodtown

Campaign folder examples:
    29_W30        →  report 29, week 30
    29_W30_Weekly →  report 29, week 30, campaign type Weekly
    25_Sale       →  report 25, Sale campaign
    FY26 Period 3 →  full name used as label and campaign type

Full examples:
    inbox/McCaffreys/29_W30_Weekly/
    inbox/USM/FY26 Period 3 Week 3/
    inbox/Redners/29_W78/
    inbox/Foodtown/Month 1/W1/

Run:
    python run_agent.py
"""

import logging
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
INBOX    = BASE_DIR / "inbox"

INBOX.mkdir(exist_ok=True)

import time

from agent.watcher import start_watcher  # noqa: E402 — after path setup


def main() -> None:
    log.info("LAM Reporting Agent starting...")
    log.info(f"Inbox → {INBOX}")
    time.sleep(3)  # let macOS settle file handles before scanning

    observer = start_watcher(INBOX)

    def _shutdown(sig, frame):
        log.info("Shutting down...")
        observer.stop()
        observer.join()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("Watching inbox/ for campaigns. Press Ctrl+C to stop.")
    observer.join()


if __name__ == "__main__":
    main()
