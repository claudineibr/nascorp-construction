import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ArrowDown, ArrowUp, ArrowUpDown, ClipboardCheck, Download, RefreshCcw, Trash2, Upload } from "lucide-react"
import { Pagination as StandalonePagination } from "../../components/Pagination.jsx"
import { listAllProjectFiles, listProjectFiles, uploadProjectFile, downloadProjectFile, deleteProjectFile } from "../../services/projectFiles.js"
import { formatBusinessDate } from "../../utils/brazilDate.js"
import { UnitBankSlipDialogFrame } from "../UnitBankSlipsDialog.jsx"
import {
  downloadProjectDocument,
  projectDocumentLabel,
  ProjectMeasurementDocumentModal,
  useProjectDocumentHistory,
} from "../projectDocuments/ProjectDocuments.jsx"
import styles from "./ProjectFilesPanel.module.css"

const sizeFormat = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 })
const formatFileSize = (bytes) => {
  if (bytes == null) return "—"
  return bytes < 1024 * 1024
    ? `${sizeFormat.format(Math.max(bytes / 1024, 0.01))} KB`
    : `${sizeFormat.format(bytes / 1024 / 1024)} MB`
}
const emptyFiles = { items: [], total: 0, total_pages: 0 }
const defaultSort = { key: "created_at", direction: "descending" }
const sortColumns = [
  { key: "file_name", label: "Nome" },
  { key: "file_size", label: "Tamanho" },
  { key: "created_at", label: "Enviado em" },
]
const fileNameOrder = new Intl.Collator("pt-BR", { numeric: true, sensitivity: "base" })

function compareFiles(left, right, { key, direction }) {
  const leftValue = left[key]
  const rightValue = right[key]
  if (leftValue == null || rightValue == null) {
    if (leftValue == null && rightValue == null) return left.id.localeCompare(right.id)
    return leftValue == null ? 1 : -1
  }
  const order = key === "file_name" ? fileNameOrder.compare(leftValue, rightValue)
    : key === "created_at" ? Date.parse(leftValue) - Date.parse(rightValue)
      : leftValue - rightValue
  return (direction === "ascending" ? order : -order) || right.id.localeCompare(left.id)
}

function mergeFiles(files, documents) {
  const filesById = new Map(files.map((file) => [file.id, file]))
  const imported = documents.map((document) => {
    const sourceIds = [document.snapshot.source_file_id, ...(document.snapshot.additional_source_file_ids ?? [])]
    const source = sourceIds.map((id) => filesById.get(id)).find(Boolean)
    sourceIds.forEach((id) => filesById.delete(id))
    return { ...document, file_size: source?.file_size, created_at: document.created_at ?? source?.created_at }
  })
  return [...imported, ...filesById.values()]
}

