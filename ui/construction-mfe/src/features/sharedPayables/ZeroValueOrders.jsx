import { useEffect, useMemo, useState } from "react"

import { Pagination as StandalonePagination } from "../../components/Pagination.jsx"
import {
  listConstructionBlocks,
  listZeroValueMeasurementIds,
  listZeroValueMeasurements,
} from "../../services/constructionApi"
import styles from "./SharedPayables.module.css"

const DEBOUNCE_MS = 400
const PAGE_SIZE_OPTIONS = [25, 50, 100]
export const SHARED_PAYABLE_BATCH_LIMIT = 1000

export const day = (value) =>
  value ? new Date(`${String(value).slice(0, 10)}T12:00:00`).toLocaleDateString("pt-BR") : "-"

function useDebounced(value) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [value])
  return debounced
}

export function ZeroValueOrders({
  bridge,
  projectId,
  supplierPersonId = "",
  payableDocumentId = "",
  selected,
  onSelectedChange,
  reloadKey = 0,
  disabled = false,
}) {
  const Pagination = bridge?.components?.Pagination ?? StandalonePagination
  const [blockId, setBlockId] = useState("")
  const [unitSearch, setUnitSearch] = useState("")
  const [orderSearch, setOrderSearch] = useState("")
  const [dueFrom, setDueFrom] = useState("")
  const [dueTo, setDueTo] = useState("")
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [blocks, setBlocks] = useState([])
  const [result, setResult] = useState({ items: [], total: 0, totalPages: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [selectingAll, setSelectingAll] = useState(false)
  const debouncedUnit = useDebounced(unitSearch)
  const debouncedOrder = useDebounced(orderSearch)

  const filters = useMemo(
    () => ({
      supplierPersonId,
      payableDocumentId,
      blockId,
      unitSearch: debouncedUnit.trim(),
      search: debouncedOrder.trim(),
      dueFrom,
      dueTo,
    }),
    [supplierPersonId, payableDocumentId, blockId, debouncedUnit, debouncedOrder, dueFrom, dueTo],
  )

  useEffect(() => {
    let active = true
    listConstructionBlocks({ bridge, projectId })
      .then((response) => {
        if (active) setBlocks(response.items)
      })
      .catch((failure) => {
        if (active) setError(failure?.message ?? "Não foi possível carregar os blocos da obra.")
      })
    return () => {
      active = false
    }
  }, [bridge, projectId])

  useEffect(() => {
    setPage(1)
  }, [filters])

  useEffect(() => {
    let active = true
    setLoading(true)
    listZeroValueMeasurements({ bridge, projectId, filters, page, pageSize })
      .then((response) => {
        if (!active) return
        setResult(response)
        setError("")
      })
      .catch((failure) => {
        if (active) setError(failure?.message ?? "Não foi possível buscar as OS sem valor.")
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [bridge, projectId, filters, page, pageSize, reloadKey])

  const pageIds = result.items.map((row) => row.id)
  const pageFullySelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id))

  const toggle = (id) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onSelectedChange(next)
  }

  const togglePage = () => {
    const next = new Set(selected)
    for (const id of pageIds) {
      if (pageFullySelected) next.delete(id)
      else next.add(id)
    }
    onSelectedChange(next)
  }

  const selectAllFiltered = async () => {
    setSelectingAll(true)
    try {
      const ids = await listZeroValueMeasurementIds({ bridge, projectId, filters })
      onSelectedChange(new Set([...selected, ...ids]))
      if (result.total > ids.length) {
        bridge?.feedback?.warning?.(
          `Foram marcadas as primeiras ${ids.length} OS do filtro. Vincule em partes de até ${SHARED_PAYABLE_BATCH_LIMIT}.`,
        )
      }
    } catch (failure) {
      bridge?.feedback?.error?.(failure?.message ?? "Não foi possível marcar as OS do filtro.")
    } finally {
      setSelectingAll(false)
    }
  }

  return (
    <div className={styles.step}>
      <div className={styles.filters}>
        <label className={styles.field}>
          <span>Bloco</span>
          <select value={blockId} onChange={(event) => setBlockId(event.target.value)} disabled={disabled}>
            <option value="">Todos</option>
            {blocks.map((block) => (
              <option key={block.id} value={block.id}>
                {block.name}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          <span>Unidade</span>
          <input
            value={unitSearch}
            onChange={(event) => setUnitSearch(event.target.value)}
            placeholder="Código ou nome"
            disabled={disabled}
          />
        </label>
        <label className={styles.field}>
          <span>Nº da OS</span>
          <input
            value={orderSearch}
            onChange={(event) => setOrderSearch(event.target.value)}
            placeholder="Ex.: 3 ou OS-005724"
            disabled={disabled}
          />
        </label>
        <label className={styles.field}>
          <span>Vencimento de</span>
          <input type="date" value={dueFrom} onChange={(event) => setDueFrom(event.target.value)} disabled={disabled} />
        </label>
        <label className={styles.field}>
          <span>Vencimento até</span>
          <input type="date" value={dueTo} onChange={(event) => setDueTo(event.target.value)} disabled={disabled} />
        </label>
      </div>
      <div className={styles.selectionBar}>
        <span>
          <strong>{selected.size}</strong> OS marcada(s) · {result.total} no filtro
        </span>
        <span className={styles.rowActions}>
          <button
            type="button"
            className={styles.linkButton}
            onClick={selectAllFiltered}
            disabled={disabled || selectingAll || !result.total}
          >
            {selectingAll ? "Marcando..." : `Marcar as ${result.total} do filtro`}
          </button>
          <button
            type="button"
            className={styles.linkButton}
            onClick={() => onSelectedChange(new Set())}
            disabled={disabled || !selected.size}
          >
            Limpar marcação
          </button>
        </span>
      </div>
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
      <div className={styles.tableWrapper}>
        {loading ? (
          <p className={styles.empty}>Buscando OS...</p>
        ) : !result.items.length ? (
          <p className={styles.empty}>Nenhuma OS sem valor neste filtro.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    aria-label="Marcar as OS desta página"
                    checked={pageFullySelected}
                    onChange={togglePage}
                    disabled={disabled}
                  />
                </th>
                <th>OS</th>
                <th>Unidade</th>
                <th>Bloco</th>
                <th>Vencimento</th>
                <th>Descrição</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((row) => (
                <tr key={row.id} className={selected.has(row.id) ? styles.chosen : undefined}>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Marcar a ${row.code}`}
                      checked={selected.has(row.id)}
                      onChange={() => toggle(row.id)}
                      disabled={disabled}
                    />
                  </td>
                  <td>
                    OS {row.sequenceNumber ?? "-"}
                    <small>{row.code}</small>
                  </td>
                  <td>
                    {row.unitCode || "-"}
                    {row.unitDescription ? <small>{row.unitDescription}</small> : null}
                  </td>
                  <td>{row.blockName || "-"}</td>
                  <td>{day(row.dueDate)}</td>
                  <td>{row.description || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {result.totalPages > 1 ? (
        <Pagination
          currentPage={page}
          totalPages={result.totalPages}
          totalItems={result.total}
          pageSize={pageSize}
          isLoading={loading}
          pageSizeOptions={PAGE_SIZE_OPTIONS}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size)
            setPage(1)
          }}
        />
      ) : null}
    </div>
  )
}
