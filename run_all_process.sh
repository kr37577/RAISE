#!/bin/bash

cd replication
echo "[info] Starting all processes..."
echo "[info] Step 1: Data Acquisition"
bash data_acquisition.sh
echo "[info] Step 2: OSS-Fuzz Cloning and Analysis"
bash ossfuzz_clone_and_analyze.sh
echo "[info] Step 3: Metrics Extraction"
bash metrics_extraction.sh
echo "[info] Step 4: Metrics Aggregation"
bash aggregate_metrics_pipeline.sh
echo "[info] Step 5: Model Training"
bash cross_project_prediction.sh
echo "[info] Step 6: RQ1/2 Results Generation"
bash RQ1_2.sh
echo "[info] Step 7: RQ3 Simulation"
bash RQ3.sh
cd ..

echo "[info] All processes completed."