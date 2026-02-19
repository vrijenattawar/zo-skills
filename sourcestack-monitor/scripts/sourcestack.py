"""SourceStack monitoring CLI — <YOUR_PRODUCT> Job Sourcing Pipeline.

Modes:
  - Ad hoc search: query SourceStack for jobs matching any criteria
  - Daily scan: automated monitoring of a predefined watchlist
  - Sweep: role-based broad search using archetype system
  - Review: inspect pending jobs, approve/reject for Notion publishing
  - Publish: push approved jobs to Notion Job board DB
  - Prune: lifecycle management (fresh → aging → stale → expired)
"""
import argparse
import json
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass, fields as dc_fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets"
WATCHLIST_PATH = ASSETS_DIR / "watchlist.yaml"
ARCHETYPES_PATH = ASSETS_DIR / "archetypes.yaml"
DB_PATH = SCRIPT_DIR.parent / "data" / "sourcestack.db"
API_BASE = "https://sourcestack-api.com"
LOG = logging.getLogger("sourcestack")
DAILY_CREDIT_CAP = 500
SCHEMA_VERSION = 2
NOTION_DB_ID = "29c5c3d6-a5db-81a3-9aa6-000b1c83fa24"

JOB_FIELDS = [
    "post_uuid",
    "job_name",
    "company_name",
    "company_url",
    "post_url",
    "post_apply_url",
    "post_full_text",
    "department",
    "seniority",
    "remote",
    "comp_range",
    "city",
    "country",
    "first_indexed",
    "last_indexed",
    "job_created_at",
    "job_published_at",
    "categories",
]


@dataclass
class JobRecord:
    post_uuid: str
    job_name: str
    company_name: str
    company_url: str
    post_url: Optional[str]
    post_apply_url: Optional[str]
    post_full_text: Optional[str]
    first_indexed: Optional[str]
    last_indexed: Optional[str]
    job_created_at: Optional[str]
    job_published_at: Optional[str]
    department: Optional[str]
    seniority: Optional[str]
    remote: Optional[bool]
    comp_range: Optional[str]
    city: Optional[str]
    country: Optional[str]
    categories: Optional[str] = None
    geo_list: Optional[str] = None
    archetype: Optional[str] = None
    freshness_score: Optional[float] = None
    freshness_tier: Optional[str] = None


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)


def get_api_key() -> str:
    key = os.environ.get("SOURCESTACK_API_KEY")
    if not key:
        LOG.error("SOURCESTACK_API_KEY environment variable is missing.")
        LOG.error("Add it at Settings > Advanced in Zo Computer.")
        sys.exit(1)
    return key


def ensure_paths() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def connect_db() -> sqlite3.Connection:
    ensure_paths()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables and run migrations to current schema version."""
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            post_uuid TEXT PRIMARY KEY,
            job_name TEXT,
            company_name TEXT,
            company_url TEXT,
            post_url TEXT,
            post_apply_url TEXT,
            post_full_text TEXT,
            department TEXT,
            seniority TEXT,
            remote BOOLEAN,
            comp_range TEXT,
            city TEXT,
            country TEXT,
            first_indexed TEXT,
            last_indexed TEXT,
            job_created_at TEXT,
            job_published_at TEXT,
            first_seen TEXT,
            last_seen TEXT,
            status TEXT DEFAULT 'active',
            scan_id TEXT,
            categories TEXT,
            geo_list TEXT,
            archetype TEXT,
            freshness_score REAL,
            freshness_tier TEXT,
            approval_status TEXT DEFAULT 'pending',
            job_type TEXT,
            notion_page_id TEXT,
            approved_at TEXT,
            pruned_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS scans (
            scan_id TEXT PRIMARY KEY,
            scan_type TEXT,
            timestamp TEXT,
            credits_used INTEGER,
            jobs_found INTEGER,
            jobs_new INTEGER,
            query_config TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            date TEXT NOT NULL,
            credits_used INTEGER NOT NULL,
            scan_id TEXT,
            operation TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()
    _run_migrations(conn)


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Add columns that may be missing from older schema versions."""
    c = conn.cursor()
    c.execute("SELECT value FROM schema_meta WHERE key = 'version'")
    row = c.fetchone()
    current = int(row["value"]) if row else 1

    if current < 2:
        new_cols = {
            "categories": "TEXT",
            "geo_list": "TEXT",
            "archetype": "TEXT",
            "freshness_score": "REAL",
            "freshness_tier": "TEXT",
            "approval_status": "TEXT DEFAULT 'pending'",
            "job_type": "TEXT",
            "notion_page_id": "TEXT",
            "approved_at": "TEXT",
            "pruned_at": "TEXT",
        }
        existing = {info[1] for info in c.execute("PRAGMA table_info(jobs)").fetchall()}
        for col, coltype in new_cols.items():
            if col not in existing:
                c.execute(f"ALTER TABLE jobs ADD COLUMN {col} {coltype}")
                LOG.info("Migration: added column jobs.%s (%s)", col, coltype)
        conn.commit()

    c.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Archetype system
# ---------------------------------------------------------------------------

def load_archetypes() -> Dict[str, Any]:
    if not ARCHETYPES_PATH.exists():
        LOG.warning("Archetypes config not found at %s", ARCHETYPES_PATH)
        return {"archetypes": {}, "geo_lists": {}}
    with ARCHETYPES_PATH.open() as fh:
        data = yaml.safe_load(fh) or {}
    return data


