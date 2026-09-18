import { useEffect, useRef, useState } from "react"
import { Search, X } from "lucide-react"

import styles from "./MeasurementInspections.module.css"
import { listConstructionPersonSummaries } from "../../services/constructionApi"

const SEARCH_DEBOUNCE_MS = 400

// Busca no SERVIDOR, não em memória. O combobox do módulo filtra sobre a lista
// que recebe, e a tela de medição carrega só 50 pessoas -- com o cadastro
// migrado do MFCON isso esconderia a maior parte dos inspetores em silêncio,
// sem nenhum sinal de que a lista estava truncada.
export function InspectorPicker({ bridge, value, valueName, onChange, disabled = false, label = "Inspetor" }) {
  const [term, setTerm] = useState("")
  const [debouncedTerm, setDebouncedTerm] = useState("")
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedTerm(term), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [term])

  useEffect(() => {
    if (!open) {
      return undefined
    }

    let active = true
    const load = async () => {
      setLoading(true)
      try {
        const response = await listConstructionPersonSummaries({
          bridge,
          search: debouncedTerm,
          page: 1,
          pageSize: 20,
        })
        if (active) {
          setOptions(response.items ?? [])
        }
      } catch {
        if (active) {
          setOptions([])
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    load()
    return () => {
      active = false
    }
  }, [bridge, debouncedTerm, open])

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const selectedLabel = valueName || (value ? `Pessoa ${String(value).slice(0, 8)}` : "")

  return (
    <div className={styles.inspectorField} ref={wrapperRef}>
      <span className={styles.fieldLabel}>{label}</span>
      {value ? (
        <div className={styles.inspectorChosen}>
          <span className={styles.inspectorName}>{selectedLabel}</span>
          <button
            type="button"
            className={styles.iconButton}
            onClick={() => onChange(null, "")}
            disabled={disabled}
            aria-label="Remover inspetor"
            title="Remover inspetor"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <div className={styles.inspectorSearch}>
          <Search size={14} />
          <input
            type="text"
            className={styles.input}
            value={term}
            disabled={disabled}
            placeholder="Buscar pelo nome"
            onFocus={() => setOpen(true)}
            onChange={(event) => {
              setTerm(event.target.value)
              setOpen(true)
            }}
          />
        </div>
      )}

      {open && !value ? (
        <ul className={styles.inspectorOptions}>
          {loading ? (
            <li className={styles.inspectorHint}>Buscando...</li>
          ) : options.length === 0 ? (
            <li className={styles.inspectorHint}>Nenhuma pessoa encontrada.</li>
          ) : (
            options.map((person) => (
              <li key={person.id}>
                <button
                  type="button"
                  className={styles.inspectorOption}
                  onClick={() => {
                    onChange(person.id, person.name)
                    setTerm("")
                    setOpen(false)
                  }}
                >
                  {person.name}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  )
}
