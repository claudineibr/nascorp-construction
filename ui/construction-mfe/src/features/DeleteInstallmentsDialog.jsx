import { useEffect, useId, useMemo, useState } from "react"
import { UnitBankSlipDialogFrame } from "./UnitBankSlipsDialog.jsx"
import { deleteConstructionUnitInstallment } from "../services/constructionApi.js"
import { installmentRequiresReversal } from "./unitInstallments.js"
import { formatBankSlipMoney } from "./UnitBankSlips.jsx"
import { formatBusinessDate } from "../utils/brazilDate.js"
import appStyles from "../App.module.css"
import styles from "./InstallmentDueDateDialog.module.css"

const previewKey = (item) => `${item.receivableId}:${item.installmentNumber}`
const itemFailure = (item, message) => ({
  typeLabel: item.typeLabel ?? "Parcela", number: item.installmentNumber, message,
})
const formatFailureSummary = (failures) => {
  const list = new Intl.ListFormat("pt-BR", { style: "long", type: "conjunction" })
  const groups = new Map()
  for (const failure of failures) {
    const message = (failure.message || "Não foi possível confirmar a exclusão").trim().replace(/[.;\s]+$/, "")
    if (!groups.has(message)) groups.set(message, { targets: new Map(), labels: new Set() })
    const group = groups.get(message)
    if (failure.number == null) group.labels.add(failure.label)
    else {
      if (!group.targets.has(failure.typeLabel)) group.targets.set(failure.typeLabel, [])
      group.targets.get(failure.typeLabel).push(failure.number)
    }
  }
  return [...groups].map(([message, group]) => {
    const labels = [...group.labels]
    for (const [type, numbers] of group.targets) {
      const label = numbers.length === 1 ? type : type === "Aditivo" ? "Aditivos" : "Parcelas"
      labels.push(`${label} ${list.format(numbers.sort((a, b) => a - b).map(String))}`)
    }
    return `${list.format(labels)}: ${message}.`
  }).join(" ")
}

