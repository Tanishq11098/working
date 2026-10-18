import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import List, Optional

from .models import JobListing, RunReport
from .security import sanitize_html, SecretScrubber

logger = logging.getLogger("InternshipBot.Notifier")

class EmailNotifier:
    """Dispatches daily HTML summaries with the single master Excel workbook attached."""

    def __init__(
        self,
        sender: str,
        password: str,
        recipient: Optional[str] = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 465,
        scrubber: Optional[SecretScrubber] = None
    ):
        self.sender = str(sender or "").strip()
        self.password = str(password or "").strip()
        self.recipient = str(recipient or sender or "").strip()
        self.smtp_host = smtp_host
        self.smtp_port = int(smtp_port)
        self.scrubber = scrubber or SecretScrubber()

        if self.password:
            self.scrubber.register_secret(self.password)
        if self.sender:
            self.scrubber.register_secret(self.sender)

    def is_configured(self) -> bool:
        return bool(self.sender and self.password and self.recipient)

    def build_html_report(self, report: RunReport, new_listings: List[JobListing]) -> str:
        """Constructs a responsive executive HTML notification."""
        date_str = sanitize_html(report.run_date_ist)
        total_found = len(new_listings)

        # Build listings table rows
        listings_rows = ""
        for item in new_listings[:30]:  # Top 30 highlights in email
            score_color = "#16a34a" if item.match_score >= 80 else "#2563eb"
            reasons_str = "<br>• ".join([sanitize_html(r) for r in item.match_reasons[:2]])
            link_url = sanitize_html(item.application_url or item.original_url)

            listings_rows += f"""
            <tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 10px; font-weight: 600; color: {score_color}; text-align: center;">{item.match_score}</td>
                <td style="padding: 10px; font-weight: 600; color: #1e293b;">{sanitize_html(item.title)}</td>
                <td style="padding: 10px; color: #475569;">{sanitize_html(item.company)}</td>
                <td style="padding: 10px; color: #475569;">{sanitize_html(item.location)}</td>
                <td style="padding: 10px; font-size: 12px; color: #64748b;">• {reasons_str}</td>
                <td style="padding: 10px; text-align: center;">
                    <a href="{link_url}" style="background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 6px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; display: inline-block;">Apply</a>
                </td>
            </tr>
            """

        # Build telemetry rows
        stats_rows = ""
        for name, stat in report.sources.items():
            status_color = "#16a34a" if stat.source_status == "Success" else ("#eab308" if stat.source_status == "Zero Results" else "#64748b")
            stats_rows += f"""
            <tr style="border-bottom: 1px solid #f1f5f9;">
                <td style="padding: 6px 10px; font-weight: 500;">{sanitize_html(name)}</td>
                <td style="padding: 6px 10px; color: {status_color}; font-weight: 600;">{sanitize_html(stat.source_status)}</td>
                <td style="padding: 6px 10px; text-align: center;">{stat.records_retrieved}</td>
                <td style="padding: 6px 10px; text-align: center;">{stat.new_listings}</td>
                <td style="padding: 6px 10px; text-align: center;">{stat.listings_passing_filters}</td>
                <td style="padding: 6px 10px; font-size: 11px; color: #ef4444;">{sanitize_html(stat.error_details or '-')}</td>
            </tr>
            """

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
                .container {{ max-width: 900px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; }}
                .header {{ background: #1e3a8a; color: #ffffff; padding: 24px; text-align: left; }}
                .stats-bar {{ display: flex; background: #eff6ff; padding: 14px 24px; border-bottom: 1px solid #dbeafe; }}
                .stat-box {{ margin-right: 24px; }}
                .stat-num {{ font-size: 18px; font-weight: bold; color: #1e40af; }}
                .stat-lbl {{ font-size: 12px; color: #64748b; text-transform: uppercase; }}
                .content {{ padding: 24px; }}
                table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
                th {{ background: #f1f5f9; padding: 10px; text-align: left; color: #334155; font-size: 12px; text-transform: uppercase; }}
                .footer {{ background: #f8fafc; padding: 16px 24px; font-size: 12px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="margin: 0; font-size: 20px;">Daily Technical Internship Digest</h2>
                    <p style="margin: 4px 0 0; font-size: 13px; opacity: 0.9;">Run Date: {date_str} IST</p>
                </div>
                <div class="stats-bar">
                    <div class="stat-box"><div class="stat-num">{report.total_retrieved}</div><div class="stat-lbl">Records Scanned</div></div>
                    <div class="stat-box"><div class="stat-num">{report.total_new}</div><div class="stat-lbl">New Listings</div></div>
                    <div class="stat-box"><div class="stat-num">{report.total_duplicates}</div><div class="stat-lbl">Duplicates Skipped</div></div>
                    <div class="stat-box"><div class="stat-num">{report.total_passing_filters}</div><div class="stat-lbl">Qualified Matches</div></div>
                </div>
                <div class="content">
                    <h3 style="color: #1e293b; margin-top: 0;">Today's Top Qualifying Technical Roles ({total_found})</h3>
                    {f'<table><thead><tr><th>Score</th><th>Title</th><th>Company</th><th>Location</th><th>Match Reasons</th><th>Action</th></tr></thead><tbody>{listings_rows}</tbody></table>' if new_listings else '<p style="color: #64748b; font-style: italic;">No new qualifying technical opportunities passed the filters today. Check the attached master workbook for the complete active tracker history.</p>'}
                    
                    <h3 style="color: #1e293b; margin-top: 32px;">Source Diagnostics & Telemetry</h3>
                    <table>
                        <thead><tr><th>Source</th><th>Status</th><th>Retrieved</th><th>New</th><th>Passing</th><th>Details / Errors</th></tr></thead>
                        <tbody>{stats_rows}</tbody>
                    </table>
                </div>
                <div class="footer">
                    <p style="margin: 0;">Attached: <strong>internships.xlsx</strong> (contains All Listings, Source Stats, seen_listings, and Tracker worksheets).</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html_body

    def send_digest(self, report: RunReport, new_listings: List[JobListing], workbook_path: str) -> bool:
        """Sends daily email with the single workbook attached."""
        if not self.is_configured():
            logger.info("Email delivery skipped: GMAIL credentials not configured.")
            return False

        logger.info(f"Connecting to SMTP {self.smtp_host}:{self.smtp_port} to deliver report...")
        try:
            msg = MIMEMultipart()
            msg["Subject"] = f"Job Hunting Digest: {report.total_passing_filters} New Technical Roles - {report.run_date_ist} IST"
            msg["From"] = self.sender
            msg["To"] = self.recipient

            html_content = self.build_html_report(report, new_listings)
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # Attach single workbook internships.xlsx
            if os.path.exists(workbook_path):
                with open(workbook_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(workbook_path))
                    part["Content-Disposition"] = f'attachment; filename="{os.path.basename(workbook_path)}"'
                    msg.attach(part)
            else:
                logger.error(f"Workbook attachment '{workbook_path}' not found on disk!")
                return False

            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.login(self.sender, self.password)
                server.send_message(msg)

            logger.info(f"Daily digest successfully delivered to {self.recipient} with workbook attachment.")
            return True
        except Exception as e:
            err_msg = self.scrubber.scrub(str(e))
            logger.error(f"Failed to deliver daily email: {err_msg}", exc_info=False)
            return False
