import { useEffect, useRef, useState } from "react"
import { bankSlipErpOperation } from "../services/constructionApi.js"
import {
  ACTIVE_BANK_SLIP_STATUSES,
  CANCELABLE_BANK_SLIP_STATUSES,
  RETRYABLE_BANK_SLIP_STATUSES,
  isBankSlipBatchRunning,
  toggleSelectionPage,
} from "./UnitBankSlips.jsx"
import { brazilTodayISO } from "../utils/brazilDate.js"
import styles from "../App.module.css"

const CANCEL_MESSAGE = "Solicitar a baixa no banco? O boleto continua ativo até o Sicredi confirmar. "
  + "A parcela continua em aberto."

const latestSlipIn = (row, statuses) => (statuses.includes(row.bankSlips?.[0]?.status) ? row.bankSlips[0] : null)
export const cancelableBankSlip = (row) =>
  row.bankSlips?.find((slip) => CANCELABLE_BANK_SLIP_STATUSES.includes(slip.status)) ?? null
export const reconcilableBankSlip = (row) => latestSlipIn(row, ACTIVE_BANK_SLIP_STATUSES)
export const retryableBankSlip = (row) => latestSlipIn(row, RETRYABLE_BANK_SLIP_STATUSES)

export const bankSlipGenerationReason = (row) => {
  if (row.status === "OVERDUE" || row.dueDate < brazilTodayISO()) {
    return "Parcela vencida: não é permitido gerar boleto."
  }
  if (!["OPEN", "OVERDUE"].includes(row.status)) return "Parcela quitada ou cancelada: não se emite boleto novo."
  if (Number(row.outstandingAmount ?? row.amount) <= 0) return "A parcela precisa ter saldo positivo."
  if ((row.bankSlips ?? []).some((slip) => ACTIVE_BANK_SLIP_STATUSES.includes(slip.status))) {
    return "A parcela já possui boleto ativo."
  }
  return ""
}

export function useUnitBankSlipOperations(bridge, unitId, onChanged) {
  const [selected, setSelected] = useState(new Map())
  const [issueRows, setIssueRows] = useState(null)
  const [cancelSlip, setCancelSlip] = useState(null)
  const [busy, setBusy] = useState(false)
  const [batch, setBatch] = useState(null)
  const changed = useRef(onChanged)
  const canCreate = Boolean(bridge?.canCreate?.("bank_slip"))
  const canUpdate = Boolean(bridge?.canUpdate?.("bank_slip"))
  useEffect(() => { changed.current = onChanged }, [onChanged])
  useEffect(() => {
    setSelected(new Map()); setIssueRows(null); setCancelSlip(null); setBatch(null)
  }, [unitId, bridge?.companyContext?.companyId])
  useEffect(() => {
    if (!batch?.id || !isBankSlipBatchRunning(batch)) return undefined
    let alive = true
    const timer = setInterval(() => {
      bankSlipErpOperation({ bridge, path: `/batches/${batch.id}`, method: "GET" })
        .then((data) => {
          if (!alive) return
          setBatch(data)
          if (!isBankSlipBatchRunning(data)) changed.current?.()
        })
        .catch((error) => { if (alive) { bridge?.feedback?.error?.(error.message); clearInterval(timer) } })
    }, 3000)
    return () => { alive = false; clearInterval(timer) }
  }, [batch, bridge])
  const operate = async (slip, action) => {
    setBusy(true)
    try {
      const result = await bankSlipErpOperation({
        bridge, path: `/${slip.id}/${action}`, body: { construction_unit_id: unitId },
      })
      if (result.reconciliation_error) bridge?.feedback?.error?.(result.reconciliation_error)
      else bridge?.feedback?.success?.(action === "cancel" && result.cancel_requested
        ? "Exclusão solicitada. Aguarde a confirmação do banco." : "Situação do boleto atualizada.")
      changed.current?.()
    } catch (error) { bridge?.feedback?.error?.(error.message) }
    finally { setBusy(false); setCancelSlip(null) }
  }
  return { bridge, unitId, canCreate, canUpdate, selected, issueRows, setIssueRows, cancelSlip, setCancelSlip,
    clearSelection: () => setSelected(new Map()),
    busy, batch, setBatch, operate,
    toggle: (row) => setSelected((current) => {
      const next = new Map(current)
      if (next.has(row.id)) next.delete(row.id)
      else if (next.size < 200 && !bankSlipGenerationReason(row)) next.set(row.id, row)
      return next
    }),
    entries: (rows) => rows.filter((row) => !bankSlipGenerationReason(row)).map((row) => [row.id, row]),
    selectPage: (entries) => setSelected((current) => toggleSelectionPage(current, entries)),
    completed: (result) => {
      setIssueRows(null); setSelected(new Map())
      if (result?.items) setBatch(result)
      changed.current?.()
    },
    retryBatch: async () => {
      try { setBatch(await bankSlipErpOperation({ bridge, path: `/batches/${batch.id}/retry` })) }
      catch (error) { bridge?.feedback?.error?.(error.message) }
    },
  }
}

