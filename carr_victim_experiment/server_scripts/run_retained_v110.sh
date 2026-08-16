#!/bin/bash
# v1.10 Part B retained-shield escape control — single REINFORCE retained poisoned run
# Usage: run_retained_v110.sh <seed> <outdir>
set -e
source /home/feihm/anaconda3/etc/profile.d/conda.sh
conda activate carr
cd /home/feihm/carr_victim_server/safe_RL_POMDPs_patched
SEED=$1; OUTDIR=$2
export OMP_NUM_THREADS=1
export TF_NUM_INTRAOP_THREADS=1
export TF_NUM_INTEROP_THREADS=1
python run_carr_victim.py --grid-model obstacle --constants N=6 \
  --learning-method REINFORCE --max-runs 5000 --maxsteps 100 \
  --obs-level BELIEF_SUPPORT --valuations --goal-value 1000 \
  --seed "$SEED" --switch-shield RETAINED --shield-episode 5000 \
  --at-retirement-eps 1000 --final-eval-eps 5000 \
  --poison-name contrast --poison-delta 2.0 --poison-scope full \
  --fname _VICTIM --no-overwrite --output-dir "$OUTDIR"