def list_archetypes() -> Dict[str, Dict]:
    data = load_archetypes()
    return data.get("archetypes", {})


def get_archetype_titles(archetype_names: List[str]) -> List[str]:
    archetypes = list_archetypes()
    titles: List[str] = []
    for name in archetype_names:
        arch = archetypes.get(name)
        if arch:
            titles.extend(arch.get("titles", []))
        else:
            LOG.warning("Unknown archetype: %s", name)
    return titles


def classify_archetype(job_name: str, categories_str: Optional[str] = None) -> Optional[str]:
    archetypes = list_archetypes()
    job_lower = (job_name or "").lower()
    for arch_name, arch_def in archetypes.items():
        for title in arch_def.get("titles", []):
            if title.lower() in job_lower:
                return arch_name
    return None


# ---------------------------------------------------------------------------
# Geo-list classification
# ---------------------------------------------------------------------------

def load_geo_lists() -> Dict[str, Any]:
    data = load_archetypes()
    return data.get("geo_lists", {})


def classify_geo(job: Dict[str, Any]) -> str:
    geo = load_geo_lists()
    city = (job.get("city") or "").strip()
    country = (job.get("country") or "").strip()
    remote = job.get("remote", False)

    nyc_cfg = geo.get("nyc", {})
    nyc_cities = [c.lower() for c in nyc_cfg.get("cities", [])]
    if city.lower() in nyc_cities and country == nyc_cfg.get("country", "United States"):
        return "nyc"

    us_cfg = geo.get("us-remote", {})
    if country == us_cfg.get("country", "United States"):
        if remote:
            return "us-remote"
        us_cities = [c.lower() for c in us_cfg.get("fallback_cities", [])]
        if city.lower() in us_cities:
            return "us-remote"
        if city.lower() in nyc_cities:
            return "nyc"
        return "us-remote"

    intl_cfg = geo.get("intl-remote", {})
    if remote and country != intl_cfg.get("exclude_country", "United States"):
        return "intl-remote"

    return "unclassified"


# ---------------------------------------------------------------------------
# Freshness scoring
# ---------------------------------------------------------------------------

def compute_freshness(first_indexed: Optional[str]) -> Dict[str, Any]:
    if not first_indexed:
        return {"days": -1, "score": -1.0, "tier": "unknown"}
    try:
        dt = datetime.fromisoformat(first_indexed.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return {"days": -1, "score": -1.0, "tier": "unknown"}

    now = datetime.now(timezone.utc)
    days = (now - dt).days
    score = round(days / 30.0, 3)

    if days < 0:
        tier = "unknown"
    elif days <= 14:
        tier = "fresh"
    elif days <= 29:
        tier = "aging"
    else:
        tier = "stale"

    return {"days": days, "score": score, "tier": tier}


# ---------------------------------------------------------------------------
# Credit tracking
# ---------------------------------------------------------------------------

def log_credits(conn: sqlite3.Connection, credits_used: int, scan_id: str, operation: str) -> None:
    now = datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO credit_log (timestamp, date, credits_used, scan_id, operation) VALUES (?, ?, ?, ?, ?)",
        (now.isoformat(), now.strftime("%Y-%m-%d"), credits_used, scan_id, operation),
    )
    conn.commit()


def get_daily_credit_usage(conn: sqlite3.Connection) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(credits_used), 0) as total FROM credit_log WHERE date = ?",
        (today,),
    ).fetchone()
    return int(row["total"])


def check_credit_budget(conn: sqlite3.Connection, estimated_cost: int = 0) -> Tuple[bool, int, int]:
    used = get_daily_credit_usage(conn)
    remaining = DAILY_CREDIT_CAP - used
    ok = (used + estimated_cost) <= DAILY_CREDIT_CAP
    return ok, used, remaining


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def load_watchlist() -> Dict[str, Any]:
    if not WATCHLIST_PATH.exists():
        LOG.warning("Watchlist not found at %s. Using empty defaults.", WATCHLIST_PATH)
        return {"companies": [], "roles": [], "filters": {}}
    with WATCHLIST_PATH.open() as fh:
        data = yaml.safe_load(fh) or {}
    return {
        "companies": data.get("companies", []),
        "roles": data.get("roles", []),
        "filters": data.get("filters", {}),
    }


