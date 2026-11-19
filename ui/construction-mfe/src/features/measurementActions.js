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
      detail: measurement.externalAccountsPayableShared ? "Título da empreitada" : null,
    }
  }
  if (measurement.status === "approved" && measurement.globalContractId) {
    return {
      tone: "muted",
      label: "Pendente",
      detail: "Título no contrato global",
      title: "OS de contrato por valor global: vincule o título no próprio contrato, na aba Empreitada da obra, em Pagamentos da empreitada.",
    }
  }
  if (measurement.status === "approved" && !measurement.subcontractId && isZeroValueMeasurement(measurement)) {
    return {
      tone: "muted",
      label: "Sem valor",
      detail: "vincule na aba Empreitada",
      title: "Medição de controle sem valor: vincule o título que paga a empreitada na aba Empreitada da obra.",
    }
  }
  if (measurement.status === "approved" && measurement.subcontractId) {
    return {
      tone: "muted",
      label: "Pendente",
      detail: "Título na aba Empreitada",
      title: "Medição de contrato: vincule o título no próprio contrato, na aba Empreitada da obra, em Pagamentos da empreitada.",
    }
  }
  return { tone: "muted", label: "Pendente", detail: null }
}

export const canApproveMeasurementInDialog = (measurement, bridge) => {
  if (!measurement || measurement.reversalPending || !bridge?.canUpdate?.("construction_measurements")) return false
  const selfApproval = Boolean(bridge.canUpdate("construction_measurement_self_approval"))
  if (["draft", "rejected"].includes(measurement.status)) return selfApproval
  if (!["submitted", "in_approval"].includes(measurement.status)) return false
  if (selfApproval) return true
  const userId = bridge.user?.id
  return Boolean(userId) && ![measurement.createdByUserId, measurement.submittedByUserId].includes(userId)
}
