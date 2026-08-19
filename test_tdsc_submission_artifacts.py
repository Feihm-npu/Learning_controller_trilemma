"""Submission-gate checks for generated tables, claim locks, and provenance."""

from __future__ import annotations

import csv
import hashlib
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PAPER = ROOT / "paper_latex"
RESULTS = ROOT / "results"


GENERATED_RESULTS = (
    RESULTS / "tdsc_core_results.csv",
    RESULTS / "tdsc_coverage_results.csv",
    RESULTS / "tdsc_frontier_results.csv",
    RESULTS / "tdsc_frontier_admission.csv",
    RESULTS / "tdsc_frontier_paired_reward_deltas.csv",
    RESULTS / "tdsc_anchor_results.csv",
    RESULTS / "tdsc_anchor_paired_reward_deltas.csv",
)


MAIN_TEX = "usenix_sec2027.tex"


def manuscript_text() -> str:
    paths = [PAPER / MAIN_TEX, *sorted((PAPER / "sections").glob("*.tex"))]
    return "\n".join(path.read_text() for path in paths)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def test_every_generated_result_row_has_existing_source() -> None:
    for path in GENERATED_RESULTS:
        with path.open(newline="") as source:
            rows = list(csv.DictReader(source))
        assert rows, f"{path.name} is empty"
        provenance_columns = {
            column for column in rows[0] if column in {"source_file", "source_files"}
        }
        assert provenance_columns, f"{path.name} has no provenance column"
        for row in rows:
            references: list[str] = []
            for column in provenance_columns:
                references.extend(item.strip() for item in row[column].split(";"))
            assert references
            for reference in references:
                source_path = ROOT / reference
                assert source_path.is_file(), f"{path.name}: missing {reference}"


def test_all_generated_table_inputs_and_figures_exist() -> None:
    source = manuscript_text()
    generated_inputs = re.findall(r"\\input\{generated/([^}]+)\}", source)
    assert generated_inputs
    for name in generated_inputs:
        assert (PAPER / "generated" / f"{name}.tex").is_file()
    figures = re.findall(r"\\includegraphics(?:\[[^\]]+\])?\{([^}]+)\}", source)
    assert figures
    for name in figures:
        assert (PAPER / "figures" / name).is_file()


def test_usenix_abstract_is_plain_text_and_concise() -> None:
    source = (PAPER / MAIN_TEX).read_text()
    match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
        source,
        flags=re.DOTALL,
    )
    assert match is not None
    abstract = match.group(1)
    assert "$" not in abstract
    plain = re.sub(
        r"\\[A-Za-z]+(?:\[[^\]]*\])?\{([^{}]*)\}",
        r"\1",
        abstract,
    )
    plain = re.sub(r"\\[A-Za-z]+", " ", plain)
    words = re.findall(r"\b[\w-]+\b", plain)
    assert 100 <= len(words) <= 200


def test_usenix_submission_format_lock() -> None:
    source = (PAPER / MAIN_TEX).read_text()
    # USENIX requires two-column, 10pt on 12pt leading, 7in x 9in text block.
    # usenix.sty supplies the geometry; the class options supply the rest.
    assert r"\documentclass[letterpaper,twocolumn,10pt]{article}" in source
    assert r"\usepackage{usenix}" in source
    assert (PAPER / "usenix.sty").is_file()
    # No leftover IEEE/NDSS machinery.
    for leftover in (r"\IEEEpubid", r"\IEEEpeerreviewmaketitle", r"\appendices"):
        assert leftover not in source, leftover
    assert "NDSS" not in source
    # Anonymous submission: no author block content.
    assert re.search(r"\\author\{\s*\}", source) is not None
    # Mandatory Open Science appendix and recommended Ethics appendix.
    ethics = (PAPER / "sections" / "sec7_ethics_usenix.tex").read_text()
    assert r"\section*{Ethical Considerations}" in ethics
    assert r"\section*{Open Science}" in ethics
    assert r"\input{sections/sec7_ethics_usenix}" in source
    # Geometry must not be overridden by hand.
    for forbidden in (
        r"\setlength{\textheight}",
        r"\setlength{\textwidth}",
        r"\setlength{\columnsep}",
        r"\usepackage{geometry}",
    ):
        assert forbidden not in source, forbidden


