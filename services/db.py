import os
import uuid
from datetime import datetime

# Try to import Supabase — falls back to in-memory dict if not configured
try:
    from supabase import create_client
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
    if SUPABASE_URL and SUPABASE_KEY:
        db = create_client(SUPABASE_URL, SUPABASE_KEY)
        USE_SUPABASE = True
        print("✅ Supabase connected")
    else:
        db = None
        USE_SUPABASE = False
        print("⚠️  No Supabase config — using in-memory storage (data lost on restart)")
except Exception as e:
    db = None
    USE_SUPABASE = False
    print(f"⚠️  Supabase failed: {e} — using in-memory storage")

# In-memory fallback storage
_users = {}
_reports = {}
_versions = {}


# ── USER OPERATIONS ──────────────────────────────────────────────────────────

def get_user(telegram_id: int):
    if USE_SUPABASE:
        res = db.table("users").select("*").eq("telegram_id", telegram_id).execute()
        return res.data[0] if res.data else None
    return _users.get(telegram_id)


def save_user(telegram_id: int, name: str, rank: str, battalion: str, coy: str, default_officer: str):
    user = {
        "telegram_id": telegram_id,
        "name": name,
        "rank": rank,
        "battalion": battalion,
        "coy": coy,
        "default_officer": default_officer,
        "created_at": datetime.now().isoformat(),
    }
    if USE_SUPABASE:
        db.table("users").upsert(user).execute()
    else:
        _users[telegram_id] = user
    return user


def update_user_profile(telegram_id: int, battalion: str, coy: str, default_officer: str):
    if USE_SUPABASE:
        db.table("users").update({
            "battalion": battalion,
            "coy": coy,
            "default_officer": default_officer,
        }).eq("telegram_id", telegram_id).execute()
    else:
        if telegram_id in _users:
            _users[telegram_id]["battalion"] = battalion
            _users[telegram_id]["coy"] = coy
            _users[telegram_id]["default_officer"] = default_officer


# ── REPORT OPERATIONS ─────────────────────────────────────────────────────────

def generate_report_id():
    now = datetime.now()
    uid = str(uuid.uuid4())[:4].upper()
    return f"IR-{now.strftime('%m%y')}-{uid}"


def save_report(filed_by: int, report_data: dict, brief: str):
    report_id = generate_report_id()
    report = {
        "id": report_id,
        "filed_by": filed_by,
        "type": report_data["type"],
        "status": "open",
        "serviceman_name": report_data["name"],
        "date": report_data["date"],
        "time": report_data["time"],
        "location": report_data["location"],
        "battalion": report_data["battalion"],
        "coy": report_data["coy"],
        "ops_impact": report_data.get("ops_impact", "NIL"),
        "causal_a": "NIL",
        "causal_b": "NIL",
        "causal_c": "NIL",
        "verbal_report": report_data.get("verbal_report", "—"),
        "written_report": report_data.get("written_report", "—"),
        "follow_up_date": report_data.get("follow_up_date"),
        "raw_dump": report_data.get("raw_dump", ""),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    version = {
        "report_id": report_id,
        "version_number": 1,
        "brief_description": brief,
        "follow_up_action": report_data.get("follow_up_action", "NIL"),
        "reporting_officer": report_data.get("reporting_officer", ""),
        "created_at": datetime.now().isoformat(),
    }
    if USE_SUPABASE:
        db.table("reports").insert(report).execute()
        db.table("versions").insert(version).execute()
    else:
        _reports[report_id] = report
        _versions[report_id] = [version]
    return report_id


def get_report(report_id: str):
    if USE_SUPABASE:
        res = db.table("reports").select("*").eq("id", report_id).execute()
        return res.data[0] if res.data else None
    return _reports.get(report_id)


def get_latest_version(report_id: str):
    if USE_SUPABASE:
        res = db.table("versions").select("*").eq("report_id", report_id).order("version_number", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    versions = _versions.get(report_id, [])
    return versions[-1] if versions else None


def get_all_versions(report_id: str):
    if USE_SUPABASE:
        res = db.table("versions").select("*").eq("report_id", report_id).order("version_number").execute()
        return res.data
    return _versions.get(report_id, [])


def get_open_reports(filed_by: int):
    if USE_SUPABASE:
        res = db.table("reports").select("*").eq("filed_by", filed_by).eq("status", "open").order("created_at", desc=True).execute()
        return res.data
    return [r for r in _reports.values() if r["filed_by"] == filed_by and r["status"] == "open"]


def get_closed_reports(filed_by: int):
    if USE_SUPABASE:
        res = db.table("reports").select("*").eq("filed_by", filed_by).eq("status", "closed").order("created_at", desc=True).execute()
        return res.data
    return [r for r in _reports.values() if r["filed_by"] == filed_by and r["status"] == "closed"]


def add_version(report_id: str, new_brief: str, follow_up_action: str, reporting_officer: str):
    versions = get_all_versions(report_id)
    new_v_num = len(versions) + 1
    version = {
        "report_id": report_id,
        "version_number": new_v_num,
        "brief_description": new_brief,
        "follow_up_action": follow_up_action,
        "reporting_officer": reporting_officer,
        "created_at": datetime.now().isoformat(),
    }
    if USE_SUPABASE:
        db.table("versions").insert(version).execute()
        db.table("reports").update({"updated_at": datetime.now().isoformat()}).eq("id", report_id).execute()
    else:
        _versions[report_id].append(version)
        if report_id in _reports:
            _reports[report_id]["updated_at"] = datetime.now().isoformat()
    return version


def close_report(report_id: str):
    if USE_SUPABASE:
        db.table("reports").update({"status": "closed", "updated_at": datetime.now().isoformat()}).eq("id", report_id).execute()
    else:
        if report_id in _reports:
            _reports[report_id]["status"] = "closed"


def get_unit_reports_this_week(battalion: str):
    """Get all reports from this week for safety insights."""
    from datetime import timedelta
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    if USE_SUPABASE:
        res = db.table("reports").select("*").eq("battalion", battalion).gte("created_at", week_ago).execute()
        return res.data
    return [r for r in _reports.values() if r["battalion"] == battalion and r["created_at"] >= week_ago]
