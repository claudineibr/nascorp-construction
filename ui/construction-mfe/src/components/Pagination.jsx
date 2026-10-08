import { ChevronLeft, ChevronRight } from "lucide-react"
import styles from "./Pagination.module.css"

const WINDOW_SIZE = 5

const buildPageWindow = (currentPage, totalPages, windowSize = WINDOW_SIZE) => {
  if (totalPages <= windowSize) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }

  const halfWindow = Math.floor(windowSize / 2)
  let start = Math.max(1, currentPage - halfWindow)
  let end = Math.min(totalPages, start + windowSize - 1)

  if (end - start + 1 < windowSize) {
    start = Math.max(1, end - windowSize + 1)
  }

  return Array.from({ length: end - start + 1 }, (_, index) => start + index)
}

export const Pagination = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  isLoading = false,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 30, 50, 100],
  className = "",
}) => {
  const safeCurrentPage = Math.max(1, currentPage || 1)
  const safeTotalPages = Math.max(1, totalPages ?? Math.ceil(totalItems / pageSize))

  const firstItem = totalItems > 0 ? (safeCurrentPage - 1) * pageSize + 1 : 0
  const lastItem = totalItems > 0 ? Math.min(totalItems, safeCurrentPage * pageSize) : 0
  const pageWindow = buildPageWindow(safeCurrentPage, safeTotalPages)

  const canGoBack = safeCurrentPage > 1 && !isLoading
  const canGoNext = safeCurrentPage < safeTotalPages && !isLoading

  const handlePageChange = (page) => {
    if (page === safeCurrentPage || page < 1 || page > safeTotalPages || isLoading) return
    onPageChange?.(page)
  }

  return (
    <div className={`${styles.container} ${className}`.trim()}>
      <p className={styles.summary}>
        Mostrando {firstItem}-{lastItem} de {totalItems} registros
      </p>

      <div className={styles.controls}>
        {onPageSizeChange && (
          <label className={styles.pageSize}>
            Itens por página
            <select value={pageSize} disabled={isLoading} onChange={(event) => {
              onPageSizeChange(Number(event.target.value))
              onPageChange?.(1)
            }}>
              {pageSizeOptions.map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
        )}
        <button
          type="button"
          className={styles.navButton}
          aria-label="Página anterior"
          onClick={() => handlePageChange(safeCurrentPage - 1)}
          disabled={!canGoBack} title="Página anterior">
          <ChevronLeft size={16} />
        </button>

        <div className={styles.pageNumbers}>
          {pageWindow[0] > 1 && (
            <>
              <button type="button" className={styles.pageButton} onClick={() => handlePageChange(1)} disabled={isLoading}>
                1
              </button>
              {pageWindow[0] > 2 && <span className={styles.ellipsis}>...</span>}
            </>
          )}

          {pageWindow.map((page) => (
            <button
              key={page}
              type="button"
              className={`${styles.pageButton} ${page === safeCurrentPage ? styles.activePageButton : ""}`}
              onClick={() => handlePageChange(page)}
              disabled={isLoading}
              aria-current={page === safeCurrentPage ? "page" : undefined}
            >
              {page}
            </button>
          ))}

          {pageWindow[pageWindow.length - 1] < safeTotalPages && (
            <>
              {pageWindow[pageWindow.length - 1] < safeTotalPages - 1 && <span className={styles.ellipsis}>...</span>}
              <button
                type="button"
                className={styles.pageButton}
                onClick={() => handlePageChange(safeTotalPages)}
                disabled={isLoading}
              >
                {safeTotalPages}
              </button>
            </>
          )}
        </div>

        <button
          type="button"
          className={styles.navButton}
          aria-label="Próxima página"
          onClick={() => handlePageChange(safeCurrentPage + 1)}
          disabled={!canGoNext} title="Próxima página">
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}