def test_usenix_body_fits_thirteen_pages() -> None:
    """USENIX allows 13 pages of body text; appendices and refs are unlimited."""
    pdf = PAPER / "usenix_sec2027.pdf"
    if not pdf.is_file():
        return
    try:
        import fitz
    except ImportError:  # pragma: no cover - optional dependency
        return
    with fitz.open(pdf) as doc:
        pages = [
            page.number + 1
            for page in doc
            if page.search_for("Ethical Considerations")
        ]
        assert pages, "Ethical Considerations appendix not found in the PDF"
        assert pages[0] <= 14, (
            f"body runs past page 13 (appendix starts p{pages[0]})"
        )
        # The appendix starting on page 14 is only compliant when no body text
        # precedes it there: a conclusion spilling onto page 14 still makes the
        # body 14 pages long, which the page index alone does not catch.
        if pages[0] == 14:
            blocks = doc[13].get_text("blocks")
            assert blocks, "page 14 is empty"
            first = blocks[0][4].strip()
            assert first.startswith("Ethical Considerations"), (
                "body text spills onto page 14 before the appendix: "
                f"{first[:60]!r}"
            )


def test_core_table_does_not_mix_legacy_runtime_subsets() -> None:
    core = (PAPER / "generated" / "tdsc_core_results.tex").read_text()
    assert "Permanent backup shield" not in core
    assert "Official linear MPSC" not in core
    frontier = (PAPER / "generated" / "tdsc_frontier_results.tex").read_text()
    assert "Permanent shield" in frontier
    assert "Official MPSC" in frontier


def test_quadrotor_gate_uses_locked_two_sided_exact_pvalue() -> None:
    gate_path = (
        RESULTS / "safe_control_gym_quadrotor_reinforce_reward_poisoning_gate.csv"
    )
    with gate_path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    row = rows[0]
    poison_only = int(row["poison_only_failures"])
    clean_only = int(row["clean_only_failures"])
    assert (poison_only, clean_only) == (68, 0)
    expected = 2.0 * (0.5**68)
    assert math.isclose(float(row["paired_exact_pvalue"]), expected, rel_tol=1e-15)
    assert r"6.776\times10^{-21}" in manuscript_text()
    sweep_source = (
        ROOT / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep.py"
    ).read_text()
    assert 'alternative="two-sided"' in sweep_source


def test_negative_boundaries_and_scope_caveats_remain_visible() -> None:
    source = " ".join(manuscript_text().split())
    required_fragments = (
        "official Safe-Control-Gym PPO audit showed checkpoint-level redirection without stable physical failure",
        "improves no paired rollout over freeze",
        "sampled finite-horizon certificates, not continuous-state invariant-set proofs",
        "official linear model predictive safety certification (MPSC) mechanism all",
        "pre-clip saturation are reported separately",
        "baseline-handoff obligation",
        "summarize within-snapshot discordance",
        "Development grids selected target",
        "fixed target and bounded attacker without establishing joint gate optimality",
        "diagnostic rerun on the development realization",
        "Coordinatewise parameter clipping remains outside the exact support computation",
        "bound two hand-designed variants, not the channel",
        "The frozen envelope therefore did not separate attack from benign duration drift",
        "neither result establishes channel closure",
    )
    for fragment in required_fragments:
        assert fragment in source


