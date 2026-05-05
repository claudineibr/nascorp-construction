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

const toBlockView = (block) => ({
  id: block.id,
  companyId: block.company_id,
  projectId: block.project_id,
  code: block.code,
  name: block.name,
  status: block.status,
  floorsCount: block.floors_count ?? null,
  createdAt: block.created_at ?? null,
  updatedAt: block.updated_at ?? null,
})

const toSchedulePhaseView = (phase) => ({
  id: phase.id,
  companyId: phase.company_id,
  projectId: phase.project_id,
  name: phase.name,
  sequenceOrder: phase.sequence_order,
  status: phase.status,
  plannedStartDate: phase.planned_start_date ?? null,
  plannedEndDate: phase.planned_end_date ?? null,
  actualStartDate: phase.actual_start_date ?? null,
  actualEndDate: phase.actual_end_date ?? null,
  progressPercent: Number(phase.progress_percent ?? 0),
  createdAt: phase.created_at ?? null,
  updatedAt: phase.updated_at ?? null,
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

const toBlockPayload = (blockData = {}) => ({
  code: String(blockData.code ?? "").trim(),
  name: String(blockData.name ?? "").trim(),
  status: blockData.status,
  floors_count: blockData.floorsCount === "" || blockData.floorsCount === null ? null : Number(blockData.floorsCount),
})

const toSchedulePhasePayload = (phaseData = {}) => ({
  name: String(phaseData.name ?? "").trim(),
  sequence_order: Number(phaseData.sequenceOrder),
  status: phaseData.status,
  planned_start_date: toNullableString(phaseData.plannedStartDate),
  planned_end_date: toNullableString(phaseData.plannedEndDate),
  actual_start_date: toNullableString(phaseData.actualStartDate),
  actual_end_date: toNullableString(phaseData.actualEndDate),
  progress_percent:
    phaseData.progressPercent === "" || phaseData.progressPercent === null
      ? 0
      : Number(phaseData.progressPercent),
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

export async function listConstructionBlocks({ bridge, projectId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/blocks`,
  })

  return {
    items: (payload.items ?? []).map(toBlockView),
    total: payload.total ?? 0,
  }
}

export async function createConstructionBlock({ bridge, projectId, blockData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/blocks`,
    method: "POST",
    body: toBlockPayload(blockData),
  })

  return toBlockView(payload)
}

export async function updateConstructionBlock({ bridge, blockId, blockData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/blocks/${blockId}`,
    method: "PATCH",
    body: toBlockPayload(blockData),
  })

  return toBlockView(payload)
}

export async function deleteConstructionBlock({ bridge, blockId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/blocks/${blockId}`,
    method: "DELETE",
  })
}

export async function listConstructionSchedulePhases({ bridge, projectId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/schedule-phases`,
  })

  return {
    items: (payload.items ?? []).map(toSchedulePhaseView),
    total: payload.total ?? 0,
  }
}

export async function createConstructionSchedulePhase({ bridge, projectId, phaseData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/schedule-phases`,
    method: "POST",
    body: toSchedulePhasePayload(phaseData),
  })

  return toSchedulePhaseView(payload)
}

export async function updateConstructionSchedulePhase({ bridge, phaseId, phaseData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/schedule-phases/${phaseId}`,
    method: "PATCH",
    body: toSchedulePhasePayload(phaseData),
  })

  return toSchedulePhaseView(payload)
}

export async function deleteConstructionSchedulePhase({ bridge, phaseId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/schedule-phases/${phaseId}`,
    method: "DELETE",
  })
}

export { requestJson, toBlockPayload, toProjectPayload, toProjectView, toSchedulePhasePayload }
