import test from "node:test"
import assert from "node:assert/strict"
import {
  canLinkPayable,
  canApproveMeasurementInDialog,
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

test("direct approval needs both edit permission and self approval authorization", () => {
  const bridge = { user: { id: "actor" }, canUpdate: (feature) => feature === "construction_measurements" }
  assert.equal(canApproveMeasurementInDialog({ status: "draft" }, bridge), false)
  assert.equal(canApproveMeasurementInDialog({ status: "draft" }, { ...bridge, canUpdate: () => true }), true)
  assert.equal(canApproveMeasurementInDialog({ status: "draft" }, { ...bridge,
    canUpdate: (feature) => feature === "construction_measurement_self_approval" }), false)
})

test("submitted creator and sender need self approval while another authorized user can approve", () => {
  const measurement = { status: "submitted", createdByUserId: "creator", submittedByUserId: "sender" }
  const bridge = { canUpdate: (feature) => feature === "construction_measurements" }
  for (const id of ["creator", "sender"]) {
    assert.equal(canApproveMeasurementInDialog(measurement, { ...bridge, user: { id } }), false)
  }
  assert.equal(canApproveMeasurementInDialog(measurement, { ...bridge, user: { id: "other" } }), true)
  assert.equal(canApproveMeasurementInDialog(measurement, bridge), false)
})

test("closed measurements and pending reversals do not offer dialog approval", () => {
  const bridge = { user: { id: "actor" }, canUpdate: () => true }
  for (const status of ["approved", "paid"]) {
    assert.equal(canApproveMeasurementInDialog({ status }, bridge), false)
  }
  assert.equal(canApproveMeasurementInDialog({ status: "submitted", reversalPending: true }, bridge), false)
})
