import { useEffect, useRef, useState } from "react"
import { Search } from "lucide-react"
import { searchConstructionProducts } from "../services/constructionApi.js"
import styles from "./ProductPicker.module.css"

export function ProductPicker({ bridge, onSelect, disabled = false }) {
  const [term, setTerm] = useState("")
  const [products, setProducts] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const wrapperRef = useRef(null)

  useEffect(() => {
    let active = true
    const timer = setTimeout(async () => {
      setLoading(true)
      setError("")
      try {
        const results = await searchConstructionProducts({ bridge, search: term })
        if (active) setProducts(results)
      } catch (requestError) {
        if (active) setError(requestError?.message ?? "Não foi possível buscar produtos.")
      } finally {
        if (active) setLoading(false)
      }
    }, term.trim() ? 250 : 0)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [bridge, term])

  useEffect(() => {
    const closeOnOutsideClick = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener("mousedown", closeOnOutsideClick)
    return () => document.removeEventListener("mousedown", closeOnOutsideClick)
  }, [])

  const choose = (product) => {
    onSelect(product)
    setTerm("")
    setOpen(false)
  }

  return (
    <div className={styles.field} ref={wrapperRef}>
      <label className={styles.label} htmlFor="procurement-product-search">Adicionar produto*</label>
      <div className={styles.search}>
        <Search size={15} aria-hidden="true" />
        <input
          id="procurement-product-search"
          type="search"
          className={styles.input}
          value={term}
          disabled={disabled}
          placeholder="Buscar por código ou descrição"
          autoComplete="off"
          aria-expanded={open}
          aria-controls="procurement-product-options"
          aria-autocomplete="list"
          role="combobox"
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setTerm(event.target.value)
            setOpen(true)
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false)
            if (event.key === "Enter" && open && products.length) {
              event.preventDefault()
              choose(products[0])
            }
          }}
        />
      </div>
      {open ? (
        <ul className={styles.options} id="procurement-product-options" role="listbox" aria-label="Produtos encontrados">
          {loading ? <li className={styles.hint}>Buscando produtos...</li> : null}
          {!loading && error ? <li className={styles.error} role="alert">{error}</li> : null}
          {!loading && !error && products.length === 0 ? (
            <li className={styles.hint}>{term.trim() ? "Nenhum produto ativo encontrado." : "Nenhum produto ativo disponível."}</li>
          ) : null}
          {!loading && !error ? products.map((product) => (
            <li key={product.id}>
              <button type="button" role="option" aria-selected="false" className={styles.option} onClick={() => choose(product)}>
                <span className={styles.optionName}>{product.code} — {product.description}</span>
                <span className={styles.optionUnit}>Unidade: {product.unitOfMeasure}</span>
              </button>
            </li>
          )) : null}
        </ul>
      ) : null}
    </div>
  )
}

export default ProductPicker
