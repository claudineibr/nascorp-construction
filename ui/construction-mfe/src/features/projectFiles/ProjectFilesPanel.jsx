import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react"
import { ArrowDown, ArrowUp, ArrowUpDown, ClipboardCheck, Download, Folder, FolderPlus, RefreshCcw, Search, Trash2, Upload } from "lucide-react"
import { Pagination as StandalonePagination } from "../../components/Pagination.jsx"
import {
  browseProjectFiles, createProjectFolder, deleteProjectFile, downloadProjectFile, readProjectFileSources, uploadProjectFile,
} from "../../services/projectFiles.js"
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
const emptyFiles = { items: [], total: 0, total_pages: 0, folders: [], breadcrumbs: [], name_query: "", extensions: [] }
const noSources = new Map()
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

function documentSourceIds(document) {
  return [document.snapshot.source_file_id, ...(document.snapshot.additional_source_file_ids ?? [])].filter(Boolean)
}

function documentMatches(file, { name_query: name, extensions }) {
  if (extensions.length) return extensions.includes(file.file_name.split(".").at(-1).toLowerCase())
  const lower = file.file_name.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
  return lower.includes(name)
}

function mergeFiles(result, documents, sourceFolders, folderId) {
  const filesById = new Map(result.items.map((file) => [file.id, file]))
  const imported = []
  const searching = Boolean(result.name_query || result.extensions.length)
  for (const document of documents) {
    const ids = documentSourceIds(document)
    const preferred = ids.find((id) => sourceFolders.has(id))
    const preferredFolder = sourceFolders.get(preferred)
    const aliases = ids.filter((id) => sourceFolders.get(id) === preferredFolder)
    const source = filesById.get(preferred) ?? (searching ? aliases.map((id) => filesById.get(id)).find(Boolean) : null)
    aliases.forEach((id) => filesById.delete(id))
    if (source) {
      imported.push({
        ...document,
        file_name: source.file_name,
        file_size: source.file_size,
        created_at: document.created_at ?? source.created_at,
        folder_path: source.folder_path,
        folder_id: source.folder_id,
      })
    } else if (!preferred && (!folderId || searching) && documentMatches(document, result)) {
      imported.push({ ...document, folder_path: [] })
    }
  }
  return [...imported, ...filesById.values()]
}

