import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Search, X } from "lucide-react"

import styles from "./PersonPicker.module.css"
import { useBridge } from "./bridgeContext"
import { listConstructionPersonSummaries } from "../services/constructionApi"

const SEARCH_DEBOUNCE_MS = 400
const PAGE_SIZE = 20

// Busca no SERVIDOR, nao em memoria.
//
// O campo que existia antes era um `<select>` alimentado por uma lista de 50
// pessoas -- e o cadastro migrado do MFCON tem 3.116. O comprador e o corretor
// de uma unidade praticamente nunca estao entre os 50 primeiros nomes em ordem
// alfabetica, entao "Editar venda" abria com os campos VAZIOS embora os ids
// estivessem gravados na unidade. Pior: a lista nao dava nenhum sinal de estar
// truncada, entao parecia que a pessoa nao existia.
export function PersonPicker({
  bridge: bridgeFromProps = null,
  label,
  value,
  onChange,
  disabled = false,
  required = false,
  emptyLabel = "Buscar pessoa pelo nome",
  error = null,
  // Recorta a busca por papel comercial (`broker`, `supplier`...). Quem ja esta
  // GRAVADO continua sendo resolvido pelo id, fora do recorte: um corretor que
  // perdeu o papel nao pode sumir do campo da unidade dele.
  businessRole = null,
  warnUnqualified = false,
  qualificationWarnings = null,
  // Nomes que a tela ja conhece, para o campo abrir preenchido sem uma ida ao
  // servidor. E atalho, nao dependencia: o que nao estiver aqui e buscado.
  knownPeople = null,
}) {
  const bridge = useBridge(bridgeFromProps)
  const [term, setTerm] = useState("")
  const [debouncedTerm, setDebouncedTerm] = useState("")
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const [resolved, setResolved] = useState(null)
  const wrapperRef = useRef(null)
  const inputRef = useRef(null)

  const knownById = useMemo(() => {
    const mapa = new Map()
    for (const person of knownPeople ?? []) {
      if (person?.id) {
        mapa.set(person.id, person)
      }
    }
    return mapa
  }, [knownPeople])

  const selected = useMemo(() => {
    if (!value) {
      return null
    }
    return (
      knownById.get(value) ??
      options.find((person) => person.id === value) ??
      (resolved?.id === value ? resolved : null)
    )
  }, [knownById, options, resolved, value])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedTerm(term), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [term])

  // Quem esta gravado, pelo id. O filtro de papel NAO entra aqui de proposito --
  // ver o comentario de `businessRole` acima.
  useEffect(() => {
    if (!value || selected) {
      return undefined
    }

    let active = true
    const resolve = async () => {
      try {
        const response = await listConstructionPersonSummaries({
          bridge,
          personId: value,
          page: 1,
          pageSize: 1,
        })
        const person = (response.items ?? [])[0]
        if (active && person) {
          setResolved(person)
        }
      } catch {
        // Pessoa apagada, ou sem permissao de leitura: o campo cai no id, que
        // ja era o comportamento antigo. Derrubar a tela inteira por causa de
        // um nome seria pior.
      }
    }

    void resolve()
    return () => {
      active = false
    }
  }, [bridge, selected, value])

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
          pageSize: PAGE_SIZE,
          businessRole,
        })
        if (active) {
          setOptions(response.items ?? [])
          setHighlighted(0)
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

    void load()
    return () => {
      active = false
    }
  }, [bridge, businessRole, debouncedTerm, open])

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const escolher = useCallback(
    (person) => {
      setResolved(person)
      onChange(person.id, person)
      setTerm("")
      setOpen(false)
    },
    [onChange]
  )

  const limpar = useCallback(() => {
    setResolved(null)
    onChange("", null)
    setOpen(false)
  }, [onChange])

  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      setOpen(false)
      return
    }
    if (event.key === "ArrowDown") {
      event.preventDefault()
      setOpen(true)
      setHighlighted((atual) => Math.min(atual + 1, Math.max(options.length - 1, 0)))
      return
    }
    if (event.key === "ArrowUp") {
      event.preventDefault()
      setHighlighted((atual) => Math.max(atual - 1, 0))
      return
    }
    if (event.key === "Enter") {
      // Nao deixa o Enter da busca SUBMETER o formulario do modal.
      event.preventDefault()
      const person = options[highlighted]
      if (person) {
        escolher(person)
      }
    }
  }

  const qualificationWarning =
    warnUnqualified && selected && qualificationWarnings
      ? qualificationWarnings[selected.qualificationStatus ?? "none"] ?? null
      : null

  const nomeSelecionado = selected
    ? `${selected.name}${selected.document ? ` - ${selected.document}` : ""}`
    : value
      ? "Carregando nome..."
      : ""

  return (
    <div className={styles.field} ref={wrapperRef}>
      <span className={styles.label}>{label}</span>
      {value ? (
        <div className={styles.chosen}>
          <span className={styles.name} title={nomeSelecionado}>
            {nomeSelecionado}
          </span>
          <button
            type="button"
            className={styles.clearButton}
            onClick={limpar}
            disabled={disabled}
            aria-label={`Remover ${label}`}
            title="Remover"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <div className={styles.search}>
          <Search size={14} aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            className={styles.input}
            value={term}
            disabled={disabled}
            placeholder={emptyLabel}
            aria-required={required || undefined}
            aria-expanded={open}
            role="combobox"
            aria-autocomplete="list"
            onFocus={() => setOpen(true)}
            onKeyDown={handleKeyDown}
            onChange={(event) => {
              setTerm(event.target.value)
              setOpen(true)
            }}
          />
        </div>
      )}

      {open && !value ? (
        <ul className={styles.options} role="listbox">
          {loading ? (
            <li className={styles.hint}>Buscando...</li>
          ) : options.length === 0 ? (
            <li className={styles.hint}>
              {businessRole
                ? "Nenhuma pessoa com este papel. Verifique o cadastro da pessoa."
                : "Nenhuma pessoa encontrada."}
            </li>
          ) : (
            options.map((person, indice) => (
              <li key={person.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={indice === highlighted}
                  className={
                    indice === highlighted ? `${styles.option} ${styles.optionActive}` : styles.option
                  }
                  onMouseEnter={() => setHighlighted(indice)}
                  onClick={() => escolher(person)}
                >
                  <span className={styles.optionName}>{person.name}</span>
                  {person.document ? (
                    <span className={styles.optionDocument}>{person.document}</span>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}

      {qualificationWarning ? (
        <small className={styles.warning} data-testid="qualification-warning">
          {qualificationWarning}
        </small>
      ) : null}
      {error ? <small className={styles.error}>{error}</small> : null}
    </div>
  )
}
