const DEFAULT_CONSTRUCTION_API_URL = "http://127.0.0.1:8010"

const toProjectView = (project) => ({
  id: project.id,
  code: project.code,
  name: project.name,
  status: project.status,
  startDate: project.start_date ?? null,
  expectedEndDate: project.expected_end_date ?? null,
  syntheticCostCenterId: project.synthetic_cost_center_id ?? null,
  analyticCostCenterId: project.analytic_cost_center_id ?? null,
})

export async function listConstructionProjects({ bridge, page = 1, pageSize = 20 } = {}) {
  const apiBaseUrl = bridge?.constructionApiBaseUrl || DEFAULT_CONSTRUCTION_API_URL
  const path = `${apiBaseUrl}/v1/construction/projects?page=${page}&page_size=${pageSize}`
  const headers = bridge?.getAuthHeaders?.() ?? {}
  let response = await fetch(path, { headers })

  if (response.status === 401 && typeof bridge?.refreshToken === "function") {
    const refreshedSession = await bridge.refreshToken()
    const retryHeaders = {
      ...headers,
      ...(refreshedSession?.token ? { Authorization: `Bearer ${refreshedSession.token}` } : {}),
    }
    response = await fetch(path, { headers: retryHeaders })
  }

  if (!response.ok) {
    throw new Error("Não foi possível carregar as obras.")
  }

  const payload = await response.json()
  return {
    items: (payload.items ?? []).map(toProjectView),
    total: payload.total ?? 0,
    page: payload.page ?? page,
    pageSize: payload.page_size ?? pageSize,
  }
}
