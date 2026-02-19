#!/usr/bin/env python3
"""GA4 Analytics CLI — Pull traffic stats for <YOUR_GITHUB>.com."""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    FilterExpressionList,
    Metric,
    OrderBy,
    RunReportRequest,
)
from google.oauth2 import service_account

DEFAULT_PROPERTY_ID = "520487128"
DEFAULT_HOST = "www.<YOUR_GITHUB>.com"


def get_client():
    raw = os.environ.get("GA4_SERVICE_ACCOUNT_JSON")
    if not raw:
        print("ERROR: GA4_SERVICE_ACCOUNT_JSON secret not set.", file=sys.stderr)
        print("Add it at: Settings > Advanced", file=sys.stderr)
        sys.exit(1)
    creds_json = json.loads(raw)
    credentials = service_account.Credentials.from_service_account_info(creds_json)
    return BetaAnalyticsDataClient(credentials=credentials)


def get_property(args):
    if args.property:
        return args.property
    return os.environ.get("GA4_VA_COM_PROPERTY_ID", DEFAULT_PROPERTY_ID)


def date_range(args):
    if args.start:
        return DateRange(start_date=args.start, end_date=args.end or "today")
    return DateRange(start_date=f"{args.days}daysAgo", end_date="today")


def host_filter(hostname):
    return FilterExpression(
        filter=Filter(
            field_name="hostName",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.EXACT,
                value=hostname,
            ),
        )
    )


def print_table(headers, rows, align=None):
    if not rows:
        print("  No data found.")
        return
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("  ".join("-" * w for w in col_widths))
    for row in rows:
        parts = []
        for i, val in enumerate(row):
            if align and i < len(align) and align[i] == "r":
                parts.append(str(val).rjust(col_widths[i]))
            else:
                parts.append(str(val).ljust(col_widths[i]))
        print("  ".join(parts))


def cmd_overview(args):
    client = get_client()
    prop = f"properties/{get_property(args)}"
    dr = date_range(args)
    host = args.host

    request = RunReportRequest(
        property=prop,
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
            Metric(name="newUsers"),
            Metric(name="screenPageViews"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
        ],
        date_ranges=[dr],
        dimension_filter=host_filter(host),
    )
    response = client.run_report(request)

    print(f"\n📊 Site Overview — {host}")
    print(f"   Period: {dr.start_date} → {dr.end_date}\n")

    if not response.rows:
        print("  No data for this period.")
        return

    row = response.rows[0]
    sessions = row.metric_values[0].value
    users = row.metric_values[1].value
    new_users = row.metric_values[2].value
    pageviews = row.metric_values[3].value
    avg_duration = float(row.metric_values[4].value)
    bounce_rate = float(row.metric_values[5].value)

    mins = int(avg_duration) // 60
    secs = int(avg_duration) % 60

    print(f"  Sessions:      {sessions}")
    print(f"  Users:         {users} ({new_users} new)")
    print(f"  Pageviews:     {pageviews}")
    print(f"  Avg Duration:  {mins}m {secs}s")
    print(f"  Bounce Rate:   {bounce_rate:.1%}")
    print()


def cmd_pages(args):
    client = get_client()
    prop = f"properties/{get_property(args)}"
    dr = date_range(args)

    request = RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="pagePath")],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="totalUsers"),
            Metric(name="averageSessionDuration"),
        ],
        date_ranges=[dr],
        dimension_filter=host_filter(args.host),
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"),
                desc=True,
            )
        ],
        limit=args.limit,
    )
    response = client.run_report(request)

    print(f"\n📄 Top Pages — {args.host}")
    print(f"   Period: {dr.start_date} → {dr.end_date}\n")

    rows = []
    for row in response.rows:
        path = row.dimension_values[0].value
        views = row.metric_values[0].value
        users = row.metric_values[1].value
        dur = float(row.metric_values[2].value)
        rows.append((path, views, users, f"{int(dur)}s"))

    print_table(["Page", "Views", "Users", "Avg Duration"], rows, align=["l", "r", "r", "r"])
    print()


