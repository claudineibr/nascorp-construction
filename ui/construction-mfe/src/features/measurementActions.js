export const isZeroValueMeasurement = (measurement) =>
  !(Number(measurement.netAmount ?? measurement.measuredAmount ?? 0) > 0)

export const getMeasurementApprovalActions = (measurement) => {
  const canRetryIntegration =
    measurement.status === "approved" &&
    !measurement.externalAccountsPayableId &&
    Boolean(measurement.approvedAt) &&
    !(!measurement.subcontractId && isZeroValueMeasurement(measurement))
  const canApprove = ["submitted", "in_approval"].includes(measurement.status) || canRetryIntegration
  return { canApprove, canRetryIntegration }
}

export const canLinkPayable = (measurement) =>
  measurement.status === "approved" &&
  !measurement.externalAccountsPayableId &&
  Boolean(measurement.supplierPersonId) &&
  !isZeroValueMeasurement(measurement)

const PAYABLE_STATUS_LABELS = {
  OPEN: "Em aberto",
  OVERDUE: "Vencido",
  PAID: "Pago",
  PARTIALLY_PAID: "Parcial",
  CANCELED: "Cancelado",
  ARCHIVED: "Arquivado",
  DELETED: "Excluído",
}

export const payableStatusLabel = (status) => PAYABLE_STATUS_LABELS[status] ?? status ?? "—"

export const measurementPayableBadge = (measurement) => {
  if (measurement.externalAccountsPayableId) {
    const status = payableStatusLabel(measurement.externalAccountsPayableStatus)
    return {
      tone: "success",
      label: "Vinculado",
      detail: measurement.externalAccountsPayableShared ? `DNF da empreitada · ${status}` : status,
    }
  }
  if (measurement.status === "approved" && !measurement.subcontractId && isZeroValueMeasurement(measurement)) {
    return {
      tone: "muted",
      label: "Sem valor",
      detail: "vincule na aba Empreitada",
      title: "Medição de controle sem valor: vincule a DNF que paga a empreitada na aba Empreitada da obra.",
    }
  }
  return { tone: "muted", label: "Pendente", detail: null }
}
