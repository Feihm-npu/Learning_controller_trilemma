#!/bin/bash
# v1.10 Part B retained-shield escape control (3 runs: REINFORCE retained v3 d2 full, seeds 1-3)
cd /home/feihm/carr_victim_server
mkdir -p results/retained_v110
R=/home/feihm/carr_victim_server/results/retained_v110
PIDS=()
for seed in 1 2 3; do
  ./run_retained_v110.sh $seed $R/obstacle_retained_REINFORCE_v3_d2_s${seed} > $R/v3_s${seed}.log 2>&1 &
  PIDS+=($!)
done
echo "launched ${#PIDS[@]} retained control runs"
echo "${PIDS[@]}" > $R/.pids
