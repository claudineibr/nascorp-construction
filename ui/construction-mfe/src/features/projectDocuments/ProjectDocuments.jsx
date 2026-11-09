import { useEffect, useState } from "react"
import { Download, RefreshCw } from "lucide-react"
import { UnitBankSlipDialogFrame } from "../UnitBankSlipsDialog.jsx"
import { requestJson } from "../../services/constructionApi.js"
import { readProjectFile } from "../../services/projectFiles.js"
import { formatBusinessDate } from "../../utils/brazilDate.js"
import styles from "../../App.module.css"
import documentStyles from "./ProjectDocuments.module.css"

const api = "/v1/construction"
const projectPath = (projectId) => `${api}/projects/${projectId}/documents`
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" })
const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 })
const MAX_BYTES = 8 * 1024 * 1024

function label(document) {
  return document.kind === "contract" ? `Contrato ${document.snapshot.contract_number}`
    : `${document.snapshot.sequence}ª medição de ${formatBusinessDate(document.snapshot.measured_on)}`
}

function measuredAmounts(document) {
  const data = document.snapshot
  return `${number.format(data.actual_percent)}% do valor do contrato medido, ${number.format(data.planned_percent)}% previsto e desvio de ${number.format(data.variance_points)} p.p.`
}

export function ProjectDocumentModal({ bridge, mode, projectId, sourceFile, onClose, onComplete }) {
  const kind = mode === "measurement" ? "measurement" : "contract"
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [code, setCode] = useState("")
  const [name, setName] = useState("")
  const [createPhases, setCreatePhases] = useState(false)
  const [busy, setBusy] = useState(false)
  const canCreatePhases = bridge.canCreate?.("construction_schedule")
  const title = mode === "create" ? "Criar empreitada pelo contrato"
    : kind === "contract" ? "Vincular contrato" : "Importar medição"

  const submit = async (event) => {
    event.preventDefault()
    if ((!file && !sourceFile) || busy) return
    const size = file?.size ?? sourceFile.file_size
    if (size > MAX_BYTES || !size) {
      bridge.feedback?.error?.("O documento precisa ter conteúdo e até 8 MB.")
      return
    }
    setBusy(true)
    try {
      let documentFile = file
      if (!documentFile) {
        const original = await readProjectFile(bridge, projectId, sourceFile.id)
        if (original.size > MAX_BYTES || !original.size) {
          throw new Error("O arquivo anexado precisa ter conteúdo e até 8 MB.")
        }
        documentFile = new File([original], sourceFile.file_name)
        setFile(documentFile)
      }
      const body = new FormData()
      body.append("file", documentFile)
      body.append("kind", kind)
      if (!preview) {
        if (projectId) body.append("project_id", projectId)
        const result = await requestJson({ bridge, path: `${api}/project-documents/preview`, method: "POST", body })
        setPreview(result)
        if (mode === "create") {
          setName(result.snapshot.name)
          setCode(`CT-${result.snapshot.contract_number.replace("/", "-")}`)
        }
        return
      }
      if (mode === "create") {
        body.append("code", code.trim())
        body.append("name", name.trim())
      } else if (kind === "measurement") {
        body.append("create_phases", String(createPhases))
      }
      const path = mode === "create" ? `${api}/projects/from-contract` : projectPath(projectId)
      const result = await requestJson({ bridge, path, method: "POST", body })
      bridge.feedback?.success?.(mode === "create" ? "Empreitada criada pelo contrato."
        : kind === "contract" ? "Contrato vinculado à obra." : "Medição registrada no cronograma.")
      onComplete(result)
    } catch (error) {
      bridge.feedback?.error?.(error.message)
    } finally {
      setBusy(false)
    }
  }

  const footer = <>
    <button className={styles.secondaryButton} type="button" onClick={onClose} disabled={busy}>Cancelar</button>
    <button className={styles.primaryButton} type="submit" form="project-document-form" disabled={(!file && !sourceFile) || busy}>
      {busy ? "Processando…" : preview ? title : "Ler documento"}
    </button>
  </>
  return <UnitBankSlipDialogFrame bridge={bridge} title={title} onClose={busy ? undefined : onClose} footer={footer}>
    <form id="project-document-form" className={documentStyles.form} onSubmit={submit}>
      {sourceFile ? <p>Arquivo da obra <strong>{sourceFile.file_name}</strong></p>
        : <label className={documentStyles.field}>{kind === "contract" ? "Contrato em PDF *" : "Boletim de Medição em XLSX *"}
          <input type="file" accept={kind === "contract" ? ".pdf" : ".xlsx"} required disabled={busy}
            onChange={(event) => { setFile(event.target.files[0] ?? null); setPreview(null); setCreatePhases(false) }} />
        </label>}
      {preview && <>
        <strong>{label(preview)}</strong>
        {kind === "contract" ? <>
          <p>{preview.snapshot.customer || "Contratante"} · CNPJ {preview.snapshot.customer_document}</p>
          <p>{preview.snapshot.object} (p. {preview.snapshot.object_page})</p>
          {preview.snapshot.contract_value && <p>Valor do contrato: R$ {preview.snapshot.contract_value}</p>}
          {preview.snapshot.term && <p>{preview.snapshot.term} (p. {preview.snapshot.term_page})</p>}
          <p>Confirme as datas de execução nos documentos da obra antes de cadastrar os prazos.</p>
          {mode === "create" && <>
            <label className={documentStyles.field}>Código *
              <input value={code} required maxLength={50} disabled={busy} onChange={(event) => setCode(event.target.value)} />
            </label>
            <label className={documentStyles.field}>Nome *
              <input value={name} required maxLength={255} disabled={busy} onChange={(event) => setName(event.target.value)} />
            </label>
          </>}
        </> : <>
          <p>{measuredAmounts(preview)}</p>
          <p>{preview.snapshot.sheet} · linha {preview.snapshot.summary_row}</p>
          <ul className={documentStyles.previewList}>{preview.snapshot.phases.map((phase) =>
            <li key={phase.row}>{phase.name} · linha {phase.row} · {money.format(phase.measured)} no boletim</li>
          )}</ul>
          {canCreatePhases && <label>
            <input type="checkbox" checked={createPhases} disabled={busy}
              onChange={(event) => setCreatePhases(event.target.checked)} /> Criar etapas faltantes
          </label>}
          <p>As etapas são vinculadas pelo nome. Cadastre as datas previstas no Cronograma.</p>
        </>}
      </>}
    </form>
  </UnitBankSlipDialogFrame>
}

