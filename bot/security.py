import re
import html
import logging
from typing import Set, Optional

logger = logging.getLogger("InternshipBot.Security")

class SecretScrubber:
    """Masks registered sensitive tokens, passwords, and keys from all logs and outputs."""
    def __init__(self):
        self._secrets: Set[str] = set()

    def register_secret(self, secret: Optional[str]) -> None:
        if secret and len(str(secret).strip()) >= 4:
            self._secrets.add(str(secret).strip())

    def scrub(self, text: str) -> str:
        if not text:
            return ""
        scrubbed = str(text)
        for s in sorted(self._secrets, key=len, reverse=True):
            scrubbed = scrubbed.replace(s, "[REDACTED]")
        # Standard API token & Bearer pattern matching
        scrubbed = re.sub(r'(bearer\s+)[a-zA-Z0-9_\-\.]{8,}', r'\1[REDACTED]', scrubbed, flags=re.I)
        scrubbed = re.sub(r'([?&](?:token|key|api_key|password|secret|app_key)=)[^&]+', r'\1[REDACTED]', scrubbed, flags=re.I)
        return scrubbed


class RedactingFormatter(logging.Formatter):
    """Custom logging formatter that scrubs sensitive credentials in log streams."""
    def __init__(self, fmt: str, datefmt: str, scrubber: SecretScrubber):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.scrubber = scrubber

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return self.scrubber.scrub(original)


def sanitize_for_spreadsheet(value: str) -> str:
    """
    Prevents spreadsheet formula injection (CSV/Excel Formula Injection).
    Prepends a single quote if the string begins with =, +, -, @, or tab/CR.
    """
    if not value or not isinstance(value, str):
        return str(value or "")
    val = value.strip()
    if val and val[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{val}"
    return val


def sanitize_html(text: str) -> str:
    """HTML-escapes string content to prevent XSS in email bodies."""
    if not text:
        return ""
    return html.escape(str(text))


def validate_url(url: str) -> bool:
    """Verifies that URL has a valid http/https scheme and host format."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    return bool(re.match(r'^https?://[^\s/$.?#].[^\s]*$', u, re.I))
