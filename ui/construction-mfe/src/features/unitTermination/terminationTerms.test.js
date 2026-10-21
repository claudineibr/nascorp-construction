import assert from "node:assert/strict"
import test from "node:test"

import {
  TERMINATION_TERMS_INCOMPLETE_MESSAGE,
  terminationTermsError,
  toTerminationTermsPayload,
  toTerminationTermsView,
} from "../../services/constructionApi.js"
import { buildInstallmentActions, installmentOutstanding } from "../unitInstallments.js"

test("converte percentual e valor em reais nos dois sentidos", () => {
  const view = toTerminationTermsView({
    deductions: [
      { type: "PERCENT_OF_PAID", value: "10", label: "Multa" },
      { type: "BROKERAGE", value: "1500.00", label: "Corretagem" },
    ],
    minimum_refund_percent: "70",
    refund_deadline_days: 180,
  })
  assert.equal(view.deductions[1].value, "1.500,00")
  const payload = toTerminationTermsPayload({
    ...view,
    deductions: [...view.deductions, { type: "FRUITION", value: "0,5", label: "" }],
  })
  assert.deepEqual(payload.deductions, [
    { type: "PERCENT_OF_PAID", value: "10", label: "Multa" },
    { type: "BROKERAGE", value: "1500.00", label: "Corretagem" },
    { type: "FRUITION", value: "0.5", label: null },
  ])
  assert.equal(payload.minimum_refund_percent, 70)
  assert.equal(payload.refund_deadline_days, 180)
})

test("percentual decimal vindo da API chega ao campo com vírgula", () => {
  const view = toTerminationTermsView({
    deductions: [{ type: "FRUITION", value: "0.5", label: "Fruição" }],
    minimum_refund_percent: "12.5",
  })
  assert.equal(view.deductions[0].value, "0,5")
  assert.equal(view.minimumRefundPercent, "12,5")
  assert.equal(toTerminationTermsPayload(view).deductions[0].value, "0.5")
  assert.equal(toTerminationTermsPayload(view).minimum_refund_percent, 12.5)
})

test("ignora dedução sem valor", () => {
  assert.deepEqual(toTerminationTermsPayload({ deductions: [{ type: "FIXED", value: "" }] }).deductions, [])
})

test("recusa enviar dedução sem tipo ou sem valor", () => {
  assert.equal(terminationTermsError({ deductions: [{ type: "FIXED", value: " " }] }), TERMINATION_TERMS_INCOMPLETE_MESSAGE)
  assert.equal(terminationTermsError({ deductions: [{ type: "", value: "10" }] }), TERMINATION_TERMS_INCOMPLETE_MESSAGE)
  assert.equal(terminationTermsError({ deductions: [{ type: "FIXED", value: "1.000,00" }] }), null)
  assert.equal(terminationTermsError(null), null)
})

test("valor da dedução em reais vem da API com máscara", () => {
  assert.equal(toTerminationTermsView({ deductions: [{ type: "FIXED", value: "0" }] }).deductions[0].value, "0,00")
})

test("abatimento usa só o principal em aberto da parcela", () => {
  const installment = { amount: "1000.00", paidAmount: "200.00", interest: "50.00", fine: "20.00", discount: "5.00" }
  assert.equal(installmentOutstanding(installment), 800)
  assert.equal(installmentOutstanding({ ...installment, outstandingAmount: "750.00" }), 750)
})

test("oferece o abatimento de saldo credor só em parcela em aberto", () => {
  const common = { onPayInstallment: () => {}, onDeleteInstallment: () => {}, onOffsetCredit: () => {} }
  const open = buildInstallmentActions({ installment: { status: "OPEN" }, ...common })
  const paid = buildInstallmentActions({ installment: { status: "PAID", payments: [] }, ...common })
  assert.ok(open.some((action) => action.key === "credit-offset"))
  assert.ok(!paid.some((action) => action.key === "credit-offset"))
})
