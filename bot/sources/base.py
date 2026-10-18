import time
import logging
import requests
from typing import Dict, Any, List, Optional
from ..models import SourceExecutionStats, JobListing
from ..security import SecretScrubber

logger = logging.getLogger("InternshipBot.Source")

class BaseSource:
    """Base class for all job and internship collectors."""

    def __init__(self, name: str, enabled: bool = True, timeout: int = 30, scrubber: Optional[SecretScrubber] = None):
        self.name = name
        self.enabled = enabled
        self.timeout = timeout
        self.scrubber = scrubber or SecretScrubber()
        self.stats = SourceExecutionStats(
            run_id="",
            run_datetime_ist="",
            source_name=name,
            source_status="Enabled" if enabled else "Skipped"
        )
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
            "Accept-Language": "en-US,en;q=0.9,en-IN;q=0.8"
        })
        return session

    def request_with_retry(self, method: str, url: str, max_retries: int = 3, **kwargs) -> Optional[requests.Response]:
        """Perform request with bounded exponential backoff for rate limits and errors."""
        kwargs.setdefault("timeout", self.timeout)
        delay = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.request(method, url, **kwargs)
                if resp.status_code == 429:
                    wait = float(resp.headers.get("Retry-After", delay))
                    logger.warning(f"[{self.name}] Rate limited (429). Retrying in {wait:.1f}s...")
                    time.sleep(wait)
                    delay *= 2
                    continue
                if resp.status_code in (500, 502, 503, 504):
                    logger.warning(f"[{self.name}] Server error ({resp.status_code}). Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    delay *= 2
                    continue

                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                msg = self.scrubber.scrub(str(e))
                if attempt == max_retries:
                    logger.error(f"[{self.name}] Request failed after {max_retries} attempts: {msg}")
                    self.stats.error_details = msg
                    self.stats.errors += 1
                    return None
                time.sleep(delay)
                delay *= 2

        return None

    def fetch(self, query: str = "intern") -> List[JobListing]:
        """Subclasses implement fetch."""
        raise NotImplementedError
