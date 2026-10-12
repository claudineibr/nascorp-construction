import assert from "node:assert/strict"
import test from "node:test"
import { currencyDecimal, currencyFromNumber, currencyNumber, formatCurrencyInput } from "./currencyInput.js"

test("mascara o valor digitado em reais, centavo a centavo", () => {
  assert.equal(formatCurrencyInput(""), "")
  assert.equal(formatCurrencyInput("5"), "0,05")
  assert.equal(formatCurrencyInput("123456"), "1.234,56")
  assert.equal(formatCurrencyInput("R$ 1.234,567"), "12.345,67")
})

test("converte o decimal da API para a máscara e de volta", () => {
  assert.equal(currencyFromNumber("1234.50000000"), "1.234,50")
  assert.equal(currencyFromNumber(null), "0,00")
  assert.equal(currencyDecimal("1.234,50"), "1234.50")
  assert.equal(currencyNumber("0,00"), 0)
  assert.equal(currencyNumber("12,30"), 12.3)
})
