#!/bin/bash
# v1.10 Part B retained-shield escape control (3 runs: REINFORCE retained v3 d2 full, seeds 1-3)
cd ${ARTIFACT_ROOT}
mkdir -p results/retained_v110
R=${ARTIFACT_ROOT}/results/retained_v110
PIDS=()
for seed in 1 2 3; do
  ./run_retained_v110.sh $seed $R/obstacle_retained_REINFORCE_v3_d2_s${seed} > $R/v3_s${seed}.log 2>&1 &
  PIDS+=($!)
done
echo "launched ${#PIDS[@]} retained control runs"
echo "${PIDS[@]}" > $R/.pids