def save_watchlist(data: Dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        LOG.info("Dry-run enabled; not saving watchlist.")
        return
    with WATCHLIST_PATH.open("w") as fh:
        yaml.safe_dump(data, fh)
    LOG.info("Updated watchlist saved to %s.", WATCHLIST_PATH)


# ---------------------------------------------------------------------------
# API layer
# ---------------------------------------------------------------------------

def post_to_api(
    path: str,
    payload: Dict[str, Any],
    api_key: str,
    conn: Optional[sqlite3.Connection] = None,
    scan_id: str = "",
    operation: str = "api_call",
) -> Tuple[Dict[str, Any], Optional[int]]:
    if conn:
        ok, used, remaining = check_credit_budget(conn)
        if not ok:
            LOG.error(
                "Daily credit cap reached (%d/%d used). Skipping API call.",
                used, DAILY_CREDIT_CAP,
            )
            return {"data": [], "error": "credit_cap_reached"}, 0

    url = f"{API_BASE}/{path.lstrip('/')}"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    LOG.debug("POST %s %s", url, payload)
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        LOG.error("API request failed (%s): %s", response.status_code, response.text)
        raise

    credits_header = response.headers.get("X-SOURCESTACK-CREDITS-REMAINING")
    credits_remaining: Optional[int] = None
    if credits_header is not None:
        try:
            credits_remaining = int(credits_header)
        except ValueError:
            pass
        LOG.info("Credits remaining: %s", credits_remaining)

    result = response.json()
    job_count = len(result.get("data") or result.get("results") or [])
    if conn and job_count > 0:
        log_credits(conn, job_count, scan_id, operation)

    return result, credits_remaining


def get_quota(api_key: str) -> Dict[str, Any]:
    url = f"{API_BASE}/quota"
    headers = {"X-API-KEY": api_key}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------

def build_filters(watchlist: Dict[str, Any]) -> List[Dict[str, Any]]:
    filters = [
        {"field": "last_indexed", "operator": "GREATER_THAN", "value": "LAST_1D"}
    ]
    companies = [entry.get("url") for entry in watchlist.get("companies", []) if entry.get("url")]
    if companies:
        filters.append({"field": "company_url", "operator": "IN", "value": companies})
    roles = [role for role in watchlist.get("roles", []) if role]
    if roles:
        filters.append({"field": "job_name", "operator": "CONTAINS_ANY", "value": roles})
    filters_config = watchlist.get("filters", {})
    countries = filters_config.get("countries") or []
    if countries:
        filters.append({"field": "country", "operator": "IN", "value": countries})
    seniority = filters_config.get("seniority") or []
    if seniority:
        filters.append({"field": "seniority", "operator": "IN", "value": seniority})
    if filters_config.get("remote_only"):
        filters.append({"field": "remote", "operator": "EQUALS", "value": True})
    return filters


def build_sweep_filters(
    archetype_names: List[str],
    geo: str,
) -> List[Dict[str, Any]]:
    """Build SourceStack API filters for a role-based sweep."""
    filters: List[Dict[str, Any]] = []

    titles = get_archetype_titles(archetype_names)
    if titles:
        filters.append({"field": "job_name", "operator": "CONTAINS_ANY", "value": titles})

    archetypes_data = list_archetypes()
    all_cats: set = set()
    for name in archetype_names:
        arch = archetypes_data.get(name, {})
        for cat in arch.get("categories", []):
            all_cats.add(cat)
    if all_cats:
        filters.append({"field": "categories", "operator": "CONTAINS_ANY", "value": list(all_cats)})

    geo_lists = load_geo_lists()
    if geo == "nyc":
        cfg = geo_lists.get("nyc", {})
        filters.append({"field": "country", "operator": "EQUALS", "value": cfg.get("country", "United States")})
        filters.append({"field": "city", "operator": "IN", "value": cfg.get("cities", ["New York"])})
    elif geo == "us-remote":
        cfg = geo_lists.get("us-remote", {})
        filters.append({"field": "country", "operator": "EQUALS", "value": cfg.get("country", "United States")})
        filters.append({"field": "remote", "operator": "EQUALS", "value": True})
    elif geo == "intl-remote":
        cfg = geo_lists.get("intl-remote", {})
        filters.append({"field": "remote", "operator": "EQUALS", "value": True})
        filters.append({"field": "country", "operator": "NOT_EQUALS", "value": cfg.get("exclude_country", "United States")})
    elif geo == "all":
        pass
    else:
        LOG.warning("Unknown geo list: %s. No geo filters applied.", geo)

    return filters


# ---------------------------------------------------------------------------
# Normalization and persistence
# ---------------------------------------------------------------------------

def normalize_job(job: Dict[str, Any]) -> JobRecord:
    cats_raw = job.get("categories")
    cats_str = json.dumps(cats_raw) if isinstance(cats_raw, list) else str(cats_raw) if cats_raw else None

    geo = classify_geo(job)
    archetype = classify_archetype(job.get("job_name", ""), cats_str)
    fresh = compute_freshness(job.get("first_indexed"))

    return JobRecord(
        post_uuid=job.get("post_uuid"),
        job_name=job.get("job_name"),
        company_name=job.get("company_name"),
        company_url=job.get("company_url"),
        post_url=job.get("post_url"),
        post_apply_url=job.get("post_apply_url"),
        post_full_text=job.get("post_full_text"),
        first_indexed=job.get("first_indexed"),
        last_indexed=job.get("last_indexed"),
        job_created_at=job.get("job_created_at"),
        job_published_at=job.get("job_published_at"),
        department=job.get("department"),
        seniority=job.get("seniority"),
        remote=job.get("remote"),
        comp_range=job.get("comp_range"),
        city=job.get("city"),
        country=job.get("country"),
        categories=cats_str,
        geo_list=geo,
        archetype=archetype,
        freshness_score=fresh["score"],
        freshness_tier=fresh["tier"],
    )


def persist_jobs(
    conn: sqlite3.Connection,
    jobs: Iterable[JobRecord],
    scan_id: str,
    dry_run: bool,
) -> Dict[str, int]:
    stats = {"found": 0, "new": 0, "updated": 0}
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.cursor()

    for job in jobs:
        if not job.post_uuid:
            continue
        stats["found"] += 1
        cursor.execute("SELECT post_uuid FROM jobs WHERE post_uuid = ?", (job.post_uuid,))
        row = cursor.fetchone()

        if dry_run:
            stats["updated" if row else "new"] += 1
            continue

        if row:
            stats["updated"] += 1
            cursor.execute(
                """
                UPDATE jobs
                SET last_seen = ?, status = 'active', scan_id = ?,
                    freshness_score = ?, freshness_tier = ?,
                    last_indexed = COALESCE(?, last_indexed)
                WHERE post_uuid = ?
                """,
                (now, scan_id, job.freshness_score, job.freshness_tier, job.last_indexed, job.post_uuid),
            )
        else:
            stats["new"] += 1
            cursor.execute(
                """
                INSERT INTO jobs(
                    post_uuid, job_name, company_name, company_url, post_url, post_apply_url,
                    post_full_text, department, seniority, remote, comp_range, city, country,
                    first_indexed, last_indexed, job_created_at, job_published_at,
                    first_seen, last_seen, scan_id, categories,
                    geo_list, archetype, freshness_score, freshness_tier, approval_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    job.post_uuid, job.job_name, job.company_name, job.company_url,
                    job.post_url, job.post_apply_url, job.post_full_text,
                    job.department, job.seniority, job.remote, job.comp_range,
                    job.city, job.country, job.first_indexed, job.last_indexed,
                    job.job_created_at, job.job_published_at, now, now, scan_id,
                    job.categories, job.geo_list, job.archetype,
                    job.freshness_score, job.freshness_tier,
                ),
            )

    if not dry_run:
        conn.commit()
    return stats


def record_scan(
    conn: sqlite3.Connection,
    scan_id: str,
    scan_type: str,
    found: int,
    new: int,
    query: Dict[str, Any],
    credits_used: Optional[int],
) -> None:
    conn.execute(
        """
        INSERT INTO scans(scan_id, scan_type, timestamp, credits_used, jobs_found, jobs_new, query_config)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (scan_id, scan_type, datetime.now(timezone.utc).isoformat(), credits_used, found, new, json.dumps(query)),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> None:
    """Run the automated watchlist scan."""
    api_key = get_api_key()
    conn = connect_db()
    watchlist = load_watchlist()
    filters = build_filters(watchlist)
    payload = {"filters": filters, "fields": JOB_FIELDS, "limit": 2000}
    scan_id = f"scan-{datetime.now(timezone.utc).isoformat()}"

    LOG.info("Starting daily scan (%s).", scan_id)
    if args.dry_run:
        LOG.info("Dry-run: query will not persist results.")
        LOG.info("Payload: %s", json.dumps(payload, indent=2))
        return

    response_data, credits = post_to_api("jobs", payload, api_key, conn, scan_id, "watchlist_scan")
    if response_data.get("error") == "credit_cap_reached":
        return

    jobs_data = response_data.get("data") or response_data.get("results") or []
    job_records = [normalize_job(job) for job in jobs_data]
    stats = persist_jobs(conn, job_records, scan_id, False)
    record_scan(conn, scan_id, "daily", stats["found"], stats["new"], payload, credits)
    LOG.info("Scan complete. Found %s jobs (%s new, %s updated).", stats["found"], stats["new"], stats["updated"])


def cmd_sweep(args: argparse.Namespace) -> None:
    """Run a role-based broad search using archetypes."""
    api_key = get_api_key()
    conn = connect_db()

    ok, used, remaining = check_credit_budget(conn)
    if not ok:
        LOG.error("Daily credit cap reached (%d/%d). Cannot sweep.", used, DAILY_CREDIT_CAP)
        return
    LOG.info("Credit budget: %d/%d used, %d remaining.", used, DAILY_CREDIT_CAP, remaining)

    all_archetypes = list(list_archetypes().keys())
    if args.all_archetypes:
        archetype_names = all_archetypes
    elif args.archetypes:
        archetype_names = [a.strip() for a in args.archetypes.split(",")]
    else:
        archetype_names = all_archetypes

    filters = build_sweep_filters(archetype_names, args.geo)
    payload = {"filters": filters, "fields": JOB_FIELDS, "limit": args.limit}
    scan_id = f"sweep-{args.geo}-{datetime.now(timezone.utc).isoformat()}"

    LOG.info("Sweep: geo=%s archetypes=%s limit=%d", args.geo, archetype_names, args.limit)

    if args.dry_run:
        LOG.info("Dry-run payload:\n%s", json.dumps(payload, indent=2))
        LOG.info("Would search %d title patterns across %d archetypes.", len(get_archetype_titles(archetype_names)), len(archetype_names))
        return

    response_data, credits = post_to_api("jobs", payload, api_key, conn, scan_id, f"sweep_{args.geo}")
    if response_data.get("error") == "credit_cap_reached":
        return

    jobs_data = response_data.get("data") or response_data.get("results") or []
    job_records = [normalize_job(job) for job in jobs_data]
    stats = persist_jobs(conn, job_records, scan_id, False)
    record_scan(conn, scan_id, f"sweep_{args.geo}", stats["found"], stats["new"], payload, credits)
    LOG.info("Sweep complete. Found %s jobs (%s new, %s updated).", stats["found"], stats["new"], stats["updated"])


def cmd_review(args: argparse.Namespace) -> None:
    """Review pending jobs or approve/reject them."""
    conn = connect_db()

    if args.approve:
        _review_approve(conn, args.approve, args.type, args.dry_run)
        return
    if args.reject:
        _review_reject(conn, args.reject, args.dry_run)
        return

    sql = """
        SELECT post_uuid, company_name, job_name, city, country, remote, comp_range,
               geo_list, archetype, freshness_tier, freshness_score, approval_status, first_indexed
        FROM jobs
        WHERE approval_status = 'pending'
    """
    params: List[Any] = []

    if args.geo:
        sql += " AND geo_list = ?"
        params.append(args.geo)
    if args.archetype:
        sql += " AND archetype = ?"
        params.append(args.archetype)
    if args.fresh_only:
        sql += " AND freshness_tier = 'fresh'"

    sql += " ORDER BY freshness_score ASC, company_name ASC LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(sql, params).fetchall()
    LOG.info("--- Pending Jobs (%d) ---", len(rows))
    for i, row in enumerate(rows, 1):
        remote_tag = "🏠" if row["remote"] else "🏢"
        comp = row["comp_range"] or "—"
        geo = row["geo_list"] or "?"
        arch = row["archetype"] or "?"
        tier = row["freshness_tier"] or "?"
        fresh_info = compute_freshness(row["first_indexed"])
        days = fresh_info["days"]
        location = f"{row['city'] or '?'}, {row['country'] or '?'}"
        print(
            f"  {i:3d}. [{tier:6s} {days:3d}d] {remote_tag} {row['company_name']:30s} | "
            f"{row['job_name']:45s} | {location:25s} | {comp:20s} | "
            f"geo:{geo:12s} arch:{arch:20s} | {row['post_uuid'][:12]}"
        )

    if not rows:
        LOG.info("No pending jobs matching filters.")


def _review_approve(conn: sqlite3.Connection, uuids: List[str], job_type: Optional[str], dry_run: bool) -> None:
    now = datetime.now(timezone.utc).isoformat()
    jtype = job_type or "source_job"
    resolved = _resolve_uuids(conn, uuids)
    for uuid in resolved:
        if dry_run:
            LOG.info("Dry-run: would approve %s as %s", uuid[:12], jtype)
            continue
        conn.execute(
            "UPDATE jobs SET approval_status = 'approved', job_type = ?, approved_at = ? WHERE post_uuid = ?",
            (jtype, now, uuid),
        )
    if not dry_run:
        conn.commit()
    LOG.info("Approved %d job(s) as '%s'.", len(resolved), jtype)


def _review_reject(conn: sqlite3.Connection, uuids: List[str], dry_run: bool) -> None:
    resolved = _resolve_uuids(conn, uuids)
    for uuid in resolved:
        if dry_run:
            LOG.info("Dry-run: would reject %s", uuid[:12])
            continue
        conn.execute("UPDATE jobs SET approval_status = 'rejected' WHERE post_uuid = ?", (uuid,))
    if not dry_run:
        conn.commit()
    LOG.info("Rejected %d job(s).", len(resolved))


def _resolve_uuids(conn: sqlite3.Connection, uuids: List[str]) -> List[str]:
    """Resolve UUID prefixes to full UUIDs. Supports partial matching."""
    resolved: List[str] = []
    for prefix in uuids:
        row = conn.execute("SELECT post_uuid FROM jobs WHERE post_uuid = ?", (prefix,)).fetchone()
        if row:
            resolved.append(row["post_uuid"])
            continue
        matches = conn.execute(
            "SELECT post_uuid FROM jobs WHERE post_uuid LIKE ?", (f"{prefix}%",)
        ).fetchall()
        if len(matches) == 1:
            resolved.append(matches[0]["post_uuid"])
            LOG.info("Resolved prefix %s → %s", prefix, matches[0]["post_uuid"][:12])
        elif len(matches) > 1:
            LOG.warning("Prefix %s matches %d jobs — skipping (be more specific).", prefix, len(matches))
        else:
            LOG.warning("No job found for UUID/prefix: %s", prefix)
    return resolved


def cmd_search(args: argparse.Namespace) -> None:
    """Run an ad hoc SourceStack search."""
    api_key = get_api_key()
    conn = connect_db()
    filters: List[Dict[str, Any]] = []
    if args.company_url:
        filters.append({"field": "company_url", "operator": "EQUALS", "value": args.company_url})
    if args.role:
        filters.append({"field": "job_name", "operator": "CONTAINS_ANY", "value": args.role.split(",")})
    if args.country:
        filters.append({"field": "country", "operator": "EQUALS", "value": args.country})
    payload = {"filters": filters, "fields": JOB_FIELDS, "limit": args.limit}
    LOG.info("Running ad hoc search: %s", args)
    response_data, _ = post_to_api("jobs", payload, api_key, conn, f"adhoc-{datetime.now(timezone.utc).isoformat()}", "adhoc")
    jobs = response_data.get("data") or response_data.get("results") or []
    for job in jobs:
        LOG.info("%s | %s | %s", job.get("company_name"), job.get("job_name"), job.get("post_url"))


def cmd_query(args: argparse.Namespace) -> None:
    """Query the local SQLite cache."""
    conn = connect_db()
    sql = """
        SELECT post_uuid, company_name, job_name, post_url, status,
               geo_list, archetype, freshness_tier, approval_status, last_seen
        FROM jobs
    """
    clauses: List[str] = []
    params: List[Any] = []

    if args.company:
        clauses.append("company_name LIKE ?")
        params.append(f"%{args.company}%")
    if args.status:
        clauses.append("status = ?")
        params.append(args.status)
    if args.text:
        clauses.append("post_full_text LIKE ?")
        params.append(f"%{args.text}%")
    if args.geo:
        clauses.append("geo_list = ?")
        params.append(args.geo)
    if args.archetype:
        clauses.append("archetype = ?")
        params.append(args.archetype)
    if args.since_days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=args.since_days)).isoformat()
        clauses.append("last_seen >= ?")
        params.append(cutoff)

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY last_seen DESC LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(sql, params).fetchall()
    LOG.info("%s rows returned.", len(rows))
    for row in rows:
        LOG.info(
            "%s | %s | geo:%s | arch:%s | %s | %s | %s",
            row["company_name"], row["job_name"], row["geo_list"] or "?",
            row["archetype"] or "?", row["freshness_tier"] or "?",
            row["approval_status"], row["post_url"],
        )


