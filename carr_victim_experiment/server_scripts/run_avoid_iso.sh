#!/bin/bash
# v1.8 avoid-domain shield-on isolation: single run (seed, clean|contrast, outdir)
# Usage: run_avoid_iso.sh <seed> <clean|contrast> <outdir>
set -e
source /home/feihm/anaconda3/etc/profile.d/conda.sh
conda activate carr
cd /home/feihm/carr_victim_server/safe_RL_POMDPs_patched
SEED=$1; POISON=$2; OUTDIR=$3
if [ "$POISON" = "clean" ]; then PNAME=clean; PDELTA=0.0; else PNAME=contrast; PDELTA=2.0; fi
export OMP_NUM_THREADS=1
export TF_NUM_INTRAOP_THREADS=1
export TF_NUM_INTEROP_THREADS=1
python run_carr_victim.py --grid-model surveillance --constants N=6,RADIUS=3 \
  --learning-method REINFORCE --max-runs 5000 --maxsteps 100 \
  --obs-level BELIEF_SUPPORT --valuations --goal-value 1000 \
  --seed "$SEED" --switch-shield HARD --shield-episode 1000 \
  --at-retirement-eps 1000 --final-eval-eps 5000 \
  --poison-name "$PNAME" --poison-delta "$PDELTA" --poison-scope shield-on \
  --fname _VICTIM --no-overwrite --output-dir "$OUTDIR"
