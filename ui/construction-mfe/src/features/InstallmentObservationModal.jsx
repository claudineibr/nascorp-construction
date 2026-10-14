import styles from "../App.module.css"

export function InstallmentObservationModal({ row, editing, observation, onChange, saving, hint, onClose, onEdit, onSubmit }) {
  const title = `${editing ? "Editar" : "Ver"} observação da parcela ${row.installmentNumber}/${row.totalInstallments}`
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section className={styles.modalCard} role="dialog" aria-modal="true" aria-label={title}
        onClick={(event) => event.stopPropagation()}>
        <header className={styles.modalHeader}>
          <h3>{title}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={saving}>Fechar</button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          {hint ? <p className={styles.metricHint}>{hint}</p> : null}
          {editing ? (
            <label className={styles.field}>Observação
              <textarea className={styles.observationInput} value={observation}
                disabled={saving || Boolean(hint)} onChange={(event) => onChange(event.target.value)} />
            </label>
          ) : <p className={styles.observationText}>{observation || "Sem observação."}</p>}
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={saving}>Fechar</button>
            {editing ? (
              <button type="submit" className={styles.primaryButton} disabled={saving || Boolean(hint)}>
                {saving ? "Salvando..." : "Salvar observação"}
              </button>
            ) : (
              <button type="button" className={styles.primaryButton} disabled={Boolean(hint)} onClick={onEdit}>
                Editar observação
              </button>
            )}
          </footer>
        </form>
      </section>
    </div>
  )
}
