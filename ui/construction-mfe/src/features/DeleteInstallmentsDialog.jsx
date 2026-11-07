import { useId, useState } from "react"
import { UnitBankSlipDialogFrame } from "./UnitBankSlipsDialog.jsx"
import { deleteConstructionUnitInstallment } from "../services/constructionApi.js"
import appStyles from "../App.module.css"
import styles from "./InstallmentDueDateDialog.module.css"

export function DeleteInstallmentsDialog({ bridge, unitId, installments, onClose, onDone }) {
  const formId = useId()
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(0)
  const close = () => { if (!busy) onClose() }
  const submit = async (event) => {
    event?.preventDefault()
    if (busy || reason.trim().length < 10) return
    setBusy(true)
    const failures = []
    let deleted = 0
    for (const [index, installment] of installments.entries()) {
      setProgress(index + 1)
      try {
        await deleteConstructionUnitInstallment({ bridge, unitId,
          installmentNumber: installment.installmentNumber, receivableId: installment.receivableId,
          reason: reason.trim() })
        deleted += 1
      } catch (error) {
        failures.push(`${installment.typeLabel ?? "Parcela"} ${installment.installmentNumber}: ${error.message}`)
      }
    }
    try { await onDone() }
    catch (error) { failures.push(`Atualização da lista: ${error.message}`) }
    setBusy(false)
    onClose()
    const message = `${deleted} de ${installments.length} parcela(s) excluída(s).`
    if (failures.length) bridge?.feedback?.warning?.(`${message} Falhas ou exclusões não confirmadas: ${failures.join("; ")}. Confira a lista atualizada antes de repetir.`)
    else bridge?.feedback?.success?.(`${message} Os administradores da empresa foram notificados.`)
  }

  const ConfirmDialog = bridge?.components?.ConfirmDialog
  if (ConfirmDialog) return <ConfirmDialog isOpen variant="danger"
    title={`Excluir ${installments.length} parcela(s)`}
    message="Confirma excluir as parcelas selecionadas e desfazer seus lançamentos? Havendo boleto, a parcela só será excluída após a confirmação da baixa no banco. Se a baixa falhar ou ficar pendente, a parcela será preservada. O motivo será auditado e os administradores da empresa serão notificados."
    reasonLabel="Motivo da exclusão *" reasonValue={reason} onReasonChange={(value) => { if (!busy) setReason(value) }}
    reasonPlaceholder="Descreva o motivo (mínimo de 10 caracteres)" reasonMinLength={10} reasonMaxLength={1000}
    confirmLabel="Confirmar exclusão" confirmDisabled={reason.trim().length < 10} loading={busy}
    onCancel={close} onConfirm={submit}>
    {busy && <p role="status">Processando {progress}/{installments.length}. Aguarde a confirmação do banco.</p>}
  </ConfirmDialog>

  return <UnitBankSlipDialogFrame bridge={bridge} title={`Excluir ${installments.length} parcela(s)`}
    onClose={close} dialogMaxWidth={560} footer={<div className={styles.footer}>
      <button type="button" className={styles.secondaryButton} disabled={busy} onClick={close}>Cancelar</button>
      <button type="submit" form={formId} className={`${appStyles.secondaryButton} ${appStyles.dangerButton}`}
        disabled={busy || reason.trim().length < 10}>
        {busy ? `Processando ${progress}/${installments.length}...` : "Confirmar exclusão"}
      </button>
    </div>}>
    <form id={formId} className={styles.form} onSubmit={submit}>
      <p>Confirma excluir as parcelas selecionadas? Os lançamentos contábeis serão desfeitos.
        Havendo boleto, a parcela só será excluída após a confirmação da baixa no banco.
        Se a baixa falhar ou continuar pendente, a parcela será preservada.</p>
      <p>A exclusão e o motivo ficarão na auditoria. Os administradores da empresa receberão uma notificação.</p>
      <label className={styles.field}>Motivo da exclusão *
        <textarea required minLength={10} maxLength={1000} rows={3} value={reason} disabled={busy}
          placeholder="Descreva o motivo (mínimo de 10 caracteres)"
          onChange={(event) => setReason(event.target.value)} />
      </label>
      {busy && <p role="status">Aguarde a confirmação do banco e a conclusão de cada parcela.</p>}
    </form>
  </UnitBankSlipDialogFrame>
}
