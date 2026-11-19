import { useCallback, useEffect, useState } from "react"
import { ExternalLink, Link2, ListChecks, RefreshCw } from "lucide-react"
import { InfoTip } from "../../components/InfoTip"

import appStyles from "../../App.module.css"
import styles from "./SharedPayables.module.css"
import { payableStatusLabel } from "../measurementActions"
import { listSharedPayables } from "../../services/constructionApi"
import { SharedPayableLinkModal, money } from "./SharedPayableLinkModal"
import { ZeroValueOrders, day } from "./ZeroValueOrders"

const openPayable = (bridge, payable, onSaved, projectId) => {
  const path = `/accounts-payable/${payable.id}/edit?${new URLSearchParams({ project_id: projectId })}`
  if (bridge.openPayable) bridge.openPayable(path, { onSaved })
  else window.open(path, "_blank", "noopener")
}

function SharedPayableOrdersModal({ bridge, projectId, project, payable, onClose }) {
  const [selected] = useState(() => new Set())
  const Modal = bridge?.components?.Modal
  const content = <div className={styles.section}>
    {project && <p className={styles.notice}><strong>Obra: {project.name}</strong>{project.code ? ` · ${project.code}` : ""}</p>}
    <p className={styles.notice}>Consulta das OS vinculadas. Depois de lançar o título, as OS não podem ser removidas manualmente.</p>
    <ZeroValueOrders bridge={bridge} projectId={projectId} payableDocumentId={payable.id}
      selected={selected} readOnly />
  </div>
  if (Modal) return <Modal isOpen title={`OS cobertas pelo título ${payable.documentNumber ?? "sem número"}`}
    onClose={onClose} closeOnEsc closeOnOverlayClick dialogMaxWidth="1100px"
    footer={<button type="button" className={appStyles.secondaryButton} onClick={onClose}>Fechar</button>}>
    {content}
  </Modal>
  return (
    <div className={appStyles.modalOverlay} role="presentation" onClick={onClose}>
      <section className={`${appStyles.modalCard} ${styles.wideModal}`} role="dialog" aria-modal="true"
        aria-label={`OS cobertas pelo título ${payable.documentNumber ?? ""}`}
        onClick={(event) => event.stopPropagation()}>
        <header className={appStyles.modalHeader}>
          <h3>OS cobertas pelo título {payable.documentNumber ?? "sem número"} · {payable.personName || "Fornecedor"}</h3>
          <button type="button" className={appStyles.closeButton} onClick={onClose}>Fechar</button>
        </header>
        <div className={appStyles.modalBody}>
          {content}
        </div>
      </section>
    </div>
  )
}

export function SharedPayablesCardTitle() {
  return <>
    Pagamentos da empreitada
    <InfoTip floating label="Sobre os documentos da empreitada e as OS cobertas">
      Esta lista reúne os títulos vinculados às OS do contrato aberto, incluindo notas fiscais e documentos não fiscais.
      Vincular OS preserva o tipo e o número cadastrados em Contas a Pagar. A coluna Documento mostra o número
      e o tipo original. Número não informado indica que o título está sem número no cadastro.
      Criar título e Vincular título existente usam o contrato aberto. Consulte as OS de cada documento nas ações da linha.
    </InfoTip>
  </>
}

export function SharedPayablesSection({
  bridge, projectId, project, renderActions, contractActions,
  subcontractId = "", withoutContract = false, reloadKey = 0, onChanged,
}) {
  const canUpdate = Boolean(bridge?.canUpdate?.("construction_measurements"))
  const canReadPayable = Boolean(bridge?.canRead?.("accounts_payable"))
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [linkTarget, setLinkTarget] = useState(null)
  const [ordersTarget, setOrdersTarget] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await listSharedPayables({ bridge, projectId, subcontractId, withoutContract }))
      setError("")
    } catch (failure) {
      setError(failure?.message ?? "Não foi possível buscar os títulos da empreitada.")
    } finally {
      setLoading(false)
    }
  }, [bridge, projectId, subcontractId, withoutContract])

  useEffect(() => {
    load()
  }, [load, reloadKey])

  const refreshPayments = async () => {
    await Promise.all([load(), onChanged?.()])
  }

  return (
    <section className={styles.section}>
      {renderActions(<>
        <button
          type="button"
          className={styles.iconButton}
          onClick={load}
          disabled={loading}
          title="Atualizar lista"
          aria-label="Atualizar lista"
        >
          <RefreshCw size={16} aria-hidden="true" />
        </button>
        {contractActions}
        {canUpdate && !contractActions ? (
          <button type="button" className={appStyles.primaryButton} onClick={() => setLinkTarget({ payable: null })}>
            <Link2 size={16} aria-hidden="true" />
            Vincular OS sem valor
          </button>
        ) : null}
      </>)}
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
      <div className={styles.tableWrapper}>
        {loading ? (
          <p className={styles.empty}>Buscando títulos da empreitada...</p>
        ) : !rows.length ? (
          <p className={styles.empty}>{subcontractId ? "Nenhum título vinculado às OS deste contrato." : withoutContract ? "Nenhum título vinculado a OS sem contrato." : "Nenhum título de empreitada vinculado a OS desta obra."}</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Documento</th>
                <th>Fornecedor</th>
                <th>Emissão</th>
                <th>Valor</th>
                <th>Pagamento</th>
                <th>OS</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    {row.documentNumber ? `Nº ${row.documentNumber}` : "Número não informado"}
                    <small>{row.documentTypeLabel || row.description || ""}</small>
                  </td>
                  <td>{row.personName || "-"}</td>
                  <td>{day(row.issueDate)}</td>
                  <td>{money(row.totalAmount)}</td>
                  <td>{payableStatusLabel(row.status)}</td>
                  <td>
                    {row.coveredCount}
                  </td>
                  <td>
                    <div className={styles.rowActions}>
                      <button
                        type="button"
                        className={styles.iconButton}
                        onClick={() => setOrdersTarget(row)}
                        title="Ver OS cobertas"
                        aria-label={`Ver OS cobertas pelo título ${row.documentNumber ?? ""}`}
                      >
                        <ListChecks size={16} aria-hidden="true" />
                      </button>
                      {canUpdate && !row.contractCoveredCount ? (
                        <button
                          type="button"
                          className={styles.iconButton}
                          onClick={() => setLinkTarget({ payable: row })}
                          title="Vincular mais OS"
                          aria-label={`Vincular mais OS ao título ${row.documentNumber ?? ""}`}
                        >
                          <Link2 size={16} aria-hidden="true" />
                        </button>
                      ) : null}
                      {canReadPayable ? (
                        <button
                          type="button"
                          className={styles.iconButton}
                          onClick={() => openPayable(bridge, row, refreshPayments, projectId)}
                          title="Ver título no ERP"
                          aria-label={`Ver o título ${row.documentNumber ?? ""} no ERP`}
                        >
                          <ExternalLink size={16} aria-hidden="true" />
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {linkTarget ? (
        <SharedPayableLinkModal
          bridge={bridge}
          projectId={projectId}
          initialPayable={linkTarget.payable}
          onClose={() => setLinkTarget(null)}
          onLinked={() => {
            setLinkTarget(null)
            refreshPayments()
          }}
        />
      ) : null}
      {ordersTarget ? (
        <SharedPayableOrdersModal
          bridge={bridge}
          projectId={projectId}
          project={project}
          payable={ordersTarget}
          onClose={() => setOrdersTarget(null)}
        />
      ) : null}
    </section>
  )
}
