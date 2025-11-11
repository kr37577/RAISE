# `additional_build_strategies.py` レビュー

## 背景
- 対象: `vuljit/analysis/research_question3/additional_build_strategies.py`
- 目的: RQ3 で利用する追加ビルド戦略実装の健全性を確認し、潜在的な欠陥や運用リスクを洗い出す。
- 観点: データ結合の前提、統計量の算出ロジック、外部副作用、パラメータの意味合い。

## 主な指摘

### 1. タイムラインと予測 CSV の日付正規化が一致せず、ラベル結合が失敗し得る
- 該当箇所: `vuljit/analysis/research_question3/additional_build_strategies.py:251-263`（タイムライン読み込み）、`348-369`（予測 CSV 読み込み）、`897-910`（日付結合）
- 内容: タイムラインの `merge_date_ts` は `pd.to_datetime(..., utc=True)` のみで正規化されず、元 CSV が「YYYY-MM-DD HH:MM:SS」形式の場合は時刻情報が残る。一方、予測 CSV 側は `.dt.normalize()` 済みの 00:00:00 UTC に丸められる。`_prepare_labelled_timeline()` は `merge_date_ts` で内部結合しているため、同日でも時刻が一致しないと `_strategy_label` がすべて欠落する。
- 影響: ラベル付きタイムラインが空扱いになり、Strategy1〜3 がそのプロジェクトを完全にスキップする。気付きにくいデータ欠落で分析結果を歪めるクリティカルな不具合。
- 改善案: タイムライン側でも `.dt.normalize()` してから `merge_date_ts` を保存する、もしくは `_prepare_labelled_timeline()` 入口で `timeline["merge_date_ts"] = timeline["merge_date_ts"].dt.normalize()` を行う。どちらかを実施し、両データソースの粒度を一致させる。

### 2. Strategy4 の教師データで commit 日付と merge 日付が混同され、目的変数が常に 0 になり得る
- 該当箇所: `1700-1708`（検出遅延を commit 日付で辞書化）、`1807-1815`（`merge_date` でルックアップ）
- 内容: `_build_regression_dataset()` は `detection_lookup[project][commit_date]` に遅延値を蓄積するが、実際のルックアップは `pd.to_datetime(row["merge_date"]).normalize()` をキーにしている。タイムライン列名が示す通り `merge_date` はマージ日時であり、コミット日時 (`commit_date_utc`) とは一般に一致しない。
- 影響: merge と commit の間にラグがある一般的な OSS では `detection_map.get(...)=[]` となり、`observed_additional_builds` が常に 0 に丸められる。結果として回帰モデルは定数列を学習し有効なスケジュールを生成できない。
- 改善案: タイムラインに commit ベースのキー（例: `commit_date_ts`）を保持し、検出遅延辞書と同じキーで突き合わせる。最低でも `merge_date` しか無い場合は、検出テーブル側を merge ベースに変換する補助関数を設け、一貫した座標系を確保する。

### 3. `global_budget` が総量制限になっていない（※現状 `None` なので実害なし）
- 該当箇所: `1520-1542`
- 内容: Strategy3 の `global_budget` は名称から全体予算を示唆するが、実装では各プロジェクトの `resolved_cap = min(requested_total, lopo_cap, global_budget)` として個別に適用されている。残余を管理する変数が存在せず、全プロジェクトで同じ値を使い回す形になっている。
- 影響: 任意の正値を設定した場合、プロジェクト数×`global_budget` までビルドが割り当てられ、総量制御のつもりで指定した利用者を誤誘導する恐れがある。一方、現状の運用では `global_budget=None` がデフォルトのため、問題は顕在化していない。
- 改善案: 引数を総量制限にするのであれば残余をグローバルで管理するよう修正し、もし「プロジェクトあたり上限」が意図なら引数名や CLI ドキュメントを `per_project_budget_cap` 等に改名して誤解を避ける。

### 4. Strategy4 実行時にデフォルトでリポジトリ配下へ JSON を書き出す（※現状は問題ないが副作用に注意）
- 該当箇所: `2048-2052`, `2140-2160`
- 内容: `diagnostics_output_path` を省略すると、`docs/reports/strategy4_diagnostics.json` に診断情報を常に書き込み、必要ならディレクトリを新規作成する。CLI から個別にパスを渡さない限り、実行のたびにワークツリーが更新される。
- 影響: 読み取り専用環境や CI での再現実験では、ファイル書き込みに失敗してジョブ自体が落ちる可能性がある。また「軽くモジュールを import して推論するだけ」で Git 差分が発生するため、利用者が気付きにくい副作用となる。ただし現状の利用フローでは意図的に `diagnostics_output_path` を指定しないため問題は出ていない。
- 改善案: デフォルトで書き込みをスキップするか、一時ディレクトリに出力して呼び出し元へパスを返すなど、IO 副作用を制御できる仕組みにすることを検討する。

## 補足
- 本レビューは 2024-10 時点のリポジトリ状態を前提としており、依存 CSV/設定ファイルは実際には別途整備されていると想定している。
- 追加で検証が必要な場合は `analysis/research_question3/tests/test_additional_build_strategies.py` を拡張し、ここで挙げたケース（例: commit/merge 日付のズレ）を再現するテストを用意することを推奨。
