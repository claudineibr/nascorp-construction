import { useEffect, useRef, useState } from "react"
import { FileText } from "lucide-react"
import { downloadErpPdf, printErpBankSlips } from "../services/constructionApi.js"
import { bankSlipActionLabel } from "./unitInstallments.js"
import styles from "../App.module.css"

export const bankSlipStatusLabel = {
  PENDING_REGISTRATION: "Aguardando registro", UNCERTAIN: "Registro incerto", REGISTERED: "Registrado",
  REJECTED: "Rejeitado", PAID: "Pago", WRITTEN_OFF: "Baixado no banco", CANCELED: "Cancelado",
}
const overdue = (slip) => ["PENDING_REGISTRATION", "UNCERTAIN", "REGISTERED"].includes(slip.status)
  && slip.due_date < new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" })
const save = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function useUnitBankSlips(bridge, unitId) {
  const [selected, setSelected] = useState(new Map())
  const [history, setHistory] = useState(null)
  const [failed, setFailed] = useState([])
  const [busy, setBusy] = useState(false)
  const [printLayout, setPrintLayout] = useState("FULL_PAGE")
  const [busyId, setBusyId] = useState(null)
  const [warning, setWarning] = useState(false)
  const pending = useRef(null)
  const allowed = Boolean(bridge?.canRead?.("bank_slip"))
  useEffect(() => { setSelected(new Map()); setHistory(null); setFailed([]); setWarning(false) }, [unitId])
  useEffect(() => { if (!allowed) setSelected(new Map()) }, [allowed])
  const guarded = (slips, action) => {
    if (slips.some(overdue)) { pending.current = action; setWarning(true) }
    else void action()
  }
  const download = async (slip) => {
    setBusy(true)
    setBusyId(slip.id)
    const originalTab = slip.has_pdf === false ? window.open("about:blank", "_blank") : null
    if (originalTab) originalTab.opener = null
    try {
      const kind = slip.has_pdf === false ? "html" : "pdf"
      const blob = await downloadErpPdf({ bridge, path: `/v1/bank-slips/${slip.id}/${kind}?construction_unit_id=${unitId}`, fallbackMessage: "Não foi possível abrir o arquivo do boleto." })
      if (kind === "html") {
        const url = URL.createObjectURL(blob)
        if (originalTab) originalTab.location.href = url
        else save(blob, `boleto-${slip.our_number}.html`)
        setTimeout(() => URL.revokeObjectURL(url), 60000)
        bridge?.feedback?.warning?.("Use Imprimir no navegador para imprimir o arquivo original do boleto.")
      } else save(blob, `boleto-${slip.our_number}.pdf`)
    } catch (err) {
      originalTab?.close()
      bridge?.feedback?.error?.(err.message)
    } finally {
      setBusy(false)
      setBusyId(null)
    }
  }
  const print = async () => {
    setBusy(true)
    try {
      const result = await printErpBankSlips({ bridge, unitId, ids: [...selected.keys()], layout: printLayout })
      if (result.pdf_base64) {
        const data = Uint8Array.from(atob(result.pdf_base64), (char) => char.charCodeAt(0))
        save(new Blob([data], { type: "application/pdf" }), printLayout === "CARNET" ? "carne.pdf" : "boletos.pdf")
      }
      setFailed(result.failed)
    } catch (err) { bridge?.feedback?.error?.(err.message) }
    finally { setBusy(false) }
  }
  return {
    allowed, selected, history, setHistory, failed, setFailed, busy, busyId, warning, setWarning, printLayout, setPrintLayout,
    toggle: (row) => setSelected((current) => {
      const next = new Map(current)
      const slip = row.bankSlips?.[0]
      if (!slip) return next
      if (next.has(slip.id)) next.delete(slip.id)
      else if (next.size < 200) next.set(slip.id, slip)
      return next
    }),
    requestDownload: (slip) => guarded([slip], () => download(slip)),
    requestPrint: () => guarded([...selected.values()], print),
    confirm: () => { setWarning(false); void pending.current?.(); pending.current = null },
  }
}

export function UnitBankSlipDialogs({ state }) {
  if (!state.allowed) return null
  const title = state.warning ? "Boleto vencido" : state.failed.length ? "Boletos que não foram impressos" : state.history
    ? `Boletos da parcela ${state.history.installmentNumber}/${state.history.totalInstallments}` : null
  if (!title) return null
  const close = () => { state.setWarning(false); state.setHistory(null); state.setFailed([]) }
  const money = (amount) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(amount)
  return <div className={styles.modalOverlay} role="presentation" onClick={close}>
    <section className={styles.modalCard} role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}>
      <header className={styles.modalHeader}><h3>{title}</h3><button className={styles.closeButton} type="button" onClick={close}>Fechar</button></header>
      <div className={styles.modalBody}>
        {state.warning ? <>
          <p>Há boleto ativo e vencido. Confirme as condições com o beneficiário antes de pagar.</p>
          <button type="button" className={styles.primaryButton} onClick={state.confirm}>Continuar</button>
        </> : state.failed.length ? <div className={styles.tableWrapper}><table className={styles.table}>
          <thead><tr><th>Parcela</th><th>Nosso número</th><th>Motivo</th></tr></thead>
          <tbody>{state.failed.map((item) => <tr key={item.bank_slip_id}><td>{item.installment_number}</td><td>{item.our_number}</td><td>{item.reason}</td></tr>)}</tbody>
        </table></div> : <div className={styles.tableWrapper}><table className={styles.table}>
          <thead><tr><th>Nosso número</th><th>Vencimento</th><th>Valor</th><th>Situação</th><th>Ações</th></tr></thead>
          <tbody>{state.history.bankSlips.map((slip) => <tr key={slip.id}>
            <td>{slip.our_number}</td><td>{slip.due_date.split("-").reverse().join("/")}</td><td>{money(slip.amount)}</td><td>{bankSlipStatusLabel[slip.status]}</td>
            <td><button type="button" className={styles.iconButton} disabled={state.busy}
              title={`${bankSlipActionLabel(slip)} ${slip.our_number}`} aria-label={`${bankSlipActionLabel(slip)} ${slip.our_number}`}
              onClick={() => state.requestDownload(slip)}><FileText size={16} aria-hidden="true" /></button></td>
          </tr>)}</tbody>
        </table></div>}
      </div>
    </section>
  </div>
}
