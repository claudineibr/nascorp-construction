import test from "node:test"
import assert from "node:assert/strict"
import { getMeasurementApprovalActions } from "../src/features/measurementActions.js"

for (const status of ["draft", "rejected", "paid"]) {
  test(`${status} does not offer approval`, () => {
    assert.deepEqual(getMeasurementApprovalActions({ status }), { canApprove: false, canRetryIntegration: false })
  })
}
for (const status of ["submitted", "in_approval"]) {
  test(`${status} offers approval`, () => {
    assert.deepEqual(getMeasurementApprovalActions({ status }), { canApprove: true, canRetryIntegration: false })
  })
}
test("approved without a title offers resending to ERP", () => {
  assert.deepEqual(getMeasurementApprovalActions({ status: "approved", externalAccountsPayableId: null }), { canApprove: true, canRetryIntegration: true })
})
test("approved with a title does not offer approval or resending", () => {
  assert.deepEqual(getMeasurementApprovalActions({ status: "approved", externalAccountsPayableId: "title-id" }), { canApprove: false, canRetryIntegration: false })
})
