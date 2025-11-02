#!/usr/bin/env python3
"""Fill the dataset summary paragraph with actual counts.

This script scans the OSS-Fuzz vulnerability CSV, filters it according to the
steps described in the manuscript, inspects the downloaded coverage reports,
and prints the paragraph with every placeholder replaced by the measured
values. By default the script assumes the repository layout used in vuljit.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple


def _normalize_repo(raw: str) -> str:
    """Normalize repository URLs for consistent counting."""
    repo = (raw or "").strip()
    if not repo:
        return ""

    repo = repo.rstrip("/")
    lower = repo.lower()

    if lower.startswith("git://github.com/"):
        repo = "https://github.com/" + repo[len("git://github.com/") :]
    elif lower.startswith("http://github.com/"):
        repo = "https://github.com/" + repo[len("http://github.com/") :]
    elif lower.startswith("https://github.com/"):
        repo = "https://github.com/" + repo[len("https://github.com/") :]
    elif lower.startswith("git@github.com:"):
        repo = "https://github.com/" + repo[len("git@github.com:") :]

    repo = repo.rstrip("/")
    if repo.lower().endswith(".git"):
        repo = repo[:-4]

    return repo.lower()

def _parse_iso_date(value: str) -> Optional[date]:
    """Return a date object from an ISO timestamp, or None on failure."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _scan_coverage(
    coverage_root: Path,
    packages: Set[str],
) -> Tuple[Dict[str, date], int, int, Optional[date], Optional[date]]:
    """Inspect coverage directories and collect per-project metadata."""
    first_dates: Dict[str, date] = {}
    total_reports = 0
    overall_min: Optional[date] = None
    overall_max: Optional[date] = None

    eight_digits = re.compile(r"^\d{8}$")

    for package in sorted(packages):
        project_dir = coverage_root / package
        if not project_dir.is_dir():
            continue

        first_for_project: Optional[date] = None
        try:
            entries = list(os.scandir(project_dir))
        except FileNotFoundError:
            entries = []

        for entry in entries:
            if not entry.is_dir():
                continue
            if not eight_digits.match(entry.name):
                continue
            linux_dir = Path(entry.path) / "linux"
            if not linux_dir.is_dir():
                continue
            has_report = False
            summary = linux_dir / "summary.json"
            summary_gz = linux_dir / "summary.json.gz"
            if summary.is_file() or summary_gz.is_file():
                has_report = True
            if not has_report:
                continue

            day = datetime.strptime(entry.name, "%Y%m%d").date()
            total_reports += 1
            if first_for_project is None or day < first_for_project:
                first_for_project = day
            if overall_min is None or day < overall_min:
                overall_min = day
            if overall_max is None or day > overall_max:
                overall_max = day

        if first_for_project is not None:
            first_dates[package] = first_for_project

    return first_dates, total_reports, len(first_dates), overall_min, overall_max


def _load_metadata(metadata_csv: Path) -> Dict[str, str]:
    """Return mapping from project name to normalized repository URL."""
    if not metadata_csv.is_file():
        raise FileNotFoundError(f"Metadata CSV not found: {metadata_csv}")

    projects: Dict[str, str] = {}
    with metadata_csv.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            language = (row.get("language") or "").strip().lower()
            if language not in {"c", "c++"}:
                continue
            project = (row.get("project") or "").strip()
            if not project:
                continue
            repo = _normalize_repo(row.get("main_repo") or "")
            if not repo:
                continue
            projects[project] = repo
    return projects


def _load_cloned_projects(cloned_root: Path) -> Set[str]:
    """Return set of project names with existing clones."""
    if not cloned_root.is_dir():
        return set()
    projects: Set[str] = set()
    for entry in cloned_root.iterdir():
        if entry.is_dir():
            projects.add(entry.name)
    return projects


def compute_statistics(
    vuln_csv: Path,
    metadata_csv: Path,
    cloned_root: Path,
    coverage_root: Path,
    min_reports_per_repo: int,
) -> Dict[str, object]:
    metadata = _load_metadata(metadata_csv)
    if not metadata:
        raise ValueError(f"No C/C++ metadata rows found in {metadata_csv}")

    cloned_projects = _load_cloned_projects(cloned_root)

    total_issues = 0
    stage1_records: List[Dict[str, str]] = []

    with vuln_csv.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_issues += 1
            ecosystem = (row.get("ecosystem") or "").strip().lower()
            if ecosystem != "oss-fuzz":
                continue
            package = (row.get("package_name") or "").strip()
            if package not in metadata:
                continue
            repo = metadata[package]
            if not repo:
                continue
            published = row.get("published") or ""
            stage1_records.append(
                {
                    "package": package,
                    "repo": repo,
                    "published": published,
                }
            )

    repo_counts_stage1 = Counter(r["repo"] for r in stage1_records)
    stage1_issue_count = len(stage1_records)
    stage1_repo_count = len(repo_counts_stage1)

    clonable_records = [
        r for r in stage1_records if r["package"] in cloned_projects
    ]
    repo_counts_clonable = Counter(r["repo"] for r in clonable_records)
    clonable_issue_count = len(clonable_records)
    clonable_repo_count = len(repo_counts_clonable)

    eligible_repos = {
        repo for repo, count in repo_counts_clonable.items() if count >= min_reports_per_repo
    }
    stage3_records = [r for r in clonable_records if r["repo"] in eligible_repos]
    stage3_repo_counts = Counter(r["repo"] for r in stage3_records)
    stage3_issue_count = len(stage3_records)
    stage3_repo_count = len(stage3_repo_counts)
    stage3_packages = {r["package"] for r in stage3_records}

    if not coverage_root.is_dir():
        raise FileNotFoundError(f"Coverage root not found: {coverage_root}")

    (
        first_dates,
        coverage_total_reports,
        coverage_projects,
        coverage_start,
        coverage_end,
    ) = _scan_coverage(coverage_root, stage3_packages)

    final_records = []
    for record in stage3_records:
        package = record["package"]
        first_day = first_dates.get(package)
        if first_day is None:
            continue
        published = _parse_iso_date(record["published"])
        if published is None:
            continue
        if published >= first_day:
            final_records.append(record)

    percentage = (
        (stage1_issue_count / total_issues * 100.0) if total_issues else 0.0
    )

    return {
        "total_issues": total_issues,
        "c_cpp_issues": stage1_issue_count,
        "c_cpp_repos": stage1_repo_count,
        "c_cpp_percent": percentage,
        "cloned_issues": clonable_issue_count,
        "cloned_repos": clonable_repo_count,
        "min10_issues": stage3_issue_count,
        "min10_repos": stage3_repo_count,
        "min10_packages": len(stage3_packages),
        "coverage_reports": coverage_total_reports,
        "coverage_projects": coverage_projects,
        "coverage_start": coverage_start.isoformat() if coverage_start else None,
        "coverage_end": coverage_end.isoformat() if coverage_end else None,
        "final_issues": len(final_records),
    }


