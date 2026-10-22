import { useCallback, useEffect, useState } from "react"
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
    ? "-"
    : Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })

export function SharedPayableLinkModal({ bridge, projectId, initialPayable = null, contract = null, onClose, onLinked }) {
  const [suppliers, setSuppliers] = useState([])
  const [loadingSuppliers, setLoadingSuppliers] = useState(!contract)
  const [supplierId, setSupplierId] = useState(contract?.supplierPersonId ?? initialPayable?.personId ?? "")
  const [netById, setNetById] = useState(() => new Map())
  const [search, setSearch] = useState("")
  const [candidates, setCandidates] = useState([])
  const [loadingCandidates, setLoadingCandidates] = useState(false)
  const [reloadCandidates, setReloadCandidates] = useState(0)
  const [chosen, setChosen] = useState(initialPayable)
  const [selected, setSelected] = useState(() => new Set())
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  const [contractSupplierName, setContractSupplierName] = useState("")
  useEffect(() => {
    if (!contract?.supplierPersonId) return undefined
    let active = true
    listConstructionPersonSummaries({ bridge, personId: contract.supplierPersonId, pageSize: 1 })
      .then((response) => {
        if (active) setContractSupplierName(response.items?.[0]?.name ?? "Fornecedor sem cadastro")
      })
      .catch(() => {
        if (active) setContractSupplierName("Fornecedor sem cadastro")
      })
    return () => {
      active = false
    }
  }, [bridge, contract?.supplierPersonId])

  useEffect(() => {
    if (contract) return undefined
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
  }, [bridge, projectId, initialPayable, contract])

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
  const rememberNets = useCallback((rows) => {
    setNetById((current) => {
      const next = new Map(current)
      for (const row of rows) next.set(row.id, Number(row.netAmount ?? 0))
      return next
    })
  }, [])
  const globalContract = contract?.pricingMode === "GLOBAL"
  const selectedTotal = [...selected].reduce((sum, id) => sum + (netById.get(id) ?? 0), 0)
  const coveredBefore = Number(chosen?.coveredAmount ?? 0)
  const chosenNet = Number(chosen?.netAmount ?? chosen?.totalAmount ?? 0)
  const totalMismatch = Boolean(contract && !globalContract && chosen) &&
    Math.round((selectedTotal + coveredBefore) * 100) !== Math.round(chosenNet * 100)
  const overBalance = Boolean(globalContract && chosen && !chosen.coveredCount) &&
    Math.round(Number(chosen.totalAmount ?? 0) * 100) > Math.round(Number(contract.remainingAmount ?? 0) * 100)
  const blockReason = !chosen
    ? "Escolha a DNF"
    : !selected.size
      ? "Marque pelo menos uma OS"
      : tooMany
        ? `Marque no máximo ${SHARED_PAYABLE_BATCH_LIMIT} OS por vez`
        : totalMismatch
          ? "A soma dos líquidos das OS precisa ser igual ao líquido da DNF"
          : overBalance
            ? "A DNF passa do saldo do contrato global"
            : ""

  const confirm = async () => {
    if (blockReason) return
    setSaving(true)
    try {
      const result = await linkSharedPayable({
        bridge,
        projectId,
        payableDocumentId: chosen.id,
        measurementIds: [...selected],
        subcontractId: contract?.id ?? null,
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
        aria-label={contract ? `Vincular DNF às medições do contrato ${contract.code}` : "Vincular OS sem valor à DNF da empreitada"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={appStyles.modalHeader}>
          <h3>{contract ? `Vincular DNF às medições do contrato ${contract.code}` : "Vincular OS sem valor à DNF da empreitada"}</h3>
          <button type="button" className={appStyles.closeButton} onClick={onClose} disabled={saving}>
            Fechar
          </button>
        </header>
        <div className={appStyles.modalBody}>
          <p className={styles.notice}>
            {contract
              ? globalContract
                ? "Escolha a DNF do empreiteiro e marque as OS do contrato global que ela paga. O valor da DNF entra no pago do contrato e não pode passar do saldo dele."
                : "Escolha a DNF do empreiteiro e marque as medições aprovadas do contrato que ela paga. A soma dos líquidos das medições precisa ser igual ao líquido da DNF (valor menos os tributos retidos)."
              : "Escolha o fornecedor, a DNF que pagou a empreitada e marque as OS sem valor que ela cobre. Aparecem só DNFs do fornecedor lançadas nos centros de custo desta obra e que não pagam uma OS com valor."}
          </p>
          {error ? (
            <p role="alert" className={styles.error}>
              {error}
            </p>
          ) : null}

          {contract ? (
            <div className={styles.step}>
              <h4>1. Empreiteiro do contrato</h4>
              <p>{contractSupplierName || "Carregando empreiteiro..."}</p>
            </div>
          ) : <div className={styles.step}>
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
          </div>}

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
                          <td>{row.documentTypeLabel || "-"}</td>
                          <td>{day(row.issueDate)}</td>
                          <td>{money(row.totalAmount)}</td>
                          <td>{payableStatusLabel(row.status)}</td>
                          <td>
                            {row.coveredCount}
                            {contract && row.coveredCount ? <small>cobre {money(row.coveredAmount)}</small> : null}
                          </td>
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
              <h4>{contract ? "3. Medições do contrato que a DNF paga" : "3. OS sem valor que a DNF cobre"}</h4>
              <ZeroValueOrders
                bridge={bridge}
                projectId={projectId}
                supplierPersonId={supplierId}
                subcontractId={contract?.id ?? ""}
                selected={selected}
                onSelectedChange={setSelected}
                onRowsLoaded={contract ? rememberNets : null}
                disabled={saving}
              />
              {contract && !globalContract ? (
                <p className={totalMismatch ? styles.error : styles.notice} role="status">
                  Soma dos líquidos marcados: {money(selectedTotal + coveredBefore)} · Líquido da DNF: {money(chosenNet)}
                  {chosenNet !== Number(chosen.totalAmount ?? 0) ? ` (valor ${money(chosen.totalAmount)} menos tributos retidos)` : ""}
                </p>
              ) : null}
              {globalContract ? (
                <p className={overBalance ? styles.error : styles.notice} role="status">
                  Valor da DNF: {money(chosen.totalAmount)} · Saldo do contrato global: {money(contract.remainingAmount)}
                </p>
              ) : null}
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
              disabled={Boolean(blockReason) || saving}
              title={blockReason || undefined}
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
