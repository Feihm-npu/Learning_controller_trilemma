#!/bin/bash
# Sync server experiment run-dirs into local results/ (new dir names, no overwrite),
# then re-run the local analysis pipeline. Idempotent: only syncs dirs present on server.
# Usage: ./carr_victim_experiment/sync_from_server.sh
set -e
HOST="${1:-NUSdgx}"
REMOTE=/home/feihm/carr_victim_server/results
LOCAL=$(cd "$(dirname "$0")/.." && pwd)/carr_victim_experiment/results
mkdir -p "$LOCAL"

sync_dirs() {
  local src="$1" base="$2"
  echo "--- syncing $src (name $base*) ---"
  local n=0
  while IFS= read -r d; do
    name=$(basename "$d")
    if [ -d "$LOCAL/$name" ] && find "$LOCAL/$name" -maxdepth 1 -name "*_summary.json" | grep -q .; then
      echo "  skip $name (exists, has summary)"
      continue
    fi
    if ! ssh -n "$HOST" "find '$d' -maxdepth 1 -name '*_summary.json' | grep -q ."; then
      echo "  skip $name (no summary on server yet)"
      continue
    fi
    echo "  rsync $name"
    rsync -az "$HOST:$d/" "$LOCAL/$name/" && n=$((n+1))
  done < <(ssh -n "$HOST" "find '$REMOTE/$src' -maxdepth 1 -type d -name '$base*' 2>/dev/null | sort")
  echo "  synced $n new dir(s)"
}

sync_dirs b1 obstacle_sudden_PPO_
sync_dirs v16 obstacle_sudden_REINFORCE_
sync_dirs fullvC obstacle_sudden_REINFORCE_
sync_dirs dose obstacle_sudden_REINFORCE_
sync_dirs avoid_fid avoid_
sync_dirs avoid_iso avoid_
sync_dirs ppo_full obstacle_sudden_PPO_
sync_dirs reinforce_full obstacle_sudden_REINFORCE_
sync_dirs sac_smoke obstacle_sudden_SAC_
sync_dirs sac_v110 obstacle_sudden_SAC_
sync_dirs retained_v110 obstacle_retained_REINFORCE_

# v1.9 full-phase at-scale + v1.10 SAC/retained analyzers (added when scripts land)
run_if_present() {
  if [ -x "$1" ] || [ -f "$1" ]; then
    ../.venv-safe-control/bin/python "$1" "${@:2}"
  else
    echo "  (skip $1: not present yet)"
  fi
}

echo "--- local analysis ---"
cd "$LOCAL/.."
../.venv-safe-control/bin/python analyze_ppo_isolation.py --ppo        --out results/ppo_isolation_report.md
../.venv-safe-control/bin/python analyze_ppo_isolation.py --reinforce16 --out results/reinforce16_isolation_report.md
../.venv-safe-control/bin/python analyze_fullvC.py
../.venv-safe-control/bin/python analyze_dose_response.py
../.venv-safe-control/bin/python analyze_seed_heterogeneity.py
../.venv-safe-control/bin/python make_fig6.py
../.venv-safe-control/bin/python make_fig_dose_response.py
../.venv-safe-control/bin/python analyze_avoid.py
run_if_present analyze_fullphase.py
run_if_present analyze_sac.py
run_if_present analyze_retained_v110.py
echo "--- done ---"
