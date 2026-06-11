import re
from datetime import datetime, date


def format_full_report(report: dict, version: dict) -> str:
    """Build the full formatted IR text."""
    brief = version["brief_description"]
    # Strip NEW tags for copy text
    brief_clean = re.sub(r"<NEW>|</NEW>", "", brief)

    lines = [
        f"{report['battalion']} - {report['coy']} INCIDENT REPORT",
        "",
        "*Updates in bold*",
        "",
        "1) Nature of Incident:",
        report["type"],
        "",
        "2) Particulars of Individual:",
        report["serviceman_name"],
        "",
        "3) Date/ Time of Incident:",
        f"{report['date']}, {report['time']}H",
        "",
        "4) Location of Incident:",
        report["location"],
        "",
        "5) Coy/Branch involved:",
        report["coy"],
        "",
        "6) Brief Description:",
        brief_clean,
        "",
        "7) Follow-up action:",
        version.get("follow_up_action") or "NIL",
        "",
        "8) Ops Impact / Interim solution:",
        report.get("ops_impact") or "NIL",
        "",
        "9) Causal Analysis (Man, Mission, Machine, Medium, Management):",
        f"a) Primary: {report.get('causal_a', 'NIL')}",
        f"b) Secondary: {report.get('causal_b', 'NIL')}",
        f"c) Tertiary: {report.get('causal_c', 'NIL')}",
        "",
        "10) Date/ Time of Verbal Report to GSOC/HQ Sigs:",
        report.get("verbal_report") or "—",
        "",
        "11) Date/ Time of Written Report to GSOC/HQ Sigs:",
        report.get("written_report") or "—",
        "",
        "12) Unit Reporting Officer:",
        version.get("reporting_officer") or "—",
    ]
    return "\n".join(lines)


def format_report_preview(report: dict, version: dict) -> str:
    """Shorter preview for Telegram message (with Markdown)."""
    brief = version["brief_description"]
    brief_clean = re.sub(r"<NEW>|</NEW>", "", brief)

    return (
        f"📋 *{report['battalion']} - {report['coy']} INCIDENT REPORT*\n"
        f"_{report['date']}, {report['time']}H — {report['location']}_\n\n"
        f"*Type:* {report['type']}\n"
        f"*Individual:* {report['serviceman_name']}\n\n"
        f"*Brief Description:*\n{brief_clean}\n\n"
        f"*Follow-up:* {version.get('follow_up_action', 'NIL')}\n"
        f"*Reporting Officer:* {version.get('reporting_officer', '—')}"
    )


def format_report_card(report: dict) -> str:
    """One-line summary for dashboard lists."""
    status_icon = "🟢" if report["status"] == "open" else "⚫"
    due_str = ""
    if report.get("follow_up_date") and report["status"] == "open":
        try:
            fu = datetime.strptime(report["follow_up_date"], "%Y-%m-%d").date()
            days = (fu - date.today()).days
            if days < 0:
                due_str = f" 🔴 OVERDUE {abs(days)}d"
            elif days == 0:
                due_str = " 🔴 DUE TODAY"
            elif days <= 3:
                due_str = f" ⚠️ DUE IN {days}d"
        except Exception:
            pass
    return f"{status_icon} {report['id']} | {report['serviceman_name']} | {report['type']}{due_str}"


def parse_brief_with_new_tags(brief: str) -> str:
    """Convert <NEW> tags to Telegram bold markdown."""
    def bold_new(match):
        return f"*{match.group(1).strip()}*"
    return re.sub(r"<NEW>(.*?)</NEW>", bold_new, brief, flags=re.DOTALL)


def days_until(date_str: str):
    """Return number of days until a date string (YYYY-MM-DD)."""
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (target - date.today()).days
    except Exception:
        return None