export function ProjectFilesPanel({ bridge, projectId, contractWork, RowActionsMenu, ConfirmModal, renderActions, onImported, reloadRevision }) {
  const [result, setResult] = useState(emptyFiles)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [sort, setSort] = useState(defaultSort)
  const [folderId, setFolderId] = useState(null)
  const [search, setSearch] = useState("")
  const [query, setQuery] = useState("")
  const [newFolder, setNewFolder] = useState(null)
  const [sourceLookup, setSourceLookup] = useState({ ids: null, failed: false })
  const folderForm = useId()
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
  const sourceIds = useMemo(() => [...new Set(importedFiles.flatMap(documentSourceIds))], [importedFiles])
  const waitingSources = sourceIds.length > 0 && !sourceLookup.ids && !sourceLookup.failed
  const documentError = documents.failed || (sourceIds.length > 0 && sourceLookup.failed)
  const waitingDocuments = (canReadDocuments && !documents.history && !documents.failed) || waitingSources
  const useLocalSort = importedFiles.length > 0 && !documentError
  const requestPage = useLocalSort ? 1 : page
  const requestPageSize = useLocalSort ? 100 : pageSize
  const files = useMemo(() => useLocalSort
    ? mergeFiles(result, importedFiles, sourceLookup.ids ?? noSources, folderId)
      .sort((left, right) => compareFiles(left, right, sort))
    : result.items, [result, importedFiles, sourceLookup.ids, folderId, sort, useLocalSort])
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
    const value = search.trim()
    if (value === query) return undefined
    const timer = setTimeout(() => {
      setQuery(value)
      setPage(1)
    }, 400)
    return () => clearTimeout(timer)
  }, [search, query])

  useEffect(() => {
    if (!sourceIds.length) return undefined
    const controller = new AbortController()
    setSourceLookup({ ids: null, failed: false })
    readProjectFileSources(bridge, projectId, sourceIds, controller.signal).then((ids) => {
      if (!controller.signal.aborted) setSourceLookup({ ids, failed: false })
    }).catch((error) => {
      if (controller.signal.aborted) return
      setSourceLookup({ ids: null, failed: true })
      report(error)
    })
    return () => controller.abort()
  }, [bridge, projectId, sourceIds, revision, report])

  useEffect(() => {
    if (!canRead || waitingDocuments) return undefined
    const controller = new AbortController()
    setLoading(true)
    setFailed(false)
    const request = browseProjectFiles(bridge, projectId, {
      folderId, search: query, sort, page: requestPage, pageSize: requestPageSize, all: useLocalSort,
    }, controller.signal)
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
  }, [bridge, projectId, folderId, query, sort, requestPage, requestPageSize,
    revision, reloadRevision, canRead, waitingDocuments, useLocalSort, report])

  const goToFolder = (id) => {
    setFolderId(id)
    setSearch("")
    setQuery("")
    setPage(1)
  }

  const saveFolder = async (event) => {
    event.preventDefault()
    const name = newFolder?.trim()
    if (!name || busy) return
    setBusy(true)
    try {
      const folder = await createProjectFolder(bridge, projectId, name, folderId)
      setNewFolder(null)
      goToFolder(folder.id)
      bridge.feedback?.success?.("Pasta criada.")
      refresh()
    } catch (error) { report(error) }
    finally { setBusy(false) }
  }

  const searching = Boolean(result.name_query || result.extensions.length)

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
          folderId,
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

  if (!canRead && bridge.permissionsLoading) return <p role="status">Carregando permissões de Obras…</p>
  if (!canRead) return <p>Você não tem permissão para consultar arquivos desta obra.</p>
  return <section className={styles.panel}>
    {renderActions(<>
      <button type="button" className={styles.secondaryButton} disabled={busy || loadingFiles}
        onClick={() => { refresh(); if (canReadDocuments) documents.refresh() }}>
        <RefreshCcw size={16} aria-hidden="true" />{failed || documentError ? "Tentar novamente" : "Atualizar"}
      </button>
      {canCreate && <button type="button" className={styles.secondaryButton} disabled={busy || Boolean(uploadStatus)}
        onClick={() => setNewFolder("")}>
        <FolderPlus size={16} aria-hidden="true" />Nova pasta
      </button>}
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
    <div className={styles.browserToolbar}>
      <nav aria-label="Pastas da obra">
        <ol className={styles.breadcrumbs}>
          <li>{folderId
            ? <button type="button" disabled={Boolean(uploadStatus)} onClick={() => goToFolder(null)}>Arquivos da obra</button>
            : <span aria-current="location">Arquivos da obra</span>}</li>
          {result.breadcrumbs.map((folder) => <li key={folder.id}>
            <span aria-hidden="true">/</span>
            {folder.id === folderId
              ? <span aria-current="location">{folder.name}</span>
              : <button type="button" disabled={Boolean(uploadStatus)} onClick={() => goToFolder(folder.id)}>{folder.name}</button>}
          </li>)}
        </ol>
      </nav>
      <label className={styles.search}>
        <Search size={16} aria-hidden="true" />
        <input type="search" aria-label="Buscar arquivos por nome ou tipo em toda a obra" value={search}
          onChange={(event) => setSearch(event.target.value)} maxLength={500} placeholder="Buscar por nome ou tipo" />
      </label>
    </div>
    {query && !searching && !loadingFiles && !failed && <small className={styles.searchHint}>
      Para buscar por nome, digite pelo menos 4 caracteres. Você também pode digitar um tipo, como PDF.
    </small>}
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
            {(failed || documentError) && <tr><td colSpan={4} className={styles.tableMessage}>
              {failed ? "Não foi possível carregar os anexos." : "Não foi possível carregar os contratos e boletins."} Clique em Tentar novamente.
            </td></tr>}
            {!failed && !documentError && !visibleFiles.length && !result.folders.length && <tr><td colSpan={4} className={styles.tableMessage}>
              {searching ? "Nenhum arquivo encontrado." : folderId ? "Esta pasta está vazia." : "Nenhum arquivo ou pasta nesta obra."}
            </td></tr>}
            {result.folders.map((folder) => <tr key={folder.id}>
              <td colSpan={4} className={styles.folderCell}>
                <button type="button" className={styles.folderLink} disabled={Boolean(uploadStatus)}
                  onClick={() => goToFolder(folder.id)}>
                  <Folder size={16} aria-hidden="true" />{folder.name}
                </button>
              </td>
            </tr>)}
            {visibleFiles.map((file) => <tr key={file.id}>
              <td className={styles.fileName}>
                {file.file_name}
                {file.kind && <small>{projectDocumentLabel(file)}</small>}
                {searching && <small>
                  <button type="button" className={styles.fileLocation} disabled={Boolean(uploadStatus)}
                    onClick={() => goToFolder(file.folder_id ?? null)}>
                    {file.folder_path.join(" / ") || "Raiz da obra"}
                  </button>
                </small>}
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
        onPageChange={setPage} onPageSizeChange={(size) => { setPageSize(size); setPage(1) }} />
    </div>
    {newFolder !== null && <UnitBankSlipDialogFrame bridge={bridge} title="Nova pasta" dialogMaxWidth={480}
      onClose={busy ? undefined : () => setNewFolder(null)} footer={<>
        <button type="button" className={styles.secondaryButton} onClick={() => setNewFolder(null)} disabled={busy}>Cancelar</button>
        <button type="submit" form={folderForm} className={styles.primaryButton} disabled={!newFolder.trim() || busy}>Criar pasta</button>
      </>}>
      <form id={folderForm} onSubmit={(event) => void saveFolder(event)} className={styles.folderForm}>
        <label>Nome da pasta *
          <input value={newFolder} onChange={(event) => setNewFolder(event.target.value)} maxLength={255}
            required disabled={busy} autoFocus />
        </label>
      </form>
    </UnitBankSlipDialogFrame>}
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
