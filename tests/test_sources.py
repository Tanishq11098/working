import pytest
from unittest.mock import MagicMock, patch
from bot.sources import ApifySource, InternshalaSource, TimesJobsSource
from bot.normalizer import normalize_url, generate_fingerprint, parse_date_string

def test_url_normalization():
    dirty = "https://www.naukri.com/job/12345?utm_source=google&gclid=xyz123&ref=feed#section"
    clean = normalize_url(dirty)
    assert "utm_source" not in clean
    assert "gclid" not in clean
    assert "#section" not in clean
    assert clean == "https://www.naukri.com/job/12345"

def test_fingerprint_deterministic():
    fp1 = generate_fingerprint("Google", "Software Intern", "Delhi")
    fp2 = generate_fingerprint("google", "software intern", "delhi")
    assert fp1 == fp2
    assert len(fp1) == 16

def test_date_parsing():
    parsed = parse_date_string("2 days ago")
    assert parsed is not None
    assert len(parsed) == 10  # YYYY-MM-DD format

def test_apify_source_mock():
    mock_items = [
        {
            "id": "123",
            "title": "Backend Python Intern",
            "companyName": "AlphaTech",
            "location": "Gurugram",
            "url": "https://linkedin.com/jobs/view/123?tracking=abc",
            "experience": "0-1 yrs",
            "skills": ["Python", "FastAPI"]
        }
    ]
    source = ApifySource(token="fake_token", enabled=True)
    with patch.object(source, "request_with_retry") as mock_req:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_items
        mock_req.return_value = mock_resp

        listings = source.fetch(query="python")
        assert len(listings) == 1
        assert listings[0].title == "Backend Python Intern"
        assert listings[0].company == "AlphaTech"
        assert "tracking" not in listings[0].original_url
        assert source.stats.records_retrieved == 1
