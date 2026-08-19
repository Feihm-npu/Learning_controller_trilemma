#!/bin/bash
# v1.10 Part A SAC pipeline smoke (2 runs: clean + contrast, seed 499, max-runs 2000)
cd ${ARTIFACT_ROOT}
mkdir -p results/sac_smoke
R=${ARTIFACT_ROOT}/results/sac_smoke
PIDS=()
./run_sac_smoke.sh clean $R/obstacle_sudden_SAC_none_d2_s499_smoke > $R/none_s499.log 2>&1 &
PIDS+=($!)
./run_sac_smoke.sh contrast $R/obstacle_sudden_SAC_v3_d2_s499_smoke > $R/v3_s499.log 2>&1 &
PIDS+=($!)
echo "launched ${#PIDS[@]} SAC smoke runs"
echo "${PIDS[@]}" > $R/.pids
