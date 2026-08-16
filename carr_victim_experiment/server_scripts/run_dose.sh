#!/bin/bash
# v1.7 dose-response: single full-phase V3-contrast run at arbitrary delta (server vC code)
# Usage: run_dose.sh <seed> <delta> <outdir>
set -e
source /home/feihm/anaconda3/etc/profile.d/conda.sh
conda activate carr
cd /home/feihm/carr_victim_server/safe_RL_POMDPs_patched
SEED=$1; DELTA=$2; OUTDIR=$3
export OMP_NUM_THREADS=1
export TF_NUM_INTRAOP_THREADS=1
export TF_NUM_INTEROP_THREADS=1
python run_carr_victim.py --grid-model obstacle --constants N=6 \
  --learning-method REINFORCE --max-runs 5000 --maxsteps 100 \
  --obs-level BELIEF_SUPPORT --valuations --goal-value 1000 \
  --seed "$SEED" --switch-shield HARD --shield-episode 1000 \
  --at-retirement-eps 1000 --final-eval-eps 5000 \
  --poison-name contrast --poison-delta "$DELTA" --poison-scope full \
  --fname _VICTIM --no-overwrite --output-dir "$OUTDIR"
