from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SubcontractItemRequest(BaseModel):
    id: UUID | None = None
    product_id: UUID | None = None
    description: str = Field(min_length=1, max_length=500)
    unit_of_measure: str = Field(min_length=1, max_length=20)
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    material_unit_price: Decimal = Field(default=0, ge=0, max_digits=20, decimal_places=8)
    labor_unit_price: Decimal = Field(default=0, ge=0, max_digits=20, decimal_places=8)


class SubcontractRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    supplier_person_id: UUID
    valid_from: date
    valid_to: date
    retention_rate: Decimal = Field(default=0, ge=0, le=100, decimal_places=4)
    escrow_rate: Decimal = Field(default=0, ge=0, le=100, decimal_places=4)
    escrow_due_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    items: list[SubcontractItemRequest] = Field(min_length=1, max_length=990)

    @model_validator(mode="after")
    def validate_sheet(self):
        if self.valid_to < self.valid_from:
            raise ValueError("A vigência final não pode preceder a inicial.")
        if self.retention_rate + self.escrow_rate >= 100:
            raise ValueError("Retenção e caução precisam deixar saldo líquido positivo.")
        if self.escrow_rate and self.escrow_due_date is None:
            raise ValueError("Informe a data prevista de liberação da caução.")
        ids = [item.id for item in self.items if item.id]
        if len(ids) != len(set(ids)):
            raise ValueError("Os itens do contrato não podem se repetir.")
        return self


class SubcontractReasonRequest(BaseModel):
    reason: str = Field(min_length=15, max_length=1000)


class SubcontractDirectBillRequest(BaseModel):
    payable_document_id: UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class SubcontractDeductionRequest(BaseModel):
    direct_bill_id: UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
