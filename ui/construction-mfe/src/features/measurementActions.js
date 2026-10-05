export const getMeasurementApprovalActions = (measurement) => {
  const canRetryIntegration = measurement.status === "approved" && !measurement.externalAccountsPayableId
  const canApprove = ["submitted", "in_approval"].includes(measurement.status) || canRetryIntegration
  return { canApprove, canRetryIntegration }
}