def test_split_trust_and_reward_integrity_boundary_are_explicit() -> None:
    source = " ".join(manuscript_text().split())
    required_fragments = (
        "explicit split-trust precondition",
        "compromise of a reward-ingestion principal",
        "benchmark models the resulting interface without assuming a particular product",
        "Evaluated write boundary",
        "No origin/semantic check",
        "Trusted recomputation blocks every evaluated edit",
        "Authentication and trusted reward recomputation therefore provide upstream controls",
        "84 clean and 84 poisoned batches",
        "That producer remains within the trusted computing base",
        "limit claims about cross-architecture prevalence and deployment overhead",
        "only trusted recomputation closes the channel",
    )
    for fragment in required_fragments:
        assert fragment in source


def test_third_party_pairing_and_opportunity_claim_are_locked() -> None:
    case = (PAPER / "sections" / "sec6_third_party_case_study.tex").read_text()
    normalized_case = " ".join(case.split())
    assert r"3$^a$ & 0.241 & 0.242 & 0.747 & 0.228" in case
    assert "0.241 & 0.748" not in case
    assert "two of the three provenance-complete pairs" in case.lower()
    assert "none of 32 high-disagreement runs was positive" in normalized_case
    assert (
        "two historical reinforce rows lack an executable deduplication rule"
        in normalized_case.lower()
    )
    assert "corpus size, exact positive count" in normalized_case
    assert "post-bootstrap" in normalized_case
    for unsupported in (
        "receiver operating characteristic curve",
        "all 11 positive outcomes",
        "eleven of 18 low-band",
    ):
        assert unsupported not in normalized_case

    central = " ".join(
        path.read_text()
        for path in (
            PAPER / MAIN_TEX,
            PAPER / "sections" / "sec1_introduction.tex",
            PAPER / "sections" / "sec6_third_party_case_study.tex",
            PAPER / "sections" / "sec6_conclusion.tex",
        )
    )
    for obsolete in (
        "on all three seeds",
        "on 3/3 paired seeds",
        "attacker-observable rather than post-hoc",
        "leave-one-family-out accuracy",
    ):
        assert obsolete not in central


def test_carr_driver_patch_and_canonical_susceptibility_corpus() -> None:
    patch_path = (
        ROOT
        / "carr_victim_experiment"
        / "upstream"
        / "carr_reward_poisoning.patch"
    )
    patch = patch_path.read_text()
    for fragment in (
        "diff --git a/model_simulator.py b/model_simulator.py",
        "diff --git a/rl_simulator.py b/rl_simulator.py",
        "diff --git a/run_carr_victim.py b/run_carr_victim.py",
        "if step == self.shield_switch_episode",
        "self.shield_on = False",
        "def set_poison",
    ):
        assert fragment in patch, fragment

    ignore_rules = (ROOT / ".gitignore").read_text().splitlines()
    assert "*.py" not in {line.strip() for line in ignore_rules}

    carr_dir = ROOT / "carr_victim_experiment"
    sys.path.insert(0, str(carr_dir))
    try:
        from analyze_fullphase import BASE, seed_row
        from susceptibility_corpus import susceptibility_2x2

        cells = susceptibility_2x2(BASE, seed_row)
    finally:
        sys.path.pop(0)
    assert cells == {
        "lo_pos": 12,
        "lo_neg": 8,
        "hi_pos": 0,
        "hi_neg": 33,
        "n": 53,
    }

    for name in ("analyze_fullphase.py", "analyze_sac_v112.py", "analyze_sac_v113.py"):
        source = (carr_dir / name).read_text()
        assert "canonical_2x2" in source, name


