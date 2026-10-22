import { useEffect, useState } from "react"
import { FilePlus2, RefreshCw, Search } from "lucide-react"

import appStyles from "../../App.module.css"
import styles from "./MeasurementPayableLink.module.css"
import { useBridge } from "../../components/bridgeContext"
import {
  getConstructionMeasurement,
  linkMeasurementPayable,
  listMeasurementPayableCandidates,
} from "../../services/constructionApi"
import { newMeasurementPayablePath, payableStatusLabel } from "../measurementActions"

const SEARCH_DEBOUNCE_MS = 400

const money = (value) =>
  value === null || value === undefined
    ? "-"
    : Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })

const day = (value) => (value ? new Date(`${String(value).slice(0, 10)}T12:00:00`).toLocaleDateString("pt-BR") : "-")

const sameAmount = (left, right) => Math.round(Number(left ?? 0) * 100) === Math.round(Number(right ?? 0) * 100)

export function MeasurementPayableLinkModal({ measurement, onClose, onLinked }) {
  const bridge = useBridge()
  const [search, setSearch] = useState("")
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [chosen, setChosen] = useState(null)
  const [saving, setSaving] = useState(false)
  const [reload, setReload] = useState(0)
  const measuredAmount = measurement.measuredAmount ?? measurement.grossAmount
  const canCreatePayable = Boolean(bridge?.canCreate?.("accounts_payable"))

  useEffect(() => {
    let active = true
    setLoading(true)
    const timer = setTimeout(() => {
      listMeasurementPayableCandidates({ bridge, measurementId: measurement.id, search })
        .then((items) => {
          if (!active) return
          setRows(items)
          setError("")
        })
        .catch((failure) => {
          if (active) setError(failure?.message ?? "Não foi possível buscar os títulos no ERP.")
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    }, search ? SEARCH_DEBOUNCE_MS : 0)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [bridge, measurement.id, search, reload])

  useEffect(() => {
    const refresh = () => {
      getConstructionMeasurement({ bridge, measurementId: measurement.id })
        .then((current) => {
          if (current.externalAccountsPayableId) {
            bridge?.feedback?.success?.(`Medição ${measurement.code} vinculada ao título lançado no ERP.`)
            onLinked()
          } else {
            setReload((value) => value + 1)
          }
        })
        .catch(() => setReload((value) => value + 1))
    }
    window.addEventListener("focus", refresh)
    return () => window.removeEventListener("focus", refresh)
  }, [bridge, measurement.id, measurement.code, onLinked])

  const openNewPayable = () => {
    bridge?.navigate?.(newMeasurementPayablePath(measurement))
  }

  const confirm = async () => {
    if (!chosen) return
    setSaving(true)
    try {
      await linkMeasurementPayable({ bridge, measurementId: measurement.id, payableDocumentId: chosen.id })
      bridge?.feedback?.success?.(
        `Medição ${measurement.code} vinculada ao título ${chosen.documentNumber ?? "sem número"}.`,
      )
      onLinked()
    } catch (linkError) {
      bridge?.feedback?.error?.(linkError?.message ?? "Não foi possível vincular o título.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={appStyles.modalOverlay} role="presentation" onClick={() => !saving && onClose()}>
      <section
        className={appStyles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={`Vincular título existente à medição ${measurement.code}`}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={appStyles.modalHeader}>
          <h3>Vincular título existente à medição {measurement.code}</h3>
          <button type="button" className={appStyles.closeButton} onClick={onClose} disabled={saving}>
            Fechar
          </button>
        </header>
        <div className={appStyles.modalBody}>
          <p className={styles.notice}>
            Escolha o título (DNF, nota fiscal ou recibo) que pagou esta medição. Aparecem só títulos do fornecedor da
            medição, lançados nos centros de custo desta obra e ainda não vinculados a outra medição. Valor da medição:{" "}
            <strong>{money(measuredAmount)}</strong>.
            {canCreatePayable
              ? " Se o fornecedor não tem nota nem recibo, use Lançar nova DNF: o Contas a Pagar abre nesta aba com os dados da medição, o título fica vinculado a ela ao salvar e a tela volta para a obra."
              : null}
          </p>
          <div className={styles.toolbar}>
            <label className={styles.search}>
              <Search size={16} aria-hidden="true" />
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value)
                  setChosen(null)
                }}
                placeholder="Buscar número ou descrição"
                aria-label="Buscar título por número ou descrição"
                disabled={saving}
              />
            </label>
            <div className={styles.toolbarActions}>
              <button
                type="button"
                className={styles.iconButton}
                onClick={() => setReload((value) => value + 1)}
                disabled={saving || loading}
                title="Atualizar lista"
                aria-label="Atualizar lista"
              >
                <RefreshCw size={16} aria-hidden="true" />
              </button>
              {canCreatePayable ? (
                <button type="button" className={appStyles.secondaryButton} onClick={openNewPayable} disabled={saving}>
                  <FilePlus2 size={16} aria-hidden="true" />
                  Lançar nova DNF
                </button>
              ) : null}
            </div>
          </div>
          {error ? <p role="alert" className={styles.error}>{error}</p> : null}
          <div className={styles.tableWrapper}>
            {loading ? (
              <p className={styles.empty}>Buscando títulos no ERP...</p>
            ) : rows.length === 0 ? (
              <p className={styles.empty}>Nenhum título livre deste fornecedor nos centros de custo da obra.</p>
            ) : (
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th aria-label="Escolher" />
                    <th>Título</th>
                    <th>Tipo</th>
                    <th>Emissão</th>
                    <th>Valor</th>
                    <th>Situação</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const differs = !sameAmount(row.totalAmount, measuredAmount)
                    return (
                      <tr key={row.id} className={chosen?.id === row.id ? styles.chosen : undefined}>
                        <td>
                          <input
                            type="radio"
                            name="measurement-payable"
                            aria-label={`Escolher o título ${row.documentNumber ?? "sem número"}`}
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
                        <td>
                          {money(row.totalAmount)}
                          {differs ? <small className={styles.warning}>valor diferente da medição</small> : null}
                        </td>
                        <td>{payableStatusLabel(row.status)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div className={appStyles.modalFooter}>
            <button type="button" className={appStyles.secondaryButton} onClick={onClose} disabled={saving}>
              Cancelar
            </button>
            <button type="button" className={appStyles.primaryButton} onClick={confirm} disabled={!chosen || saving}>
              {saving ? "Vinculando..." : "Vincular título"}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
