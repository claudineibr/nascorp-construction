import { useEffect, useId, useRef, useState } from "react"
import { fetchCashRegisterOptions } from "../services/constructionApi.js"
import styles from "./CashRegisterPicker.module.css"

const SEARCH_DEBOUNCE_MS = 400

const registerLabel = (item) => `${item.name} — ${item.location}`

export function CashRegisterPicker({ bridge, value, onChange, disabled = false }) {
  const [term, setTerm] = useState("")
  const [options, setOptions] = useState([])
  const [selected, setSelected] = useState(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const callback = useRef(onChange)
  callback.current = onChange
  const valueRef = useRef(value)
  valueRef.current = value
  const listId = useId()
  const search = term.trim().length >= 4 ? term.trim() : ""

  useEffect(() => {
    if (!open) return undefined
    let cancelled = false
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const result = await fetchCashRegisterOptions({ bridge, search })
        if (!cancelled) {
          setOptions(result.items)
          setHighlighted(0)
        }
      } catch (error) {
        if (!cancelled) bridge?.feedback?.error?.(error?.message ?? "Não foi possível listar os caixas.")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [bridge, search, open])

  useEffect(() => {
    if (valueRef.current) return undefined
    let cancelled = false
    fetchCashRegisterOptions({ bridge, preferred: true })
      .then((item) => {
        if (cancelled || !item || valueRef.current) return
        setSelected(item)
        callback.current(item.id)
      })
      .catch((error) => {
        if (!cancelled) bridge?.feedback?.error?.(error?.message ?? "Não foi possível sugerir o caixa.")
      })
    return () => {
      cancelled = true
    }
  }, [bridge])

  useEffect(() => {
    if (!value || selected?.id === value) return undefined
    let cancelled = false
    fetchCashRegisterOptions({ bridge, registerId: value })
      .then((item) => {
        if (!cancelled) setSelected(item)
      })
      .catch((error) => {
        if (!cancelled) bridge?.feedback?.error?.(error?.message ?? "Não foi possível consultar o caixa.")
      })
    return () => {
      cancelled = true
    }
  }, [bridge, value, selected?.id])

  const choose = (item) => {
    setSelected(item)
    onChange(item.id)
    setTerm("")
    setOpen(false)
  }

  const handleKeyDown = (event) => {
    if (event.key === "Escape") setOpen(false)
    if (event.key === "ArrowDown") {
      event.preventDefault()
      setOpen(true)
      setHighlighted((index) => Math.min(options.length - 1, index + 1))
    }
    if (event.key === "ArrowUp") {
      event.preventDefault()
      setHighlighted((index) => Math.max(0, index - 1))
    }
    if (event.key === "Enter" && open) {
      event.preventDefault()
      if (options[highlighted]) choose(options[highlighted])
    }
  }

  const showOptions = open && !loading && options.length > 0

  return (
    <div className={styles.root}>
      <input
        type="text"
        role="combobox"
        aria-label="Caixa físico"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={showOptions ? `${listId}-${highlighted}` : undefined}
        autoComplete="off"
        disabled={disabled}
        placeholder="Selecione o caixa"
        value={value && selected?.id === value ? registerLabel(selected) : term}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onChange={(event) => {
          setTerm(event.target.value)
          setSelected(null)
          onChange("")
          setOpen(true)
        }}
        onKeyDown={handleKeyDown}
      />
      {open && (
        <div id={listId} role="listbox" aria-label="Caixas autorizados" className={styles.options}>
          {loading ? (
            <p className={styles.message}>Carregando caixas...</p>
          ) : !options.length ? (
            <p className={styles.message}>Nenhum caixa autorizado encontrado.</p>
          ) : (
            options.map((item, index) => (
              <button
                type="button"
                key={item.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={highlighted === index}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(item)}
              >
                <strong>{item.name}</strong>
                <small>
                  {item.location} · {item.current_session ? "aberto" : "fechado"}
                </small>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
