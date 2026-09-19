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
  receiptTemplateId: project.receipt_template_id ?? null,
  commissionReceiptTemplateId: project.commission_receipt_template_id ?? null,
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

const toServiceTemplateItemView = (item) => ({
  id: item.id,
  sectionId: item.section_id ?? null,
  sequenceNumber: item.sequence_number,
  description: item.description,
  verificationMethod: item.verification_method,
  requiresComment: item.requires_comment ?? false,
  requiresPhoto: item.requires_photo ?? false,
})

const toServiceTemplateAuditView = (audit) => ({
  id: audit.id,
  sequenceNumber: audit.sequence_number,
  event: audit.event,
  source: audit.source ?? "manual",
  actorUserId: audit.actor_user_id ?? null,
  actorName: audit.actor_name ?? "",
  serviceName: audit.service_template_name ?? "",
  summary: audit.summary ?? "",
  snapshot: audit.snapshot ?? null,
  createdAt: audit.created_at,
})

const toServiceTemplateView = (template) => ({
  id: template.id,
  companyId: template.company_id,
  name: template.name,
  productId: template.product_id ?? null,
  sourceFileName: template.source_file_name ?? "",
  isActive: template.is_active,
  createdByUserId: template.created_by_user_id ?? null,
  updatedByUserId: template.updated_by_user_id ?? null,
  deletedAt: template.deleted_at ?? null,
  sections: (template.sections ?? []).map((section) => ({
    id: section.id,
    sequenceNumber: section.sequence_number,
    name: section.name,
    items: (section.items ?? []).map(toServiceTemplateItemView),
  })),
  items: (template.items ?? []).map(toServiceTemplateItemView),
})

const toServiceTemplatePayload = (templateData) => ({
  name: toNullableString(templateData.name),
  product_id: templateData.productId || null,
  is_active: templateData.isActive ?? true,
  sections: (templateData.sections ?? []).map((section, sectionIndex) => ({
    sequence_number: sectionIndex + 1,
    name: section.name,
    items: (section.items ?? []).map((item, itemIndex) => ({
      sequence_number: itemIndex + 1,
      description: item.description,
      verification_method: item.verificationMethod,
      requires_comment: item.requiresComment ?? false,
      requires_photo: item.requiresPhoto ?? false,
    })),
  })),
})

