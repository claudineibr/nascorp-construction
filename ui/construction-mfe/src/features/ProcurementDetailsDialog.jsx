import { UnitBankSlipDialogFrame } from "./UnitBankSlipsDialog.jsx"
import appStyles from "../App.module.css"
import styles from "./ProcurementDetailsDialog.module.css"

const orderStatuses = {
  DRAFT: "Rascunho", OPEN: "Aberto", PARTIALLY_RECEIVED: "Recebido parcialmente",
  RECEIVED: "Recebido", CLOSED: "Encerrado", CANCELED: "Cancelado",
}
const quantities = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 4 })
const quantity = (value) => value == null || value === "" ? "—" : Number.isFinite(Number(value)) ? quantities.format(Number(value)) : String(value)

export function ProcurementDetailsDialog({ bridge, request, statusLabel, integrationLabel, estimatedAmount, neededBy, onClose }) {
  const orders = request.externalOrders?.length ? request.externalOrders : (request.externalOrderNumbers ?? []).map((number) => ({ number }))
  return <UnitBankSlipDialogFrame bridge={bridge} title={`Requisição ${request.code}`} onClose={onClose} dialogMaxWidth={1320}
    footer={<button type="button" className={appStyles.secondaryButton} onClick={onClose}>Fechar</button>}>
    <div className={styles.content}>
      <h3 className={styles.title}>{request.title}</h3>
      <dl className={styles.summary}>
        <div><dt>Situação</dt><dd>{statusLabel}</dd></div>
        <div><dt>Valor estimado</dt><dd>{estimatedAmount}</dd></div>
        <div><dt>Necessidade</dt><dd>{neededBy}</dd></div>
        <div><dt>Integração ERP</dt><dd>{integrationLabel}</dd></div>
      </dl>
      <section className={styles.section}>
        <h4>Descrição e orientações</h4>
        <p className={styles.description}>{request.description || "Sem descrição adicional."}</p>
      </section>
      {request.rejectionReason && <section className={styles.section}>
        <h4>Motivo da rejeição</h4>
        <p className={styles.description}>{request.rejectionReason}</p>
      </section>}
      {orders.length > 0 && <section className={styles.section}>
        <h4>Pedidos de compra</h4>
        <ul className={styles.orders}>
          {orders.map((order) => <li key={order.id ?? order.number}>
            {order.number}{order.status ? ` · ${orderStatuses[order.status] ?? "Em andamento"}` : ""}
          </li>)}
        </ul>
      </section>}
      <section className={styles.section}>
        <h4>Saldo por item</h4>
        {request.externalItems?.length ? <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead><tr><th>Item</th><th>Descrição</th><th>Solicitado</th><th>Em pedido</th><th>Reservado</th><th>Disponível</th></tr></thead>
            <tbody>{request.externalItems.map((item) => <tr key={item.id ?? item.sequence_number}>
              <td>{item.sequence_number}</td>
              <td>{item.description || `Item ${item.sequence_number}`}{item.unit_of_measure && <small>{item.unit_of_measure}</small>}</td>
              <td>{quantity(item.quantity)}</td><td>{quantity(item.qty_ordered)}</td>
              <td>{quantity(item.qty_reserved ?? 0)}</td><td>{quantity(item.qty_available)}</td>
            </tr>)}</tbody>
          </table>
        </div> : <p className={styles.muted}>Sem saldo por item informado pela integração ERP.</p>}
      </section>
    </div>
  </UnitBankSlipDialogFrame>
}
