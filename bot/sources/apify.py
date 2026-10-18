import time
import logging
from typing import Dict, Any, List, Optional
from .base import BaseSource
from ..models import JobListing
from ..normalizer import normalize_url, generate_fingerprint, parse_date_string

logger = logging.getLogger("InternshipBot.Source.Apify")

class ApifySource(BaseSource):
    """
    Robust Apify Integration.
    Supports official REST API actor invocation (run-sync-get-dataset-items or async polling),
    correct token handling, timeouts, and dataset pagination/capping.
    """

    def __init__(
        self,
        token: str,
        actor_id: str = "scrapio/linkedin-search-jobs-scraper",
        actor_name: str = "Apify-LinkedIn",
        actor_input: Optional[Dict[str, Any]] = None,
        max_items: int = 100,
        enabled: bool = True
    ):
        super().__init__(name=actor_name, enabled=enabled)
        self.token = str(token or "").strip()
        self.actor_id = actor_id
        self.actor_input = actor_input or {}
        self.max_items = min(max_items, 100)  # Max 100 records per run as mandated
        self.scrubber.register_secret(self.token)

    def fetch(self, query: str = "Software Intern") -> List[JobListing]:
        if not self.enabled or not self.token:
            self.stats.source_status = "Skipped"
            self.stats.error_details = "APIFY_TOKEN not configured or source disabled"
            logger.info(f"[{self.name}] Skipped: APIFY_TOKEN not configured.")
            return []

        start_time = time.time()
        # Apify API requires '/' to be replaced by '~' in actor path
        actor_path = self.actor_id.replace('/', '~')
        endpoint = f"https://api.apify.com/v2/acts/{actor_path}/run-sync-get-dataset-items"
        
        # Prepare actor input payload
        payload = dict(self.actor_input)
        if not payload:
            payload = {
                "queries": [f"{query} India"],
                "query": query,
                "location": "India",
                "maxItems": self.max_items,
                "limit": self.max_items
            }

        params = {
            "token": self.token,
            "timeout": 120,
            "memory": 1024,
            "limit": self.max_items
        }

        logger.info(f"[{self.name}] Calling Apify Actor {self.actor_id} (limit={self.max_items})...")
        resp = self.request_with_retry("POST", endpoint, params=params, json=payload, timeout=140)
        self.stats.execution_duration_sec = time.time() - start_time

        if not resp:
            self.stats.source_status = "Failed"
            return []

        try:
            items = resp.json()
            if isinstance(items, dict) and "error" in items:
                err_msg = items.get("error", {}).get("message") or "Unknown Apify error"
                self.stats.error_details = self.scrubber.scrub(err_msg)
                self.stats.source_status = "Failed"
                self.stats.errors += 1
                logger.error(f"[{self.name}] Apify error: {self.stats.error_details}")
                return []

            if not isinstance(items, list):
                self.stats.source_status = "Zero Results"
                return []

            self.stats.records_retrieved = len(items)
            self.stats.source_pagination_info = f"Items fetched: {len(items)}"
            listings: List[JobListing] = []

            for item in items[:self.max_items]:
                if not isinstance(item, dict):
                    continue

                title = (
                    item.get("title") or item.get("jobTitle") or
                    item.get("position") or item.get("job_title") or ""
                ).strip()
                company = (
                    item.get("companyName") or item.get("company") or
                    item.get("employer_name") or item.get("organization") or ""
                ).strip()
                link = normalize_url(
                    item.get("url") or item.get("jobUrl") or item.get("link") or
                    item.get("applyUrl") or item.get("jobDetailsUrl") or ""
                )
                location = (
                    item.get("location") or item.get("jobLocation") or
                    item.get("place") or item.get("city") or "India"
                ).strip()

                if not title or not company:
                    self.stats.records_rejected += 1
                    continue

                desc = str(item.get("description") or item.get("jobDescription") or item.get("snippet") or "").strip()
                post_raw = item.get("postedTime") or item.get("datePosted") or item.get("postedDate")
                posted_date = parse_date_string(post_raw) or ""
                exp_raw = item.get("experience") or item.get("exp") or "0-1 yrs"
                salary_raw = item.get("salary") or item.get("estimatedSalary") or "Not Disclosed"

                skills_raw = item.get("skills") or item.get("keySkills") or []
                skills = [str(s).strip() for s in skills_raw if str(s).strip()] if isinstance(skills_raw, list) else []

                fp = generate_fingerprint(company, title, location)
                job_id = f"APIFY-{item.get('id') or item.get('jobId') or fp}"

                listing = JobListing(
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=desc,
                    posted_date=posted_date,
                    experience=str(exp_raw),
                    salary=str(salary_raw),
                    skills=skills,
                    source=self.name,
                    original_url=link,
                    application_url=link,
                    fingerprint=fp,
                    raw_data=item
                )
                listings.append(listing)

            self.stats.records_parsed = len(listings)
            self.stats.source_status = "Success" if listings else "Zero Results"
            logger.info(f"[{self.name}] Successfully parsed {len(listings)} listings.")
            return listings

        except Exception as e:
            self.stats.source_status = "Failed"
            self.stats.error_details = self.scrubber.scrub(str(e))
            self.stats.errors += 1
            logger.error(f"[{self.name}] Error parsing Apify response: {e}")
            return []
