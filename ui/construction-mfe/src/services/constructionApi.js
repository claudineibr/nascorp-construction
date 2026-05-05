const DEFAULT_CONSTRUCTION_API_URL = "http://127.0.0.1:8010"

const toProjectView = (project) => ({
  id: project.id,
  code: project.code,
  name: project.name,
  description: project.description ?? "",
  status: project.status,
  projectType: project.project_type,
  customerPersonId: project.customer_person_id ?? null,
  cnpjSpe: project.cnpj_spe ?? "",
  address: project.address_json ?? null,
  startDate: project.start_date ?? null,
  expectedEndDate: project.expected_end_date ?? null,
  actualEndDate: project.actual_end_date ?? null,
  syntheticCostCenterId: project.synthetic_cost_center_id ?? null,
  analyticCostCenterId: project.analytic_cost_center_id ?? null,
  createdAt: project.created_at ?? null,
  updatedAt: project.updated_at ?? null,
})

const toNullableString = (value) => {
  if (typeof value !== "string") {
    return null
  }

  const cleanedValue = value.trim()
  return cleanedValue.length ? cleanedValue : null
}

const toAddressPayload = (address) => {
  if (!address || typeof address !== "object") {
    return null
  }

  const entries = Object.entries(address)
    .map(([key, value]) => [key, typeof value === "string" ? value.trim() : value])
    .filter(([, value]) => value !== null && value !== undefined && value !== "")

  if (!entries.length) {
    return null
  }

  return Object.fromEntries(entries)
}

const toProjectPayload = (projectData = {}) => ({
  code: String(projectData.code ?? "").trim(),
  name: String(projectData.name ?? "").trim(),
  description: toNullableString(projectData.description),
  status: projectData.status,
  project_type: projectData.projectType,
  customer_person_id: toNullableString(projectData.customerPersonId),
  cnpj_spe: toNullableString(projectData.cnpjSpe),
  address_json: toAddressPayload(projectData.address),
  start_date: toNullableString(projectData.startDate),
  expected_end_date: toNullableString(projectData.expectedEndDate),
  actual_end_date: toNullableString(projectData.actualEndDate),
})

async function requestJson({ bridge, path, method = "GET", body = null }) {
  const apiBaseUrl = bridge?.constructionApiBaseUrl || DEFAULT_CONSTRUCTION_API_URL
  const headers = {
    ...(bridge?.getAuthHeaders?.() ?? {}),
  }

  if (!headers.Authorization || !headers["X-Company-ID"]) {
    throw new Error("Contexto autenticado da empresa indisponível.")
  }

  if (body !== null) {
    headers["Content-Type"] = "application/json"
  }

  const execute = async (overrideHeaders = headers) =>
    fetch(`${apiBaseUrl}${path}`, {
      method,
      headers: overrideHeaders,
      body: body === null ? undefined : JSON.stringify(body),
    })

  let response = await execute()

  if (response.status === 401 && typeof bridge?.refreshToken === "function") {
    const refreshedSession = await bridge.refreshToken()
    const retryHeaders = {
      ...headers,
      ...(refreshedSession?.token ? { Authorization: `Bearer ${refreshedSession.token}` } : {}),
    }
    response = await execute(retryHeaders)
  }

  if (!response.ok) {
    const fallback = "Não foi possível concluir a requisição do módulo de obras."
    try {
      const payload = await response.json()
      throw new Error(payload?.detail?.message || payload?.message || fallback)
    } catch {
      throw new Error(fallback)
    }
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export async function listConstructionProjects({ bridge, page = 1, pageSize = 20, search = "" } = {}) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })

  if (search.trim()) {
    query.set("search", search.trim())
  }

  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects?${query.toString()}`,
  })

  return {
    items: (payload.items ?? []).map(toProjectView),
    total: payload.total ?? 0,
    page: payload.page ?? page,
    pageSize: payload.page_size ?? pageSize,
    totalPages: payload.total_pages ?? 0,
  }
}

export async function createConstructionProject({ bridge, projectData }) {
  const payload = await requestJson({
    bridge,
    path: "/v1/construction/projects",
    method: "POST",
    body: toProjectPayload(projectData),
  })

  return toProjectView(payload)
}

export async function updateConstructionProject({ bridge, projectId, projectData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}`,
    method: "PATCH",
    body: toProjectPayload(projectData),
  })

  return toProjectView(payload)
}

export async function deleteConstructionProject({ bridge, projectId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}`,
    method: "DELETE",
  })
}

export { requestJson, toProjectPayload, toProjectView }
