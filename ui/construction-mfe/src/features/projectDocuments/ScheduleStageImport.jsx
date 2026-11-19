import { useRef, useState } from "react"
import { Upload } from "lucide-react"
import { requestJson } from "../../services/constructionApi.js"
import styles from "../../App.module.css"

export function ScheduleStageImport({ bridge, projectId, onImported }) {
  const [busy, setBusy] = useState(false)
  const input = useRef(null)
  const upload = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file || busy) return
    setBusy(true)
    try {
      const body = new FormData()
      body.append("file", file)
      const result = await requestJson({ bridge, path: `/v1/construction/projects/${projectId}/schedule/import-stages`, method: "POST", body })
      bridge.feedback?.success?.(`${result.created} etapa(s) cadastrada(s); ${result.matched} etapa(s) já existente(s) preservada(s).`)
      await onImported?.()
    } catch (error) {
      bridge.feedback?.error?.(error.message)
    } finally {
      setBusy(false)
    }
  }
  return <>
    <button type="button" className={styles.secondaryButton} disabled={busy} onClick={() => input.current?.click()}>
      <Upload size={16} aria-hidden="true" />
      {busy ? "Importando etapas..." : "Importar etapas da planilha"}
    </button>
    <input ref={input} aria-label="Planilha de etapas" type="file" accept=".xlsx,.xlsm" hidden
      disabled={busy} onChange={upload} />
  </>
}
