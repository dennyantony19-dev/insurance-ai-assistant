from guardrails_core.pii import scan


def test_ssn_masked():
    r = scan("Customer SSN is 123-45-6789, please test with it")
    assert "123-45-6789" not in r.text and "{US_SSN}" in r.text
    assert r.masked and not r.blocked


def test_invalid_ssn_area_not_masked():
    assert scan("id 000-12-3456").findings == []


def test_policy_and_claim_numbers_masked_but_synthetic_range_kept():
    r = scan("POL-48213377 and CLM-90011234 vs POL-00000001")
    assert r.text == "{POLICY_NUMBER} and {CLAIM_NUMBER} vs POL-00000001"


def test_card_needs_luhn():
    assert "{CREDIT_CARD}" in scan("card 4111 1111 1111 1111").text
    assert scan("order 1234 5678 9012 3456").findings == []


def test_email_and_phone():
    r = scan("mail jane.doe@acme-insure.com or call (212) 555-7788")
    assert r.types() == ["EMAIL", "PHONE"]


def test_example_domains_and_555_01_are_synthetic():
    assert scan("test@example.com 555-0100").findings == []


def test_aws_key_blocks_and_is_not_echoed():
    r = scan("key=AKIAABCDEFGHIJKLMNOP")
    assert r.blocked and "AKIAABCDEFGHIJKLMNOP" not in r.text


def test_findings_never_hold_values():
    r = scan("SSN 123-45-6789")
    assert all(set(f) == {"type", "action"} for f in r.findings)
