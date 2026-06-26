"""Tests for the cohort builder."""
from __future__ import annotations

from medigraph.services import get_engine
from medigraph.services.cohort import CohortCriteria, build_cohort, preset_registries


def test_preset_registries_run():
    eng = get_engine()
    for name, crit in preset_registries().items():
        res = eng.build_cohort(crit)
        assert res.size >= 0
        assert res.label == crit.label


def test_condition_inclusion_and_med_exclusion():
    recs = get_engine().all_records()
    crit = CohortCriteria(any_conditions=["afib"], without_medications=["warfarin", "apixaban"])
    res = build_cohort(recs, crit)
    for r in res.records:
        assert "afib" in r.condition_keys
        assert not ({"warfarin", "apixaban"} & set(r.medication_keys))


def test_lab_filter():
    recs = get_engine().all_records()
    crit = CohortCriteria(any_conditions=["t2dm"], lab_filters=[("hba1c", ">=", 9.0)])
    res = build_cohort(recs, crit)
    for r in res.records:
        obs = r.latest_observation("hba1c")
        assert obs is not None and obs.value >= 9.0


def test_summary_fields():
    recs = get_engine().all_records()
    res = build_cohort(recs, CohortCriteria(any_conditions=["htn"]))
    summary = res.summary()
    assert "size" in summary and "female_pct" in summary
