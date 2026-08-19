#!/bin/bash
# v1.9 PPO full-phase battery (20 runs: seeds 101-110 x clean/contrast d2, scope=full)
cd ${ARTIFACT_ROOT}
mkdir -p results/ppo_full
R=${ARTIFACT_ROOT}/results/ppo_full
PIDS=()
for seed in $(seq 101 110); do
  ./run_ppo_full.sh $seed clean $R/obstacle_sudden_PPO_none_d2_s${seed}_fullvC > $R/none_s${seed}.log 2>&1 &
  PIDS+=($!)
  ./run_ppo_full.sh $seed contrast $R/obstacle_sudden_PPO_v3_d2_s${seed}_fullvC > $R/v3_s${seed}.log 2>&1 &
  PIDS+=($!)
done
echo "launched ${#PIDS[@]} PPO full-phase runs"
echo "${PIDS[@]}" > $R/.pids