const toDocumentationTypeView = (documentationType) => ({
  id: documentationType.id,
  companyId: documentationType.company_id,
  name: documentationType.name,
  systemCode: documentationType.system_code ?? null,
  isActive: documentationType.is_active,
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

const toInspectionRoundView = (round) => ({
  id: round.id,
  inspectionId: round.inspection_id,
  sequenceNumber: round.sequence_number,
  status: round.status,
  verifiedAt: round.verified_at,
  inspectedOn: round.inspected_on ?? null,
  inspectorPersonId: round.inspector_person_id ?? null,
  inspectorName: round.inspector_name ?? "",
  recordedByUserId: round.recorded_by_user_id ?? null,
  recordedByName: round.recorded_by_name ?? "",
  comment: round.comment ?? "",
  source: round.source ?? "manual",
  isInferred: round.is_inferred ?? false,
})

// Ponte para uma API que ainda nao conhece rodadas: entre o restart da API e o
// build do MFE, `rounds` vem undefined e a ficha inteira apareceria como
// pendente. Reconstroi as rodadas a partir da dupla conferencia antiga.
const roundsFromLegacyChecks = (inspection) => {
  const rounds = []
  if (inspection.first_status && inspection.first_status !== "pending") {
    rounds.push({
      id: `${inspection.id}-1`,
      inspection_id: inspection.id,
      sequence_number: 1,
      status: inspection.first_status,
      verified_at: inspection.first_status_at,
      recorded_by_user_id: inspection.first_status_by_user_id,
    })
  }

  if (inspection.second_status && inspection.second_status !== "pending") {
    rounds.push({
      id: `${inspection.id}-2`,
      inspection_id: inspection.id,
      sequence_number: 2,
      status: inspection.second_status,
      verified_at: inspection.second_status_at,
      recorded_by_user_id: inspection.second_status_by_user_id,
    })
  }

  return rounds
}

const toMeasurementInspectionView = (inspection) => {
  const rawRounds = inspection.rounds ?? roundsFromLegacyChecks(inspection)
  const rounds = rawRounds.map(toInspectionRoundView)
  const lastRound = rounds.length ? rounds[rounds.length - 1] : null

  return {
    id: inspection.id,
    measurementItemId: inspection.measurement_item_id,
    sequenceNumber: inspection.sequence_number,
    description: inspection.description,
    verificationMethod: inspection.verification_method ?? "",
    startDate: inspection.start_date ?? null,
    endDate: inspection.end_date ?? null,
    inspectorPersonId: inspection.inspector_person_id ?? null,
    requiresComment: inspection.requires_comment ?? false,
    requiresPhoto: inspection.requires_photo ?? false,
    status: inspection.status ?? lastRound?.status ?? "pending",
    roundsCount: inspection.rounds_count ?? rounds.length,
    lastVerifiedAt: inspection.last_verified_at ?? lastRound?.verifiedAt ?? null,
    approvedAfterReinspection:
      inspection.approved_after_reinspection ?? (lastRound?.status === "compliant" && rounds.length > 1),
    rounds,
    lastRound,
  }
}

const toMeasurementOccurrenceView = (occurrence) => ({
  id: occurrence.id,
  measurementItemId: occurrence.measurement_item_id,
  inspectionId: occurrence.inspection_id ?? null,
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
  // Campo opcional de proposito: um core que ainda nao o devolve deixa a tela
  // tratar como "none" em vez de quebrar. E a ordem de deploy e ERP primeiro.
  qualificationStatus: person.qualification_status ?? "none",
  qualificationExpiresAt: person.qualification_expires_at ?? null,
  qualificationCriterion: person.qualification_criterion ?? null,
  qualifiedAt: person.qualified_at ?? null,
  businessRoles: person.business_roles ?? [],
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
  receipt_template_id: toNullableString(projectData.receiptTemplateId),
  commission_receipt_template_id: toNullableString(projectData.commissionReceiptTemplateId),
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

const describeValidationErrors = (detail) => {
  if (!Array.isArray(detail) || !detail.length) {
    return null
  }

  const described = detail
    .map((item) => {
      const field = (item?.loc ?? []).filter((part) => part !== "body").join(".")
      return field ? `${field}: ${item?.msg ?? "inválido"}` : item?.msg
    })
    .filter(Boolean)

  return described.length ? `Dados recusados pelo servidor — ${described.join("; ")}.` : null
}

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

const toSaleDocumentationPayload = (documentation = {}) => ({
  documentation_type_id: toNullableString(documentation.documentationTypeId),
  name: toNullableString(documentation.name),
  amount: toNullableNumber(documentation.amountValue),
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
        // `detail` como TEXTO puro e o que toda recusa de autorizacao produz:
        // `raise HTTPException(detail="Permissao insuficiente no modulo de
        // Obras")`. Nenhuma das chaves acima existe nesse corpo, e sem este
        // ramo o 403 chegava como "Nao foi possivel concluir a requisicao" --
        // indistinguivel de queda de rede justamente no caso em que o operador
        // precisa saber que o problema e permissao, e nao tentar de novo.
        (typeof payload?.detail === "string" ? payload.detail : null) ||
        // Um 422 do FastAPI traz `detail` como LISTA de erros de campo, e nenhuma
        // das chaves acima existe nele: sem este ramo, toda recusa de contrato
        // virava a mensagem generica e o operador nao sabia o que corrigir.
        describeValidationErrors(payload?.detail) ||
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

export async function listConstructionProjects({
  bridge,
  page = 1,
  pageSize = 20,
  search = "",
  status = "",
  startDate = "",
  endDate = "",
} = {}) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })

  if (search.trim()) {
    query.set("search", search.trim())
  }

  // Os filtros vao para o servidor porque a lista pagina no servidor: filtrar
  // no navegador olharia so a pagina aberta e esconderia obra que casa com o
  // filtro duas paginas adiante.
  if (status) {
    query.set("status", status)
  }

  if (startDate) {
    query.set("start_date_from", startDate)
  }

  if (endDate) {
    query.set("start_date_to", endDate)
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
  // first_due_date e a data do SALDO -- e com ela que o backend grava a fonte
  // BALANCE. A precedencia era invertida: havendo qualquer fonte, o vencimento
  // da primeira (a entrada, quase sempre) vinha na frente e o vencimento do
  // saldo que o usuario escolheu era descartado, ancorando as parcelas na data
  // errada. A fonte so serve de fallback para venda que nao tem saldo.
  const firstPaymentDueDate = saleData.firstDueDate || paymentSources[0]?.due_date
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
      documentations: (saleData.documentations ?? []).map(toSaleDocumentationPayload),
    },
  })

  return toUnitView(payload)
}

export async function updateConstructionUnitInstallment({
  bridge,
  unitId,
  installmentNumber,
  changes,
  receivableId = null,
}) {
  return requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/installments/${installmentNumber}`,
    method: "PATCH",
    body: { ...changes, receivable_id: toNullableString(receivableId) },
  })
}

export async function createConstructionUnitInstallments({ bridge, unitId, installmentData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/installments`,
    method: "POST",
    body: {
      receivable_id: toNullableString(installmentData.receivableId),
      starting_number: Number(installmentData.startingNumber || 1),
      count: Number(installmentData.count || 1),
      first_due_date: toNullableString(installmentData.firstDueDate),
      amount: toNullableNumber(installmentData.amount),
    },
  })

  return (payload ?? []).map(toReceivableInstallmentView)
}

