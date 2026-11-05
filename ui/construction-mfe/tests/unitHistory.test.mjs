import assert from "node:assert/strict"
import test from "node:test"

import { buildUnitHistoryRows } from "../src/features/unitTermination/unitHistory.js"

const entered = "2026-11-05T18:01:40Z"
const left = "2026-11-05T19:26:51Z"
const legacy = {
  id: "legacy", buyer_person_id: "buyer", included_at: "2026-11-05T17:16:29Z", excluded_at: entered,
}
const native = { id: "native", buyer_person_id: "buyer", included_at: entered, excluded_at: left }
const sale = {
  id: "sale", buyerPersonId: "buyer", status: "TRANSFERRED", soldAt: entered, transferredAt: left,
}
const incoming = {
  transfer_id: "incoming", source_unit_id: "previous", target_unit_id: "unit",
  source_sale_id: "previous-sale", occurred_at: entered,
}
const outgoing = {
  transfer_id: "outgoing", source_unit_id: "unit", target_unit_id: "next",
  source_sale_id: "sale", occurred_at: left,
}

test("one buyer passage contains its sale and both transfers without erasing the legacy passage", () => {
  const rows = buildUnitHistoryRows({
    buyers: [legacy, native], sales: [sale], transfers: [outgoing, incoming], unitId: "unit",
  })
  assert.equal(rows.length, 2)
  assert.equal(rows[0].excludedAt, entered)
  assert.equal(rows[1].sales[0].id, sale.id)
  assert.equal(rows[1].transfers.length, 2)
  assert.deepEqual(rows[1].transfers.map((item) => item.transfer_id), ["incoming", "outgoing"])
  assert.equal(rows[1].includedAt, entered)
  assert.equal(rows[1].excludedAt, left)
})

test("reactivated sale joins the new open passage while preserving the closed passage", () => {
  const rows = buildUnitHistoryRows({
    buyers: [native, { ...native, id: "reactivated", included_at: "2026-11-06T12:00:00Z", excluded_at: null }],
    sales: [{ ...sale, status: "ACTIVE" }], transfers: [], unitId: "unit",
  })
  assert.equal(rows.length, 2)
  assert.equal(rows[0].sales.length, 0)
  assert.equal(rows[1].sales[0].id, sale.id)
  assert.equal(rows[1].excludedAt, null)
})

test("ambiguous passages remain separate and an explicit sale link keeps its transfer", () => {
  const rows = buildUnitHistoryRows({
    buyers: [native, { ...native, id: "another-import" }],
    sales: [{ ...sale, soldAt: "2026-11-01T12:00:00Z" }], transfers: [outgoing], unitId: "unit",
  })
  assert.equal(rows.length, 3)
  assert.equal(rows.filter((row) => row.history).length, 2)
  assert.equal(rows.find((row) => row.sales.length).transfers[0].transfer_id, outgoing.transfer_id)
})
