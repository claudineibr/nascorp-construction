import { currencyCents, currencyDecimal } from "./procurementAmounts.js"

export const formatCurrencyInput = (value) => {
  const digits = String(value ?? "").replace(/\D/g, "")
  if (!digits) return ""
  return (Number(currencyCents(digits)) / 100).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export const currencyFromNumber = (value) => {
  const parsed = Number(value ?? 0)
  return (Number.isFinite(parsed) ? parsed : 0).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export const currencyNumber = (value) => Number(currencyDecimal(value))

export { currencyDecimal }