// A baixa e por N formas de recebimento, e o ERP so aceita quando a soma fecha o
// que ha para receber. Cada linha leva o DINHEIRO daquela forma -- o principal
// amortizado e derivado la, porque o extrato bancario nao traz principal.
export async function payConstructionUnitInstallment({
  bridge,
  unitId,
  installmentNumber,
  paymentData,
  receivableId = null,
}) {
  return requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/installments/${installmentNumber}/pay`,
    method: "POST",
    body: {
      receivable_id: toNullableString(receivableId),
      payments: paymentData.payments.map((line) => ({
        payment_method: line.paymentMethod,
        amount: toNullableNumber(line.amount),
        paid_at: line.paidAt ? `${line.paidAt}T12:00:00` : null,
        document_number: toNullableString(line.documentNumber),
      })),
      // Sempre numero, nunca ausente: campo omitido faz o ERP herdar o juros e a
      // multa combinados na parcela, e o rodape da tela fecharia numa conta
      // enquanto o servidor recusa por outra.
      interest: toNullableNumber(paymentData.interest) ?? 0,
      fine: toNullableNumber(paymentData.fine) ?? 0,
      discount: toNullableNumber(paymentData.discount) ?? 0,
      observation: toNullableString(paymentData.observation),
    },
  })
}

// Estorno da baixa inteira. Nao ha estorno por linha aqui: com recibo emitido a
// parcela e imutavel, e derrubar a baixa toda cancela o recibo e queima o numero.
export async function reverseConstructionUnitInstallment({
  bridge,
  unitId,
  installmentNumber,
  receivableId = null,
}) {
  return requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/installments/${installmentNumber}/reverse`,
    method: "POST",
    body: { receivable_id: toNullableString(receivableId) },
  })
}

export async function listErpPaymentMethods({ bridge }) {
  const erpApiBaseUrl = bridge?.erpApiBaseUrl || import.meta.env.VITE_ERP_API_URL || DEFAULT_ERP_API_URL
  const payload = await requestJson({
    bridge,
    path: "/v1/finance/payment-methods",
    baseUrl: erpApiBaseUrl,
  })
  return Array.isArray(payload) ? payload : []
}

