#!/bin/bash
# v1.12 SAC retirement-boundary isolation extension (6 runs: seeds 404-406 x clean/contrast d2, scope=shield-on)
cd ${ARTIFACT_ROOT}
mkdir -p results/sac_v112
R=${ARTIFACT_ROOT}/results/sac_v112
PIDS=()
for seed in 404 405 406; do
  ./run_sac_v112.sh $seed clean $R/obstacle_sudden_SAC_none_d2_s${seed} > $R/none_s${seed}.log 2>&1 &
  PIDS+=($!)
  ./run_sac_v112.sh $seed contrast $R/obstacle_sudden_SAC_v3_d2_s${seed} > $R/v3_s${seed}.log 2>&1 &
  PIDS+=($!)
done
echo "launched ${#PIDS[@]} SAC v1.12 isolation runs"
echo "${PIDS[@]}" > $R/.pids
