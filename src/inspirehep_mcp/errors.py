"""Custom exception classes for InspireHEP MCP server.

All exceptions include an ``suggestion`` field with actionable advice
suitable for display to an LLM or end user.
"""


class InspireHEPError(Exception):
    """Base exception for all InspireHEP errors."""

    def __init__(
        self,
        message: str,
        details: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.message = message
        self.details = details
        self.suggestion = suggestion
        super().__init__(message)

    def __str__(self) -> str:
        parts = [self.message]
        if self.details:
            parts.append(self.details)
        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")
        return " — ".join(parts)


class APIError(InspireHEPError):
    """Error communicating with the InspireHEP API."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.status_code = status_code
        if suggestion is None and status_code is not None:
            suggestion = _api_suggestion(status_code)
        super().__init__(message, details, suggestion)

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code is not None:
            parts[0] += f" (HTTP {self.status_code})"
        if self.details:
            parts.append(self.details)
        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")
        return " — ".join(parts)


def _api_suggestion(status_code: int) -> str:
    """Return a user-friendly suggestion based on HTTP status code."""
    suggestions = {
        400: "Check the query syntax. InspireHEP uses SPIRES-style search syntax.",
        403: "Access denied. This resource may require special permissions.",
        404: "The record was not found. Verify the identifier is correct.",
        429: "Rate limit exceeded. Wait a moment and try again.",
        500: "InspireHEP server error. Try again in a few minutes.",
        502: "InspireHEP is temporarily unavailable. Try again shortly.",
        503: "InspireHEP is under maintenance. Try again later.",
    }
    return suggestions.get(status_code, "An unexpected API error occurred. Try again later.")


class RateLimitError(APIError):
    """Rate limit exceeded on the InspireHEP API."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        details = f"retry after {retry_after}s" if retry_after else None
        suggestion = (
            f"Wait {retry_after} seconds before retrying."
            if retry_after
            else "Wait a few seconds before retrying."
        )
        super().__init__(msg, status_code=429, details=details, suggestion=suggestion)


class NotFoundError(APIError):
    """Requested resource was not found on InspireHEP."""

    def __init__(self, resource_type: str, identifier: str) -> None:
        self.resource_type = resource_type
        self.identifier = identifier
        suggestion = (
            f"No {resource_type} found for '{identifier}'. "
            "Check the identifier format: Inspire IDs are numeric, "
            "arXiv IDs look like '2301.12345' or 'hep-ph/0123456', "
            "DOIs start with '10.'."
        )
        super().__init__(
            f"{resource_type} not found",
            status_code=404,
            details=f"identifier={identifier}",
            suggestion=suggestion,
        )


class InvalidIdentifierError(InspireHEPError):
    """An identifier (arXiv ID, DOI, Inspire ID) is malformed."""

    _FORMAT_HINTS = {
        "arXiv": "Expected formats: '2301.12345', 'hep-ph/0123456', or 'https://arxiv.org/abs/...'",
        "DOI": "Expected format: '10.XXXX/...' or 'https://doi.org/10.XXXX/...'",
        "Inspire": "Expected format: a numeric ID like '3456' or '1234567'",
        "unknown": "Provide an arXiv ID, DOI, or numeric Inspire ID.",
    }

    def __init__(self, id_type: str, value: str) -> None:
        self.id_type = id_type
        self.value = value
        hint = self._FORMAT_HINTS.get(id_type, self._FORMAT_HINTS["unknown"])
        super().__init__(
            f"Invalid {id_type} identifier",
            details=f"'{value}'",
            suggestion=hint,
        )
