#!/usr/bin/env python3
"""Warmer Jobs API CLI — search for job listings."""

import argparse
import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_URL = "https://warmerjobs.com/api/v1/search"

VALID_SENIORITY = [
    "intern", "entry", "midlevel", "senior", "manager",
    "director", "vp", "svp", "c_level",
]
VALID_WORK_TYPE = ["remote", "hybrid", "in_person"]
VALID_EMPLOYMENT_TYPE = [
    "full_time", "part_time", "contract", "temporary", "seasonal", "volunteer",
]
VALID_EDUCATION = ["high_school", "associates", "bachelors", "masters", "phd"]
VALID_FUNDING = [
    "pre_seed", "seed", "series_a", "series_b", "series_c", "series_d",
    "series_e+", "acquired", "public", "private_equity", "bootstrapped", "nonprofit",
]
VALID_INDUSTRIES = [
    "administrative/support services", "arts and culture", "biotechnology",
    "construction", "consumer services", "ecommerce", "education", "entertainment",
    "farming/ranching/forestry", "financial services", "food and beverage",
    "government", "holding companies", "hospitals/health care", "hospitality",
    "information services", "insurance", "legal", "manufacturing", "media",
    "military and defense", "nonprofit", "oil/gas/mining", "professional services",
    "real estate", "religious", "retail", "scientific/technical services",
    "software/it services", "sports/recreation", "telecommunications",
    "transportation/logistics/supply chain/storage", "utilities", "wholesale",
]


def build_form_body(args: argparse.Namespace, token: str) -> bytes:
    pairs: list[tuple[str, str]] = [("api_token", token), ("job_title", args.title)]

    def add_array(key: str, values: list[str] | None):
        if values:
            for v in values:
                pairs.append((f"{key}[]", v))

    add_array("seniority", args.seniority)
    add_array("locations", args.locations)
    add_array("work_type", args.work_type)
    add_array("employment_type", args.employment_type)
    add_array("education_level", args.education_level)
    add_array("visa_sponsored", args.visa_sponsored)
    add_array("industries", args.industries)
    add_array("funding_stage", args.funding_stage)

    if args.in_network:
        pairs.append(("in_network[]", "true"))
    if args.out_of_network:
        pairs.append(("out_of_network[]", "true"))
    if args.show_second_degree:
        pairs.append(("show_second_degree_contacts[]", "true"))
    if args.unique_company is not None:
        pairs.append(("fetch_unique_company_results", str(args.unique_company).lower()))
    if args.salary_min is not None:
        pairs.append(("salary_min", str(args.salary_min)))
    if args.salary_max is not None:
        pairs.append(("salary_max", str(args.salary_max)))
    if args.exp_min is not None:
        pairs.append(("experience_min", str(args.exp_min)))
    if args.exp_max is not None:
        pairs.append(("experience_max", str(args.exp_max)))

    return urlencode(pairs).encode()


def search(args: argparse.Namespace):
    token = os.environ.get("WARMERJOBS_API_TOKEN")
    if not token:
        print("Error: WARMERJOBS_API_TOKEN not set.", file=sys.stderr)
        sys.exit(1)

    body = build_form_body(args, token)
    req = Request(API_URL, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }, method="POST")

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        print(f"API error {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(1)

    jobs = data.get("jobs") or []

    if args.json:
        print(json.dumps(jobs, indent=2))
        return

    if not jobs:
        print("No jobs found.")
        return

    print(f"Found {len(jobs)} job(s):\n")
    for i, job in enumerate(jobs, 1):
        locs = ", ".join(job.get("locations") or ["N/A"])
        salary = job.get("salary") or "Not listed"
        updated = job.get("lastUpdated", "?")
        print(f"{i}. {job.get('title', 'Untitled')} @ {job.get('company', 'Unknown')}")
        print(f"   Locations: {locs}")
        print(f"   Salary: {salary}  |  Updated: {updated}")
        print(f"   URL: {job.get('url', 'N/A')}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Warmer Jobs API CLI")
    sub = parser.add_subparsers(dest="command")

    sp = sub.add_parser("search", help="Search for jobs")
    sp.add_argument("--title", required=True, help="Job title / keyword (required)")
    sp.add_argument("--locations", nargs="+", help="Location filters")
    sp.add_argument("--seniority", nargs="+", choices=VALID_SENIORITY, help="Seniority levels")
    sp.add_argument("--work-type", nargs="+", choices=VALID_WORK_TYPE, help="Work type filters")
    sp.add_argument("--employment-type", nargs="+", choices=VALID_EMPLOYMENT_TYPE)
    sp.add_argument("--education-level", nargs="+", choices=VALID_EDUCATION)
    sp.add_argument("--visa-sponsored", nargs="+", choices=["true", "false"])
    sp.add_argument("--industries", nargs="+", help="Industry filters (exact strings)")
    sp.add_argument("--funding-stage", nargs="+", choices=VALID_FUNDING)
    sp.add_argument("--salary-min", type=int, dest="salary_min")
    sp.add_argument("--salary-max", type=int, dest="salary_max")
    sp.add_argument("--exp-min", type=int, help="Min years experience")
    sp.add_argument("--exp-max", type=int, help="Max years experience")
    sp.add_argument("--in-network", action="store_true", help="Include in-network jobs")
    sp.add_argument("--out-of-network", action="store_true", default=True, help="Include out-of-network jobs (default)")
    sp.add_argument("--show-second-degree", action="store_true")
    sp.add_argument("--unique-company", type=bool, default=None, help="One job per company")
    sp.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "search":
        search(args)


if __name__ == "__main__":
    main()
