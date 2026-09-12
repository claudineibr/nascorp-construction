import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import styles from "./CreatableCombobox.module.css"

export const CreatableCombobox = ({
  value,
  onChange,
  items,
  disabled = false,
  placeholder = "Buscar...",
  loadingPlaceholder = "Carregando...",
  emptyMessage = "Nenhum registro cadastrado.",
  notFoundMessage = "Nenhum registro encontrado.",
  createLabel = (text) => `Criar "${text}"`,
  allowCreate = false,
  loading = false,
  className,
}) => {
  const [filterText, setFilterText] = useState("")
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const wrapperRef = useRef(null)
  const inputRef = useRef(null)

  // O catálogo inteiro chega pronto de quem monta a tela: filtrar aqui evita
  // uma ida ao servidor por tecla e um GET por linha de documentação.
  const displayList = useMemo(() => {
    const list = Array.isArray(items) ? [...items] : []
    list.sort((a, b) => (a?.name ?? "").localeCompare(b?.name ?? ""))

    const term = filterText.trim().toLowerCase()
    if (!term) {
      return list
    }

    return list.filter((item) => (item?.name ?? "").toLowerCase().includes(term))
  }, [items, filterText])

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleKeyDown = useCallback((event) => {
    if (event.key === "Escape") {
      setDropdownOpen(false)
      inputRef.current?.blur()
    }
  }, [])

  const handleSelect = useCallback(
    (item) => {
      onChange?.(item)
      setFilterText("")
      setDropdownOpen(false)
    },
    [onChange]
  )

  const handleClear = useCallback(() => {
    onChange?.(null)
    setFilterText("")
    setDropdownOpen(false)
  }, [onChange])

  const handleInputChange = (event) => {
    setFilterText(event.target.value)
    if (!dropdownOpen) setDropdownOpen(true)
  }

  const handleFocus = () => {
    if (!value && !disabled) setDropdownOpen(true)
  }

  const typedName = filterText.trim()
  const isSearching = typedName.length > 0
  // O tipo novo so e gravado na confirmacao da venda: aqui ele e apenas uma
  // escolha do formulario, entao cancelar o modal nao deixa tipo orfao.
  const showCreateOption =
    allowCreate &&
    isSearching &&
    !loading &&
    !displayList.some((item) => (item?.name ?? "").toLowerCase() === typedName.toLowerCase())

  return (
    <div ref={wrapperRef} className={`${styles.wrapper}${className ? ` ${className}` : ""}`}>
      <input
        ref={inputRef}
        type="text"
        className={`${styles.input}${value ? ` ${styles.inputSelected}` : ""}`}
        value={value ? value.name : filterText}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onFocus={handleFocus}
        placeholder={loading ? loadingPlaceholder : placeholder}
        disabled={disabled || Boolean(value)}
        readOnly={Boolean(value)}
        autoComplete="off"
      />

      {value && !disabled && (
        <button type="button" className={styles.clearBtn} onClick={handleClear} aria-label="Limpar seleção">
          ✕
        </button>
      )}

      {dropdownOpen && !value && (
        <div className={styles.dropdown}>
          {loading && <p className={styles.dropdownMsg}>Carregando...</p>}

          {!loading && displayList.length === 0 && !showCreateOption && (
            <p className={styles.dropdownMsg}>{isSearching ? notFoundMessage : emptyMessage}</p>
          )}

          {!loading &&
            displayList.map((item) => (
              <button
                key={item.id}
                type="button"
                className={styles.dropdownItem}
                onClick={() => handleSelect(item)}
              >
                <span className={styles.itemName}>{item.name}</span>
              </button>
            ))}

          {showCreateOption && (
            <button
              type="button"
              className={`${styles.dropdownItem} ${styles.createItem}`}
              onClick={() => handleSelect({ id: null, name: typedName, isNew: true })}
            >
              <span className={styles.itemName}>{createLabel(typedName)}</span>
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default CreatableCombobox
