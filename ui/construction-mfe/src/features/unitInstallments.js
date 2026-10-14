export const RECEIPT_ISSUED_HINT =
  "Recibo já emitido: a parcela não pode mais ser alterada, estornada nem excluída."

export const INSTALLMENT_COLUMNS = ["Tipo", "Parcela", "Vencimento", "Valor", "Boleto", "Pago", "Ações"]

export const bankSlipActionLabel = (slip) =>
  slip?.has_pdf === false ? "Imprimir original do boleto" : "Baixar PDF do boleto"

export const hasObservation =(installment) => String(installment.observation ?? "").trim() !== ""

export const observationEditHint = (installment, canUpdate) => installment.hasIssuedReceipt
  ? RECEIPT_ISSUED_HINT
  : canUpdate ? "" : "Seu perfil não pode alterar unidades."

export function buildInstallmentRows(paymentPlan = {}) {
  const adjustments = paymentPlan.adjustments ?? []
  return [
    ...(paymentPlan.installments ?? []).map((installment) => ({
      ...installment,
      typeLabel: "Parcela",
      typeHint: "",
      receivableId: installment.receivableId ?? paymentPlan.receivableId,
      adjustment: null,
    })),
    ...adjustments.flatMap((adjustment, index) => (adjustment.installments ?? []).map((installment) => ({
      ...installment,
      typeLabel: "Aditivo",
      typeHint: [adjustments.length > 1 ? `Aditivo ${index + 1}` : "", adjustment.reason].filter(Boolean).join(" · "),
      receivableId: adjustment.receivableId,
      adjustment,
    }))),
  ].sort((first, second) => String(first.dueDate).localeCompare(String(second.dueDate)))
}

export function buildInstallmentActions({
  installment,
  adjustment,
  onReverseInstallment,
  onPayInstallment,
  onDeleteInstallment,
  onDeleteAdjustment,
  onInstallmentReceipt,
  receiptBusy = false,
  onEditObservation,
  onDownloadBankSlip,
  onViewBankSlips,
  canUpdate = false,
  icons = {},
}) {
  const isPaid = installment.status === "PAID"
  const hasPayments = (installment.payments?.length ?? 0) > 0
  const receiptIssued = Boolean(installment.hasIssuedReceipt)
  const actions = []
  if (onDownloadBankSlip) actions.push({ key: "bank-slip-pdf", label: bankSlipActionLabel(installment.bankSlips?.[0]), icon: icons.FileText, onSelect: onDownloadBankSlip })
  if (onViewBankSlips) actions.push({ key: "bank-slips", label: "Ver boletos", icon: icons.FileText, onSelect: onViewBankSlips })
  if (onEditObservation) {
    actions.push({
      key: "observation",
      label: "Editar observação",
      icon: icons.Pencil,
      disabled: receiptIssued || !canUpdate,
      title: observationEditHint(installment, canUpdate) || undefined,
      onSelect: () => onEditObservation(installment),
    })
  }

  if (onInstallmentReceipt) {
    actions.push({
      key: "receipt",
      label: receiptIssued ? "Baixar recibo" : "Gerar recibo",
      icon: icons.FileText,
      disabled: receiptBusy || (!isPaid && !receiptIssued),
      title:
        !isPaid && !receiptIssued
          ? "O recibo só sai depois que a parcela for baixada."
          : undefined,
      onSelect: () => onInstallmentReceipt(installment),
    })
  }

  if (!isPaid) {
    actions.push({
      key: "pay",
      label: "Baixar parcela",
      icon: icons.CheckCircle,
      onSelect: () => onPayInstallment(installment),
    })
    actions.push({
      key: "delete",
      label: "Excluir parcela",
      icon: icons.Trash2,
      danger: true,
      disabled: receiptIssued,
      title: receiptIssued ? RECEIPT_ISSUED_HINT : undefined,
      onSelect: () => onDeleteInstallment(installment),
    })
  }

  if (hasPayments) {
    actions.push({
      key: "reverse",
      label: "Estornar baixa",
      icon: icons.RotateCcw,
      danger: true,
      disabled: receiptIssued,
      title: receiptIssued ? RECEIPT_ISSUED_HINT : undefined,
      onSelect: () => onReverseInstallment(installment),
    })
  }

  if (adjustment) {
    actions.push({
      key: "delete-adjustment",
      label: "Excluir aditivo inteiro",
      icon: icons.Trash2,
      danger: true,
      onSelect: () => onDeleteAdjustment(adjustment),
    })
  }

  return actions
}

