# File: app/tests/test_validators.py
"""Pure-function validators and content helpers."""

from datetime import date, timedelta

import pytest

from app.common.validators import (
    ContentValidator,
    ValidationUtils,
    content_validator,
    email_validator,
    file_extension_validator,
    file_size_validator,
    password_validator,
    slug_validator,
    url_validator,
    username_validator,
)


class TestValidationUtils:
    @pytest.mark.parametrize(
        ("email", "expected"),
        [
            ("a@b.co", True),
            ("first.last+tag@example.org", True),
            ("no-at.example", False),
            ("", False),
        ],
    )
    def test_validate_email(self, email, expected):
        assert ValidationUtils.validate_email(email) is expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://example.com/path?q=1", True),
            ("ftp://example.com", False),
            ("not a url", False),
        ],
    )
    def test_validate_url(self, url, expected):
        assert ValidationUtils.validate_url(url) is expected

    def test_validate_url_custom_schemes(self):
        assert ValidationUtils.validate_url("ftp://host/file", allowed_schemes=["ftp"])

    @pytest.mark.parametrize(
        ("slug", "expected"),
        [("fast-api-course", True), ("Bad Slug", False), ("with_underscore", False)],
    )
    def test_validate_slug(self, slug, expected):
        assert ValidationUtils.validate_slug(slug) is expected

    @pytest.mark.parametrize(
        ("name", "expected"), [("user_01", True), ("ab", False), ("no spaces", False)]
    )
    def test_validate_username(self, name, expected):
        assert ValidationUtils.validate_username(name) is expected

    def test_password_strength_reports_every_issue(self):
        result = ValidationUtils.validate_password_strength("short")
        assert result["is_valid"] is False
        assert result["strength"] == "weak"
        assert any("8 characters" in issue for issue in result["issues"])
        assert any("uppercase" in issue for issue in result["issues"])

    def test_password_strength_strong(self):
        result = ValidationUtils.validate_password_strength("Str0ng!Passw0rd#2024")
        assert result == {"is_valid": True, "strength": "strong", "score": 6, "issues": []}

    def test_password_strength_penalises_common_patterns(self):
        result = ValidationUtils.validate_password_strength("Password123!")
        assert "Password contains common patterns" in result["issues"]
        assert result["is_valid"] is False

    def test_sanitize_html_strips_scripts_and_handlers(self):
        dirty = '<p onclick="x()">hi</p><script>alert(1)</script><a href="javascript:evil()">l</a>'
        clean = ValidationUtils.sanitize_html(dirty)
        assert "<script" not in clean
        assert "onclick" not in clean
        assert "javascript:" not in clean
        assert "<p>hi</p>" in clean

    def test_file_size_and_extension(self):
        assert ValidationUtils.validate_file_size(10, 100)
        assert not ValidationUtils.validate_file_size(101, 100)
        assert ValidationUtils.validate_file_extension("report.PDF", ["pdf", "txt"])
        assert not ValidationUtils.validate_file_extension("shell.sh", ["pdf"])

    def test_date_range_and_age(self):
        today = date.today()
        assert ValidationUtils.validate_date_range(today, today + timedelta(days=1))
        assert not ValidationUtils.validate_date_range(today, today - timedelta(days=1))
        assert ValidationUtils.validate_age(today - timedelta(days=365 * 20))
        assert not ValidationUtils.validate_age(today - timedelta(days=365 * 5))
        assert not ValidationUtils.validate_age(today - timedelta(days=365 * 130))

    def test_phone(self):
        assert ValidationUtils.validate_phone("+1 (555) 123-4567")
        assert not ValidationUtils.validate_phone("12")


class TestPydanticValidatorFactories:
    def test_scalar_validators_pass_through_valid_values(self):
        assert email_validator(None, "a@b.co") == "a@b.co"
        assert url_validator(None, "https://x.io") == "https://x.io"
        assert slug_validator(None, "ok-slug") == "ok-slug"
        assert username_validator(None, "valid_user") == "valid_user"
        assert password_validator(None, "Str0ng!Passw0rd#") == "Str0ng!Passw0rd#"

    @pytest.mark.parametrize(
        ("validator", "value"),
        [
            (email_validator, "nope"),
            (url_validator, "nope"),
            (slug_validator, "Nope Slug"),
            (username_validator, "x"),
            (password_validator, "weak"),
        ],
    )
    def test_scalar_validators_reject(self, validator, value):
        with pytest.raises(ValueError):
            validator(None, value)

    def test_file_validators(self):
        class Upload:
            size = 5
            filename = "a.txt"

        assert file_size_validator(10)(None, Upload()) is not None
        with pytest.raises(ValueError):
            file_size_validator(1)(None, Upload())
        assert file_extension_validator(["txt"])(None, Upload()) is not None
        with pytest.raises(ValueError):
            file_extension_validator(["pdf"])(None, Upload())

    def test_content_validator_sanitises_and_checks(self):
        check = content_validator(min_length=3, max_length=40, check_profanity=True)
        assert check(None, "<b>fine</b><script>x</script>") == "<b>fine</b>"
        with pytest.raises(ValueError):
            check(None, "this is a scam offer")
        with pytest.raises(ValueError):
            check(None, "x" * 50)
        assert check(None, "") == ""


class TestContentValidator:
    def test_profanity_substring_vs_strict(self):
        assert ContentValidator.validate_profanity("a scammer's tale") is False
        assert ContentValidator.validate_profanity("a scammer's tale", strict=True) is True
        assert ContentValidator.validate_profanity("hello world")

    def test_content_length(self):
        result = ContentValidator.validate_content_length("one two", min_words=3)
        assert result["word_count"] == 2 and not result["is_valid"]
        assert ContentValidator.validate_content_length("ok", max_length=1)["is_valid"] is False
        assert ContentValidator.validate_content_length("a b c", max_words=2)["is_valid"] is False

    def test_extractors(self):
        text = "hi @alice and @bob_1 see #fastapi #py https://x.io/a?b=1"
        assert ContentValidator.extract_mentions(text) == ["alice", "bob_1"]
        assert ContentValidator.extract_hashtags(text) == ["fastapi", "py"]
        assert ContentValidator.extract_urls(text) == ["https://x.io/a?b=1"]
