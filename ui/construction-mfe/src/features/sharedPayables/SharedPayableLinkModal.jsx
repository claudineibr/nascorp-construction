import { useEffect, useState } from "react"
import { RefreshCw } from "lucide-react"

import appStyles from "../../App.module.css"
import styles from "./SharedPayables.module.css"
import { payableStatusLabel } from "../measurementActions"
import {
  linkSharedPayable,
  listConstructionPersonSummaries,
  listSharedPayableCandidates,
  listZeroValueSuppliers,
} from "../../services/constructionApi"
import { SHARED_PAYABLE_BATCH_LIMIT, ZeroValueOrders, day } from "./ZeroValueOrders"

const SEARCH_DEBOUNCE_MS = 400

export const money = (value) =>
  value === null || value === undefined
    ? "—"
    : Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })

export function SharedPayableLinkModal({ bridge, projectId, initialPayable = null, onClose, onLinked }) {
  const [suppliers, setSuppliers] = useState([])
  const [loadingSuppliers, setLoadingSuppliers] = useState(true)
  const [supplierId, setSupplierId] = useState(initialPayable?.personId ?? "")
  const [search, setSearch] = useState("")
  const [candidates, setCandidates] = useState([])
  const [loadingCandidates, setLoadingCandidates] = useState(false)
  const [reloadCandidates, setReloadCandidates] = useState(0)
  const [chosen, setChosen] = useState(initialPayable)
  const [selected, setSelected] = useState(() => new Set())
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    const load = async () => {
      setLoadingSuppliers(true)
      try {
        const rows = await listZeroValueSuppliers({ bridge, projectId })
        if (initialPayable?.personId && !rows.some((row) => row.supplierPersonId === initialPayable.personId)) {
          rows.push({ supplierPersonId: initialPayable.personId, openCount: 0 })
        }
        const named = await Promise.all(
          rows.map(async (row) => {
            try {
              const response = await listConstructionPersonSummaries({ bridge, personId: row.supplierPersonId, pageSize: 1 })
              return { ...row, name: response.items?.[0]?.name ?? "Fornecedor sem cadastro" }
            } catch {
              return { ...row, name: "Fornecedor sem cadastro" }
            }
          }),
        )
        if (active) setSuppliers(named)
      } catch (failure) {
        if (active) setError(failure?.message ?? "Não foi possível buscar os fornecedores com OS sem valor.")
      } finally {
        if (active) setLoadingSuppliers(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [bridge, projectId, initialPayable])

  useEffect(() => {
    if (!supplierId) {
      setCandidates([])
      return undefined
    }
    let active = true
    setLoadingCandidates(true)
    const timer = setTimeout(() => {
      listSharedPayableCandidates({ bridge, projectId, supplierPersonId: supplierId, search })
        .then((rows) => {
          if (!active) return
          setCandidates(rows)
          setError("")
        })
        .catch((failure) => {
          if (active) setError(failure?.message ?? "Não foi possível buscar as DNFs no ERP.")
        })
        .finally(() => {
          if (active) setLoadingCandidates(false)
        })
    }, search ? SEARCH_DEBOUNCE_MS : 0)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [bridge, projectId, supplierId, search, reloadCandidates])

  const chooseSupplier = (value) => {
    setSupplierId(value)
    setChosen(null)
    setSelected(new Set())
    setSearch("")
  }

  const tooMany = selected.size > SHARED_PAYABLE_BATCH_LIMIT

  const confirm = async () => {
    if (!chosen || !selected.size || tooMany) return
    setSaving(true)
    try {
      const result = await linkSharedPayable({
        bridge,
        projectId,
        payableDocumentId: chosen.id,
        measurementIds: [...selected],
      })
      bridge?.feedback?.success?.(
        `${result.affected} OS vinculada(s) à DNF ${chosen.documentNumber ?? "sem número"}.`,
      )
      onLinked()
    } catch (linkError) {
      bridge?.feedback?.error?.(linkError?.message ?? "Não foi possível vincular as OS à DNF.")
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
        aria-label="Vincular OS sem valor à DNF da empreitada"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={appStyles.modalHeader}>
          <h3>Vincular OS sem valor à DNF da empreitada</h3>
          <button type="button" className={appStyles.closeButton} onClick={onClose} disabled={saving}>
            Fechar
          </button>
        </header>
        <div className={appStyles.modalBody}>
          <p className={styles.notice}>
            Escolha o fornecedor, a DNF que pagou a empreitada e marque as OS sem valor que ela cobre. Aparecem só DNFs do
            fornecedor lançadas nos centros de custo desta obra e que não pagam uma OS com valor.
          </p>
          {error ? (
            <p role="alert" className={styles.error}>
              {error}
            </p>
          ) : null}

          <div className={styles.step}>
            <h4>1. Fornecedor</h4>
            <label className={styles.field}>
              <span>Fornecedor com OS sem valor</span>
              <select
                value={supplierId}
                onChange={(event) => chooseSupplier(event.target.value)}
                disabled={saving || loadingSuppliers || Boolean(initialPayable)}
              >
                <option value="">{loadingSuppliers ? "Carregando fornecedores..." : "Selecione"}</option>
                {suppliers.map((row) => (
                  <option key={row.supplierPersonId} value={row.supplierPersonId}>
                    {row.name} · {row.openCount} OS sem DNF
                  </option>
                ))}
              </select>
            </label>
          </div>

          {supplierId ? (
            <div className={styles.step}>
              <h4>2. DNF da empreitada</h4>
              <div className={styles.toolbar}>
                <label className={styles.search}>
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Buscar número ou descrição"
                    aria-label="Buscar DNF por número ou descrição"
                    disabled={saving || Boolean(initialPayable)}
                  />
                </label>
                <button
                  type="button"
                  className={styles.iconButton}
                  onClick={() => setReloadCandidates((value) => value + 1)}
                  disabled={saving || loadingCandidates || Boolean(initialPayable)}
                  title="Atualizar lista"
                  aria-label="Atualizar lista"
                >
                  <RefreshCw size={16} aria-hidden="true" />
                </button>
              </div>
              <div className={styles.tableWrapper}>
                {initialPayable ? (
                  <table className={styles.table}>
                    <tbody>
                      <tr className={styles.chosen}>
                        <td>
                          Nº {initialPayable.documentNumber ?? "sem número"}
                          {initialPayable.description ? <small>{initialPayable.description}</small> : null}
                        </td>
                        <td>{money(initialPayable.totalAmount)}</td>
                        <td>já cobre {initialPayable.coveredCount} OS</td>
                      </tr>
                    </tbody>
                  </table>
                ) : loadingCandidates ? (
                  <p className={styles.empty}>Buscando DNFs no ERP...</p>
                ) : !candidates.length ? (
                  <p className={styles.empty}>Nenhuma DNF livre deste fornecedor nos centros de custo da obra.</p>
                ) : (
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th aria-label="Escolher" />
                        <th>DNF</th>
                        <th>Tipo</th>
                        <th>Emissão</th>
                        <th>Valor</th>
                        <th>Situação</th>
                        <th>OS cobertas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.map((row) => (
                        <tr key={row.id} className={chosen?.id === row.id ? styles.chosen : undefined}>
                          <td>
                            <input
                              type="radio"
                              name="shared-payable"
                              aria-label={`Escolher a DNF ${row.documentNumber ?? "sem número"}`}
                              checked={chosen?.id === row.id}
                              onChange={() => setChosen(row)}
                              disabled={saving}
                            />
                          </td>
                          <td>
                            {row.documentNumber ? `Nº ${row.documentNumber}` : "Sem número"}
                            {row.description ? <small>{row.description}</small> : null}
                          </td>
                          <td>{row.documentTypeLabel || "—"}</td>
                          <td>{day(row.issueDate)}</td>
                          <td>{money(row.totalAmount)}</td>
                          <td>{payableStatusLabel(row.status)}</td>
                          <td>{row.coveredCount}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          ) : null}

          {supplierId && chosen ? (
            <div className={styles.step}>
              <h4>3. OS sem valor que a DNF cobre</h4>
              <ZeroValueOrders
                bridge={bridge}
                projectId={projectId}
                supplierPersonId={supplierId}
                selected={selected}
                onSelectedChange={setSelected}
                disabled={saving}
              />
              {tooMany ? (
                <p role="alert" className={styles.error}>
                  Marque no máximo {SHARED_PAYABLE_BATCH_LIMIT} OS por vez.
                </p>
              ) : null}
            </div>
          ) : null}

          <div className={appStyles.modalFooter}>
            <button type="button" className={appStyles.secondaryButton} onClick={onClose} disabled={saving}>
              Cancelar
            </button>
            <button
              type="button"
              className={appStyles.primaryButton}
              onClick={confirm}
              disabled={!chosen || !selected.size || tooMany || saving}
            >
              {saving
                ? "Vinculando..."
                : `Vincular ${selected.size} OS${chosen ? ` à DNF ${chosen.documentNumber ?? ""}` : ""}`}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
