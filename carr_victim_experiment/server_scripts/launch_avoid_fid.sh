#!/bin/bash
# v1.8 avoid-domain fidelity gate (4 runs, clean, seed 1)
cd /home/feihm/carr_victim_server
mkdir -p results/avoid_fid
R=/home/feihm/carr_victim_server/results/avoid_fid
PIDS=(); i=0
for spec in "noshield avoid_noshield_s1_fid" "retained avoid_retained_s1_fid" "sudden avoid_sudden_s1_fid" "smooth avoid_smooth_s1_fid"; do
  set -- $spec; mode=$1; name=$2
  ./run_avoid_fid.sh "$mode" $R/$name > $R/${mode}.log 2>&1 &
  PIDS+=($!); i=$((i+1))
done
echo "launched $i fidelity runs"
echo "${PIDS[@]}" > $R/.pids
