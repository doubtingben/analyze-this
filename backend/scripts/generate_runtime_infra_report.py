#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional

import google.auth
from google.auth.transport.requests import AuthorizedSession
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/logging.read",
    "https://www.googleapis.com/auth/monitoring.read",
    "https://www.googleapis.com/auth/cloud-billing.readonly",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a runtime and infrastructure report as a PDF."
    )
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID"))
    parser.add_argument("--region", default=os.getenv("CLOUD_RUN_REGION", "-"))
    parser.add_argument("--github-repo", default=os.getenv("GITHUB_REPO"))
    parser.add_argument("--github-token", default=os.getenv("GITHUB_TOKEN"))
    parser.add_argument(
        "--days", type=int, default=int(os.getenv("REPORT_DAYS", "7"))
    )
    parser.add_argument(
        "--output",
        default=os.getenv("REPORT_OUTPUT", "runtime-infra-report.pdf"),
    )
    return parser.parse_args()


def get_authed_session() -> AuthorizedSession:
    credentials, _ = google.auth.default(scopes=SCOPES)
    return AuthorizedSession(credentials)


def request_json(
    session: AuthorizedSession,
    method: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response = session.request(method, url, params=params, json=body)
    if not response.ok:
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {response.text}")
    if response.text:
        return response.json()
    return {}


def github_request(
    url: str, token: Optional[str], params: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    import requests

    response = requests.get(url, headers=headers, params=params, timeout=30)
    if not response.ok:
        raise RuntimeError(f"GitHub API {url} failed: {response.status_code} {response.text}")
    return response.json()


def time_range(days: int) -> Dict[str, str]:
    end = dt.datetime.utcnow()
    start = end - dt.timedelta(days=days)
    return {"startTime": start.isoformat("T") + "Z", "endTime": end.isoformat("T") + "Z"}


def fetch_cloud_run_services(
    session: AuthorizedSession, project_id: str, region: str
) -> List[Dict[str, Any]]:
    url = f"https://run.googleapis.com/v2/projects/{project_id}/locations/{region}/services"
    data = request_json(session, "GET", url)
    return data.get("services", [])


def fetch_request_counts(
    session: AuthorizedSession,
    project_id: str,
    service_name: str,
    days: int,
    response_class: Optional[str] = None,
) -> float:
    filter_parts = [
        'metric.type="run.googleapis.com/request_count"',
        'resource.type="cloud_run_revision"',
        f'resource.labels.service_name="{service_name}"',
    ]
    if response_class:
        filter_parts.append(f'metric.labels.response_code_class="{response_class}"')
    filter_str = " AND ".join(filter_parts)
    interval = time_range(days)
    params = {
        "filter": filter_str,
        "interval.startTime": interval["startTime"],
        "interval.endTime": interval["endTime"],
        "aggregation.alignmentPeriod": "86400s",
        "aggregation.perSeriesAligner": "ALIGN_DELTA",
        "aggregation.crossSeriesReducer": "REDUCE_SUM",
    }
    url = f"https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries"
    data = request_json(session, "GET", url, params=params)
    total = 0.0
    for series in data.get("timeSeries", []):
        for point in series.get("points", []):
            value = point.get("value", {})
            if "doubleValue" in value:
                total += float(value["doubleValue"])
            elif "int64Value" in value:
                total += float(value["int64Value"])
    return total


def fetch_cloud_run_errors(
    session: AuthorizedSession, project_id: str, service_name: str, days: int
) -> List[Dict[str, Any]]:
    interval = time_range(days)
    filter_str = (
        'resource.type="cloud_run_revision" '
        f'AND resource.labels.service_name="{service_name}" '
        'AND severity>=ERROR'
    )
    body = {
        "resourceNames": [f"projects/{project_id}"],
        "filter": filter_str,
        "orderBy": "timestamp desc",
        "pageSize": 5,
        "timeRange": interval,
    }
    url = "https://logging.googleapis.com/v2/entries:list"
    data = request_json(session, "POST", url, body=body)
    return data.get("entries", [])


def fetch_billing_info(session: AuthorizedSession, project_id: str) -> Dict[str, Any]:
    url = f"https://cloudbilling.googleapis.com/v1/projects/{project_id}/billingInfo"
    return request_json(session, "GET", url)


def fetch_budgets(session: AuthorizedSession, billing_account: str) -> List[Dict[str, Any]]:
    url = f"https://billingbudgets.googleapis.com/v1/{billing_account}/budgets"
    data = request_json(session, "GET", url)
    return data.get("budgets", [])


def fetch_billing_cost(session: AuthorizedSession, project_id: str, days: int) -> Optional[float]:
    interval = time_range(days)
    params = {
        "filter": 'metric.type="billing.googleapis.com/total_cost"',
        "interval.startTime": interval["startTime"],
        "interval.endTime": interval["endTime"],
        "aggregation.alignmentPeriod": "86400s",
        "aggregation.perSeriesAligner": "ALIGN_DELTA",
        "aggregation.crossSeriesReducer": "REDUCE_SUM",
    }
    url = f"https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries"
    data = request_json(session, "GET", url, params=params)
    total = 0.0
    for series in data.get("timeSeries", []):
        for point in series.get("points", []):
            value = point.get("value", {})
            if "doubleValue" in value:
                total += float(value["doubleValue"])
            elif "int64Value" in value:
                total += float(value["int64Value"])
    if total == 0.0:
        return None
    return total


def summarize_service_resources(service: Dict[str, Any]) -> Dict[str, str]:
    template = service.get("template", {})
    containers = template.get("containers", [])
    resources = {}
    if containers:
        limits = containers[0].get("resources", {}).get("limits", {})
        resources = {k: str(v) for k, v in limits.items()}
    scaling = template.get("scaling", {})
    return {
        "cpu": resources.get("cpu", "unknown"),
        "memory": resources.get("memory", "unknown"),
        "min_instances": str(scaling.get("minInstanceCount", "default")),
        "max_instances": str(scaling.get("maxInstanceCount", "default")),
    }


def render_pdf(
    output_path: str,
    project_id: str,
    days: int,
    cloud_run_summary: List[Dict[str, Any]],
    github_prs: List[Dict[str, Any]],
    github_issues: List[Dict[str, Any]],
    billing_info: Dict[str, Any],
    budgets: List[Dict[str, Any]],
    cost_total: Optional[float],
) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    story: List[Any] = []

    story.append(Paragraph("Runtime & Infrastructure Report", styles["Title"]))
    story.append(Paragraph(f"Project: {project_id}", styles["Heading2"]))
    story.append(Paragraph(f"Window: last {days} days", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Cloud Run Activity", styles["Heading2"]))
    if cloud_run_summary:
        data = [
            [
                "Service",
                "Requests",
                "5xx Errors",
                "4xx Errors",
                "CPU",
                "Memory",
                "Min Instances",
                "Max Instances",
            ]
        ]
        for item in cloud_run_summary:
            data.append(
                [
                    item["service"],
                    f"{item['requests']:.0f}",
                    f"{item['errors_5xx']:.0f}",
                    f"{item['errors_4xx']:.0f}",
                    item["cpu"],
                    item["memory"],
                    item["min_instances"],
                    item["max_instances"],
                ]
            )
        table = Table(data, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("No Cloud Run services found.", styles["Normal"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Recent Cloud Run Errors", styles["Heading2"]))
    for item in cloud_run_summary:
        story.append(Paragraph(f"Service: {item['service']}", styles["Heading3"]))
        if not item["errors"]:
            story.append(Paragraph("No errors in the time window.", styles["Normal"]))
            continue
        for entry in item["errors"]:
            timestamp = entry.get("timestamp", "unknown")
            message = entry.get("textPayload") or json.dumps(entry.get("jsonPayload", {}))
            story.append(Paragraph(f"{timestamp}: {message}", styles["Normal"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("GitHub Activity", styles["Heading2"]))
    story.append(Paragraph(f"Open PRs: {len(github_prs)}", styles["Normal"]))
    for pr in github_prs:
        story.append(Paragraph(f"#{pr['number']}: {pr['title']}", styles["Normal"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Open Issues: {len(github_issues)}", styles["Normal"]))
    for issue in github_issues:
        story.append(Paragraph(f"#{issue['number']}: {issue['title']}", styles["Normal"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Billing & Budget", styles["Heading2"]))
    billing_account = billing_info.get("billingAccountName", "unknown")
    story.append(Paragraph(f"Billing Account: {billing_account}", styles["Normal"]))
    if cost_total is not None:
        story.append(Paragraph(f"Estimated cost (last {days} days): ${cost_total:.2f}", styles["Normal"]))
    else:
        story.append(Paragraph("Estimated cost: unavailable", styles["Normal"]))
    if budgets:
        for budget in budgets:
            amount = budget.get("amount", {})
            specified = amount.get("specifiedAmount", {})
            units = specified.get("units")
            currency = specified.get("currencyCode", "USD")
            if units is not None:
                story.append(Paragraph(
                    f"Budget: {budget.get('displayName', 'unnamed')} - {units} {currency}",
                    styles["Normal"],
                ))
    else:
        story.append(Paragraph("No budgets found.", styles["Normal"]))

    doc.build(story)


def main() -> None:
    args = parse_args()
    if not args.project_id:
        raise SystemExit("GCP project ID is required via --project-id or GCP_PROJECT_ID.")
    if not args.github_repo:
        raise SystemExit("GitHub repo is required via --github-repo or GITHUB_REPO (owner/repo).")

    session = get_authed_session()
    services = fetch_cloud_run_services(session, args.project_id, args.region)
    cloud_run_summary = []
    for service in services:
        name = service.get("name", "")
        service_name = name.split("/")[-1] if name else "unknown"
        resources = summarize_service_resources(service)
        requests = fetch_request_counts(session, args.project_id, service_name, args.days)
        errors_5xx = fetch_request_counts(
            session, args.project_id, service_name, args.days, response_class="5xx"
        )
        errors_4xx = fetch_request_counts(
            session, args.project_id, service_name, args.days, response_class="4xx"
        )
        errors = fetch_cloud_run_errors(session, args.project_id, service_name, args.days)
        cloud_run_summary.append(
            {
                "service": service_name,
                "requests": requests,
                "errors_5xx": errors_5xx,
                "errors_4xx": errors_4xx,
                "errors": errors,
                **resources,
            }
        )

    owner, repo = args.github_repo.split("/", 1)
    github_prs = github_request(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        args.github_token,
        params={"state": "open"},
    )
    github_issues_all = github_request(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        args.github_token,
        params={"state": "open"},
    )
    github_issues = [issue for issue in github_issues_all if "pull_request" not in issue]

    billing_info = fetch_billing_info(session, args.project_id)
    billing_account = billing_info.get("billingAccountName")
    budgets = fetch_budgets(session, billing_account) if billing_account else []
    cost_total = fetch_billing_cost(session, args.project_id, args.days)

    render_pdf(
        args.output,
        args.project_id,
        args.days,
        cloud_run_summary,
        github_prs,
        github_issues,
        billing_info,
        budgets,
        cost_total,
    )
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
