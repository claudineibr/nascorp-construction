import { useCallback, useEffect, useRef, useState } from "react"
import { ClipboardCheck, Download, FileText, RefreshCcw, Trash2, Upload } from "lucide-react"
import { Pagination as StandalonePagination } from "../../components/Pagination.jsx"
import { listProjectFiles, uploadProjectFile, downloadProjectFile, deleteProjectFile } from "../../services/projectFiles.js"
import { formatBusinessDate } from "../../utils/brazilDate.js"
import { UnitBankSlipDialogFrame } from "../UnitBankSlipsDialog.jsx"
import { ImportedProjectFiles, ProjectDocumentModal, useProjectDocumentHistory } from "../projectDocuments/ProjectDocuments.jsx"
import styles from "./ProjectFilesPanel.module.css"

const sizeFormat = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 })
const formatFileSize = (bytes) => bytes < 1024 * 1024
  ? `${sizeFormat.format(Math.max(bytes / 1024, 0.01))} KB`
  : `${sizeFormat.format(bytes / 1024 / 1024)} MB`

export function ProjectFilesPanel({ bridge, projectId, contractWork, RowActionsMenu, ConfirmModal, renderActions, onImported }) {
  const [result, setResult] = useState({ items: [], total: 0, total_pages: 0 })
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [revision, setRevision] = useState(0)
  const [uploadChoice, setUploadChoice] = useState(null)
  const [sourceFile, setSourceFile] = useState(null)
  const input = useRef(null)
  const activeUpload = useRef(null)
  const canRead = bridge?.canRead?.("construction_projects") === true
  const canCreate = bridge?.canCreate?.("construction_projects") === true
  const canDelete = bridge?.canDelete?.("construction_projects") === true
  const canReadDocuments = canRead && contractWork && bridge.canRead?.("construction_schedule")
  const canAttachContract = canReadDocuments && bridge.canUpdate?.("construction_projects")
  const canImportMeasurement = canReadDocuments
    && bridge.canRead?.("construction_measurements") && bridge.canCreate?.("construction_measurements")
  const documents = useProjectDocumentHistory(bridge, projectId, canReadDocuments)
  const contract = documents.history?.items.find((file) => file.kind === "contract")
  const canChooseContract = canAttachContract && !contract
  const showUploadChoices = canChooseContract || (canImportMeasurement && (contract || !documents.history))
  const importedFiles = documents.history?.items ?? []
  const Pagination = bridge.components?.Pagination ?? StandalonePagination
  const Actions = bridge.components?.RowActionsMenu ?? RowActionsMenu
  const report = useCallback((error) => bridge.feedback?.error?.(error.message), [bridge])
  const refresh = () => setRevision((value) => value + 1)

  useEffect(() => () => activeUpload.current?.abort(), [])

  useEffect(() => {
    if (!canRead) return undefined
    const controller = new AbortController()
    setLoading(true)
    setFailed(false)
    listProjectFiles(bridge, projectId, page, pageSize, controller.signal).then((data) => {
      if (controller.signal.aborted) return
      if (page > 1 && !data.items.length) { setPage(Math.max(1, data.total_pages)); return }
      setResult(data)
    }).catch((error) => {
      if (!controller.signal.aborted) { setFailed(true); report(error) }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [bridge, projectId, page, pageSize, revision, canRead, report])

  const upload = async (event) => {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ""
    if (!files.length || activeUpload.current) return
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
    try { await downloadProjectFile(bridge, projectId, file) }
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

  const openExistingFile = (mode, file) => {
    setSourceFile(file)
    setUploadChoice(mode)
  }

  const closeUpload = () => {
    setSourceFile(null)
    setUploadChoice(null)
  }

  if (!canRead) return <p>Você não tem permissão para consultar arquivos desta obra.</p>
  return <section className={styles.panel}>
    {renderActions(<>
      <button type="button" className={styles.secondaryButton} disabled={busy || loading}
        onClick={() => { refresh(); if (canReadDocuments) documents.refresh() }}>
        <RefreshCcw size={16} aria-hidden="true" />{failed || documents.failed ? "Tentar novamente" : "Atualizar"}
      </button>
      {(canCreate || showUploadChoices) && <button type="button" className={styles.primaryButton} disabled={Boolean(uploadStatus)}
        onClick={() => showUploadChoices ? setUploadChoice("choose") : input.current?.click()}>
        <Upload size={16} aria-hidden="true" />{uploadStatus ? "Enviando arquivos…" : "Enviar arquivos"}
      </button>}
    </>)}
    {canCreate && <input ref={input} className={styles.fileInput} type="file" multiple
      aria-label="Selecionar arquivos da obra" onChange={upload} disabled={Boolean(uploadStatus)} />}
    {uploadStatus && <div className={styles.uploadStatus}>
      <div role="status">
        <strong>{uploadStatus.percent === 100 ? "Confirmando envio" : "Enviando arquivo"} {uploadStatus.index} de {uploadStatus.total}</strong>
        <span>{uploadStatus.name}</span>
      </div>
      <progress max={100} value={uploadStatus.percent ?? undefined} aria-label="Progresso do envio" />
      <small>Mantenha esta aba aberta até a confirmação.</small>
    </div>}
    {canReadDocuments && !documents.history && !documents.failed && <p role="status">Carregando contratos e boletins…</p>}
    {documents.failed && <p>Não foi possível carregar os contratos e boletins. Clique em Tentar novamente.</p>}
    <ImportedProjectFiles bridge={bridge} projectId={projectId} documents={importedFiles} />
    {Boolean(importedFiles.length) && <h3>Outros arquivos da obra</h3>}
    <div className={styles.tableWrapper} aria-busy={loading}>
      <table className={styles.table}>
        <thead><tr><th>Nome</th><th>Tamanho</th><th>Enviado em</th><th>Ações</th></tr></thead>
        <tbody>{loading ? <tr><td colSpan={4}>Carregando arquivos...</td></tr>
          : failed ? <tr><td colSpan={4}>Não foi possível carregar os arquivos. Clique em Tentar novamente.</td></tr>
            : !result.items.length ? <tr><td colSpan={4}>{importedFiles.length
              ? "Nenhum outro arquivo enviado para esta obra." : "Nenhum arquivo enviado para esta obra."}</td></tr>
              : result.items.map((file) => <tr key={file.id}>
                <td className={styles.fileName}>{file.file_name}</td>
                <td>{formatFileSize(file.file_size)}</td>
                <td>{formatBusinessDate(file.created_at)}</td>
                <td><Actions busy={busy} disabled={busy} actions={[
                  { key: "contract", label: "Vincular como contrato", icon: FileText,
                    visible: Boolean(documents.history && canChooseContract && /\.pdf$/i.test(file.file_name)),
                    onSelect: () => openExistingFile("contract", file) },
                  { key: "measurement", label: "Lançar medição", icon: ClipboardCheck,
                    visible: Boolean(contract && canImportMeasurement && /\.xlsx$/i.test(file.file_name)),
                    onSelect: () => openExistingFile("measurement", file) },
                  { key: "download", label: "Baixar", icon: Download, disabled: busy, onSelect: () => download(file) },
                  { key: "delete", label: "Remover", icon: Trash2, danger: true, visible: canDelete, disabled: busy, onSelect: () => setDeleting(file) },
                ]} /></td>
              </tr>)}</tbody>
      </table>
    </div>
    <div className={`${styles.paginationSlot} ${!result.total || failed ? styles.paginationHidden : ""}`}>
      <Pagination className={styles.pagination} currentPage={page} totalPages={result.total_pages}
        totalItems={result.total} pageSize={pageSize} isLoading={loading || busy}
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
        {documents.history && canChooseContract && <button type="button" className={styles.secondaryButton}
          onClick={() => setUploadChoice("contract")}>Vincular contrato</button>}
        {contract && canImportMeasurement && <button type="button" className={styles.secondaryButton}
          onClick={() => setUploadChoice("measurement")}>Importar medição</button>}
      </div>
      {documents.failed ? <button type="button" className={styles.secondaryButton} onClick={documents.refresh}>
        Tentar novamente
      </button> : !documents.history && <p role="status">Carregando contratos e boletins…</p>}
      {documents.history && !contract && canImportMeasurement && <p>Vincule o contrato para importar boletins de medição.</p>}
    </UnitBankSlipDialogFrame>}
    {(uploadChoice === "contract" || uploadChoice === "measurement") && <ProjectDocumentModal
      bridge={bridge} projectId={projectId} mode={uploadChoice} sourceFile={sourceFile} onClose={closeUpload}
      onComplete={() => {
        closeUpload()
        documents.refresh()
        void onImported()
      }} />}
  </section>
}
