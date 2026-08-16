#!/bin/bash
# v1.9 REINFORCE full-phase battery (20 runs: seeds 201-210 x clean/contrast d2, scope=full)
cd /home/feihm/carr_victim_server
mkdir -p results/reinforce_full
R=/home/feihm/carr_victim_server/results/reinforce_full
PIDS=()
for seed in $(seq 201 210); do
  ./run_reinforce_full.sh $seed clean $R/obstacle_sudden_REINFORCE_none_d2_s${seed}_fullvC > $R/none_s${seed}.log 2>&1 &
  PIDS+=($!)
  ./run_reinforce_full.sh $seed contrast $R/obstacle_sudden_REINFORCE_v3_d2_s${seed}_fullvC > $R/v3_s${seed}.log 2>&1 &
  PIDS+=($!)
done
echo "launched ${#PIDS[@]} REINFORCE full-phase runs"
echo "${PIDS[@]}" > $R/.pids
