#!/bin/bash
# v1.10 Part A SAC retirement-boundary isolation (6 runs: seeds 401-403 x clean/contrast d2, scope=shield-on)
cd /home/feihm/carr_victim_server
mkdir -p results/sac_v110
R=/home/feihm/carr_victim_server/results/sac_v110
PIDS=()
for seed in 401 402 403; do
  ./run_sac_v110.sh $seed clean $R/obstacle_sudden_SAC_none_d2_s${seed} > $R/none_s${seed}.log 2>&1 &
  PIDS+=($!)
  ./run_sac_v110.sh $seed contrast $R/obstacle_sudden_SAC_v3_d2_s${seed} > $R/v3_s${seed}.log 2>&1 &
  PIDS+=($!)
done
echo "launched ${#PIDS[@]} SAC isolation runs"
echo "${PIDS[@]}" > $R/.pids
