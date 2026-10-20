let businessTimezone = "America/Sao_Paulo"

export const setBusinessTimezone = (value) => { businessTimezone = value || "America/Sao_Paulo" }

export const brazilTodayISO = () => {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: businessTimezone, year: "numeric", month: "2-digit", day: "2-digit",
  })
  const parts = Object.fromEntries(formatter.formatToParts(new Date()).map(({ type, value }) => [type, value]))
  return `${parts.year}-${parts.month}-${parts.day}`
}

export const formatBusinessDate = (value) => {
  if (!value) return "-"
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.split("-").reverse().join("/")
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? "-" : new Intl.DateTimeFormat("pt-BR", { timeZone: businessTimezone }).format(parsed)
}

export const getBusinessTimezone = () => businessTimezone