// A conta que recebeu cada forma decide a conta contabil de debito
// (BANK_CASH_{id}). Sem a lista aqui, PIX no Itau e TED no Bradesco debitariam o
// mesmo razao -- o defeito que a conta por linha existe para corrigir.
export async function listErpCompanyBankAccounts({ bridge }) {
  const erpApiBaseUrl = bridge?.erpApiBaseUrl || import.meta.env.VITE_ERP_API_URL || DEFAULT_ERP_API_URL
  const companyId = bridge?.companyContext?.companyId
  if (!companyId) {
    return []
  }

  const payload = await requestJson({
    bridge,
    path: `/v1/company/${companyId}`,
    baseUrl: erpApiBaseUrl,
  })

  return (payload?.financial_accounts ?? [])
    .filter((account) => account?.is_active !== false)
    .map((account) => ({
      id: account.id,
      label: account.bank_name || account.account_number || "Conta sem nome",
    }))
}

export async function deleteConstructionUnitInstallment({
  bridge,
  unitId,
  installmentNumber,
  receivableId = null,
}) {
  const params = new URLSearchParams()
  if (receivableId) {
    params.set("receivable_id", String(receivableId))
  }

  const query = params.toString()
  await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/installments/${installmentNumber}${query ? `?${query}` : ""}`,
    method: "DELETE",
  })

  return true
}

export async function deleteConstructionUnitAdjustment({ bridge, unitId, receivableId, reason }) {
  const params = new URLSearchParams({ reason })
  await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/adjustments/${receivableId}?${params.toString()}`,
    method: "DELETE",
  })

  return true
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

const toReceivableInstallmentView = (installment) => ({
  id: installment.id,
  installmentNumber: installment.installment_number,
  totalInstallments: installment.total_installments,
  dueDate: installment.due_date,
  amount: installment.amount ?? null,
  paidAmount: installment.paid_amount ?? null,
  outstandingAmount: installment.outstanding_amount ?? null,
  paymentDate: installment.payment_date ?? null,
  status: installment.status,
  documentNumber: installment.document_number ?? "",
  observation: installment.observation ?? "",
  paymentMethod: installment.payment_method ?? "",
  interest: installment.interest ?? null,
  fine: installment.fine ?? null,
  discount: installment.discount ?? null,
  // Com recibo definitivo emitido a parcela e somente leitura: e o que faz o
  // diálogo abrir travado em vez de deixar o operador digitar e o ERP recusar.
  hasIssuedReceipt: Boolean(installment.has_issued_receipt),
  payments: (installment.payments ?? []).map((payment) => ({
    id: payment.id,
    sequenceNumber: payment.sequence_number,
    paymentMethod: payment.payment_method ?? "",
    amount: payment.amount ?? null,
    netAmount: payment.net_amount ?? null,
    paidAt: payment.paid_at ?? null,
    documentNumber: payment.document_number ?? "",
  })),
})

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
    documentationTotal: payload.documentation_total ?? null,
    totalCharged: payload.total_charged ?? null,
    installmentTotal: payload.installment_total ?? null,
    balanceTotal: payload.balance_total ?? null,
    settlementTotal: payload.settlement_total ?? null,
    commissionTotal: payload.commission_total ?? null,
    commissionPaidTotal: payload.commission_paid_total ?? null,
    commissionOffset: payload.commission_offset ?? null,
    commissions: (payload.commissions ?? []).map(toUnitCommissionView),
    externalReceivableId: payload.external_receivable_id ?? null,
    externalReceivableStatus: payload.external_receivable_status ?? null,
    documentations: (payload.documentations ?? []).map((documentation) => ({
      id: documentation.id,
      documentationTypeId: documentation.documentation_type_id,
      name: documentation.name,
      amount: documentation.amount ?? null,
      sequenceNumber: documentation.sequence_number ?? 1,
    })),
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
      installments: (plan.installments ?? []).map(toReceivableInstallmentView),
      adjustments: (plan.adjustments ?? []).map((adjustment) => ({
        receivableId: adjustment.receivable_id,
        receivableStatus: adjustment.receivable_status ?? "",
        description: adjustment.description ?? "",
        totalAmount: adjustment.total_amount ?? null,
        reason: adjustment.reason ?? "",
        installmentsTotal: adjustment.installments_total ?? 0,
        paidTotal: adjustment.paid_total ?? 0,
        openTotal: adjustment.open_total ?? 0,
        overdueCount: adjustment.overdue_count ?? 0,
        installments: (adjustment.installments ?? []).map(toReceivableInstallmentView),
      })),
    },
  }
}

