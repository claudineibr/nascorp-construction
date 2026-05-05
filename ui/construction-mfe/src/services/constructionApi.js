const DEFAULT_CONSTRUCTION_API_URL = "http://127.0.0.1:8010"

const toProjectView = (project) => ({
  id: project.id,
  code: project.code,
  name: project.name,
  description: project.description ?? "",
  status: project.status,
  startDate: project.start_date ?? null,
  expectedEndDate: project.expected_end_date ?? null,
  actualEndDate: project.actual_end_date ?? null,
  syntheticCostCenterId: project.synthetic_cost_center_id ?? null,
  analyticCostCenterId: project.analytic_cost_center_id ?? null,
  createdAt: project.created_at ?? null,
  updatedAt: project.updated_at ?? null,
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

export { requestJson, toProjectView }
