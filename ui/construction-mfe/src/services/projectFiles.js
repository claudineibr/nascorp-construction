import { requestJson } from "./constructionApi.js"

const baseUrl = (bridge) => bridge?.erpApiBaseUrl || import.meta.env.VITE_ERP_API_URL || "http://127.0.0.1:8000"
const pathFor = (projectId) => `/v1/construction-project-files/${projectId}`

export const listProjectFiles = (bridge, projectId, page, pageSize, signal) => requestJson({
  bridge, baseUrl: baseUrl(bridge), path: `${pathFor(projectId)}?page=${page}&page_size=${pageSize}`, signal,
})

export async function listAllProjectFiles(bridge, projectId, signal) {
  const pageSize = 100
  const firstPage = await listProjectFiles(bridge, projectId, 1, pageSize, signal)
  const files = new Map(firstPage.items.map((file) => [file.id, file]))
  for (let page = 2; page <= firstPage.total_pages; page += 1) {
    const result = await listProjectFiles(bridge, projectId, page, pageSize, signal)
    for (const file of result.items) files.set(file.id, file)
  }
  return { items: [...files.values()] }
}

export async function browseProjectFiles(bridge, projectId, options, signal) {
  const { folderId, search, sort, page, pageSize, all } = options
  const params = new URLSearchParams({
    q: search, sort: sort.key, direction: sort.direction, page_size: all ? 100 : pageSize,
  })
  if (folderId) params.set("folder_id", folderId)
  const load = (number) => {
    params.set("page", number)
    return requestJson({ bridge, baseUrl: baseUrl(bridge), path: `${pathFor(projectId)}/browse?${params}`, signal })
  }
  const first = await load(all ? 1 : page)
  if (!all || first.total_pages <= 1) return first
  const files = new Map(first.items.map((file) => [file.id, file]))
  for (let number = 2; number <= first.total_pages; number += 1) {
    const next = await load(number)
    for (const file of next.items) files.set(file.id, file)
  }
  return { ...first, items: [...files.values()] }
}

export async function readProjectFileSources(bridge, projectId, ids, signal) {
  const batches = []
  for (let start = 0; start < ids.length; start += 300) {
    batches.push(requestJson({
      bridge, baseUrl: baseUrl(bridge), path: `${pathFor(projectId)}/file-sources`,
      method: "POST", body: { file_ids: ids.slice(start, start + 300) }, signal,
    }))
  }
  return new Map((await Promise.all(batches)).flat().map((file) => [file.id, file.folder_id]))
}

export const createProjectFolder = (bridge, projectId, name, parentId) => requestJson({
  bridge, baseUrl: baseUrl(bridge), path: `${pathFor(projectId)}/folders`,
  method: "POST", body: { name, parent_id: parentId },
})

export async function checkProjectFileAvailability(bridge, projectId, fileId, signal) {
  try {
    await requestJson({
      bridge, baseUrl: baseUrl(bridge), path: `${pathFor(projectId)}/${fileId}/download`, method: "HEAD", signal,
    })
    return true
  } catch (error) {
    if (error.status === 404) return false
    throw error
  }
}

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

export async function uploadProjectFile(bridge, projectId, file, { signal, onProgress, folderId }) {
  const body = new FormData()
  body.append("file", file)
  if (folderId) body.append("folder_id", folderId)
  const response = await fileRequest(bridge, pathFor(projectId), { method: "POST", body, signal }, onProgress)
  return response.json()
}

async function readProjectFile(bridge, projectId, fileId) {
  const response = await fileRequest(bridge, `${pathFor(projectId)}/${fileId}/download`)
  return response.blob()
}

export async function downloadProjectFile(bridge, projectId, file) {
  const url = URL.createObjectURL(await readProjectFile(bridge, projectId, file.id))
  const link = document.createElement("a")
  link.href = url
  link.download = file.file_name
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}
