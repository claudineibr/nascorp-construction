export const measurementPurpose = (measurement) => measurement.subcontractId
  ? "CONTRACT"
  : measurement.purpose || (Number(measurement.grossAmount ?? measurement.measuredAmount ?? 0) === 0 ? "CONTROL" : "SERVICE")

export const measurementEditable = (measurement) => ["draft", "rejected"].includes(measurement.status)

export const measurementCancelled = (measurement) => measurement.status === "rejected" && !measurement.rejectedAt

export const measurementItemLabel = (item) =>
  item.serviceTemplateName && item.serviceTemplateName.toLowerCase() !== item.description.toLowerCase()
    ? `${item.serviceTemplateName} · ${item.description}`
    : item.description

export const inspectionEligibleForBulk = (inspection) => !inspection.roundsCount && !inspection.requiresComment

export const measurementInspectionBlockers = (measurement, items, unit = null) => {
  const blockers = []
  if (unit && !unit.analyticCostCenterId) blockers.push("Vincule um centro de custo analítico à unidade antes de enviar.")
  if (!measurement.unitId) blockers.push("Selecione a unidade.")
  if (!measurement.schedulePhaseId) blockers.push("Selecione a etapa.")
  if (!measurement.supplierPersonId) blockers.push("Informe o fornecedor antes de enviar.")
  if (!items.length) blockers.push("Inclua os serviços executados e suas inspeções.")
  const missing = items.filter((item) => !item.inspections?.length)
  if (missing.length) blockers.push(`Serviços sem FVS: ${missing.map(measurementItemLabel).join(", ")}.`)
  if (items.some((item) => item.inspections?.some((line) => !line.roundsCount || line.status === "non_compliant"))) {
    blockers.push("Conclua as verificações pendentes e reinspeções.")
  }
  return blockers
}
