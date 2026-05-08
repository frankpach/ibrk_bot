# run.py
import logging
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from app.db.database import init_db
from app.ibkr.client import IBKRClient
from app.scanner.preprocessor import run_scan
from app.positions.manager import check_positions
from app.config.settings import SCAN_INTERVAL_MINUTES, POSITION_CHECK_MINUTES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Initializing database...")
    init_db()

    logger.info("Connecting to IB Gateway...")
    ib_client = IBKRClient()

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: run_scan(ib_client), "interval", minutes=SCAN_INTERVAL_MINUTES, id="scanner")
    scheduler.add_job(lambda: check_positions(), "interval", minutes=POSITION_CHECK_MINUTES, id="position_manager")
    scheduler.start()
    logger.info(f"Scheduler started - scan every {SCAN_INTERVAL_MINUTES}min, positions every {POSITION_CHECK_MINUTES}min")

    logger.info("Starting FastAPI on 127.0.0.1:8088...")
    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8088, workers=1)


if __name__ == "__main__":
    main()
