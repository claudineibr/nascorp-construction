import { useCallback, useEffect, useState } from "react"
import { ExternalLink, Link2, ListChecks, RefreshCw } from "lucide-react"
import { InfoTip } from "../../components/InfoTip"

import appStyles from "../../App.module.css"
import styles from "./SharedPayables.module.css"
import { payableStatusLabel } from "../measurementActions"
import { listSharedPayables, unlinkSharedPayable } from "../../services/constructionApi"
import { SharedPayableLinkModal, money } from "./SharedPayableLinkModal"
import { ZeroValueOrders, day } from "./ZeroValueOrders"

const openPayable = (payable) => window.open(`/accounts-payable/${payable.id}/edit`, "_blank", "noopener")

function SharedPayableOrdersModal({ bridge, projectId, payable, canUpdate, onClose, onChanged }) {
  const canRemove = canUpdate && !payable.globalCoveredCount
  const [selected, setSelected] = useState(() => new Set())
  const [reloadKey, setReloadKey] = useState(0)
  const [confirming, setConfirming] = useState(false)
  const [saving, setSaving] = useState(false)

  const remove = async () => {
    if (!canRemove) return
    setSaving(true)
    try {
      const result = await unlinkSharedPayable({
        bridge,
        projectId,
        payableDocumentId: payable.id,
        measurementIds: [...selected],
      })
      bridge?.feedback?.success?.(
        `${result.affected} OS removida(s) do título ${payable.documentNumber ?? "sem número"}. Elas voltam a ficar sem título e podem ir para outro documento.`,
      )
      setSelected(new Set())
      setConfirming(false)
      setReloadKey((value) => value + 1)
      onChanged()
    } catch (removeError) {
      bridge?.feedback?.error?.(removeError?.message ?? "Não foi possível remover as OS da DNF.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={appStyles.modalOverlay} role="presentation" onClick={() => !saving && onClose()}>
      <section
        className={`${appStyles.modalCard} ${styles.wideModal}`}
        role="dialog"
        aria-modal="true"
        aria-label={`OS cobertas pelo título ${payable.documentNumber ?? ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={appStyles.modalHeader}>
          <h3>
            OS cobertas pelo título {payable.documentNumber ?? "sem número"} · {payable.personName || "Fornecedor"}
          </h3>
          <button type="button" className={appStyles.closeButton} onClick={onClose} disabled={saving}>
            Fechar
          </button>
        </header>
        <div className={appStyles.modalBody}>
          {payable.globalCoveredCount ? <p className={styles.notice}>As OS do contrato global só são liberadas ao cancelar o título no ERP.</p> : null}
          <ZeroValueOrders
            bridge={bridge}
            projectId={projectId}
            payableDocumentId={payable.id}
            selected={selected}
            onSelectedChange={setSelected}
            reloadKey={reloadKey}
            disabled={saving || !canRemove}
          />
          <div className={appStyles.modalFooter}>
            <button type="button" className={appStyles.secondaryButton} onClick={onClose} disabled={saving}>
              Fechar
            </button>
            {canRemove ? (
              <button
                type="button"
                className={`${appStyles.secondaryButton} ${appStyles.dangerButton}`}
                onClick={() => setConfirming(true)}
                disabled={!selected.size || saving}
              >
                Remover {selected.size} OS do título
              </button>
            ) : null}
          </div>
        </div>
      </section>
      {confirming ? (
        <div
          className={appStyles.modalOverlay}
          role="presentation"
          onClick={(event) => {
            event.stopPropagation()
            if (!saving) setConfirming(false)
          }}
        >
          <section
            className={appStyles.modalCard}
            role="dialog"
            aria-modal="true"
            aria-label="Remover OS do título"
            onClick={(event) => event.stopPropagation()}
          >
            <header className={appStyles.modalHeader}>
              <h3>Remover OS do título</h3>
            </header>
            <div className={appStyles.modalBody}>
              <p>
                Remover {selected.size} OS do título {payable.documentNumber ?? "sem número"}? O título no ERP não muda; as
                OS voltam a ficar sem título e podem ser vinculadas a outro documento.
              </p>
              <div className={appStyles.modalFooter}>
                <button
                  type="button"
                  className={appStyles.secondaryButton}
                  onClick={() => setConfirming(false)}
                  disabled={saving}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className={`${appStyles.secondaryButton} ${appStyles.dangerButton}`}
                  onClick={remove}
                  disabled={saving}
                >
                  {saving ? "Removendo..." : "Remover"}
                </button>
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}

export function SharedPayablesSection({ bridge, projectId }) {
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
      setRows(await listSharedPayables({ bridge, projectId }))
      setError("")
    } catch (failure) {
      setError(failure?.message ?? "Não foi possível buscar os títulos da empreitada.")
    } finally {
      setLoading(false)
    }
  }, [bridge, projectId])

  useEffect(() => {
    load()
  }, [load])

  return (
    <section className={styles.section}>
      <div className={styles.toolbar}>
        <InfoTip floating label="Sobre os documentos da empreitada e as OS cobertas">
          Esta lista reúne os títulos que pagam as OS da obra, incluindo notas fiscais e documentos não fiscais.
          Vincular OS não altera o tipo nem o número cadastrado no Contas a Pagar. A coluna Documento mostra o número
          e o tipo original; Número não informado indica que o título está sem número no cadastro.
          Os títulos das medições de contrato são vinculados no próprio contrato e também aparecem aqui.
        </InfoTip>
        <div className={styles.toolbarActions}>
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
          {canUpdate ? (
            <button type="button" className={appStyles.primaryButton} onClick={() => setLinkTarget({ payable: null })}>
              <Link2 size={16} aria-hidden="true" />
              Vincular OS sem valor
            </button>
          ) : null}
        </div>
      </div>
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
      <div className={styles.tableWrapper}>
        {loading ? (
          <p className={styles.empty}>Buscando títulos da empreitada...</p>
        ) : !rows.length ? (
          <p className={styles.empty}>Nenhum título de empreitada vinculado a OS desta obra.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Documento</th>
                <th>Fornecedor</th>
                <th>Emissão</th>
                <th>Valor</th>
                <th>Situação</th>
                <th>OS cobertas</th>
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
                    {row.contractCoveredCount ? <small>do contrato</small> : null}
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
                          onClick={() => openPayable(row)}
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
            load()
          }}
        />
      ) : null}
      {ordersTarget ? (
        <SharedPayableOrdersModal
          bridge={bridge}
          projectId={projectId}
          payable={ordersTarget}
          canUpdate={canUpdate}
          onClose={() => setOrdersTarget(null)}
          onChanged={load}
        />
      ) : null}
    </section>
  )
}
