import assert from "node:assert/strict"
import test from "node:test"
import { currencyDecimal, procurementLineCents, procurementSubtotalCents, quantityUnits } from "./procurementAmounts.js"

test("arredonda meio centavo como ROUND_HALF_UP do servidor", () => {
  assert.equal(procurementLineCents({ quantity: "1.005", unitPrice: "1,00" }), 101n)
  assert.equal(procurementLineCents({ quantity: "0.145", unitPrice: "1,00" }), 15n)
  assert.equal(procurementLineCents({ quantity: "0.1449", unitPrice: "1,00" }), 14n)
})

test("soma linhas arredondadas e aplica desconto em centavos exatos", () => {
  const items = [{ quantity: "1.005", unitPrice: "1,00" }, { quantity: "2.5", unitPrice: "12,50" }]
  assert.equal(procurementSubtotalCents(items), 3226n)
  assert.equal(procurementSubtotalCents(items) - 26n, 3200n)
})

test("aceita quatro casas e rejeita quantidades fora do contrato", () => {
  assert.equal(quantityUnits("0.0001"), 1n)
  assert.equal(quantityUnits("1e-4"), 1n)
  assert.equal(quantityUnits("9999999999.9999"), 99999999999999n)
  for (const value of ["", "-1", "0", "NaN", "0.00001", "10000000000", "1e50"]) {
    assert.equal(quantityUnits(value), null)
  }
})

test("serializa o preço e desconto em decimal sem ponto flutuante", () => {
  assert.equal(currencyDecimal("999.999.999.999,99"), "999999999999.99")
  assert.equal(currencyDecimal("0,01"), "0.01")
  assert.equal(currencyDecimal(""), "0.00")
})
