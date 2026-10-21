from decimal import Decimal, InvalidOperation

from app.domain.exceptions import ConstructionInvalidValueError

DEDUCTION_TYPES = {
    "FIXED": "Valor fixo",
    "PERCENT_OF_PAID": "Multa sobre o valor pago",
    "PERCENT_OF_CONTRACT": "Percentual sobre o valor do contrato",
    "FRUITION": "Taxa de fruição",
    "BROKERAGE": "Comissão de corretagem",
}
PERCENT_TYPES = {"PERCENT_OF_PAID", "PERCENT_OF_CONTRACT", "FRUITION"}
PENALTY_CEILING = Decimal("25")
SEGREGATED_PENALTY_CEILING = Decimal("50")
HUNDRED = Decimal("100")


def _invalid(message: str) -> ConstructionInvalidValueError:
    return ConstructionInvalidValueError(message=message, error_code="CONSTRUCTION_TERMINATION_TERMS_INVALID")


def normalize_termination_terms(terms: dict | None, *, has_segregated_assets: bool) -> dict:
    terms = dict(terms or {})
    ceiling = SEGREGATED_PENALTY_CEILING if has_segregated_assets else PENALTY_CEILING
    deductions = []
    for raw in terms.get("deductions") or []:
        raw = dict(raw or {})
        kind = str(raw.get("type") or "").upper()
        if kind not in DEDUCTION_TYPES:
            raise _invalid("Tipo de dedução do distrato desconhecido.")
        try:
            value = Decimal(str(raw.get("value")))
        except (InvalidOperation, TypeError) as error:
            raise _invalid("Informe o valor de cada dedução do distrato.") from error
        if value < 0:
            raise _invalid("A dedução do distrato não pode ser negativa.")
        if kind in PERCENT_TYPES and value > HUNDRED:
            raise _invalid("O percentual da dedução precisa ficar entre 0 e 100.")
        if kind == "PERCENT_OF_PAID" and value > ceiling:
            raise _invalid(
                f"A multa sobre o valor pago não pode passar de {ceiling}% "
                f"({'com' if has_segregated_assets else 'sem'} patrimônio de afetação)."
            )
        label = str(raw.get("label") or "").strip()[:120] or DEDUCTION_TYPES[kind]
        deductions.append({"type": kind, "value": str(value), "label": label})
    try:
        minimum = Decimal(str(terms.get("minimum_refund_percent") or 0))
        deadline = int(terms.get("refund_deadline_days") or 0)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise _invalid("Mínimo a devolver e prazo de devolução precisam ser números.") from error
    if minimum < 0 or minimum > HUNDRED:
        raise _invalid("O mínimo a devolver precisa ficar entre 0% e 100% do valor pago.")
    if deadline < 0:
        raise _invalid("O prazo de devolução não pode ser negativo.")
    return {"deductions": deductions, "minimum_refund_percent": str(minimum), "refund_deadline_days": deadline}
