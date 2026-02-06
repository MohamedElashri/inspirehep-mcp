"""Custom exception classes for InspireHEP MCP server."""


class InspireHEPError(Exception):
    """Base exception for all InspireHEP errors."""

    def __init__(self, message: str, details: str | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class APIError(InspireHEPError):
    """Error communicating with the InspireHEP API."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: str | None = None,
    ) -> None:
        self.status_code = status_code
        super().__init__(message, details)

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code is not None:
            parts.append(f"(HTTP {self.status_code})")
        if self.details:
            parts.append(f": {self.details}")
        return " ".join(parts)


class RateLimitError(APIError):
    """Rate limit exceeded on the InspireHEP API."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        details = f"retry after {retry_after}s" if retry_after else None
        super().__init__(msg, status_code=429, details=details)


class NotFoundError(APIError):
    """Requested resource was not found on InspireHEP."""

    def __init__(self, resource_type: str, identifier: str) -> None:
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(
            f"{resource_type} not found",
            status_code=404,
            details=f"identifier={identifier}",
        )


class InvalidIdentifierError(InspireHEPError):
    """An identifier (arXiv ID, DOI, Inspire ID) is malformed."""

    def __init__(self, id_type: str, value: str) -> None:
        self.id_type = id_type
        self.value = value
        super().__init__(
            f"Invalid {id_type} identifier",
            details=f"'{value}'",
        )
