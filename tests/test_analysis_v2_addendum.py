"""Regression guards for the two defects the addendum documents.

1. No post-decision feature may re-enter the pre-decision vector.
2. The rows the paper's claim rests on must not contain a format-compliance
   term, so they stay invariant to the declared MATH bug fix.
3. The v1 and v2 format-compliance definitions may differ for `math` only.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import analysis as av1  # noqa: E402
import analysis_v2 as v2  # noqa: E402

# Anything only knowable after the full fine-tune has already run.
POST_DECISION_TOKENS = ("gen_len.full", "gen_len.pilot.full", "full_n", "delta_full", "full_pass1")


def test_pre_decision_vector_has_no_post_decision_feature() -> None:
    for name in v2.PRE_DECISION:
        for bad in POST_DECISION_TOKENS:
            assert bad not in name, f"{name} leaks post-decision information into the gate"


def test_no_pass8_variant_is_also_pre_decision() -> None:
    for name in v2.NO_PASS8:
        assert name in v2.PRE_DECISION


def test_registered_vector_is_the_one_that_leaks() -> None:
    # The registered row is kept precisely because it is the honesty-clause row;
    # this test documents that it does contain the oracle feature.
    assert "gen_len.full.median" in v2.LEAKED_12


def test_trio_is_invariant_to_the_format_compliance_fix() -> None:
    # The paper's pre-decision claim rests on TRIO; it must carry no compliance
    # term, otherwise the declared MATH fix would move it.
    assert not any("format_compliance" in n for n in v2.TRIO)


def _block(**scalars: float) -> dict[str, dict[str, float]]:
    return {"base": {"n": 200, **scalars}}


def test_fc_definitions_agree_except_for_math() -> None:
    gsm = _block(hash=58, last_only=142, none=0)
    assert av1.format_compliance_scalar("gsm8k", gsm) == v2.format_compliance_base("gsm8k", gsm)

    other = _block(unparseable=10)
    assert av1.format_compliance_scalar("task010", other) == v2.format_compliance_base("task010", other)

    math = _block(boxed=110, last_only=90, none=0)
    # v1 has no `unparseable` key to read, so it silently reports full compliance.
    assert av1.format_compliance_scalar("math", math) == 1.0
    assert v2.format_compliance_base("math", math) == 110 / 200


def test_fc_v1_is_blind_whenever_unparseable_is_absent() -> None:
    # The shape of the v1 defect: any block without `unparseable` reads as 1.0.
    assert av1.format_compliance_scalar("anything", _block(boxed=0)) == 1.0
