import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import Dict
from app.config import settings

logger = logging.getLogger(__name__)

def send_batch_report_email(profiles: Dict, recipient: str, duration: float = 0.0):
    """
    Generate and send an HTML summary report of safety violations detected during the live stream.
    If SMTP server is not configured, it will print a mock email to the logger.
    """
    if not recipient:
        logger.warning("No recipient email provided for batch report. Skipping.")
        return

    # Compile Summary Data
    total_persons = len(profiles)
    total_violations = 0
    violation_counts = {}

    for tid, profile in profiles.items():
        total_violations += profile.violation_count
        for v_type, count in profile.violation_types.items():
            if v_type not in violation_counts:
                violation_counts[v_type] = 0
            violation_counts[v_type] += count

    # Calculate compliance score
    if total_persons > 0:
        violation_rate = total_violations / total_persons
        # Score: 100% = no violations, decreases with each violation per person
        compliance_score = max(0, 100 - (violation_rate * 25))
    else:
        compliance_score = 100.0

    compliance_status = "PASS" if compliance_score >= 70 else "FAIL"
    status_color = "#16a34a" if compliance_status == "PASS" else "#dc2626"
    status_bg = "#dcfce7" if compliance_status == "PASS" else "#fef2f2"

    # Format duration nicely
    duration_mins = int(duration // 60)
    duration_secs = int(duration % 60)
    duration_str = f"{duration_mins}m {duration_secs}s" if duration_mins > 0 else f"{duration_secs}s"

    # Generate HTML Content
    html_content = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                h1 {{ color: #2563eb; }}
                h2 {{ color: #1e40af; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }}
                .compliance-banner {{ padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center; border: 2px solid {status_color}; background: {status_bg}; }}
                .compliance-score {{ font-size: 48px; font-weight: bold; color: {status_color}; margin: 0; }}
                .compliance-label {{ font-size: 14px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; }}
                .compliance-status {{ display: inline-block; padding: 6px 20px; border-radius: 20px; font-weight: bold; font-size: 18px; color: white; background: {status_color}; margin-top: 8px; }}
                .summary-box {{ background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }}
                th {{ background-color: #e5e7eb; }}
                .danger {{ color: #dc2626; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>VioTrack: Safety Compliance Report</h1>

            <div class="compliance-banner">
                <p class="compliance-label">Overall Compliance Score</p>
                <p class="compliance-score">{compliance_score:.0f}%</p>
                <div class="compliance-status">{compliance_status}</div>
            </div>

            <h2>Session Summary</h2>
            <div class="summary-box">
                <p><strong>Session Duration:</strong> {duration_str}</p>
                <p><strong>Total Persons Tracked:</strong> {total_persons}</p>
                <p><strong>Total Violations Detected:</strong> <span class="{"danger" if total_violations > 0 else ""}">{total_violations}</span></p>
                <p><strong>Compliance Score:</strong> <span style="color: {status_color}; font-weight: bold;">{compliance_score:.0f}% — {compliance_status}</span></p>
            </div>
    """

    if total_violations > 0:
        html_content += """
            <h2>Violation Breakdown</h2>
            <table>
                <tr>
                    <th>Violation Type</th>
                    <th>Incidents</th>
                </tr>
        """
        for v_type, count in sorted(violation_counts.items(), key=lambda x: x[1], reverse=True):
            html_content += f"""
                <tr>
                    <td>{v_type}</td>
                    <td>{count}</td>
                </tr>
            """
        html_content += "</table>"
        
        html_content += """
            <h2>Person Log (Violators Only)</h2>
            <table>
                <tr>
                    <th>Track ID</th>
                    <th>Violations</th>
                    <th>Details</th>
                </tr>
        """
        for tid, profile in profiles.items():
            if profile.violation_count > 0:
                details = ", ".join([f"{k} ({v})" for k, v in profile.violation_types.items()])
                html_content += f"""
                    <tr>
                        <td>Person-{tid}</td>
                        <td>{profile.violation_count}</td>
                        <td>{details}</td>
                    </tr>
                """
        html_content += "</table>"
    else:
        html_content += "<p><em>No safety violations were detected during this session. Great job!</em></p>"

    html_content += """
            <br>
            <p style="font-size: 12px; color: #6b7280;">This is an automated safety report generated by VioTrack.</p>
        </body>
    </html>
    """

    # Check if SMTP is configured
    if not settings.SMTP_SERVER or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.info(f"--- MOCK EMAIL START ---")
        logger.info(f"To: {recipient}")
        logger.info(f"Subject: [VioTrack] Live Stream Batch Report - {total_violations} Violations")
        logger.info("HTML Body generated successfully. Setup SMTP credentials in .env to actually send this over the internet.")
        logger.info(f"--- MOCK EMAIL END ---")
        return

    # Send the email via SMTP
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[VioTrack] Live Stream Batch Report - {total_violations} Violations"
        msg["From"] = settings.SMTP_USERNAME
        msg["To"] = recipient

        part = MIMEText(html_content, "html")
        msg.attach(part)

        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USERNAME, recipient, msg.as_string())
        server.quit()
        logger.info(f"Batch report email successfully sent to {recipient}")
    except Exception as e:
        logger.error(f"Failed to send email to {recipient}: {e}")
