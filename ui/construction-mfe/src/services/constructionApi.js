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

const toUnitView = (unit) => ({
  id: unit.id,
  companyId: unit.company_id,
  projectId: unit.project_id,
  blockId: unit.block_id ?? null,
  code: unit.code,
  unitType: unit.unit_type,
  typology: unit.typology ?? "",
  floor: unit.floor ?? "",
  privateArea: unit.private_area ?? null,
  totalArea: unit.total_area ?? null,
  salePrice: unit.sale_price ?? null,
  buyerPersonId: unit.buyer_person_id ?? null,
  reservedAt: unit.reserved_at ?? null,
  reservationExpiresAt: unit.reservation_expires_at ?? null,
  soldAt: unit.sold_at ?? null,
  externalContractId: unit.external_contract_id ?? null,
  externalContractStatus: unit.external_contract_status ?? null,
  externalReceivableId: unit.external_receivable_id ?? null,
  externalReceivableStatus: unit.external_receivable_status ?? null,
  status: unit.status,
  createdAt: unit.created_at ?? null,
  updatedAt: unit.updated_at ?? null,
})

const toMeasurementView = (measurement) => ({
  id: measurement.id,
  companyId: measurement.company_id,
  projectId: measurement.project_id,
  code: measurement.code,
  sequenceNumber: measurement.sequence_number ?? null,
  measurementType: measurement.measurement_type ?? null,
  competenceDate: measurement.competence_date ?? null,
  description: measurement.description ?? "",
  grossAmount: measurement.gross_amount ?? null,
  retentionsAmount: measurement.retentions_amount ?? null,
  netAmount: measurement.net_amount ?? null,
  measuredAmount: measurement.measured_amount,
  dueDate: measurement.due_date,
  supplierPersonId: measurement.supplier_person_id ?? null,
  documentType: measurement.document_type ?? null,
  documentNumber: measurement.document_number ?? null,
  status: measurement.status,
  rejectionReason: measurement.rejection_reason ?? null,
  approvedAt: measurement.approved_at ?? null,
  externalAccountsPayableId: measurement.external_accounts_payable_id ?? null,
  externalAccountsPayableStatus: measurement.external_accounts_payable_status ?? null,
  createdAt: measurement.created_at ?? null,
  updatedAt: measurement.updated_at ?? null,
})

const toProcurementView = (procurementRequest) => ({
  id: procurementRequest.id,
  companyId: procurementRequest.company_id,
  projectId: procurementRequest.project_id,
  code: procurementRequest.code,
  title: procurementRequest.title,
  description: procurementRequest.description ?? "",
  estimatedAmount: procurementRequest.estimated_amount,
  neededByDate: procurementRequest.needed_by_date ?? null,
  supplierPersonId: procurementRequest.supplier_person_id ?? null,
  status: procurementRequest.status,
  rejectionReason: procurementRequest.rejection_reason ?? null,
  approvedByUserId: procurementRequest.approved_by_user_id ?? null,
  approvedAt: procurementRequest.approved_at ?? null,
  externalProcurementId: procurementRequest.external_procurement_id ?? null,
  externalProcurementStatus: procurementRequest.external_procurement_status ?? null,
  createdAt: procurementRequest.created_at ?? null,
  updatedAt: procurementRequest.updated_at ?? null,
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

const toNullableNumber = (value) => {
  if (value === "" || value === null || value === undefined) {
    return null
  }

  const parsedValue = Number(value)
  return Number.isNaN(parsedValue) ? null : parsedValue
}

const toUnitPayload = (unitData = {}) => ({
  code: String(unitData.code ?? "").trim(),
  unit_type: String(unitData.unitType ?? "").trim(),
  typology: toNullableString(unitData.typology),
  block_id: toNullableString(unitData.blockId),
  floor: toNullableString(unitData.floor),
  private_area: toNullableNumber(unitData.privateArea),
  total_area: toNullableNumber(unitData.totalArea),
  sale_price: toNullableNumber(unitData.salePrice),
  status: unitData.status,
})

const toMeasurementPayload = (measurementData = {}) => ({
  code: String(measurementData.code ?? "").trim(),
  sequence_number: toNullableNumber(measurementData.sequenceNumber),
  measurement_type: toNullableString(measurementData.measurementType),
  competence_date: toNullableString(measurementData.competenceDate),
  description: toNullableString(measurementData.description),
  gross_amount: toNullableNumber(measurementData.grossAmount),
  retentions_amount: toNullableNumber(measurementData.retentionsAmount),
  net_amount: toNullableNumber(measurementData.netAmount),
  measured_amount: toNullableNumber(measurementData.measuredAmount),
  due_date: toNullableString(measurementData.dueDate),
  supplier_person_id: toNullableString(measurementData.supplierPersonId),
  document_type: toNullableString(measurementData.documentType),
  document_number: toNullableString(measurementData.documentNumber),
})

const toProcurementPayload = (procurementData = {}) => ({
  code: toNullableString(procurementData.code),
  title: String(procurementData.title ?? "").trim(),
  description: toNullableString(procurementData.description),
  estimated_amount: toNullableNumber(procurementData.estimatedAmount),
  needed_by_date: toNullableString(procurementData.neededByDate),
  supplier_person_id: toNullableString(procurementData.supplierPersonId),
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

export async function listConstructionUnits({ bridge, projectId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/units`,
  })

  return {
    items: (payload.items ?? []).map(toUnitView),
    total: payload.total ?? 0,
  }
}

export async function createConstructionUnit({ bridge, projectId, unitData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/units`,
    method: "POST",
    body: toUnitPayload(unitData),
  })

  return toUnitView(payload)
}

export async function updateConstructionUnit({ bridge, unitId, unitData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}`,
    method: "PATCH",
    body: toUnitPayload(unitData),
  })

  return toUnitView(payload)
}

export async function deleteConstructionUnit({ bridge, unitId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}`,
    method: "DELETE",
  })
}

export async function reserveConstructionUnit({ bridge, unitId, reserveData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/reserve`,
    method: "POST",
    body: {
      buyer_person_id: reserveData.buyerPersonId,
      reservation_expires_at: toNullableString(reserveData.reservationExpiresAt),
    },
  })

  return toUnitView(payload)
}

export async function releaseConstructionUnitReservation({ bridge, unitId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/release`,
    method: "POST",
  })

  return toUnitView(payload)
}