export function useProjectDocumentHistory(bridge, projectId, enabled = true) {
  const [history, setHistory] = useState(null)
  const [failed, setFailed] = useState(false)
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    if (!enabled) return undefined
    const controller = new AbortController()
    setFailed(false)
    requestJson({ bridge, path: projectPath(projectId), signal: controller.signal }).then((result) => {
      if (!controller.signal.aborted) setHistory(result)
    }).catch((error) => {
      if (controller.signal.aborted) return
      setFailed(true)
      bridge.feedback?.error?.(error.message)
    })
    return () => controller.abort()
  }, [bridge, projectId, revision, enabled])

  return {
    history: enabled ? history : null,
    failed: enabled && failed,
    refresh: () => setRevision((value) => value + 1),
  }
}

export function ImportedProjectFiles({ bridge, projectId, documents }) {
  const download = async (document) => {
    try {
      const file = await requestJson({
        bridge, path: `${projectPath(projectId)}/${document.id}/download`, responseType: "blob",
      })
      const url = URL.createObjectURL(file)
      const link = window.document.createElement("a")
      link.href = url
      link.download = document.file_name
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      bridge.feedback?.error?.(error.message)
    }
  }

  if (!documents.length) return null
  return <section className={documentStyles.panel} aria-label="Contratos e boletins importados">
    <h3>Contratos e boletins importados</h3>
    <ul className={documentStyles.history}>{documents.map((document) => (
      <li key={document.id}>
        <div><strong>{document.file_name}</strong><p>{label(document)}</p></div>
        <button className={styles.secondaryButton} type="button" onClick={() => download(document)}>
          <Download size={16} aria-hidden="true" /> Baixar original
        </button>
      </li>
    ))}</ul>
  </section>
}

export function ProjectScheduleSummary({ bridge, projectId, children }) {
  const { history, failed, refresh } = useProjectDocumentHistory(bridge, projectId)
  const contract = history?.items.find((item) => item.kind === "contract")
  const measurements = (history?.items ?? []).filter((item) => item.kind === "measurement").sort((left, right) =>
    right.snapshot.measured_on.localeCompare(left.snapshot.measured_on) || right.snapshot.sequence - left.snapshot.sequence)
  const measuredByPhase = new Map()
  for (const document of measurements) {
    for (const phase of document.snapshot.phases) {
      if (!measuredByPhase.has(phase.phase_id)) measuredByPhase.set(phase.phase_id, phase)
    }
  }
  return <>
    {children(history?.today, measuredByPhase)}
    <section className={documentStyles.panel} aria-label="Acompanhamento da empreitada">
      <h3>Acompanhamento da empreitada</h3>
      {failed ? <button type="button" className={styles.secondaryButton} onClick={refresh}>
        <RefreshCw size={16} aria-hidden="true" /> Tentar novamente
      </button> : !history ? <p role="status">Carregando dados da empreitada…</p>
        : !history.total ? <p>Vincule o contrato na aba Arquivos para iniciar o acompanhamento.</p> : <>
          {contract?.snapshot.term && <p><strong>Vigência contratual:</strong> {contract.snapshot.term}</p>}
          <ul className={documentStyles.history}>{measurements.map((document) =>
            <li key={document.id}>
              <div><strong>{label(document)}</strong><p>{measuredAmounts(document)}</p></div>
            </li>)}
          </ul>
        </>}
    </section>
  </>
}

export function phaseDeadline(phase, today) {
  if (phase.status === "cancelled") return "—"
  if (!phase.plannedEndDate) return "Sem prazo"
  if (phase.status === "completed" && !phase.actualEndDate) return "Sem data de conclusão"
  const reference = phase.actualEndDate || today
  if (!reference) return "—"
  const days = (Date.parse(phase.plannedEndDate) - Date.parse(reference)) / 86400000
  if (days < 0) return `${-days} d de atraso`
  if (phase.actualEndDate) return "Concluída no prazo"
  if (days === 0) return "Vence hoje"
  return `${days} d restantes`
}