def cmd_watchlist(args: argparse.Namespace) -> None:
    """Inspect or edit the watchlist."""
    data = load_watchlist()
    if not args.add_company and not args.remove_company and not args.add_role and not args.remove_role:
        LOG.info(
            "Current watchlist:\nCompanies: %s\nRoles: %s\nFilters: %s",
            data["companies"], data["roles"], data["filters"],
        )
        return
    companies = data["companies"]
    roles = data["roles"]
    if args.add_company:
        url, label = args.add_company.split(":", 1) if ":" in args.add_company else (args.add_company, args.add_company)
        if not any(entry.get("url") == url for entry in companies):
            companies.append({"url": url, "label": label})
    if args.remove_company:
        companies = [entry for entry in companies if entry.get("url") != args.remove_company]
    if args.add_role and args.add_role not in roles:
        roles.append(args.add_role)
    if args.remove_role:
        roles = [role for role in roles if role != args.remove_role]
    data["companies"] = companies
    data["roles"] = roles
    save_watchlist(data, args.dry_run)


def cmd_archetypes(args: argparse.Namespace) -> None:
    """List all archetypes and their title patterns."""
    archetypes = list_archetypes()
    if not archetypes:
        LOG.info("No archetypes configured.")
        return
    total_titles = 0
    for name, defn in sorted(archetypes.items()):
        titles = defn.get("titles", [])
        total_titles += len(titles)
        cats = defn.get("categories", [])
        print(f"\n  {name}")
        print(f"    Categories: {', '.join(cats)}")
        print(f"    Titles ({len(titles)}):")
        for t in titles:
            print(f"      - {t}")
    print(f"\n  Total: {len(archetypes)} archetypes, {total_titles} title patterns")