const toUnitCommissionView = (commission) => ({
  id: commission.id,
  unitId: commission.unit_id,
  beneficiaryPersonId: commission.beneficiary_person_id,
  sequenceNumber: commission.sequence_number,
  amount: commission.amount ?? null,
  dueDate: commission.due_date ?? null,
  paymentDate: commission.payment_date ?? null,
  composesSalePrice: Boolean(commission.composes_sale_price),
  receiptTemplateId: commission.receipt_template_id ?? null,
  documentNumber: commission.document_number ?? "",
  notes: commission.notes ?? "",
})

export async function listConstructionUnitCommissions({ bridge, unitId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/commissions`,
  })

  return {
    items: (payload.items ?? []).map(toUnitCommissionView),
    total: payload.total ?? 0,
  }
}

export async function createConstructionUnitCommissions({ bridge, unitId, commissionData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/commissions`,
    method: "POST",
    body: {
      beneficiary_person_id: commissionData.beneficiaryPersonId,
      amount: toNullableNumber(commissionData.amount),
      due_date: toNullableString(commissionData.dueDate),
      installments: Number(commissionData.installments || 1),
      document_number: toNullableString(commissionData.documentNumber),
      notes: toNullableString(commissionData.notes),
    },
  })

  return {
    items: (payload.items ?? []).map(toUnitCommissionView),
    total: payload.total ?? 0,
  }
}

export async function updateConstructionUnitCommission({ bridge, commissionId, commissionData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/commissions/${commissionId}`,
    method: "PATCH",
    body: {
      beneficiary_person_id: toNullableString(commissionData.beneficiaryPersonId),
      amount: toNullableNumber(commissionData.amount),
      due_date: toNullableString(commissionData.dueDate),
      document_number: toNullableString(commissionData.documentNumber),
      notes: toNullableString(commissionData.notes),
    },
  })

  return toUnitCommissionView(payload)
}

export async function settleConstructionUnitCommission({ bridge, commissionId, paymentDate }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/commissions/${commissionId}/settle`,
    method: "POST",
    body: { payment_date: toNullableString(paymentDate) },
  })

  return toUnitCommissionView(payload)
}

export async function deleteConstructionUnitCommission({ bridge, commissionId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/commissions/${commissionId}`,
    method: "DELETE",
  })

  return true
}

export async function createConstructionUnitAdjustment({ bridge, unitId, adjustmentData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/units/${unitId}/adjustments`,
    method: "POST",
    body: {
      amount: toNullableNumber(adjustmentData.amount),
      installments: Number(adjustmentData.installments || 1),
      first_due_date: toNullableString(adjustmentData.firstDueDate),
      reason: toNullableString(adjustmentData.reason),
    },
  })

  return {
    constructionUnitId: payload.construction_unit_id ?? null,
    contractId: payload.contract_id ?? null,
    receivableId: payload.receivable_id ?? null,
    receivableStatus: payload.receivable_status ?? "",
    totalAmount: payload.total_amount ?? null,
    installments: payload.installments ?? 1,
  }
}

export async function listErpReceiptTemplates({ bridge }) {
  const erpApiBaseUrl = bridge?.erpApiBaseUrl || import.meta.env.VITE_ERP_API_URL || DEFAULT_ERP_API_URL
  const payload = await requestJson({
    bridge,
    path: "/v1/receipt-templates/?page=1&page_size=200",
    baseUrl: erpApiBaseUrl,
  })

  return {
    items: (payload.items ?? []).map((template) => ({
      id: template.id,
      name: template.name,
      isActive: template.is_active ?? true,
    })),
    total: payload.total ?? 0,
  }
}

