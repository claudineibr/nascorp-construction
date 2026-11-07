import { useEffect, useState } from "react"
import { Download, FileText, Loader2 } from "lucide-react"
import { UnitBankSlipDialogFrame } from "./UnitBankSlipsDialog.jsx"
import { listErpInstallmentReceipts, downloadErpReceiptPdf } from "../services/constructionApi.js"
import { formatBRL } from "../utils/currencyInput.js"
import { formatBusinessDate } from "../utils/brazilDate.js"
import styles from "./InstallmentReceiptsDialog.module.css"

export function InstallmentReceiptsDialog({ bridge, installment, onClose }) {
  const [page, setPage] = useState(1)
  const [result, setResult] = useState({ items: [], total: 0, total_pages: 1 })
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(null)
  const [failed, setFailed] = useState(false)
  const [reload, setReload] = useState(0)
  const Pagination = bridge?.components?.Pagination
  const original = Number(installment.amount || 0)
  const principal = Number(installment.paidAmount || 0)
  const outstanding = Number(installment.outstandingAmount ?? Math.max(0, original - principal))
  const received = (installment.payments ?? []).reduce(
    (sum, payment) => sum + Number(payment.netAmount ?? payment.amount ?? 0), 0,
  )

  useEffect(() => {
    let active = true
    setLoading(true)
    setFailed(false)
    listErpInstallmentReceipts({ bridge, installmentId: installment.id, page })
      .then((data) => { if (active) setResult(data) })
      .catch((error) => { if (active) { setFailed(true); bridge?.feedback?.error?.(error.message) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [bridge, installment.id, page, reload])

  const download = async (receipt) => {
    setBusy(receipt.id)
    try {
      const blob = await downloadErpReceiptPdf({ bridge, receiptId: receipt.id })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `recibo-${receipt.receipt_number.replace("/", "-")}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (error) { bridge?.feedback?.error?.(error.message) }
    finally { setBusy(null) }
  }

  return <UnitBankSlipDialogFrame bridge={bridge}
    title={`Recibos da parcela ${installment.installmentNumber}/${installment.totalInstallments ?? 1}`}
    dialogMaxWidth={880} onClose={onClose}
    footer={<div className={styles.footer}>
      <span>{loading ? "Carregando recibos…" : failed ? "Consulta indisponível"
        : `${result.total} ${result.total === 1 ? "recibo emitido" : "recibos emitidos"}`}</span>
      <button type="button" className={styles.secondaryButton} onClick={onClose}>Fechar</button>
    </div>}>
    <div className={styles.content}>
      <dl className={styles.summary}>
        <div><dt>Valor original</dt><dd>{formatBRL(original)}</dd></div>
        <div><dt>Principal abatido</dt><dd>{formatBRL(principal)}</dd></div>
        <div><dt>Total recebido</dt><dd>{formatBRL(received)}</dd></div>
        <div><dt>Saldo pendente</dt><dd>{formatBRL(outstanding)}</dd></div>
      </dl>
      <div className={styles.sectionHeading}>
        <h4>Recebimentos documentados</h4>
        <span>Vencimento atual: {formatBusinessDate(installment.dueDate)}</span>
      </div>
      {loading ? <div className={styles.state} role="status">
        <Loader2 size={20} className={styles.spinning} aria-hidden="true" />Carregando recibos…
      </div> : failed ? <div className={styles.state}>
        <p>Não foi possível consultar os recibos.</p>
        <button type="button" className={styles.secondaryButton} onClick={() => setReload((value) => value + 1)}>
          Tentar novamente
        </button>
      </div> : result.items.length ? <ul className={styles.receipts}>
        {result.items.map((receipt) => <li key={receipt.id} className={styles.receipt}>
          <div className={styles.document}>
            <FileText size={20} aria-hidden="true" />
            <div><strong>Recibo {receipt.receipt_number}</strong>
              <span>Emitido em {formatBusinessDate(receipt.issue_date)}</span>
            </div>
          </div>
          <div className={styles.amount}><span>Valor recebido</span>
            <strong>{formatBRL(receipt.total_paid)}</strong>
          </div>
          <button type="button" className={styles.downloadButton} disabled={Boolean(busy)}
            aria-label={`Baixar PDF do recibo ${receipt.receipt_number}`} onClick={() => download(receipt)}>
            {busy === receipt.id ? <Loader2 size={16} className={styles.spinning} aria-hidden="true" />
              : <Download size={16} aria-hidden="true" />}
            {busy === receipt.id ? "Baixando…" : "Baixar PDF"}
          </button>
        </li>)}
      </ul> : <div className={styles.state}><FileText size={24} aria-hidden="true" />
        <p>Nenhum recibo emitido para esta parcela.</p>
      </div>}
      {!loading && !failed && result.total_pages > 1 && <div className={styles.paginationSlot}>
        {Pagination ? <Pagination className={styles.pagination} currentPage={page} totalPages={result.total_pages}
          totalItems={result.total} pageSize={20} isLoading={loading} onPageChange={setPage} />
          : <div className={styles.fallbackPagination}>
            <button type="button" className={styles.secondaryButton} disabled={page <= 1}
              onClick={() => setPage(page - 1)}>Anterior</button>
            <span>Página {page} de {result.total_pages}</span>
            <button type="button" className={styles.secondaryButton} disabled={page >= result.total_pages}
              onClick={() => setPage(page + 1)}>Próxima</button>
          </div>}
      </div>}
    </div>
  </UnitBankSlipDialogFrame>
}
