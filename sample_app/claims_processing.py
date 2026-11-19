"""Claims intake and settlement (task T2: document; task T4: fix the flagged bug)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

AUTO_APPROVE_LIMIT = 5_000
FRAUD_REVIEW_THRESHOLD = 50_000


class ClaimStatus(StrEnum):
    """Lifecycle states a claim moves through during processing."""

    RECEIVED = "RECEIVED"
    AUTO_APPROVED = "AUTO_APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FRAUD_REVIEW = "FRAUD_REVIEW"
    REJECTED = "REJECTED"


@dataclass
class Claim:
    """A single insurance claim submitted for processing.

    Attributes:
        claim_number: Unique identifier for the claim.
        policy_number: Identifier of the associated insurance policy.
        amount: Gross loss amount reported by the claimant.
        deductible: Policy deductible that reduces the payable amount.
        coverage_limit: Maximum amount the policy will pay for a single claim.
        prior_claims_12m: Number of claims filed by the policyholder in the
            preceding 12 months; used for fraud-risk scoring.
        status: Current lifecycle status of the claim.
        notes: Audit trail of processing notes appended during triage and
            settlement.
    """

    claim_number: str
    policy_number: str
    amount: float
    deductible: float
    coverage_limit: float
    prior_claims_12m: int = 0
    status: ClaimStatus = ClaimStatus.RECEIVED
    notes: list[str] = field(default_factory=list)


def triage(claim: Claim) -> ClaimStatus:
    """Assign an initial status to a claim based on amount and claim history.

    Rules applied in priority order:

    1. **Rejected** – amount is zero or negative.
    2. **Fraud review** – amount meets or exceeds ``FRAUD_REVIEW_THRESHOLD``
       (``$50,000``), *or* the policyholder has three or more prior claims in
       the last 12 months.
    3. **Auto-approved** – amount is strictly below ``AUTO_APPROVE_LIMIT``
       (``$5,000``).
    4. **Manual review** – all other cases.

    The claim's ``status`` and ``notes`` fields are updated in-place.

    Args:
        claim: The claim to evaluate.

    Returns:
        The ``ClaimStatus`` assigned to the claim.
    """
    if claim.amount <= 0:
        claim.status = ClaimStatus.REJECTED
        claim.notes.append("non-positive amount")
    elif claim.amount >= FRAUD_REVIEW_THRESHOLD or claim.prior_claims_12m >= 3:
        claim.status = ClaimStatus.FRAUD_REVIEW
    elif claim.amount < AUTO_APPROVE_LIMIT:
        claim.status = ClaimStatus.AUTO_APPROVED
    else:
        claim.status = ClaimStatus.MANUAL_REVIEW
    return claim.status


def settlement_amount(claim: Claim) -> float:
    """Calculate the net payable amount for an approved claim.

    Subtracts the deductible from the gross loss first, then applies the
    coverage limit.  The result is clamped to zero so the insurer never owes
    a negative amount.

    Correct order of operations:

    1. ``payable = amount − deductible``  (claimant bears the deductible)
    2. ``payable = min(payable, coverage_limit)``  (policy cap)
    3. ``payable = max(payable, 0)``  (never negative)

    Args:
        claim: The claim whose settlement amount is to be calculated.

    Returns:
        The net payable amount, rounded to two decimal places.
    """
    # Fix for INS-142: subtract the deductible from the raw loss *before*
    # applying the coverage limit, so the cap is not artificially reduced.
    payable = claim.amount - claim.deductible
    payable = min(payable, claim.coverage_limit)
    return round(max(payable, 0.0), 2)