export async function listConstructionDocumentationTypes({ bridge, search = null, onlyActive = true } = {}) {
  const params = new URLSearchParams()
  if (search) {
    params.set("search", search)
  }

  params.set("only_active", onlyActive ? "true" : "false")

  const payload = await requestJson({
    bridge,
    path: `/v1/construction/documentation-types?${params.toString()}`,
  })

  return {
    items: (payload.items ?? []).map(toDocumentationTypeView),
    total: payload.total ?? 0,
  }
}

export async function listConstructionServiceTemplates({
  bridge,
  search = null,
  onlyActive = true,
  onlyDeleted = false,
} = {}) {
  const params = new URLSearchParams()
  if (search) {
    params.set("search", search)
  }

  params.set("only_active", onlyActive ? "true" : "false")
  params.set("only_deleted", onlyDeleted ? "true" : "false")

  const payload = await requestJson({
    bridge,
    path: `/v1/construction/service-templates?${params.toString()}`,
  })

  return {
    items: (payload.items ?? []).map(toServiceTemplateView),
    total: payload.total ?? 0,
  }
}

export async function listConstructionServiceTemplateAudits({ bridge, serviceTemplateId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/service-templates/${serviceTemplateId}/audits`,
  })

  return {
    items: (payload.items ?? []).map(toServiceTemplateAuditView),
    total: payload.total ?? 0,
  }
}

export async function createConstructionServiceTemplate({ bridge, templateData }) {
  const payload = await requestJson({
    bridge,
    path: "/v1/construction/service-templates",
    method: "POST",
    body: toServiceTemplatePayload(templateData),
  })

  return toServiceTemplateView(payload)
}

export async function replaceConstructionServiceTemplate({ bridge, serviceTemplateId, templateData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/service-templates/${serviceTemplateId}`,
    method: "PUT",
    body: toServiceTemplatePayload(templateData),
  })

  return toServiceTemplateView(payload)
}

export async function updateConstructionServiceTemplate({ bridge, serviceTemplateId, templateData }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/service-templates/${serviceTemplateId}`,
    method: "PATCH",
    body: {
      name: toNullableString(templateData.name),
      product_id: templateData.productId || null,
      is_active: templateData.isActive,
    },
  })

  return toServiceTemplateView(payload)
}

export async function deleteConstructionServiceTemplate({ bridge, serviceTemplateId }) {
  await requestJson({
    bridge,
    path: `/v1/construction/service-templates/${serviceTemplateId}`,
    method: "DELETE",
  })
}

export async function downloadConstructionServiceTemplateExample({ bridge }) {
  const apiBaseUrl = bridge?.constructionApiBaseUrl || DEFAULT_CONSTRUCTION_API_URL
  const headers = { ...(bridge?.getAuthHeaders?.() ?? {}) }

  if (!headers.Authorization || !headers["X-Company-ID"]) {
    throw new Error("Contexto autenticado da empresa indisponível.")
  }

  const response = await fetch(`${apiBaseUrl}/v1/construction/service-templates/example`, { headers })

  if (!response.ok) {
    throw new Error("Não foi possível baixar o modelo da planilha.")
  }

  return response.blob()
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
      sectionsCount: result.sections_count ?? 0,
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

export async function verifyConstructionMeasurementInspection({
  bridge,
  inspectionId,
  status,
  comment = "",
  inspectorPersonId = null,
  inspectedOn = null,
  openOccurrence = false,
}) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurement-inspections/${inspectionId}/verify`,
    method: "POST",
    body: {
      status,
      comment: comment || null,
      inspector_person_id: inspectorPersonId || null,
      inspected_on: inspectedOn || null,
      open_occurrence: openOccurrence,
    },
  })

  return toMeasurementInspectionView(payload)
}

export async function listConstructionInspectionRounds({ bridge, inspectionId }) {
  const payload = await requestJson({
    bridge,
    path: `/v1/construction/measurement-inspections/${inspectionId}/rounds`,
  })

  return {
    items: (payload.items ?? []).map(toInspectionRoundView),
    total: payload.total ?? 0,
  }
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
