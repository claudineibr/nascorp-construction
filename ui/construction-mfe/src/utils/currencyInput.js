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

const brlFormatter = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" })

export const formatBRL = (value) => (value == null || value === "" ? "-" : brlFormatter.format(Number(value)))

export { currencyDecimal }
