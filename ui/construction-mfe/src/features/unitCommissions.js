const COMMISSION_STATUS_LABELS = {
  open: "Em aberto",
  overdue: "Vencida",
  paid: "Paga",
}

export const commissionStatusLabel = (status) => COMMISSION_STATUS_LABELS[status] ?? status ?? "-"
