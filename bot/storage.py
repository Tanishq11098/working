import os
import shutil
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Set, Tuple, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import JobListing, SourceExecutionStats
from .security import sanitize_for_spreadsheet, validate_url
from .normalizer import normalize_url, generate_fingerprint

logger = logging.getLogger("InternshipBot.Storage")
IST = timezone(timedelta(hours=5, minutes=30))

EXCEL_FILENAME = "internships.xlsx"

SHEET_ALL_LISTINGS = "All Listings"
SHEET_SOURCE_STATS = "Source Stats"
SHEET_SEEN_LISTINGS = "seen_listings"
SHEET_TRACKER = "Tracker"

ALL_LISTINGS_HEADERS = [
    "Job ID", "Job Title", "Company", "Location", "Work Mode",
    "Job Type", "Experience Required", "Salary or Stipend", "Description",
    "Required Skills", "Eligibility", "Posted Date", "Deadline",
    "Source", "Original Job URL", "Application URL", "Date Discovered",
    "Date Last Verified", "Match Score", "Match Reasons", "Application Status"
]

SOURCE_STATS_HEADERS = [
    "Run ID", "Run Date and Time in IST", "Source Name", "Source Status",
    "Records Retrieved", "Records Parsed", "Records Rejected", "New Listings",
    "Duplicate Listings", "Listings Passing Filters", "Errors", "Error Details",
    "Execution Duration (s)", "API Usage / Credits", "Pagination Info"
]

SEEN_LISTINGS_HEADERS = [
    "Stable Listing ID", "Canonical Job URL", "Job Title", "Company",
    "Source", "First Seen Date", "Last Seen Date", "Last Notified Date"
]

TRACKER_HEADERS = [
    "Job ID", "Job Title", "Company", "Location", "Application URL",
    "Date Added", "Application Status", "Application Date", "Follow-up Date",
    "Contact or Recruiter", "Notes", "Priority"
]

# Styling definitions
NAVY_FILL = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
THIN_BORDER = Border(
    left=Side(style='thin', color='E2E8F0'),
    right=Side(style='thin', color='E2E8F0'),
    top=Side(style='thin', color='E2E8F0'),
    bottom=Side(style='thin', color='E2E8F0')
)

