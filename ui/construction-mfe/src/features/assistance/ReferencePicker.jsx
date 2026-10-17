import { X } from "lucide-react"
import { useEffect, useId, useState } from "react"
import { subcontractRequest } from "../../services/constructionApi"
import styles from "./AssistancePanel.module.css"

export function ReferencePicker({
  bridge,
  kind,
  value,
  onChange,
  onResolve,
  displayName,
  label,
  projectId,
  disabled = false,
  required = false,
}) {
  const [term, setTerm] = useState("")
  const [name, setName] = useState("")
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const listId = useId()
  const [highlighted, setHighlighted] = useState(0)
  useEffect(() => {
    if (!value) {
      setName("")
      return undefined
    }
    let active = true
    subcontractRequest({
      bridge,
      path: `/assistance-requests/references?kind=${kind}&reference_id=${value}`,
    })
      .then((data) => {
        if (active) {
          setName(data.items[0]?.name || "Registro indisponível")
          if (data.items[0]) onResolve?.(data.items[0])
        }
      })
      .catch((error) => {
        if (active) bridge.feedback?.error?.(error.message)
      })
    return () => {
      active = false
    }
  }, [bridge, kind, value, onResolve])
  useEffect(() => {
    if (!open) return undefined
    let active = true
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const query = new URLSearchParams({ kind, search: term })
        if (projectId) query.set("project_id", projectId)
        const data = await subcontractRequest({
          bridge,
          path: `/assistance-requests/references?${query}`,
        })
        if (active) setItems(data.items)
      } catch (error) {
        if (active) bridge.feedback?.error?.(error.message)
      } finally {
        if (active) setLoading(false)
      }
    }, 400)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [bridge, kind, open, term, projectId])
  return (
    <div className={styles.field}>
      <span>
        {label}
        {required ? " *" : ""}
      </span>
      <div className={styles.clearableField}>
        <input
          aria-label={label}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={open && items[highlighted] ? `${listId}-${highlighted}` : undefined}
          value={open ? term : displayName || name}
          title={displayName || name || undefined}
          disabled={disabled}
          required={required && !value}
          placeholder="Digite para buscar"
          onFocus={() => {
            setTerm("")
            setHighlighted(0)
            setOpen(true)
          }}
          onChange={(event) => setTerm(event.target.value)}
          onBlur={() => setOpen(false)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false)
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault()
              setOpen(true)
              setHighlighted((old) =>
                Math.max(0, Math.min(items.length - 1, old + (event.key === "ArrowDown" ? 1 : -1)))
              )
            }
            if (event.key === "Enter" && open && items[highlighted]) {
              event.preventDefault()
              onChange(items[highlighted].id, items[highlighted])
              setName(items[highlighted].name)
              setOpen(false)
            }
          }}
        />
        {value && !disabled ? (
          <button
            type="button"
            className={styles.removeButton}
            title={`Limpar ${label.toLowerCase()}`}
            aria-label={`Limpar ${label.toLowerCase()}`}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              onChange(null)
              setName("")
              setTerm("")
              setOpen(false)
            }}
          >
            <X size={16} aria-hidden="true" />
          </button>
        ) : null}
      </div>
      {open ? (
        <div className={styles.options} id={listId} role="listbox">
          {loading ? (
            <p>Carregando...</p>
          ) : !items.length ? (
            <p>Nenhum registro encontrado.</p>
          ) : (
            items.map((item, index) => (
              <button
                className={styles.option}
                type="button"
                key={item.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === highlighted}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange(item.id, item)
                  setName(item.name)
                  setOpen(false)
                }}
              >
                {item.name}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  )
}
