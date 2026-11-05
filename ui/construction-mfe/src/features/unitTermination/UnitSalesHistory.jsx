import { useCallback, useEffect, useRef, useState } from "react"
import { RotateCcw } from "lucide-react"

import appStyles from "../../App.module.css"
import styles from "./unitTermination.module.css"
import {
  listConstructionUnitSales, listUnitBuyerHistory, listUnitTransfers,
  reactivateConstructionUnitTermination, retryUnitTransfer,
} from "../../services/constructionApi.js"
import { formatBRL as money } from "../../utils/currencyInput.js"
import { formatBusinessDateTime } from "../../utils/brazilDate.js"
import { buildUnitHistoryRows, unitTransferStatusLabels } from "./unitHistory.js"

export function findReactivableSale({ sales, unitStatus }) {
  if (unitStatus !== "available" || sales.some((sale) => sale.status === "ACTIVE")) return null
  const latest = sales
    .filter((sale) => sale.source !== "LEGACY" || sale.transferredFromSaleId || sale.transferredAt)
    .reduce(
      (current, sale) => (current == null || Number(sale.sequence) > Number(current.sequence) ? sale : current),
      null,
    )
  if (latest?.status !== "TERMINATED" || latest.source !== "NATIVE" || !latest.externalTerminationId) return null
  return latest
}

