# Production-Ready Technical Internship & Job-Hunting Bot

An autonomous Python intelligence bot engineered to discover, score, deduplicate, and track high-conviction Software Development, Python, Web Development, Data Science, AI/ML, and Automation internships and fresher opportunities.

Runs daily via GitHub Actions at **8:00 AM IST** (`02:30 UTC`), maintains state within a single Excel workbook (`internships.xlsx`), and delivers a styled HTML summary directly to your email with the complete spreadsheet attached.

---

## 1. Non-Negotiable Single-Workbook Architecture

The bot uses **exactly one Excel workbook named `internships.xlsx`** across the entire lifecycle. No Google Sheets or secondary Excel workbooks are created.

The workbook contains exactly four worksheets:
1. **`All Listings`**: Master catalog of collected and normalized technical internship opportunities with scores, match reasons, and application URLs.
2. **`Source Stats`**: Execution telemetry table tracking records retrieved, rejected, new vs duplicates, passing filters, API credits, and error details per source.
3. **`seen_listings`**: Persistent cross-run deduplication registry using canonical URLs and 16-character deterministic SHA-256 fingerprints.
4. **`Tracker`**: Interactive application tracker initialized with `Not Applied` status for high-conviction roles (Score ≥ 60), preserving all user-added notes and follow-up dates across runs.

---

## 2. Target Roles & Eligibility Filters

- **Target Roles**: Software Development Intern, Python Developer Intern, Web Development (Frontend/Backend/Full Stack), Data Analyst, Data Science, Machine Learning, AI Engineer, QA/Automation, and Research/Technology Interns.
- **Experience Eligibility**: Freshers, Entry-Level, 0-1 years, 0-2 years. Strict rejection of roles demanding >2 years experience, or senior/lead titles.
- **Location Compatibility**: National Capital Region (Delhi, Gurugram/Gurgaon, Noida, Faridabad, Ghaziabad) and Remote opportunities open to applicants across India.

---

## 3. GitHub Actions Setup & Persistence

The bot persists `internships.xlsx` directly in your GitHub repository:
1. Runner checks out the repository with `contents: write` permission.
2. Loads the tracked `internships.xlsx`.
3. Runs the scraping, scoring, and deduplication pipeline.
4. Atomically updates all 4 worksheets in `internships.xlsx`.
5. Re-validates that all 4 worksheets are present and readable.
6. Commits and pushes the updated `internships.xlsx` back to your repository using `[skip ci]` to avoid infinite workflow triggers.
7. Dispatches the daily email with `internships.xlsx` attached.
8. Uploads `internships.xlsx` as the GitHub Actions artifact named `internship-report`.

---

## 4. GitHub Secrets Configuration

Configure the following secrets in **Settings > Secrets and variables > Actions**:

| Secret Name | Required? | Description |
|---|---|---|
| `GMAIL_ADDRESS` | **Required** (for email) | Your sender Gmail address |
| `GMAIL_APP_PASSWORD` | **Required** (for email) | 16-character Gmail App Password (Google Account > Security > App Passwords) |
| `EMAIL_TO` | Optional | Recipient email address (defaults to `GMAIL_ADDRESS` if omitted) |
| `APIFY_API_TOKEN` | Optional | Apify API token for LinkedIn / Naukri / Indeed actors |
| `ADZUNA_APP_ID` | Optional | Adzuna India API Application ID |
| `ADZUNA_APP_KEY` | Optional | Adzuna India API Application Key |
| `JSEARCH_API_KEY` | Optional | RapidAPI key for JSearch |

---

## 5. Local Usage & Testing

### Install Dependencies:
```bash
pip install -r requirements.txt
```

### Run Tests:
```bash
python -m pytest tests
```

### Run the Bot Locally:
```bash
# Dry-run mode (scrapes and displays results without modifying Excel or emailing)
python internship_bot.py --dry-run

# Live execution
python internship_bot.py
```
