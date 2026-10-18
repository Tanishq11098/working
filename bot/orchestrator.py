import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Set, Optional

from .models import JobListing, RunReport, SourceExecutionStats
from .config import Config
from .scoring import ScoringEngine
from .storage import ExcelStorageManager
from .notifier import EmailNotifier
from .security import SecretScrubber
from .sources import BaseSource, ApifySource, InternshalaSource, TimesJobsSource, AdzunaSource, JSearchSource

logger = logging.getLogger("InternshipBot.Orchestrator")
IST = timezone(timedelta(hours=5, minutes=30))

class BotOrchestrator:
    """Master orchestrator executing the end-to-end collection, filtering, Excel update, and email."""

    def __init__(self, config: Optional[Config] = None, dry_run: bool = False):
        self.config = config or Config()
        self.dry_run = dry_run
        self.scrubber = SecretScrubber()
        self._register_secrets()

        self.storage = ExcelStorageManager(filepath=self.config.excel_filename)
        self.scoring_engine = ScoringEngine(strict_location=self.config.strict_location)
        self.notifier = EmailNotifier(
            sender=self.config.gmail_address,
            password=self.config.gmail_password,
            recipient=self.config.email_to,
            scrubber=self.scrubber
        )

    def _register_secrets(self) -> None:
        for s in [
            self.config.gmail_password,
            self.config.gmail_address,
            self.config.apify_token,
            self.config.adzuna_app_id,
            self.config.adzuna_app_key,
            self.config.jsearch_api_key
        ]:
            if s:
                self.scrubber.register_secret(s)

    def _build_sources(self) -> List[BaseSource]:
        """Constructs list of active source adapters."""
        sources: List[BaseSource] = []

        # 1. Apify LinkedIn
        sources.append(ApifySource(
            token=self.config.apify_token,
            actor_id=self.config.apify_actor_id,
            actor_name="Apify-LinkedIn",
            max_items=self.config.apify_max_items,
            enabled=bool(self.config.apify_token)
        ))

        # 2. Portals (Direct HTML)
        sources.append(InternshalaSource(enabled=True))
        sources.append(TimesJobsSource(enabled=True))

        # 3. Optional APIs
        sources.append(AdzunaSource(
            app_id=self.config.adzuna_app_id,
            app_key=self.config.adzuna_app_key,
            enabled=bool(self.config.adzuna_app_id and self.config.adzuna_app_key)
        ))
        sources.append(JSearchSource(
            rapidapi_key=self.config.jsearch_api_key,
            enabled=bool(self.config.jsearch_api_key)
        ))

        return sources

    def run(self) -> RunReport:
        run_id = f"RUN-{datetime.now(IST).strftime('%Y%m%d-%H%M%S')}"
        now_ist = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
        report = RunReport(run_id=run_id, run_date_ist=now_ist)

        logger.info(f"========== Starting Internship Bot Run: {run_id} ({now_ist} IST) ==========")
        self.config.log_status()

        sources = self._build_sources()
        all_new_listings: List[JobListing] = []
        source_stats_list: List[SourceExecutionStats] = []
        seen_in_this_run: Set[str] = set()

        for source in sources:
            source.stats.run_id = run_id
            source.stats.run_datetime_ist = now_ist
            logger.info(f"--> Executing source: {source.name}...")

            raw_listings: List[JobListing] = []
            try:
                # Query source with representative target roles
                for q in self.config.queries[:2]:  # Query top keywords
                    batch = source.fetch(query=q)
                    raw_listings.extend(batch)
            except Exception as e:
                err_msg = self.scrubber.scrub(str(e))
                logger.error(f"Source {source.name} unhandled error: {err_msg}", exc_info=False)
                source.stats.errors += 1
                source.stats.error_details = err_msg
                source.stats.source_status = "Failed"

            source.stats.records_retrieved = len(raw_listings)
            report.total_retrieved += len(raw_listings)

            source_passing: List[JobListing] = []
            for item in raw_listings:
                key = item.job_id or item.fingerprint or item.original_url
                if key in seen_in_this_run:
                    source.stats.duplicate_listings += 1
                    report.total_duplicates += 1
                    continue

                if self.storage.is_duplicate(item):
                    source.stats.duplicate_listings += 1
                    report.total_duplicates += 1
                    continue

                seen_in_this_run.add(key)
                source.stats.new_listings += 1
                report.total_new += 1

                # Apply scoring & hard eligibility filters
                passed = self.scoring_engine.evaluate(item)
                if passed:
                    source.stats.listings_passing_filters += 1
                    report.total_passing_filters += 1
                    source_passing.append(item)
                    all_new_listings.append(item)
                else:
                    source.stats.records_rejected += 1

            if source.stats.source_status == "Pending":
                source.stats.source_status = "Success" if source.stats.records_retrieved > 0 else "Zero Results"

            report.sources[source.name] = source.stats
            source_stats_list.append(source.stats)
            logger.info(f"[{source.name}] Finished: {source.stats.records_retrieved} retrieved, {source.stats.listings_passing_filters} passed filters.")

        # Sort all new qualifying listings descending by match score
        all_new_listings.sort(key=lambda x: x.match_score, reverse=True)

        # 4. Update the single master Excel workbook
        if not self.dry_run:
            logger.info(f"Updating single master workbook: {self.config.excel_filename}...")
            saved = self.storage.update_workbook(
                new_listings=all_new_listings,
                source_stats=source_stats_list,
                tracker_threshold=self.config.tracker_score_threshold
            )
            report.workbook_saved = saved

            # Validate saved workbook
            valid, reason = self.storage.validate_workbook()
            if not valid:
                logger.critical(f"CRITICAL: Workbook validation failed: {reason}")
                report.errors.append(reason)
            else:
                logger.info("Workbook validated successfully with all 4 worksheets.")

            # 5. Email Notification
            if self.notifier.is_configured():
                logger.info("Dispatching daily email digest with master workbook...")
                sent = self.notifier.send_digest(report, all_new_listings, self.config.excel_filename)
                report.email_sent = sent
                if sent:
                    notified_ids = {item.job_id for item in all_new_listings}
                    self.storage.mark_notified(notified_ids)
            else:
                logger.info("Email delivery skipped (GMAIL credentials not set).")
        else:
            logger.info("Dry-run requested: skipped Excel write and email dispatch.")

        logger.info(f"========== Bot Run Completed: {report.total_passing_filters} Qualifying Listings ==========")
        return report