def cmd_credits(args: argparse.Namespace) -> None:
    """Show daily credit usage and budget."""
    conn = connect_db()
    used = get_daily_credit_usage(conn)
    remaining = DAILY_CREDIT_CAP - used
    api_key = get_api_key()
    quota = get_quota(api_key)
    account_remaining = quota.get("credits_remaining") or quota.get("message", "?")

    print(f"\n  Daily Budget")
    print(f"    Used today:     {used:,}")
    print(f"    Daily cap:      {DAILY_CREDIT_CAP:,}")
    print(f"    Remaining:      {remaining:,}")
    print(f"\n  Account Total")
    print(f"    Remaining:      {account_remaining}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT operation, SUM(credits_used) as total FROM credit_log WHERE date = ? GROUP BY operation",
        (today,),
    ).fetchall()
    if rows:
        print(f"\n  Today's Usage by Operation:")
        for row in rows:
            print(f"    {row['operation']:25s} {row['total']:>6,} credits")


def cmd_delta(args: argparse.Namespace) -> None:
    """Show recent job changes."""
    conn = connect_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.since_days)
    rows = conn.execute(
        "SELECT post_uuid, company_name, job_name, post_url, status, geo_list, archetype FROM jobs WHERE last_seen >= ? ORDER BY last_seen DESC",
        (cutoff.isoformat(),),
    ).fetchall()
    LOG.info("%s jobs changed in the last %s days", len(rows), args.since_days)
    for row in rows:
        LOG.info(
            "%s | %s | %s | geo:%s | arch:%s",
            row["company_name"], row["job_name"], row["status"],
            row["geo_list"] or "?", row["archetype"] or "?",
        )