def cmd_page(args):
    client = get_client()
    prop = f"properties/{get_property(args)}"
    dr = date_range(args)
    page_path = args.path if args.path.startswith("/") else f"/{args.path}"

    page_filter = FilterExpression(
        and_group=FilterExpressionList(
            expressions=[
                host_filter(args.host),
                FilterExpression(
                    filter=Filter(
                        field_name="pagePath",
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.EXACT,
                            value=page_path,
                        ),
                    )
                ),
            ]
        )
    )

    # Overall stats
    request = RunReportRequest(
        property=prop,
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="totalUsers"),
            Metric(name="averageSessionDuration"),
        ],
        date_ranges=[dr],
        dimension_filter=page_filter,
    )
    response = client.run_report(request)

    print(f"\n🔍 Page Stats — {page_path}")
    print(f"   Host: {args.host}")
    print(f"   Period: {dr.start_date} → {dr.end_date}\n")

    if not response.rows:
        print("  No data for this page in this period.")
        return

    row = response.rows[0]
    print(f"  Pageviews:     {row.metric_values[0].value}")
    print(f"  Users:         {row.metric_values[1].value}")
    dur = float(row.metric_values[2].value)
    print(f"  Avg Duration:  {int(dur)}s")
    print()

    # Daily breakdown
    request2 = RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="screenPageViews"), Metric(name="totalUsers")],
        date_ranges=[dr],
        dimension_filter=page_filter,
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
    )
    response2 = client.run_report(request2)

    if response2.rows:
        print("  Daily breakdown:")
        rows = []
        for row in response2.rows:
            d = row.dimension_values[0].value
            date_str = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            rows.append((date_str, row.metric_values[0].value, row.metric_values[1].value))
        print_table(["Date", "Views", "Users"], rows, align=["l", "r", "r"])
        print()


def cmd_sources(args):
    client = get_client()
    prop = f"properties/{get_property(args)}"
    dr = date_range(args)

    request = RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="sessionSource"), Dimension(name="sessionMedium")],
        metrics=[Metric(name="sessions"), Metric(name="totalUsers")],
        date_ranges=[dr],
        dimension_filter=host_filter(args.host),
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="sessions"),
                desc=True,
            )
        ],
        limit=args.limit,
    )
    response = client.run_report(request)

    print(f"\n🔗 Traffic Sources — {args.host}")
    print(f"   Period: {dr.start_date} → {dr.end_date}\n")

    rows = []
    for row in response.rows:
        source = row.dimension_values[0].value
        medium = row.dimension_values[1].value
        rows.append((f"{source} / {medium}", row.metric_values[0].value, row.metric_values[1].value))

    print_table(["Source / Medium", "Sessions", "Users"], rows, align=["l", "r", "r"])
    print()


def cmd_devices(args):
    client = get_client()
    prop = f"properties/{get_property(args)}"
    dr = date_range(args)

    request = RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="deviceCategory")],
        metrics=[Metric(name="sessions"), Metric(name="totalUsers")],
        date_ranges=[dr],
        dimension_filter=host_filter(args.host),
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="sessions"),
                desc=True,
            )
        ],
    )
    response = client.run_report(request)

    print(f"\n📱 Devices — {args.host}")
    print(f"   Period: {dr.start_date} → {dr.end_date}\n")

    rows = []
    for row in response.rows:
        rows.append((row.dimension_values[0].value, row.metric_values[0].value, row.metric_values[1].value))

    print_table(["Device", "Sessions", "Users"], rows, align=["l", "r", "r"])
    print()


def cmd_daily(args):
    client = get_client()
    prop = f"properties/{get_property(args)}"
    dr = date_range(args)

    request = RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="date")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
            Metric(name="screenPageViews"),
        ],
        date_ranges=[dr],
        dimension_filter=host_filter(args.host),
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
    )
    response = client.run_report(request)

    print(f"\n📅 Daily Traffic — {args.host}")
    print(f"   Period: {dr.start_date} → {dr.end_date}\n")

    rows = []
    for row in response.rows:
        d = row.dimension_values[0].value
        date_str = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        rows.append((
            date_str,
            row.metric_values[0].value,
            row.metric_values[1].value,
            row.metric_values[2].value,
        ))

    print_table(["Date", "Sessions", "Users", "Pageviews"], rows, align=["l", "r", "r", "r"])
    print()


def main():
    parser = argparse.ArgumentParser(
        description="GA4 Analytics CLI — Pull traffic stats for <YOUR_GITHUB>.com"
    )
    parser.add_argument("--property", help="GA4 property ID (default: from env or 520487128)")
    parser.add_argument("--days", type=int, default=90, help="Lookback days (default: 90)")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Hostname filter (default: {DEFAULT_HOST})")
    parser.add_argument("--limit", type=int, default=10, help="Max rows (default: 10)")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("overview", help="Site traffic summary")
    sub.add_parser("pages", help="Top pages by pageviews")

    page_parser = sub.add_parser("page", help="Stats for a specific page")
    page_parser.add_argument("path", help="Page path (e.g. /mind)")

    sub.add_parser("sources", help="Traffic sources breakdown")
    sub.add_parser("devices", help="Device category breakdown")
    sub.add_parser("daily", help="Day-by-day traffic")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "overview": cmd_overview,
        "pages": cmd_pages,
        "page": cmd_page,
        "sources": cmd_sources,
        "devices": cmd_devices,
        "daily": cmd_daily,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
