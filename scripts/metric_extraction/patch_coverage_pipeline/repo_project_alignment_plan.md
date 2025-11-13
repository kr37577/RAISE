# Patch-Coverage 入力整合性 改修計画

## 目的
OSS-Fuzz プロジェクト名 (`project_name`) と `repo_name` が一致しないケース（例: `php` vs `php-src`）でもパッチカバレッジを算出できるよう、入力 CSV とパイプライン全体を調整する。

---

## 実装タスク

### 1. `create_project_csvs_from_srcmap.py` の拡張
1. `generate_revisions()` が書き出すヘッダーを `['project', 'date', 'repo_name', 'url', 'revision']` に変更。
2. 各レコードへ `project_name` を新列として追加 (`project` 列)。
3. 既存 CSV を再生成する必要がある旨を docstring / ログに追加。

### 2. `revision_with_date.py` の対応
1. `pd.read_csv()` 時に `project` 列を保持したまま DataFrame を処理。
2. `df.apply(...)` で `commit_date` を付与した後も `project` 列を残す。
3. `revisions_with_commit_date_<project>.csv` のヘッダーへ `project` を含める。

### 3. 既存 CSV の更新
1. 手順:
   - `create_project_csvs_from_srcmap.py` を実行して `revisions_<project>.csv` を全再生成。
   - 続けて `revision_with_date.py` / `prepare_patch_coverage_inputs.py` を実行し、`revisions_with_commit_date_<project>.csv` を再作成。
2. もし一括再生成が困難な場合は、暫定策として `python` スクリプトで既存 CSV に `project` 列を追記（全行同じ OSS-Fuzz 名を設定）。

### 4. `run_culculate_patch_coverage_pipeline.py` のフィルタ修正
1. 入力 DataFrame 読み込み後に以下を実施:
   ```python
   df['project'] = df['project'] if 'project' in df else df['repo_name']
   df = df[df['project'] == project_name].copy()
   ```
2. 旧 CSV (project 列なし) でも `repo_name` をフォールバックに使えるよう、上記のような後方互換処理を入れる。

### 5. 動作確認
1. `php` を含む複数プロジェクトで `prepare_patch_coverage_inputs.py` → `run_culculate_patch_coverage_pipeline.py` を実行し、`*_patch_coverage.csv` が生成されることを確認。
2. `project` 列無しの旧 CSV を読み込ませた場合も落ちないことを確認（フォールバックの動作確認）。

### 6. ドキュメント / 付随スクリプト更新
1. `README` やジョブスクリプトに「新たに `project` 列が追加された」こと、旧 CSV は再生成が必要なことを追記。
2. 必要に応じて `prepare_patch_coverage_inputs.py` のヘルプメッセージに注意書きを追加。

---

## 補足
- 既存の `repo_name` 列は Git 差分計算や GCS レポートとの対応に引き続き使用するため、削除しない。
- CSV 再生成が完了するまでは `project` 列が空のファイルが混在する可能性があるため、フォールバック処理は必須。

## 追加で調査・確認すること
- `create_project_csvs_from_srcmap.py` が `project` 列を正しく出力するか、実ファイルを再生成して内容を確認する。既存 CSV に列が無い・空の場合の扱いも要把握。
- `revisions_with_commit_date_<project>.csv` を再生成しない暫定対応時に `project` 列が欠落するリスクがあるため、`prepare_patch_coverage_inputs.py` の各ステージをどう実行・スキップすべきか手順を具体化する。
- `run_culculate_patch_coverage_pipeline.py` へ導入予定の `project` ベースフィルタが、列が存在しない／空文字の入力でも `repo_name` へフォールバックできるかをテストで確認する。