export function UnitSalesHistory({ bridge, unit, people = [], onEnsurePeople, requestConfirm, onChanged }) {
  const [sales, setSales] = useState([])
  const [buyers, setBuyers] = useState([])
  const [transfers, setTransfers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const generation = useRef(0)
  const previousTransfers = useRef(new Map())
  const changed = useRef(onChanged)
  changed.current = onChanged
  const canReactivate = Boolean(bridge?.canDelete?.("construction_unit_termination"))
  const canRetry = Boolean(bridge?.canUpdate?.("construction_units") && bridge?.canUpdate?.("receivable"))
  const personName = (personId) => people.find((person) => person.id === personId)?.name
  const amount = (value) => value == null ? "-" : money(value)

  const load = useCallback(async () => {
    const current = ++generation.current
    setLoading(true)
    const results = await Promise.allSettled([
      listUnitBuyerHistory({ bridge, unitId: unit.id }),
      listConstructionUnitSales({ bridge, unitId: unit.id }),
      listUnitTransfers({ bridge, unitId: unit.id }),
    ])
    if (current !== generation.current) return
    const [buyerResult, saleResult, transferResult] = results
    const errors = []
    const labels = ["moradores", "vendas", "trocas de unidade"]
    results.forEach((result, index) => {
      if (result.status === "rejected") {
        errors.push(`Não foi possível carregar ${labels[index]}: ${result.reason?.message || "tente atualizar"}.`)
      }
    })
    setError(errors.join(" "))
    if (buyerResult.status === "fulfilled") setBuyers(buyerResult.value.items)
    if (saleResult.status === "fulfilled") {
      setSales(saleResult.value)
      void onEnsurePeople?.(
        saleResult.value.flatMap((sale) => [sale.buyerPersonId, sale.secondaryBuyerPersonId, sale.brokerPersonId])
      )
    }
    let completed = false
    if (transferResult.status === "fulfilled") {
      const items = transferResult.value.items
      completed = items.some((item) => item.status === "published"
        && previousTransfers.current.has(item.transfer_id)
        && previousTransfers.current.get(item.transfer_id) !== "published")
      previousTransfers.current = new Map(items.map((item) => [item.transfer_id, item.status]))
      setTransfers(items)
    }
    setLoading(false)
    if (completed) {
      try {
        await changed.current?.()
      } catch (requestError) {
        bridge?.feedback?.error?.(requestError.message ?? "A troca concluiu, mas os detalhes não foram atualizados.")
      }
    }
  }, [bridge, unit.id, onEnsurePeople])

  useEffect(() => {
    void load()
    return () => { generation.current += 1 }
  }, [load, unit.currentSaleId, unit.buyerPersonId, unit.status])

  useEffect(() => {
    if (loading || !transfers.some((item) => item.status !== "published")) return undefined
    const timer = setTimeout(() => { void load() }, 5000)
    return () => clearTimeout(timer)
  }, [transfers, loading, load])

  const reactivate = (sale) => {
    requestConfirm({
      title: `Reativar o distrato da venda ${sale.sequence}`,
      message:
        "As parcelas baixadas por distrato voltam a ficar em aberto, o contrato é reativado, o lançamento do " +
        "distrato é estornado e a unidade volta para o comprador. Só é possível se o saldo credor não foi usado.",
      confirmLabel: "Reativar distrato",
      danger: false,
      run: async () => {
        try {
          await reactivateConstructionUnitTermination({ bridge, unitId: unit.id, reason: "Reativação do distrato" })
          bridge?.feedback?.success?.("Distrato reativado. A venda voltou a valer.")
          if (changed.current) await changed.current()
          else await load()
        } catch (requestError) {
          bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível reativar o distrato.")
        }
      },
    })
  }

  const retry = async (item) => {
    setLoading(true)
    try {
      await retryUnitTransfer({ bridge, unitId: unit.id, transferId: item.transfer_id })
      await load()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError.message ?? "Não foi possível reenviar a integração.")
      setLoading(false)
    }
  }

  const reactivableSale = canReactivate ? findReactivableSale({ sales, unitStatus: unit.status }) : null
  const rows = buildUnitHistoryRows({ buyers, sales, transfers, unitId: unit.id })

  return (
    <section className={appStyles.tableCard} aria-label="Histórico da unidade">
      <div className={appStyles.tableWrapper}>
        <table className={styles.historyTable}>
          <caption>
            <div className={appStyles.tableHeaderRow}>
              <span>Histórico da unidade — {unit.code}</span>
              <button type="button" className={appStyles.secondaryButton} onClick={load} disabled={loading}>
                {loading ? "Atualizando..." : "Atualizar"}
              </button>
            </div>
          </caption>
          <thead>
            <tr>
              <th>Cliente</th><th>Inclusão</th><th>Exclusão</th><th>Movimentação</th><th>Financeiro</th>
              <th aria-label="Ações" />
            </tr>
          </thead>
          <tbody>
            {error && <tr><td colSpan={6} role="alert">{error}</td></tr>}
            {!rows.length ? (
              <tr><td colSpan={6}>{loading ? "Carregando histórico..." : "Nenhum histórico registrado."}</td></tr>
            ) : rows.map((row) => (
              <tr key={row.id}>
                <td title={row.originLabel === "ONAVE" ? "Registro criado neste sistema"
                  : `Origem do registro: ${row.originLabel || "não informada"}`}>
                  {row.buyerName || personName(row.buyerPersonId) || "Cliente não identificado no histórico"}
                </td>
                <td>
                  {formatBusinessDateTime(row.includedAt)}
                  {row.includedAt && <div className={appStyles.rowSecondaryText}>
                    {row.includedBy || "Responsável não informado"}
                  </div>}
                </td>
                <td>
                  {formatBusinessDateTime(row.excludedAt)}
                  {row.excludedAt && <div className={appStyles.rowSecondaryText}>
                    {row.excludedBy || "Responsável não informado"}
                  </div>}
                </td>
                <td>
                  <div className={styles.historyDetails}>
                    {row.sales.map((sale) => (
                      <div key={sale.id}>
                        <strong>Venda {sale.sequence} · </strong>
                        <span className={`${appStyles.statusPill} ${sale.status === "ACTIVE"
                          ? appStyles.statussold : appStyles.statusterminated}`}>
                          {sale.status === "ACTIVE" ? "Vigente" : sale.status === "TRANSFERRED"
                            ? "Transferida" : "Distratada"}
                        </span>
                        {sale.status === "TERMINATED" && <div>
                          Distrato em: {formatBusinessDateTime(sale.terminationDate || sale.terminatedAt)}
                        </div>}
                        {sale.terminationReason && <div>Motivo: {sale.terminationReason}</div>}
                      </div>
                    ))}
                    {row.transfers.map((item) => (
                      <div key={item.transfer_id}>
                        <strong>{item.outgoing
                          ? "Comprador transferido desta unidade" : "Comprador recebido nesta unidade"}</strong>
                        <div><strong>Origem:</strong> {item.source_label}</div>
                        <div><strong>Destino:</strong> {item.target_label}</div>
                        <div>{formatBusinessDateTime(item.occurred_at)} · {
                          unitTransferStatusLabels[item.status] ?? item.status
                        }</div>
                        <div>Motivo: {item.reason}</div>
                      </div>
                    ))}
                    {!row.sales.length && !row.transfers.length && (row.reason || "Passagem do comprador")}
                  </div>
                </td>
                <td>
                  {row.sales.length ? row.sales.map((sale) => (
                    <div key={sale.id} className={styles.historyAmounts}>
                      <strong>Venda {sale.sequence}</strong>
                      <div>Vendida em: {formatBusinessDateTime(sale.soldAt)}</div>
                      <div>Preço: {amount(sale.salePrice)}</div>
                      <div>Pago: {amount(sale.paidAmount)}</div>
                      <div>A devolver: {amount(sale.refundAmount)}</div>
                    </div>
                  )) : "-"}
                </td>
                <td>
                  {row.sales.filter((sale) => reactivableSale?.id === sale.id).map((sale) => (
                    <button key={sale.id} type="button" className={appStyles.iconButton} disabled={loading}
                      title="Reativar distrato" aria-label="Reativar distrato" onClick={() => reactivate(sale)}>
                      <RotateCcw size={16} aria-hidden="true" />
                    </button>
                  ))}
                  {canRetry && row.transfers.filter((item) => ["failed", "dead_letter"].includes(item.status))
                    .map((item) => (
                      <button key={item.transfer_id} type="button" className={appStyles.secondaryButton}
                        disabled={loading} onClick={() => retry(item)}>Tentar novamente</button>
                    ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
