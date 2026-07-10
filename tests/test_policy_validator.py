from datetime import date

from src.policy_validator import (
    calculate_age,
    check_document_validity,
    get_minimum_age_for_account,
)

calculate_age_fn = calculate_age.func
check_document_validity_fn = check_document_validity.func
get_minimum_age_for_account_fn = get_minimum_age_for_account.func


class TestCalculateAge:
    def test_adult_age(self):
        age = calculate_age_fn("15-08-1990")
        expected = date.today().year - 1990
        if (date.today().month, date.today().day) < (8, 15):
            expected -= 1
        assert age == expected

    def test_exact_birthday(self):
        today = date.today()
        birth = today.strftime("%d-%m-%Y")
        age = calculate_age_fn(birth)
        assert age == 0

    def test_invalid_date(self):
        age = calculate_age_fn("invalid-date")
        assert age == -1

    def test_future_date(self):
        age = calculate_age_fn("15-08-2099")
        today = date.today()
        expected = today.year - 2099
        if (today.month, today.day) < (8, 15):
            expected -= 1
        assert age == expected

    def test_year_boundary(self):
        age = calculate_age_fn("01-01-2000")
        today = date.today()
        expected = today.year - 2000
        if (today.month, today.day) < (1, 1):
            expected -= 1
        assert age == expected


class TestCheckDocumentValidity:
    def test_lifetime_validity(self):
        result = check_document_validity_fn("SEUMUR HIDUP")
        assert result["is_valid"] is True
        assert result["status"] == "VALID_LIFETIME"

    def test_lifetime_alternative(self):
        result = check_document_validity_fn("LIFETIME")
        assert result["is_valid"] is True

    def test_valid_document(self):
        future = date(2030, 6, 15).strftime("%d-%m-%Y")
        result = check_document_validity_fn(future)
        assert result["is_valid"] is True
        assert result["status"] == "VALID"

    def test_expiring_soon(self):
        from datetime import timedelta

        soon = (date.today() + timedelta(days=15)).strftime("%d-%m-%Y")
        result = check_document_validity_fn(soon)
        assert result["is_valid"] is True
        assert result["status"] == "EXPIRING_SOON"

    def test_recently_expired(self):
        from datetime import timedelta

        recent = (date.today() - timedelta(days=15)).strftime("%d-%m-%Y")
        result = check_document_validity_fn(recent)
        assert result["is_valid"] is False
        assert result["status"] == "RECENTLY_EXPIRED"

    def test_expired(self):
        old = "01-01-2020"
        result = check_document_validity_fn(old)
        assert result["is_valid"] is False
        assert result["status"] == "EXPIRED"

    def test_invalid_format(self):
        result = check_document_validity_fn("not-a-date")
        assert result["is_valid"] is False
        assert result["status"] == "INVALID_FORMAT"


class TestGetMinimumAgeForAccount:
    def test_stocks(self):
        r = get_minimum_age_for_account_fn("Stocks")
        assert r["minimum_age"] == 18
        assert r["found"] is True

    def test_futures(self):
        r = get_minimum_age_for_account_fn("Futures")
        assert r["minimum_age"] == 21
        assert r["risk_level"] == "High"

    def test_crypto(self):
        r = get_minimum_age_for_account_fn("Crypto")
        assert r["minimum_age"] == 25
        assert r["risk_level"] == "Very High"

    def test_unknown_account(self):
        r = get_minimum_age_for_account_fn("UnknownType")
        assert r["minimum_age"] == 18
        assert r["found"] is False

    def test_case_insensitive(self):
        r1 = get_minimum_age_for_account_fn("crypto")
        r2 = get_minimum_age_for_account_fn("CRYPTO")
        assert r1["minimum_age"] == r2["minimum_age"] == 25
