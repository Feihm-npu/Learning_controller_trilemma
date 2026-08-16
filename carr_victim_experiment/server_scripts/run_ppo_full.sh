#!/bin/bash
# v1.9 PPO full-phase single run (server vC code)
# Usage: run_ppo_full.sh <seed> <clean|contrast> <outdir>
set -e
source /home/feihm/anaconda3/etc/profile.d/conda.sh
conda activate carr
cd /home/feihm/carr_victim_server/safe_RL_POMDPs_patched
SEED=$1; POISON=$2; OUTDIR=$3
export OMP_NUM_THREADS=1
export TF_NUM_INTRAOP_THREADS=1
export TF_NUM_INTEROP_THREADS=1
if [ "$POISON" = "clean" ]; then PNAME=clean; PDELTA=0.0; else PNAME=contrast; PDELTA=2.0; fi
python run_carr_victim.py --grid-model obstacle --constants N=6 \
  --learning-method PPO --max-runs 100000 --maxsteps 100 \
  --obs-level BELIEF_SUPPORT --valuations --goal-value 1000 \
  --seed "$SEED" --switch-shield HARD --shield-episode 4000 \
  --at-retirement-eps 1000 --final-eval-eps 5000 \
  --poison-name "$PNAME" --poison-delta "$PDELTA" --poison-scope full \
  --fname _VICTIM --no-overwrite --output-dir "$OUTDIR"