def test_carr_run_configuration_and_marker_corpora_are_distinct() -> None:
    with (
        ROOT / "carr_victim_experiment" / "results" / "two_sided_accounting.csv"
    ).open(newline="") as source:
        configurations = [
            row for row in csv.DictReader(source) if row["shape"] == "contrast"
        ]
    assert len(configurations) == 54
    exploratory = [
        row
        for row in configurations
        if row["method"] == "REINFORCE"
        and row["scope"] == "full"
        and row["run_index"] in {"1", "2"}
    ]
    assert len(exploratory) == 4
    assert {float(row["delta"]) for row in exploratory} == {
        0.28300000000000003,
        0.28500000000000003,
        0.007000000000000006,
        0.271,
    }

    with (
        ROOT / "carr_victim_experiment" / "results" / "disagreement_marker.csv"
    ).open(newline="") as source:
        marker = list(csv.DictReader(source))
    assert len(marker) == 58
    assert sum(row["positive"] == "True" for row in marker) == 15
    assert sum(row["positive"] == "False" for row in marker) == 43
    assert sum(row["band"] == "high" for row in marker) == 32
    assert not any(
        row["band"] == "high" and row["positive"] == "True" for row in marker
    )

    appendix = " ".join(
        (PAPER / "sections" / "appendix_thirdparty.tex").read_text().split()
    )
    assert "executable marker audit emits 58 configuration rows" in appendix
    assert "raw totals are not treated as the marker's analysis denominator" in appendix
    assert "plots the same corpus" not in appendix


def test_hero_table_and_evaluation_spine_are_locked() -> None:
    source = (PAPER / "sections" / "sec4_evaluation.tex").read_text()
    hero = source.index(r"\subsection{Prospective Contract-Separation Audit}")
    geometry = source.index(
        r"\subsection{Reward-Influence Geometry and Optimizer Boundary}"
    )
    cross_system = source.index(r"\subsection{Cross-System Reward-Record Poisoning}")
    assert hero < geometry < cross_system

    required_rows = (
        "V5 clean cohort (480 pairs; 20 training runs)",
        "Clean permanent raw release & 10/480",
        "Clean resident predictive authority & 0/480 & 11 switches",
        "V4 fixed-attack confirmation (120 pairs; 5 runs)",
        "Clean permanent raw release & 2/120",
        "Poisoned permanent raw release & 27/120",
        "Poisoned resident predictive authority & 0/120 & 27 switches",
        "Independent audit (71 accepted states, poisoned snapshots)",
        "One-step resident kernel & 14/71 & 79 int.; 41 empty",
        "Resident predictive authority & 0/71 & 19 switches",
    )
    for row in required_rows:
        assert row in source


def test_clean_resident_arm_and_carr_corpora_are_reported() -> None:
    """The V4 harness check and the Carr corpus boundaries must stay visible."""
    source = " ".join(manuscript_text().split())
    for fragment in (
        "Clean resident predictive authority & 0/120 & 2 switches",
        "Twelve comparisons met the positive rule, 20 had a rate difference",
        "54-comparison obstacle-only configuration table",
        "those configurations reuse run indices",
        "one of eleven same-version clean replicate pairs crosses",
    ):
        assert fragment in source, fragment

    rollouts = RESULTS / "cartpole_v4_clean_resident_arm_rollouts.csv"
    assert rollouts.is_file(), rollouts
    with rollouts.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 120
    violations = [r for r in rows if int(r["physical_first_violation_step"]) >= 0]
    switches = [r for r in rows if int(r["forward_switch_step"]) >= 0]
    assert not violations, "clean resident arm must remain violation-free"
    assert len(switches) == 2, len(switches)
    for row in switches:
        lead = int(row["paired_clean_release_violation_step"]) - int(
            row["forward_switch_step"]
        )
        assert lead == 4, lead


def test_v5_clean_cohort_rate_and_replication_are_locked() -> None:
    summary_path = RESULTS / "cartpole_v5_clean_cohort_summary.csv"
    rollouts_path = RESULTS / "cartpole_v5_clean_cohort_rollouts.csv"
    with summary_path.open(newline="") as source:
        summary = list(csv.DictReader(source))
    with rollouts_path.open(newline="") as source:
        rollouts = list(csv.DictReader(source))

    assert len(summary) == 20
    assert [int(row["learner_seed"]) for row in summary] == list(range(2300, 2320))
    assert sum(int(row["states_accepted"]) for row in summary) == 480
    assert sum(int(row["raw_release_violations"]) for row in summary) == 10
    assert sum(int(row["resident_violations"]) for row in summary) == 0
    assert sum(int(row["resident_switches"]) for row in summary) == 11
    assert sum(int(row["raw_release_violations"]) > 0 for row in summary) == 5
    assert len(rollouts) == 960

    source = " ".join(manuscript_text().split())
    for fragment in (
        "20 independently trained controllers",
        "10/480",
        "0/480",
        "5/20",
        "[11.2\\%,46.9\\%]",
        "two-sided exact paired $p=0.00195$",
        "answer different conditional questions and are not pooled",
    ):
        assert fragment in source, fragment


