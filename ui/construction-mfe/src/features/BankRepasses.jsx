import { Fragment, useEffect, useId, useState } from "react"
import { createPortal } from "react-dom"
import { InfoTip } from "../components/InfoTip.jsx"
import { listErpCompanyBankAccounts, requestJson } from "../services/constructionApi.js"
import { currencyDecimal, currencyFromNumber, formatBRL, formatCurrencyInput } from "../utils/currencyInput.js"
import styles from "./BankRepasses.module.css"

const labels = { financing: "Financiamento", fgts: "FGTS", government_subsidy: "Subsídio" }
const receivedLabels = { financing: "Financiamento recebido", fgts: "FGTS recebido", government_subsidy: "Subsídio recebido" }
const amountFields = [
  ["expected", "Previsto"], ["confirmed", "Confirmado no banco"],
  ["historical", "Recebido no histórico"], ["outstanding", "A receber"],
]

const api = (bridge, path, options = {}) => requestJson({
  bridge, baseUrl: bridge.erpApiBaseUrl, path: "/v1/bank-repasses" + path, ...options,
})

const historicalPageSize = 1000

const amountKey = (sale, source) => sale + ":" + source
const positive = (amount) => Number(amount) > 0
const cents = (amount) => Math.round(Number(currencyDecimal(amount)) * 100)
const asMoney = (totalCents) => formatBRL(totalCents / 100)

function useRepassData(bridge, path, revision) {
  const [state, setState] = useState(null)
  useEffect(() => {
    const controller = new AbortController()
    if (!path) return () => controller.abort()
    api(bridge, path, { signal: controller.signal }).then((data) => {
      if (!controller.signal.aborted) setState({ bridge, path, revision, data, error: "", loading: false })
    }).catch((error) => {
      if (!controller.signal.aborted) {
        setState({ bridge, path, revision, data: null, error: error.message, loading: false })
      }
    })
    return () => controller.abort()
  }, [bridge, path, revision])
  return state?.bridge === bridge && state?.path === path && state?.revision === revision
    ? state
    : { data: null, error: "", loading: true }
}

function RepassTable({ sale }) {
  return <div className={styles.scroll}>
    <table className={styles.table}>
      <thead><tr><th scope="col">Origem</th>{amountFields.map(([key, label]) => <th key={key} scope="col">{label}</th>)}</tr></thead>
      <tbody>{sale.amounts.map((row) => <tr key={row.source}>
        <th scope="row">{labels[row.source]}</th>
        {amountFields.map(([key]) => <td key={key}>{formatBRL(row[key])}</td>)}
      </tr>)}</tbody>
      <tfoot><tr><th scope="row">Total</th>{amountFields.map(([key]) => (
        <td key={key}>{formatBRL(sale.amounts.reduce((sum, row) => sum + Number(row[key]), 0))}</td>
      ))}</tr></tfoot>
    </table>
  </div>
}

function RepassForm({ bridge, title, children, submitLabel, onClose, onSubmit, busy, disabled, error, inline, formId }) {
  const generatedId = useId()
  const id = formId ?? generatedId
  const Modal = bridge.components.Modal
  const primary = bridge.actionClasses?.primary || styles.primary
  const actions = <div className={styles.actions}>
    <button type="button" className={styles.secondary} disabled={busy} onClick={onClose}>Cancelar</button>
    <button type="submit" form={id} className={primary} disabled={busy || disabled}>
      {busy ? "Salvando..." : submitLabel}
    </button>
  </div>
  const content = <>
    {children}
    {error && <p role="alert" className={styles.error}>{error}</p>}
  </>
  function submit(event) {
    event.stopPropagation()
    onSubmit(event)
  }
  if (inline) return <div className={`${styles.credit} ${styles.form}`}>
    {createPortal(<form id={id} onSubmit={submit} />, document.body)}
    {content}
    {actions}
  </div>
  const form = <form id={id} className={styles.form} onSubmit={submit}>{content}</form>
  return <Modal isOpen title={title} onClose={busy ? undefined : onClose} dialogMaxWidth="56rem" hideCloseButton={busy} footer={actions}>
    {form}
  </Modal>
}

