import time
import logging
import urllib.parse
from typing import List
from bs4 import BeautifulSoup

from .base import BaseSource
from ..models import JobListing
from ..normalizer import normalize_url, generate_fingerprint, parse_date_string

logger = logging.getLogger("InternshipBot.Source.Portals")

class InternshalaSource(BaseSource):
    """Direct scraper for Internshala with graceful degradation on anti-bot."""
    def __init__(self, enabled: bool = True):
        super().__init__(name="Internshala", enabled=enabled)

    def fetch(self, query: str = "python developer") -> List[JobListing]:
        if not self.enabled:
            self.stats.source_status = "Skipped"
            return []

        start_time = time.time()
        slug = urllib.parse.quote_plus(query.replace(" ", "-"))
        url = f"https://internshala.com/internships/keywords-{slug}"

        resp = self.request_with_retry("GET", url)
        self.stats.execution_duration_sec = time.time() - start_time

        if not resp or resp.status_code != 200:
            self.stats.source_status = "Failed" if resp else "Connection Error"
            return []

        listings: List[JobListing] = []
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div.individual_internship") or soup.select("div[class*='internship_meta']")
        self.stats.records_retrieved = len(cards)

        for card in cards:
            try:
                title_el = (
                    card.select_one("a.job-title-href") or
                    card.select_one("h2.job-internship-name a") or
                    card.select_one("a[id='job_title']") or
                    card.select_one("a.view_detail_button") or
                    card.select_one("h3 > a")
                )
                comp_el = (
                    card.select_one("p.company-name") or
                    card.select_one("p.company_name") or
                    card.select_one("div.company_name") or
                    card.select_one("a.link_display_like_text")
                )
                loc_el = (
                    card.select_one("div.row-1-item.locations span a") or
                    card.select_one("div.row-1-item.locations span") or
                    card.select_one("div.locations") or
                    card.select_one("span.location_link")
                )
                desc_el = card.select_one("div.about_job div.text") or card.select_one("div.text")

                if not title_el or not comp_el:
                    self.stats.records_rejected += 1
                    continue

                title = title_el.get_text(strip=True)
                company = comp_el.get_text(strip=True)
                location = loc_el.get_text(strip=True) if loc_el else "Delhi NCR"
                href = title_el.get("href") or card.get("data-href") or ""
                full_url = normalize_url(urllib.parse.urljoin("https://internshala.com", href))
                description = desc_el.get_text(strip=True) if desc_el else ""

                fp = generate_fingerprint(company, title, location)
                listing = JobListing(
                    job_id=f"ISHALA-{fp}",
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    source="Internshala",
                    original_url=full_url,
                    application_url=full_url,
                    fingerprint=fp
                )
                listings.append(listing)
            except Exception:
                self.stats.records_rejected += 1
                continue

        self.stats.records_parsed = len(listings)
        self.stats.source_status = "Success" if listings else "Zero Results"
        return listings


class TimesJobsSource(BaseSource):
    """Direct scraper for TimesJobs."""
    def __init__(self, enabled: bool = True):
        super().__init__(name="TimesJobs", enabled=enabled)

    def fetch(self, query: str = "python intern") -> List[JobListing]:
        if not self.enabled:
            self.stats.source_status = "Skipped"
            return []

        start_time = time.time()
        url = (
            f"https://www.timesjobs.com/candidate/job-search.html"
            f"?searchType=personal498&from=submit&txtKeywords={urllib.parse.quote_plus(query)}&txtLocation="
        )
        resp = self.request_with_retry("GET", url, verify=False)
        self.stats.execution_duration_sec = time.time() - start_time

        if not resp or resp.status_code != 200:
            self.stats.source_status = "Failed" if resp else "Connection Error"
            return []

        listings: List[JobListing] = []
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("li.clearfix.job-bx") or soup.select("div.job-container")
        self.stats.records_retrieved = len(cards)

        for card in cards:
            try:
                title_el = card.select_one("h2 > a") or card.select_one("h3 > a")
                comp_el = card.select_one("h3.joblist-comp-name") or card.select_one("span.joblist-comp-name")
                loc_el = card.select_one("ul.top-jd-dtl li span") or card.select_one("span[title]")

                if not title_el or not comp_el:
                    self.stats.records_rejected += 1
                    continue

                title = title_el.get_text(strip=True)
                company = comp_el.get_text(strip=True)
                location = loc_el.get_text(strip=True) if loc_el else "Delhi NCR"
                href = title_el.get("href", "")
                link = normalize_url(href)

                fp = generate_fingerprint(company, title, location)
                listing = JobListing(
                    job_id=f"TJ-{fp}",
                    title=title,
                    company=company,
                    location=location,
                    source="TimesJobs",
                    original_url=link,
                    application_url=link,
                    fingerprint=fp
                )
                listings.append(listing)
            except Exception:
                self.stats.records_rejected += 1
                continue

        self.stats.records_parsed = len(listings)
        self.stats.source_status = "Success" if listings else "Zero Results"
        return listings
