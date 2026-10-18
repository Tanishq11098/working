import pytest
from bot.scoring import ScoringEngine
from bot.models import JobListing

def test_eligible_technical_roles():
    engine = ScoringEngine(strict_location=True)

    # 1. Valid Python Intern in Noida
    listing1 = JobListing(
        job_id="T1",
        title="Python Developer Intern",
        company="StartupHub",
        location="Noida, India",
        experience="0-1 yrs",
        description="We are looking for a Python intern proficient in Django/Flask and SQL."
    )
    assert engine.evaluate(listing1) is True
    assert listing1.match_score >= 60

    # 2. Remote Software Intern
    listing2 = JobListing(
        job_id="T2",
        title="Software Engineering Intern",
        company="GlobalTech",
        location="Remote (India)",
        experience="Fresher",
        description="Looking for entry level engineers with React and Python skills."
    )
    assert engine.evaluate(listing2) is True
    assert listing2.match_score >= 60

def test_rejection_of_unrelated_roles():
    engine = ScoringEngine(strict_location=True)

    # Telecaller / BPO role
    noise_listing = JobListing(
        job_id="T3",
        title="Telecaller Executive & Sales BPO",
        company="CallCenter",
        location="Delhi",
        description="Calling clients for lead generation."
    )
    assert engine.evaluate(noise_listing) is False

def test_rejection_of_ineligible_experience():
    engine = ScoringEngine(strict_location=True)

    # 5+ years senior role
    senior_listing = JobListing(
        job_id="T4",
        title="Senior Python Architect",
        company="BigCorp",
        location="Gurgaon",
        experience="5-8 yrs",
        description="Lead engineering teams on microservices."
    )
    assert engine.evaluate(senior_listing) is False

def test_strict_location_filter():
    engine = ScoringEngine(strict_location=True)

    # Non-NCR, non-remote on-site location (e.g. Pune)
    pune_listing = JobListing(
        job_id="T5",
        title="Python Developer Intern",
        company="PuneTech",
        location="Pune, Maharashtra",
        experience="0-1 yrs",
        description="On-site Pune internship."
    )
    assert engine.evaluate(pune_listing) is False
