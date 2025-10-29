import argparse
import os
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from google.cloud import storage

from calculate_patch_coverage_per_project import (
    DEFAULT_OUTPUT_BASE_DIRECTORY,
    compute_patch_coverage_for_patch_text,
)

# create_daily_diff.py の設定と揃える
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent

DEFAULT_INPUT_CSV_DIRECTORY = Path(
    os.environ.get(
        "VULJIT_PATCH_COVERAGE_INPUTS_DIR",
        REPO_ROOT / "datasets" / "derived_artifacts" / "patch_coverage_inputs",
    )
)
DEFAULT_CLONED_REPOS_DIRECTORY = Path(
    os.environ.get(
        "VULJIT_CLONED_REPOS_DIR",
        REPO_ROOT / "data" / "intermediate" / "cloned_repos",
    )
)

# 差分対象の拡張子リスト（create_daily_diff.py と同一）
CODE_FILE_EXTENSIONS: Tuple[str, ...] = (
    '.c', '.cc', '.cpp', '.cxx', '.c++',
    '.h', '.hh', '.hpp', '.hxx', '.h++'
)


def get_repo_dir_name_from_url(url: str) -> str:
    if not isinstance(url, str) or not url:
        return ""
    return url.split('/')[-1].replace('.git', '')


def get_changed_files(repo_path: Path, old_revision: str, new_revision: str, extensions: Iterable[str]) -> List[str]:
    try:
        if not repo_path.is_dir():
            print(f"  - エラー: リポジトリパスが見つかりません: {repo_path}")
            return []

        cmd = [
            'git', '-C', str(repo_path), 'diff', '--name-only',
            str(old_revision), str(new_revision)
        ]
        env = os.environ.copy()
        env.setdefault('GIT_OPTIONAL_LOCKS', '0')
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, env=env)
        names = [line.strip() for line in out.decode('utf-8', errors='ignore').splitlines() if line.strip()]

        target_extensions = tuple(ext.lower() for ext in extensions)
        files = [p for p in names if p.lower().endswith(target_extensions)]
        return files
    except subprocess.CalledProcessError:
        return []
    except Exception as e:
        print(f"  - 警告: 差分取得中に予期せぬエラーが発生しました: {e}")
        return []


def get_patch_text(repo_path: Path, old_revision: str, new_revision: str, rel_path: str) -> Optional[str]:
    try:
        cmd = [
            'git', '-C', str(repo_path), 'diff',
            str(old_revision), str(new_revision), '--', rel_path
        ]
        env = os.environ.copy()
        env.setdefault('GIT_OPTIONAL_LOCKS', '0')
        patch = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, env=env)
        patch_text = patch.decode('utf-8', errors='ignore')
        if not patch_text.strip():
            return None

        lines = patch_text.splitlines()
        start_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('@@'):
                start_idx = i
                break
        if not lines or not (start_idx < len(lines) and lines[start_idx].startswith('@@')):
            return None
        return "\n".join(lines[start_idx:]) + "\n"
    except subprocess.CalledProcessError:
        return None
    except Exception as e:
        print(f"  - 警告: パッチ生成中に予期せぬエラーが発生しました ({rel_path}): {e}")
        return None


def _compute_coverage_worker(args: Tuple[str, str, str, str, Optional[str]]) -> Optional[dict]:
    project_name, date, file_path, patch_text, parsing_out = args
    parsing_root = Path(parsing_out) if parsing_out else None
    return compute_patch_coverage_for_patch_text(
        project_name=project_name,
        date=date,
        file_path_str=file_path,
        patch_text=patch_text,
        parsing_output_root=parsing_root,
    )


def _normalize_projects(values: Sequence[str]) -> List[str]:
    tokens: List[str] = []
    for val in values:
        if not val:
            continue
        for token in re.split(r"[,\s]+", val.strip()):
            token = token.strip()
            if token:
                tokens.append(token)
    return tokens