export function DeleteInstallmentsDialog({ bridge, unitId, installments, onClose, onDone }) {
  const formId = useId()
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(0)
  const [notificationBatchId] = useState(() => crypto.randomUUID())
  const [previews, setPreviews] = useState({})
  const paidItems = useMemo(() => installments.filter(installmentRequiresReversal), [installments])
  const openItems = useMemo(() => installments.filter((item) => !installmentRequiresReversal(item)), [installments])
  const [previewLoading, setPreviewLoading] = useState(paidItems.length > 0)
  useEffect(() => {
    let current = true
    setPreviews({})
    if (!paidItems.length) { setPreviewLoading(false); return undefined }
    setPreviewLoading(true)
    const load = async () => {
      try {
        if (!bridge?.canSpecial?.("receivable_paid_installment_delete") || !bridge?.previewFinancialDeletionBatch) {
          throw new Error("A exclusão de parcelas com recebimentos exige autorização especial e o módulo atualizado.")
        }
        const response = await bridge.previewFinancialDeletionBatch({ unit_id: unitId,
          items: paidItems.map((item) => ({ title_id: item.receivableId, installment_number: item.installmentNumber })) })
        if (current) setPreviews(Object.fromEntries(response.items.map((item) => [
          `${item.title_id}:${item.installment_number}`, { ...item, request_key: crypto.randomUUID() },
        ])))
      } catch (error) {
        if (current) setPreviews(Object.fromEntries(paidItems.map((item) => [previewKey(item), { message: error.message }])))
      } finally { if (current) setPreviewLoading(false) }
    }
    load()
    return () => { current = false }
  }, [bridge, unitId, paidItems])
  const eligiblePaid = paidItems.filter((item) => {
    const result = previews[previewKey(item)]
    return result?.preview && !result.preview.blockers.length && !result.message
  })
  const confirmDisabled = previewLoading || reason.trim().length < 10 || (!openItems.length && !eligiblePaid.length)
  const close = () => { if (!busy) onClose() }
  const submit = async (event) => {
    event?.preventDefault()
    if (busy || confirmDisabled) return
    setBusy(true)
    const failures = []
    let deleted = 0
    let unconfirmed = 0
    for (const item of paidItems) {
      const result = previews[previewKey(item)]
      if (!eligiblePaid.includes(item)) failures.push(itemFailure(item, result?.message
        || result?.preview?.blockers.join(" ") || "Prévia indisponível; atualize e confira novamente."))
    }
    if (eligiblePaid.length) {
      setProgress(paidItems.length)
      try {
        const response = await bridge.executeFinancialDeletionBatch({ unit_id: unitId,
          notification_batch_id: notificationBatchId, reason: reason.trim(),
          items: eligiblePaid.map((item) => ({ title_id: item.receivableId, installment_number: item.installmentNumber,
            preview_token: previews[previewKey(item)].preview.preview_token,
            request_key: previews[previewKey(item)].request_key })) })
        for (const result of response.items) {
          if (result.status === "COMPLETED") deleted += 1
          else {
            const item = eligiblePaid.find((row) => row.receivableId === result.title_id
              && row.installmentNumber === result.installment_number)
            failures.push(itemFailure(item ?? { installmentNumber: result.installment_number }, result.message))
          }
        }
      } catch (error) {
        unconfirmed += eligiblePaid.length
        failures.push({ label: "Parcelas com recebimentos", message: error.message })
      }
    }
    for (const [index, installment] of openItems.entries()) {
      setProgress(paidItems.length + index + 1)
      try {
        await deleteConstructionUnitInstallment({ bridge, unitId,
          installmentNumber: installment.installmentNumber, receivableId: installment.receivableId,
          reason: reason.trim(), notificationBatchId })
        deleted += 1
      } catch (error) {
        unconfirmed += 1
        failures.push(itemFailure(installment, error.message))
      }
    }
    try { await onDone() }
    catch (error) { failures.push({ label: "Atualização da lista", message: error.message }) }
    setBusy(false)
    onClose()
    const message = `${deleted} de ${installments.length} exclusões confirmadas.`
    const pendingMessage = unconfirmed
      ? " Algumas exclusões ficaram sem confirmação. Confira a lista atualizada antes de repetir." : ""
    if (failures.length) bridge?.feedback?.warning?.(`${message} ${formatFailureSummary(failures)}${pendingMessage}`)
    else bridge?.feedback?.success?.(`${message} Os administradores da empresa receberam um único aviso com o resumo.`)
  }

  const previewDetails = paidItems.length > 0 && <div className={styles.form}>
    <p>Parcelas com recebimentos exigem estornos financeiros e contábeis. Os recibos serão cancelados e preservados
      no histórico. Esta operação não devolve dinheiro no banco. Parcelas bloqueadas serão preservadas.</p>
    {previewLoading ? <p role="status">Conferindo os vínculos das parcelas com recebimentos...</p> : <ul>
      {paidItems.map((item) => {
        const result = previews[previewKey(item)]
        const preview = result?.preview
        return <li key={previewKey(item)}>
          <strong>{item.typeLabel ?? "Parcela"} {item.installmentNumber}</strong>
          {preview ? <>
            <p>Valor: {formatBankSlipMoney(preview.amount)}. Recebido: {formatBankSlipMoney(preview.paid_amount)}.
              Lançamentos a estornar: {preview.accounting_entry_ids.length}.
              Data contábil: {formatBusinessDate(preview.accounting_date)}.</p>
            {preview.receipt_numbers.length > 0 && <p>Recibos a cancelar: {preview.receipt_numbers.join(", ")}.</p>}
            {preview.blockers.length > 0 && <p>Bloqueada: {preview.blockers.join(" ")}</p>}
          </> : <p>Bloqueada: {result?.message ?? "Prévia indisponível."}</p>}
        </li>
      })}
    </ul>}
  </div>
  const ConfirmDialog = bridge?.components?.ConfirmDialog
  if (ConfirmDialog) return <ConfirmDialog isOpen variant="danger"
    title={`Excluir ${installments.length} parcela(s)`}
    message="Confirma excluir as parcelas selecionadas e desfazer seus lançamentos? Havendo boleto, a parcela só será excluída após a confirmação da baixa no banco. Se a baixa falhar ou ficar pendente, a parcela será preservada. O motivo será auditado e os administradores da empresa receberão um único aviso com o resumo das parcelas excluídas."
    reasonLabel="Motivo da exclusão *" reasonValue={reason} onReasonChange={(value) => { if (!busy) setReason(value) }}
    reasonPlaceholder="Descreva o motivo (mínimo de 10 caracteres)" reasonMinLength={10} reasonMaxLength={1000}
    confirmLabel="Confirmar exclusão" confirmDisabled={confirmDisabled} loading={busy}
    onCancel={close} onConfirm={submit}>
    {previewDetails}
    {busy && <p role="status">Processando {progress}/{installments.length}. Aguarde a confirmação do banco.</p>}
  </ConfirmDialog>

  return <UnitBankSlipDialogFrame bridge={bridge} title={`Excluir ${installments.length} parcela(s)`}
    onClose={close} dialogMaxWidth={560} footer={<div className={styles.footer}>
      <button type="button" className={styles.secondaryButton} disabled={busy} onClick={close}>Cancelar</button>
      <button type="submit" form={formId} className={`${appStyles.secondaryButton} ${appStyles.dangerButton}`}
        disabled={busy || confirmDisabled}>
        {busy ? `Processando ${progress}/${installments.length}...` : "Confirmar exclusão"}
      </button>
    </div>}>
    <form id={formId} className={styles.form} onSubmit={submit}>
      <p>Confirma excluir as parcelas selecionadas? Os lançamentos contábeis serão desfeitos.
        Havendo boleto, a parcela só será excluída após a confirmação da baixa no banco.
        Se a baixa falhar ou continuar pendente, a parcela será preservada.</p>
      <p>A exclusão e o motivo ficarão na auditoria. Os administradores da empresa receberão um único aviso com o resumo das parcelas excluídas.</p>
      {previewDetails}
      <label className={styles.field}>Motivo da exclusão *
        <textarea required minLength={10} maxLength={1000} rows={3} value={reason} disabled={busy}
          placeholder="Descreva o motivo (mínimo de 10 caracteres)"
          onChange={(event) => setReason(event.target.value)} />
      </label>
      {busy && <p role="status">Aguarde a confirmação do banco e a conclusão de cada parcela.</p>}
    </form>
  </UnitBankSlipDialogFrame>
}
