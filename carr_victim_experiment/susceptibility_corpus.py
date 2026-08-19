#!/usr/bin/env python3
"""Canonical Carr 2x2 susceptibility-corpus construction.

All report scripts call this module so the SAC namespace cannot drift between
six and ten seeds.  The locked corpus contains 20 full-phase pairs, 20
shield-on isolation pairs, ten SAC isolation pairs, and three avoid-domain
pairs, for 53 paired training runs.
"""

from __future__ import annotations

import os
from collections.abc import Callable


PairReader = Callable[[str, str], dict | None]


BATTERIES = (
    ("REINFORCE full", "obstacle_sudden_REINFORCE_none_d2_s",
     "obstacle_sudden_REINFORCE_v3_d2_s", range(201, 211), "_fullvC"),
    ("REINFORCE isolation", "obstacle_sudden_REINFORCE_none_d2_s",
     "obstacle_sudden_REINFORCE_v3_d2_s", range(201, 211), ""),
    ("PPO full", "obstacle_sudden_PPO_none_d2_s",
     "obstacle_sudden_PPO_v3_d2_s", range(101, 111), "_fullvC"),
    ("PPO isolation", "obstacle_sudden_PPO_none_d2_s",
     "obstacle_sudden_PPO_v3_d2_s", range(101, 111), ""),
    ("SAC isolation", "obstacle_sudden_SAC_none_d2_s",
     "obstacle_sudden_SAC_v3_d2_s", range(401, 411), ""),
    ("avoid isolation", "avoid_sudden_REINFORCE_none_d2_s",
     "avoid_sudden_REINFORCE_v3_d2_s", range(1, 4), ""),
)


def susceptibility_rows(base: str, seed_row: PairReader) -> list[tuple[str, float, bool]]:
    rows: list[tuple[str, float, bool]] = []
    for category, clean_prefix, poison_prefix, seeds, suffix in BATTERIES:
        for seed in seeds:
            pair = seed_row(
                os.path.join(base, f"{clean_prefix}{seed}{suffix}"),
                os.path.join(base, f"{poison_prefix}{seed}{suffix}"),
            )
            if pair is not None:
                rows.append((category, float(pair["ca"]), bool(pair["strict"])))
    return rows


def susceptibility_2x2(base: str, seed_row: PairReader) -> dict[str, int]:
    rows = susceptibility_rows(base, seed_row)
    cells = {"lo_pos": 0, "lo_neg": 0, "hi_pos": 0, "hi_neg": 0}
    for _category, clean_at_retirement, positive in rows:
        level = "lo" if clean_at_retirement < 0.5 else "hi"
        outcome = "pos" if positive else "neg"
        cells[f"{level}_{outcome}"] += 1
    cells["n"] = len(rows)
    return cells


def append_markdown(out: list[str], cells: dict[str, int]) -> None:
    out.extend(
        [
            "### Recomputed 2x2 susceptibility cross-tabulation (canonical 53-run corpus)",
            "",
            "| | positive | not positive |",
            "|---|---|---|",
            f"| clean at-ret < 0.5 | {cells['lo_pos']} | {cells['lo_neg']} |",
            f"| clean at-ret >= 0.5 | {cells['hi_pos']} | {cells['hi_neg']} |",
            "",
            f"> Rows: {cells['n']} paired training runs across full-phase and isolation "
            "batteries, all three learners, and both domains.",
            "",
        ]
    )
