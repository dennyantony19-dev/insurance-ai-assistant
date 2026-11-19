"""Unit tests for sample_app/policy_validation.py::validate_policy."""
from __future__ import annotations

from datetime import date

import pytest

from sample_app.policy_validation import (
    Policy,
    PolicyValidationError,
    age_on,
    validate_policy,
)

# ---------------------------------------------------------------------------
# Fixed reference date used throughout so tests are deterministic.
# ---------------------------------------------------------------------------
TODAY = date(2026, 11, 19)


# ---------------------------------------------------------------------------
# Helper: build a fully-valid policy and optionally override specific fields.
# ---------------------------------------------------------------------------
def make_policy(**overrides) -> Policy:
    """Return a valid Policy, with any fields replaced by *overrides*."""
    fields = dict(
        policy_number="POL-00000001",
        product="AUTO",
        holder_birth_date=date(1988, 6, 15),
        start_date=date(2026, 12, 1),
        end_date=date(2027, 12, 1),
        sum_insured=100_000,
        state="CA",
    )
    fields.update(overrides)
    return Policy(**fields)


# ===========================================================================
# age_on helper
# ===========================================================================
class TestAgeOn:
    def test_exact_birthday(self):
        assert age_on(date(1990, 3, 10), date(2026, 3, 10)) == 36

    def test_day_before_birthday(self):
        """The birthday has not yet occurred this year."""
        assert age_on(date(1990, 3, 10), date(2026, 3, 9)) == 35

    def test_day_after_birthday(self):
        assert age_on(date(1990, 3, 10), date(2026, 3, 11)) == 36

    def test_leap_day_birthday_non_leap_year(self):
        """Feb-29 birthday; check that the year is decremented correctly."""
        assert age_on(date(2000, 2, 29), date(2026, 2, 28)) == 25

    def test_newborn(self):
        assert age_on(date(2026, 1, 1), date(2026, 1, 1)) == 0


# ===========================================================================
# Happy path
# ===========================================================================
class TestValidPolicies:
    def test_valid_auto_policy(self):
        validate_policy(make_policy(), today=TODAY)

    def test_valid_home_policy(self):
        validate_policy(make_policy(product="HOME"), today=TODAY)

    def test_valid_life_policy(self):
        validate_policy(make_policy(product="LIFE"), today=TODAY)

    def test_policy_starting_today_is_accepted(self):
        """start_date == today should NOT raise (only strictly in the past fails)."""
        validate_policy(make_policy(start_date=TODAY, end_date=date(2027, 11, 19)), today=TODAY)

    def test_max_term_exactly_366_days(self):
        """A term of exactly 366 days is at the boundary and must pass."""
        start = date(2026, 12, 1)
        end = date(2027, 12, 2)  # 366 days
        validate_policy(make_policy(start_date=start, end_date=end), today=TODAY)

    def test_sum_insured_at_product_maximum_auto(self):
        validate_policy(make_policy(sum_insured=250_000), today=TODAY)

    def test_sum_insured_at_product_maximum_home(self):
        validate_policy(make_policy(product="HOME", sum_insured=2_000_000), today=TODAY)

    def test_sum_insured_at_product_maximum_life(self):
        validate_policy(make_policy(product="LIFE", sum_insured=5_000_000), today=TODAY)

    def test_holder_at_minimum_age(self):
        """Holder turns exactly 18 on start_date."""
        start = date(2026, 12, 1)
        birth = date(2008, 12, 1)
        validate_policy(make_policy(holder_birth_date=birth, start_date=start), today=TODAY)

    def test_holder_at_maximum_age_auto(self):
        """Holder turns exactly 85 on start_date for AUTO."""
        start = date(2026, 12, 1)
        birth = date(1941, 12, 1)
        validate_policy(make_policy(holder_birth_date=birth, start_date=start), today=TODAY)

    def test_two_letter_state_various_codes(self):
        for state in ("NY", "FL", "WA", "TX", "OH"):
            validate_policy(make_policy(state=state), today=TODAY)


# ===========================================================================
# policy_number
# ===========================================================================
class TestPolicyNumber:
    @pytest.mark.parametrize("bad_number", [
        "12345678",          # no prefix
        "POL-1234567",       # only 7 digits
        "POL-123456789",     # 9 digits
        "POL_12345678",      # underscore instead of dash
        "pol-12345678",      # lowercase
        "POL-1234567A",      # letter in digits
        "",                  # empty
        "POL-",              # digits missing
    ])
    def test_invalid_policy_number_rejected(self, bad_number):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(policy_number=bad_number), today=TODAY)
        assert any("policy_number" in e for e in exc_info.value.errors)

    def test_valid_policy_number_all_zeros(self):
        validate_policy(make_policy(policy_number="POL-00000000"), today=TODAY)

    def test_valid_policy_number_all_nines(self):
        validate_policy(make_policy(policy_number="POL-00000099"), today=TODAY)


# ===========================================================================
# product
# ===========================================================================
class TestProduct:
    @pytest.mark.parametrize("bad_product", [
        "DENTAL", "TRAVEL", "auto", "home", "life", "", "AU TO",
    ])
    def test_unsupported_product_rejected(self, bad_product):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(product=bad_product), today=TODAY)
        assert any("unsupported product" in e for e in exc_info.value.errors)


