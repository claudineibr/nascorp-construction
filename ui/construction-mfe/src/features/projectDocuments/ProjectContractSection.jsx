import { useEffect, useId, useRef, useState } from "react"
import { listConstructionPersonSummaries, previewProjectContract } from "../../services/constructionApi.js"
import { checkProjectFileAvailability, listAllProjectFiles } from "../../services/projectFiles.js"
import { formatBusinessDate } from "../../utils/brazilDate.js"
import { downloadProjectDocument, useProjectDocumentHistory } from "./ProjectDocuments.jsx"
import styles from "../../App.module.css"
import documentStyles from "./ProjectDocuments.module.css"

const MAX_PDF_BYTES = 8 * 1024 * 1024
const FILES_PER_PAGE = 20
const AVAILABILITY_BATCH_SIZE = 6
const digits = (value) => String(value ?? "").replace(/\D/g, "")

async function listAvailableContractFiles(bridge, projectId, signal) {
  const { items } = await listAllProjectFiles(bridge, projectId, signal)
  const candidates = items.filter((file) =>
    /\.pdf$/i.test(file.file_name) && file.file_size > 0 && file.file_size <= MAX_PDF_BYTES)
  const available = []
  for (let offset = 0; offset < candidates.length; offset += AVAILABILITY_BATCH_SIZE) {
    const batch = candidates.slice(offset, offset + AVAILABILITY_BATCH_SIZE)
    const checks = await Promise.all(batch.map((file) =>
      checkProjectFileAvailability(bridge, projectId, file.id, signal)))
    available.push(...batch.filter((_, index) => checks[index]))
  }
  return available
}

