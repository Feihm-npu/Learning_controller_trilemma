#!/bin/bash
# v1.13 SAC retirement-boundary isolation extension (8 runs: seeds 407-410 x clean/contrast d2, scope=shield-on)
cd /home/feihm/carr_victim_server
mkdir -p results/sac_v113
R=/home/feihm/carr_victim_server/results/sac_v113
PIDS=()
for seed in 407 408 409 410; do
  ./run_sac_v113.sh $seed clean $R/obstacle_sudden_SAC_none_d2_s${seed} > $R/none_s${seed}.log 2>&1 &
  PIDS+=($!)
  ./run_sac_v113.sh $seed contrast $R/obstacle_sudden_SAC_v3_d2_s${seed} > $R/v3_s${seed}.log 2>&1 &
  PIDS+=($!)
done
echo "launched ${#PIDS[@]} SAC v1.13 isolation runs"
echo "${PIDS[@]}" > $R/.pids
