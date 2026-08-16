#!/bin/bash
# v1.8 avoid-domain shield-on isolation battery (6 runs, seeds 1-3) — run AFTER fidelity gate passes
cd /home/feihm/carr_victim_server
mkdir -p results/avoid_iso
R=/home/feihm/carr_victim_server/results/avoid_iso
PIDS=(); i=0
for seed in 1 2 3; do
  ./run_avoid_iso.sh $seed clean $R/avoid_sudden_REINFORCE_none_d2_s${seed} > $R/none_s${seed}.log 2>&1 &
  PIDS+=($!); i=$((i+1))
  ./run_avoid_iso.sh $seed contrast $R/avoid_sudden_REINFORCE_v3_d2_s${seed} > $R/v3_s${seed}.log 2>&1 &
  PIDS+=($!); i=$((i+1))
done
echo "launched $i isolation runs"
echo "${PIDS[@]}" > $R/.pids
