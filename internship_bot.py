#!/usr/bin/env python3
"""
Production-Ready Automated Internship & Job-Hunting Bot
Single-Workbook Architecture with OpenPyXL persistence, multi-source collection,
resilient scoring, and Gmail SMTP alerts.
"""

import sys
import os
import argparse
import logging

from bot.config import Config
from bot.orchestrator import BotOrchestrator
from bot.security import RedactingFormatter, SecretScrubber

def setup_logging(level_name: str = "INFO") -> SecretScrubber:
    scrubber = SecretScrubber()
    log_level = getattr(logging, level_name.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    formatter = RedactingFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        scrubber=scrubber
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    return scrubber

def parse_args():
    parser = argparse.ArgumentParser(description="Automated Technical Internship Job-Hunting Bot")
    parser.add_argument("--dry-run", action="store_true", help="Run without modifying the Excel workbook or dispatching real emails.")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR).")
    return parser.parse_args()

def main():
    args = parse_args()
    config = Config()
    scrubber = setup_logging(args.log_level)

    logger = logging.getLogger("InternshipBot")
    logger.info("Initializing Production Technical Internship Bot...")

    try:
        orchestrator = BotOrchestrator(config=config, dry_run=args.dry_run)
        report = orchestrator.run()

        logger.info("-------------------- EXECUTION SUMMARY --------------------")
        logger.info(f"Run ID:                 {report.run_id}")
        logger.info(f"Execution Date:         {report.run_date_ist} IST")
        logger.info(f"Total Records Scanned:  {report.total_retrieved}")
        logger.info(f"New Listings Found:     {report.total_new}")
        logger.info(f"Duplicates Skipped:     {report.total_duplicates}")
        logger.info(f"Qualifying Passed:      {report.total_passing_filters}")
        logger.info(f"Workbook Saved:         {'Yes' if report.workbook_saved else 'No/DryRun'}")
        logger.info(f"Email Delivered:        {'Yes' if report.email_sent else 'No/Skipped'}")
        logger.info("-----------------------------------------------------------")

        if report.errors:
            logger.error(f"Completed with {len(report.errors)} errors: {report.errors}")
            return 1

        return 0
    except Exception as e:
        logger.critical(f"Fatal error in bot pipeline: {scrubber.scrub(str(e))}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
