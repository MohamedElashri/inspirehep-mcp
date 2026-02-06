"""Unit tests for error classes."""

from inspirehep_mcp.errors import (
    APIError,
    InspireHEPError,
    InvalidIdentifierError,
    NotFoundError,
    RateLimitError,
    _api_suggestion,
)


class TestInspireHEPError:
    def test_message_only(self):
        e = InspireHEPError("something failed")
        assert e.message == "something failed"
        assert e.details is None
        assert e.suggestion is None
        assert str(e) == "something failed"

    def test_with_details(self):
        e = InspireHEPError("fail", details="extra info")
        assert "extra info" in str(e)

    def test_with_suggestion(self):
        e = InspireHEPError("fail", suggestion="try again")
        assert "Suggestion: try again" in str(e)

    def test_full(self):
        e = InspireHEPError("fail", details="detail", suggestion="hint")
        s = str(e)
        assert "fail" in s
        assert "detail" in s
        assert "hint" in s


class TestAPIError:
    def test_with_status_code(self):
        e = APIError("bad request", status_code=400)
        assert e.status_code == 400
        assert "HTTP 400" in str(e)

    def test_auto_suggestion_from_status(self):
        e = APIError("error", status_code=429)
        assert e.suggestion is not None
        assert "Wait" in e.suggestion or "rate" in e.suggestion.lower()

    def test_custom_suggestion_overrides(self):
        e = APIError("error", status_code=429, suggestion="custom hint")
        assert e.suggestion == "custom hint"

    def test_no_status_code(self):
        e = APIError("generic error")
        assert e.status_code is None


class TestRateLimitError:
    def test_with_retry_after(self):
        e = RateLimitError(retry_after=30.0)
        assert e.retry_after == 30.0
        assert e.status_code == 429
        assert "30.0" in str(e)

    def test_without_retry_after(self):
        e = RateLimitError()
        assert e.retry_after is None
        assert "few seconds" in e.suggestion


class TestNotFoundError:
    def test_attributes(self):
        e = NotFoundError("paper", "12345")
        assert e.resource_type == "paper"
        assert e.identifier == "12345"
        assert e.status_code == 404

    def test_suggestion_includes_identifier(self):
        e = NotFoundError("paper", "12345")
        assert "12345" in e.suggestion

    def test_suggestion_includes_format_hints(self):
        e = NotFoundError("paper", "bad")
        assert "arXiv" in e.suggestion
        assert "DOI" in e.suggestion


class TestInvalidIdentifierError:
    def test_arxiv_hint(self):
        e = InvalidIdentifierError("arXiv", "bad")
        assert "2301.12345" in e.suggestion

    def test_doi_hint(self):
        e = InvalidIdentifierError("DOI", "bad")
        assert "10.XXXX" in e.suggestion

    def test_inspire_hint(self):
        e = InvalidIdentifierError("Inspire", "abc")
        assert "numeric" in e.suggestion

    def test_unknown_hint(self):
        e = InvalidIdentifierError("unknown", "???")
        assert "arXiv" in e.suggestion

    def test_attributes(self):
        e = InvalidIdentifierError("arXiv", "bad-val")
        assert e.id_type == "arXiv"
        assert e.value == "bad-val"


class TestApiSuggestion:
    def test_known_codes(self):
        for code in [400, 403, 404, 429, 500, 502, 503]:
            s = _api_suggestion(code)
            assert isinstance(s, str)
            assert len(s) > 10

    def test_unknown_code(self):
        s = _api_suggestion(418)
        assert "unexpected" in s.lower()
