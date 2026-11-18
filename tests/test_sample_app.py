"""Baseline tests for the sample app. Deliberately thin: task T1 asks the assistant to extend them."""
from datetime import date

import pytest

from sample_app.claims_processing import Claim, ClaimStatus, triage
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
