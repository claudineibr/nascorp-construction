import { useEffect, useRef, useState } from "react"

import styles from "./MeasurementInspections.module.css"
import { InspectorPicker } from "./InspectorPicker"
import { roundStatusLabel } from "./inspectionVocabulary"

const title = {
  non_compliant: "Registrar não conformidade",
  waived: "Dispensar a reinspeção",
}

const hint = {
  non_compliant: "O motivo é o que a reinspeção precisa para existir.",
  waived: "Explique por que esta linha não pode mais ser reinspecionada. Fica no histórico.",
}

// Abre NA PROPRIA LINHA, não em modal: a lista de inspeções já vive dentro de um
// modal, e uma terceira dobra é impossível de ler no celular -- que é onde o
// fiscal preenche a ficha.
export function InspectionRoundForm({
  bridge,
  inspection,
  status,
  defaultInspectorPersonId,
  defaultInspectorName,
  saving,
  onCancel,
  onSubmit,
}) {
  const [comment, setComment] = useState("")
  const [inspectorPersonId, setInspectorPersonId] = useState(defaultInspectorPersonId ?? null)
  const [inspectorName, setInspectorName] = useState(defaultInspectorName ?? "")
  const [openOccurrence, setOpenOccurrence] = useState(false)
  const commentRef = useRef(null)

  useEffect(() => {
    commentRef.current?.focus()
  }, [])

  const previousRound = inspection.lastRound
  const canSubmit = comment.trim().length > 0 && !saving

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!canSubmit) {
      return
    }

    onSubmit({
      status,
      comment: comment.trim(),
      inspectorPersonId,
      openOccurrence: status === "non_compliant" && openOccurrence,
    })
  }

  return (
    <form className={styles.roundForm} onSubmit={handleSubmit}>
      <strong className={styles.roundFormTitle}>
        {title[status] ?? roundStatusLabel[status]} — linha {inspection.sequenceNumber} “{inspection.description}”
      </strong>

      {previousRound?.comment && previousRound.status === "non_compliant" ? (
        <p className={styles.previousComment}>
          Reprovado antes por: <em>{previousRound.comment}</em>
        </p>
      ) : null}

      <label className={styles.roundFormField}>
        <span className={styles.fieldLabel}>Motivo*</span>
        <textarea
          ref={commentRef}
          className={styles.textarea}
          rows={2}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="diferença de 4 cm em relação à cota de projeto"
          required
        />
        <span className={styles.fieldHint}>{hint[status]}</span>
      </label>

      <InspectorPicker
        bridge={bridge}
        value={inspectorPersonId}
        valueName={inspectorName}
        disabled={saving}
        label="Inspetor desta rodada"
        onChange={(personId, personName) => {
          setInspectorPersonId(personId)
          setInspectorName(personName)
        }}
      />

      {status === "non_compliant" ? (
        <label className={styles.checkboxField}>
          <input
            type="checkbox"
            checked={openOccurrence}
            onChange={(event) => setOpenOccurrence(event.target.checked)}
          />
          <span>Registrar também como ocorrência</span>
        </label>
      ) : null}

      <div className={styles.roundFormActions}>
        {inspection.requiresPhoto ? (
          <span className={styles.fieldHint}>Foto: ainda não exigida no preenchimento.</span>
        ) : (
          <span />
        )}
        <div className={styles.roundFormButtons}>
          <button type="button" className={styles.secondaryButton} onClick={onCancel} disabled={saving}>
            Cancelar
          </button>
          <button type="submit" className={styles.primaryButton} disabled={!canSubmit}>
            {saving ? "Registrando..." : title[status] ?? "Registrar"}
          </button>
        </div>
      </div>
    </form>
  )
}
