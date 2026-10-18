import time
import logging
import urllib.parse
from typing import List, Optional
from .base import BaseSource
from ..models import JobListing
from ..normalizer import normalize_url, generate_fingerprint

logger = logging.getLogger("InternshipBot.Source.APIs")

class AdzunaSource(BaseSource):
    """Optional Adzuna Jobs API (India)."""
    def __init__(self, app_id: Optional[str], app_key: Optional[str], enabled: bool = True):
        super().__init__(name="Adzuna", enabled=enabled)
        self.app_id = str(app_id or "").strip()
        self.app_key = str(app_key or "").strip()
        self.scrubber.register_secret(self.app_id)
        self.scrubber.register_secret(self.app_key)

    def fetch(self, query: str = "software developer intern") -> List[JobListing]:
        if not self.enabled or not self.app_id or not self.app_key:
            self.stats.source_status = "Skipped"
            self.stats.error_details = "ADZUNA credentials not configured"
            return []

        start_time = time.time()
        url = (
            f"https://api.adzuna.com/v1/api/jobs/in/search/1"
            f"?app_id={self.app_id}&app_key={self.app_key}&results_per_page=50&what={urllib.parse.quote_plus(query)}"
            f"&where=India&content-type=application/json"
        )
        resp = self.request_with_retry("GET", url)
        self.stats.execution_duration_sec = time.time() - start_time

        if not resp or resp.status_code != 200:
            self.stats.source_status = "Failed" if resp else "Connection Error"
            return []

        listings: List[JobListing] = []
        try:
            data = resp.json().get("results", [])
            self.stats.records_retrieved = len(data)
            for item in data:
                title = item.get("title", "")
                company = item.get("company", {}).get("display_name", "")
                location = item.get("location", {}).get("display_name", "India")
                link = normalize_url(item.get("redirect_url", ""))
                desc = item.get("description", "")
                job_id = f"ADZ-{item.get('id', '')}"

                if title and company and link:
                    fp = generate_fingerprint(company, title, location)
                    listings.append(JobListing(
                        job_id=job_id or f"ADZ-{fp}",
                        title=title,
                        company=company,
                        location=location,
                        source="Adzuna",
                        original_url=link,
                        application_url=link,
                        description=desc,
                        fingerprint=fp
                    ))
                else:
                    self.stats.records_rejected += 1

            self.stats.records_parsed = len(listings)
            self.stats.source_status = "Success" if listings else "Zero Results"
            return listings
        except Exception as e:
            self.stats.source_status = "Failed"
            self.stats.error_details = self.scrubber.scrub(str(e))
            self.stats.errors += 1
            return []


class JSearchSource(BaseSource):
    """Optional JSearch API via RapidAPI."""
    def __init__(self, rapidapi_key: Optional[str], enabled: bool = True):
        super().__init__(name="JSearch", enabled=enabled)
        self.rapidapi_key = str(rapidapi_key or "").strip()
        self.scrubber.register_secret(self.rapidapi_key)

    def fetch(self, query: str = "software intern") -> List[JobListing]:
        if not self.enabled or not self.rapidapi_key:
            self.stats.source_status = "Skipped"
            self.stats.error_details = "RAPIDAPI_KEY not configured"
            return []

        start_time = time.time()
        url = "https://jsearch.p.rapidapi.com/search"
        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }
        params = {"query": f"{query} in India", "page": "1", "num_pages": "1", "date_posted": "week"}
        resp = self.request_with_retry("GET", url, headers=headers, params=params)
        self.stats.execution_duration_sec = time.time() - start_time

        if not resp or resp.status_code != 200:
            self.stats.source_status = "Failed" if resp else "Connection Error"
            return []

        listings: List[JobListing] = []
        try:
            data = resp.json().get("data", [])
            self.stats.records_retrieved = len(data)
            for item in data:
                title = item.get("job_title", "")
                company = item.get("employer_name", "")
                location = item.get("job_city") or item.get("job_country") or "India"
                link = normalize_url(item.get("job_apply_link") or item.get("job_google_link", ""))
                desc = item.get("job_description", "")
                job_id = f"JSEARCH-{item.get('job_id', '')}"

                if title and company and link:
                    fp = generate_fingerprint(company, title, location)
                    listings.append(JobListing(
                        job_id=job_id or f"JS-{fp}",
                        title=title,
                        company=company,
                        location=location,
                        source="JSearch",
                        original_url=link,
                        application_url=link,
                        description=desc,
                        fingerprint=fp
                    ))
                else:
                    self.stats.records_rejected += 1

            self.stats.records_parsed = len(listings)
            self.stats.source_status = "Success" if listings else "Zero Results"
            return listings
        except Exception as e:
            self.stats.source_status = "Failed"
            self.stats.error_details = self.scrubber.scrub(str(e))
            self.stats.errors += 1
            return []
