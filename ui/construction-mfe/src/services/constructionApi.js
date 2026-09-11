const DEFAULT_CONSTRUCTION_API_URL = "http://127.0.0.1:8010"
const DEFAULT_ERP_API_URL = "http://127.0.0.1:8000"

const stripNonDigits = (value) => String(value ?? "").replace(/\D/g, "")

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
  description: unit.description ?? "",
  unitType: unit.unit_type,
  typology: unit.typology ?? "",
  floor: unit.floor ?? "",
  privateArea: unit.private_area ?? null,
  totalArea: unit.total_area ?? null,
  salePrice: unit.sale_price ?? null,
  discountAmount: unit.discount_amount ?? null,
  netSalePrice: unit.net_sale_price ?? null,
  buyerPersonId: unit.buyer_person_id ?? null,
  secondaryBuyerPersonId: unit.secondary_buyer_person_id ?? null,
  brokerPersonId: unit.broker_person_id ?? null,
  contractSignatureDate: unit.contract_signature_date ?? null,
  saleNotes: unit.sale_notes ?? "",
  reservedAt: unit.reserved_at ?? null,
  reservationExpiresAt: unit.reservation_expires_at ?? null,
  soldAt: unit.sold_at ?? null,
  externalContractId: unit.external_contract_id ?? null,
  externalContractStatus: unit.external_contract_status ?? null,
  externalReceivableId: unit.external_receivable_id ?? null,
  externalReceivableStatus: unit.external_receivable_status ?? null,
  analyticCostCenterId: unit.analytic_cost_center_id ?? null,
  status: unit.status,
  createdAt: unit.created_at ?? null,
  updatedAt: unit.updated_at ?? null,
})

const toServiceTemplateView = (template) => ({
  id: template.id,
  companyId: template.company_id,
  name: template.name,
  productId: template.product_id ?? null,
  sourceFileName: template.source_file_name ?? "",
  isActive: template.is_active,
  items: (template.items ?? []).map((item) => ({
    id: item.id,
    sequenceNumber: item.sequence_number,
    description: item.description,
    verificationMethod: item.verification_method,
  })),
})

const toMeasurementItemView = (item) => ({
  id: item.id,
  companyId: item.company_id,
  measurementId: item.measurement_id,
  sequenceNumber: item.sequence_number,
  serviceTemplateId: item.service_template_id ?? null,
  productId: item.product_id ?? null,
  productDescription: item.product_description ?? "",
  description: item.description,
  amount: item.amount ?? null,
  startDate: item.start_date ?? null,
  endDate: item.end_date ?? null,
  inspectorPersonId: item.inspector_person_id ?? null,
  inspectionStatus: item.inspection_status,
  createdByUserId: item.created_by_user_id ?? null,
  inspections: (item.inspections ?? []).map(toMeasurementInspectionView),
  occurrences: (item.occurrences ?? []).map(toMeasurementOccurrenceView),
})

const toMeasurementInspectionView = (inspection) => ({
  id: inspection.id,
  measurementItemId: inspection.measurement_item_id,
  sequenceNumber: inspection.sequence_number,
  description: inspection.description,
  verificationMethod: inspection.verification_method ?? "",
  startDate: inspection.start_date ?? null,
  endDate: inspection.end_date ?? null,
  inspectorPersonId: inspection.inspector_person_id ?? null,
  firstStatus: inspection.first_status,
  firstStatusAt: inspection.first_status_at ?? null,
  firstStatusByUserId: inspection.first_status_by_user_id ?? null,
  secondStatus: inspection.second_status,
  secondStatusAt: inspection.second_status_at ?? null,
  secondStatusByUserId: inspection.second_status_by_user_id ?? null,
  isDoubleChecked: inspection.is_double_checked ?? false,
})

const toMeasurementOccurrenceView = (occurrence) => ({
  id: occurrence.id,
  measurementItemId: occurrence.measurement_item_id,
  sequenceNumber: occurrence.sequence_number,
  problem: occurrence.problem,
  solution: occurrence.solution ?? "",
  status: occurrence.status,
  openedAt: occurrence.opened_at ?? null,
  closedAt: occurrence.closed_at ?? null,
  inspectorPersonId: occurrence.inspector_person_id ?? null,
  registeredByUserId: occurrence.registered_by_user_id ?? null,
})