def process_project(
    project_name: str,
    input_dir: Path,
    repos_dir: Path,
    output_dir: Path,
    parsing_dir: Optional[Path],
    workers: int,
) -> None:
    csv_file = input_dir / f"revisions_with_commit_date_{project_name}.csv"
    if not csv_file.is_file():
        print(f"エラー: 入力CSVが見つかりません: {csv_file}")
        return

    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"エラー: '{csv_file}' の読み込みに失敗しました: {e}")
        return

    required_cols = {'date', 'url', 'revision'}
    if not required_cols.issubset(df.columns):
        print(f"エラー: '{csv_file}' に必要な列 {required_cols} がありません。")
        return

    df = df.sort_values(by='date').reset_index(drop=True)
    if len(df) < 2:
        print(f"  - データが少ないため差分を計算できません ({csv_file}).")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file_path = output_dir / f"{project_name}_patch_coverage.csv"

    parsing_dir_path = None
    if parsing_dir is not None:
        parsing_dir.mkdir(parents=True, exist_ok=True)
        parsing_dir_path = parsing_dir

    processed_dates: set[str] = set()
    if output_file_path.exists():
        try:
            existing_df = pd.read_csv(output_file_path)
            if 'date' in existing_df.columns:
                processed_dates = set(existing_df['date'].astype(str))
            print(f"✔ 既存の出力から {len(processed_dates)} 件の日付をスキップ対象として読み込みました。")
        except pd.errors.EmptyDataError:
            print("⚠️ 既存の出力ファイルは空でした。")
        except Exception as e:
            print(f"⚠️ 既存の出力を読み込む際にエラーが発生しました: {e}")

    print(f"\n▶ プロジェクト '{project_name}' の処理を開始します。")

    workers = max(1, workers)
    storage_client_for_sequential: Optional[storage.Client] = None
    if workers == 1:
        try:
            storage_client_for_sequential = storage.Client.create_anonymous_client()
        except Exception as e:
            print(f"  - 警告: GCSクライアントの初期化に失敗しました（逐次モード）: {e}")

    processed_any = False

    for i in range(1, len(df)):
        previous_row = df.iloc[i - 1]
        current_row = df.iloc[i]
        date_str = str(current_row['date'])

        if date_str in processed_dates:
            print(f"  - スキップ: 日付 '{date_str}' は既に処理済みです。")
            continue

        repo_dir_name = get_repo_dir_name_from_url(str(current_row['url']))
        repo_local_path = repos_dir / repo_dir_name

        print(f"  - 日付: {date_str}")

        changed_files = get_changed_files(
            repo_local_path,
            str(previous_row['revision']),
            str(current_row['revision']),
            CODE_FILE_EXTENSIONS,
        )

        if not changed_files:
            print("    - 差分対象のファイルが見つかりませんでした。")
            continue

        patch_records: List[Tuple[str, str]] = []
        for rel_path in changed_files:
            patch_text = get_patch_text(
                repo_local_path,
                str(previous_row['revision']),
                str(current_row['revision']),
                rel_path,
            )
            if patch_text:
                patch_records.append((rel_path, patch_text))

        if not patch_records:
            print("    - パッチを生成できるファイルがありませんでした。")
            continue

        parsing_out_str = str(parsing_dir_path) if parsing_dir_path else None

        daily_results: List[Optional[dict]]
        if workers == 1:
            daily_results = []
            for file_path, patch_text in patch_records:
                result = compute_patch_coverage_for_patch_text(
                    project_name=project_name,
                    date=date_str,
                    file_path_str=file_path,
                    patch_text=patch_text,
                    parsing_output_root=parsing_dir_path,
                    storage_client=storage_client_for_sequential,
                )
                daily_results.append(result)
        else:
            args_list = [
                (project_name, date_str, file_path, patch_text, parsing_out_str)
                for file_path, patch_text in patch_records
            ]
            with ProcessPoolExecutor(max_workers=workers) as pool:
                daily_results = list(pool.map(_compute_coverage_worker, args_list))

        filtered_results = [r for r in daily_results if r]
        for r in filtered_results:
            total_added = r['total_added_lines']
            if total_added > 0:
                print(f"    - {r['file_path']}: 追加 {total_added}行, うちカバー {r['covered_added_lines']}行 (カバレッジ: {r['patch_coverage']:.2f}%)")

        if filtered_results:
            processed_any = True
            df_result = pd.DataFrame(filtered_results)
            header = not output_file_path.exists() or output_file_path.stat().st_size == 0
            df_result.to_csv(output_file_path, mode='a', header=header, index=False, encoding='utf-8-sig')
            print(f"  ✔ 日付 '{date_str}' の結果を '{output_file_path}' に追記しました。")
            processed_dates.add(date_str)

    if processed_any or processed_dates:
        print(f"\n✔ プロジェクト '{project_name}' の処理が完了しました。結果は '{output_file_path}' に保存されています。")
    else:
        print(f"プロジェクト '{project_name}' で処理対象のデータが見つかりませんでした。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="revisions_with_commit_date CSV を直接処理してパッチカバレッジを計算するインメモリパイプライン。"
    )
    parser.add_argument(
        "-p",
        "--project",
        dest="projects",
        action="append",
        required=True,
        help="処理対象のプロジェクト名（複数指定可、カンマ区切り可）",
    )
    parser.add_argument(
        "--input",
        dest="input_dir",
        help="revisions_with_commit_date_<project>.csv が存在するディレクトリ",
    )
    parser.add_argument(
        "--repos",
        dest="repos_dir",
        help="差分取得に使用する git クローン済みリポジトリのディレクトリ",
    )
    parser.add_argument(
        "--coverage-out",
        dest="coverage_out",
        help="パッチカバレッジCSVの出力先ベースディレクトリ",
    )
    parser.add_argument(
        "--parsing-out",
        dest="parsing_out",
        help="HTML解析結果(JSON)を保存するディレクトリ（指定しない場合は保存しません）",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=16,
        help="カバレッジ計算を行う並列プロセス数 (既定: 4、1で逐次実行)",
    )
    args = parser.parse_args()

    projects = _normalize_projects(args.projects or [])
    if not projects:
        print("エラー: --project で少なくとも1つのプロジェクトを指定してください。")
        raise SystemExit(1)

    input_dir = Path(args.input_dir or DEFAULT_INPUT_CSV_DIRECTORY)
    if not input_dir.is_dir():
        print(f"エラー: 入力ディレクトリ '{input_dir}' が見つかりません。")
        raise SystemExit(1)

    repos_dir = Path(args.repos_dir or DEFAULT_CLONED_REPOS_DIRECTORY)
    if not repos_dir.is_dir():
        print(f"エラー: リポジトリディレクトリ '{repos_dir}' が見つかりません。")
        raise SystemExit(1)

    coverage_out_dir = Path(args.coverage_out or DEFAULT_OUTPUT_BASE_DIRECTORY)
    parsing_out_dir = Path(args.parsing_out) if args.parsing_out else None

    for project in projects:
        process_project(
            project_name=project,
            input_dir=input_dir,
            repos_dir=repos_dir,
            output_dir=coverage_out_dir / project,
            parsing_dir=parsing_out_dir,
            workers=args.workers,
        )

    print("\nすべての処理が完了しました。")


if __name__ == "__main__":
    main()
