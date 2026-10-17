export const maskPhone = (value = "") => {
  const digits = String(value).replace(/\D/g, "").slice(0, 11)
  if (!digits) return ""
  if (digits.length < 3) return `(${digits}`
  if (digits.length < 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`
  const split = digits.length > 10 ? 7 : 6
  return `(${digits.slice(0, 2)}) ${digits.slice(2, split)}-${digits.slice(split)}`
}
