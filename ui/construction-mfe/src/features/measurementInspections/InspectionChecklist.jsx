import { useMemo, useState } from "react"
import { CheckCircle, History, Plus, ShieldOff, Trash2, TriangleAlert } from "lucide-react"

import styles from "./MeasurementInspections.module.css"
import { InspectionRoundForm } from "./InspectionRoundForm"
import { InspectionRoundsModal } from "./InspectionRoundsModal"
import { InspectorPicker } from "./InspectorPicker"
import { describeActor, describeInspector } from "./actorLabel"
import { countBlockingLines, countPendingLines, deriveLineState, lineStateLabel } from "./inspectionVocabulary"

const stateStyle = {
  pending: styles.statePending,
  compliant: styles.stateCompliant,
  approved_after_reinspection: styles.stateCompliant,
  non_compliant: styles.stateNonCompliant,
  waived: styles.stateWaived,
}

const formatMoment = (value) => {
  if (!value) {
    return ""
  }

  const moment = new Date(value)
  return Number.isNaN(moment.getTime())
    ? ""
    : moment.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" })
}

/**
 * A FVS de um item de medição.
 *
 * Lista em `<ul>` com grid em vez de `<table>`: a tabela do módulo tem
 * `min-width: 760px` e esta lista vive dentro de um modal que já rola, então
 * uma tabela produziria rolagem em dois eixos no celular.
 */
