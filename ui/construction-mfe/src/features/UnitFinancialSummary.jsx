import { useEffect, useState } from "react"
import { requestJson } from "../services/constructionApi.js"
import styles from "./UnitFinancialSummary.module.css"

export function UnitFinancialSummary({ bridge, unit, plan, formatMoney, downloadAction }) {
  const FieldInfo = bridge?.components?.FieldInfo
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError("")
    const baseUrl = bridge?.erpApiBaseUrl || import.meta.env.VITE_ERP_API_URL || "http://127.0.0.1:8000"
    requestJson({
      bridge,
      baseUrl,
      path: `/v1/reports/units/${unit.id}/sales/${unit.currentSaleId}/summary`,
    }).then((data) => {
      if (active) setSummary(data)
    }).catch((err) => {
      if (!active) return
      const message = err?.message || "Não foi possível carregar o resumo financeiro."
      setSummary(null)
      setError(message)
      bridge?.feedback?.error?.(message)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [bridge, unit.id, unit.currentSaleId, plan, retry])

  const header = (
    <div className={styles.header}>
      <h3>Resumo financeiro</h3>
      {downloadAction}
    </div>
  )

  if (loading || error || !summary) return (
    <section className={styles.card} aria-label="Resumo financeiro da unidade">
      {header}
      {loading && <p className={styles.state}>Carregando resumo financeiro...</p>}
      {error && (
        <div className={styles.state}>
          <p>{error}</p>
          <button type="button" className={styles.retry} onClick={() => setRetry((value) => value + 1)}>Tentar novamente</button>
        </div>
      )}
    </section>
  )

  const saleValues = Object.fromEntries(summary.sale_values)
  const openTotal = summary.groups.reduce((sum, group) => sum + Number(group.pending) + Number(group.overdue), 0)
  const openCount = summary.groups.reduce((sum, group) => sum + group.pending_count + group.overdue_count, 0)
  const details = [
    ["Subsídio", saleValues["Subsídio"]],
    ["FGTS", saleValues.FGTS],
    ["Financiamento", saleValues.Financiamento],
    ["Entrada", summary.entry],
    ["Desconto", saleValues.Desconto],
  ]

  return (
    <section className={styles.card} aria-label="Resumo financeiro da unidade">
      {header}
      <div className={styles.groups}>
        {summary.groups.map((group) => (
          <div key={group.label} className={styles.group}>
            <div className={styles.total}><strong>{formatMoney(group.total)}</strong><span>{group.label} ({group.count})</span></div>
            <div className={styles.metrics}>
              {[
                ["Pagas", group.settled, group.paid],
                ["Pendentes", group.pending_count, group.pending],
                ["Vencidas", group.overdue_count, group.overdue],
              ].map(([label, count, amount]) => (
                <div className={styles.metric} key={label}>
                  <strong className={label === "Vencidas" && Number(amount) > 0 ? styles.overdue : undefined}>{formatMoney(amount)}</strong>
                  <span>{label} ({count})</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className={styles.grandTotal}>
        <strong>{formatMoney(openTotal)}</strong>
        <span>Parcelas, aditivos e sinal pendentes ou vencidos ({openCount})</span>
      </div>
      <div className={styles.saleTotals}>
        <div><strong>{formatMoney(saleValues["Valor do imóvel"])}</strong><span>Valor da venda</span></div>
        <div><strong>{formatMoney(summary.documentation_total)}</strong><span>Documentação</span></div>
      </div>
      <div className={styles.saleDetails}>
        {details.map(([label, amount]) => <div key={label}><strong>{formatMoney(amount)}</strong><span>{label}</span></div>)}
      </div>
      <div className={styles.grandTotal}>
        <strong className={summary.balance_label === "Saldo devedor" ? styles.overdue : undefined}>{formatMoney(summary.balance)}</strong>
        <span>{summary.balance_label}</span>
      </div>
      <div className={styles.saleTotals}>
        <div>
          <strong>{formatMoney(summary.billed_outstanding)}</strong>
          <span className={styles.metricLabel}>
            Cobranças da venda em aberto
            {FieldInfo && (
              <FieldInfo
                label="Cobranças da venda em aberto"
                description="Valor que já tem cobrança lançada e ainda está em aberto. Inclui parcelas, aditivos e sinais que compõem a venda, a vencer ou vencidos."
                example="R$ 16.750,00 em parcelas já lançadas e ainda não pagas."
                usage="Consulte as abas Parcelas e Sinal para ver essas cobranças."
              />
            )}
          </span>
        </div>
        <div>
          <strong>{formatMoney(summary.balance_to_charge)}</strong>
          <span className={styles.metricLabel}>
            Saldo sem cobrança lançada
            {FieldInfo && (
              <FieldInfo
                label="Saldo sem cobrança lançada"
                description="Parte do saldo devedor que ainda não tem cobrança. É o saldo devedor menos as cobranças da venda em aberto, com mínimo de zero."
                example="R$ 183.450,00 de saldo devedor menos R$ 16.750,00 em cobranças abertas resulta em R$ 166.700,00."
                usage="Mostra quanto ainda precisa ser cobrado por sinal ou aditivo."
              />
            )}
          </span>
        </div>
      </div>
    </section>
  )
}