export function ProjectContractSection({ bridge, projectId, projectForm, draft, reading, focusImport,
  onDraft, onReading, onChange, people,
}) {
  const titleId = useId()
  const input = useRef(null)
  const importButton = useRef(null)
  const firstFileButton = useRef(null)
  const previewRequest = useRef(null)
  const [choosing, setChoosing] = useState(false)
  const [page, setPage] = useState(1)
  const [availableFiles, setAvailableFiles] = useState(null)
  const [fileError, setFileError] = useState(false)
  const [filesRevision, setFilesRevision] = useState(0)
  const documents = useProjectDocumentHistory(bridge, projectId, Boolean(projectId))
  const linked = documents.history?.items.find((document) => document.kind === "contract")
  const canLookUpFiles = Boolean(projectId && documents.history && !linked)

  useEffect(() => () => previewRequest.current?.abort(), [])
  useEffect(() => {
    if (focusImport) importButton.current?.focus()
  }, [focusImport])
  useEffect(() => {
    if (choosing) firstFileButton.current?.focus()
  }, [choosing])
  useEffect(() => {
    if (!canLookUpFiles) return undefined
    const controller = new AbortController()
    listAvailableContractFiles(bridge, projectId, controller.signal).then((files) => {
      if (!controller.signal.aborted) {
        setFileError(false)
        setAvailableFiles(files)
      }
    }).catch(() => {
      if (!controller.signal.aborted) setFileError(true)
    })
    return () => controller.abort()
  }, [bridge, canLookUpFiles, filesRevision, projectId])

  const read = async (source) => {
    if (previewRequest.current) return
    if (source.file && (!source.file.size || source.file.size > MAX_PDF_BYTES)) {
      bridge.feedback?.error?.("Selecione um PDF não vazio de até 8 MB.")
      return
    }
    const controller = new AbortController()
    previewRequest.current = controller
    onReading(true)
    try {
      const preview = await previewProjectContract({ bridge, projectId, contractDraft: source, signal: controller.signal })
      const document = preview.snapshot.customer_document
      let customer = people.find((person) => person.isActive && digits(person.document) === document)
      if (!customer && document) {
        try {
          const { items } = await listConstructionPersonSummaries({ bridge, search: document, signal: controller.signal })
          customer = items.find((person) => person.isActive && digits(person.document) === document)
        } catch {
          if (controller.signal.aborted) return
        }
      }
      if (!controller.signal.aborted) {
        onDraft({ ...source, preview, customer })
        setChoosing(false)
      }
    } catch (error) {
      if (!controller.signal.aborted) bridge.feedback?.error?.(error.message)
    } finally {
      previewRequest.current = null
      if (!controller.signal.aborted) onReading(false)
    }
  }

  const snapshot = draft?.preview.snapshot
  const currentCustomer = people.find((person) => person.id === projectForm.customerPersonId)
  const suggestions = snapshot ? [
    ...(!projectId ? [["Código", "code", `CT-${snapshot.contract_number.replace("/", "-")}`]] : []),
    ["Nome da obra", "name", snapshot.name],
    ["Descrição", "description", snapshot.object],
    ["Custo estimado", "estimatedCost", snapshot.contract_value],
    ["Cliente/Contratante", "customerPersonId", draft.customer?.id, draft.customer?.name, currentCustomer?.name],
  ].filter(([, , value]) => value) : []
  const totalFilePages = Math.ceil((availableFiles?.length ?? 0) / FILES_PER_PAGE)
  const files = availableFiles?.slice((page - 1) * FILES_PER_PAGE, page * FILES_PER_PAGE) ?? []

  return <section className={styles.projectFormSection} aria-labelledby={titleId}>
    <h4 id={titleId} className={styles.sectionTitle}>Contrato com o cliente</h4>
    {linked ? <div className={documentStyles.form}>
      <strong>Contrato {linked.snapshot.contract_number}</strong>
      {linked.snapshot.contract_value && <p>Valor original R$ {linked.snapshot.contract_value}</p>}
      {linked.snapshot.term && <p>{linked.snapshot.term}</p>}
      <div className={styles.projectFormActions}>
        <button type="button" className={styles.secondaryButton}
          onClick={() => downloadProjectDocument(bridge, projectId, linked)}>Ver contrato</button>
      </div>
    </div> : projectId && !documents.history ? (
      documents.failed ? <button type="button" className={styles.secondaryButton}
        onClick={documents.refresh}>Tentar novamente</button> : <p role="status">Carregando contrato…</p>
    ) : <div className={documentStyles.form}>
      <input ref={input} type="file" accept=".pdf" hidden
        aria-label="Selecionar contrato em PDF" onChange={(event) => {
          const file = event.target.files[0]
          event.target.value = ""
          if (file) void read({ file })
        }} />
      <div className={styles.projectFormActions}>
        <button ref={importButton} type="button" className={styles.secondaryButton} disabled={reading}
          onClick={() => input.current?.click()}>Importar PDF</button>
        {projectId && <button type="button" className={styles.secondaryButton}
          disabled={reading || fileError || !availableFiles?.length}
          onClick={() => { setPage(1); setChoosing(!choosing) }}>
          {choosing ? "Fechar seleção de arquivos" : "Selecionar dos Arquivos"}
        </button>}
        {draft && <button type="button" className={styles.secondaryButton} disabled={reading}
          onClick={() => onDraft(null)}>Descartar PDF</button>}
      </div>
      {reading && <p role="status">Lendo contrato…</p>}
      {projectId && fileError && <div className={documentStyles.form}>
        <p role="alert">Não foi possível consultar os arquivos da obra.</p>
        <div className={styles.projectFormActions}>
          <button type="button" className={styles.secondaryButton} disabled={reading}
            onClick={() => {
              setAvailableFiles(null)
              setChoosing(false)
              setFileError(false)
              setFilesRevision((value) => value + 1)
            }}>Tentar novamente</button>
        </div>
      </div>}
      {projectId && !fileError && availableFiles === null && <p role="status">Verificando os arquivos da obra…</p>}
      {projectId && !fileError && availableFiles?.length === 0 && <p>Nenhum PDF de até 8 MB disponível em Arquivos.</p>}
      {choosing && files.length > 0 && <div className={documentStyles.form}>
        <ul className={documentStyles.history}>{files.map((file, index) =>
          <li key={file.id}><span>{file.file_name}</span>
            <button ref={index === 0 ? firstFileButton : null} type="button" className={styles.secondaryButton} disabled={reading}
              aria-label={`Ler ${file.file_name}`}
              onClick={() => void read({ sourceFileId: file.id })}>Ler PDF</button>
          </li>
        )}</ul>
        {totalFilePages > 1 && <div className={styles.projectFormActions}>
          <button type="button" className={styles.secondaryButton} disabled={reading || page <= 1}
            onClick={() => setPage(page - 1)}>Anterior</button>
          <button type="button" className={styles.secondaryButton} disabled={reading || page >= totalFilePages}
            onClick={() => setPage(page + 1)}>Próxima</button>
        </div>}
      </div>}
      {snapshot && <div className={documentStyles.form}>
        <strong>Prévia do contrato {snapshot.contract_number}</strong>
        <p>{draft.preview.file_name}</p>
        <p>{snapshot.customer || "Contratante"} · CNPJ {snapshot.customer_document}</p>
        {snapshot.term && <p>{snapshot.term}</p>}
        <p>Previsão de início {formatBusinessDate(projectForm.plannedStartDate)} · Previsão de término {formatBusinessDate(projectForm.expectedEndDate)}</p>
        <ul className={documentStyles.history}>{suggestions.map(([label, field, value, display, current]) => (
          <li key={field}>
            <div><strong>{label}</strong>
              <p>Do PDF {display || value}</p>
              <p>No cadastro {current || (field === "customerPersonId"
                ? (projectForm[field] ? "Contratante selecionado" : "Em branco")
                : projectForm[field] || "Em branco")}</p>
            </div>
            <button type="button" className={styles.secondaryButton} disabled={reading || projectForm[field] === value}
              onClick={() => onChange(field, value)}>Usar {label.toLowerCase()}</button>
          </li>
        ))}</ul>
        <p>O PDF será vinculado quando você salvar a obra.</p>
      </div>}
    </div>}
  </section>
}