const toMeasurementView = (measurement) => ({
  id: measurement.id,
  companyId: measurement.company_id,
  projectId: measurement.project_id,
  unitId: measurement.unit_id ?? null,
  schedulePhaseId: measurement.schedule_phase_id ?? null,
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
  createdByUserId: measurement.created_by_user_id ?? null,
  submittedByUserId: measurement.submitted_by_user_id ?? null,
  submittedAt: measurement.submitted_at ?? null,
  approvedByUserId: measurement.approved_by_user_id ?? null,
  rejectedByUserId: measurement.rejected_by_user_id ?? null,
  rejectedAt: measurement.rejected_at ?? null,
  itemsTotalAmount: measurement.items_total_amount ?? null,
  itemsCount: measurement.items_count ?? null,
  pendingInspectionsCount: measurement.pending_inspections_count ?? null,
  openOccurrencesCount: measurement.open_occurrences_count ?? null,
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

const toPersonSummaryView = (person) => ({
  id: person.id,
  name: person.name,
  document: person.document ?? null,
  primaryPhone: person.primary_phone ?? null,
  primaryEmail: person.primary_email ?? null,
  isActive: person.is_active !== false,
})

const toAddressView = (address) => ({
  zipCode: address.zip_code ?? "",
  street: address.street ?? "",
  district: address.neighborhood ?? "",
  city: address.city ?? "",
  state: address.state ?? "",
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

  if (typeof value === "number") {
    return Number.isNaN(value) ? null : value
  }

  const valueText = String(value).trim()
  const normalizedValue = valueText.includes(",")
    ? valueText.replace(/\s+/g, "").replace(/\./g, "").replace(",", ".").replace(/[^0-9.-]/g, "")
    : valueText.replace(/[^0-9.-]/g, "")
  const parsedValue = Number(normalizedValue)
  return Number.isNaN(parsedValue) ? null : parsedValue
}

const toUnitPayload = (unitData = {}) => ({
  code: String(unitData.code ?? "").trim(),
  description: toNullableString(unitData.description),
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
  unit_id: toNullableString(measurementData.unitId),
  schedule_phase_id: toNullableString(measurementData.schedulePhaseId),
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

const toMeasurementItemPayload = (itemData = {}) => ({
  description: toNullableString(itemData.description),
  service_template_id: toNullableString(itemData.serviceTemplateId),
  amount: toNullableNumber(itemData.amount),
  product_id: toNullableString(itemData.productId),
  product_description: toNullableString(itemData.productDescription),
  start_date: toNullableString(itemData.startDate),
  end_date: toNullableString(itemData.endDate),
  inspector_person_id: toNullableString(itemData.inspectorPersonId),
})

const toSalePaymentSourcePayload = (paymentSource = {}) => ({
  source_type: String(paymentSource.sourceType ?? "").trim(),
  amount: toNullableNumber(paymentSource.amount),
  due_date: toNullableString(paymentSource.dueDate),
  installments: Number(paymentSource.installments || 1),
})

async function requestJson({ bridge, path, method = "GET", body = null, baseUrl = null }) {
  const apiBaseUrl = baseUrl || bridge?.constructionApiBaseUrl || DEFAULT_CONSTRUCTION_API_URL
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
    let errorMessage = fallback
    try {
      const payload = await response.json()
      const payloadDetails = payload?.details
      errorMessage =
        payload?.detail?.message ||
        payload?.message ||
        (typeof payloadDetails === "string" ? payloadDetails : payloadDetails?.message) ||
        fallback
    } catch {
      errorMessage = fallback
    }
    throw new Error(errorMessage)
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export async function fetchConstructionAddressByZip({ bridge, zipCode }) {
  const normalizedZip = stripNonDigits(zipCode).slice(0, 8)
  if (normalizedZip.length !== 8) {
    throw new Error("Informe um CEP válido com 8 dígitos.")
  }

  const erpApiBaseUrl = bridge?.erpApiBaseUrl || import.meta.env.VITE_ERP_API_URL || DEFAULT_ERP_API_URL
  const payload = await requestJson({
    bridge,
    path: `/v1/address/${normalizedZip}`,
    baseUrl: erpApiBaseUrl,
  })

  return toAddressView(payload)
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

export async function listConstructionPersonSummaries({
  bridge,
  search = "",
  page = 1,
  pageSize = 50,
} = {}) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })

  if (search.trim()) {
    query.set("search", search.trim())
  }

  const payload = await requestJson({
    bridge,
    path: `/v1/construction/person-summaries?${query.toString()}`,
  })

  return {
    items: (payload.items ?? []).map(toPersonSummaryView),
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
  const paymentSources = (saleData.paymentSources ?? []).map(toSalePaymentSourcePayload)
  const firstPaymentDueDate = paymentSources[0]?.due_date ?? saleData.firstDueDate
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/confirm-sale`,
    method: "POST",
    body: {
      buyer_person_id: saleData.buyerPersonId,
      secondary_buyer_person_id: toNullableString(saleData.secondaryBuyerPersonId),
      broker_person_id: toNullableString(saleData.brokerPersonId),
      sale_price: toNullableNumber(saleData.salePrice),
      discount_amount: toNullableNumber(saleData.discountAmount),
      contract_signature_date: toNullableString(saleData.contractSignatureDate),
      sale_notes: toNullableString(saleData.saleNotes),
      first_due_date: firstPaymentDueDate,
      installments: Number(saleData.installments || paymentSources[0]?.installments || 1),
      payment_sources: paymentSources.length ? paymentSources : null,
    },
  })

  return toUnitView(payload)
}

export async function updateConstructionUnitInstallment({ bridge, unitId, installmentNumber, changes }) {
  return requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/installments/${installmentNumber}`,
    method: "PATCH",
    body: changes,
  })
}

export async function getConstructionProjectSummary({ bridge, projectId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/projects/${projectId}/summary`,
  })

  return {
    unitsCount: payload.units_count ?? 0,
    unitsSoldCount: payload.units_sold_count ?? 0,
    unitsReservedCount: payload.units_reserved_count ?? 0,
    unitsAvailableCount: payload.units_available_count ?? 0,
    unitsTotalAmount: payload.units_total_amount ?? 0,
    unitsSoldAmount: payload.units_sold_amount ?? 0,
    discountAmount: payload.discount_amount ?? 0,
    plannedCostAmount: payload.planned_cost_amount ?? 0,
    measuredCostAmount: payload.measured_cost_amount ?? 0,
    paidCostAmount: payload.paid_cost_amount ?? 0,
    costDifferenceAmount: payload.cost_difference_amount ?? 0,
    measurementsCount: payload.measurements_count ?? 0,
    measurementsApprovedCount: payload.measurements_approved_count ?? 0,
    procurementRequestsCount: payload.procurement_requests_count ?? 0,
    receivablesCount: payload.receivables_count ?? 0,
    receivableTotalAmount: payload.receivable_total_amount ?? 0,
    receivedAmount: payload.received_amount ?? 0,
    openAmount: payload.open_amount ?? 0,
    overdueAmount: payload.overdue_amount ?? 0,
    overdueCount: payload.overdue_count ?? 0,
    erpUnavailableReason: payload.erp_unavailable_reason ?? "",
  }
}

export async function getConstructionUnitPaymentPlan({ bridge, unitId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/payment-plan`,
  })

  const plan = payload.payment_plan ?? {}

  return {
    constructionUnitId: payload.construction_unit_id,
    unitCode: payload.unit_code,
    salePrice: payload.sale_price ?? null,
    discountAmount: payload.discount_amount ?? null,
    installmentTotal: payload.installment_total ?? null,
    settlementTotal: payload.settlement_total ?? null,
    externalReceivableId: payload.external_receivable_id ?? null,
    externalReceivableStatus: payload.external_receivable_status ?? null,
    sources: (payload.sources ?? []).map((source) => ({
      sourceType: source.source_type,
      label: source.label,
      amount: source.amount ?? null,
      dueDate: source.due_date ?? null,
      installments: source.installments ?? 1,
      generatesInstallments: Boolean(source.generates_installments),
    })),
    paymentPlan: {
      receivableId: plan.receivable_id ?? null,
      receivableStatus: plan.receivable_status ?? null,
      receivableDescription: plan.receivable_description ?? "",
      receivableTotalAmount: plan.receivable_total_amount ?? null,
      contractId: plan.contract_id ?? null,
      contractCode: plan.contract_code ?? "",
      contractStatus: plan.contract_status ?? "",
      contractContentHtml: plan.contract_content_html ?? "",
      installmentsTotal: plan.installments_total ?? 0,
      paidTotal: plan.paid_total ?? 0,
      openTotal: plan.open_total ?? 0,
      overdueCount: plan.overdue_count ?? 0,
      erpUnavailableReason: plan.erp_unavailable_reason ?? "",
      installments: (plan.installments ?? []).map((installment) => ({
        id: installment.id,
        installmentNumber: installment.installment_number,
        totalInstallments: installment.total_installments,
        dueDate: installment.due_date,
        amount: installment.amount ?? null,
        paidAmount: installment.paid_amount ?? null,
        paymentDate: installment.payment_date ?? null,
        status: installment.status,
        documentNumber: installment.document_number ?? "",
        observation: installment.observation ?? "",
        paymentMethod: installment.payment_method ?? "",
      })),
    },
  }
}

export async function listConstructionServiceTemplates({ bridge, search = null, onlyActive = true } = {}) {
  const params = new URLSearchParams()
  if (search) {
    params.set("search", search)
  }

  params.set("only_active", onlyActive ? "true" : "false")

  const payload = await requestJson({
    bridge,
    path: `/v1/construction/service-templates?${params.toString()}`,
  })

  return {
    items: (payload.items ?? []).map(toServiceTemplateView),
    total: payload.total ?? 0,
  }
}

export async function updateConstructionServiceTemplate({ bridge, serviceTemplateId, templateData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/service-templates/${serviceTemplateId}`,
    method: "PATCH",
    body: {
      name: toNullableString(templateData.name),
      is_active: templateData.isActive,
    },
  })

  return toServiceTemplateView(payload)
}

export async function importConstructionServiceTemplates({ bridge, files }) {
  const apiBaseUrl = bridge?.constructionApiBaseUrl || DEFAULT_CONSTRUCTION_API_URL
  const headers = { ...(bridge?.getAuthHeaders?.() ?? {}) }

  if (!headers.Authorization || !headers["X-Company-ID"]) {
    throw new Error("Contexto autenticado da empresa indisponível.")
  }

  const formData = new FormData()
  for (const file of files) {
    formData.append("files", file, file.name)
  }

  const response = await fetch(`${apiBaseUrl}/v1/construction/service-templates/import`, {
    method: "POST",
    headers,
    body: formData,
  })

  if (!response.ok) {
    let errorMessage = "Não foi possível importar a planilha de serviços."
    try {
      const payload = await response.json()
      errorMessage = payload?.detail?.message || payload?.detail || payload?.message || errorMessage
    } catch {
      // resposta sem corpo JSON mantém a mensagem padrão
    }
    throw new Error(typeof errorMessage === "string" ? errorMessage : "Falha ao importar a planilha.")
  }

  const payload = await response.json()

  return {
    results: (payload.results ?? []).map((result) => ({
      fileName: result.file_name,
      status: result.status,
      serviceTemplateId: result.service_template_id ?? null,
      serviceName: result.service_name ?? "",
      itemsCount: result.items_count ?? 0,
      message: result.message ?? "",
    })),
    created: payload.created ?? 0,
    updated: payload.updated ?? 0,
    skipped: payload.skipped ?? 0,
    failed: payload.failed ?? 0,
  }
}

export async function submitConstructionMeasurement({ bridge, measurementId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurements/${measurementId}/submit`,
    method: "POST",
  })

  return toMeasurementView(payload)
}

export async function listConstructionMeasurementItems({ bridge, measurementId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurements/${measurementId}/items`,
  })

  return {
    items: (payload.items ?? []).map(toMeasurementItemView),
    total: payload.total ?? 0,
    totalAmount: payload.total_amount ?? 0,
  }
}

export async function createConstructionMeasurementItem({ bridge, measurementId, itemData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurements/${measurementId}/items`,
    method: "POST",
    body: toMeasurementItemPayload(itemData),
  })

  return toMeasurementItemView(payload)
}

