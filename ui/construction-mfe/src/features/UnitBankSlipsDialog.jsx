import { useEffect, useState } from "react"
import { bankSlipErpOperation } from "../services/constructionApi.js"
import { bankSlipStatusLabel, formatBankSlipMoney, SelectPageCheckbox, toggleSelectionPage } from "./UnitBankSlips.jsx"
import styles from "../App.module.css"
import dialogStyles from "./UnitInstallmentsPanel.module.css"

export function UnitBankSlipDialogFrame({ bridge, title, onClose, children, footer }) {
  const Modal = bridge?.components?.Modal
  if (Modal) return <Modal isOpen title={title} onClose={onClose} dialogMaxWidth={1040} footer={footer}>
    {children}
  </Modal>
  return <div className={styles.modalOverlay} role="presentation"><section className={dialogStyles.dialog}
    role="dialog" aria-modal="true" aria-label={title}>
    <header className={styles.modalHeader}><h3>{title}</h3>
      <button type="button" className={styles.secondaryButton} onClick={onClose}>Fechar</button></header>
    <div className={styles.modalBody}>{children}</div>
    {footer && <footer className={styles.modalFooter}>{footer}</footer>}
  </section></div>
}

export function UnitBankSlipsDialog({ state, unitId, onClose }) {
  const [result, setResult] = useState({ items: [], total: 0, total_pages: 1 })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  const [reload, setReload] = useState(0)
  const [selected, setSelected] = useState(new Map())
  const Pagination = state.bridge?.components?.Pagination
  useEffect(() => {
    let alive = true
    setLoading(true); setFailed(false)
    bankSlipErpOperation({ bridge: state.bridge, path: `?unit_id=${unitId}&page=${page}&page_size=50`, method: "GET" })
      .then((data) => { if (alive) setResult(data) })
      .catch((error) => { if (alive) { setFailed(true); state.bridge?.feedback?.error?.(error.message) } })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [state.bridge, unitId, page, reload])
  const toggle = (slip) => setSelected((current) => {
    const next = new Map(current)
    if (next.has(slip.id)) next.delete(slip.id)
    else if (next.size < 200) next.set(slip.id, slip)
    return next
  })
  const footer = <div className={dialogStyles.batchActions}>
    {result.total > 0 && <>
      <label className={dialogStyles.field}>Formato de impressão
        <select value={state.printLayout} disabled={state.busy}
          onChange={(event) => state.setPrintLayout(event.target.value)}>
          <option value="FULL_PAGE">Boleto completo — um por página</option>
          <option value="CARNET">Carnê — três por folha A4</option>
        </select>
      </label>
      <button type="button" className={styles.primaryButton} disabled={state.busy || state.warning || !selected.size}
        onClick={() => state.requestPrintSlips([...selected.values()])}>
        {state.printLayout === "CARNET" ? "Imprimir carnê" : "Imprimir boletos"} ({selected.size})</button>
    </>}
    <button type="button" className={styles.secondaryButton} disabled={state.busy} onClick={onClose}>Fechar</button>
  </div>
  return <UnitBankSlipDialogFrame bridge={state.bridge} title="Boletos da unidade"
    onClose={state.busy ? undefined : onClose} footer={footer}>
    {state.warning && <div>
      <p>Há boleto ativo e vencido. Confirme as condições com o beneficiário antes de pagar.</p>
      <button type="button" className={styles.primaryButton} onClick={state.confirm}>Continuar impressão</button>
      <button type="button" className={styles.secondaryButton} onClick={() => state.setWarning(false)}>
        Cancelar impressão</button>
    </div>}
    {state.failed.length > 0 && <div role="status">
      <p>Boletos que não foram impressos:</p>
      <ul>{state.failed.map((item) => <li key={item.bank_slip_id}>{item.our_number}: {item.reason}</li>)}</ul>
    </div>}
    {loading ? <p role="status">Carregando boletos...</p> : failed ? <>
      <p role="status">Não foi possível carregar os boletos da unidade.</p>
      <button type="button" className={styles.secondaryButton} onClick={() => setReload((value) => value + 1)}>
        Tentar novamente</button>
    </> : !result.items.length ? <p>Nenhum boleto cadastrado para esta unidade.</p> : <>
      <p className={styles.metricHint}>Selecione até 200 boletos para imprimir.
        A seleção é mantida ao trocar de página.</p>
      <div className={styles.tableWrapper}><table className={`${styles.table} ${dialogStyles.table}`}>
        <thead><tr><th className={dialogStyles.selectionCell}>
          <SelectPageCheckbox ids={result.items.map((slip) => slip.id)} selected={selected}
            disabled={state.busy || state.warning} label="Selecionar todos os boletos desta página"
            onToggle={() => setSelected((current) =>
              toggleSelectionPage(current, result.items.map((slip) => [slip.id, slip])))} />
        </th><th>Parcela</th><th>Nosso número</th><th>Vencimento</th>
          <th>Valor</th><th>Situação</th></tr></thead>
        <tbody>{result.items.map((slip) => <tr key={slip.id}
          className={selected.has(slip.id) ? dialogStyles.selectedRow : undefined}>
          <td className={dialogStyles.selectionCell}>
            <input type="checkbox" checked={selected.has(slip.id)}
            aria-label={`Selecionar boleto ${slip.our_number}`}
            disabled={state.busy || state.warning || (!selected.has(slip.id) && selected.size >= 200)}
            onChange={() => toggle(slip)} /></td>
          <td>{slip.installment_number}/{slip.total_installments}</td><td>{slip.our_number}</td>
          <td>{slip.due_date.split("-").reverse().join("/")}</td><td>{formatBankSlipMoney(slip.amount)}</td>
          <td>{bankSlipStatusLabel[slip.status]}</td>
        </tr>)}</tbody>
      </table></div>
      {Pagination ? <Pagination currentPage={page} pageSize={50}
        totalItems={result.total} totalPages={result.total_pages}
        onPageChange={setPage} isLoading={loading} /> : <div className={dialogStyles.batchActions}>
        <button type="button" className={styles.secondaryButton} disabled={page <= 1} onClick={() => setPage(page - 1)}>
          Anterior</button><span>Página {page} de {result.total_pages}</span>
        <button type="button" className={styles.secondaryButton}
          disabled={page >= result.total_pages}
          onClick={() => setPage(page + 1)}>Próxima</button>
      </div>}
    </>}
  </UnitBankSlipDialogFrame>
}
