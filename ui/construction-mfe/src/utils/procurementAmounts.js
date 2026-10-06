export const currencyCents = (value) => BigInt(String(value ?? "").replace(/\D/g, "") || "0")

export const quantityUnits = (value) => {
  const match = /^\+?(\d+(?:\.\d*)?|\.\d+)(?:[eE]([+-]?\d+))?$/.exec(String(value ?? "").trim())
  if (!match) return null
  const exponent = Number(match[2] ?? 0)
  if (!Number.isInteger(exponent) || Math.abs(exponent) > 30) return null
  const [whole, fraction = ""] = match[1].split(".")
  const digits = BigInt((whole || "0") + fraction)
  const scale = 4 + exponent - fraction.length
  let units
  if (scale >= 0) {
    units = digits * 10n ** BigInt(scale)
  } else {
    const divisor = 10n ** BigInt(-scale)
    if (digits % divisor !== 0n) return null
    units = digits / divisor
  }
  return units > 0n && units <= 99999999999999n ? units : null
}

export const procurementLineCents = (item) => {
  const units = quantityUnits(item.quantity)
  if (units === null) return 0n
  return (units * currencyCents(item.unitPrice) + 5000n) / 10000n
}

export const procurementSubtotalCents = (items = []) => items.reduce((sum, item) => sum + procurementLineCents(item), 0n)

export const currencyDecimal = (value) => {
  const digits = currencyCents(value).toString().padStart(3, "0")
  return `${digits.slice(0, -2)}.${digits.slice(-2)}`
}