export async function confirmConstructionUnitSale({ bridge, unitId, saleData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/confirm-sale`,
    method: "POST",
    body: {
      buyer_person_id: saleData.buyerPersonId,
      sale_price: toNullableNumber(saleData.salePrice),
      first_due_date: saleData.firstDueDate,
      installments: Number(saleData.installments || 1),
    },
  })

  return toUnitView(payload)
}

export async function listConstructionMeasurements({ bridge, projectId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/measurements`,
  })

  return {
    items: (payload.items ?? []).map(toMeasurementView),
    total: payload.total ?? 0,
  }
}

export async function createConstructionMeasurement({ bridge, projectId, measurementData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/measurements`,
    method: "POST",
    body: toMeasurementPayload(measurementData),
  })

  return toMeasurementView(payload)
}

export async function updateConstructionMeasurement({ bridge, measurementId, measurementData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurements/${measurementId}`,
    method: "PATCH",
    body: toMeasurementPayload(measurementData),
  })

  return toMeasurementView(payload)
}

export async function approveConstructionMeasurement({ bridge, measurementId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurements/${measurementId}/approve`,
    method: "POST",
  })

  return toMeasurementView(payload)
}

export async function rejectConstructionMeasurement({ bridge, measurementId, reason }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurements/${measurementId}/reject`,
    method: "POST",
    body: {
      reason: toNullableString(reason),
    },
  })

  return toMeasurementView(payload)
}

export async function deleteConstructionMeasurement({ bridge, measurementId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/measurements/${measurementId}`,
    method: "DELETE",
  })
}

export async function listConstructionProcurementRequests({ bridge, projectId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/procurement-requests`,
  })

  return {
    items: (payload.items ?? []).map(toProcurementView),
    total: payload.total ?? 0,
  }
}

export async function createConstructionProcurementRequest({ bridge, projectId, procurementData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/procurement-requests`,
    method: "POST",
    body: toProcurementPayload(procurementData),
  })

  return toProcurementView(payload)
}

export async function updateConstructionProcurementRequest({ bridge, procurementRequestId, procurementData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/procurement-requests/${procurementRequestId}`,
    method: "PATCH",
    body: toProcurementPayload(procurementData),
  })

  return toProcurementView(payload)
}

export async function submitConstructionProcurementRequest({ bridge, procurementRequestId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/procurement-requests/${procurementRequestId}/submit`,
    method: "POST",
  })

  return toProcurementView(payload)
}

export async function approveConstructionProcurementRequest({ bridge, procurementRequestId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/procurement-requests/${procurementRequestId}/approve`,
    method: "POST",
  })

  return toProcurementView(payload)
}

export async function rejectConstructionProcurementRequest({ bridge, procurementRequestId, reason }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/procurement-requests/${procurementRequestId}/reject`,
    method: "POST",
    body: {
      reason: toNullableString(reason),
    },
  })

  return toProcurementView(payload)
}

export async function deleteConstructionProcurementRequest({ bridge, procurementRequestId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/procurement-requests/${procurementRequestId}`,
    method: "DELETE",
  })
}

export {
  requestJson,
  toBlockPayload,
  toProcurementPayload,
  toProjectPayload,
  toProjectView,
  toSchedulePhasePayload,
  toMeasurementPayload,
  toUnitPayload,
}
