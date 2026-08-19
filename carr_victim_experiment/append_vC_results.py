#!/usr/bin/env python3
"""Append vC-family runs to aggregate_table_v2.csv from per-run *_summary.json files.

Usage:  python carr_victim_experiment/append_vC_results.py

Reads run dirs under carr_victim_experiment/results/ that contain a
`*_VICTIM_summary.json` (local runs use `obstacle-6-computed-shield_...`,
server-synced runs use `obstacle-N-6-computed-shield_...`), maps them to
table rows, and appends only rows that are not already present (matched on
method/poison/delta/seed/scope/version). Never overwrites existing rows.

Scope and version are taken from the summary's `poison_scope` field and the
directory name:
  * poison_scope absent (legacy runs)  -> scope=full,  version=vA
    (old PPO full-phase s1-3; old REINFORCE v3 d10 s1-3)
  * poison_scope present:
      - `_fullvC` suffix               -> scope=poison_scope, version=vC (v1.4)
      - REINFORCE seed >= 201          -> scope=poison_scope, version=v16 (v1.6)
      - else                           -> scope=poison_scope, version=vC (v1.5)
  * delta is forced to 0.0 for clean runs (dirnames carry the contrast delta).
"""
import csv, glob, json, os, re, sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
CSV = os.path.join(BASE, "aggregate_table_v2.csv")
SUMMARY_GLOBS = ("obstacle-6-computed-shield_VICTIM_summary.json",
                 "obstacle-N-6-computed-shield_VICTIM_summary.json")

FIELDS = ["env","condition","method","poison","delta","seed","runs","during","after",
          "frac","first_ep","first_step","disagree","scope","version",
          "at_ret_frac","at_ret_first","at_ret_disagree","dir","notes","flag"]

# directory name -> (condition, method, poison, delta, seed, fullvC-suffix)
# fullvC names: obstacle_sudden_REINFORCE_{none,constant,risk,contrast}_d{2,10}_s{1,2,3}_fullvC
# v1.5 PPO:     obstacle_sudden_PPO_{none,v3}_d2_s{101..110}
# v1.6 REINFORCE: obstacle_sudden_REINFORCE_{none,v3}_d2_s{201..210}
# v1.10 SAC:    obstacle_sudden_SAC_{none,v3}_d2_s{401..403}
# v1.10 retained: obstacle_retained_REINFORCE_v3_d2_s{1,2,3}
# legacy vA:    obstacle_sudden_PPO_{none,v3}_d2_s{1,2,3};
#               obstacle_sudden_REINFORCE_{none,v3}_d{2,10}_s{1,2,3} (older runs)
DIRNAME_RE = re.compile(
    r"obstacle_(?P<condition>sudden|retained)_"
    r"(?P<method>REINFORCE|PPO|SAC)_"
    r"(?P<poison>none|constant|risk|contrast|v3)_"
    r"d(?P<delta>[0-9.]+)_"
    r"s(?P<seed>\d+)"
    r"(?P<suffix>_fullvC)?"
)


def parse_dirname(dn):
    m = DIRNAME_RE.fullmatch(dn)
    if not m:
        return None
    poison_map = {"none": "clean", "v3": "contrast"}
    poison = poison_map.get(m.group("poison"), m.group("poison"))
    delta = float(m.group("delta"))
    seed = int(m.group("seed"))
    return dict(condition=m.group("condition"), method=m.group("method"),
                poison=poison, delta=delta, seed=seed,
                suffix=bool(m.group("suffix")))


def find_summary(dn):
    for g in SUMMARY_GLOBS:
        p = os.path.join(BASE, dn, g)
        if os.path.isfile(p):
            return p
    return None


def load_row(dn):
    meta = parse_dirname(dn)
    if meta is None:
        return None
    sfile = find_summary(dn)
    if sfile is None:
        return None
    with open(sfile) as fh:
        s = json.load(fh)
    poison_scope = s.get("poison_scope")  # None for legacy vA runs
    at = s.get("at_retirement_stats") or {}
    ev = s.get("eval_stats") or {}

    poison = meta["poison"]
    delta = 0.0 if poison == "clean" else meta["delta"]

    if poison_scope is None:
        scope, version = "full", "vA"
    elif meta["suffix"]:
        scope, version = poison_scope, "vC"
    elif meta["method"] == "REINFORCE" and meta["seed"] >= 201:
        scope, version = poison_scope, "v16"
    else:
        scope, version = poison_scope, "vC"

    notes = "retained shield (v1.10.2)" if meta["condition"] == "retained" else ""
    row = {
        "env": "obstacle", "condition": meta["condition"],
        "method": meta["method"], "poison": poison,
        "delta": str(delta), "seed": str(meta["seed"]),
        "runs": str(s.get("cfg", {}).get("max_runs", "")),
        "during": str(s.get("during_violations", "")),
        "after": str(ev.get("num_violations", "")),
        "frac": str(ev.get("violation_fraction", "")),
        "first_ep": str(ev.get("first_violation_episode", "")),
        "first_step": str(ev.get("first_violation_step", "")),
        "disagree": str(ev.get("disagreement_fraction", "")),
        "scope": scope, "version": version,
        "at_ret_frac": str(at.get("violation_fraction", "")),
        "at_ret_first": str(at.get("first_violation_episode", "")),
        "at_ret_disagree": str(at.get("disagreement_fraction", "")),
        "dir": os.path.join(BASE, dn),
        "notes": notes, "flag": "",
    }
    return row


def key(r):
    return (r["condition"], r["method"], r["poison"], r["delta"],
            r["seed"], r["scope"], r["version"])


def main():
    existing = []
    if os.path.isfile(CSV):
        with open(CSV) as fh:
            existing = list(csv.DictReader(fh))
    have = {key(r) for r in existing}

    dirs = sorted(d for d in os.listdir(BASE)
                  if os.path.isdir(os.path.join(BASE, d))
                  and find_summary(d))
    added = 0
    for dn in dirs:
        row = load_row(dn)
        if row is None:
            continue
        if key(row) in have:
            print(f"skip (present): {dn}")
            continue
        existing.append(row)
        have.add(key(row))
        added += 1
        print(f"add: {dn} -> {row['method']}/{row['poison']}/d{row['delta']}/s{row['seed']}/{row['scope']}/{row['version']}")

    with open(CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(existing)
    print(f"wrote {CSV}: {len(existing)} rows total, {added} added")


if __name__ == "__main__":
    main()
