import test from "node:test"
import assert from "node:assert/strict"
import {
  canLinkPayable,
  getMeasurementApprovalActions,
  isZeroValueMeasurement,
  measurementPayableBadge,
  newMeasurementPayablePath,
  payableStatusLabel,
} from "../src/features/measurementActions.js"

for (const status of ["draft", "rejected", "paid"]) {
  test(`${status} does not offer approval`, () => {
    assert.deepEqual(getMeasurementApprovalActions({ status }), { canApprove: false })
  })
}
for (const status of ["submitted", "in_approval"]) {
  test(`${status} offers approval`, () => {
    assert.deepEqual(getMeasurementApprovalActions({ status }), { canApprove: true })
  })
}
test("approved without a title does not offer approval again", () => {
  assert.deepEqual(getMeasurementApprovalActions({ status: "approved", externalAccountsPayableId: null, approvedAt: "2026-09-01T10:00:00Z" }), { canApprove: false })
})
test("measurement with a pending reversal cannot link a title", () => {
  assert.equal(canLinkPayable({ status: "approved", externalAccountsPayableId: null, reversalPending: true, supplierPersonId: "supplier", netAmount: "810.00" }), false)
})
test("approved measurement without a title can link an existing ERP title", () => {
  assert.equal(canLinkPayable({ status: "approved", externalAccountsPayableId: null, supplierPersonId: "supplier", netAmount: "810.00" }), true)
})
test("zero-value measurement is paid by the subcontract DNF and cannot link a title", () => {
  const measurement = { status: "approved", externalAccountsPayableId: null, supplierPersonId: "supplier", netAmount: "0.00", measuredAmount: "0.00" }
  assert.equal(isZeroValueMeasurement(measurement), true)
  assert.equal(canLinkPayable(measurement), false)
})
test("linked, unapproved or supplierless measurement cannot link a title", () => {
  assert.equal(canLinkPayable({ status: "approved", externalAccountsPayableId: "title", supplierPersonId: "supplier", netAmount: "810.00" }), false)
  assert.equal(canLinkPayable({ status: "draft", externalAccountsPayableId: null, supplierPersonId: "supplier", netAmount: "810.00" }), false)
  assert.equal(canLinkPayable({ status: "approved", externalAccountsPayableId: null, supplierPersonId: null, netAmount: "810.00" }), false)
})
test("financial badge tells own title, subcontract DNF, zero value and pending apart", () => {
  const base = { status: "approved", supplierPersonId: "supplier" }
  assert.deepEqual(
    measurementPayableBadge({ ...base, netAmount: "810.00", externalAccountsPayableId: "t" }),
    { tone: "success", label: "Vinculado", detail: null },
  )
  assert.equal(
    measurementPayableBadge({ ...base, netAmount: "0.00", externalAccountsPayableId: "t", externalAccountsPayableShared: true }).detail,
    "Título da empreitada",
  )
  assert.equal(measurementPayableBadge({ ...base, netAmount: "0.00" }).label, "Sem valor")
  assert.equal(measurementPayableBadge({ ...base, netAmount: "0.00", subcontractId: "contract" }).label, "Pendente")
  assert.equal(measurementPayableBadge({ ...base, netAmount: "810.00", subcontractId: "contract" }).detail, "Título na aba Empreitada")
  assert.equal(measurementPayableBadge({ ...base, netAmount: "810.00" }).label, "Pendente")
})
test("contract measurement is paid by the contract DNF and cannot link its own title", () => {
  assert.equal(canLinkPayable({ status: "approved", subcontractId: "contract", externalAccountsPayableId: null, supplierPersonId: "supplier", netAmount: "810.00" }), false)
})
test("new title path opens the ERP form for the measurement and returns to the project units", () => {
  const path = newMeasurementPayablePath({ id: "m1", projectId: "p1" })
  const params = new URLSearchParams(path.split("?").slice(1).join("?"))
  assert.equal(path.startsWith("/accounts-payable/new?"), true)
  assert.equal(params.get("measurement_id"), "m1")
  assert.equal(params.get("return_to"), "/construction?project_id=p1&tab=units")
})
test("ERP title status is shown in Portuguese", () => {
  assert.equal(payableStatusLabel("PAID"), "Pago")
  assert.equal(payableStatusLabel("OPEN"), "Em aberto")
  assert.equal(payableStatusLabel(null), "-")
})