def cmd_lifecycle(args: argparse.Namespace) -> None:
    """Run lifecycle state transitions on all active jobs."""
    conn = connect_db()
    stats = {"aged": 0, "staled": 0, "expired": 0, "expunged": 0}
    now = datetime.now(timezone.utc)

    rows = conn.execute(
        "SELECT post_uuid, first_indexed, status, freshness_tier, notion_page_id, pruned_at FROM jobs WHERE status = 'active'"
    ).fetchall()

    for row in rows:
        fresh = compute_freshness(row["first_indexed"])
        days = fresh["days"]
        current_tier = row["freshness_tier"]
        new_tier = fresh["tier"]

        if current_tier == "fresh" and new_tier == "aging":
            stats["aged"] += 1
            if not args.dry_run:
                conn.execute(
                    "UPDATE jobs SET freshness_tier = 'aging', freshness_score = ? WHERE post_uuid = ?",
                    (fresh["score"], row["post_uuid"]),
                )
            else:
                LOG.info("Would age: %s (day %d)", row["post_uuid"][:12], days)

        elif new_tier == "stale" and current_tier != "stale":
            stats["staled"] += 1
            if not args.dry_run:
                conn.execute(
                    "UPDATE jobs SET freshness_tier = 'stale', status = 'closed', freshness_score = ? WHERE post_uuid = ?",
                    (fresh["score"], row["post_uuid"]),
                )
            else:
                LOG.info("Would close (stale): %s (day %d)", row["post_uuid"][:12], days)

    expired_rows = conn.execute(
        "SELECT post_uuid, first_indexed FROM jobs WHERE status = 'closed'"
    ).fetchall()
    for row in expired_rows:
        fresh = compute_freshness(row["first_indexed"])
        if fresh["days"] >= 60:
            stats["expired"] += 1
            if not args.dry_run:
                conn.execute("DELETE FROM jobs WHERE post_uuid = ?", (row["post_uuid"],))
            else:
                LOG.info("Would expire (delete): %s (day %d)", row["post_uuid"][:12], fresh["days"])

    if not args.dry_run:
        conn.commit()

    LOG.info(
        "Lifecycle complete. Aged: %d, Staled/closed: %d, Expired/deleted: %d, Expunged: %d",
        stats["aged"], stats["staled"], stats["expired"], stats["expunged"],
    )
    return stats


