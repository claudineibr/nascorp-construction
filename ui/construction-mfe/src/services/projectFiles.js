import { requestJson } from "./constructionApi.js"

const baseUrl = (bridge) => bridge?.erpApiBaseUrl || import.meta.env.VITE_ERP_API_URL || "http://127.0.0.1:8000"
const pathFor = (projectId) => `/v1/construction-project-files/${projectId}`

export const listProjectFiles = (bridge, projectId, page, pageSize, signal) => requestJson({
  bridge, baseUrl: baseUrl(bridge), path: `${pathFor(projectId)}?page=${page}&page_size=${pageSize}`, signal,
})

export const deleteProjectFile = (bridge, projectId, fileId) => requestJson({
  bridge, baseUrl: baseUrl(bridge), path: `${pathFor(projectId)}/${fileId}`, method: "DELETE",
})

function sendUpload(url, { headers, body, signal }, onProgress) {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted()
    const xhr = new XMLHttpRequest()
    const abort = () => xhr.abort()
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(Math.min(99, Math.floor(event.loaded * 100 / event.total)))
    })
    xhr.upload.addEventListener("load", () => onProgress(100))
    xhr.addEventListener("load", () => resolve(new Response(xhr.responseText || null, { status: xhr.status })))
    xhr.addEventListener("error", () => reject(new Error("A conexão caiu durante o envio. Confira a lista antes de reenviar.")))
    xhr.addEventListener("abort", () => reject(signal.reason))
    xhr.addEventListener("loadend", () => signal.removeEventListener("abort", abort))
    xhr.open("POST", url)
    Object.entries(headers).forEach(([key, value]) => xhr.setRequestHeader(key, value))
    signal.addEventListener("abort", abort, { once: true })
    onProgress(null)
    xhr.send(body)
  })
}

async function fileRequest(bridge, path, options = {}, onProgress) {
  const headers = bridge?.getAuthHeaders?.() ?? {}
  if (!headers.Authorization || !headers["X-Company-ID"]) throw new Error("Contexto autenticado da empresa indisponível.")
  const url = `${baseUrl(bridge)}${path}`
  const execute = (auth) => onProgress
    ? sendUpload(url, { ...options, headers: auth }, onProgress)
    : fetch(url, { ...options, headers: auth })
  let response = await execute(headers)
  if (response.status === 401 && bridge?.refreshToken) {
    options.signal?.throwIfAborted()
    const session = await bridge.refreshToken()
    response = await execute({ ...headers, ...(session?.token ? { Authorization: `Bearer ${session.token}` } : {}) })
  }
  if (!response.ok) {
    let message = "Não foi possível acessar os arquivos da obra."
    try {
      const payload = await response.json()
      message = payload.message || (typeof payload.detail === "string" ? payload.detail : payload.detail?.message) || message
    } catch { message = `Não foi possível acessar os arquivos da obra (HTTP ${response.status}).` }
    throw new Error(message)
  }
  return response
}

export async function uploadProjectFile(bridge, projectId, file, { signal, onProgress }) {
  const body = new FormData()
  body.append("file", file)
  const response = await fileRequest(bridge, pathFor(projectId), { method: "POST", body, signal }, onProgress)
  return response.json()
}

export async function downloadProjectFile(bridge, projectId, file) {
  const response = await fileRequest(bridge, `${pathFor(projectId)}/${file.id}/download`)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement("a")
  link.href = url
  link.download = file.file_name
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}
