export const isZeroValueMeasurement = (measurement) =>
  !(Number(measurement.netAmount ?? measurement.measuredAmount ?? 0) > 0)

export const getMeasurementApprovalActions = (measurement) => ({
  canApprove: ["submitted", "in_approval"].includes(measurement.status),
})

export const canLinkPayable = (measurement) =>
  measurement.status === "approved" &&
  !measurement.subcontractId &&
  !measurement.externalAccountsPayableId &&
  !measurement.reversalPending &&
  Boolean(measurement.supplierPersonId) &&
  !isZeroValueMeasurement(measurement)

export const newMeasurementPayablePath = (measurement) =>
  "/accounts-payable/new?" +
  new URLSearchParams({
    measurement_id: measurement.id,
    return_to: "/construction?" + new URLSearchParams({ project_id: measurement.projectId, tab: "units" }),
  })

const PAYABLE_STATUS_LABELS = {
  OPEN: "Em aberto",
  PAID: "Pago",
  PARTIALLY_PAID: "Parcial",
  CANCELED: "Cancelado",
  ARCHIVED: "Arquivado",
  DELETED: "Excluído",
}

export const payableStatusLabel = (status) => PAYABLE_STATUS_LABELS[status] ?? status ?? "-"

export const measurementPayableBadge = (measurement) => {
  if (measurement.externalAccountsPayableId) {
    return {
      tone: "success",
      label: "Vinculado",
      detail: measurement.externalAccountsPayableShared ? "DNF da empreitada" : null,
    }
  }
  if (measurement.status === "approved" && measurement.globalContractId) {
    return {
      tone: "muted",
      label: "Pendente",
      detail: "DNF no contrato global",
      title: "OS de contrato por valor global: vincule a DNF no próprio contrato, na aba Empreitada da obra, em DNF das medições do contrato.",
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
  if (measurement.status === "approved" && measurement.subcontractId) {
    return {
      tone: "muted",
      label: "Pendente",
      detail: "DNF na aba Empreitada",
      title: "Medição de contrato: vincule a DNF no próprio contrato, na aba Empreitada da obra, em DNF das medições do contrato.",
    }
  }
  return { tone: "muted", label: "Pendente", detail: null }
}
