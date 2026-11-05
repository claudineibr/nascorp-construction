const instant = (value) => value ? Date.parse(value) : NaN
const sameInstant = (first, second) => Number.isFinite(instant(first)) && instant(first) === instant(second)
const unique = (items) => items.length === 1 ? items[0] : null
const compareInstants = (first, second) => {
  const firstDate = instant(first)
  const secondDate = instant(second)
  if (!Number.isFinite(firstDate)) return Number.isFinite(secondDate) ? -1 : 0
  if (!Number.isFinite(secondDate)) return 1
  return firstDate - secondDate
}

export const unitTransferStatusLabels = {
  pending: "Integração financeira pendente",
  failed: "Integração aguardando nova tentativa",
  dead_letter: "Integração precisa de nova tentativa",
  published: "Concluída",
}

export function buildUnitHistoryRows({ buyers, sales, transfers, unitId }) {
  const rows = buyers.map((item) => ({
    id: `buyer:${item.id}`,
    buyerPersonId: item.buyer_person_id,
    buyerName: item.buyer_name,
    originLabel: item.origin_label,
    includedAt: item.included_at,
    includedBy: item.included_by_name,
    excludedAt: item.excluded_at,
    excludedBy: item.excluded_by_name,
    reason: item.reason,
    history: true,
    sales: [],
    transfers: [],
  }))

  for (const sale of sales) {
    const endedAt = sale.status === "TRANSFERRED" ? sale.transferredAt : sale.terminatedAt
    const candidates = rows.filter((row) => row.history && sale.buyerPersonId
      && row.buyerPersonId === sale.buyerPersonId)
    let row = sale.status === "ACTIVE"
      ? unique(candidates.filter((item) => !item.excludedAt))
      : unique(candidates.filter((item) => sameInstant(item.excludedAt, endedAt)))
    if (!row && sale.status !== "ACTIVE") {
      row = unique(candidates.filter((item) => sameInstant(item.includedAt, sale.soldAt)))
    }
    if (!row) {
      row = {
        id: `sale:${sale.id}`, buyerPersonId: sale.buyerPersonId,
        originLabel: sale.source === "LEGACY" ? "Sistema anterior" : "ONAVE",
        includedAt: sale.soldAt,
        excludedAt: sale.status === "ACTIVE" ? null : endedAt || sale.terminationDate,
        sales: [], transfers: [],
      }
      rows.push(row)
    }
    row.sales.push(sale)
  }

  for (const transfer of transfers) {
    const outgoing = transfer.source_unit_id === unitId
    if (!outgoing && transfer.target_unit_id !== unitId) continue
    const bySale = rows.filter((row) => row.sales.some((sale) => outgoing
      ? sale.id === transfer.source_sale_id : sale.transferredFromSaleId === transfer.source_sale_id))
    let row = unique(rows.filter((item) => item.history && sameInstant(
      outgoing ? item.excludedAt : item.includedAt, transfer.occurred_at,
    )))
    if (!row) {
      row = unique(bySale)
    }
    if (!row) {
      row = {
        id: `transfer:${transfer.transfer_id}`, originLabel: "ONAVE",
        includedAt: outgoing ? null : transfer.occurred_at,
        excludedAt: outgoing ? transfer.occurred_at : null,
        sales: [], transfers: [],
      }
      rows.push(row)
    }
    row.transfers.push({ ...transfer, outgoing })
  }

  for (const row of rows) {
    row.transfers.sort((first, second) => compareInstants(first.occurred_at, second.occurred_at))
  }
  return rows.sort((first, second) => compareInstants(
    first.includedAt || first.excludedAt, second.includedAt || second.excludedAt,
  ))
}
