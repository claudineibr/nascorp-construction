import { useState } from "react"
import { InfoTip } from "../components/InfoTip.jsx"
import styles from "./ProjectSummaryDashboard.module.css"

const money = (value) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value))
const compact = (value) => new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 }).format(value)
const monthLabel = (month) => `${month.slice(5)}/${month.slice(0, 4)}`
const FIELD_HELP = {
  gross: "Soma do bruto das NFS-e de produção disponíveis com vínculo confirmado à obra. Exemplo: duas notas de R$ 10.000,00 somam R$ 20.000,00. Use para acompanhar o faturamento; não representa dinheiro recebido.",
  net: "Soma dos valores líquidos informados nos XMLs das notas disponíveis. Exemplo: bruto de R$ 10.000,00 e líquido de R$ 9.000,00. Use para comparar o valor líquido faturado, sem classificar a diferença automaticamente como retenção.",
  received: "Dinheiro das baixas dos títulos ativos vinculados às notas disponíveis, incluindo recebimentos parciais. Exemplo: uma baixa de R$ 3.000,00 soma R$ 3.000,00. Use para acompanhar a entrada financeira, respeitando seu acesso aos centros de custo.",
  open: "Saldo das parcelas dos títulos ativos vinculados às notas disponíveis, incluindo as vencidas. Exemplo: R$ 9.000,00 menos R$ 3.000,00 de principal baixado deixa R$ 6.000,00. Use para acompanhar a cobrança no seu escopo de acesso.",
  balance: "Faturamento bruto disponível menos o custo realizado apropriado à obra. Exemplo: R$ 100.000,00 faturados menos R$ 60.000,00 de custo deixa R$ 40.000,00. É um comparativo gerencial: não inclui custos futuros e não representa lucro contábil nem saldo bancário.",
  canceled: "Bruto das NFS-e canceladas vinculadas à obra, excluído do faturamento e dos recebimentos deste painel. Exemplo: uma nota cancelada de R$ 5.000,00 aparece aqui. Use para conferir o histórico fiscal.",
}

function Metric({ label, value, help, hint }) {
  return <article className={styles.metric}>
    <span className={styles.label}>{label}<InfoTip floating label={`Sobre ${label}`}>{help}</InfoTip></span>
    <strong>{value == null ? "Indisponível" : money(value)}</strong>
    {hint && <small>{hint}</small>}
  </article>
}

function CostChart({ summary }) {
  const rows = [
    ["Estimado", summary?.estimatedCostAmount],
    ["Requisitado aprovado", summary?.approvedRequisitionAmount],
    ["Comprometido em pedidos", summary?.committedOrderAmount],
    ["Realizado", summary?.realizedAmount],
    ["Medido", summary?.measuredCostAmount],
  ]
  const max = Math.max(1, ...rows.map(([, value]) => Number(value) || 0))
  return <article className={styles.chart}>
    <h3>Custos da obra</h3>
    <p>Barras proporcionais ao maior valor. Indicadores independentes; não some os valores.</p>
    <div className={styles.rows}>{rows.map(([label, value]) => <div className={styles.row} key={label}>
      <div><span>{label}</span><strong>{value == null ? "Indisponível" : money(value)}</strong></div>
      <progress max={max} value={Math.max(0, Number(value) || 0)}
        aria-label={label} aria-valuetext={value == null ? "Indisponível" : money(value)} />
    </div>)}</div>
  </article>
}