export function InspectionChecklist({
  bridge,
  item,
  people,
  saving,
  isLocked,
  canWaive,
  onVerifyInspection,
  onVerifyAllPending,
  onDeleteInspection,
  onCreateInspection,
}) {
  const [sessionInspectorId, setSessionInspectorId] = useState(item.inspectorPersonId ?? null)
  // O inspetor do item ja vem como id; sem resolver o nome com a lista que a
  // tela ja carregou, o campo abriria mostrando "Pessoa 00000000".
  const [sessionInspectorName, setSessionInspectorName] = useState(
    () => (people ?? []).find((person) => person.id === item.inspectorPersonId)?.name ?? "",
  )
  const [openForm, setOpenForm] = useState(null)
  const [historyFor, setHistoryFor] = useState(null)
  const [newLine, setNewLine] = useState({ description: "", verificationMethod: "" })

  const inspections = item.inspections ?? []
  const summary = useMemo(
    () => ({
      total: inspections.length,
      blocking: countBlockingLines(inspections),
      pending: countPendingLines(inspections),
    }),
    [inspections],
  )

  const handleQuickVerify = (inspection, status) => {
    onVerifyInspection(inspection, {
      status,
      comment: "",
      inspectorPersonId: sessionInspectorId,
      openOccurrence: false,
    })
  }

  const handleFormSubmit = (payload) => {
    const inspection = openForm.inspection
    setOpenForm(null)
    onVerifyInspection(inspection, payload)
  }

  const handleCreate = (event) => {
    event.preventDefault()
    if (!newLine.description.trim()) {
      return
    }

    onCreateInspection(newLine)
    setNewLine({ description: "", verificationMethod: "" })
  }

  return (
    <section className={styles.checklist}>
      <header className={styles.checklistHeader}>
        <div className={styles.checklistInspector}>
          <InspectorPicker
            bridge={bridge}
            value={sessionInspectorId}
            valueName={sessionInspectorName}
            disabled={isLocked || saving}
            label="Inspetor desta rodada"
            onChange={(personId, personName) => {
              setSessionInspectorId(personId)
              setSessionInspectorName(personName)
            }}
          />
        </div>
        {isLocked || summary.pending === 0 ? null : (
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() => onVerifyAllPending(item, { inspectorPersonId: sessionInspectorId })}
            disabled={saving}
          >
            <CheckCircle size={15} />
            Marcar as {summary.pending} pendentes como conformes
          </button>
        )}
      </header>

      <p className={styles.checklistSummary}>
        {summary.total} linha(s) · {summary.blocking} aguardando reinspeção · {summary.pending} pendente(s)
      </p>

      {inspections.length === 0 ? (
        <p className={styles.emptyHint}>Nenhuma linha de verificação cadastrada.</p>
      ) : (
        <ul className={styles.lineList}>
          <li className={styles.lineHeader} aria-hidden="true">
            <span>#</span>
            <span>O que se verifica</span>
            <span>Situação</span>
            <span>Última rodada</span>
            <span>Ações</span>
          </li>
          {inspections.map((inspection) => {
            const state = deriveLineState(inspection)
            const lastRound = inspection.lastRound
            const inspector = lastRound ? describeInspector(lastRound) : ""
            const isFormOpen = openForm?.inspection.id === inspection.id

            return (
              <li key={inspection.id} className={styles.lineRow}>
                <span className={styles.lineSequence}>{inspection.sequenceNumber}</span>

                <span className={styles.lineDescription}>
                  <strong>{inspection.description}</strong>
                  {inspection.verificationMethod ? (
                    <span className={styles.lineMethod}>{inspection.verificationMethod}</span>
                  ) : null}
                </span>

                <span className={styles.lineState}>
                  <span className={`${styles.statePill} ${stateStyle[state] ?? ""}`}>{lineStateLabel[state]}</span>
                </span>

                <span className={styles.lineLastRound}>
                  {lastRound ? (
                    <>
                      <span className={styles.lineMoment}>
                        #{lastRound.sequenceNumber} · {formatMoment(lastRound.verifiedAt)}
                      </span>
                      {inspector ? <span className={styles.lineActor}>insp. {inspector}</span> : null}
                      <span className={styles.lineActor}>lanç. {describeActor(lastRound)}</span>
                      {lastRound.comment ? (
                        <span className={styles.lineComment}>“{lastRound.comment}”</span>
                      ) : null}
                    </>
                  ) : (
                    <span className={styles.lineMoment}>—</span>
                  )}
                </span>

                <span className={styles.lineActions}>
                  {isLocked ? null : (
                    <>
                      {state === "pending" ? (
                        <>
                          <button
                            type="button"
                            className={styles.lineButton}
                            onClick={() => handleQuickVerify(inspection, "compliant")}
                            disabled={saving}
                          >
                            <CheckCircle size={14} />
                            Conforme
                          </button>
                          <button
                            type="button"
                            className={`${styles.lineButton} ${styles.lineButtonWarn}`}
                            onClick={() => setOpenForm({ inspection, status: "non_compliant" })}
                            disabled={saving}
                          >
                            <TriangleAlert size={14} />
                            Não conforme
                          </button>
                        </>
                      ) : state === "non_compliant" ? (
                        <>
                          <button
                            type="button"
                            className={styles.lineButton}
                            onClick={() => handleQuickVerify(inspection, "compliant")}
                            disabled={saving}
                          >
                            <CheckCircle size={14} />
                            Reinspeção aprovada
                          </button>
                          <button
                            type="button"
                            className={`${styles.lineButton} ${styles.lineButtonWarn}`}
                            onClick={() => setOpenForm({ inspection, status: "non_compliant" })}
                            disabled={saving}
                          >
                            <TriangleAlert size={14} />
                            Reprovar de novo
                          </button>
                          {canWaive ? (
                            <button
                              type="button"
                              className={styles.lineButton}
                              onClick={() => setOpenForm({ inspection, status: "waived" })}
                              disabled={saving}
                              title="Liberar o fechamento sem apagar a reprovação"
                            >
                              <ShieldOff size={14} />
                              Dispensar
                            </button>
                          ) : null}
                        </>
                      ) : null}

                      <button
                        type="button"
                        className={styles.iconButton}
                        onClick={() => setHistoryFor(inspection)}
                        disabled={!inspection.roundsCount}
                        aria-label={`Ver as ${inspection.roundsCount} rodadas desta linha`}
                        title={
                          inspection.roundsCount
                            ? `Ver as ${inspection.roundsCount} rodada(s) desta linha`
                            : "Sem rodadas registradas"
                        }
                      >
                        <History size={14} />
                        {inspection.roundsCount || ""}
                      </button>

                      {inspection.roundsCount ? null : (
                        <button
                          type="button"
                          className={`${styles.iconButton} ${styles.dangerIconButton}`}
                          onClick={() => onDeleteInspection(inspection)}
                          disabled={saving}
                          aria-label="Excluir linha da FVS"
                          title="Excluir linha da FVS"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </>
                  )}
                </span>

                {isFormOpen ? (
                  <div className={styles.lineForm}>
                    <InspectionRoundForm
                      bridge={bridge}
                      inspection={inspection}
                      status={openForm.status}
                      defaultInspectorPersonId={sessionInspectorId}
                      defaultInspectorName={sessionInspectorName}
                      saving={saving}
                      onCancel={() => setOpenForm(null)}
                      onSubmit={handleFormSubmit}
                    />
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}

      {isLocked ? null : (
        <form className={styles.newLineForm} onSubmit={handleCreate}>
          <label className={styles.roundFormField}>
            <span className={styles.fieldLabel}>Nova linha de verificação*</span>
            <input
              type="text"
              className={styles.input}
              value={newLine.description}
              onChange={(event) => setNewLine((form) => ({ ...form, description: event.target.value }))}
              placeholder="Prumo e alinhamento"
              required
            />
          </label>
          <label className={styles.roundFormField}>
            <span className={styles.fieldLabel}>Método</span>
            <input
              type="text"
              className={styles.input}
              value={newLine.verificationMethod}
              onChange={(event) => setNewLine((form) => ({ ...form, verificationMethod: event.target.value }))}
              placeholder="Régua de 2m em 3 pontos"
            />
          </label>
          <button type="submit" className={styles.primaryButton} disabled={saving}>
            <Plus size={16} />
            Adicionar linha
          </button>
        </form>
      )}

      {historyFor ? (
        <InspectionRoundsModal inspection={historyFor} onClose={() => setHistoryFor(null)} />
      ) : null}
    </section>
  )
}
