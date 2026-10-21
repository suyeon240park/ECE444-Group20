"""The one exception services raise when a product request cannot be answered."""

from __future__ import annotations

from app.models.product import ApiError, ErrorCode


class ProductLookupError(Exception):
    """A lookup that ends in one of the contract's error responses (docs/api/README.md)."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    @property
    def error(self) -> ApiError:
        return ApiError(self.code, self.message)