class ExcelStorageManager:
    """
    Manages the single persistent Excel workbook 'internships.xlsx' containing exactly four sheets:
    - All Listings
    - Source Stats
    - seen_listings
    - Tracker
    Preserves all existing user-entered notes, deduplication history, and statuses.
    """

    def __init__(self, filepath: str = EXCEL_FILENAME):
        self.filepath = filepath
        self.seen_urls: Set[str] = set()
        self.seen_ids: Set[str] = set()
        self.existing_tracker_ids: Set[str] = set()
        self.ensure_initialized()
        self.load_history()

    def ensure_initialized(self) -> None:
        """Initializes internships.xlsx with all 4 sheets if not present."""
        if not os.path.exists(self.filepath):
            logger.info(f"Creating new master workbook: {self.filepath}")
            wb = openpyxl.Workbook()
            # Default active sheet becomes 'All Listings'
            ws1 = wb.active
            ws1.title = SHEET_ALL_LISTINGS
            ws1.append(ALL_LISTINGS_HEADERS)

            # Sheet 2: Source Stats
            ws2 = wb.create_sheet(title=SHEET_SOURCE_STATS)
            ws2.append(SOURCE_STATS_HEADERS)

            # Sheet 3: seen_listings
            ws3 = wb.create_sheet(title=SHEET_SEEN_LISTINGS)
            ws3.append(SEEN_LISTINGS_HEADERS)

            # Sheet 4: Tracker
            ws4 = wb.create_sheet(title=SHEET_TRACKER)
            ws4.append(TRACKER_HEADERS)

            self._apply_header_styles(wb)
            wb.save(self.filepath)
            wb.close()
            logger.info("Master workbook initialized successfully with 4 required worksheets.")
        else:
            self._validate_and_repair_sheets()

    def _validate_and_repair_sheets(self) -> None:
        """Validates that all 4 required sheets exist, repairing if any are missing."""
        wb = openpyxl.load_workbook(self.filepath)
        sheet_names = wb.sheetnames
        modified = False

        if SHEET_ALL_LISTINGS not in sheet_names:
            ws = wb.create_sheet(title=SHEET_ALL_LISTINGS)
            ws.append(ALL_LISTINGS_HEADERS)
            modified = True

        if SHEET_SOURCE_STATS not in sheet_names:
            ws = wb.create_sheet(title=SHEET_SOURCE_STATS)
            ws.append(SOURCE_STATS_HEADERS)
            modified = True

        if SHEET_SEEN_LISTINGS not in sheet_names:
            ws = wb.create_sheet(title=SHEET_SEEN_LISTINGS)
            ws.append(SEEN_LISTINGS_HEADERS)
            modified = True

        if SHEET_TRACKER not in sheet_names:
            ws = wb.create_sheet(title=SHEET_TRACKER)
            ws.append(TRACKER_HEADERS)
            modified = True

        if modified:
            self._apply_header_styles(wb)
            wb.save(self.filepath)
        wb.close()

    def _apply_header_styles(self, wb: openpyxl.Workbook) -> None:
        """Applies consistent executive styling to sheet headers."""
        for ws in wb.worksheets:
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = NAVY_FILL
                cell.font = HEADER_FONT
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            ws.freeze_panes = "A2"
            ws.row_dimensions[1].height = 28

    def load_history(self) -> None:
        """Loads deduplication history and existing tracker keys into memory."""
        self.seen_urls.clear()
        self.seen_ids.clear()
        self.existing_tracker_ids.clear()

        try:
            wb = openpyxl.load_workbook(self.filepath, data_only=True)
            
            # Load seen_listings
            if SHEET_SEEN_LISTINGS in wb.sheetnames:
                ws = wb[SHEET_SEEN_LISTINGS]
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row:
                        continue
                    sid = str(row[0] or "").strip()
                    url = str(row[1] or "").strip()
                    if sid:
                        self.seen_ids.add(sid)
                    if url:
                        self.seen_urls.add(normalize_url(url))

            # Load Tracker existing IDs
            if SHEET_TRACKER in wb.sheetnames:
                ws = wb[SHEET_TRACKER]
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row:
                        continue
                    jid = str(row[0] or "").strip()
                    if jid:
                        self.existing_tracker_ids.add(jid)

            wb.close()
            logger.info(f"Loaded {len(self.seen_ids)} seen IDs and {len(self.seen_urls)} seen URLs from history.")
        except Exception as e:
            logger.warning(f"Error loading history from {self.filepath}: {e}")

    def is_duplicate(self, listing: JobListing) -> bool:
        """Checks if listing has been seen previously."""
        canonical_url = normalize_url(listing.application_url or listing.original_url)
        if canonical_url and canonical_url in self.seen_urls:
            return True
        if listing.job_id and listing.job_id in self.seen_ids:
            return True
        if listing.fingerprint and listing.fingerprint in self.seen_ids:
            return True
        return False

    def update_workbook(
        self,
        new_listings: List[JobListing],
        source_stats: List[SourceExecutionStats],
        tracker_threshold: int = 60
    ) -> bool:
        """
        Updates the 4 worksheets atomically without destroying historical data.
        """
        now_ist = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
        today_str = datetime.now(IST).strftime('%Y-%m-%d')
        temp_file = f"{self.filepath}.tmp"

        try:
            wb = openpyxl.load_workbook(self.filepath)

            # 1. Update All Listings
            ws_all = wb[SHEET_ALL_LISTINGS]
            for item in new_listings:
                skills_str = ", ".join(item.skills) if isinstance(item.skills, list) else str(item.skills or "")
                reasons_str = "; ".join(item.match_reasons) if isinstance(item.match_reasons, list) else str(item.match_reasons or "")
                
                row = [
                    sanitize_for_spreadsheet(item.job_id),
                    sanitize_for_spreadsheet(item.title),
                    sanitize_for_spreadsheet(item.company),
                    sanitize_for_spreadsheet(item.location),
                    sanitize_for_spreadsheet(item.work_mode),
                    sanitize_for_spreadsheet(item.job_type),
                    sanitize_for_spreadsheet(item.experience),
                    sanitize_for_spreadsheet(item.salary),
                    sanitize_for_spreadsheet(item.description[:500]),
                    sanitize_for_spreadsheet(skills_str),
                    sanitize_for_spreadsheet(item.eligibility),
                    sanitize_for_spreadsheet(item.posted_date),
                    sanitize_for_spreadsheet(item.deadline),
                    sanitize_for_spreadsheet(item.source),
                    sanitize_for_spreadsheet(item.original_url),
                    sanitize_for_spreadsheet(item.application_url),
                    sanitize_for_spreadsheet(item.date_discovered or today_str),
                    sanitize_for_spreadsheet(now_ist),
                    item.match_score,
                    sanitize_for_spreadsheet(reasons_str),
                    sanitize_for_spreadsheet(item.application_status)
                ]
                ws_all.append(row)

                # Add link formatting to URL columns
                row_idx = ws_all.max_row
                orig_cell = ws_all.cell(row=row_idx, column=15)
                if orig_cell.value and validate_url(str(orig_cell.value)):
                    orig_cell.hyperlink = str(orig_cell.value)
                    orig_cell.font = Font(color="2563EB", underline="single")

                app_cell = ws_all.cell(row=row_idx, column=16)
                if app_cell.value and validate_url(str(app_cell.value)):
                    app_cell.hyperlink = str(app_cell.value)
                    app_cell.font = Font(color="2563EB", underline="single")

            # 2. Update Source Stats
            ws_stats = wb[SHEET_SOURCE_STATS]
            for stat in source_stats:
                row = [
                    sanitize_for_spreadsheet(stat.run_id),
                    sanitize_for_spreadsheet(stat.run_datetime_ist),
                    sanitize_for_spreadsheet(stat.source_name),
                    sanitize_for_spreadsheet(stat.source_status),
                    stat.records_retrieved,
                    stat.records_parsed,
                    stat.records_rejected,
                    stat.new_listings,
                    stat.duplicate_listings,
                    stat.listings_passing_filters,
                    stat.errors,
                    sanitize_for_spreadsheet(stat.error_details),
                    round(stat.execution_duration_sec, 2),
                    sanitize_for_spreadsheet(stat.api_usage_credits),
                    sanitize_for_spreadsheet(stat.source_pagination_info)
                ]
                ws_stats.append(row)

            # 3. Update seen_listings
            ws_seen = wb[SHEET_SEEN_LISTINGS]
            for item in new_listings:
                canonical = normalize_url(item.application_url or item.original_url)
                sid = item.job_id or item.fingerprint
                if sid not in self.seen_ids and (not canonical or canonical not in self.seen_urls):
                    row = [
                        sanitize_for_spreadsheet(sid),
                        sanitize_for_spreadsheet(canonical),
                        sanitize_for_spreadsheet(item.title),
                        sanitize_for_spreadsheet(item.company),
                        sanitize_for_spreadsheet(item.source),
                        sanitize_for_spreadsheet(item.date_discovered or today_str),
                        sanitize_for_spreadsheet(today_str),
                        ""  # Last Notified Date (populated when emailed)
                    ]
                    ws_seen.append(row)
                    self.seen_ids.add(sid)
                    if canonical:
                        self.seen_urls.add(canonical)

            # 4. Update Tracker (add high conviction listings >= tracker_threshold)
            ws_tracker = wb[SHEET_TRACKER]
            for item in new_listings:
                if item.match_score >= tracker_threshold and item.job_id not in self.existing_tracker_ids:
                    priority = "High" if item.match_score >= 80 else "Medium"
                    row = [
                        sanitize_for_spreadsheet(item.job_id),
                        sanitize_for_spreadsheet(item.title),
                        sanitize_for_spreadsheet(item.company),
                        sanitize_for_spreadsheet(item.location),
                        sanitize_for_spreadsheet(item.application_url or item.original_url),
                        sanitize_for_spreadsheet(today_str),
                        "Not Applied",  # Default status
                        "",             # Application Date
                        "",             # Follow-up Date
                        "",             # Contact / Recruiter
                        "",             # Notes (preserved for user)
                        priority
                    ]
                    ws_tracker.append(row)
                    self.existing_tracker_ids.add(item.job_id)

                    # Clickable URL
                    t_cell = ws_tracker.cell(row=ws_tracker.max_row, column=5)
                    if t_cell.value and validate_url(str(t_cell.value)):
                        t_cell.hyperlink = str(t_cell.value)
                        t_cell.font = Font(color="2563EB", underline="single")

            # Auto-fit column widths across all sheets
            for ws in wb.worksheets:
                for col in ws.columns:
                    max_len = max(len(str(cell.value or '')) for cell in col[:50])
                    col_letter = get_column_letter(col[0].column)
                    ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

            # Atomic save: save to temp and replace
            wb.save(temp_file)
            wb.close()
            shutil.move(temp_file, self.filepath)
            logger.info(f"Successfully and atomically updated {self.filepath}")
            return True
        except Exception as e:
            logger.critical(f"Failed to update Excel workbook {self.filepath}: {e}", exc_info=True)
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    def mark_notified(self, notified_ids: Set[str]) -> None:
        """Updates Last Notified Date in seen_listings only after confirmed email delivery."""
        if not notified_ids:
            return
        today_str = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
        try:
            wb = openpyxl.load_workbook(self.filepath)
            if SHEET_SEEN_LISTINGS in wb.sheetnames:
                ws = wb[SHEET_SEEN_LISTINGS]
                for row_idx in range(2, ws.max_row + 1):
                    sid = str(ws.cell(row=row_idx, column=1).value or "").strip()
                    if sid in notified_ids:
                        ws.cell(row=row_idx, column=8, value=today_str)
            wb.save(self.filepath)
            wb.close()
            logger.info(f"Marked {len(notified_ids)} listings as notified.")
        except Exception as e:
            logger.warning(f"Failed to mark listings as notified: {e}")

    def validate_workbook(self) -> Tuple[bool, str]:
        """Validates that the physical workbook exists, is non-empty, and contains all 4 sheets."""
        if not os.path.exists(self.filepath):
            return False, f"Workbook '{self.filepath}' does not exist on disk."
        try:
            wb = openpyxl.load_workbook(self.filepath, data_only=True)
            required = {SHEET_ALL_LISTINGS, SHEET_SOURCE_STATS, SHEET_SEEN_LISTINGS, SHEET_TRACKER}
            missing = required - set(wb.sheetnames)
            wb.close()
            if missing:
                return False, f"Workbook is missing required sheet(s): {', '.join(missing)}"
            return True, "Workbook valid with all 4 worksheets intact."
        except Exception as e:
            return False, f"Corrupted or unreadable workbook: {e}"
