# scripts配下のデータ保存先まとめ

この資料は `vuljit/scripts` 内の代表的なスクリプトがどこにデータを保存するかを整理したものです。各パイプラインは環境変数で出力先を上書きできる設計になっており、未設定の場合はリポジトリ内の `datasets/` 系ディレクトリに保存されます。

## 基本的なディレクトリと環境変数

- `VULJIT_BASE_DATA_DIR`（既定: `datasets`）と `VULJIT_RESULTS_DIR`（既定: `datasets/model_outputs`）が分析済みデータとモデル出力のルートを決める [`modeling/settings.py`](../modeling/settings.py#L68-L83)。
- CLI やシェルスクリプトは `VULJIT_*` 系の環境変数を参照し、未指定時は `datasets/raw/` や `datasets/derived_artifacts/` 配下を既定値とする。
- `scripts/orchestration/config/default.yaml` には CLI で使う想定ディレクトリの雛形が定義されている（例: `datasets/raw/srcmap_json` や `datasets/metric_inputs`）。

## データ取得系 (`data_acquisition`)

| スクリプト | 既定保存先 | 上書き方法 | 補足 |
| --- | --- | --- | --- |
| `data_acquisition/coverage_download_reports.py` | `datasets/raw/coverage_report` | `--out`, `VULJIT_COVERAGE_DIR` | 取得対象 CSV やファイル種別も CLI/環境変数で調整可能 [`coverage_download_reports.py`](data_acquisition/coverage_download_reports.py#L345-L375)。 |
| `data_acquisition/coverage_download_reports.sh` | 同上（環境変数をエクスポート） | `VULJIT_COVERAGE_DIR`, `VULJIT_COVERAGE_ZIP_DIR` | Python 実行後の zip 化先は `datasets/derived_artifacts/coverage_zip` が既定。 |
| `data_acquisition/download_srcmap.py` | `datasets/raw/srcmap_json` | `-d/--dir`, `VULJIT_SRCDOWN_DIR` | CSV/期間の既定は OSS-Fuzz 脆弱性一覧 [`download_srcmap.py`](data_acquisition/download_srcmap.py#L126-L171)。 |
| `data_acquisition/download_srcmap.sh` | 同上 | `VULJIT_SRCDOWN_DIR`, `VULJIT_VUL_CSV` | Slurm 用ラッパー。 |
| `data_acquisition/ossfuzz_vulnerability_issue_report_extraction.py` | `datasets/derived_artifacts/vulnerability_reports/oss_fuzz_vulnerabilities.csv` | `--out`, `VULJIT_VUL_CSV` | `--cache-dir` で ZIP キャッシュ先を指定可能 [`ossfuzz_vulnerability_issue_report_extraction.py`](data_acquisition/ossfuzz_vulnerability_issue_report_extraction.py#L240-L290)。 |

## メトリクス抽出 (`metric_extraction`)

### コミット/テキストメトリクス

| スクリプト | 既定保存先 | 上書き方法・備考 |
| --- | --- | --- |
| `metric_extraction/build_commit_metrics_pipeline.py` | `<metrics_dir>/<project>/<project>_commit_metrics_with_tfidf.csv`（既定 `datasets/metric_inputs`） | `--metrics-dir`, `VULJIT_METRICS_DIR`。脆弱性 CSV は `--vuln-csv`/`VULJIT_VUL_CSV` で差し替え可 [`build_commit_metrics_pipeline.py`](metric_extraction/build_commit_metrics_pipeline.py#L201-L335, #L337-L365)。 |
| `metric_extraction/text_code_metrics/label.py` | `<output_dir>/<package>_commit_metrics_with_vulnerability_label.csv` | `--vuln_file` で参照 CSV を変更。既定は `/work/riku-ka/...` の絶対パスなので環境に合わせて要調整 [`label.py`](metric_extraction/text_code_metrics/label.py#L15-L112, #L134-L162)。 |
| `metric_extraction/text_code_metrics/vccfinder_commit_message_metrics.py` | `<metrics_dir>/<project>/<project>_commit_metrics_with_tfidf.csv` | `-m/--metrics-dir`。`collect_metrics_from_github_project.sh` から呼び出され、同ディレクトリに出力する設計 [`vccfinder_commit_message_metrics.py`](metric_extraction/text_code_metrics/vccfinder_commit_message_metrics.py#L55-L112, #L140-L166)。 |
| `metric_extraction/collect_code_text_metrics.py` | `merged_metrics.csv`（実行時 `-o` で指定） | `collect_metrics_from_github_project.sh` では `<metrics_dir>/<project>/<project>_code_text_metrics.csv` に書き出す [`collect_code_text_metrics.py`](metric_extraction/collect_code_text_metrics.py#L32-L200) と [`collect_metrics_from_github_project.sh`](metric_extraction/collect_metrics_from_github_project.sh#L7-L47)。 |

### カバレッジ集約

| スクリプト | 既定保存先 | 上書き方法・備考 |
| --- | --- | --- |
| `metric_extraction/coverage_aggregation/process_coverage_project.py` | `datasets/coverage_metrics/<project>/...` | `--out` または `VULJIT_COVERAGE_METRICS_DIR` で上書き可能。未指定時は `VULJIT_BASE_DATA_DIR/coverage_metrics` → `<repo>/datasets/coverage_metrics` の順でフォールバックする [`process_coverage_project.py`](metric_extraction/coverage_aggregation/process_coverage_project.py#L10-L58)。 |
| `orchestration/cli.py` の `metrics coverage-aggregate` サブコマンド | `datasets/coverage_metrics/<project>/...` | `--out`, `VULJIT_COVERAGE_METRICS_DIR`, `VULJIT_BASE_DATA_DIR` で上書き可。入力の既定は `data/coverage_gz`（`VULJIT_COVERAGE_DIR`） [`cli.py`](orchestration/cli.py#L190-L208)。 |

### パッチカバレッジ

| スクリプト | 既定保存先 | 上書き方法・備考 |
| --- | --- | --- |
| `metric_extraction/patch_coverage_pipeline/create_daily_diff.py` | `data/intermediate/patch_coverage/daily_diffs`（`VULJIT_INTERMEDIATE_DIR` 基準） | `--out`, `--src`, `--repos` で入出力を切り替え可能 [`create_daily_diff.py`](metric_extraction/patch_coverage_pipeline/create_daily_diff.py#L120-L209)。 |
| `metric_extraction/patch_coverage_pipeline/calculate_patch_coverage_per_project_test.py` | `<out>/<project>_patch_coverage.csv`（既定 `outputs/metrics/patch_coverage`） | `--out`, `VULJIT_PATCH_COVERAGE_OUT`, `VULJIT_PARSING_RESULTS_DIR` 等で制御。途中再開用に既存 CSV を追記する仕様 [`calculate_patch_coverage_per_project_test.py`](metric_extraction/patch_coverage_pipeline/calculate_patch_coverage_per_project_test.py#L1-L126)。 |
| `metric_extraction/patch_coverage_pipeline/calculate_patch_coverage.py` | `/work/riku-ka/patch_coverage_culculater/...` に固定 | 実験用スクリプトで絶対パスがハードコードされているため、利用前に定数を書き換える必要がある [`calculate_patch_coverage.py`](metric_extraction/patch_coverage_pipeline/calculate_patch_coverage.py#L12-L22)。 |

## モデリング (`modeling`)

| スクリプト | 既定保存先 | 上書き方法・備考 |
| --- | --- | --- |
| `modeling/aggregate_metrics_pipeline.py` | `<output_base>/<project>/<project>_daily_aggregated_metrics.csv`（既定 `datasets/derived_artifacts/aggregate`） | CLI の `--metrics`, `--coverage`, `--patch-coverage`, `--out` や `VULJIT_*` で制御 [`aggregate_metrics_pipeline.py`](modeling/aggregate_metrics_pipeline.py#L748-L814)。 |
| `modeling/main_per_project.py` | `datasets/model_outputs/<model>/<project>/...` | [`settings.py`](modeling/settings.py#L68-L83) の環境変数でモデル出力先を変更可能。実験ごとに `*_metrics.json`, `*_importances.csv`, `*_per_fold_metrics.csv`, `*_daily_aggregated_metrics_with_predictions.csv` を生成 [`main_per_project.py`](modeling/main_per_project.py#L218-L315)。 |
| `modeling/evaluation.py` | `MODEL_OUTPUT_DIRECTORY`（モデル）と `LOGS_DIRECTORY`（HPO 結果） | `settings.SAVE_BEST_MODEL` や `SAVE_HYPERPARAM_RESULTS` を有効化すると joblib/JSON を保存する [`evaluation.py`](modeling/evaluation.py#L139-L207)。 |
| `modeling/predict_one_project.sh`, `aggregate_metrics_pipeline.sh` など | それぞれ `VULJIT_BASE_DATA_DIR` などをハードコードしている | 動作前に環境変数で上書きすると再配置が容易。 |

## オーケストレーション (`orchestration`)

- `orchestration/cli.py` は `download-srcmap`, `download-coverage`, `metrics`, `prediction` などのコマンドで各処理を実行し、未指定時は `scripts/orchestration/data/...` 配下を利用する (`VULJIT_*` 環境変数で上書き可能)。
- `orchestration/config/default.yaml` には CLI 用の標準パス (`datasets/raw/oss_fuzz_vulns.csv` など) がまとめられている。
- `orchestration/prediction.sh`・`prediction/*.py` は `datasets/derived_artifacts/aggregate` を入力、`datasets/model_outputs` を出力として想定している。

## プロジェクトマッピング (`project_mapping`)

| スクリプト | 既定保存先 | 備考 |
| --- | --- | --- |
| `project_mapping/mapping.py` | `scripts/project_mapping/project_mapping.csv` | 入力 CSV から `project_id,directory_name` の対応表を生成 [`mapping.py`](project_mapping/mapping.py#L61-L92)。 |
| `project_mapping/mapping_filter.py` | `scripts/project_mapping/filtered_project_mapping.csv` | `--mapping`, `--projects`, `--output` でパス指定可 [`mapping_filter.py`](project_mapping/mapping_filter.py#L5-L45)。 |
| `project_mapping/count_c_cpp_projects.py` | 指定した `--out-csv`（未指定なら標準出力） | CLI 経由で呼び出す想定。 |

## ユーティリティ

- `utilities/zip.sh` は引数で受け取ったディレクトリ群を zip 化し、3 番目の引数（既定は元ディレクトリ）に保存する。Slurm 環境で動かす前提のため、ローカル利用時は引数に注意。
- `utilities/single_zip.sh` も同様に個別ディレクトリを圧縮する簡易ツール。

## 補足

- `calculate_patch_coverage.py` や `text_code_metrics/label.py` など、一部スクリプトは `/work/riku-ka/...` といった開発者ローカルの絶対パスを既定値にしている。利用環境に合わせて変数や環境変数を先に調整すること。
- `scripts/orchestration` 経由で実行する場合、コマンドライン引数より `.env`（存在すれば）→ 環境変数 → 既定値の順に参照されるため、グローバルな出力先を統一したい場合は `.env` もしくは環境変数の設定が便利。
