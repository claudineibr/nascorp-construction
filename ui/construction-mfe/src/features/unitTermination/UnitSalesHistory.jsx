import { useCallback, useEffect, useState } from "react"
import { RotateCcw } from "lucide-react"

import appStyles from "../../App.module.css"
import styles from "./unitTermination.module.css"
import { listConstructionUnitSales, reactivateConstructionUnitTermination } from "../../services/constructionApi.js"
import { formatBRL as money } from "../../utils/currencyInput.js"
import { formatBusinessDate } from "../../utils/brazilDate.js"

export function findReactivableSale({ sales, unitStatus }) {
  if (unitStatus !== "available" || sales.some((sale) => sale.status === "ACTIVE")) return null
  return (
    sales
      .filter((sale) => sale.status === "TERMINATED" && sale.source === "NATIVE" && sale.externalTerminationId)
      .sort((first, second) => String(second.terminatedAt ?? "").localeCompare(String(first.terminatedAt ?? "")))[0] ??
    null
  )
}

export function UnitSalesHistory({ bridge, unit, people = [], onEnsurePeople, requestConfirm, onChanged }) {
  const [sales, setSales] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const canReactivate = Boolean(bridge?.canDelete?.("construction_unit_termination"))
  const personName = (personId) => people.find((person) => person.id === personId)?.name ?? (personId ? "Pessoa cadastrada" : "-")

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const items = await listConstructionUnitSales({ bridge, unitId: unit.id })
      setSales(items)
      void onEnsurePeople?.(
        items.flatMap((sale) => [sale.buyerPersonId, sale.secondaryBuyerPersonId, sale.brokerPersonId])
      )
    } catch (requestError) {
      setError(requestError?.message ?? "Não foi possível carregar o histórico de vendas.")
    } finally {
      setLoading(false)
    }
  }, [bridge, unit.id, onEnsurePeople])

  useEffect(() => {
    void load()
  }, [load])

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
          await onChanged?.()
        } catch (requestError) {
          bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível reativar o distrato.")
        }
      },
    })
  }

  const reactivableSale = canReactivate ? findReactivableSale({ sales, unitStatus: unit.status }) : null

  return (
    <section className={appStyles.tableCard}>
      <div className={appStyles.tableWrapper}>
        <table className={styles.historyTable}>
          <thead>
            <tr>
              <th>Venda</th>
              <th>Comprador</th>
              <th>Vendida em</th>
              <th>Preço</th>
              <th>Situação</th>
              <th>Distrato</th>
              <th>Motivo</th>
              <th className={appStyles.textRight}>Pago</th>
              <th className={appStyles.textRight}>A devolver</th>
              <th aria-label="Ações" />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10}>Carregando histórico...</td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={10}>{error}</td>
              </tr>
            ) : !sales.length ? (
              <tr>
                <td colSpan={10}>Nenhuma venda registrada para esta unidade.</td>
              </tr>
            ) : (
              sales.map((sale) => (
                <tr key={sale.id}>
                  <td>
                    {sale.sequence}
                    {sale.source === "LEGACY" ? <div className={appStyles.rowSecondaryText}>Importada</div> : null}
                  </td>
                  <td>{personName(sale.buyerPersonId)}</td>
                  <td>{formatBusinessDate(sale.soldAt)}</td>
                  <td>{money(sale.salePrice)}</td>
                  <td>
                    <span className={`${appStyles.statusPill} ${sale.status === "ACTIVE" ? appStyles.statussold : appStyles.statusterminated}`}>
                      {sale.status === "ACTIVE" ? "Vigente" : "Distratada"}
                    </span>
                  </td>
                  <td>{formatBusinessDate(sale.terminationDate || sale.terminatedAt)}</td>
                  <td>{sale.terminationReason || "-"}</td>
                  <td className={appStyles.textRight}>{money(sale.paidAmount)}</td>
                  <td className={appStyles.textRight}>{money(sale.refundAmount)}</td>
                  <td>
                    {reactivableSale?.id === sale.id ? (
                      <button
                        type="button"
                        className={appStyles.iconButton}
                        title="Reativar distrato"
                        aria-label="Reativar distrato"
                        onClick={() => reactivate(sale)}
                      >
                        <RotateCcw size={16} aria-hidden="true" />
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