# ===========================================================================
# Holder age
# ===========================================================================
class TestHolderAge:
    def test_holder_too_young_auto(self):
        """Holder is 17 on start_date for AUTO — below minimum of 18."""
        start = date(2026, 12, 1)
        birth = date(2009, 12, 2)  # turns 17 on 2026-12-01
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(holder_birth_date=birth, start_date=start), today=TODAY)
        assert any("holder age" in e for e in exc_info.value.errors)

    def test_holder_too_old_auto(self):
        """Holder is 86 on start_date for AUTO — above maximum of 85."""
        start = date(2026, 12, 1)
        birth = date(1940, 11, 30)  # turns 86 on 2026-11-30
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(holder_birth_date=birth, start_date=start), today=TODAY)
        assert any("holder age" in e for e in exc_info.value.errors)

    def test_holder_too_old_life(self):
        """LIFE has a tighter maximum of 70."""
        start = date(2026, 12, 1)
        birth = date(1955, 11, 30)  # turns 71 on 2026-11-30
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(product="LIFE", holder_birth_date=birth, start_date=start), today=TODAY)
        assert any("holder age" in e for e in exc_info.value.errors)

    def test_holder_at_life_maximum_age(self):
        """Holder turns exactly 70 on start_date for LIFE — boundary is valid."""
        start = date(2026, 12, 1)
        birth = date(1956, 12, 1)
        validate_policy(
            make_policy(product="LIFE", holder_birth_date=birth, start_date=start),
            today=TODAY,
        )


# ===========================================================================
# sum_insured
# ===========================================================================
class TestSumInsured:
    def test_zero_sum_insured_rejected(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(sum_insured=0), today=TODAY)
        assert any("sum_insured must be positive" in e for e in exc_info.value.errors)

    def test_negative_sum_insured_rejected(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(sum_insured=-1), today=TODAY)
        assert any("sum_insured must be positive" in e for e in exc_info.value.errors)

    def test_sum_insured_above_auto_max_rejected(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(product="AUTO", sum_insured=250_001), today=TODAY)
        assert any("sum_insured above product maximum" in e for e in exc_info.value.errors)

    def test_sum_insured_above_home_max_rejected(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(product="HOME", sum_insured=2_000_001), today=TODAY)
        assert any("sum_insured above product maximum" in e for e in exc_info.value.errors)

    def test_sum_insured_above_life_max_rejected(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(product="LIFE", sum_insured=5_000_001), today=TODAY)
        assert any("sum_insured above product maximum" in e for e in exc_info.value.errors)

    def test_minimum_valid_sum_insured(self):
        validate_policy(make_policy(sum_insured=1), today=TODAY)


# ===========================================================================
# Policy dates
# ===========================================================================
class TestPolicyDates:
    def test_end_date_before_start_date_rejected(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(
                make_policy(start_date=date(2026, 12, 1), end_date=date(2026, 11, 30)),
                today=TODAY,
            )
        assert any("end_date must be after start_date" in e for e in exc_info.value.errors)

    def test_end_date_equal_to_start_date_rejected(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(
                make_policy(start_date=date(2026, 12, 1), end_date=date(2026, 12, 1)),
                today=TODAY,
            )
        assert any("end_date must be after start_date" in e for e in exc_info.value.errors)

    def test_term_exceeds_366_days_rejected(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(
                make_policy(start_date=date(2026, 12, 1), end_date=date(2027, 12, 3)),  # 367 days
                today=TODAY,
            )
        assert any("policy term cannot exceed one year" in e for e in exc_info.value.errors)

    def test_start_date_in_the_past_rejected(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(
                make_policy(start_date=date(2026, 11, 18), end_date=date(2027, 11, 18)),
                today=TODAY,
            )
        assert any("start_date cannot be in the past" in e for e in exc_info.value.errors)

    def test_start_date_well_in_future_accepted(self):
        validate_policy(
            make_policy(start_date=date(2027, 6, 1), end_date=date(2028, 6, 1)),
            today=TODAY,
        )


# ===========================================================================
# state code
# ===========================================================================
class TestStateCode:
    @pytest.mark.parametrize("bad_state", [
        "cal",    # 3 letters
        "C",      # 1 letter
        "ca",     # lowercase
        "C1",     # digit
        "12",     # all digits
        "",       # empty
        "C A",    # space
    ])
    def test_invalid_state_rejected(self, bad_state):
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(state=bad_state), today=TODAY)
        assert any("state must be a two-letter code" in e for e in exc_info.value.errors)


# ===========================================================================
# Multiple simultaneous errors
# ===========================================================================
class TestMultipleErrors:
    def test_all_errors_reported_at_once(self):
        """A policy with several broken rules surfaces all of them in one exception."""
        bad_policy = make_policy(
            policy_number="INVALID",
            sum_insured=0,
            start_date=date(2026, 11, 1),   # in the past
            end_date=date(2026, 11, 1),      # equal to start (also in the past)
            state="bad",
        )
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(bad_policy, today=TODAY)
        errors = exc_info.value.errors
        assert len(errors) >= 4, f"Expected ≥4 errors, got {errors}"

    def test_error_list_accessible_on_exception(self):
        """PolicyValidationError.errors is a list of strings."""
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(policy_number="BAD", sum_insured=-5), today=TODAY)
        assert isinstance(exc_info.value.errors, list)
        assert all(isinstance(e, str) for e in exc_info.value.errors)

    def test_exception_str_contains_all_errors(self):
        """The string form of the exception joins all error messages."""
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(policy_number="BAD", sum_insured=-5), today=TODAY)
        exc_str = str(exc_info.value)
        for error in exc_info.value.errors:
            assert error in exc_str

    def test_unsupported_product_skips_age_and_sum_insured_max_checks(self):
        """When the product is unsupported, age/max-sum checks do not run (no key error)."""
        with pytest.raises(PolicyValidationError) as exc_info:
            validate_policy(make_policy(product="DENTAL"), today=TODAY)
        # Only the unsupported-product error appears, not an age or sum_insured-max error
        assert any("unsupported product" in e for e in exc_info.value.errors)
        assert not any("holder age" in e for e in exc_info.value.errors)
        assert not any("sum_insured above" in e for e in exc_info.value.errors)