export async function updateConstructionMeasurementItem({ bridge, itemId, itemData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurement-items/${itemId}`,
    method: "PATCH",
    body: toMeasurementItemPayload(itemData),
  })

  return toMeasurementItemView(payload)
}

export async function deleteConstructionMeasurementItem({ bridge, itemId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/measurement-items/${itemId}`,
    method: "DELETE",
  })
}

export async function createConstructionMeasurementInspection({ bridge, itemId, inspectionData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurement-items/${itemId}/inspections`,
    method: "POST",
    body: {
      description: inspectionData.description,
      verification_method: toNullableString(inspectionData.verificationMethod),
      start_date: toNullableString(inspectionData.startDate),
      end_date: toNullableString(inspectionData.endDate),
      inspector_person_id: toNullableString(inspectionData.inspectorPersonId),
    },
  })

  return toMeasurementInspectionView(payload)
}

export async function verifyConstructionMeasurementInspection({ bridge, inspectionId, checkNumber, status }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurement-inspections/${inspectionId}/verify`,
    method: "POST",
    body: {
      check_number: checkNumber,
      status,
    },
  })

  return toMeasurementInspectionView(payload)
}

export async function deleteConstructionMeasurementInspection({ bridge, inspectionId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/measurement-inspections/${inspectionId}`,
    method: "DELETE",
  })
}

export async function createConstructionMeasurementOccurrence({ bridge, itemId, occurrenceData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurement-items/${itemId}/occurrences`,
    method: "POST",
    body: {
      problem: occurrenceData.problem,
      solution: toNullableString(occurrenceData.solution),
      opened_at: toNullableString(occurrenceData.openedAt),
      inspector_person_id: toNullableString(occurrenceData.inspectorPersonId),
    },
  })

  return toMeasurementOccurrenceView(payload)
}

export async function updateConstructionMeasurementOccurrence({ bridge, occurrenceId, occurrenceData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurement-occurrences/${occurrenceId}`,
    method: "PATCH",
    body: {
      problem: toNullableString(occurrenceData.problem),
      solution: toNullableString(occurrenceData.solution),
      status: toNullableString(occurrenceData.status),
      closed_at: toNullableString(occurrenceData.closedAt),
    },
  })

  return toMeasurementOccurrenceView(payload)
}

export async function deleteConstructionMeasurementOccurrence({ bridge, occurrenceId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/measurement-occurrences/${occurrenceId}`,
    method: "DELETE",
  })
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
