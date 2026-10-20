export const isZeroValueMeasurement = (measurement) =>
  !(Number(measurement.netAmount ?? measurement.measuredAmount ?? 0) > 0)

export const getMeasurementApprovalActions = (measurement) => ({
  canApprove: ["submitted", "in_approval"].includes(measurement.status),
})

export const canLinkPayable = (measurement) =>
  measurement.status === "approved" &&
  !measurement.externalAccountsPayableId &&
  !measurement.reversalPending &&
  Boolean(measurement.supplierPersonId) &&
  !isZeroValueMeasurement(measurement)

const PAYABLE_STATUS_LABELS = {
  OPEN: "Em aberto",
  PAID: "Pago",
  PARTIALLY_PAID: "Parcial",
  CANCELED: "Cancelado",
  ARCHIVED: "Arquivado",
  DELETED: "Excluído",
}

export const payableStatusLabel = (status) => PAYABLE_STATUS_LABELS[status] ?? status ?? "—"

export const measurementPayableBadge = (measurement) => {
  if (measurement.externalAccountsPayableId) {
    return {
      tone: "success",
      label: "Vinculado",
      detail: measurement.externalAccountsPayableShared ? "DNF da empreitada" : null,
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
