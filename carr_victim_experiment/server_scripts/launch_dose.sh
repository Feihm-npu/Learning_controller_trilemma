#!/bin/bash
# v1.7 dose-response battery launch (10 runs, seed 1, server vC code)
cd ${ARTIFACT_ROOT}
mkdir -p results/dose
R=${ARTIFACT_ROOT}/results/dose
PIDS=()
i=0
# Primary: full-phase contrast on transfer-sensitive seed 1 (delta 0.1,0.25,0.5,1.0)
for spec in "0.1 d0p1" "0.25 d0p25" "0.5 d0p5" "1.0 d1p0"; do
  set -- $spec; d=$1; name=$2
  ./run_dose.sh 1 "$d" $R/obstacle_sudden_REINFORCE_contrast_${name}_s1_doser > $R/full_${name}.log 2>&1 &
  PIDS+=($!); i=$((i+1))
done
# Secondary: shield-on-only clean + contrast on seed 1
./run_shieldon_dose.sh 1 0.0 $R/obstacle_sudden_REINFORCE_none_d0_s1_shieldon_doser > $R/so_clean.log 2>&1 &
PIDS+=($!); i=$((i+1))
for spec in "0.1 d0p1" "0.25 d0p25" "0.5 d0p5" "1.0 d1p0" "2.0 d2p0"; do
  set -- $spec; d=$1; name=$2
  ./run_shieldon_dose.sh 1 "$d" $R/obstacle_sudden_REINFORCE_contrast_${name}_s1_shieldon_doser > $R/so_${name}.log 2>&1 &
  PIDS+=($!); i=$((i+1))
done
echo "launched $i runs"
echo "${PIDS[@]}" > $R/.pids
