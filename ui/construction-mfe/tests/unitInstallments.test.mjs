import assert from "node:assert/strict"
import test from "node:test"
import { buildInstallmentRows, buildInstallmentActions, hasObservation } from "../src/features/unitInstallments.js"

test("41 rows keep separate series, 36 additions and 36 observations", () => {
  const installment = (id, observed) => ({ id, installmentNumber: 1, dueDate: "2026-10-01", observation: observed ? "Texto" : "" })
  const rows = buildInstallmentRows({
    receivableId: "sale", installments: Array.from({ length: 5 }, (_, i) => installment(`sale-${i}`, true)),
    adjustments: [{ receivableId: "addition", installments: Array.from({ length: 36 }, (_, i) => installment(`addition-${i}`, i < 31)) }],
  })
  assert.equal(rows.length, 41)
  assert.equal(rows.filter((row) => row.typeLabel === "Aditivo").length, 36)
  assert.equal(rows.filter(hasObservation).length, 36)
  assert.equal(rows[0].receivableId, "sale")
  assert.equal(rows[5].receivableId, "addition")
  assert.equal(hasObservation({ observation: " \n " }), false)
})

test("observation editing remains available on paid rows and explains locks", () => {
  for (const status of ["OPEN", "PAID"]) {
    for (const canUpdate of [false, true]) {
      for (const hasIssuedReceipt of [false, true]) {
        const actions = buildInstallmentActions({ installment: { status, hasIssuedReceipt }, canUpdate, onEditObservation() {} })
        const action = actions.find((item) => item.key === "observation")
        assert.equal(action.disabled, hasIssuedReceipt || !canUpdate)
        if (action.disabled) assert.ok(action.title)
      }
    }
  }
})