def cmd_prune(args: argparse.Namespace) -> None:
    """Run lifecycle + Notion pruning in one command."""
    LOG.info("Running lifecycle pass...")
    cmd_lifecycle(args)
    LOG.info("Run 'publish' or 'notion-prune' commands for Notion operations.")


def cmd_publish(args: argparse.Namespace) -> None:
    """Prepare approved jobs for Notion push. Outputs JSON for Zo to execute via Notion API."""
    conn = connect_db()
    rows = conn.execute(
        """
        SELECT post_uuid, job_name, company_name, comp_range, city, country, remote,
               geo_list, archetype, department, seniority, post_url, post_apply_url, job_type
        FROM jobs
        WHERE approval_status = 'approved' AND (notion_page_id IS NULL OR notion_page_id = '')
        """
    ).fetchall()

    if not rows:
        LOG.info("No approved jobs pending Notion sync.")
        return

    LOG.info("--- Jobs to Publish to Notion (%d) ---", len(rows))
    publish_queue = []
    for row in rows:
        location = f"{row['city'] or '?'}, {row['country'] or '?'}"
        setup = "Remote" if row["remote"] else "In office"
        job_type_label = "Direct Apply" if row["job_type"] == "direct_apply" else "Source Job"
        name = f"{row['company_name']} — {row['job_name']}"

        entry = {
            "post_uuid": row["post_uuid"],
            "notion_properties": {
                "Name": name,
                "Job title": row["job_name"],
                "Company": row["company_name"],
                "Comp": row["comp_range"] or "",
                "Location": [location],
                "Setup": [setup],
                "Status": "Active",
                "Hiring Type": "Full-time",
                "APPLICATION LINK": row["post_url"] or row["post_apply_url"] or "",
                "Type": job_type_label,
            },
        }
        publish_queue.append(entry)

        if not args.dry_run:
            LOG.info(
                "  → %s | %s | %s | %s",
                row["company_name"], row["job_name"], location, job_type_label,
            )

    if args.dry_run:
        print(json.dumps(publish_queue, indent=2))
        LOG.info("Dry-run: %d jobs would be published.", len(publish_queue))
        return

    print(json.dumps(publish_queue, indent=2))
    LOG.info(
        "%d jobs ready for Notion push. Use Zo to execute: "
        "'publish these jobs to the Notion Job board'.",
        len(publish_queue),
    )


def cmd_notion_prune(args: argparse.Namespace) -> None:
    """List stale jobs that should be archived in Notion."""
    conn = connect_db()
    rows = conn.execute(
        """
        SELECT post_uuid, job_name, company_name, notion_page_id, freshness_tier, first_indexed
        FROM jobs
        WHERE (status = 'closed' OR freshness_tier = 'stale')
          AND notion_page_id IS NOT NULL
          AND notion_page_id != ''
          AND (pruned_at IS NULL OR pruned_at = '')
        """
    ).fetchall()

    if not rows:
        LOG.info("No stale jobs to prune from Notion.")
        return

    LOG.info("--- Jobs to Prune from Notion (%d) ---", len(rows))
    prune_queue = []
    for row in rows:
        fresh = compute_freshness(row["first_indexed"])
        entry = {
            "post_uuid": row["post_uuid"],
            "notion_page_id": row["notion_page_id"],
            "company": row["company_name"],
            "title": row["job_name"],
            "days_old": fresh["days"],
            "tier": row["freshness_tier"],
        }
        prune_queue.append(entry)
        LOG.info(
            "  ✂ %s | %s | %dd old | page: %s",
            row["company_name"], row["job_name"], fresh["days"], row["notion_page_id"][:12],
        )

    if args.dry_run:
        print(json.dumps(prune_queue, indent=2))
        LOG.info("Dry-run: %d jobs would be pruned.", len(prune_queue))
        return

    print(json.dumps(prune_queue, indent=2))
    LOG.info(
        "%d stale jobs ready for Notion archival. Use Zo to execute.",
        len(prune_queue),
    )


