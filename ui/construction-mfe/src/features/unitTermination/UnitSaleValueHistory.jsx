import { useEffect, useState } from "react"
import { Pagination as LocalPagination } from "../../components/Pagination.jsx"
import { listUnitSaleValueHistory } from "../../services/constructionApi.js"
import { formatBusinessDateTime } from "../../utils/brazilDate.js"
import appStyles from "../../App.module.css"
import styles from "./UnitSaleValueHistory.module.css"

const money = (value) => value == null ? "Não informado" : new Intl.NumberFormat("pt-BR", {
  style: "currency", currency: "BRL",
}).format(Number(value))

const fields = {
  sale_price: "Preço da venda", discount_amount: "Desconto", government_subsidy: "Subsídio",
  fgts: "FGTS", financing: "Financiamento", down_payment: "Entrada", commission_offset: "Sinal",
  documentation_total: "Total da documentação", balance: "Saldo da composição",
  composition_difference: "Diferença de composição para conferência",
}

const changesFor = (item) => {
  const changes = Object.entries(fields).filter(([key]) => item.old_data[key] !== item.new_data[key])
    .map(([key, label]) => ({ key, label, before: money(item.old_data[key]), after: money(item.new_data[key]) }))
  const previous = new Map((item.old_data.documentations ?? []).map((row) => [row.documentation_type_id, row]))
  const current = new Map((item.new_data.documentations ?? []).map((row) => [row.documentation_type_id, row]))
  for (const id of new Set([...previous.keys(), ...current.keys()])) {
    const before = previous.get(id)
    const after = current.get(id)
    if (before?.amount !== after?.amount || before?.name !== after?.name) {
      changes.push({ key: `documentation-${id}`, label: `Documentação: ${after?.name ?? before?.name}`,
        before: before ? `${before.name}: ${money(before.amount)}` : "Não informada",
        after: after ? `${after.name}: ${money(after.amount)}` : "Removida" })
    }
  }
  return changes
}

export function UnitSaleValueHistory({ bridge, unit }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [direction, setDirection] = useState("desc")
  const [refresh, setRefresh] = useState(0)
  const Pagination = bridge?.components?.Pagination ?? LocalPagination

  useEffect(() => {
    let active = true
    setLoading(true)
    setFailed(false)
    setData(null)
    listUnitSaleValueHistory({ bridge, unitId: unit.id, page, pageSize, direction })
      .then((result) => { if (active) setData(result) })
      .catch((error) => {
        if (!active) return
        setFailed(true)
        bridge?.feedback?.error?.(error.message ?? "Não foi possível carregar as alterações de valores.")
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [bridge, unit.id, unit.updatedAt, page, pageSize, direction, refresh])

  return (
    <section className={styles.panel} aria-label="Alterações de valores">
      <div className={appStyles.tableHeaderRow}>
        <h2>Alterações de valores</h2>
        <div className={styles.actions}>
          <label className={styles.order}>
            Ordem
            <select value={direction} disabled={loading} onChange={(event) => {
              setDirection(event.target.value)
              setPage(1)
            }}>
              <option value="desc">Mais recentes primeiro</option>
              <option value="asc">Mais antigas primeiro</option>
            </select>
          </label>
          <button type="button" className={appStyles.secondaryButton} disabled={loading}
            onClick={() => setRefresh((value) => value + 1)}>Atualizar valores</button>
        </div>
      </div>
      <div className={appStyles.tableWrapper} aria-busy={loading}>
        {!data?.items.length ? (
          <p className={styles.empty}>{loading ? "Carregando alterações..." : failed
            ? "Consulta indisponível. Use Atualizar valores para tentar novamente."
            : "Nenhuma alteração de valores registrada. O histórico começa a partir desta atualização."}</p>
        ) : data.items.map((item) => (
          <article key={item.id} className={styles.event}>
            <h3>Venda {item.sale_sequence} · {formatBusinessDateTime(item.changed_at)}</h3>
            <p><strong>Responsável:</strong> {item.actor_name ?? item.actor_user_id ?? "Usuário não identificado"}</p>
            <p className={styles.reason}><strong>Motivo:</strong> {item.reason}</p>
            <dl className={styles.changes}>
              {changesFor(item).map((change) => (
                <div key={change.key} className={styles.change}>
                  <dt>{change.label}</dt>
                  <dd><span>Antes</span> {change.before}</dd>
                  <dd><span>Depois</span> {change.after}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>
      <div className={appStyles.paginationSlot}>
        <Pagination currentPage={page} totalPages={data?.total_pages ?? 1} totalItems={data?.total ?? 0}
          pageSize={pageSize} isLoading={loading} onPageChange={setPage} onPageSizeChange={setPageSize}
          className={styles.pagination} />
      </div>
    </section>
  )
}
