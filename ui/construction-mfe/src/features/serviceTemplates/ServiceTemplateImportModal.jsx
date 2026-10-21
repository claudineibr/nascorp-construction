import { useRef, useState } from "react"
import { Download, FileSpreadsheet, Trash2, UploadCloud } from "lucide-react"

import appStyles from "../../App.module.css"
import styles from "./ServiceTemplates.module.css"
import { importConstructionServiceTemplates, downloadConstructionServiceTemplateExample } from "../../services/constructionApi"

const MAX_FILES = 30
const MAX_FILE_BYTES = 5 * 1024 * 1024
const ACCEPTED_EXTENSIONS = [".xlsx", ".xlsm"]

const resultStyle = {
  created: styles.resultCreated,
  updated: styles.resultUpdated,
  skipped: styles.resultSkipped,
  failed: styles.resultFailed,
}

const resultLabel = {
  created: "Criado",
  updated: "Atualizado",
  skipped: "Já existia",
  failed: "Falhou",
}

const formatSize = (bytes) => `${(bytes / 1024).toFixed(0)} KB`

export function ServiceTemplateImportModal({
  bridge,
  submitting,
  results,
  onClose,
  onImport,
  title = "Importar planilha (FVS)",
  allowRevision = false,
}) {
  const [files, setFiles] = useState([])
  const [preview, setPreview] = useState([])
  const [reviewing, setReviewing] = useState(false)
  const [reviseExisting, setReviseExisting] = useState(false)
  const canRevise = Boolean(bridge?.canUpdate?.("construction_measurements"))
  const review = async () => {
    setReviewing(true)
    try {
      const result = await importConstructionServiceTemplates({ bridge, files, mode: "preview" })
      setPreview(result.results)
      setReviseExisting(false)
    } catch (failure) {
      bridge?.feedback?.error?.(failure?.message ?? "Não foi possível comparar as planilhas.")
    } finally {
      setReviewing(false)
    }
  }
  const apply = () => onImport(files, {
    mode: reviseExisting ? "replace" : "create",
    revisions: Object.fromEntries(preview.map((row) => [row.fileName, row.revisionToken])),
  })
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState("")
  const [downloading, setDownloading] = useState(false)
  const inputRef = useRef(null)

  const handleDownloadExample = async () => {
    setDownloading(true)
    try {
      const blob = await downloadConstructionServiceTemplateExample({ bridge })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = "modelo-fvs.xlsx"
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (downloadError) {
      setError(downloadError?.message ?? "Não foi possível baixar o modelo.")
    } finally {
      setDownloading(false)
    }
  }

  const acceptFiles = (incoming) => {
    if (reviewing || submitting) return
    setPreview([])
    setReviseExisting(false)
    const candidates = Array.from(incoming ?? [])
    const rejected = candidates.filter(
      (file) => !ACCEPTED_EXTENSIONS.some((extension) => file.name.toLowerCase().endsWith(extension)),
    )
    const tooLarge = candidates.filter((file) => file.size > MAX_FILE_BYTES)
    const accepted = candidates.filter(
      (file) =>
        ACCEPTED_EXTENSIONS.some((extension) => file.name.toLowerCase().endsWith(extension)) &&
        file.size <= MAX_FILE_BYTES,
    )

    if (rejected.length > 0) {
      setError("Somente planilhas .xlsx ou .xlsm. Converta o arquivo antes de importar.")
    } else if (tooLarge.length > 0) {
      setError("Cada planilha precisa ter no máximo 5 MB.")
    } else {
      setError("")
    }

    setFiles((current) => {
      const merged = [...current]
      for (const file of accepted) {
        if (!merged.some((existing) => existing.name === file.name && existing.size === file.size)) {
          merged.push(file)
        }
      }

      if (merged.length > MAX_FILES) {
        setError(`Envie no máximo ${MAX_FILES} planilhas por importação.`)
        return merged.slice(0, MAX_FILES)
      }

      return merged
    })
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setDragging(false)
    acceptFiles(event.dataTransfer?.files)
  }

  const removeFile = (index) => {
    if (reviewing || submitting) return
    setPreview([])
    setReviseExisting(false)
    setFiles((current) => current.filter((_, position) => position !== index))
  }

  return (
    <div className={appStyles.modalOverlay} role="dialog" aria-modal="true">
      <div className={`${appStyles.modalCard} ${styles.importCard}`}>
        <header className={appStyles.modalHeader}>
          <h3>{title}</h3>
          <button type="button" className={appStyles.closeButton} onClick={onClose}>
            Fechar
          </button>
        </header>

        <div className={appStyles.modalBody}>
          <div
            className={`${styles.dropZone} ${dragging ? styles.dropZoneActive : ""}`}
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            <UploadCloud size={28} />
            <span>
              Arraste e solte as fichas aqui ou{" "}
              <span
                className={styles.fileLink}
                role="button"
                tabIndex={0}
                onClick={() => inputRef.current?.click()}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    inputRef.current?.click()
                  }
                }}
              >
                selecione os arquivos
              </span>
            </span>
            <span className={styles.dropZoneHint}>
              Uma planilha por serviço, no layout da Caixa. Até {MAX_FILES} arquivos de 5 MB cada.
            </span>
            <button
              type="button"
              className={styles.textButton}
              onClick={handleDownloadExample}
              disabled={downloading}
            >
              <Download size={14} />
              {downloading ? "Baixando..." : "Baixar modelo de planilha"}
            </button>
            <input
              ref={inputRef}
              type="file"
              hidden
              multiple
              accept=".xlsx,.xlsm"
              onChange={(event) => {
                acceptFiles(event.target.files)
                event.target.value = ""
              }}
            />
          </div>

          {error ? <span className={styles.fieldError}>{error}</span> : null}

          {files.length > 0 ? (
            <ul className={styles.fileList}>
              {files.map((file, index) => (
                <li key={`${file.name}-${file.size}`} className={styles.fileRow}>
                  <span>
                    <FileSpreadsheet size={15} />
                    <span className={styles.fileName}>{file.name}</span>
                  </span>
                  <span>
                    {formatSize(file.size)}
                    <button
                      type="button"
                      className={`${styles.iconButton} ${styles.dangerIconButton}`}
                      onClick={() => removeFile(index)}
                      aria-label={`Remover ${file.name}`}
                      title="Remover arquivo"
                    >
                      <Trash2 size={14} />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          ) : null}

          {results.length > 0 ? (
            <ul className={styles.fileList}>
              {results.map((result) => (
                <li key={result.fileName} className={`${styles.resultRow} ${resultStyle[result.status] ?? ""}`}>
                  <strong>{resultLabel[result.status] ?? result.status}</strong> — {result.fileName}
                  {result.serviceName ? ` · ${result.serviceName}` : ""}
                  {result.status === "created" || result.status === "updated"
                    ? ` · ${result.itemsCount} ${result.itemsCount === 1 ? "item" : "itens"}`
                    : ""}
                  {result.linked ? " · vinculado à obra" : ""}
                  {result.message ? ` · ${result.message}` : ""}
                </li>
              ))}
            </ul>
          ) : null}

          {allowRevision && preview.length > 0 && (
            <section>
              <h4>Prévia da importação</h4>
              <p>Revisões valem para os próximos serviços. As inspeções e rodadas já registradas nas OS serão preservadas. Marcações de comentário e foto nas linhas mantidas também serão preservadas.</p>
              {preview.map((row) => <div key={row.fileName}>
                <strong>{row.serviceName || row.fileName}</strong>
                <p>{row.existingItemsCount} linhas atuais → {row.itemsCount} na planilha. {row.message}</p>
                <ul>{row.changes.map((change, index) => <li key={`${index}:${change}`}>{change}</li>)}</ul>
              </div>)}
              {canRevise && preview.some((row) => row.serviceTemplateId) && <label>
                <input type="checkbox" checked={reviseExisting} disabled={submitting || reviewing}
                  onChange={(event) => setReviseExisting(event.target.checked)} />
                Aplicar também as revisões às fichas existentes
              </label>}
            </section>
          )}
          <div className={appStyles.modalFooter}>
            <button type="button" className={appStyles.secondaryButton} onClick={onClose} disabled={submitting || reviewing}>
              {results.length > 0 ? "Fechar" : "Cancelar"}
            </button>
            <button
              type="button"
              className={appStyles.primaryButton}
              onClick={allowRevision ? preview.length ? apply : review : () => onImport(files)}
              disabled={submitting || reviewing || files.length === 0 || (allowRevision && preview.some((row) => row.status === "failed"))}
            >
              {submitting ? "Aplicando..." : reviewing ? "Comparando..." : allowRevision ? preview.length ? "Aplicar importação" : "Comparar planilhas" : `Importar ${files.length || ""}`.trim()}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
