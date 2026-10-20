import assert from "node:assert/strict"
import test from "node:test"
import { commissionStatusLabel } from "../src/features/unitCommissions.js"

test("o status calculado pela API aparece em português", () => {
  assert.equal(commissionStatusLabel("open"), "Em aberto")
  assert.equal(commissionStatusLabel("overdue"), "Vencida")
  assert.equal(commissionStatusLabel("paid"), "Paga")
  assert.equal(commissionStatusLabel(null), "—")
})
