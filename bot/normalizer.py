import re
import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from datetime import datetime, timezone, timedelta
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))

TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "ref", "source", "trk", "trkinfo",
    "tracking", "trackingid", "tracking_id", "orig", "from", "spref", "midToken", "sid", "sc",
    "mc_cid", "mc_eid", "yclid", "igshid"
}

def normalize_url(raw_url: str) -> str:
    """
    Strips tracking query parameters and fragments while retaining necessary identifiers.
    Normalizes hostname to lowercase.
    """
    if not raw_url or not isinstance(raw_url, str):
        return ""
    url = raw_url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        return url

    try:
        parsed = urlparse(url)
        # Parse query params, filtering out tracking params
        filtered_q = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
            if k.lower() not in TRACKING_QUERY_PARAMS
        ]
        # Rebuild query string sorted for deterministic canonical comparison
        filtered_q.sort(key=lambda x: x[0])
        new_query = urlencode(filtered_q)

        # Normalize host to lowercase and strip fragments
        clean_url = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip('/') if parsed.path != '/' else '/',
            parsed.params,
            new_query,
            ""  # Strip fragment
        ))
        return clean_url
    except Exception:
        return url


def generate_fingerprint(company: str, title: str, location: str) -> str:
    """
    Generates deterministic 16-character SHA-256 fingerprint from cleaned core attributes.
    """
    c = re.sub(r'[^a-z0-9]', '', (company or "").lower())
    t = re.sub(r'[^a-z0-9]', '', (title or "").lower())
    l = re.sub(r'[^a-z0-9]', '', (location or "").lower())
    seed = f"{c}:{t}:{l}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def parse_date_string(raw: Optional[str]) -> Optional[str]:
    """
    Parses various date and relative strings into YYYY-MM-DD in IST.
    """
    if not raw or not isinstance(raw, str):
        return None
    r = raw.strip()
    now_ist = datetime.now(IST)

    # Relative handling: '1 day ago', '3 days ago', 'just now', 'today', 'yesterday'
    r_lower = r.lower()
    if "today" in r_lower or "just now" in r_lower or "hour" in r_lower or "minute" in r_lower:
        return now_ist.strftime('%Y-%m-%d')
    if "yesterday" in r_lower:
        return (now_ist - timedelta(days=1)).strftime('%Y-%m-%d')

    days_match = re.search(r'(\d+)\s*(?:day|days|d)\s*ago', r_lower)
    if days_match:
        days = int(days_match.group(1))
        return (now_ist - timedelta(days=days)).strftime('%Y-%m-%d')

    # Standard date format parsing
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y",
        "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(r[:25].strip(), fmt)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            continue

    return None
