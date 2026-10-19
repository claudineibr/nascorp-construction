const UNIT_TYPES = Object.freeze([
  { value: "casa", label: "Casa" },
  { value: "apartamento", label: "Apartamento" },
  { value: "lote", label: "Lote" },
  { value: "sala_comercial", label: "Sala comercial" },
  { value: "loja", label: "Loja" },
  { value: "vaga_de_garagem", label: "Vaga de garagem" },
])

const normalizedType = (value) => {
  const name = String(value ?? "").trim().toLocaleLowerCase("pt-BR").replace(/\s+/g, "_")
  return name === "moradia" ? "casa" : name
}

export const formatUnitType = (value) =>
  UNIT_TYPES.find((option) => option.value === normalizedType(value))?.label || String(value ?? "")

export const unitTypeOptions = (currentValue) => {
  if (!currentValue) return UNIT_TYPES
  const normalized = normalizedType(currentValue)
  if (UNIT_TYPES.some((option) => option.value === normalized)) {
    return UNIT_TYPES.map((option) => option.value === normalized ? { ...option, value: currentValue } : option)
  }
  return [...UNIT_TYPES, { value: currentValue, label: `${currentValue} (tipo existente)` }]
}