export function UnitBankSlipOperationDialogs({ state }) {
  if (state.issueRows) {
    const IssueDialog = state.bridge?.components?.BankSlipIssueDialog
    if (IssueDialog) return <IssueDialog
      items={state.issueRows.map((row) => ({ id: row.id, unit_id: state.unitId, due_date: row.dueDate,
        status: row.status }))}
      onClose={() => state.setIssueRows(null)} onCompleted={state.completed} />
    return <UnitBankSlipIssueDialog state={state} />
  }
  if (!state.cancelSlip) return null
  const cancel = () => state.setCancelSlip(null)
  const confirm = () => state.operate(state.cancelSlip, "cancel")
  const ConfirmDialog = state.bridge?.components?.ConfirmDialog
  if (ConfirmDialog) return <ConfirmDialog isOpen variant="danger" title="Excluir boleto" loading={state.busy}
    message={CANCEL_MESSAGE} confirmLabel="Excluir boleto" onCancel={cancel} onConfirm={confirm} />
  return <div className={styles.modalOverlay} role="presentation"><section className={styles.modalCard}
    role="dialog" aria-modal="true" aria-label="Excluir boleto">
    <header className={styles.modalHeader}><h3>Excluir boleto</h3></header>
    <div className={styles.modalBody}><p>{CANCEL_MESSAGE}</p></div>
    <footer className={styles.modalFooter}>
      <button type="button" className={styles.secondaryButton} disabled={state.busy} onClick={cancel}>Cancelar</button>
      <button type="button" className={styles.dangerButton} disabled={state.busy} onClick={confirm}>
        Excluir boleto</button>
    </footer>
  </section></div>
}

function UnitBankSlipIssueDialog({ state }) {
  const [configs, setConfigs] = useState([])
  const [account, setAccount] = useState("")
  const [busy, setBusy] = useState(true)
  useEffect(() => {
    let alive = true
    bankSlipErpOperation({ bridge: state.bridge, path: "/settings", method: "GET" }).then((data) => {
      if (!alive) return
      const active = data.items.filter((config) => config.is_active)
      setConfigs(active)
      setAccount(active[0]?.company_bank_account_id ?? "")
    }).catch((error) => { if (alive) state.bridge?.feedback?.error?.(error.message) })
      .finally(() => { if (alive) setBusy(false) })
    return () => { alive = false }
  }, [state.bridge])
  const generate = async (event) => {
    event.preventDefault()
    if (!account || busy || !state.canCreate || state.issueRows.some((row) => bankSlipGenerationReason(row))) return
    setBusy(true)
    try {
      const items = state.issueRows.map((row) => ({ installment_id: row.id, company_bank_account_id: account,
        construction_unit_id: state.unitId }))
      const result = await bankSlipErpOperation({
        bridge: state.bridge,
        path: items.length === 1 ? "/issue" : "/batches",
        body: items.length === 1 ? items[0] : { items },
      })
      if (result.reconciliation_error) state.bridge?.feedback?.error?.(result.reconciliation_error)
      else state.bridge?.feedback?.success?.(items.length === 1 ? "Boleto gerado." : "Lote enfileirado.")
      state.completed(result)
    } catch (error) { state.bridge?.feedback?.error?.(error.message) }
    finally { setBusy(false) }
  }
  return <div className={styles.modalOverlay} role="presentation"><section className={styles.modalCard}
    role="dialog" aria-modal="true" aria-label="Gerar boletos">
    <header className={styles.modalHeader}><h3>Gerar boletos ({state.issueRows.length})</h3></header>
    <form onSubmit={generate}><div className={styles.modalBody}>
      {busy && <p role="status">Processando...</p>}
      {!busy && !configs.length && <p>Configure a cobrança da conta bancária em Empresas &gt; Financeiro.</p>}
      <label className={styles.filterControl}>Conta de cobrança *
        <select required disabled={busy} value={account} onChange={(event) => setAccount(event.target.value)}>
          <option value="">Selecione</option>
          {configs.map((config) => <option key={config.id} value={config.company_bank_account_id}>
            {config.account_label}</option>)}
        </select></label>
      <p>O boleto usa o vencimento da parcela. Não é permitido gerar boletos de parcelas vencidas.
        Gerar não baixa a parcela.</p>
    </div><footer className={styles.modalFooter}>
      <button type="button" className={styles.secondaryButton} disabled={busy}
        onClick={() => state.setIssueRows(null)}>Cancelar</button>
      <button type="submit" className={styles.primaryButton}
        disabled={busy || !account || state.issueRows.some((row) => bankSlipGenerationReason(row))}>
        Gerar boletos</button>
    </footer></form>
  </section></div>
}
