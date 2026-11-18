"""Policy validation rules for new and renewed policies (task T1: generate unit tests)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

POLICY_NUMBER_RE = re.compile(r"^POL-\d{8}$")
SUPPORTED_PRODUCTS = {"AUTO", "HOME", "LIFE"}
MIN_AGE = {"AUTO": 18, "HOME": 18, "LIFE": 18}
MAX_AGE = {"AUTO": 85, "HOME": 120, "LIFE": 70}
MAX_SUM_INSURED = {"AUTO": 250_000, "HOME": 2_000_000, "LIFE": 5_000_000}


@dataclass(frozen=True)
class Policy:
    policy_number: str
    product: str
    holder_birth_date: date
    start_date: date
    end_date: date
    sum_insured: int
    state: str


class PolicyValidationError(ValueError):
    """Raised with every failed rule, so callers can show all problems at once."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def age_on(birth: date, on: date) -> int:
    """Whole years between birth and the given date."""
    years = on.year - birth.year
    if (on.month, on.day) < (birth.month, birth.day):
        years -= 1
    return years


def validate_policy(policy: Policy, today: date | None = None) -> None:
    """Validate a policy. Raises PolicyValidationError listing every broken rule."""
    today = today or date.today()
    errors: list[str] = []
    if not POLICY_NUMBER_RE.match(policy.policy_number):
        errors.append("policy_number must look like POL-########")
    if policy.product not in SUPPORTED_PRODUCTS:
        errors.append(f"unsupported product {policy.product!r}")
    else:
        age = age_on(policy.holder_birth_date, policy.start_date)
        if not MIN_AGE[policy.product] <= age <= MAX_AGE[policy.product]:
            errors.append(f"holder age {age} outside {MIN_AGE[policy.product]}-{MAX_AGE[policy.product]}")
        if policy.sum_insured > MAX_SUM_INSURED[policy.product]:
            errors.append("sum_insured above product maximum")
    if policy.sum_insured <= 0:
        errors.append("sum_insured must be positive")
    if policy.end_date <= policy.start_date:
        errors.append("end_date must be after start_date")
    if (policy.end_date - policy.start_date).days > 366:
        errors.append("policy term cannot exceed one year")
    if policy.start_date < today:
        errors.append("start_date cannot be in the past")
    if len(policy.state) != 2 or not policy.state.isalpha() or not policy.state.isupper():
        errors.append("state must be a two-letter code")
    if errors:
        raise PolicyValidationError(errors)
