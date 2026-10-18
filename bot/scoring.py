import re
import logging
from typing import Tuple, List, Dict, Any, Optional
from .models import JobListing

logger = logging.getLogger("InternshipBot.Scoring")

# National Capital Region (NCR) matching
NCR_PATTERNS = [
    r"\bdelhi\b", r"\bnew delhi\b", r"\bgurgaon\b", r"\bgurugram\b",
    r"\bnoida\b", r"\bgreater noida\b", r"\bfaridabad\b", r"\bghaziabad\b",
    r"\bncr\b", r"delhi[- ]ncr"
]

# Target Technical Role Keywords
TECH_ROLE_KEYWORDS = {
    "software": 30,
    "python": 30,
    "web development": 28,
    "frontend": 28,
    "front end": 28,
    "backend": 28,
    "back end": 28,
    "full stack": 30,
    "fullstack": 30,
    "data analyst": 28,
    "data science": 30,
    "machine learning": 30,
    "artificial intelligence": 30,
    "ai engineer": 30,
    "ml engineer": 30,
    "automation": 28,
    "qa": 25,
    "quality assurance": 25,
    "software testing": 25,
    "business analyst": 22,
    "research intern": 25,
    "technology intern": 25,
    "developer": 25
}

# Unrelated Noise terms (Strict rejection unless explicitly technical)
NOISE_TITLES = [
    r"\btelecaller\b", r"\bbpo\b", r"\bcontent writer\b", r"\bcopywriter\b",
    r"\bgraphic design\b", r"\bvideo edit\b", r"\bdigital marketing\b",
    r"\bsocial media\b", r"\bseo intern\b", r"\bhr intern\b", r"\brecruiter\b",
    r"\bcampus ambassador\b", r"\bfundraising\b", r"\blegal intern\b"
]

