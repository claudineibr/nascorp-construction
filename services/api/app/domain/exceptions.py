class ConstructionDomainError(Exception):
    def __init__(self, *, message: str, status_code: int = 400, error_code: str = "CONSTRUCTION_DOMAIN_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class ConstructionNotFoundError(ConstructionDomainError):
    """`resource_name` arrives with its article ("a obra", "o bloco").

    The project has no i18n and the UI is entirely in Portuguese, so the domain
    message is what the user reads. Carrying the article along with the name
    solves gender agreement without threading it through every call site.
    """

    def __init__(self, *, resource_name: str) -> None:
        super().__init__(
            message=f"Não foi possível encontrar {resource_name}.",
            status_code=404,
            error_code="CONSTRUCTION_RESOURCE_NOT_FOUND",
        )


class ConstructionDuplicateCodeError(ConstructionDomainError):
    def __init__(self, *, resource_name: str, code: str, code_label: str = "código") -> None:
        super().__init__(
            message=f"O {code_label} '{code}' já está em uso para {resource_name}.",
            status_code=409,
            error_code="CONSTRUCTION_DUPLICATE_CODE",
        )


class ConstructionInvalidStatusTransitionError(ConstructionDomainError):
    def __init__(self, *, current_status: str, next_status: str) -> None:
        super().__init__(
            message=f"Não é possível mudar a situação de '{current_status}' para '{next_status}'.",
            status_code=400,
            error_code="CONSTRUCTION_INVALID_STATUS_TRANSITION",
        )


class ConstructionInvalidValueError(ConstructionDomainError):
    def __init__(self, *, message: str, error_code: str = "CONSTRUCTION_INVALID_VALUE") -> None:
        super().__init__(message=message, status_code=400, error_code=error_code)


class ConstructionResourceInUseError(ConstructionDomainError):
    def __init__(self, *, message: str, error_code: str = "CONSTRUCTION_RESOURCE_IN_USE") -> None:
        super().__init__(message=message, status_code=409, error_code=error_code)
