"""Claims intake and settlement (task T2: document; task T4: fix the flagged bug)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

AUTO_APPROVE_LIMIT = 5_000
FRAUD_REVIEW_THRESHOLD = 50_000


class ClaimStatus(StrEnum):
    RECEIVED = "RECEIVED"
    AUTO_APPROVED = "AUTO_APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FRAUD_REVIEW = "FRAUD_REVIEW"
    REJECTED = "REJECTED"


@dataclass
class Claim:
    claim_number: str
    policy_number: str
    amount: float
    deductible: float
    coverage_limit: float
    prior_claims_12m: int = 0
    status: ClaimStatus = ClaimStatus.RECEIVED
    notes: list[str] = field(default_factory=list)


def triage(claim: Claim) -> ClaimStatus:
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
    # BUG (flagged by QA, ticket INS-142): the coverage limit is applied before the
    # deductible, so large claims are underpaid by the deductible amount.
    capped = min(claim.amount, claim.coverage_limit)
    payable = capped - claim.deductible
    return round(max(payable, 0.0), 2)
