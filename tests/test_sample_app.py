"""Baseline tests for the sample app. Deliberately thin: task T1 asks the assistant to extend them."""
from datetime import date

import pytest

from sample_app.claims_processing import Claim, ClaimStatus, settlement_amount, triage
from sample_app.policy_validation import Policy, PolicyValidationError, validate_policy

TODAY = date(2026, 11, 18)


def make_policy(**overrides):
    fields = dict(
        policy_number="POL-00000001",
        product="AUTO",
        holder_birth_date=date(1990, 5, 1),
        start_date=date(2026, 12, 1),
        end_date=date(2027, 12, 1),
        sum_insured=50_000,
        state="TX",
    )
    fields.update(overrides)
    return Policy(**fields)


def test_valid_policy_passes():
    validate_policy(make_policy(), today=TODAY)


def test_bad_policy_number_rejected():
    with pytest.raises(PolicyValidationError):
        validate_policy(make_policy(policy_number="12345"), today=TODAY)


def test_small_claim_auto_approved():
    claim = Claim("CLM-00000001", "POL-00000001", amount=800, deductible=250, coverage_limit=10_000)
    assert triage(claim) is ClaimStatus.AUTO_APPROVED


# ---------------------------------------------------------------------------
# Regression tests for INS-142: deductible must be applied to the raw loss
# *before* the coverage limit, not after.
# ---------------------------------------------------------------------------

def make_claim(**overrides) -> Claim:
    """Return a minimal Claim with sensible defaults for settlement tests."""
    fields = dict(
        claim_number="CLM-00000002",
        policy_number="POL-00000001",
        amount=10_000.0,
        deductible=1_000.0,
        coverage_limit=20_000.0,
    )
    fields.update(overrides)
    return Claim(**fields)


def test_settlement_uncapped_subtracts_deductible_from_raw_loss():
    """When amount < coverage_limit, payout = amount − deductible."""
    claim = make_claim(amount=10_000, deductible=1_000, coverage_limit=20_000)
    # Correct:  10,000 − 1,000 = 9,000  (not capped)
    # Buggy:    min(10,000, 20,000) − 1,000 = 9,000  (same here — no difference)
    assert settlement_amount(claim) == 9_000.00


def test_settlement_capped_claim_ins142_regression():
    """INS-142 regression: when amount == coverage_limit the full cap is paid
    out minus the deductible, not the cap minus the deductible applied twice.

    Old (buggy) order:
        capped  = min(60,000, 50,000) = 50,000
        payable = 50,000 − 2,000     = 48,000   ← underpaid by $2,000

    Correct order:
        payable = 60,000 − 2,000     = 58,000
        capped  = min(58,000, 50,000) = 50,000   ← full policy limit paid
    """
    claim = make_claim(amount=60_000, deductible=2_000, coverage_limit=50_000)
    assert settlement_amount(claim) == 50_000.00


def test_settlement_deductible_exceeds_amount_returns_zero():
    """When the loss is smaller than the deductible, nothing is payable."""
    claim = make_claim(amount=500, deductible=1_000, coverage_limit=20_000)
    assert settlement_amount(claim) == 0.00


def test_settlement_exact_deductible_equals_amount_returns_zero():
    """Edge case: loss exactly equals the deductible → $0 payable."""
    claim = make_claim(amount=1_000, deductible=1_000, coverage_limit=20_000)
    assert settlement_amount(claim) == 0.00


def test_settlement_result_rounded_to_two_decimal_places():
    """Payout is always rounded to two decimal places."""
    claim = make_claim(amount=1_000.005, deductible=0.0, coverage_limit=20_000)
    assert settlement_amount(claim) == round(1_000.005, 2)