def _format_int(value: int) -> str:
    return str(value)


def _format_percent(value: float) -> str:
    return f"{value:.1f}"


def build_paragraph(stats: Dict[str, object]) -> str:
    percent = _format_percent(float(stats["c_cpp_percent"]))
    text = (
        "We collected issue reports created on repositories that have code primarily "
        "written in C/C++. The reason why we only focus on C/C++ is that many C/C++ "
        "projects use OSS-Fuzz and many vulnerabilities are discovered in those "
        "projects. We obtained {c_cpp_issues} issues ({c_cpp_percent} %) from "
        "{c_cpp_repos} repositories. Furthermore, we restricted the dataset to "
        "projects that we successfully cloned using the OSS-Fuzz metadata. This step "
        "resulted in {cloned_issues} issues from {cloned_repos} repositories. Also, "
        "to ensure evaluation reliability, we excluded the repositories that do not "
        "have at least 10 vulnerability issue reports, resulting in {min10_issues} "
        "issues from {min10_repos} repositories.\n"
        "Additionally, the model we develop makes use of fuzzing coverage. We thus "
        "collect daily coverage reports that are archived on the public Google Cloud "
        "Storage (GCS) of OSS-Fuzz. We downloaded a total of {coverage_reports} daily "
        "coverage reports from the abovementioned {coverage_projects} projects, which "
        "are generated from {coverage_start} to {coverage_end}. These files contain "
        "aggregated coverage data, such as line, function, region, branch, and "
        "instruction coverage for the entire project for each day.\n"
        "It is worth mentioning that we excluded vulnerability reports created before "
        "the first coverage report for each project (i.e., removed issues created "
        "before their integration into OSS-Fuzz). This filtering yields "
        "{final_issues} vulnerability reports. Table II summarizes the statistics of "
        "the final dataset."
    )
    return text.format(
        c_cpp_issues=_format_int(int(stats["c_cpp_issues"])),
        c_cpp_percent=percent,
        c_cpp_repos=_format_int(int(stats["c_cpp_repos"])),
        cloned_issues=_format_int(int(stats["cloned_issues"])),
        cloned_repos=_format_int(int(stats["cloned_repos"])),
        min10_issues=_format_int(int(stats["min10_issues"])),
        min10_repos=_format_int(int(stats["min10_repos"])),
        coverage_reports=_format_int(int(stats["coverage_reports"])),
        coverage_projects=_format_int(int(stats["coverage_projects"])),
        coverage_start=stats["coverage_start"] or "N/A",
        coverage_end=stats["coverage_end"] or "N/A",
        final_issues=_format_int(int(stats["final_issues"])),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    default_vuln_csv = (
        repo_root
        / "datasets"
        / "derived_artifacts"
        / "vulnerability_reports"
        / "oss_fuzz_vulnerabilities.csv"
    )
    default_metadata_csv = (
        repo_root
        / "datasets"
        / "derived_artifacts"
        / "oss_fuzz_metadata"
        / "oss_fuzz_project_metadata.csv"
    )
    default_cloned_root = repo_root / "datasets" / "raw" / "cloned_c_cpp_projects"
    default_coverage_root = repo_root / "datasets" / "raw" / "coverage_report"

    parser = argparse.ArgumentParser(
        description="Fill the dataset summary paragraph with measured statistics."
    )
    parser.add_argument("--vuln-csv", type=Path, default=default_vuln_csv)
    parser.add_argument("--metadata-csv", type=Path, default=default_metadata_csv)
    parser.add_argument("--cloned-root", type=Path, default=default_cloned_root)
    parser.add_argument("--coverage-root", type=Path, default=default_coverage_root)
    parser.add_argument(
        "--min-issues-per-repo",
        type=int,
        default=10,
        help="Minimum number of vulnerability reports per repository.",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        help="If specified, suppress the JSON statistics on stderr.",
    )
    args = parser.parse_args(argv)

    stats = compute_statistics(
        vuln_csv=args.vuln_csv,
        metadata_csv=args.metadata_csv,
        cloned_root=args.cloned_root,
        coverage_root=args.coverage_root,
        min_reports_per_repo=args.min_issues_per_repo,
    )

    if not args.no_stats:
        json.dump(stats, sys.stderr, indent=2, sort_keys=True)
        sys.stderr.write("\n")

    paragraph = build_paragraph(stats)
    print(paragraph)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
