"""
LAM Reporting Agent
===================
Drop campaign files into the inbox and the agent processes them automatically,
writing outputs to the output folder.

Folder structure:
    inbox/
      {Brand}/                       ← brand key folder
        {CampaignFolder}/            ← W{N}, W{N}_{CampaignType}, or {Client}_W{N}_...
          weekly.xlsx
          frequency.xlsx
          ft.xlsx
          gs.xlsx                    (Redner's only, optional)

    output/
      {Brand}/
        {CampaignFolder}/
          ({R}) {Client} {dates}.xlsx
          {Client}_Internal_Raw_File_for_CS.xlsx

Brand keys:
    USM | Redners | McCaffreys | Bottlemart | Wrays | Repco | Detwilers | Foodtown

Campaign folder examples:
    W8_Sale_R8            →  week 8, Sale campaign, report 8
    W12_Weekly            →  week 12, Weekly campaign
    W3_Promo              →  week 3, Promo campaign
    W6                    →  week 6, no campaign type
    MyClient_W8_Sale      →  explicit client name "MyClient"

Full examples:
    inbox/McCaffreys/W8_Sale_R8/
    inbox/USM/W12_Weekly/
    inbox/Bottlemart/W3_Promo/
    inbox/Redners/W6/

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
OUTPUT   = BASE_DIR / "output"

INBOX.mkdir(exist_ok=True)
OUTPUT.mkdir(exist_ok=True)

from agent.watcher import start_watcher  # noqa: E402 — after path setup


def main() -> None:
    log.info("LAM Reporting Agent starting...")
    log.info(f"Inbox  → {INBOX}")
    log.info(f"Output → {OUTPUT}")

    observer = start_watcher(INBOX, OUTPUT)

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