def mark_published(post_uuid: str, notion_page_id: str) -> None:
    """Update local DB after successful Notion push."""
    conn = connect_db()
    conn.execute(
        "UPDATE jobs SET notion_page_id = ? WHERE post_uuid = ?",
        (notion_page_id, post_uuid),
    )
    conn.commit()
    LOG.info("Marked %s as published (notion_page_id=%s).", post_uuid[:12], notion_page_id[:12])


def mark_pruned(post_uuid: str) -> None:
    """Update local DB after successful Notion archival."""
    conn = connect_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE jobs SET pruned_at = ? WHERE post_uuid = ?",
        (now, post_uuid),
    )
    conn.commit()
    LOG.info("Marked %s as pruned.", post_uuid[:12])


def cmd_quota(args: argparse.Namespace) -> None:
    api_key = get_api_key()
    result = get_quota(api_key)
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="SourceStack CLI — <YOUR_PRODUCT> Job Sourcing Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="skip stateful writes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    scan_p = subparsers.add_parser("scan", help="Run the automated watchlist scan")
    scan_p.set_defaults(func=cmd_scan)

    # sweep
    sweep_p = subparsers.add_parser("sweep", help="Role-based broad search using archetypes")
    sweep_p.add_argument("--geo", required=True, choices=["nyc", "us-remote", "intl-remote", "all"], help="Geography list")
    sweep_p.add_argument("--archetypes", help="Comma-separated archetype names")
    sweep_p.add_argument("--all-archetypes", action="store_true", help="Use all defined archetypes")
    sweep_p.add_argument("--limit", type=int, default=100, help="Max results")
    sweep_p.set_defaults(func=cmd_sweep)

    # review
    review_p = subparsers.add_parser("review", help="Review pending jobs, approve/reject")
    review_p.add_argument("--pending", action="store_true", help="Show pending jobs")
    review_p.add_argument("--geo", help="Filter by geo list")
    review_p.add_argument("--archetype", help="Filter by archetype")
    review_p.add_argument("--fresh-only", action="store_true", help="Only show fresh (0-14d) jobs")
    review_p.add_argument("--limit", type=int, default=50, help="Max results")
    review_p.add_argument("--approve", nargs="+", help="Approve job(s) by UUID")
    review_p.add_argument("--reject", nargs="+", help="Reject job(s) by UUID")
    review_p.add_argument("--type", choices=["direct_apply", "source_job"], default="source_job", help="Job type for approval")
    review_p.set_defaults(func=cmd_review)

    # search
    search_p = subparsers.add_parser("search", help="Ad hoc SourceStack search")
    search_p.add_argument("--company-url", help="Company URL to filter")
    search_p.add_argument("--role", help="Role/title to filter (comma separated)")
    search_p.add_argument("--country", help="Country name")
    search_p.add_argument("--limit", type=int, default=25)
    search_p.set_defaults(func=cmd_search)

    # query
    query_p = subparsers.add_parser("query", help="Query local SQLite cache")
    query_p.add_argument("--company", help="Partial company name")
    query_p.add_argument("--text", help="Search in job description text")
    query_p.add_argument("--status", choices=["active", "closed", "disappeared"])
    query_p.add_argument("--geo", choices=["nyc", "us-remote", "intl-remote", "unclassified"])
    query_p.add_argument("--archetype", help="Filter by archetype name")
    query_p.add_argument("--since-days", type=int, default=7)
    query_p.add_argument("--limit", type=int, default=25)
    query_p.set_defaults(func=cmd_query)

    # watchlist
    watch_p = subparsers.add_parser("watchlist", help="Inspect or edit the watchlist")
    watch_p.add_argument("--add-company", help="Add company in format url:Label")
    watch_p.add_argument("--remove-company", help="Remove company by URL")
    watch_p.add_argument("--add-role", help="Add role keyword")
    watch_p.add_argument("--remove-role", help="Remove role keyword")
    watch_p.set_defaults(func=cmd_watchlist)

    # archetypes
    arch_p = subparsers.add_parser("archetypes", help="List all archetypes and their titles")
    arch_p.set_defaults(func=cmd_archetypes)

    # credits
    credits_p = subparsers.add_parser("credits", help="Show daily credit usage and budget")
    credits_p.set_defaults(func=cmd_credits)

    # quota
    quota_p = subparsers.add_parser("quota", help="Check SourceStack account credit quota")
    quota_p.set_defaults(func=cmd_quota)

    # delta
    delta_p = subparsers.add_parser("delta", help="Show recent job changes")
    delta_p.add_argument("--since-days", type=int, default=1)
    delta_p.set_defaults(func=cmd_delta)

    # lifecycle
    life_p = subparsers.add_parser("lifecycle", help="Run lifecycle state transitions")
    life_p.set_defaults(func=cmd_lifecycle)

    # prune
    prune_p = subparsers.add_parser("prune", help="Lifecycle + Notion pruning")
    prune_p.set_defaults(func=cmd_prune)

    # publish
    pub_p = subparsers.add_parser("publish", help="Prepare approved jobs for Notion push")
    pub_p.set_defaults(func=cmd_publish)

    # notion-prune
    np_p = subparsers.add_parser("notion-prune", help="List stale jobs to archive from Notion")
    np_p.set_defaults(func=cmd_notion_prune)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        LOG.error("Failed to execute %s: %s", args.command, exc, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
