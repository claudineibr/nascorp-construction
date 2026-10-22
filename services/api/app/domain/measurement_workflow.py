from decimal import Decimal

from app.domain.exceptions import ConstructionInvalidValueError


def measurement_purpose(measurement):
    if measurement.subcontract_id:
        return "CONTRACT"
    if getattr(measurement, "purpose", None):
        return measurement.purpose
    return "CONTROL" if Decimal(str(measurement.gross_amount or measurement.measured_amount or 0)) == 0 else "SERVICE"


def assert_measurement_editable(measurement):
    if measurement.status not in {"draft", "rejected"}:
        raise ConstructionInvalidValueError(
            message="Somente medição em rascunho ou rejeitada pode ser alterada. Devolva a medição enviada para ajustes antes de editar.",
            error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
        )


def measurement_item_label(description, service_template_name):
    if not service_template_name or description.casefold() == service_template_name.casefold():
        return description
    return f"{service_template_name} · {description}"


def resolve_measurement_purpose(purpose, contract_id, amount):
    resolved = purpose or ("CONTRACT" if contract_id else "CONTROL" if not amount else "SERVICE")
    if (resolved == "CONTRACT") != bool(contract_id):
        raise ConstructionInvalidValueError(message="Selecione um contrato para a medição contratual; OS de controle e serviço avulso não usam contrato.")
    if resolved == "CONTROL" and amount:
        raise ConstructionInvalidValueError(message="OS de controle não tem valor próprio. Use serviço avulso para registrar pagamento próprio.")
    return resolved
