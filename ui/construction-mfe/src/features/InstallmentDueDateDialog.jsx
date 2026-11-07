import { useId, useState } from "react"
import { UnitBankSlipDialogFrame } from "./UnitBankSlipsDialog.jsx"
import { installmentOutstanding } from "./unitInstallments.js"
import { updateConstructionUnitInstallment } from "../services/constructionApi.js"
import styles from "./InstallmentDueDateDialog.module.css"

export function InstallmentDueDateDialog({ bridge, unitId, installment, onClose, onSaved }) {
  const formId = useId()
  const [dueDate, setDueDate] = useState("")
  const [reason, setReason] = useState("")
  const [saving, setSaving] = useState(false)
  const valid = dueDate && dueDate !== installment.dueDate && reason.trim().length >= 3
  const close = () => { if (!saving) onClose() }
  const submit = async (event) => {
    event.preventDefault()
    if (saving || !valid || !bridge?.canUpdate?.("construction_units")) return
    setSaving(true)
    try {
      await updateConstructionUnitInstallment({ bridge, unitId,
        installmentNumber: installment.installmentNumber, receivableId: installment.receivableId,
        changes: { renegotiation: { due_date: dueDate, expected_due_date: installment.dueDate,
          expected_outstanding_amount: installmentOutstanding(installment), reason: reason.trim() } } })
      await onSaved()
      onClose()
      bridge?.feedback?.success?.("Vencimento alterado com sucesso.")
    } catch (error) { bridge?.feedback?.error?.(error.message ?? "Não foi possível alterar o vencimento.") }
    finally { setSaving(false) }
  }

  return <UnitBankSlipDialogFrame bridge={bridge} title="Alterar vencimento" dialogMaxWidth={480} onClose={close}
    footer={<div className={styles.footer}>
      <button type="button" className={styles.secondaryButton} disabled={saving} onClick={close}>Cancelar</button>
      <button type="submit" form={formId} className={styles.primaryButton} disabled={saving || !valid}>
        {saving ? "Salvando..." : "Salvar"}
      </button>
    </div>}>
    <form id={formId} className={styles.form} onSubmit={submit}>
      <label className={styles.field}>Nova data *
        <input type="date" required value={dueDate} disabled={saving}
          onChange={(event) => setDueDate(event.target.value)} />
      </label>
      <label className={styles.field}>Motivo *
        <textarea required minLength={3} maxLength={1000} rows={3} value={reason} disabled={saving}
          placeholder="Informe o motivo da alteração (mínimo de 3 caracteres)"
          onChange={(event) => setReason(event.target.value)} />
      </label>
    </form>
  </UnitBankSlipDialogFrame>
}