export function ProjectSummaryDashboard({ summary, schedulePhases }) {
  const [period, setPeriod] = useState("12")
  const invoices = summary?.invoices
  const allMonths = invoices?.monthly ?? []
  const lastMonth = allMonths.at(-1)?.month
  const endIndex = lastMonth ? Number(lastMonth.slice(0, 4)) * 12 + Number(lastMonth.slice(5)) - 1 : 0
  const startIndex = period === "all" && allMonths.length
    ? Number(allMonths[0].month.slice(0, 4)) * 12 + Number(allMonths[0].month.slice(5)) - 1
    : endIndex - Number(period) + 1
  const months = lastMonth ? Array.from({ length: endIndex - startIndex + 1 }, (_, index) => {
    const offset = startIndex + index
    const key = `${Math.floor(offset / 12)}-${String(offset % 12 + 1).padStart(2, "0")}`
    return allMonths.find((item) => item.month === key) ?? { month: key, gross_amount: 0, invoices_count: 0 }
  }) : []
  const max = Math.max(1, ...months.map((item) => Number(item.gross_amount)))
  const width = Math.max(480, months.length * 64)
  const slot = width / Math.max(1, months.length)
  const balance = invoices && summary?.realizedAmount != null
    ? Number(invoices.gross_amount) - Number(summary.realizedAmount) : null

  return <section className={styles.dashboard} aria-label="Dashboard da obra">
    {summary?.invoicesError && <p role="status">Faturamento indisponível: {summary.invoicesError} Use Recarregar para tentar novamente.</p>}
    {invoices && <>
      <h3>Faturamento da obra</h3>
      <div className={styles.metrics}>
        <Metric label="Faturado bruto" value={invoices.gross_amount} help={FIELD_HELP.gross} hint={`${invoices.invoices_count} nota(s) disponível(is)`} />
        <Metric label="Faturado líquido" value={invoices.net_amount} help={FIELD_HELP.net} />
        <Metric label="Recebido das notas" value={invoices.received_amount} help={FIELD_HELP.received} />
        <Metric label="A receber das notas" value={invoices.open_amount} help={FIELD_HELP.open}
          hint={invoices.overdue_amount == null ? "Sem acesso ao financeiro" : `${money(invoices.overdue_amount)} vencido(s)`} />
        <Metric label="Faturado menos realizado" value={balance} help={FIELD_HELP.balance} hint="comparativo gerencial" />
        <Metric label="Notas canceladas" value={invoices.canceled_amount} help={FIELD_HELP.canceled} hint={`${invoices.canceled_count} nota(s), fora dos totais`} />
      </div>
      {invoices.without_receivable_count > 0 && <p role="status">{invoices.without_receivable_count} nota(s) sem título ativo acessível. Confira em Notas fiscais; o faturamento não é automaticamente um recebimento.</p>}
      {invoices.missing_values_count > 0 && <p role="status">{invoices.missing_values_count} nota(s) com valores incompletos ou inconsistentes no XML. Confira os documentos; o líquido está indisponível.</p>}
    </>}
    <div className={styles.charts}>
      {invoices && <article className={styles.chart}>
        <div className={styles.heading}><h3>Faturamento por mês</h3>
          <label>Período<select value={period} onChange={(event) => setPeriod(event.target.value)}>
            <option value="6">6 meses</option><option value="12">12 meses</option><option value="all">Todo o histórico</option>
          </select></label>
        </div>
        <p>Bruto por emissão · período encerrado no último mês com nota disponível.</p>
        {months.length ? <>
          <div className={styles.chartScroll} tabIndex={0} role="region" aria-label="Gráfico de faturamento mensal com rolagem horizontal">
            <svg width={width} height="230" viewBox={`0 0 ${width} 230`} role="img" aria-label="Faturamento bruto mensal. Valores disponíveis também na tabela abaixo.">
              {[0, 1, 2, 3].map((line) => <line key={line} x1="0" x2={width} y1={30 + line * 50} y2={30 + line * 50} className={styles.gridLine} />)}
              {months.map((item, index) => {
                const height = Number(item.gross_amount) / max * 140
                const x = index * slot + slot / 2
                return <g key={item.month}>
                  <rect x={x - 14} y={180 - height} width="28" height={height} rx="5" className={styles.bar}>
                    <title>{monthLabel(item.month)}: {money(item.gross_amount)} · {item.invoices_count} nota(s)</title>
                  </rect>
                  <text x={x} y={170 - height} textAnchor="middle" className={styles.chartValue}>{compact(Number(item.gross_amount))}</text>
                  <text x={x} y="208" textAnchor="middle" className={styles.chartLabel}>{monthLabel(item.month)}</text>
                </g>
              })}
            </svg>
          </div>
          <details><summary>Ver valores mensais</summary><div className={styles.chartScroll}>
            <table><thead><tr><th>Mês</th><th>Notas</th><th>Faturado bruto</th></tr></thead>
              <tbody>{months.map((item) => <tr key={item.month}><td>{monthLabel(item.month)}</td><td>{item.invoices_count}</td><td>{money(item.gross_amount)}</td></tr>)}</tbody>
            </table>
          </div></details>
        </> : <p>Nenhuma nota disponível com data de emissão para exibir.</p>}
        {invoices.undated_count > 0 && <p>{invoices.undated_count} nota(s) sem emissão: incluídas nos indicadores, fora do gráfico.</p>}
      </article>}
      <CostChart summary={summary} />
      <article className={styles.chart}>
        <h3>Avanço por etapa</h3>
        <p>Percentual registrado no cronograma; não representa avanço financeiro.</p>
        {schedulePhases.length ? <div className={styles.phaseList}>{schedulePhases.map((phase) => <div className={styles.row} key={phase.id}>
          <div><span>{phase.name}</span><strong>{phase.progressPercent}%</strong></div>
          <progress max="100" value={phase.progressPercent} aria-label={`Avanço de ${phase.name}`} />
        </div>)}</div> : <p>Cadastre etapas no Cronograma para acompanhar a execução.</p>}
      </article>
    </div>
  </section>
}
