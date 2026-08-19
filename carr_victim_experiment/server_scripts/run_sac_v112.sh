#!/bin/bash
# v1.12 SAC retirement-boundary isolation extension — single run (seed, clean|contrast, outdir)
# Usage: run_sac_v112.sh <seed> <clean|contrast> <outdir>
set -e
source ${CONDA_ROOT}/etc/profile.d/conda.sh
conda activate carr
cd ${ARTIFACT_ROOT}/safe_RL_POMDPs_patched
SEED=$1; POISON=$2; OUTDIR=$3
export OMP_NUM_THREADS=1
export TF_NUM_INTRAOP_THREADS=1
export TF_NUM_INTEROP_THREADS=1
if [ "$POISON" = "clean" ]; then PNAME=clean; PDELTA=0.0; else PNAME=contrast; PDELTA=2.0; fi
python run_carr_victim.py --grid-model obstacle --constants N=6 \
  --learning-method SAC --max-runs 100000 --maxsteps 100 \
  --obs-level BELIEF_SUPPORT --valuations --goal-value 1000 \
  --seed "$SEED" --switch-shield HARD --shield-episode 100000 \
  --at-retirement-eps 1000 --final-eval-eps 5000 \
  --poison-name "$PNAME" --poison-delta "$PDELTA" --poison-scope shield-on \
  --fname _VICTIM --no-overwrite --output-dir "$OUTDIR"