class ScoringEngine:
    """
    Transparent scoring engine (0-100) and hard filter verification.
    Validates technical internship relevance, location compatibility, and fresher eligibility.
    """

    def __init__(self, strict_location: bool = True):
        self.strict_location = strict_location

    def is_noise_title(self, title: str) -> bool:
        t_clean = (title or "").lower()
        for pat in NOISE_TITLES:
            if re.search(pat, t_clean):
                return True
        return False

    def check_experience_eligibility(self, exp_text: str, description: str) -> Tuple[bool, str]:
        """
        Hard filter:
        Accepts: Fresher, Entry-level, Internship, 0-1 yrs, 0-2 yrs.
        Rejects: >2 years required, Senior, Lead, Manager, Architect.
        """
        combined = f"{exp_text} {description}".lower()

        # Reject senior indicators
        if re.search(r'\b(?:senior|lead|principal|architect|manager|head of|vp|director)\b', combined):
            return False, "Senior or leadership title/role"

        # Look for explicit years
        exp_matches = re.findall(r'(\d+)\s*(?:-|to)\s*(\d+)\s*(?:yrs|years)', combined)
        if exp_matches:
            try:
                min_yr = int(exp_matches[0][0])
                if min_yr > 2:
                    return False, f"Requires {min_yr}+ years experience (exceeds 2-year cap)"
            except Exception:
                pass
        else:
            single = re.search(r'(\d+)\+?\s*(?:yrs|years)(?:\s+of\s+exp)?', combined)
            if single:
                try:
                    yrs = int(single.group(1))
                    if yrs > 2:
                        return False, f"Requires {yrs}+ years experience (exceeds 2-year cap)"
                except Exception:
                    pass

        return True, "Eligible fresher / entry-level / <=2 years"

    def check_location(self, location_str: str) -> Tuple[bool, str, int]:
        """
        Evaluates location compatibility:
        - Delhi NCR: Eligible (+20 pts)
        - Remote / WFH India: Eligible (+20 pts)
        - Other: Ineligible if strict_location is True, else 0 pts.
        """
        if not location_str:
            if self.strict_location:
                return False, "Missing location in strict mode", 0
            return True, "Unspecified location", 0

        loc_clean = location_str.lower()

        # Check NCR
        for pat in NCR_PATTERNS:
            if re.search(pat, loc_clean):
                return True, "Delhi-NCR location", 20

        # Check Remote
        if re.search(r'\b(?:remote|work from home|wfh|anywhere in india|virtual)\b', loc_clean):
            return True, "Remote / WFH eligible", 20

        if self.strict_location:
            return False, f"Location '{location_str}' outside target Delhi-NCR/Remote", 0
        return True, f"Other location '{location_str}'", 5

    def evaluate(self, listing: JobListing) -> bool:
        """
        Calculates score (0-100) and applies hard eligibility filters.
        Returns True if listing qualifies for retention (score >= 40), False otherwise.
        """
        title_lower = (listing.title or "").lower()
        desc_lower = (listing.description or "").lower()
        combined = f"{title_lower} {desc_lower}"

        # 1. Hard Filter: Noise rejection
        if self.is_noise_title(listing.title):
            listing.match_reasons.append("Rejected: Unrelated non-technical role")
            listing.match_score = 0
            return False

        # 2. Hard Filter: Experience check
        exp_ok, exp_reason = self.check_experience_eligibility(listing.experience, listing.description)
        if not exp_ok:
            listing.match_reasons.append(f"Rejected: {exp_reason}")
            listing.match_score = 0
            return False

        # 3. Hard Filter: Location check
        loc_ok, loc_reason, loc_pts = self.check_location(listing.location)
        if not loc_ok:
            listing.match_reasons.append(f"Rejected: {loc_reason}")
            listing.match_score = 0
            return False

        score = 0
        reasons = []

        # Location points
        score += loc_pts
        reasons.append(f"+{loc_pts} pts: {loc_reason}")

        # 4. Target Role Title Relevance (up to 30 pts)
        role_pts = 0
        matched_roles = []
        for kw, pts in TECH_ROLE_KEYWORDS.items():
            if re.search(rf'\b{re.escape(kw)}\b', title_lower):
                matched_roles.append(kw)
                if pts > role_pts:
                    role_pts = pts

        if role_pts > 0:
            score += role_pts
            reasons.append(f"+{role_pts} pts: Title matches target role keywords ({', '.join(matched_roles[:2])})")
        else:
            # Check description for role relevance
            desc_matches = [kw for kw in TECH_ROLE_KEYWORDS if re.search(rf'\b{re.escape(kw)}\b', desc_lower)]
            if desc_matches:
                score += 15
                reasons.append(f"+15 pts: Description matches target skills ({', '.join(desc_matches[:3])})")
            else:
                reasons.append("+0 pts: No strong technical keyword match")

        # 5. Internship / Fresher Explicit Signal (up to 20 pts)
        if re.search(r'\b(?:intern|internship|trainee|fresher|entry[- ]level|graduate trainee)\b', title_lower):
            score += 20
            reasons.append("+20 pts: Explicit internship/fresher designation in title")
        elif re.search(r'\b(?:intern|internship|trainee|fresher|entry[- ]level|0[- ]1 yrs|0[- ]2 yrs)\b', desc_lower):
            score += 10
            reasons.append("+10 pts: Fresher or internship designation in description")

        # 6. Technical Skills Present (up to 15 pts)
        tech_skills = ["python", "javascript", "react", "node", "sql", "git", "docker", "aws", "pandas", "html", "css", "java", "c++"]
        found_skills = [s for s in tech_skills if re.search(rf'\b{re.escape(s)}\b', combined)]
        if found_skills:
            skill_pts = min(len(found_skills) * 3, 15)
            score += skill_pts
            reasons.append(f"+{skill_pts} pts: Relevant technical skills found ({', '.join(found_skills[:4])})")
            listing.skills = list(set(listing.skills + found_skills))

        # 7. Application URL quality (up to 10 pts)
        if listing.application_url or listing.original_url:
            score += 10
            reasons.append("+10 pts: Legitimate application link present")

        # 8. Description completeness (up to 5 pts)
        if len(listing.description.strip()) > 100:
            score += 5
            reasons.append("+5 pts: Detailed job description available")

        # Cap at 100
        final_score = min(score, 100)
        listing.match_score = final_score
        listing.match_reasons = reasons

        # Pass if match_score >= 40
        return final_score >= 40