function CreditForm({ bridge, selected, onClose, onSaved, inline = false }) {
  const formId = useId()
  const [bankOptions, setBankOptions] = useState([])
  const [data, setData] = useState({ bank_account_id: "", credit_date: "", reference: "", amount: "" })
  const [manualLines, setManualLines] = useState(null)
  const [proof, setProof] = useState(null)
  const [entryReference, setEntryReference] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    let active = true
    listErpCompanyBankAccounts({ bridge, distinguishAccounts: true }).then((accounts) => {
      if (!active) return
      setBankOptions(accounts)
      if (accounts.length === 1) setData((current) => ({ ...current, bank_account_id: accounts[0].id }))
    }).catch((err) => { if (active) setError(err.message) })
    return () => { active = false }
  }, [bridge])

  const sources = selected.flatMap((sale) => sale.amounts.map((row) => ({
    saleId: sale.sale_id, project: sale.project_name, unit: sale.unit_code,
    source: row.source, key: amountKey(sale.sale_id, row.source),
    available: Math.round(Number(row.outstanding) * 100) + Math.round(Number(row.historical) * 100),
  }))).filter((row) => row.available > 0)
  const singleSale = selected.length === 1
  const enteredTotal = cents(data.amount)
  const available = sources.reduce((sum, row) => sum + row.available, 0)
  const canSuggest = !singleSale && enteredTotal > 0 &&
    (enteredTotal === available || (sources.length === 1 && enteredTotal <= available))
  const suggested = canSuggest ? Object.fromEntries(sources.map((row) => [
    row.key, currencyFromNumber((sources.length === 1 ? enteredTotal : row.available) / 100),
  ])) : null
  const lines = manualLines ?? suggested ?? {}
  const allocations = sources.filter((row) => cents(lines[row.key]) > 0).map((row) => ({
    sale_id: row.saleId, source: row.source, amount: currencyDecimal(lines[row.key]),
  }))
  const allocated = sources.reduce((sum, row) => sum + cents(lines[row.key]), 0)
  const overAllocated = sources.some((row) => cents(lines[row.key]) > row.available)
  const credit = singleSale ? allocated : enteredTotal
  const tooManyAllocations = allocations.length > 300
  const ready = data.bank_account_id && data.credit_date && data.reference.trim() &&
    credit > 0 && allocated === credit && !overAllocated && !tooManyAllocations
  const needsManual = !singleSale && credit > 0 && credit <= available && (manualLines !== null || !suggested)

  async function submit(event) {
    event.preventDefault()
    if (busy || !ready) return
    setBusy(true)
    setError("")
    try {
      const formData = new FormData()
      formData.append("payload", JSON.stringify({
        ...data, amount: (credit / 100).toFixed(2), allocations, confirmed_in_statement: true,
        entry_reference: entryReference.trim() || null,
      }))
      if (proof) formData.append("proof", proof)
      await api(bridge, "/confirm", { method: "POST", body: formData })
      onSaved("Repasse recebido e contabilizado.")
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function change(key, value) {
    setData((current) => ({ ...current, [key]: value }))
  }

  function sourceLabel(row) {
    return [row.project, row.unit, labels[row.source]].join(" · ")
  }

  return <RepassForm bridge={bridge} title="Registrar recebimento" submitLabel="Confirmar e baixar repasse"
    onClose={onClose} onSubmit={submit} busy={busy} error={error} disabled={!ready} inline={inline} formId={formId}>
    {singleSale ? <>
      {sources.length > 1 && <p className={styles.formNote}>Preencha só os valores que entraram neste depósito.</p>}
      <div className={styles.formGrid}>
        {sources.map((row) => (
          <label className={styles.field} key={row.key}>
            <span>{receivedLabels[row.source]}{sources.length === 1 && " *"} <InfoTip floating insideLabel
              label={`Sobre o valor de ${labels[row.source]}`}>Informe apenas a parte deste tipo que entrou no depósito.</InfoTip></span>
            <input form={formId} required={sources.length === 1} inputMode="decimal" placeholder="0,00"
              value={lines[row.key] ?? ""} onChange={(event) => setManualLines({ ...lines, [row.key]: formatCurrencyInput(event.target.value) })} />
            {cents(lines[row.key]) > row.available && <small className={styles.error}>Saldo disponível {asMoney(row.available)}</small>}
          </label>
        ))}
      </div>
      {sources.length > 1 && credit > 0 && <strong>Total recebido {asMoney(credit)}</strong>}
    </> : <>
      <details className={styles.breakdown}>
        <summary>{selected.length} vendas selecionadas</summary>
        <ul>{selected.map((sale) => <li key={sale.sale_id}>{sale.project_name} · {sale.unit_code}</li>)}</ul>
      </details>
      <label className={styles.field}>
        <span>Valor do depósito * <InfoTip floating insideLabel label="Sobre o valor do depósito">Valor total que entrou na conta para as unidades selecionadas.</InfoTip></span>
        <input form={formId} required inputMode="decimal" placeholder="0,00" value={data.amount} onChange={(event) => change("amount", formatCurrencyInput(event.target.value))} />
      </label>
    </>}
    <div className={styles.bankFields}>
      <label className={styles.field}>
        <span>Dia em que entrou * <InfoTip floating insideLabel label="Sobre o dia em que entrou">Copie a data em que o banco creditou o depósito no extrato.</InfoTip></span>
        <input form={formId} required type="date" value={data.credit_date} onChange={(event) => change("credit_date", event.target.value)} />
      </label>
      {bankOptions.length !== 1 && (
        <label className={styles.field}>
          <span>Conta bancária * <InfoTip floating insideLabel label="Sobre a conta bancária">Selecione a conta da empresa em que o depósito aparece no extrato.</InfoTip></span>
          <select form={formId} required value={data.bank_account_id} onChange={(event) => change("bank_account_id", event.target.value)}>
            <option value="">Selecione</option>{bankOptions.map((row) => <option value={row.id} key={row.id}>{row.label}</option>)}
          </select>
        </label>
      )}
      <label className={styles.field}>
        <span>Referência no extrato * <InfoTip floating insideLabel label="Sobre a referência no extrato">Copie o identificador que o banco mostra para esse depósito. Ele evita registrar o mesmo crédito duas vezes na conta.</InfoTip></span>
        <input form={formId} required maxLength={100} value={data.reference} onChange={(event) => change("reference", event.target.value)} />
      </label>
    </div>
    {bankOptions.length === 1 && <p className={styles.formNote}>Conta bancária <strong>{bankOptions[0].label}</strong></p>}
    <details className={styles.breakdown}>
      <summary>{proof ? "Comprovante anexado" : "Anexar comprovante (opcional)"}</summary>
      <label className={styles.field}>
        <span>Comprovante bancário (até 3 MB) <InfoTip floating insideLabel label="Sobre o comprovante bancário">Se tiver o arquivo que identifica o depósito, você pode anexá-lo. Conferir o extrato é suficiente para registrar o recebimento.</InfoTip></span>
        <input form={formId} type="file" accept="application/pdf,image/jpeg,image/png,image/gif,image/webp"
          onChange={(event) => setProof(event.target.files[0] || null)} />
      </label>
    </details>
    {bridge.canUpdate?.("accounting_entry") && <details className={styles.breakdown}>
      <summary>Depósito já lançado no razão</summary>
      <label className={styles.field}>Referência do lançamento no razão
        <input form={formId} maxLength={50} value={entryReference}
          onChange={(event) => setEntryReference(event.target.value)} />
      </label>
    </details>}
    {needsManual && <fieldset className={styles.formGrid}>
      <legend>Quanto entrou de cada tipo?</legend>
      {sources.map((row) => <label className={styles.field} key={row.key}>
        {sourceLabel(row)} <small>Disponível {asMoney(row.available)}</small>
        <input form={formId} inputMode="decimal" placeholder="0,00" value={lines[row.key] ?? ""}
          onChange={(event) => setManualLines({ ...lines, [row.key]: formatCurrencyInput(event.target.value) })} />
      </label>)}
      {suggested && <button type="button" className={styles.link} onClick={() => setManualLines(null)}>Usar sugestão</button>}
    </fieldset>}
    {suggested && !needsManual && <div className={styles.header}>
      <span>{sources.map((row) => sourceLabel(row) + " " + asMoney(cents(lines[row.key]))).join(" · ")}</span>
      {sources.length > 1 && <button type="button" className={styles.link} onClick={() => setManualLines(suggested)}>Ajustar valores</button>}
    </div>}
    {tooManyAllocations && <p role="alert" className={styles.error}>O depósito aceita até 300 valores distribuídos entre financiamento, FGTS e subsídio.</p>}
    {needsManual && <strong>Distribuído {asMoney(allocated)} de {asMoney(credit)}</strong>}
    {!singleSale && overAllocated && <p className={styles.error}>Confira os limites de cada origem.</p>}
    {!singleSale && credit > available && <p className={styles.error}>O crédito supera o saldo disponível de {asMoney(available)}.</p>}
  </RepassForm>
}

function AccountingModal({ bridge, credit, item, onClose, onSaved }) {
  const [reference, setReference] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      await api(bridge, "/" + credit.id + "/allocations/" + item.id + "/account", {
        method: "POST", body: {
          treatment: reference.trim() ? "existing" : "direct",
          entry_reference: reference.trim() || null,
        },
      })
      onSaved("Repasse contabilizado.")
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return <RepassForm bridge={bridge} title="Contabilizar repasse"
    submitLabel={reference.trim() ? "Vincular lançamento" : "Contabilizar depósito"} onClose={onClose}
    onSubmit={submit} busy={busy} error={error}>
    <strong>{item.unit_code} · {labels[item.source]} · {formatBRL(item.amount)}</strong>
    <p className={styles.formNote}>Se o depósito já estiver no razão, informe a referência para usar o lançamento existente.</p>
    <label className={styles.field}>Referência do lançamento no razão
      <input maxLength={50} value={reference} onChange={(event) => setReference(event.target.value)} />
    </label>
  </RepassForm>
}

function describeRepassReversal(credit) {
  const sales = new Set(credit.allocations.map((item) => item.sale_id)).size
  const batch = sales > 1
  const historical = !credit.bank_account_id
  const amount = formatBRL(credit.amount)
  const title = batch ? "Estornar lote" : historical ? "Estornar histórico" : "Estornar repasse"
  const scope = batch
    ? `Você vai estornar o lote inteiro de ${sales} vendas, no valor total de ${amount}.`
    : `Você vai estornar ${amount} desta venda.`
  const effect = historical
    ? "O saldo a receber será reaberto para os repasses incluídos no histórico."
    : "O saldo a receber será reaberto. O ONAVE também estorna os lançamentos que gerou para este crédito."
  return { title, message: `${scope} ${effect}`, confirmLabel: batch ? "Estornar lote inteiro" : "Estornar" }
}

export function UnitBankRepasses({ bridge, saleId, onChanged, canRegister = true }) {
  const [revision, setRevision] = useState(0)
  const [dialog, setDialog] = useState(null)
  const [registering, setRegistering] = useState(false)
  const [error, setError] = useState("")
  const [reversing, setReversing] = useState(false)
  const { data: sale, loading, error: saleError } = useRepassData(bridge, "/sales/" + saleId, revision)
  const receipts = useRepassData(bridge, "/sales/" + saleId + "/receipts", revision)
  const writable = bridge.canUpdate?.("receivable")
  const ConfirmDialog = bridge.components.ConfirmDialog
  const primary = bridge.actionClasses?.primary || styles.primary

  function saved(message) {
    setRegistering(false)
    setDialog(null)
    setRevision((current) => current + 1)
    bridge.feedback?.success?.(message)
    onChanged?.()
  }

  async function download(credit) {
    try {
      const blob = await api(bridge, "/" + credit.id + "/proof", { responseType: "blob" })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = credit.proof_name
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setError(err.message)
    }
  }

  async function reverse() {
    setReversing(true)
    setError("")
    try {
      await api(bridge, "/" + dialog.credit.id + "/reverse", { method: "POST" })
      saved("Repasse estornado.")
    } catch (err) {
      setDialog(null)
      setError(err.message)
    } finally {
      setReversing(false)
    }
  }

  if (!bridge.components?.Modal) return null
  if (loading) return <p role="status">Carregando repasses...</p>
  if (!sale) return <p role="alert" className={styles.error}>{saleError}</p>
  if (!sale.amounts.some((row) => positive(row.expected) || positive(row.confirmed) || positive(row.historical))) return null

  const canReceive = canRegister && writable && sale.amounts.some((row) => positive(row.outstanding) || positive(row.historical))
  const needsHistoryReview = canReceive && sale.financing_completed &&
    !sale.amounts.some((row) => positive(row.confirmed) || positive(row.historical))

  return <section className={styles.card} aria-label="Recebimentos do banco">
    <header className={styles.header}>
      <h3>Recebimentos do banco</h3>
      {canReceive && !registering && (
        <button type="button" className={primary} onClick={() => setRegistering(true)}>Registrar depósito</button>
      )}
    </header>
    {registering ? (
      <CreditForm inline bridge={bridge} selected={[sale]} onClose={() => setRegistering(false)} onSaved={saved} />
    ) : (
      <>
        {needsHistoryReview && <p className={styles.formNote}>Recebimento sem extrato? Use <strong>Regularizar histórico</strong> na lista de unidades.</p>}
        <dl className={styles.totals}>
          {amountFields.map(([key, label]) => {
            const total = sale.amounts.reduce((sum, row) => sum + Number(row[key]), 0)
            if (key === "historical" && !total) return null
            return <div key={key}><dt>{label}</dt><dd>{formatBRL(total)}</dd></div>
          })}
        </dl>
        {sale.amounts.filter((row) => positive(row.expected) || positive(row.confirmed) || positive(row.historical)).length > 1 && (
          <details className={styles.breakdown}>
            <summary>Ver valores por tipo</summary>
            <RepassTable sale={sale} />
          </details>
        )}
      </>
    )}
    {(error || receipts.error) && <p role="alert" className={styles.error}>{error || receipts.error}</p>}
    {[...(receipts.data || [])].sort((left, right) => {
      const pending = (credit) => credit.allocations.some((item) => item.sale_id === saleId && item.accounting_status === "pending")
      return Number(pending(right)) - Number(pending(left))
    }).map((credit) => <article className={styles.credit} key={credit.id}>
      <div className={styles.header}>
        <strong>{credit.reference || (credit.bank_account_id ? "Crédito bancário" : "Valor aprovado no histórico")} · {
          formatBRL(credit.allocations.filter((item) => item.sale_id === saleId).reduce((total, item) => total + Number(item.amount), 0))
        }</strong>
        {credit.credit_date && <span>{credit.credit_date.split("-").reverse().join("/")}</span>}
        <div className={styles.actions}>
          {credit.proof_name && <button type="button" className={styles.secondary} onClick={() => download(credit)}>Comprovante</button>}
          {credit.bank_account_id && credit.can_manage && !credit.proof_name && <span>Conferido no extrato · sem anexo</span>}
          {credit.can_manage && bridge.canDelete?.("receivable") && ConfirmDialog && (
            <button type="button" className={styles.secondary} onClick={() => setDialog({ kind: "reverse", credit })}>
              {credit.allocations.some((item) => item.sale_id !== saleId) ? "Estornar lote" : "Estornar"}
            </button>
          )}
        </div>
      </div>
      {credit.allocations.filter((item) => item.sale_id === saleId).map((item) => (
        <div key={item.id} className={styles.header}>
          <span>{labels[item.source]} · {formatBRL(item.amount)} · {
            { pending: "Para contabilizar", accounted: "Contabilizado", historical: "Valor original" }[item.accounting_status]
          }</span>
          {credit.can_manage && writable && bridge.canUpdate?.("accounting_entry") && item.accounting_status === "pending" && <button type="button" className={styles.secondary}
            onClick={() => setDialog({ kind: "account", credit, item })}>Contabilizar</button>}
        </div>
      ))}
    </article>)}
    {dialog?.kind === "account" && <AccountingModal bridge={bridge} {...dialog} onClose={() => setDialog(null)} onSaved={saved} />}
    {dialog?.kind === "reverse" && <ConfirmDialog isOpen variant="danger"
      {...describeRepassReversal(dialog.credit)} loading={reversing}
      onCancel={reversing ? undefined : () => setDialog(null)} onConfirm={reverse} />}
  </section>
}

export function BankRepassBatches({ bridge, projectId, projectName, openHistory, saleRevision }) {
  const writable = bridge.canUpdate?.("receivable")
  const [mode, setMode] = useState(writable && openHistory ? "historical" : null)
  const toggle = (next) => setMode((current) => current === next ? null : next)
  return <div className={styles.batchTools}>
    <div className={styles.header}>
      <button type="button" className={styles.secondary} aria-expanded={mode === "credits"} onClick={() => toggle("credits")}>
        {writable ? "Depósito de várias unidades" : "Consultar repasses"}
      </button>
      {writable && <button type="button" className={styles.secondary} aria-expanded={mode === "historical"} onClick={() => toggle("historical")}>
        Regularizar histórico
      </button>}
    </div>
    {mode && <BankRepassBatchPanel key={mode} bridge={bridge} projectId={projectId} projectName={projectName}
      saleRevision={saleRevision} historicalMode={mode === "historical"} />}
  </div>
}

function BankRepassBatchPanel({ bridge, projectId, projectName, historicalMode, saleRevision = 0 }) {
  const scopeId = useId()
  const selectionId = useId()
  const [depositSelections, setDepositSelections] = useState({})
  const [allWorks, setAllWorks] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [objects, setObjects] = useState({})
  const [selectHistoryByDefault, setSelectHistoryByDefault] = useState(true)
  const [revision, setRevision] = useState(0)
  const [dialog, setDialog] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [selectedSale, setSelectedSale] = useState(null)
  const [amounts, setAmounts] = useState({})
  const search = new URLSearchParams({
    page: String(historicalMode ? 1 : page),
    page_size: String(historicalMode ? historicalPageSize : pageSize),
  })
  if (historicalMode) search.set("historical", "true")
  if (!allWorks) search.set("project_id", projectId)
  const view = useRepassData(bridge, "/sales?" + search.toString(), revision + saleRevision)
  const sales = view.data?.items || []
  const exceedsHistoryLimit = historicalMode && view.data?.total > sales.length
  const totalItems = historicalMode ? sales.length : (view.data?.total ?? 0)
  const totalPages = historicalMode ? Math.ceil(totalItems / pageSize) : view.data?.total_pages
  const currentPage = historicalMode && totalPages ? Math.min(page, totalPages) : page
  const items = historicalMode ? sales.slice((currentPage - 1) * pageSize, currentPage * pageSize) : sales
  const writable = Boolean(bridge.canUpdate?.("receivable"))
  const Pagination = bridge.components.Pagination
  const primary = bridge.actionClasses?.primary || styles.primary
  const canSelect = (sale) => sale.amounts.some((row) => positive(row.outstanding) || (!historicalMode && positive(row.historical)))
  const selectable = items.filter(canSelect)
  const selectedForHistory = (sale) => objects[sale.sale_id] ?? selectHistoryByDefault
  const pageSelection = selectable.filter((sale) => historicalMode
    ? selectedForHistory(sale)
    : Boolean(depositSelections[sale.sale_id]))
  const selected = historicalMode ? sales.filter(selectedForHistory) : Object.values(depositSelections)
  const allocations = (historicalMode ? selected : []).flatMap((sale) => sale.amounts.map((row) => {
    const key = amountKey(sale.sale_id, row.source)
    return { sale_id: sale.sale_id, source: row.source, amount: currencyDecimal(amounts[key] ?? currencyFromNumber(row.outstanding)) }
  })).filter((row) => positive(row.amount))
  const allocatedSales = new Set(allocations.map((row) => row.sale_id))
  const projectsBySale = new Map(selected.map((sale) => [sale.sale_id, sale]))
  const totalsByProject = new Map()
  if (historicalMode) {
    for (const allocation of allocations) {
      const sale = projectsBySale.get(allocation.sale_id)
      const total = totalsByProject.get(sale.project_id) ?? { name: sale.project_name, amount: 0 }
      total.amount += Math.round(Number(allocation.amount) * 100)
      totalsByProject.set(sale.project_id, total)
    }
  }

  function refresh() {
    setRevision((current) => current + 1)
  }

  function selectAllHistory(checked) {
    setObjects({})
    setSelectHistoryByDefault(checked)
  }

  function reset() {
    setDialog(null)
    setAmounts({})
    selectAllHistory(true)
    setDepositSelections({})
    if (historicalMode) changePage(1)
    refresh()
  }

  function changePage(next) {
    setPage(next)
    setSelectedSale(null)
  }

  function changeScope(checked) {
    setAllWorks(checked)
    if (historicalMode) {
      setAmounts({})
      selectAllHistory(true)
    }
    if (!checked) {
      setDepositSelections((current) => Object.fromEntries(
        Object.entries(current).filter(([, sale]) => sale.project_id === projectId),
      ))
    }
    changePage(1)
  }

  function selectSales(sales, checked) {
    if (historicalMode) {
      setObjects((current) => ({
        ...current,
        ...Object.fromEntries(sales.map((sale) => [sale.sale_id, checked])),
      }))
      return
    }
    setDepositSelections((current) => {
      const next = { ...current }
      for (const sale of sales) {
        if (checked) next[sale.sale_id] = sale
        else delete next[sale.sale_id]
      }
      return next
    })
  }

  async function approve(event) {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      await api(bridge, "/historical", { method: "POST", body: { allocations } })
      reset()
      bridge.feedback?.success?.("Histórico aprovado.")
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return <section className={styles.card} aria-label={historicalMode ? "Regularizar histórico" : "Repasses bancários"}>
    <div className={styles.header}>
      <div className={styles.scope}>
        <label className={styles.scopeToggle}>
          <input type="checkbox" checked={allWorks} aria-describedby={scopeId}
            onChange={(event) => changeScope(event.target.checked)} />
          Mostrar vendas de todas as obras
        </label>
        <p id={scopeId} role="status" className={styles.formNote}>
          {allWorks ? "Exibindo vendas de todas as obras a que você tem acesso." : `Exibindo vendas de ${projectName}.`}
        </p>
      </div>
      {writable && <div className={styles.actions}>
        <span id={selectionId} role="status" className={styles.formNote}>
          {selected.length > 0
            ? (selected.length === 1 ? "1 venda selecionada" : `${selected.length} vendas selecionadas`)
            : (historicalMode ? "Marque as vendas para revisar." : "Marque as vendas deste depósito para continuar.")}
        </span>
        {selected.length > 0 && <button type="button" className={styles.secondary} onClick={() => {
          if (historicalMode) selectAllHistory(false)
          else setDepositSelections({})
        }}>Limpar seleção</button>}
        {historicalMode && !selected.length && sales.length > 0 && <button type="button"
          className={styles.secondary} onClick={() => selectAllHistory(true)}>
          Selecionar todas
        </button>}
        <button type="button" className={primary} aria-describedby={selectionId}
          disabled={view.loading || Boolean(view.error) || exceedsHistoryLimit ||
            (historicalMode ? !allocations.length : !selected.length)}
          onClick={() => { setError(""); setDialog(historicalMode ? "approve" : { kind: "credit", selected }) }}>
          {historicalMode ? "Revisar lote" : "Preencher dados do depósito"}
        </button>
      </div>}
    </div>
    {view.loading && <p role="status">Carregando repasses...</p>}
    {view.error && <p role="alert" className={styles.error}>{view.error}</p>}
    {exceedsHistoryLimit && <p role="alert" className={styles.error}>
      Há mais de mil vendas no histórico. Desmarque Mostrar vendas de todas as obras e revise um lote por obra.
    </p>}
    {!view.loading && !view.error && !items.length && <p>
      {historicalMode ? "Nenhuma venda com saldo para regularizar." : "Nenhuma venda com previsão de repasse."}
    </p>}
    {items.length > 0 && <div className={styles.scroll}>
      <table className={styles.table}>
        <thead><tr>
          {writable && <th scope="col" className={styles.selectionCell}>
            <input type="checkbox" aria-label="Selecionar vendas desta página"
              disabled={!selectable.length} checked={selectable.length > 0 && pageSelection.length === selectable.length}
              ref={(input) => {
                if (input) input.indeterminate = pageSelection.length > 0 && pageSelection.length < selectable.length
              }}
              onChange={(event) => selectSales(selectable, event.target.checked)} />
          </th>}
          <th scope="col" className={styles.unitHeading}>Obra e unidade</th>
          {historicalMode ? Object.values(labels).map((label) => <th key={label} scope="col">{label}</th>)
            : amountFields.map(([key, label]) => <th key={key} scope="col">{label}</th>)}
        </tr></thead>
        <tbody>{items.map((sale) => {
          const checked = pageSelection.includes(sale)
          const pending = sale.amounts.reduce((sum, row) => sum + Number(row.accounting_pending || 0), 0)
          const hasReceipts = sale.amounts.some((row) => positive(row.confirmed) || positive(row.historical))
          const expanded = selectedSale === sale.sale_id
          return <Fragment key={sale.sale_id}>
            <tr>
              {writable && <td className={styles.selectionCell}><input type="checkbox" checked={checked} disabled={!canSelect(sale)}
                aria-label={"Selecionar " + sale.project_name + " " + sale.unit_code}
                onChange={(event) => selectSales([sale], event.target.checked)} /></td>}
              <th scope="row">
                {sale.project_name} · {sale.unit_code}
                {sale.terminated && <small>Distrato</small>}
                {!historicalMode && (hasReceipts || pending > 0) && (
                  <button type="button" className={styles.pendingLink} aria-expanded={expanded}
                    onClick={() => setSelectedSale(expanded ? null : sale.sale_id)}>
                    {pending > 0 ? "Para contabilizar · " + formatBRL(pending) : "Ver recebimentos"}
                  </button>
                )}
                {historicalMode && sale.financing_completed && <small>Financiamento concluído</small>}
              </th>
              {historicalMode ? sale.amounts.map((row) => {
                const key = amountKey(sale.sale_id, row.source)
                return <td key={key}><input inputMode="decimal" disabled={!checked || !positive(row.outstanding)}
                  aria-label={labels[row.source] + " " + sale.unit_code}
                  value={amounts[key] ?? currencyFromNumber(row.outstanding)}
                  onChange={(event) => setAmounts((current) => ({ ...current, [key]: formatCurrencyInput(event.target.value) }))} /></td>
              }) : amountFields.map(([key]) => (
                <td key={key}>
                  {formatBRL(sale.amounts.reduce((sum, row) => sum + Number(row[key]), 0))}
                </td>
              ))}
            </tr>
            {expanded && <tr>
              <td className={styles.receiptsCell} colSpan={amountFields.length + 1 + Number(writable)}>
                <UnitBankRepasses bridge={bridge} saleId={sale.sale_id} canRegister={false} onChanged={reset} />
              </td>
            </tr>}
          </Fragment>
        })}</tbody>
      </table>
    </div>}
    {Pagination && totalItems > 0 && <Pagination currentPage={currentPage} totalPages={totalPages}
      totalItems={totalItems} pageSize={pageSize} onPageChange={changePage}
      onPageSizeChange={(size) => { setPageSize(size); changePage(1) }} />}
    {dialog?.kind === "credit" && <CreditForm bridge={bridge} selected={dialog.selected} onClose={() => setDialog(null)}
      onSaved={(message) => { reset(); bridge.feedback?.success?.(message) }} />}
    {dialog === "approve" && <RepassForm bridge={bridge} title="Aprovar histórico de repasses" submitLabel="Aprovar lote"
      onClose={() => setDialog(null)} onSubmit={approve} busy={busy} disabled={!allocations.length} error={error}>
      <strong>{allocatedSales.size} {allocatedSales.size === 1 ? "venda" : "vendas"} · {
        asMoney(allocations.reduce((sum, row) => sum + Math.round(Number(row.amount) * 100), 0))
      }</strong>
      <div>
        <strong>Total por obra</strong>
        <ul>{Array.from(totalsByProject, ([id, work]) => <li key={id}>{work.name} · {asMoney(work.amount)}</li>)}</ul>
      </div>
      <ul>{Object.entries(labels).map(([source, label]) => <li key={source}>
        {label} · {formatBRL(allocations.filter((row) => row.source === source).reduce((sum, row) => sum + Number(row.amount), 0))}
      </li>)}</ul>
      <p>Já confirmado no banco nas vendas selecionadas: {formatBRL(selected.flatMap((sale) => sale.amounts)
        .reduce((sum, row) => sum + Number(row.confirmed), 0))}.</p>
      <p>Os valores aprovados ficam no histórico operacional, sem conciliação bancária.</p>
    </RepassForm>}
  </section>
}
