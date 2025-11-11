"""Combine Strategy 4 simple/multi mode simulation outputs into a single dataset.

The script reads every CSV in the strategy4 simple and multi simulation output
directories, keeps the simple-mode results as Strategy 4, and re-labels the
multi-mode Strategy 4 rows as Strategy 5 before appending them to each CSV.

Example:
    python combine_strategy4_modes.py \
        --simple-dir ../../datasets/derived_artifacts/rq3/simulation_outputs_strategy4_simple \
        --multi-dir ../../datasets/derived_artifacts/rq3/simulation_outputs_strategy4_multi \
        --output-dir ../../datasets/derived_artifacts/rq3/simulation_outputs_strategy_combined
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIMPLE_DIR = (
    REPO_ROOT / "datasets" / "derived_artifacts" / "rq3" / "simulation_outputs_strategy4_simple"
)
DEFAULT_MULTI_DIR = (
    REPO_ROOT / "datasets" / "derived_artifacts" / "rq3" / "simulation_outputs_strategy4_multi"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "datasets" / "derived_artifacts" / "rq3" / "simulation_outputs_strategy_combined"
)


@dataclass(frozen=True)
class CombineStats:
    filename: str
    simple_rows: int
    strategy5_rows: int
    total_rows: int


def read_csv_rows(path: Path) -> Tuple[Sequence[str], List[Dict[str, str]]]:
    """Read a CSV file into a header plus list of dictionaries."""
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        rows = [row for row in reader]
    if not header:
        raise ValueError(f"Missing header in CSV: {path}")
    return header, rows


def write_csv_rows(path: Path, header: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    """Write rows back to disk using the provided header order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def combine_file(
    simple_file: Path,
    multi_file: Path,
    output_file: Path,
    strategy_column: str,
    strategy4_source_label: str,
    strategy4_target_label: str,
    strategy5_source_label: str,
    strategy5_target_label: str,
) -> CombineStats:
    """Merge a pair of CSV files, keeping Strategy4 simple rows and adding Strategy5."""
    header, simple_rows = read_csv_rows(simple_file)
    _, multi_rows = read_csv_rows(multi_file)

    if strategy_column not in header:
        # For completeness, copy untouched files (though we currently expect all to have strategy).
        write_csv_rows(output_file, header, simple_rows)
        return CombineStats(output_file.name, len(simple_rows), 0, len(simple_rows))

    # Keep all simple rows and optionally normalize their labels if the user changed them.
    normalized_simple_rows: List[Dict[str, str]] = []
    for row in simple_rows:
        updated = dict(row)
        if strategy_column in updated and updated[strategy_column] == strategy4_source_label:
            updated[strategy_column] = strategy4_target_label
        normalized_simple_rows.append(updated)

    # Extract strategy5 rows from the multi-mode file and re-label them.
    strategy5_rows: List[Dict[str, str]] = []
    for row in multi_rows:
        if row.get(strategy_column) != strategy5_source_label:
            continue
        updated_row = dict(row)
        updated_row[strategy_column] = strategy5_target_label
        strategy5_rows.append(updated_row)

    combined_rows = normalized_simple_rows + strategy5_rows
    write_csv_rows(output_file, header, combined_rows)
    return CombineStats(output_file.name, len(normalized_simple_rows), len(strategy5_rows), len(combined_rows))


def infer_csv_files(simple_dir: Path) -> List[Path]:
    """Return CSV files under the simple directory sorted by name."""
    return sorted(simple_dir.glob("*.csv"))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simple-dir", type=Path, default=DEFAULT_SIMPLE_DIR, help="Path to strategy4 simple outputs.")
    parser.add_argument("--multi-dir", type=Path, default=DEFAULT_MULTI_DIR, help="Path to strategy4 multi outputs.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Destination for merged CSV files.")
    parser.add_argument(
        "--strategy-column",
        default="strategy",
        help="Column name containing strategy identifiers (default: strategy).",
    )
    parser.add_argument(
        "--strategy4-source-label",
        default="strategy4_regression",
        help="Label present in the simple-mode files before relabeling (default: strategy4_regression).",
    )
    parser.add_argument(
        "--strategy4-target-label",
        default="strategy4_regression_simple",
        help="Label to assign to the simple-mode regression rows (default: strategy4_regression_simple).",
    )
    parser.add_argument(
        "--strategy5-source-label",
        default="strategy4_regression",
        help="Label used in the multi-mode files before relabeling (default: strategy4_regression).",
    )
    parser.add_argument(
        "--strategy5-target-label",
        default="strategy5_regression_multi",
        help="Label to assign to the relabeled multi-mode rows (default: strategy5_regression_multi).",
    )
    return parser.parse_args(argv)


def validate_inputs(simple_dir: Path, multi_dir: Path) -> None:
    if not simple_dir.exists():
        raise FileNotFoundError(f"Simple directory not found: {simple_dir}")
    if not multi_dir.exists():
        raise FileNotFoundError(f"Multi directory not found: {multi_dir}")


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    validate_inputs(args.simple_dir, args.multi_dir)

    csv_files = infer_csv_files(args.simple_dir)
    if not csv_files:
        print(f"No CSV files found in {args.simple_dir}", file=sys.stderr)
        return 1

    stats: List[CombineStats] = []
    for simple_file in csv_files:
        multi_file = args.multi_dir / simple_file.name
        if not multi_file.exists():
            print(f"Skipping {simple_file.name}: missing matching file under {args.multi_dir}", file=sys.stderr)
            continue
        output_file = args.output_dir / simple_file.name
        file_stats = combine_file(
            simple_file=simple_file,
            multi_file=multi_file,
            output_file=output_file,
            strategy_column=args.strategy_column,
            strategy4_source_label=args.strategy4_source_label,
            strategy4_target_label=args.strategy4_target_label,
            strategy5_source_label=args.strategy5_source_label,
            strategy5_target_label=args.strategy5_target_label,
        )
        stats.append(file_stats)

    if not stats:
        print("No CSV files processed. Nothing to do.", file=sys.stderr)
        return 1

    print(f"Wrote merged CSVs to {args.output_dir}")
    for result in stats:
        print(
            f"[{result.filename}] rows(simple+other)={result.simple_rows} + strategy5={result.strategy5_rows} => total={result.total_rows}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
