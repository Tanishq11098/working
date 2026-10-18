from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class JobListing:
    """Standardized job and internship listing model across all sources."""
    job_id: str
    title: str
    company: str
    location: str
    work_mode: str = "On-site"  # On-site, Hybrid, Remote
    job_type: str = "Internship"  # Internship, Entry-Level, Graduate Trainee
    experience: str = "0-1 yrs"
    salary: str = "Not Disclosed"
    description: str = ""
    skills: List[str] = field(default_factory=list)
    eligibility: str = "Fresher / Entry-Level"
    posted_date: str = ""
    deadline: str = ""
    source: str = ""
    original_url: str = ""
    application_url: str = ""
    date_discovered: str = ""
    date_last_verified: str = ""
    match_score: int = 0
    match_reasons: List[str] = field(default_factory=list)
    application_status: str = "Not Applied"
    fingerprint: str = ""
    is_new: bool = True
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceExecutionStats:
    """Telemetry and execution metrics for an individual source."""
    run_id: str
    run_datetime_ist: str
    source_name: str
    source_status: str = "Pending"  # Success, Partial, Failed, Skipped, Zero Results
    records_retrieved: int = 0
    records_parsed: int = 0
    records_rejected: int = 0
    new_listings: int = 0
    duplicate_listings: int = 0
    listings_passing_filters: int = 0
    errors: int = 0
    error_details: str = ""
    execution_duration_sec: float = 0.0
    api_usage_credits: str = "N/A"
    source_pagination_info: str = "N/A"


@dataclass
class RunReport:
    """Consolidated report across all sources for an execution run."""
    run_id: str
    run_date_ist: str
    sources: Dict[str, SourceExecutionStats] = field(default_factory=dict)
    total_retrieved: int = 0
    total_parsed: int = 0
    total_new: int = 0
    total_duplicates: int = 0
    total_passing_filters: int = 0
    workbook_saved: bool = False
    email_sent: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