def test_v6_duration_and_handoff_boundary_are_locked() -> None:
    summary_path = RESULTS / "cartpole_v6_duration_summary.csv"
    rollouts_path = RESULTS / "cartpole_v6_duration_rollouts.csv"
    with summary_path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    with rollouts_path.open(newline="") as source:
        rollouts = list(csv.DictReader(source))
    assert len(rows) == 45

    expected = {
        (12, "clean"): (120, 4, 0, 0, 0),
        (12, "constrained"): (120, 17, 0, 0, 0),
        (12, "unconstrained"): (119, 36, 0, 56, 56),
        (24, "clean"): (120, 6, 0, 0, 1),
        (24, "constrained"): (120, 15, 0, 0, 0),
        (24, "unconstrained"): (120, 16, 0, 89, 96),
        (48, "clean"): (120, 9, 0, 0, 6),
        (48, "constrained"): (116, 46, 34, 0, 2),
        (48, "unconstrained"): (117, 54, 38, 144, 160),
    }
    for key, target in expected.items():
        duration, condition = key
        cell = [
            row
            for row in rows
            if int(row["duration"]) == duration and row["condition"] == condition
        ]
        observed = (
            sum(int(row["states_accepted"]) for row in cell),
            sum(int(row["raw_release_violations"]) for row in cell),
            sum(int(row["resident_violations"]) for row in cell),
            sum(int(row["known_sign_batches_flagged"]) for row in cell),
            sum(int(row["scalar_envelope_batches_flagged"]) for row in cell),
        )
        assert observed == target, (key, observed)

    constrained = [
        row
        for row in rollouts
        if row["duration"] == "48"
        and row["condition"] == "constrained"
        and row["mechanism"] == "resident_predictive_authority"
        and row["physical_first_violation_step"]
    ]
    assert len(constrained) == 34
    assert all(row["forward_switch_step"] for row in constrained)
    post_switch = [
        int(row["physical_first_violation_step"]) - int(row["forward_switch_step"])
        for row in constrained
    ]
    assert statistics.median(post_switch) == 1
    assert max(post_switch) == 2

    accepted = [
        row
        for row in rollouts
        if row["duration"] == "48"
        and row["condition"] == "constrained"
        and row["snapshot_initially_accepted"] == "True"
    ]
    paired: dict[tuple[str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in accepted:
        key = (row["learner_seed"], row["evaluation_seed"], row["selected_index"])
        paired[key][row["mechanism"]] = row
    assert len(paired) == 116
    contingency = Counter(
        (
            bool(pair["raw_release"]["physical_first_violation_step"]),
            bool(pair["resident_predictive_authority"]["physical_first_violation_step"]),
        )
        for pair in paired.values()
    )
    assert contingency == {
        (True, True): 27,
        (True, False): 19,
        (False, True): 7,
        (False, False): 63,
    }
    resident_seeds = Counter(
        row["learner_seed"]
        for row in accepted
        if row["mechanism"] == "resident_predictive_authority"
        and row["physical_first_violation_step"]
    )
    assert resident_seeds == {"2400": 17, "2403": 17}
    both_failure_leads = [
        int(pair["raw_release"]["physical_first_violation_step"])
        - int(pair["resident_predictive_authority"]["forward_switch_step"])
        for pair in paired.values()
        if pair["raw_release"]["physical_first_violation_step"]
        and pair["resident_predictive_authority"]["physical_first_violation_step"]
    ]
    assert len(both_failure_leads) == 27
    assert (min(both_failure_leads), statistics.median(both_failure_leads), max(both_failure_leads)) == (4, 4, 5)

    source = " ".join(manuscript_text().split())
    for fragment in (
        "46/116 failures under raw release and 34/116 under resident authority",
        "no known-sign flags at any duration",
        "fewer than the 6/240 flags from clean training",
        "All 34 resident failures occurred after",
        "median of one step and at most two",
        "27 pairs failed under both contracts",
        "19 failed only under raw release",
        "seven failed only under resident authority",
        "63 failed under neither",
        "two of the five independently trained controllers with 17 failures each",
        "baseline-handoff obligation",
    ):
        assert fragment in source, fragment


def test_release_contract_terminology_and_cohort_scope_are_normalized() -> None:
    source = " ".join(manuscript_text().split())
    assert "Before the sequential V3 audit, we fixed the target" in source
    assert "evaluated once on five new learner/evaluation pairs" in source
    assert "Permanent raw release" in source
    assert "Resident predictive authority" in source
    assert "One-step resident kernel" in source
    assert "Commit admission" in source

    legacy_aliases = (
        "Predictive resident Simplex",
        "predictive resident mechanism",
        "resident predictive and MPSC",
        "permanent predictive authority",
        "repeated predictive authority",
        "detector therefore fired on time",
        "trusted baseline could no longer recover",
        "exhaust a trusted baseline's recovery",
    )
    for alias in legacy_aliases:
        assert alias not in source


def test_release_contract_hard_gate_and_claim_lock() -> None:
    decision_path = RESULTS / "cartpole_multiseed_release_contract_decision.csv"
    with decision_path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    row = rows[0]
    assert int(row["learner_seeds"]) == 3
    assert int(row["initially_accepted_states"]) == 71
    assert int(row["permanent_release_violations"]) == 19
    assert int(row["permanent_release_seeds_with_violation"]) == 3
    assert int(row["predictive_resident_violations"]) == 0
    assert int(row["paired_release_failures_with_timely_switch"]) == 19
    assert row["pair_keys_valid"] == "True"
    assert int(row["untouched_release_violations"]) == 13
    assert int(row["untouched_predictive_violations"]) == 0
    assert row["hard_gate_pass"] == "True"

    source = manuscript_text()
    for claim in ("19/71", "14/71", "0/71", "reached an empty kernel 41 times"):
        assert claim in source


def test_reward_geometry_and_clipped_extension_claim_lock() -> None:
    decision_path = RESULTS / "cartpole_reward_geometry_smoke_decision.csv"
    with decision_path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    row = rows[0]
    assert row["clean_gradient_clipped"] == "False"
    assert row["clean_parameter_clipped"] == "False"
    assert int(row["constraints_not_robust"]) == 0
    assert float(row["gradient_reconstruction_error"]) < 1e-12
    assert float(row["maximum_witness_support_error"]) < 1e-7
    assert row["geometry_smoke_pass"] == "True"

    source = " ".join(manuscript_text().split())
    assert "neither gradient nor parameter clipping is active" in source
    assert "under global Euclidean gradient-norm clipping" in source
    assert "Coordinatewise parameter clipping remains outside" in source
    assert "The exact-support result therefore serves as a batch audit" in source

    with (
        RESULTS / "cartpole_v3_clipped_influence_decision.csv"
    ).open(newline="") as clipped_source:
        clipped_rows = list(csv.DictReader(clipped_source))
    assert len(clipped_rows) == 1
    clipped = clipped_rows[0]
    assert int(clipped["old_exact_support_eligible_batches"]) == 0
    assert int(clipped["exact_clipped_support_eligible_batches"]) == 22
    assert int(clipped["newly_covered_normalization_singular_batches"]) == 18
    assert int(clipped["newly_covered_possible_gradient_clip_batches"]) == 20
    assert float(clipped["maximum_witness_support_error"]) < 5e-5
    assert clipped["all_witness_budgets_valid"] == "True"
    assert clipped["all_actual_updates_bounded_by_support"] == "True"
    assert clipped["clipped_theory_audit_pass"] == "True"


def test_failed_prospective_attack_boundary_is_locked() -> None:
    with (
        RESULTS / "cartpole_prospective_gate_aware_decision.csv"
    ).open(newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    row = rows[0]
    assert int(row["learner_seed"]) == 2060
    assert int(row["poison_initially_accepted"]) == 24
    assert int(row["nonzero_support_batches"]) == 0
    assert int(row["solver_failure_batches"]) == 12
    assert float(row["max_reward_poison"]) == 0.0
    assert int(row["poisoned_release_violations"]) == 0
    assert row["development_smoke_pass"] == "False"

    with (
        RESULTS / "cartpole_gate_aware_v2_exploratory_decision.csv"
    ).open(newline="") as source:
        v2_rows = list(csv.DictReader(source))
    assert len(v2_rows) == 1
    v2 = v2_rows[0]
    assert int(v2["learner_seed"]) == 2060
    assert int(v2["nonzero_support_batches"]) == 1
    assert int(v2["solver_failure_batches"]) == 11
    assert int(v2["poisoned_release_violations"]) == 0
    assert v2["development_smoke_pass"] == "False"

    with (
        RESULTS / "cartpole_homogenized_gate_aware_2060_decision.csv"
    ).open(newline="") as source:
        homogenized_rows = list(csv.DictReader(source))
    assert len(homogenized_rows) == 1
    homogenized = homogenized_rows[0]
    assert int(homogenized["learner_seed"]) == 2060
    assert int(homogenized["nonzero_support_batches"]) == 9
    assert int(homogenized["poison_initially_accepted"]) == 24
    assert int(homogenized["poisoned_release_violations"]) == 0
    assert homogenized["budget_integrity"] == "True"
    assert homogenized["development_smoke_pass"] == "False"

    source = (
        ROOT / "safe_control_gym_cartpole_prospective_gate_aware_attack.py"
    ).read_text()
    assert 'set(args.learner_seeds) - {2060}' in source
    assert "untouched seeds require --confirmatory" in source


def test_v3_prospective_fixed_target_hard_gate() -> None:
    with (
        RESULTS / "cartpole_v3_fixed_target_multiseed_aggregate.csv"
    ).open(newline="") as source:
        aggregate_rows = list(csv.DictReader(source))
    assert len(aggregate_rows) == 1
    aggregate = aggregate_rows[0]
    assert int(aggregate["learner_seeds"]) == 3
    assert int(aggregate["poison_initially_accepted"]) == 72
    assert int(aggregate["seeds_with_poisoned_release_failure"]) == 3
    assert int(aggregate["clean_release_violations"]) == 2
    assert int(aggregate["poisoned_release_violations"]) == 23
    assert int(aggregate["resident_predictive_violations"]) == 0
    assert int(aggregate["paired_release_failures"]) == 23
    assert int(aggregate["paired_release_failures_with_timely_switch"]) == 23
    assert int(aggregate["poison_only_discordant"]) == 21
    assert int(aggregate["clean_only_discordant"]) == 0
    assert math.isclose(
        float(aggregate["paired_exact_pvalue"]),
        2.0 * (0.5**21),
        rel_tol=1e-15,
    )
    assert aggregate["all_budget_integrity"] == "True"
    assert aggregate["all_pair_keys_valid"] == "True"
    assert aggregate["three_seed_hard_gate_pass"] == "True"

    with (
        RESULTS / "cartpole_v3_fixed_target_multiseed_decision.csv"
    ).open(newline="") as source:
        seed_rows = list(csv.DictReader(source))
    assert [int(row["learner_seed"]) for row in seed_rows] == [2070, 2071, 2072]
    assert [int(row["poisoned_release_violations"]) for row in seed_rows] == [
        11,
        5,
        7,
    ]
    assert all(row["development_smoke_pass"] == "True" for row in seed_rows)

    source = (
        ROOT / "safe_control_gym_cartpole_v3_fixed_target_tanh.py"
    ).read_text()
    assert "development smoke did not authorize confirmation" in source
    assert "confirmatory mode requires the locked three seed pairs" in source
    manuscript = manuscript_text()
    for claim in ("23/72", "2/72", "0/72", r"9.537\times10^{-7}"):
        assert claim in manuscript


def test_no_locked_forbidden_positive_phrasing() -> None:
    source = manuscript_text().lower()
    forbidden_patterns = (
        r"lifecyclegate (?:proves|demonstrates|establishes) "
        r"(?:benign|positive|useful) adaptation utility",
        r"official ppo (?:consistently|stably) (?:fails|violates)",
        r"sampled (?:casadi )?certificate (?:proves|guarantees) "
        r"continuous-state invariance",
        r"official mpsc is ineffective",
        r"accepted update fraction (?:proves|establishes) learning utility",
        r"universal safety--security--learning impossibility theorem",
    )
    for pattern in forbidden_patterns:
        assert re.search(pattern, source) is None, pattern
    assert "pre-registered" not in source.lower()


def test_checksum_inventory_matches_locked_files() -> None:
    path = RESULTS / "tdsc_artifact_checksums.csv"
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) >= 100
    for row in rows:
        artifact = ROOT / row["path"]
        assert artifact.is_file(), row["path"]
        assert artifact.stat().st_size == int(row["bytes"]), row["path"]
        assert digest(artifact) == row["sha256"], row["path"]


def test_uplift_experiment_numbers_locked() -> None:
    import collections

    def one(name: str) -> dict:
        with (RESULTS / name).open(newline="") as source:
            return list(csv.DictReader(source))[0]

    # U1 learned-baseline advantage variant
    a2c = one("cartpole_a2c_reward_poisoning_multiseed_decision.csv")
    assert int(a2c["pooled_poison_violations"]) == 40
    assert int(a2c["pooled_clean_violations"]) == 2
    assert int(a2c["pooled_freeze_violations"]) == 0
    assert int(a2c["pooled_commit_violations"]) == 0
    assert a2c["canary_pass"] == "True"

    # U2 non-singleton adaptation set (pooled by rho)
    with (RESULTS / "cartpole_joint_channel_poisoning_multiseed_frontier.csv").open(
        newline=""
    ) as source:
        front = list(csv.DictReader(source))
    agg: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"clean": 0, "poison": 0, "freeze": 0, "commit": 0}
    )
    for row in front:
        cell = agg[row["rho"]]
        for key in ("clean", "poison", "freeze", "commit"):
            cell[key] += int(row[key])
    assert (agg["0.005"]["poison"], agg["0.005"]["clean"]) == (41, 5)
    assert (agg["0.02"]["poison"], agg["0.02"]["clean"]) == (44, 4)
    assert (agg["0.04"]["poison"], agg["0.04"]["clean"]) == (61, 3)
    for rho in ("0.005", "0.02", "0.04"):
        assert agg[rho]["freeze"] == 0 and agg[rho]["commit"] == 0

    # U3 in-loop known-sign gate
    defense = one("cartpole_inloop_defense_multiseed_decision.csv")
    assert int(defense["pooled_poison_undefended_violations"]) == 39
    assert int(defense["pooled_poison_defended_violations"]) == 0
    assert int(defense["pooled_clean_defended_batches_frozen"]) == 0
    assert defense["canary_pass"] == "True"

    # Paper text must state the corrected uplift numbers with honest scoping.
    source = " ".join(manuscript_text().split())
    for fragment in (
        "40/126",
        "44/126 and 61/126",
        "39/126 raw-release failures to 0/126",
        "robustness check within the Monte Carlo policy-gradient family",
        "a pole-angle bias of radius",
        "neither result establishes channel closure",
    ):
        assert fragment in source, fragment
