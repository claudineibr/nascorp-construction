import { FileSpreadsheet } from "lucide-react"

import styles from "./MeasurementInspections.module.css"
import { describeActor, describeInspector } from "./actorLabel"
import { roundStatusLabel } from "./inspectionVocabulary"

const roundStyle = {
  compliant: styles.roundCompliant,
  non_compliant: styles.roundNonCompliant,
  waived: styles.roundWaived,
}

const formatMoment = (value) => {
  if (!value) {
    return ""
  }

  const moment = new Date(value)
  return Number.isNaN(moment.getTime()) ? "" : moment.toLocaleString("pt-BR")
}

const formatDay = (value) => {
  if (!value) {
    return ""
  }

  const [year, month, day] = String(value).split("-")
  return day ? `${day}/${month}/${year}` : String(value)
}

export function InspectionRoundsModal({ inspection, onClose }) {
  const rounds = [...(inspection.rounds ?? [])].reverse()

  return (
    <div className={styles.historyOverlay} role="dialog" aria-modal="true">
      <div className={styles.historyCard}>
        <header className={styles.historyHeader}>
          <h3>
            Rodadas · linha {inspection.sequenceNumber} “{inspection.description}”
          </h3>
          <button type="button" className={styles.secondaryButton} onClick={onClose}>
            Fechar
          </button>
        </header>

        <div className={styles.historyBody}>
          {rounds.length === 0 ? (
            <p className={styles.emptyHint}>Esta linha ainda não foi verificada.</p>
          ) : (
            <ol className={styles.timeline}>
              {rounds.map((round) => {
                const inspector = describeInspector(round)
                const recorder = describeActor(round)
                return (
                  <li key={round.id} className={styles.timelineRow}>
                    <div className={styles.timelineHead}>
                      <span className={`${styles.roundBadge} ${roundStyle[round.status] ?? ""}`}>
                        {round.sequenceNumber}. {roundStatusLabel[round.status] ?? round.status}
                      </span>
                      <span className={styles.timelineMoment}>{formatMoment(round.verifiedAt)}</span>
                      {round.source === "migration" ? (
                        <span className={styles.sourceTag} title="Veio da carga do sistema antigo">
                          <FileSpreadsheet size={12} />
                          carga do legado
                        </span>
                      ) : null}
                      {round.isInferred ? (
                        <span
                          className={styles.sourceTag}
                          title="Reprovação deduzida do status do legado: data, motivo e responsável não foram preservados"
                        >
                          inferida
                        </span>
                      ) : null}
                    </div>

                    <span className={styles.timelineActor}>
                      {inspector ? `inspetor ${inspector} · ` : ""}
                      lançado por {recorder}
                    </span>
                    {round.inspectedOn ? (
                      <span className={styles.timelineDetail}>em campo em {formatDay(round.inspectedOn)}</span>
                    ) : null}
                    {round.comment ? <span className={styles.timelineComment}>“{round.comment}”</span> : null}
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      </div>
    </div>
  )
}
