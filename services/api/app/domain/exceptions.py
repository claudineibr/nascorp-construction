class ConstructionDomainError(Exception):
    def __init__(self, *, message: str, status_code: int = 400, error_code: str = "CONSTRUCTION_DOMAIN_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class ConstructionNotFoundError(ConstructionDomainError):
    def __init__(self, *, resource_name: str) -> None:
        super().__init__(
            message=f"{resource_name} was not found.",
            status_code=404,
            error_code="CONSTRUCTION_RESOURCE_NOT_FOUND",
        )


class ConstructionDuplicateCodeError(ConstructionDomainError):
    def __init__(self, *, resource_name: str, code: str) -> None:
        super().__init__(
            message=f"{resource_name} code '{code}' already exists in this scope.",
            status_code=409,
            error_code="CONSTRUCTION_DUPLICATE_CODE",
        )


class ConstructionInvalidStatusTransitionError(ConstructionDomainError):
    def __init__(self, *, current_status: str, next_status: str) -> None:
        super().__init__(
            message=f"Cannot transition project from '{current_status}' to '{next_status}'.",
            status_code=400,
            error_code="CONSTRUCTION_INVALID_STATUS_TRANSITION",
        )


class ConstructionInvalidValueError(ConstructionDomainError):
    def __init__(self, *, message: str, error_code: str = "CONSTRUCTION_INVALID_VALUE") -> None:
        super().__init__(message=message, status_code=400, error_code=error_code)