export function ProjectFilesPanel({ bridge, projectId, contractWork, RowActionsMenu, ConfirmModal, renderActions, onImported, reloadRevision }) {
  const [result, setResult] = useState(emptyFiles)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [sort, setSort] = useState(defaultSort)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [revision, setRevision] = useState(0)
  const [uploadChoice, setUploadChoice] = useState(null)
  const [sourceFile, setSourceFile] = useState(null)
  const input = useRef(null)
  const addendumInput = useRef(null)
  const activeUpload = useRef(null)
  const canRead = bridge?.canRead?.("construction_projects") === true
  const canCreate = bridge?.canCreate?.("construction_projects") === true
  const canDelete = bridge?.canDelete?.("construction_projects") === true
  const canReadDocuments = canRead && contractWork
  const canImportMeasurement = canReadDocuments && bridge.canRead?.("construction_schedule")
    && bridge.canRead?.("construction_measurements") && bridge.canCreate?.("construction_measurements")
  const documents = useProjectDocumentHistory(bridge, projectId, canReadDocuments, reloadRevision)
  const contract = documents.history?.items.find((file) => file.kind === "contract")
  const canAttachAddenda = canCreate && contractWork
  const showUploadChoices = canAttachAddenda || (canImportMeasurement && (contract || !documents.history))
  const importedFiles = documents.history?.items ?? emptyFiles.items
  const waitingDocuments = canReadDocuments && !documents.history && !documents.failed
  const useLocalSort = importedFiles.length > 0 || sort.key !== defaultSort.key || sort.direction !== defaultSort.direction
  const requestPage = useLocalSort ? 1 : page
  const requestPageSize = useLocalSort ? 100 : pageSize
  const files = useMemo(() => useLocalSort
    ? mergeFiles(result.items, importedFiles).sort((left, right) => compareFiles(left, right, sort))
    : result.items, [result.items, importedFiles, sort, useLocalSort])
  const total = useLocalSort ? files.length : result.total
  const totalPages = useLocalSort ? Math.ceil(total / pageSize) : result.total_pages
  const currentPage = Math.min(page, Math.max(1, totalPages))
  const visibleFiles = useLocalSort ? files.slice((currentPage - 1) * pageSize, currentPage * pageSize) : files
  const loadingFiles = loading || waitingDocuments
  const Pagination = bridge.components?.Pagination ?? StandalonePagination
  const Actions = bridge.components?.RowActionsMenu ?? RowActionsMenu
  const report = useCallback((error) => bridge.feedback?.error?.(error.message), [bridge])
  const refresh = () => setRevision((value) => value + 1)

  useEffect(() => () => activeUpload.current?.abort(), [])

  useEffect(() => {
    if (!canRead || waitingDocuments) return undefined
    const controller = new AbortController()
    setLoading(true)
    setFailed(false)
    const request = useLocalSort
      ? listAllProjectFiles(bridge, projectId, controller.signal)
      : listProjectFiles(bridge, projectId, requestPage, requestPageSize, controller.signal)
    request.then((data) => {
      if (controller.signal.aborted) return
      if (!useLocalSort && requestPage > 1 && !data.items.length) {
        setPage(Math.max(1, data.total_pages))
        return
      }
      setResult(data)
    }).catch((error) => {
      if (controller.signal.aborted) return
      setResult(emptyFiles)
      setFailed(true)
      report(error)
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [bridge, projectId, requestPage, requestPageSize, revision, reloadRevision, canRead, waitingDocuments, useLocalSort, report])

  const changeSort = (key) => {
    setSort((previous) => ({
      key,
      direction: previous.key === key && previous.direction === "ascending" ? "descending" : "ascending",
    }))
    setPage(1)
  }

  const upload = async (event, addenda = false) => {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ""
    if (!files.length || activeUpload.current) return
    if (addenda && files.some((file) => !/\.pdf$/i.test(file.name))) {
      report(new Error("Selecione os aditivos em PDF."))
      return
    }
    if (files.some((file) => !file.size || file.size > 20 * 1024 * 1024)) {
      report(new Error("Selecione arquivos não vazios de até 20 MB cada."))
      return
    }
    const controller = new AbortController()
    activeUpload.current = controller
    let sent = 0
    try {
      for (const file of files) {
        await uploadProjectFile(bridge, projectId, file, {
          signal: controller.signal,
          onProgress: (percent) => {
            if (!controller.signal.aborted) setUploadStatus({ name: file.name, index: sent + 1, total: files.length, percent })
          },
        })
        sent += 1
      }
      if (!controller.signal.aborted) bridge.feedback?.success?.(`${sent} arquivo(s) enviado(s).`)
    } catch (error) {
      if (!controller.signal.aborted) {
        report(new Error(`${sent} de ${files.length} arquivo(s) enviado(s). ${error.message}`))
      }
    } finally {
      activeUpload.current = null
      if (!controller.signal.aborted) {
        setUploadStatus(null)
        refresh()
      }
    }
  }

  const download = async (file) => {
    setBusy(true)
    try {
      if (file.kind) await downloadProjectDocument(bridge, projectId, file)
      else await downloadProjectFile(bridge, projectId, file)
    }
    catch (error) { report(error) }
    finally { setBusy(false) }
  }

  const remove = async () => {
    if (busy) return
    setBusy(true)
    try {
      await deleteProjectFile(bridge, projectId, deleting.id)
      setDeleting(null)
      bridge.feedback?.success?.("Arquivo removido.")
      refresh()
    } catch (error) { report(error) }
    finally { setBusy(false) }
  }

  const openMeasurement = (file) => {
    setSourceFile(file)
    setUploadChoice("measurement")
  }

  const closeUpload = () => {
    setSourceFile(null)
    setUploadChoice(null)
  }

  if (!canRead) return <p>Você não tem permissão para consultar arquivos desta obra.</p>
  return <section className={styles.panel}>
    {renderActions(<>
      <button type="button" className={styles.secondaryButton} disabled={busy || loadingFiles}
        onClick={() => { refresh(); if (canReadDocuments) documents.refresh() }}>
        <RefreshCcw size={16} aria-hidden="true" />{failed || documents.failed ? "Tentar novamente" : "Atualizar"}
      </button>
      {(canCreate || showUploadChoices) && <button type="button" className={styles.primaryButton} disabled={Boolean(uploadStatus)}
        onClick={() => showUploadChoices ? setUploadChoice("choose") : input.current?.click()}>
        <Upload size={16} aria-hidden="true" />{uploadStatus ? "Enviando arquivos…" : "Enviar arquivos"}
      </button>}
    </>)}
    {canCreate && <input ref={input} className={styles.fileInput} type="file" multiple
      aria-label="Selecionar arquivos da obra" onChange={(event) => void upload(event)} disabled={Boolean(uploadStatus)} />}
    {canAttachAddenda && <input ref={addendumInput} className={styles.fileInput} type="file" multiple accept=".pdf"
      aria-label="Selecionar PDFs de aditivos" onChange={(event) => void upload(event, true)} disabled={Boolean(uploadStatus)} />}
    {uploadStatus && <div className={styles.uploadStatus}>
      <div role="status">
        <strong>{uploadStatus.percent === 100 ? "Confirmando envio" : "Enviando arquivo"} {uploadStatus.index} de {uploadStatus.total}</strong>
        <span>{uploadStatus.name}</span>
      </div>
      <progress max={100} value={uploadStatus.percent ?? undefined} aria-label="Progresso do envio" />
      <small>Mantenha esta aba aberta até a confirmação.</small>
    </div>}
    <div className={styles.tableWrapper} aria-busy={loadingFiles}>
      <table className={styles.table}>
        <thead><tr>
          {sortColumns.map(({ key, label }) => {
            const direction = sort.key === key ? sort.direction : undefined
            const SortIcon = direction === "ascending" ? ArrowUp : direction === "descending" ? ArrowDown : ArrowUpDown
            return <th key={key} scope="col" aria-sort={direction}>
              <button type="button" className={styles.sortButton} disabled={loadingFiles}
                onClick={() => changeSort(key)}>
                {label} <SortIcon size={14} aria-hidden="true" />
              </button>
            </th>
          })}
          <th scope="col">Ações</th>
        </tr></thead>
        <tbody>
          {loadingFiles ? <tr><td colSpan={4} className={styles.tableMessage}>Carregando arquivos…</td></tr> : <>
            {(failed || documents.failed) && <tr><td colSpan={4} className={styles.tableMessage}>
              {failed ? "Não foi possível carregar os anexos." : "Não foi possível carregar os contratos e boletins."} Clique em Tentar novamente.
            </td></tr>}
            {!failed && !documents.failed && !visibleFiles.length && <tr><td colSpan={4} className={styles.tableMessage}>
              Nenhum arquivo enviado para esta obra.
            </td></tr>}
            {visibleFiles.map((file) => <tr key={file.id}>
              <td className={styles.fileName}>
                {file.file_name}
                {file.kind && <small>{projectDocumentLabel(file)}</small>}
              </td>
              <td>{formatFileSize(file.file_size)}</td>
              <td>{formatBusinessDate(file.created_at)}</td>
              <td><Actions busy={busy} disabled={busy} actions={[
                { key: "measurement", label: "Lançar medição", icon: ClipboardCheck,
                  visible: Boolean(!file.kind && contract && canImportMeasurement && /\.xlsx$/i.test(file.file_name)),
                  onSelect: () => openMeasurement(file) },
                { key: "download", label: file.kind ? "Baixar original" : "Baixar", icon: Download,
                  disabled: busy, onSelect: () => download(file) },
                { key: "delete", label: "Remover", icon: Trash2, danger: true,
                  visible: !file.kind && canDelete, disabled: busy, onSelect: () => setDeleting(file) },
              ]} /></td>
            </tr>)}
          </>}
        </tbody>
      </table>
    </div>
    <div className={`${styles.paginationSlot} ${!total ? styles.paginationHidden : ""}`}>
      <Pagination className={styles.pagination} currentPage={currentPage} totalPages={totalPages}
        totalItems={total} pageSize={pageSize} isLoading={loadingFiles || busy}
        onPageChange={setPage} onPageSizeChange={setPageSize} />
    </div>
    {deleting && <ConfirmModal bridge={bridge} title="Remover arquivo" danger
      message={`Confirma a remoção de “${deleting.file_name}” da obra? A remoção é permanente.`}
      confirmLabel="Remover" loading={busy} onCancel={() => { if (!busy) setDeleting(null) }} onConfirm={remove} />}
    {uploadChoice === "choose" && <UnitBankSlipDialogFrame bridge={bridge} title="Enviar arquivos"
      onClose={() => setUploadChoice(null)} footer={<button type="button" className={styles.secondaryButton}
        onClick={() => setUploadChoice(null)}>Cancelar</button>}>
      <div className={styles.uploadOptions}>
        {canCreate && <button type="button" className={styles.secondaryButton} onClick={() => {
          input.current?.click()
          setUploadChoice(null)
        }}>Anexar arquivos</button>}
        {canAttachAddenda && <button type="button" className={styles.secondaryButton} onClick={() => {
          addendumInput.current?.click()
          setUploadChoice(null)
        }}>Anexar aditivos</button>}
        {contract && canImportMeasurement && <button type="button" className={styles.secondaryButton}
          onClick={() => setUploadChoice("measurement")}>Importar medição</button>}
      </div>
      {documents.failed ? <button type="button" className={styles.secondaryButton} onClick={documents.refresh}>
        Tentar novamente
      </button> : !documents.history && <p role="status">Carregando contratos e boletins…</p>}
      {documents.history && !contract && canImportMeasurement && <p>Vincule o contrato em Editar obra para importar boletins de medição.</p>}
    </UnitBankSlipDialogFrame>}
    {uploadChoice === "measurement" && <ProjectMeasurementDocumentModal
      bridge={bridge} projectId={projectId} sourceFile={sourceFile} onClose={closeUpload}
      onComplete={() => {
        closeUpload()
        documents.refresh()
        void onImported()
      }} />}
  </section>
}
