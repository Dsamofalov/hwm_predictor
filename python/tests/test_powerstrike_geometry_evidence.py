from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.powerstrike_geometry_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_powerstrike_geometry_anomalies_are_auditable():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["analysis_errors"] == []
    assert report["proc_rows"] > 0
    assert len(report["same_coordinate"]) > 0
    assert len(report["non_unit_distance"]) > 0

    warnings.warn(
        "POWERSTRIKE_GEOMETRY "
        + json.dumps(
            {
                "proc_rows": report["proc_rows"],
                "anomaly_rows": report["anomaly_rows"],
                "same_coordinate": report["same_coordinate"],
                "non_unit_distance": report["non_unit_distance"],
                "preoccupied_destination": report["preoccupied_destination"],
                "killed_by_primary_anomalies": report["killed_by_primary_anomalies"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
