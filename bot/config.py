import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("InternshipBot.Config")

DEFAULT_QUERIES = [
    "Software Engineer Intern",
    "Python Developer Intern",
    "Frontend Developer Intern",
    "Backend Developer Intern",
    "Data Analyst Intern",
    "Machine Learning Intern"
]

class Config:
    """Central configuration for bot credentials, limits, and runtime flags."""

    def __init__(self):
        # Mandatory / Core Email Credentials
        self.gmail_address: str = os.getenv("GMAIL_ADDRESS") or os.getenv("EMAIL", "")
        self.gmail_password: str = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("PASSWORD", "")
        self.email_to: str = os.getenv("EMAIL_TO") or self.gmail_address

        # Apify Credentials
        self.apify_token: str = (
            os.getenv("APIFY_API_TOKEN") or
            os.getenv("APIFY_TOKEN") or
            os.getenv("APIFY_KEY") or ""
        )
        self.apify_actor_id: str = os.getenv("APIFY_ACTOR_ID", "scrapio/linkedin-search-jobs-scraper")
        self.apify_max_items: int = int(os.getenv("APIFY_MAX_ITEMS", "100"))

        # Optional Job Portal APIs
        self.adzuna_app_id: str = os.getenv("ADZUNA_APP_ID", "")
        self.adzuna_app_key: str = os.getenv("ADZUNA_APP_KEY", "")
        self.jsearch_api_key: str = os.getenv("JSEARCH_API_KEY") or os.getenv("RAPIDAPI_KEY", "")

        # Operational Settings & Thresholds
        self.strict_location: bool = os.getenv("STRICT_LOCATION", "true").lower() in ("true", "1", "yes")
        self.excel_filename: str = os.getenv("EXCEL_FILENAME", "internships.xlsx")
        self.tracker_score_threshold: int = int(os.getenv("TRACKER_SCORE_THRESHOLD", "60"))
        self.api_record_cap: int = int(os.getenv("API_RECORD_CAP", "100"))
        self.queries: List[str] = DEFAULT_QUERIES

    def log_status(self) -> None:
        """Logs loaded configuration state safely without exposing secret values."""
        logger.info("------------- CONFIGURATION STATUS -------------")
        logger.info(f"Target Excel File:     {self.excel_filename}")
        logger.info(f"Strict Location:       {self.strict_location}")
        logger.info(f"Apify Configured:      {'Yes' if bool(self.apify_token) else 'No'}")
        logger.info(f"Adzuna Configured:     {'Yes' if bool(self.adzuna_app_id and self.adzuna_app_key) else 'No'}")
        logger.info(f"JSearch Configured:    {'Yes' if bool(self.jsearch_api_key) else 'No'}")
        logger.info(f"Email Configured:      {'Yes' if bool(self.gmail_address and self.gmail_password) else 'No'}")
        logger.info("------------------------------------------------")
