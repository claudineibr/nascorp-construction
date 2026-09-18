import { useEffect, useState } from "react"
import { ChevronDown, ChevronRight, FileSpreadsheet } from "lucide-react"

import appStyles from "../../App.module.css"
import styles from "./ServiceTemplates.module.css"
import { listConstructionServiceTemplateAudits } from "../../services/constructionApi"

const eventLabel = {
  created: "Cadastrado",
  updated: "Alterado",
  replaced: "Ficha revisada",
  activated: "Reativado",
  deactivated: "Desativado",
  deleted: "Excluído",
}

const eventStyle = {
  created: styles.eventCreated,
  updated: styles.eventUpdated,
  replaced: styles.eventUpdated,
  activated: styles.eventCreated,
  deactivated: styles.eventWarning,
  deleted: styles.eventDanger,
}

const formatMoment = (value) => {
  if (!value) {
    return ""
  }

  const moment = new Date(value)
  return Number.isNaN(moment.getTime()) ? "" : moment.toLocaleString("pt-BR")
}

// The trail predates the audit table for services imported before it existed:
// there is a row, but nobody was captured. Saying so is more honest than an
// empty space the reader has to interpret.
const describeActor = (audit) => {
  if (audit.actorName) {
    return audit.actorName
  }

  if (audit.source === "migration") {
    return "Autor não registrado (anterior à auditoria)"
  }

  return audit.actorUserId ? `Usuário ${audit.actorUserId.slice(0, 8)}` : "Autor não identificado"
}

function AuditSnapshot({ snapshot }) {
  const sections = snapshot?.sections ?? []
  if (sections.length === 0) {
    return <p className={styles.snapshotEmpty}>A ficha não tinha nenhuma seção nesta versão.</p>
  }

  return (
    <div className={styles.snapshotBody}>
      {sections.map((section) => (
        <div key={`${section.sequence_number}-${section.name}`} className={styles.snapshotSection}>
          <strong>
            {section.sequence_number}. {section.name}
          </strong>
          <ol className={styles.snapshotItems}>
            {(section.items ?? []).map((item) => (
              <li key={item.sequence_number}>
                <span className={styles.snapshotItemText}>{item.description}</span>
                <span className={styles.snapshotItemMethod}>{item.verification_method}</span>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}

export function ServiceTemplateHistoryModal({ bridge, template, onClose }) {
  const [audits, setAudits] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    let active = true

    const load = async () => {
      setLoading(true)
      setError("")
      try {
        const response = await listConstructionServiceTemplateAudits({
          bridge,
          serviceTemplateId: template.id,
        })
        if (active) {
          setAudits(response.items)
        }
      } catch (loadError) {
        if (active) {
          setError(loadError?.message ?? "Não foi possível carregar o histórico do serviço.")
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
  }, [bridge, template.id])

  return (
    <div className={appStyles.modalOverlay} role="dialog" aria-modal="true">
      <div className={`${appStyles.modalCard} ${styles.historyCard}`}>
        <header className={appStyles.modalHeader}>
          <h3>Histórico · {template.name}</h3>
          <button type="button" className={appStyles.closeButton} onClick={onClose}>
            Fechar
          </button>
        </header>

        <div className={appStyles.modalBody}>
          {loading ? (
            <p className={styles.loading}>Carregando histórico...</p>
          ) : error ? (
            <p className={styles.empty}>{error}</p>
          ) : audits.length === 0 ? (
            <p className={styles.empty}>Nenhum evento registrado para este serviço.</p>
          ) : (
            <ol className={styles.timeline}>
              {audits.map((audit) => {
                const isExpanded = expanded === audit.id
                return (
                  <li key={audit.id} className={styles.timelineRow}>
                    <div className={styles.timelineHead}>
                      <span className={`${styles.eventBadge} ${eventStyle[audit.event] ?? ""}`}>
                        {eventLabel[audit.event] ?? audit.event}
                      </span>
                      <span className={styles.timelineMoment}>{formatMoment(audit.createdAt)}</span>
                      {audit.source === "import" ? (
                        <span className={styles.sourceTag} title="Veio da importação de planilha">
                          <FileSpreadsheet size={12} />
                          Planilha
                        </span>
                      ) : null}
                    </div>

                    <span className={styles.timelineActor}>{describeActor(audit)}</span>
                    {audit.summary ? <span className={styles.timelineSummary}>{audit.summary}</span> : null}
                    {audit.serviceName !== template.name ? (
                      <span className={styles.timelineSummary}>
                        Na época o serviço se chamava <strong>{audit.serviceName}</strong>.
                      </span>
                    ) : null}

                    {audit.snapshot ? (
                      <>
                        <button
                          type="button"
                          className={styles.textButton}
                          onClick={() => setExpanded(isExpanded ? null : audit.id)}
                          aria-expanded={isExpanded}
                        >
                          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          {isExpanded ? "Ocultar a ficha desta versão" : "Ver a ficha desta versão"}
                        </button>
                        {isExpanded ? <AuditSnapshot snapshot={audit.snapshot} /> : null}
                      </>
                    ) : null}
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
