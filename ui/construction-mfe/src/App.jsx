import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  BarChart3,
  Building2,
  ChevronDown,
  ChevronLeft,
  CheckCircle,
  Clock,
  FileCog,
  FileText,
  HandCoins,
  Home,
  Layers3,
  ListChecks,
  PackageSearch,
  Pencil,
  Plus,
  RefreshCw,
  Route,
  Send,
  ShieldCheck,
  Upload,
  ShoppingCart,
  TriangleAlert,
  Trash2,
  Unlock,
} from "lucide-react"
import styles from "./App.module.css"
import CreatableCombobox from "./components/CreatableCombobox.jsx"
import { resolveConstructionBridge } from "./bridge/constructionBridge.js"
import {
  approveConstructionProcurementRequest,
  approveConstructionMeasurement,
  confirmConstructionUnitSale,
  createConstructionBlock,
  createConstructionMeasurement,
  createConstructionMeasurementInspection,
  createConstructionMeasurementItem,
  createConstructionMeasurementOccurrence,
  createConstructionProcurementRequest,
  createConstructionProject,
  createConstructionSchedulePhase,
  createConstructionUnit,
  createConstructionUnitAdjustment,
  createConstructionUnitCommissions,
  createConstructionUnitInstallments,
  deleteConstructionUnitAdjustment,
  deleteConstructionUnitInstallment,
  deleteConstructionBlock,
  deleteConstructionMeasurement,
  deleteConstructionMeasurementInspection,
  deleteConstructionMeasurementItem,
  deleteConstructionMeasurementOccurrence,
  deleteConstructionProcurementRequest,
  deleteConstructionProject,
  deleteConstructionSchedulePhase,
  deleteConstructionUnit,
  deleteConstructionUnitCommission,
  fetchConstructionAddressByZip,
  listConstructionBlocks,
  listConstructionDocumentationTypes,
  getConstructionProjectSummary,
  getConstructionUnitPaymentPlan,
  updateConstructionUnitInstallment,
  importConstructionServiceTemplates,
  listConstructionMeasurementItems,
  listConstructionMeasurements,
  listConstructionPersonSummaries,
  listConstructionProcurementRequests,
  listConstructionProjects,
  listConstructionSchedulePhases,
  listConstructionServiceTemplates,
  listConstructionUnits,
  listErpReceiptTemplates,
  payConstructionUnitInstallment,
  rejectConstructionProcurementRequest,
  rejectConstructionMeasurement,
  releaseConstructionUnitReservation,
  reserveConstructionUnit,
  settleConstructionUnitCommission,
  submitConstructionMeasurement,
  submitConstructionProcurementRequest,
  updateConstructionBlock,
  updateConstructionMeasurement,
  updateConstructionMeasurementItem,
  updateConstructionMeasurementOccurrence,
  updateConstructionProcurementRequest,
  verifyConstructionMeasurementInspection,
  updateConstructionProject,
  updateConstructionSchedulePhase,
  updateConstructionUnit,
} from "./services/constructionApi.js"

const defaultFilters = {
  search: "",
  status: "",
  startDate: "",
  endDate: "",
}

const statusLabel = {
  draft: "Rascunho",
  active: "Ativa",
  paused: "Pausada",
  completed: "Concluída",
  cancelled: "Cancelada",
  canceled: "Cancelada",
}

const projectTypeOptions = [
  { value: "residential_vertical", label: "Residencial vertical" },
  { value: "residential_horizontal", label: "Residencial horizontal" },
  { value: "commercial", label: "Comercial" },
  { value: "mixed_use", label: "Uso misto" },
  { value: "infrastructure", label: "Infraestrutura" },
  { value: "industrial", label: "Industrial" },
]

const projectTypeLabel = Object.fromEntries(projectTypeOptions.map((option) => [option.value, option.label]))

const blockStatusOptions = [
  { value: "active", label: "Ativo" },
  { value: "inactive", label: "Inativo" },
]

const scheduleStatusOptions = [
  { value: "planned", label: "Planejada" },
  { value: "in_progress", label: "Em andamento" },
  { value: "completed", label: "Concluída" },
  { value: "cancelled", label: "Cancelada" },
]

const scheduleStatusLabel = Object.fromEntries(scheduleStatusOptions.map((option) => [option.value, option.label]))

const unitStatusOptions = [
  { value: "available", label: "Disponível" },
  { value: "reserved", label: "Reservada" },
  { value: "sold", label: "Vendida" },
  { value: "delivered", label: "Entregue" },
  { value: "terminated", label: "Distratada" },
  { value: "unavailable", label: "Indisponível" },
]

const unitStatusLabel = Object.fromEntries(unitStatusOptions.map((option) => [option.value, option.label]))

const measurementStatusOptions = [
  { value: "draft", label: "Rascunho" },
  { value: "submitted", label: "Enviada" },
  { value: "in_approval", label: "Em aprovação" },
  { value: "approved", label: "Aprovada" },
  { value: "rejected", label: "Rejeitada" },
  { value: "paid", label: "Paga" },
]

const measurementStatusLabel = Object.fromEntries(measurementStatusOptions.map((option) => [option.value, option.label]))

const procurementStatusOptions = [
  { value: "draft", label: "Rascunho" },
  { value: "pending_approval", label: "Aguardando aprovação" },
  { value: "approved", label: "Aprovada" },
  { value: "rejected", label: "Rejeitada" },
  { value: "sent_to_erp", label: "Enviada ao ERP" },
]

const procurementStatusLabel = Object.fromEntries(procurementStatusOptions.map((option) => [option.value, option.label]))

const projectDetailTabs = [
  { id: "overview", label: "Visão geral", icon: Building2 },
  { id: "blocks", label: "Blocos/Torres", icon: Route },
  { id: "units", label: "Unidades", icon: Home },
  { id: "schedule", label: "Cronograma", icon: ListChecks },
  { id: "procurement", label: "Requisições", icon: PackageSearch },
  { id: "reports", label: "Relatórios", icon: BarChart3 },
  { id: "integrations", label: "Integrações", icon: FileCog },
]

const unitDetailTabs = [
  { id: "summary", label: "Resumo", icon: Home },
  { id: "measurements", label: "Medições", icon: HandCoins },
  { id: "installments", label: "Parcelas", icon: ShoppingCart },
  { id: "commissions", label: "Sinal", icon: HandCoins },
  { id: "contract", label: "Contrato", icon: FileText },
]

const statusOptions = Object.entries(statusLabel)
  .filter(([value]) => value !== "canceled")
  .map(([value, label]) => ({ value, label }))

const dateFormatter = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" })
const moneyFormatter = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" })

const stripNonDigits = (value) => String(value ?? "").replace(/\D/g, "")

const formatCurrencyInput = (value = "") => {
  const digits = stripNonDigits(value)
  if (!digits) {
    return ""
  }

  const cents = Number.parseInt(digits.replace(/^0+/, "") || "0", 10)
  if (Number.isNaN(cents)) {
    return ""
  }

  return (cents / 100).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

const parseCurrencyToNumber = (value) => {
  const digits = stripNonDigits(value)
  return digits ? Number.parseInt(digits, 10) / 100 : 0
}

// O saldo da parcela: com N recebimentos por parcela, `amount` deixou de ser o
// que se baixa -- o que se baixa e o que ainda falta. Quem decide e o ERP, que
// devolve o saldo pronto; a subtracao aqui so cobre a resposta antiga.
const installmentOutstanding = (installment) => {
  if (installment?.outstandingAmount != null) {
    return Number(installment.outstandingAmount)
  }

  const amount = Number(installment?.amount) || 0
  const received = Number(installment?.paidAmount) || 0
  return Math.max(0, amount - received)
}

const formatCurrencyFromNumber = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return ""
  }

  return Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

const maskZip = (value) => {
  const digits = stripNonDigits(value).slice(0, 8)
  if (digits.length <= 5) {
    return digits
  }

  return `${digits.slice(0, 5)}-${digits.slice(5)}`
}

const normalizeZip = (value) => stripNonDigits(value).slice(0, 8)

const defaultProjectForm = {
  code: "",
  name: "",
  description: "",
  status: "draft",
  projectType: "residential_vertical",
  customerPersonId: "",
  cnpjSpe: "",
  startDate: "",
  expectedEndDate: "",
  actualEndDate: "",
  addressStreet: "",
  addressNumber: "",
  addressDistrict: "",
  addressCity: "",
  addressState: "",
  addressZipCode: "",
  receiptTemplateId: "",
  commissionReceiptTemplateId: "",
}

const defaultBlockForm = {
  code: "",
  name: "",
  status: "active",
  floorsCount: "",
}

const defaultSchedulePhaseForm = {
  name: "",
  sequenceOrder: "",
  status: "planned",
  plannedStartDate: "",
  plannedEndDate: "",
  actualStartDate: "",
  actualEndDate: "",
  progressPercent: "0",
}

const DEFAULT_UNIT_DESCRIPTION = "UNIDADE"
const MAX_UNIT_BATCH_SIZE = 200

const defaultUnitForm = {
  code: "",
  description: DEFAULT_UNIT_DESCRIPTION,
  quantity: "1",
  unitType: "",
  typology: "",
  blockId: "",
  floor: "",
  privateArea: "",
  totalArea: "",
  salePrice: "",
  status: "available",
}

const defaultReserveUnitForm = {
  buyerPersonId: "",
  reservationExpiresAt: "",
}

const defaultEditInstallmentForm = {
  paymentMethod: "",
  documentNumber: "",
  observation: "",
}

const defaultCommissionForm = {
  beneficiaryPersonId: "",
  amount: "",
  dueDate: "",
  installments: "1",
  composesSalePrice: false,
  documentNumber: "",
  notes: "",
}

const defaultAdjustmentForm = {
  amount: "",
  installments: "1",
  firstDueDate: "",
  reason: "",
}

const defaultCreateInstallmentForm = {
  receivableId: "",
  startingNumber: "1",
  count: "1",
  firstDueDate: "",
  amount: "",
}

const defaultPayInstallmentForm = {
  paymentMethod: "PIX",
  paidAmount: "",
  paidAt: "",
  interest: "",
  fine: "",
  discount: "",
  observation: "",
}

const defaultSaleUnitForm = {
  buyerPersonId: "",
  secondaryBuyerPersonId: "",
  brokerPersonId: "",
  salePrice: "",
  discountAmount: "",
  contractSignatureDate: "",
  saleNotes: "",
  downPaymentAmount: "",
  downPaymentDueDate: "",
  downPaymentInstallments: "1",
  firstDueDate: "",
  installments: "1",
  governmentSubsidyAmount: "",
  governmentSubsidyDueDate: "",
  governmentSubsidyInstallments: "1",
  fgtsAmount: "",
  fgtsDueDate: "",
  fgtsInstallments: "1",
  financingAmount: "",
  financingDueDate: "",
  financingInstallments: "1",
  documentations: [],
}

// Das fontes informadas, so a entrada vira parcela. O saldo tambem parcela,
// mas nao esta aqui porque nao e digitado: ele e o que sobra do preco.
const SALE_INSTALLMENT_SOURCE_TYPES = ["down_payment"]

// O saldo nao tem campo de valor: ele e calculado. Do que veio gravado
// aproveitamos so as parcelas e o primeiro vencimento que o usuario escolheu.
const SALE_BALANCE_SOURCE_TYPES = ["balance", "direct_builder"]

function saleFormFieldsFromSources(sources) {
  const fields = {}

  for (const source of sources ?? []) {
    if (SALE_BALANCE_SOURCE_TYPES.includes(source.sourceType)) {
      fields.installments = String(source.installments ?? 1)
      fields.firstDueDate = source.dueDate ?? ""
      continue
    }

    const definition = salePaymentSourceDefinitions.find(
      (candidate) => candidate.sourceType === source.sourceType,
    )
    if (!definition) {
      continue
    }

    fields[definition.amountField] = formatCurrencyFromNumber(source.amount)
    fields[definition.dueDateField] = source.dueDate ?? ""
    fields[definition.installmentsField] = String(source.installments ?? 1)
  }

  return fields
}

const salePaymentSourceDefinitions = [
  {
    sourceType: "down_payment",
    label: "Entrada",
    amountField: "downPaymentAmount",
    dueDateField: "downPaymentDueDate",
    installmentsField: "downPaymentInstallments",
  },
  {
    sourceType: "government_subsidy",
    label: "Subsídio",
    amountField: "governmentSubsidyAmount",
    dueDateField: "governmentSubsidyDueDate",
    installmentsField: "governmentSubsidyInstallments",
  },
  {
    sourceType: "fgts",
    label: "FGTS",
    amountField: "fgtsAmount",
    dueDateField: "fgtsDueDate",
    installmentsField: "fgtsInstallments",
  },
  {
    sourceType: "financing",
    label: "Financiamento",
    amountField: "financingAmount",
    dueDateField: "financingDueDate",
    installmentsField: "financingInstallments",
  },
]

const receivableInstallmentStatusLabel = {
  OPEN: "Aberta",
  PAID: "Paga",
  PARTIALLY_PAID: "Parcial",
  OVERDUE: "Vencida",
  CANCELED: "Cancelada",
}

// O ERP responde com os status em maiúsculas e em inglês (ACTIVE, OPEN...).
// Sem estes mapas eles chegavam crus à tela.
const erpContractStatusLabel = {
  DRAFT: "Rascunho",
  ACTIVE: "Ativo",
  SUSPENDED: "Suspenso",
  FINISHED: "Encerrado",
  CANCELED: "Cancelado",
  CANCELLED: "Cancelado",
}

const erpReceivableStatusLabel = {
  OPEN: "Em aberto",
  PARTIALLY_PAID: "Parcialmente pago",
  PAID: "Pago",
  OVERDUE: "Vencido",
  CANCELED: "Cancelado",
  CANCELLED: "Cancelado",
}

function translateErpStatus(labels, value, fallback = "") {
  if (!value) {
    return fallback
  }

  return labels[String(value).toUpperCase()] ?? value
}

const inspectionStatusLabel = {
  pending: "Pendente",
  compliant: "Procedente",
  non_compliant: "Improcedente",
}

const occurrenceStatusLabel = {
  open: "Aberta",
  resolved: "Resolvida",
  cancelled: "Cancelada",
}

const defaultMeasurementItemForm = {
  serviceTemplateId: "",
  description: "",
  amount: "",
  productDescription: "",
  startDate: "",
  endDate: "",
  inspectorPersonId: "",
}

const defaultInspectionForm = {
  description: "",
  verificationMethod: "",
  startDate: "",
  endDate: "",
}

const defaultOccurrenceForm = {
  problem: "",
  solution: "",
}

const defaultMeasurementForm = {
  code: "",
  unitId: "",
  schedulePhaseId: "",
  sequenceNumber: "",
  measurementType: "",
  competenceDate: "",
  description: "",
  grossAmount: "",
  retentionsAmount: "0",
  netAmount: "",
  measuredAmount: "",
  dueDate: "",
  supplierPersonId: "",
  documentType: "",
  documentNumber: "",
}

const defaultMeasurementRejectForm = {
  reason: "",
}

const defaultProcurementForm = {
  code: "",
  title: "",
  description: "",
  estimatedAmount: "",
  neededByDate: "",
  supplierPersonId: "",
}

const defaultProcurementRejectForm = {
  reason: "",
}

function toFormProject(project) {
  return {
    code: project.code ?? "",
    name: project.name ?? "",
    description: project.description ?? "",
    status: project.status ?? "draft",
    projectType: project.projectType ?? "residential_vertical",
    customerPersonId: project.customerPersonId ?? "",
    cnpjSpe: project.cnpjSpe ?? "",
    startDate: project.startDate ? String(project.startDate).slice(0, 10) : "",
    expectedEndDate: project.expectedEndDate ? String(project.expectedEndDate).slice(0, 10) : "",
    actualEndDate: project.actualEndDate ? String(project.actualEndDate).slice(0, 10) : "",
    addressStreet: project.address?.street ?? "",
    addressNumber: project.address?.number ?? "",
    addressDistrict: project.address?.district ?? "",
    addressCity: project.address?.city ?? "",
    addressState: project.address?.state ?? "",
    addressZipCode: maskZip(project.address?.zip_code ?? ""),
    receiptTemplateId: project.receiptTemplateId ?? "",
    commissionReceiptTemplateId: project.commissionReceiptTemplateId ?? "",
  }
}

function toFormBlock(block) {
  return {
    code: block.code ?? "",
    name: block.name ?? "",
    status: block.status ?? "active",
    floorsCount: block.floorsCount === null || block.floorsCount === undefined ? "" : String(block.floorsCount),
  }
}

function toFormSchedulePhase(phase) {
  return {
    name: phase.name ?? "",
    sequenceOrder: String(phase.sequenceOrder ?? ""),
    status: phase.status ?? "planned",
    plannedStartDate: phase.plannedStartDate ? String(phase.plannedStartDate).slice(0, 10) : "",
    plannedEndDate: phase.plannedEndDate ? String(phase.plannedEndDate).slice(0, 10) : "",
    actualStartDate: phase.actualStartDate ? String(phase.actualStartDate).slice(0, 10) : "",
    actualEndDate: phase.actualEndDate ? String(phase.actualEndDate).slice(0, 10) : "",
    progressPercent:
      phase.progressPercent === null || phase.progressPercent === undefined ? "0" : String(phase.progressPercent),
  }
}

function toFormUnit(unit) {
  return {
    code: unit.code ?? "",
    description: unit.description ?? "",
    quantity: "1",
    unitType: unit.unitType ?? "",
    typology: unit.typology ?? "",
    blockId: unit.blockId ?? "",
    floor: unit.floor ?? "",
    privateArea: unit.privateArea === null || unit.privateArea === undefined ? "" : String(unit.privateArea),
    totalArea: unit.totalArea === null || unit.totalArea === undefined ? "" : String(unit.totalArea),
    salePrice: formatCurrencyFromNumber(unit.salePrice),
    status: unit.status ?? "available",
  }
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function getNextUnitSequence(unitDescription, currentUnits) {
  const escapedDescription = escapeRegExp(unitDescription)
  const sequencePattern = new RegExp(`^${escapedDescription}\\s*-\\s*(\\d+)$`, "i")
  const highestSequence = currentUnits.reduce((highestValue, unit) => {
    const unitLabel = unit.description || unit.code || ""
    const match = String(unitLabel).match(sequencePattern)
    if (!match) {
      return highestValue
    }

    const sequenceNumber = Number(match[1])
    return Number.isInteger(sequenceNumber) ? Math.max(highestValue, sequenceNumber) : highestValue
  }, 0)

  return highestSequence + 1
}

function buildUnitCreateForms(formUnit, currentUnits) {
  const unitQuantity = Number(formUnit.quantity)
  const unitDescription = String(formUnit.description || DEFAULT_UNIT_DESCRIPTION).trim()
  const firstSequence = getNextUnitSequence(unitDescription, currentUnits)

  return Array.from({ length: unitQuantity }, (_, index) => {
    const generatedDescription = `${unitDescription} - ${firstSequence + index}`

    return {
      ...formUnit,
      code: generatedDescription,
      description: generatedDescription,
    }
  })
}

function toApiProject(formProject) {
  return {
    code: formProject.code,
    name: formProject.name,
    description: formProject.description,
    status: formProject.status,
    projectType: formProject.projectType,
    customerPersonId: formProject.customerPersonId,
    cnpjSpe: formProject.cnpjSpe,
    startDate: formProject.startDate,
    expectedEndDate: formProject.expectedEndDate,
    actualEndDate: formProject.actualEndDate,
    address: {
      street: formProject.addressStreet,
      number: formProject.addressNumber,
      district: formProject.addressDistrict,
      city: formProject.addressCity,
      state: formProject.addressState,
      zip_code: normalizeZip(formProject.addressZipCode),
    },
    receiptTemplateId: formProject.receiptTemplateId,
    commissionReceiptTemplateId: formProject.commissionReceiptTemplateId,
  }
}

function toFormProcurement(procurementRequest) {
  return {
    code: procurementRequest.code ?? "",
    title: procurementRequest.title ?? "",
    description: procurementRequest.description ?? "",
    estimatedAmount:
      procurementRequest.estimatedAmount === null || procurementRequest.estimatedAmount === undefined
        ? ""
        : String(procurementRequest.estimatedAmount),
    neededByDate: procurementRequest.neededByDate ? String(procurementRequest.neededByDate).slice(0, 10) : "",
    supplierPersonId: procurementRequest.supplierPersonId ?? "",
  }
}

function requiredProjectFieldError(formProject) {
  if (!String(formProject.code ?? "").trim()) {
    return "Informe o código da obra."
  }

  if (!String(formProject.name ?? "").trim()) {
    return "Informe o nome da obra."
  }

  if (!formProject.status) {
    return "Selecione um status para a obra."
  }

  if (!formProject.projectType) {
    return "Selecione o tipo da obra."
  }

  return null
}

function requiredBlockFieldError(formBlock) {
  if (!String(formBlock.code ?? "").trim()) {
    return "Informe o código do bloco."
  }

  if (!String(formBlock.name ?? "").trim()) {
    return "Informe o nome do bloco."
  }

  if (!formBlock.status) {
    return "Selecione o status do bloco."
  }

  return null
}

function requiredScheduleFieldError(formPhase) {
  if (!String(formPhase.name ?? "").trim()) {
    return "Informe o nome da fase."
  }

  const sequenceOrder = Number(formPhase.sequenceOrder)
  if (!Number.isInteger(sequenceOrder) || sequenceOrder <= 0) {
    return "Informe uma ordem válida para a fase."
  }

  const progress = Number(formPhase.progressPercent)
  if (Number.isNaN(progress) || progress < 0 || progress > 100) {
    return "O progresso deve estar entre 0 e 100."
  }

  return null
}

function requiredUnitFieldError(formUnit, mode) {
  if (mode === "create") {
    const unitQuantity = Number(formUnit.quantity)
    if (!Number.isInteger(unitQuantity) || unitQuantity < 1 || unitQuantity > MAX_UNIT_BATCH_SIZE) {
      return `Informe uma quantidade entre 1 e ${MAX_UNIT_BATCH_SIZE}.`
    }

    if (!String(formUnit.description ?? "").trim()) {
      return "Informe a descrição base das unidades."
    }
  } else if (!String(formUnit.code ?? "").trim()) {
    return "Informe o código da unidade."
  }

  if (!String(formUnit.unitType ?? "").trim()) {
    return "Informe o tipo da unidade."
  }

  if (!formUnit.status) {
    return "Selecione o status da unidade."
  }

  return null
}

function requiredReserveFieldError(formReserve) {
  if (!String(formReserve.buyerPersonId ?? "").trim()) {
    return "Informe a pessoa compradora para reservar."
  }

  return null
}

function parseCurrencyFormValue(value) {
  if (value === "" || value === null || value === undefined) {
    return 0
  }

  const valueText = String(value).trim()
  const normalizedValue = valueText.includes(",")
    ? valueText.replace(/\s+/g, "").replace(/\./g, "").replace(",", ".").replace(/[^0-9.-]/g, "")
    : valueText.replace(/[^0-9.-]/g, "")
  const parsedValue = Number(normalizedValue)
  return Number.isNaN(parsedValue) ? 0 : parsedValue
}

let saleDocumentationKeySequence = 0

function nextSaleDocumentationKey() {
  saleDocumentationKeySequence += 1
  return `doc-${saleDocumentationKeySequence}`
}

function makeSaleDocumentationRow() {
  return {
    key: nextSaleDocumentationKey(),
    documentationTypeId: "",
    documentationTypeName: "",
    amount: "",
  }
}

// Mesma normalização do backend (colapsa espaços e sobe a caixa): é ela que
// decide se duas linhas são o mesmo tipo.
function normalizeDocumentationName(value) {
  return String(value ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .join(" ")
    .toUpperCase()
}

function buildSaleDocumentationsFromForm(formSale) {
  return (formSale.documentations ?? [])
    .map((documentation) => ({
      documentationTypeId: String(documentation.documentationTypeId ?? "").trim(),
      name: String(documentation.documentationTypeName ?? "").trim(),
      amountValue: parseCurrencyFormValue(documentation.amount),
    }))
    .filter((documentation) => documentation.amountValue > 0)
}

function sumSaleDocumentations(documentations) {
  return documentations.reduce((total, documentation) => total + documentation.amountValue, 0)
}

function buildSalePaymentSourcesFromForm(formSale) {
  return salePaymentSourceDefinitions
    .map((definition) => ({
      sourceType: definition.sourceType,
      amount: formSale[definition.amountField],
      amountValue: parseCurrencyFormValue(formSale[definition.amountField]),
      dueDate: formSale[definition.dueDateField],
      installments: formSale[definition.installmentsField] || "1",
      label: definition.label,
    }))
    .filter((paymentSource) => paymentSource.amountValue > 0)
}

function requiredSaleFieldError(formSale) {
  if (!String(formSale.buyerPersonId ?? "").trim()) {
    return "Informe a pessoa compradora para confirmar a venda."
  }

  const secondaryBuyerPersonId = String(formSale.secondaryBuyerPersonId ?? "").trim()
  if (secondaryBuyerPersonId && secondaryBuyerPersonId === String(formSale.buyerPersonId ?? "").trim()) {
    return "O comprador secundário deve ser diferente do comprador principal."
  }

  const grossSalePrice = parseCurrencyFormValue(formSale.salePrice)
  const discountAmount = parseCurrencyFormValue(formSale.discountAmount)
  if (discountAmount < 0) {
    return "O desconto não pode ser negativo."
  }

  if (grossSalePrice > 0 && discountAmount >= grossSalePrice) {
    return "O desconto deve ser menor que o preço da venda."
  }

  const seenDocumentationKeys = new Set()
  let documentationTotal = 0
  for (const documentationRow of formSale.documentations ?? []) {
    const rowTypeName = String(documentationRow.documentationTypeName ?? "").trim()
    const rowTypeId = String(documentationRow.documentationTypeId ?? "").trim()
    const rowAmount = parseCurrencyFormValue(documentationRow.amount)

    // Gravar é replace-all: uma linha com tipo e sem valor sairia da lista em
    // silêncio e apagaria a documentação que já estava na venda.
    if ((rowTypeId || rowTypeName) && rowAmount <= 0) {
      return `Informe o valor da documentação '${rowTypeName || "selecionada"}' ou remova a linha.`
    }

    if (rowAmount <= 0) {
      continue
    }

    if (!rowTypeId && !rowTypeName) {
      return "Informe o tipo da documentação."
    }

    const documentationKey = rowTypeId || normalizeDocumentationName(rowTypeName)
    if (seenDocumentationKeys.has(documentationKey)) {
      return `A documentação '${rowTypeName || "informada"}' está informada mais de uma vez.`
    }

    seenDocumentationKeys.add(documentationKey)
    documentationTotal += rowAmount
  }

  const paymentSources = buildSalePaymentSourcesFromForm(formSale)
  if (paymentSources.length) {
    for (const paymentSource of paymentSources) {
      if (!String(paymentSource.dueDate ?? "").trim()) {
        return `Informe o vencimento de ${paymentSource.label}.`
      }

      const sourceInstallments = Number(paymentSource.installments)
      if (!Number.isInteger(sourceInstallments) || sourceInstallments <= 0 || sourceInstallments > 120) {
        return `Parcelas de ${paymentSource.label} devem estar entre 1 e 120.`
      }
    }

    const sourcesTotal = paymentSources.reduce((total, paymentSource) => total + paymentSource.amountValue, 0)
    // O que sobra do preço é o saldo, e o saldo é o que vira parcela. Só é erro
    // quando as fontes informadas passam do preço, nunca quando sobra.
    const balance = grossSalePrice + documentationTotal - discountAmount - sourcesTotal
    if (grossSalePrice > 0 && balance < -0.01) {
      return `A composição somada ao desconto excede o preço da venda mais a documentação em ${formatMoney(Math.abs(balance))}.`
    }

    const downPaymentTotal = paymentSources
      .filter((paymentSource) => SALE_INSTALLMENT_SOURCE_TYPES.includes(paymentSource.sourceType))
      .reduce((total, paymentSource) => total + paymentSource.amountValue, 0)
    if (grossSalePrice > 0 && downPaymentTotal + Math.max(balance, 0) <= 0.01) {
      return "Não sobrou nada para cobrar do comprador: entrada, desconto e liberações do banco já cobrem o preço mais a documentação."
    }

    for (const paymentSource of paymentSources) {
      if (
        !SALE_INSTALLMENT_SOURCE_TYPES.includes(paymentSource.sourceType) &&
        Number(paymentSource.installments) > 1
      ) {
        return `${paymentSource.label} depende de liberação do banco e não pode ser parcelado.`
      }
    }

    return null
  }

  const installments = Number(formSale.installments)
  if (!Number.isInteger(installments) || installments <= 0 || installments > 120) {
    return "Parcelas devem estar entre 1 e 120."
  }

  if (!String(formSale.firstDueDate ?? "").trim()) {
    return "Informe a data do primeiro vencimento."
  }

  return null
}

function requiredMeasurementFieldError(formMeasurement) {
  if (!String(formMeasurement.code ?? "").trim()) {
    return "Informe o código da medição."
  }

  if (!String(formMeasurement.unitId ?? "").trim()) {
    return "Informe a unidade da medição."
  }

  if (!String(formMeasurement.schedulePhaseId ?? "").trim()) {
    return "Informe a etapa da medição."
  }

  if (!String(formMeasurement.dueDate ?? "").trim()) {
    return "Informe a data de vencimento."
  }

  const grossAmount = Number(formMeasurement.grossAmount || 0)
  if (Number.isNaN(grossAmount) || grossAmount <= 0) {
    return "Informe o valor bruto da medição."
  }

  return null
}

function requiredProcurementFieldError(formProcurement) {
  if (!String(formProcurement.title ?? "").trim()) {
    return "Informe o título da requisição."
  }

  const estimatedAmount = Number(formProcurement.estimatedAmount || 0)
  if (Number.isNaN(estimatedAmount) || estimatedAmount <= 0) {
    return "Informe o valor estimado da requisição."
  }

  return null
}

export default function ConstructionApp({ bridge: providedBridge } = {}) {
  const bridge = useMemo(() => providedBridge ?? resolveConstructionBridge(), [providedBridge])
  const [viewMode, setViewMode] = useState("projects")
  const [projectDetailTab, setProjectDetailTab] = useState("overview")
  const [activeProjectId, setActiveProjectId] = useState(null)
  const [activeUnitId, setActiveUnitId] = useState(null)
  const [unitDetailTab, setUnitDetailTab] = useState("summary")

  const [filters, setFilters] = useState(defaultFilters)
  const [projects, setProjects] = useState([])
  const [totalProjects, setTotalProjects] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [isProjectModalOpen, setIsProjectModalOpen] = useState(false)
  const [projectModalMode, setProjectModalMode] = useState("create")
  const [editingProjectId, setEditingProjectId] = useState(null)
  const [projectForm, setProjectForm] = useState(defaultProjectForm)
  const [submittingProject, setSubmittingProject] = useState(false)
  const [projectZipLookup, setProjectZipLookup] = useState({ loading: false, error: null })

  const [blocks, setBlocks] = useState([])
  const [loadingBlocks, setLoadingBlocks] = useState(false)
  const [blockError, setBlockError] = useState(null)
  const [isBlockModalOpen, setIsBlockModalOpen] = useState(false)
  const [blockModalMode, setBlockModalMode] = useState("create")
  const [editingBlockId, setEditingBlockId] = useState(null)
  const [blockForm, setBlockForm] = useState(defaultBlockForm)
  const [submittingBlock, setSubmittingBlock] = useState(false)

  const [schedulePhases, setSchedulePhases] = useState([])
  const [loadingSchedule, setLoadingSchedule] = useState(false)
  const [scheduleError, setScheduleError] = useState(null)
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false)
  const [scheduleModalMode, setScheduleModalMode] = useState("create")
  const [editingPhaseId, setEditingPhaseId] = useState(null)
  const [schedulePhaseForm, setSchedulePhaseForm] = useState(defaultSchedulePhaseForm)
  const [submittingSchedule, setSubmittingSchedule] = useState(false)

  const [units, setUnits] = useState([])
  const [loadingUnits, setLoadingUnits] = useState(false)
  const [unitError, setUnitError] = useState(null)
  const [isUnitModalOpen, setIsUnitModalOpen] = useState(false)
  const [unitModalMode, setUnitModalMode] = useState("create")
  const [editingUnitId, setEditingUnitId] = useState(null)
  const [unitForm, setUnitForm] = useState(defaultUnitForm)
  const [submittingUnit, setSubmittingUnit] = useState(false)

  const [isReserveModalOpen, setIsReserveModalOpen] = useState(false)
  const [reserveUnitForm, setReserveUnitForm] = useState(defaultReserveUnitForm)
  const [reserveTargetUnit, setReserveTargetUnit] = useState(null)
  const [submittingReserve, setSubmittingReserve] = useState(false)

  const [isSaleModalOpen, setIsSaleModalOpen] = useState(false)
  const [itemsTargetMeasurement, setItemsTargetMeasurement] = useState(null)
  const [measurementItems, setMeasurementItems] = useState([])
  const [loadingMeasurementItems, setLoadingMeasurementItems] = useState(false)
  const [measurementItemsError, setMeasurementItemsError] = useState(null)
  const [savingMeasurementItem, setSavingMeasurementItem] = useState(false)
  const [serviceTemplates, setServiceTemplates] = useState([])
  const [loadingServiceTemplates, setLoadingServiceTemplates] = useState(false)
  const [importingServiceTemplates, setImportingServiceTemplates] = useState(false)
  const [projectSummary, setProjectSummary] = useState(null)
  const [loadingProjectSummary, setLoadingProjectSummary] = useState(false)
  const [projectSummaryError, setProjectSummaryError] = useState(null)
  const [unitPaymentPlan, setUnitPaymentPlan] = useState(null)
  const [loadingUnitPaymentPlan, setLoadingUnitPaymentPlan] = useState(false)
  const [unitPaymentPlanError, setUnitPaymentPlanError] = useState(null)
  const [saleUnitForm, setSaleUnitForm] = useState(defaultSaleUnitForm)
  const [saleTargetUnit, setSaleTargetUnit] = useState(null)
  const [documentationTypes, setDocumentationTypes] = useState([])
  const [loadingDocumentationTypes, setLoadingDocumentationTypes] = useState(false)
  const [submittingSale, setSubmittingSale] = useState(false)
  const [editingInstallment, setEditingInstallment] = useState(null)
  const [editInstallmentForm, setEditInstallmentForm] = useState(defaultEditInstallmentForm)
  const [savingInstallment, setSavingInstallment] = useState(false)
  const [isCommissionModalOpen, setIsCommissionModalOpen] = useState(false)
  const [commissionForm, setCommissionForm] = useState(defaultCommissionForm)
  const [submittingCommission, setSubmittingCommission] = useState(false)
  const [isAdjustmentModalOpen, setIsAdjustmentModalOpen] = useState(false)
  const [adjustmentForm, setAdjustmentForm] = useState(defaultAdjustmentForm)
  const [submittingAdjustment, setSubmittingAdjustment] = useState(false)
  const [receiptTemplates, setReceiptTemplates] = useState([])
  const [receiptTemplatesError, setReceiptTemplatesError] = useState(null)
  const [payingInstallment, setPayingInstallment] = useState(null)
  const [payInstallmentForm, setPayInstallmentForm] = useState(defaultPayInstallmentForm)
  const [submittingInstallmentPayment, setSubmittingInstallmentPayment] = useState(false)
  const [isCreateInstallmentOpen, setIsCreateInstallmentOpen] = useState(false)
  const [createInstallmentForm, setCreateInstallmentForm] = useState(defaultCreateInstallmentForm)
  const [submittingCreateInstallment, setSubmittingCreateInstallment] = useState(false)
  const [deletingAdjustment, setDeletingAdjustment] = useState(null)
  const [deleteAdjustmentReason, setDeleteAdjustmentReason] = useState("")
  const [submittingAdjustmentDelete, setSubmittingAdjustmentDelete] = useState(false)

  const [measurements, setMeasurements] = useState([])
  const [loadingMeasurements, setLoadingMeasurements] = useState(false)
  const [measurementError, setMeasurementError] = useState(null)
  const [isMeasurementModalOpen, setIsMeasurementModalOpen] = useState(false)
  const [measurementModalMode, setMeasurementModalMode] = useState("create")
  const [editingMeasurementId, setEditingMeasurementId] = useState(null)
  const [measurementForm, setMeasurementForm] = useState(defaultMeasurementForm)
  const [submittingMeasurement, setSubmittingMeasurement] = useState(false)
  const [rejectMeasurementTarget, setRejectMeasurementTarget] = useState(null)
  const [rejectMeasurementForm, setRejectMeasurementForm] = useState(defaultMeasurementRejectForm)
  const [submittingMeasurementReject, setSubmittingMeasurementReject] = useState(false)

  const [procurementRequests, setProcurementRequests] = useState([])
  const [loadingProcurement, setLoadingProcurement] = useState(false)
  const [procurementError, setProcurementError] = useState(null)
  const [isProcurementModalOpen, setIsProcurementModalOpen] = useState(false)
  const [procurementModalMode, setProcurementModalMode] = useState("create")
  const [editingProcurementId, setEditingProcurementId] = useState(null)
  const [procurementForm, setProcurementForm] = useState(defaultProcurementForm)
  const [submittingProcurement, setSubmittingProcurement] = useState(false)
  const [rejectProcurementTarget, setRejectProcurementTarget] = useState(null)
  const [rejectProcurementForm, setRejectProcurementForm] = useState(defaultProcurementRejectForm)
  const [submittingProcurementReject, setSubmittingProcurementReject] = useState(false)

  const [personLookupQuery, setPersonLookupQuery] = useState("")
  const [personSummaries, setPersonSummaries] = useState([])
  const [loadingPersonSummaries, setLoadingPersonSummaries] = useState(false)
  const [personLookupError, setPersonLookupError] = useState(null)

  const loadProjects = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await listConstructionProjects({
        bridge,
        search: filters.search,
      })
      setProjects(result.items)
      setTotalProjects(result.total)
    } catch (requestError) {
      setError(requestError?.message ?? "Não foi possível carregar as obras.")
    } finally {
      setLoading(false)
    }
  }, [bridge, filters.search])

  useEffect(() => {
    void loadProjects()
  }, [loadProjects])

  useEffect(() => {
    if (!projects.length) {
      setActiveProjectId(null)
      setActiveUnitId(null)
      setViewMode("projects")
      return
    }

    const projectExists = activeProjectId && projects.some((project) => project.id === activeProjectId)
    if (activeProjectId && !projectExists) {
      setActiveProjectId(null)
      setActiveUnitId(null)
      setViewMode("projects")
    }
  }, [activeProjectId, projects])

  useEffect(() => {
    if (!activeUnitId) {
      return
    }

    const unitExists = units.some((unit) => unit.id === activeUnitId)
    if (!unitExists) {
      setActiveUnitId(null)
      setUnitDetailTab("summary")
    }
  }, [activeUnitId, units])

  const visibleProjects = useMemo(() => {
    const searchTerm = filters.search.trim().toLowerCase()

    return projects.filter((project) => {
      const matchesSearch = searchTerm
        ? [project.code, project.name, project.cnpjSpe].some((value) =>
            String(value ?? "").toLowerCase().includes(searchTerm)
          )
        : true
      const matchesStatus = filters.status ? project.status === filters.status : true
      const startDate = project.startDate ? String(project.startDate).slice(0, 10) : ""
      const matchesStartDate = filters.startDate ? startDate >= filters.startDate : true
      const matchesEndDate = filters.endDate ? startDate <= filters.endDate : true

      return matchesSearch && matchesStatus && matchesStartDate && matchesEndDate
    })
  }, [filters, projects])

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === activeProjectId) ?? null,
    [activeProjectId, projects]
  )

  const selectedUnit = useMemo(
    () => units.find((unit) => unit.id === activeUnitId) ?? null,
    [activeUnitId, units]
  )

  const selectedUnitMeasurements = useMemo(
    () => measurements.filter((measurement) => measurement.unitId === activeUnitId),
    [activeUnitId, measurements]
  )

  const summaryItems = useMemo(() => {
    const activeProjects = projects.filter((project) => project.status === "active").length
    const pendingCostCenters = projects.filter((project) => !project.analyticCostCenterId).length

    return [
      {
        label: "Empreendimentos",
        value: totalProjects,
        hint: `${visibleProjects.length} na lista`,
        icon: Building2,
        tone: "muted",
      },
      {
        label: "Ativas",
        value: activeProjects,
        hint: "obras em andamento",
        icon: CheckCircle,
        tone: "success",
      },
      {
        label: "Centros pendentes",
        value: pendingCostCenters,
        hint: "sem vínculo analítico",
        icon: Clock,
        tone: "warning",
      },
      {
        label: "Filtradas",
        value: visibleProjects.length,
        hint: "obras na lista atual",
        icon: Layers3,
        tone: "muted",
      },
    ]
  }, [projects, totalProjects, visibleProjects.length])

  const hasActiveFilters = Object.values(filters).some(Boolean)

  const scheduleProgress = useMemo(() => {
    if (!schedulePhases.length) {
      return 0
    }

    const totalProgress = schedulePhases.reduce((sum, phase) => sum + Number(phase.progressPercent ?? 0), 0)
    return Number((totalProgress / schedulePhases.length).toFixed(1))
  }, [schedulePhases])

  const loadBlocks = useCallback(async () => {
    if (!activeProjectId) {
      setBlocks([])
      return
    }

    setLoadingBlocks(true)
    setBlockError(null)
    try {
      const result = await listConstructionBlocks({
        bridge,
        projectId: activeProjectId,
      })
      setBlocks(result.items)
    } catch (requestError) {
      setBlockError(requestError?.message ?? "Não foi possível carregar os blocos.")
    } finally {
      setLoadingBlocks(false)
    }
  }, [activeProjectId, bridge])

  const loadSchedulePhases = useCallback(async () => {
    if (!activeProjectId) {
      setSchedulePhases([])
      return
    }

    setLoadingSchedule(true)
    setScheduleError(null)
    try {
      const result = await listConstructionSchedulePhases({
        bridge,
        projectId: activeProjectId,
      })
      setSchedulePhases(result.items)
    } catch (requestError) {
      setScheduleError(requestError?.message ?? "Não foi possível carregar o cronograma.")
    } finally {
      setLoadingSchedule(false)
    }
  }, [activeProjectId, bridge])

  const loadUnits = useCallback(async () => {
    if (!activeProjectId) {
      setUnits([])
      return
    }

    setLoadingUnits(true)
    setUnitError(null)
    try {
      const result = await listConstructionUnits({
        bridge,
        projectId: activeProjectId,
      })
      setUnits(result.items)
    } catch (requestError) {
      setUnitError(requestError?.message ?? "Não foi possível carregar as unidades.")
    } finally {
      setLoadingUnits(false)
    }
  }, [activeProjectId, bridge])

  const loadMeasurements = useCallback(async () => {
    if (!activeProjectId) {
      setMeasurements([])
      return
    }

    setLoadingMeasurements(true)
    setMeasurementError(null)
    try {
      const result = await listConstructionMeasurements({
        bridge,
        projectId: activeProjectId,
      })
      setMeasurements(result.items)
    } catch (requestError) {
      setMeasurementError(requestError?.message ?? "Não foi possível carregar as medições.")
    } finally {
      setLoadingMeasurements(false)
    }
  }, [activeProjectId, bridge])

  const loadProjectSummary = useCallback(
    async (projectId) => {
      if (!projectId) {
        return
      }

      setLoadingProjectSummary(true)
      setProjectSummaryError(null)
      try {
        setProjectSummary(await getConstructionProjectSummary({ bridge, projectId }))
      } catch (requestError) {
        setProjectSummary(null)
        setProjectSummaryError(requestError?.message ?? "Não foi possível carregar o resumo da obra.")
      } finally {
        setLoadingProjectSummary(false)
      }
    },
    [bridge]
  )

  const loadProcurementRequests = useCallback(async () => {
    if (!activeProjectId) {
      setProcurementRequests([])
      return
    }

    setLoadingProcurement(true)
    setProcurementError(null)
    try {
      const result = await listConstructionProcurementRequests({
        bridge,
        projectId: activeProjectId,
      })
      setProcurementRequests(result.items)
    } catch (requestError) {
      setProcurementError(requestError?.message ?? "Não foi possível carregar as requisições.")
    } finally {
      setLoadingProcurement(false)
    }
  }, [activeProjectId, bridge])

  // O catálogo inteiro é carregado uma vez por abertura do modal de venda: são
  // poucos tipos por empresa, e o combobox filtra localmente. Buscar por
  // combobox faria um GET por linha de documentação.
  const loadDocumentationTypes = useCallback(async () => {
    setLoadingDocumentationTypes(true)
    try {
      const result = await listConstructionDocumentationTypes({ bridge })
      setDocumentationTypes(result.items)
    } catch {
      setDocumentationTypes([])
    } finally {
      setLoadingDocumentationTypes(false)
    }
  }, [bridge])

  const loadPersonSummaries = useCallback(
    async (search = "") => {
      setLoadingPersonSummaries(true)
      setPersonLookupError(null)
      try {
        const result = await listConstructionPersonSummaries({
          bridge,
          search,
          page: 1,
          pageSize: 50,
        })
        setPersonSummaries(result.items)
      } catch (requestError) {
        setPersonLookupError(requestError?.message ?? "Não foi possível carregar o cadastro de pessoas.")
      } finally {
        setLoadingPersonSummaries(false)
      }
    },
    [bridge]
  )

  useEffect(() => {
    if (viewMode !== "projectDetail" || projectDetailTab !== "blocks") {
      return
    }

    void loadBlocks()
  }, [projectDetailTab, loadBlocks, viewMode])

  useEffect(() => {
    if (viewMode !== "projectDetail" || projectDetailTab !== "schedule") {
      return
    }

    void loadSchedulePhases()
  }, [projectDetailTab, loadSchedulePhases, viewMode])

  useEffect(() => {
    if (viewMode !== "projectDetail" || projectDetailTab !== "units") {
      return
    }

    void loadUnits()
    void loadBlocks()
    void loadSchedulePhases()
    void loadMeasurements()
  }, [projectDetailTab, loadBlocks, loadMeasurements, loadSchedulePhases, loadUnits, viewMode])

  useEffect(() => {
    if (viewMode !== "projectDetail" || projectDetailTab !== "procurement") {
      return
    }

    void loadProcurementRequests()
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }
  }, [loadPersonSummaries, loadProcurementRequests, personSummaries.length, projectDetailTab, viewMode])

  useEffect(() => {
    if (viewMode !== "projectDetail" || projectDetailTab !== "units") {
      return
    }

    if (!personSummaries.length) {
      void loadPersonSummaries()
    }
  }, [loadPersonSummaries, personSummaries.length, projectDetailTab, viewMode])

  useEffect(() => {
    if (viewMode !== "projectDetail" || !["overview", "reports", "integrations"].includes(projectDetailTab)) {
      return
    }

    if (!activeProjectId) {
      return
    }

    void Promise.all([
      loadBlocks(),
      loadSchedulePhases(),
      loadUnits(),
      loadMeasurements(),
      loadProcurementRequests(),
      loadProjectSummary(activeProjectId),
    ])
  }, [
    activeProjectId,
    loadBlocks,
    loadMeasurements,
    loadProjectSummary,
    loadProcurementRequests,
    loadSchedulePhases,
    loadUnits,
    projectDetailTab,
    viewMode,
  ])

  const handleFilterChange = (field, value) => {
    setFilters((currentFilters) => ({ ...currentFilters, [field]: value }))
  }

  const handlePersonLookupQueryChange = (value) => {
    setPersonLookupQuery(value)
  }

  const handlePersonLookupSearch = async () => {
    await loadPersonSummaries(personLookupQuery)
  }

  const clearFilters = () => setFilters(defaultFilters)

  const openProjectDetail = (project) => {
    setActiveProjectId(project.id)
    setProjectDetailTab("overview")
    setActiveUnitId(null)
    setUnitDetailTab("summary")
    setViewMode("projectDetail")
  }

  const closeProjectDetail = () => {
    setProjectDetailTab("overview")
    setActiveUnitId(null)
    setUnitDetailTab("summary")
    setViewMode("projects")
  }

  const openUnitDetail = (unit) => {
    // A aba de sinal mostra o corretor pelo nome, e o nome vem daqui: sem as
    // pessoas carregadas a tabela exibiria o UUID do favorecido.
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    setActiveUnitId(unit.id)
    setUnitDetailTab("summary")
    setUnitPaymentPlan(null)
    setUnitPaymentPlanError(null)
    void loadUnitPaymentPlan(unit.id)
  }

  const closeUnitDetail = () => {
    setActiveUnitId(null)
    setUnitDetailTab("summary")
    setUnitPaymentPlan(null)
    setUnitPaymentPlanError(null)
  }

  const reloadProjectDetail = async () => {
    await Promise.all([
      loadProjects(),
      loadBlocks(),
      loadSchedulePhases(),
      loadUnits(),
      loadMeasurements(),
      loadProcurementRequests(),
    ])
  }

  const openCreateProject = () => {
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    void loadReceiptTemplates()
    setProjectModalMode("create")
    setEditingProjectId(null)
    setProjectForm(defaultProjectForm)
    setProjectZipLookup({ loading: false, error: null })
    setIsProjectModalOpen(true)
  }

  const openEditProject = (project) => {
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    void loadReceiptTemplates()
    setProjectModalMode("edit")
    setEditingProjectId(project.id)
    setProjectForm(toFormProject(project))
    setProjectZipLookup({ loading: false, error: null })
    setIsProjectModalOpen(true)
  }

  const closeProjectModal = () => {
    if (submittingProject) {
      return
    }

    setIsProjectModalOpen(false)
    setEditingProjectId(null)
    setProjectForm(defaultProjectForm)
    setProjectZipLookup({ loading: false, error: null })
  }

  const handleProjectFieldChange = (field, value) => {
    const nextValue = field === "addressZipCode" ? maskZip(value) : value
    setProjectForm((currentProjectForm) => ({ ...currentProjectForm, [field]: nextValue }))

    if (field === "addressZipCode") {
      setProjectZipLookup({ loading: false, error: null })
    }
  }

  const handleProjectZipLookup = async () => {
    const normalizedZip = normalizeZip(projectForm.addressZipCode)
    if (!normalizedZip) {
      setProjectZipLookup({ loading: false, error: null })
      return
    }

    if (normalizedZip.length !== 8) {
      setProjectZipLookup({ loading: false, error: "Informe um CEP válido com 8 dígitos." })
      return
    }

    setProjectZipLookup({ loading: true, error: null })
    try {
      const address = await fetchConstructionAddressByZip({ bridge, zipCode: normalizedZip })
      setProjectForm((currentProjectForm) => ({
        ...currentProjectForm,
        addressZipCode: maskZip(address.zipCode || normalizedZip),
        addressStreet: address.street || currentProjectForm.addressStreet,
        addressDistrict: address.district || currentProjectForm.addressDistrict,
        addressCity: address.city || currentProjectForm.addressCity,
        addressState: address.state || currentProjectForm.addressState,
      }))
      setProjectZipLookup({ loading: false, error: null })
    } catch (requestError) {
      setProjectZipLookup({
        loading: false,
        error: requestError?.message ?? "Não foi possível buscar o CEP.",
      })
    }
  }

  const handleProjectSubmit = async (event) => {
    event.preventDefault()

    const validationError = requiredProjectFieldError(projectForm)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    setSubmittingProject(true)
    try {
      const projectData = toApiProject(projectForm)
      if (projectModalMode === "create") {
        const createdProject = await createConstructionProject({ bridge, projectData })
        setProjects((currentProjects) => [
          createdProject,
          ...currentProjects.filter((project) => project.id !== createdProject.id),
        ])
        setActiveProjectId(createdProject.id)
        setProjectDetailTab("overview")
        setViewMode("projectDetail")
        bridge?.feedback?.success?.("Obra criada com sucesso.")
      } else if (editingProjectId) {
        await updateConstructionProject({
          bridge,
          projectId: editingProjectId,
          projectData,
        })
        bridge?.feedback?.success?.("Obra atualizada com sucesso.")
      }

      closeProjectModal()
      await loadProjects()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível salvar a obra.")
    } finally {
      setSubmittingProject(false)
    }
  }

  const handleDeleteProject = async (project) => {
    const confirmed = window.confirm(`Deseja remover a obra ${project.code} - ${project.name}?`)
    if (!confirmed) {
      return
    }

    try {
      await deleteConstructionProject({ bridge, projectId: project.id })
      bridge?.feedback?.success?.("Obra removida com sucesso.")
      if (activeProjectId === project.id) {
        setActiveProjectId(null)
        setProjectDetailTab("overview")
        setViewMode("projects")
      }
      await loadProjects()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover a obra.")
    }
  }

  const openCreateBlock = () => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de criar blocos.")
      return
    }

    setBlockModalMode("create")
    setEditingBlockId(null)
    setBlockForm(defaultBlockForm)
    setIsBlockModalOpen(true)
  }

  const openEditBlock = (block) => {
    setBlockModalMode("edit")
    setEditingBlockId(block.id)
    setBlockForm(toFormBlock(block))
    setIsBlockModalOpen(true)
  }

  const closeBlockModal = () => {
    if (submittingBlock) {
      return
    }

    setIsBlockModalOpen(false)
    setEditingBlockId(null)
    setBlockForm(defaultBlockForm)
  }

  const handleBlockFieldChange = (field, value) => {
    setBlockForm((currentBlockForm) => ({ ...currentBlockForm, [field]: value }))
  }

  const handleBlockSubmit = async (event) => {
    event.preventDefault()

    const validationError = requiredBlockFieldError(blockForm)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de salvar blocos.")
      return
    }

    setSubmittingBlock(true)
    try {
      if (blockModalMode === "create") {
        await createConstructionBlock({
          bridge,
          projectId: activeProjectId,
          blockData: blockForm,
        })
        bridge?.feedback?.success?.("Bloco criado com sucesso.")
      } else if (editingBlockId) {
        await updateConstructionBlock({
          bridge,
          blockId: editingBlockId,
          blockData: blockForm,
        })
        bridge?.feedback?.success?.("Bloco atualizado com sucesso.")
      }

      closeBlockModal()
      await loadBlocks()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível salvar o bloco.")
    } finally {
      setSubmittingBlock(false)
    }
  }

  const handleDeleteBlock = async (block) => {
    const confirmed = window.confirm(`Deseja remover o bloco ${block.code} - ${block.name}?`)
    if (!confirmed) {
      return
    }

    try {
      await deleteConstructionBlock({ bridge, blockId: block.id })
      bridge?.feedback?.success?.("Bloco removido com sucesso.")
      await loadBlocks()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover o bloco.")
    }
  }

  const openCreateSchedulePhase = () => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de criar fases.")
      return
    }

    const nextSequenceOrder = schedulePhases.length
      ? Math.max(...schedulePhases.map((phase) => phase.sequenceOrder || 0)) + 1
      : 1

    setScheduleModalMode("create")
    setEditingPhaseId(null)
    setSchedulePhaseForm({
      ...defaultSchedulePhaseForm,
      sequenceOrder: String(nextSequenceOrder),
    })
    setIsScheduleModalOpen(true)
  }

  const openEditSchedulePhase = (phase) => {
    setScheduleModalMode("edit")
    setEditingPhaseId(phase.id)
    setSchedulePhaseForm(toFormSchedulePhase(phase))
    setIsScheduleModalOpen(true)
  }

  const closeScheduleModal = () => {
    if (submittingSchedule) {
      return
    }

    setIsScheduleModalOpen(false)
    setEditingPhaseId(null)
    setSchedulePhaseForm(defaultSchedulePhaseForm)
  }

  const handleSchedulePhaseFieldChange = (field, value) => {
    setSchedulePhaseForm((currentPhaseForm) => ({ ...currentPhaseForm, [field]: value }))
  }

  const handleSchedulePhaseSubmit = async (event) => {
    event.preventDefault()

    const validationError = requiredScheduleFieldError(schedulePhaseForm)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de salvar fases.")
      return
    }

    setSubmittingSchedule(true)
    try {
      if (scheduleModalMode === "create") {
        await createConstructionSchedulePhase({
          bridge,
          projectId: activeProjectId,
          phaseData: schedulePhaseForm,
        })
        bridge?.feedback?.success?.("Fase criada com sucesso.")
      } else if (editingPhaseId) {
        await updateConstructionSchedulePhase({
          bridge,
          phaseId: editingPhaseId,
          phaseData: schedulePhaseForm,
        })
        bridge?.feedback?.success?.("Fase atualizada com sucesso.")
      }

      closeScheduleModal()
      await loadSchedulePhases()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível salvar a fase.")
    } finally {
      setSubmittingSchedule(false)
    }
  }

  const handleDeleteSchedulePhase = async (phase) => {
    const confirmed = window.confirm(`Deseja remover a fase ${phase.name}?`)
    if (!confirmed) {
      return
    }

    try {
      await deleteConstructionSchedulePhase({ bridge, phaseId: phase.id })
      bridge?.feedback?.success?.("Fase removida com sucesso.")
      await loadSchedulePhases()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover a fase.")
    }
  }

  const openCreateUnit = () => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de criar unidades.")
      return
    }

    setUnitModalMode("create")
    setEditingUnitId(null)
    setUnitForm(defaultUnitForm)
    setIsUnitModalOpen(true)
  }

  const openEditUnit = (unit) => {
    setUnitModalMode("edit")
    setEditingUnitId(unit.id)
    setUnitForm(toFormUnit(unit))
    setIsUnitModalOpen(true)
  }

  const closeUnitModal = () => {
    if (submittingUnit) {
      return
    }

    setIsUnitModalOpen(false)
    setEditingUnitId(null)
    setUnitForm(defaultUnitForm)
  }

  const handleUnitFieldChange = (field, value) => {
    setUnitForm((currentUnitForm) => ({ ...currentUnitForm, [field]: value }))
  }

  const handleUnitSubmit = async (event) => {
    event.preventDefault()

    const validationError = requiredUnitFieldError(unitForm, unitModalMode)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de salvar unidades.")
      return
    }

    setSubmittingUnit(true)
    try {
      if (unitModalMode === "create") {
        const unitCreateForms = buildUnitCreateForms(unitForm, units)
        const oversizedUnit = unitCreateForms.find((unitCreateForm) => unitCreateForm.code.length > 50)
        if (oversizedUnit) {
          bridge?.feedback?.warning?.("A descrição gerada deve ter até 50 caracteres.")
          return
        }

        for (const unitCreateForm of unitCreateForms) {
          await createConstructionUnit({
            bridge,
            projectId: activeProjectId,
            unitData: unitCreateForm,
          })
        }

        bridge?.feedback?.success?.(
          unitCreateForms.length === 1
            ? "Unidade criada com sucesso."
            : `${unitCreateForms.length} unidades criadas com sucesso.`
        )
      } else if (editingUnitId) {
        await updateConstructionUnit({
          bridge,
          unitId: editingUnitId,
          unitData: unitForm,
        })
        bridge?.feedback?.success?.("Unidade atualizada com sucesso.")
      }

      closeUnitModal()
      await loadUnits()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível salvar a unidade.")
    } finally {
      setSubmittingUnit(false)
    }
  }

  const handleDeleteUnit = async (unit) => {
    const confirmed = window.confirm(`Deseja remover a unidade ${unit.code}?`)
    if (!confirmed) {
      return
    }

    try {
      await deleteConstructionUnit({
        bridge,
        unitId: unit.id,
      })
      bridge?.feedback?.success?.("Unidade removida com sucesso.")
      await loadUnits()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover a unidade.")
    }
  }

  const openReserveUnitModal = (unit) => {
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    setReserveTargetUnit(unit)
    setReserveUnitForm({
      ...defaultReserveUnitForm,
      buyerPersonId: unit.buyerPersonId ?? "",
      reservationExpiresAt: unit.reservationExpiresAt ? String(unit.reservationExpiresAt).slice(0, 10) : "",
    })
    setIsReserveModalOpen(true)
  }

  const closeReserveUnitModal = () => {
    if (submittingReserve) {
      return
    }

    setReserveTargetUnit(null)
    setReserveUnitForm(defaultReserveUnitForm)
    setIsReserveModalOpen(false)
  }

  const handleReserveUnitChange = (field, value) => {
    setReserveUnitForm((currentForm) => ({ ...currentForm, [field]: value }))
  }

  const handleReserveUnitSubmit = async (event) => {
    event.preventDefault()

    if (!reserveTargetUnit) {
      return
    }

    const validationError = requiredReserveFieldError(reserveUnitForm)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    setSubmittingReserve(true)
    try {
      await reserveConstructionUnit({
        bridge,
        unitId: reserveTargetUnit.id,
        reserveData: reserveUnitForm,
      })
      bridge?.feedback?.success?.("Unidade reservada com sucesso.")
      closeReserveUnitModal()
      await loadUnits()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível reservar a unidade.")
    } finally {
      setSubmittingReserve(false)
    }
  }

  const handleReleaseUnit = async (unit) => {
    const confirmed = window.confirm(`Deseja liberar a reserva da unidade ${unit.code}?`)
    if (!confirmed) {
      return
    }

    try {
      await releaseConstructionUnitReservation({
        bridge,
        unitId: unit.id,
      })
      bridge?.feedback?.success?.("Reserva liberada com sucesso.")
      await loadUnits()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível liberar a reserva da unidade.")
    }
  }

  const openSaleUnitModal = async (unit) => {
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    void loadDocumentationTypes()
    setSaleTargetUnit(unit)
    setSaleUnitForm({
      ...defaultSaleUnitForm,
      buyerPersonId: unit.buyerPersonId ?? "",
      secondaryBuyerPersonId: unit.secondaryBuyerPersonId ?? "",
      brokerPersonId: unit.brokerPersonId ?? "",
      salePrice: formatCurrencyFromNumber(unit.salePrice),
      discountAmount: formatCurrencyFromNumber(unit.discountAmount),
      contractSignatureDate: unit.contractSignatureDate ?? "",
      saleNotes: unit.saleNotes ?? "",
    })
    setIsSaleModalOpen(true)

    if (unit.status !== "sold") {
      return
    }

    // Venda já confirmada: o formulário tem de abrir com a composição que está
    // valendo, senão editar o comprador zeraria os valores sem avisar.
    try {
      const plan = await getConstructionUnitPaymentPlan({ bridge, unitId: unit.id })
      setSaleUnitForm((current) => ({
        ...current,
        ...saleFormFieldsFromSources(plan.sources),
        documentations: (plan.documentations ?? []).map((documentation) => ({
          key: nextSaleDocumentationKey(),
          documentationTypeId: documentation.documentationTypeId ?? "",
          documentationTypeName: documentation.name ?? "",
          amount: formatCurrencyFromNumber(documentation.amount),
        })),
      }))
    } catch (requestError) {
      bridge?.feedback?.warning?.(
        requestError?.message ?? "Não foi possível carregar a composição atual da venda.",
      )
    }
  }

  const handleOpenCreateInstallment = (series) => {
    // O numero ja sugerido e o proximo livre da serie: o usuario pode trocar,
    // e o ERP recusa se colidir com uma parcela que ja existe.
    const rows = series?.installments ?? []
    const nextNumber = rows.reduce((highest, row) => Math.max(highest, Number(row.installmentNumber || 0)), 0) + 1
    setCreateInstallmentForm({
      ...defaultCreateInstallmentForm,
      receivableId: series?.receivableId ?? "",
      startingNumber: String(nextNumber),
      firstDueDate: new Date().toISOString().slice(0, 10),
    })
    setIsCreateInstallmentOpen(true)
  }

  const closeCreateInstallmentModal = () => {
    if (submittingCreateInstallment) {
      return
    }

    setIsCreateInstallmentOpen(false)
    setCreateInstallmentForm(defaultCreateInstallmentForm)
  }

  const handleCreateInstallmentChange = (field, value) => {
    setCreateInstallmentForm((current) => ({ ...current, [field]: value }))
  }

  const handleSubmitCreateInstallment = async (event) => {
    event.preventDefault()

    if (!selectedUnit) {
      return
    }

    setSubmittingCreateInstallment(true)
    try {
      await createConstructionUnitInstallments({
        bridge,
        unitId: selectedUnit.id,
        installmentData: createInstallmentForm,
      })
      bridge?.feedback?.success?.("Parcela incluída.")
      setIsCreateInstallmentOpen(false)
      setCreateInstallmentForm(defaultCreateInstallmentForm)
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível incluir a parcela.")
    } finally {
      setSubmittingCreateInstallment(false)
    }
  }

  const handleOpenPayInstallment = (installment) => {
    setPayingInstallment(installment)
    setPayInstallmentForm({
      ...defaultPayInstallmentForm,
      paymentMethod: installment.paymentMethod || "PIX",
      // A parcela aceita N recebimentos, entao o valor sugerido e o SALDO. Com o
      // valor cheio numa parcela ja recebida em parte o ERP recusa a baixa.
      paidAmount: formatCurrencyFromNumber(installmentOutstanding(installment)),
      paidAt: new Date().toISOString().slice(0, 10),
    })
  }

  const closePayInstallmentModal = () => {
    if (submittingInstallmentPayment) {
      return
    }

    setPayingInstallment(null)
    setPayInstallmentForm(defaultPayInstallmentForm)
  }

  const handlePayInstallmentChange = (field, value) => {
    setPayInstallmentForm((current) => ({ ...current, [field]: value }))
  }

  const handleSubmitPayInstallment = async (event) => {
    event.preventDefault()

    if (!payingInstallment || !selectedUnit) {
      return
    }

    setSubmittingInstallmentPayment(true)
    try {
      await payConstructionUnitInstallment({
        bridge,
        unitId: selectedUnit.id,
        installmentNumber: payingInstallment.installmentNumber,
        receivableId: payingInstallment.receivableId ?? null,
        paymentData: payInstallmentForm,
      })
      bridge?.feedback?.success?.(
        installmentOutstanding(payingInstallment) > parseCurrencyToNumber(payInstallmentForm.paidAmount)
          ? "Recebimento registrado. A parcela segue em aberto pelo saldo."
          : "Parcela baixada.",
      )
      setPayingInstallment(null)
      setPayInstallmentForm(defaultPayInstallmentForm)
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível baixar a parcela.")
    } finally {
      setSubmittingInstallmentPayment(false)
    }
  }

  const handleDeleteInstallment = async (installment) => {
    if (!selectedUnit) {
      return
    }

    const label = installment.receivableId ? "do aditivo" : "da venda"
    const confirmed = window.confirm(
      `Deseja excluir a parcela ${installment.installmentNumber} ${label}? A parcela é cancelada e os lançamentos contábeis dela são desfeitos.`,
    )
    if (!confirmed) {
      return
    }

    try {
      await deleteConstructionUnitInstallment({
        bridge,
        unitId: selectedUnit.id,
        installmentNumber: installment.installmentNumber,
        receivableId: installment.receivableId ?? null,
      })
      bridge?.feedback?.success?.("Parcela excluída.")
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível excluir a parcela.")
    }
  }

  const handleOpenDeleteAdjustment = (adjustment) => {
    setDeletingAdjustment(adjustment)
    setDeleteAdjustmentReason("")
  }

  const closeDeleteAdjustmentModal = () => {
    if (submittingAdjustmentDelete) {
      return
    }

    setDeletingAdjustment(null)
    setDeleteAdjustmentReason("")
  }

  const handleSubmitDeleteAdjustment = async (event) => {
    event.preventDefault()

    if (!deletingAdjustment || !selectedUnit) {
      return
    }

    setSubmittingAdjustmentDelete(true)
    try {
      await deleteConstructionUnitAdjustment({
        bridge,
        unitId: selectedUnit.id,
        receivableId: deletingAdjustment.receivableId,
        reason: deleteAdjustmentReason.trim(),
      })
      bridge?.feedback?.success?.("Aditivo excluído.")
      setDeletingAdjustment(null)
      setDeleteAdjustmentReason("")
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível excluir o aditivo.")
    } finally {
      setSubmittingAdjustmentDelete(false)
    }
  }

  const handleOpenEditInstallment = (installment) => {
    setEditingInstallment(installment)
    setEditInstallmentForm({
      paymentMethod: installment.paymentMethod ?? "",
      documentNumber: installment.documentNumber ?? "",
      observation: installment.observation ?? "",
    })
  }

  const closeEditInstallmentModal = () => {
    if (savingInstallment) {
      return
    }

    setEditingInstallment(null)
    setEditInstallmentForm(defaultEditInstallmentForm)
  }

  const handleEditInstallmentChange = (field, value) => {
    setEditInstallmentForm((current) => ({ ...current, [field]: value }))
  }

  const handleSubmitEditInstallment = async (event) => {
    event.preventDefault()

    if (!editingInstallment || !selectedUnit) {
      return
    }

    // Só viaja o que o usuário mexeu: o PATCH do ERP trata ausente como
    // "mantém", e mandar o valor atual de volta marcaria a parcela como
    // alterada na auditoria sem nada ter mudado.
    const changes = {}
    if (
      editInstallmentForm.paymentMethod &&
      editInstallmentForm.paymentMethod !== (editingInstallment.paymentMethod ?? "")
    ) {
      changes.payment_method = editInstallmentForm.paymentMethod
    }

    if (editInstallmentForm.documentNumber !== (editingInstallment.documentNumber ?? "")) {
      changes.document_number = editInstallmentForm.documentNumber
    }

    if (editInstallmentForm.observation !== (editingInstallment.observation ?? "")) {
      changes.observation = editInstallmentForm.observation
    }

    if (!Object.keys(changes).length) {
      bridge?.feedback?.warning?.("Nenhuma alteração para salvar nesta parcela.")
      return
    }

    setSavingInstallment(true)
    try {
      await updateConstructionUnitInstallment({
        bridge,
        unitId: selectedUnit.id,
        installmentNumber: editingInstallment.installmentNumber,
        receivableId: editingInstallment.receivableId ?? null,
        changes,
      })
      bridge?.feedback?.success?.("Parcela atualizada.")
      setEditingInstallment(null)
      setEditInstallmentForm(defaultEditInstallmentForm)
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível editar a parcela.")
    } finally {
      setSavingInstallment(false)
    }
  }

  const openCommissionModal = () => {
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    setCommissionForm(defaultCommissionForm)
    setIsCommissionModalOpen(true)
  }

  const closeCommissionModal = () => {
    if (submittingCommission) {
      return
    }

    setIsCommissionModalOpen(false)
    setCommissionForm(defaultCommissionForm)
  }

  const handleCommissionFormChange = (field, value) => {
    setCommissionForm((current) => ({ ...current, [field]: value }))
  }

  const handleSubmitCommission = async (event) => {
    event.preventDefault()

    if (!selectedUnit) {
      return
    }

    if (!commissionForm.beneficiaryPersonId) {
      bridge?.feedback?.warning?.("Informe o corretor favorecido do sinal.")
      return
    }

    setSubmittingCommission(true)
    try {
      await createConstructionUnitCommissions({
        bridge,
        unitId: selectedUnit.id,
        commissionData: commissionForm,
      })
      bridge?.feedback?.success?.("Sinal lançado.")
      setIsCommissionModalOpen(false)
      setCommissionForm(defaultCommissionForm)
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível lançar o sinal.")
    } finally {
      setSubmittingCommission(false)
    }
  }

  const handleSettleCommission = async (commission) => {
    if (!selectedUnit) {
      return
    }

    // Estornar devolve o sinal para em aberto: e o caminho para corrigir um
    // sinal que compoe a venda e foi baixado por engano.
    const paymentDate = commission.paymentDate ? null : new Date().toISOString().slice(0, 10)
    try {
      await settleConstructionUnitCommission({
        bridge,
        commissionId: commission.id,
        paymentDate,
      })
      bridge?.feedback?.success?.(paymentDate ? "Sinal baixado." : "Baixa do sinal estornada.")
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível baixar o sinal.")
    }
  }

  const handleDeleteCommission = async (commission) => {
    if (!selectedUnit) {
      return
    }

    try {
      await deleteConstructionUnitCommission({ bridge, commissionId: commission.id })
      bridge?.feedback?.success?.("Sinal removido.")
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover o sinal.")
    }
  }

  const openAdjustmentModal = () => {
    setAdjustmentForm(defaultAdjustmentForm)
    setIsAdjustmentModalOpen(true)
  }

  const closeAdjustmentModal = () => {
    if (submittingAdjustment) {
      return
    }

    setIsAdjustmentModalOpen(false)
    setAdjustmentForm(defaultAdjustmentForm)
  }

  const handleAdjustmentFormChange = (field, value) => {
    setAdjustmentForm((current) => ({ ...current, [field]: value }))
  }

  const handleSubmitAdjustment = async (event) => {
    event.preventDefault()

    if (!selectedUnit) {
      return
    }

    setSubmittingAdjustment(true)
    try {
      await createConstructionUnitAdjustment({
        bridge,
        unitId: selectedUnit.id,
        adjustmentData: adjustmentForm,
      })
      bridge?.feedback?.success?.("Aditivo lançado no contas a receber.")
      setIsAdjustmentModalOpen(false)
      setAdjustmentForm(defaultAdjustmentForm)
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível lançar o aditivo.")
    } finally {
      setSubmittingAdjustment(false)
    }
  }

  const closeSaleUnitModal = () => {
    if (submittingSale) {
      return
    }

    setSaleTargetUnit(null)
    setSaleUnitForm(defaultSaleUnitForm)
    setIsSaleModalOpen(false)
  }

  const handleSaleUnitChange = (field, value) => {
    setSaleUnitForm((currentForm) => ({ ...currentForm, [field]: value }))
  }

  const handleSaleUnitSubmit = async (event) => {
    event.preventDefault()

    if (!saleTargetUnit) {
      return
    }

    const validationError = requiredSaleFieldError(saleUnitForm)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    setSubmittingSale(true)
    try {
      const paymentSources = buildSalePaymentSourcesFromForm(saleUnitForm)
      await confirmConstructionUnitSale({
        bridge,
        unitId: saleTargetUnit.id,
        saleData: {
          ...saleUnitForm,
          paymentSources,
          documentations: buildSaleDocumentationsFromForm(saleUnitForm),
        },
      })
      // Os tipos criados digitando no combobox só existem depois do confirm:
      // recarregar deixa o próximo lançamento achá-los na lista.
      void loadDocumentationTypes()
      const wasEditing = saleTargetUnit.status === "sold"
      bridge?.feedback?.success?.(
        wasEditing ? "Venda atualizada: contrato e parcelas em aberto refeitos." : "Venda confirmada com sucesso.",
      )
      closeSaleUnitModal()
      await loadUnits()

      // A aba de parcelas e a de contrato leem o plano do ERP: sem recarregar,
      // a tela continuaria mostrando a cobrança antiga.
      if (selectedUnit?.id === saleTargetUnit.id) {
        await loadUnitPaymentPlan(saleTargetUnit.id)
      }
    } catch (requestError) {
      bridge?.feedback?.error?.(
        requestError?.message ??
          (saleTargetUnit.status === "sold"
            ? "Não foi possível atualizar a venda da unidade."
            : "Não foi possível confirmar a venda da unidade."),
      )
    } finally {
      setSubmittingSale(false)
    }
  }

  const loadMeasurementItems = useCallback(
    async (measurementId) => {
      if (!measurementId) {
        return
      }

      setLoadingMeasurementItems(true)
      setMeasurementItemsError(null)
      try {
        const result = await listConstructionMeasurementItems({ bridge, measurementId })
        setMeasurementItems(result.items)
      } catch (requestError) {
        setMeasurementItems([])
        setMeasurementItemsError(requestError?.message ?? "Não foi possível carregar os itens da medição.")
      } finally {
        setLoadingMeasurementItems(false)
      }
    },
    [bridge]
  )

  const loadUnitPaymentPlan = useCallback(
    async (unitId) => {
      if (!unitId) {
        return
      }

      setLoadingUnitPaymentPlan(true)
      setUnitPaymentPlanError(null)
      try {
        const plan = await getConstructionUnitPaymentPlan({ bridge, unitId })
        setUnitPaymentPlan(plan)
      } catch (requestError) {
        setUnitPaymentPlan(null)
        setUnitPaymentPlanError(requestError?.message ?? "Não foi possível carregar as parcelas da unidade.")
      } finally {
        setLoadingUnitPaymentPlan(false)
      }
    },
    [bridge]
  )

  const loadReceiptTemplates = useCallback(async () => {
    setReceiptTemplatesError(null)
    try {
      const result = await listErpReceiptTemplates({ bridge })
      setReceiptTemplates(result.items)
    } catch (requestError) {
      setReceiptTemplates([])
      setReceiptTemplatesError(
        requestError?.message ?? "Não foi possível carregar os modelos de recibo do ERP.",
      )
    }
  }, [bridge])

  const loadServiceTemplates = useCallback(async () => {
    setLoadingServiceTemplates(true)
    try {
      const result = await listConstructionServiceTemplates({ bridge })
      setServiceTemplates(result.items)
    } catch (requestError) {
      setServiceTemplates([])
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível carregar o catálogo de serviços.")
    } finally {
      setLoadingServiceTemplates(false)
    }
  }, [bridge])

  const handleImportServiceTemplates = async (fileList) => {
    const files = Array.from(fileList ?? [])
    if (!files.length) {
      return
    }

    setImportingServiceTemplates(true)
    try {
      const result = await importConstructionServiceTemplates({ bridge, files })
      const summary = [
        result.created ? `${result.created} serviço(s) criado(s)` : "",
        result.updated ? `${result.updated} atualizado(s)` : "",
        result.skipped ? `${result.skipped} já cadastrado(s)` : "",
        result.failed ? `${result.failed} com erro` : "",
      ]
        .filter(Boolean)
        .join(", ")

      if (result.failed) {
        const failures = result.results
          .filter((item) => item.status === "failed")
          .map((item) => `${item.fileName}: ${item.message}`)
          .join(" | ")
        bridge?.feedback?.warning?.(`${summary}. ${failures}`)
      } else {
        bridge?.feedback?.success?.(`Importação concluída: ${summary}.`)
      }

      await loadServiceTemplates()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível importar a planilha de serviços.")
    } finally {
      setImportingServiceTemplates(false)
    }
  }

  const openMeasurementItems = (measurement) => {
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    setItemsTargetMeasurement(measurement)
    setMeasurementItems([])
    void loadMeasurementItems(measurement.id)
    if (!serviceTemplates.length) {
      void loadServiceTemplates()
    }
  }

  const closeMeasurementItems = () => {
    if (savingMeasurementItem) {
      return
    }

    setItemsTargetMeasurement(null)
    setMeasurementItems([])
    setMeasurementItemsError(null)
  }

  const handleCreateMeasurementItem = async (itemForm) => {
    if (!itemsTargetMeasurement) {
      return false
    }

    if (!String(itemForm.serviceTemplateId ?? "").trim() && !String(itemForm.description ?? "").trim()) {
      bridge?.feedback?.warning?.("Escolha o serviço do catálogo ou informe a descrição.")
      return false
    }

    if (parseCurrencyFormValue(itemForm.amount) <= 0) {
      bridge?.feedback?.warning?.("Informe o valor do serviço medido.")
      return false
    }

    setSavingMeasurementItem(true)
    try {
      await createConstructionMeasurementItem({
        bridge,
        measurementId: itemsTargetMeasurement.id,
        itemData: itemForm,
      })
      bridge?.feedback?.success?.("Item de serviço adicionado.")
      await loadMeasurementItems(itemsTargetMeasurement.id)
      await loadMeasurements()
      return true
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível adicionar o item de serviço.")
      return false
    } finally {
      setSavingMeasurementItem(false)
    }
  }

  const handleDeleteMeasurementItem = async (item) => {
    if (!itemsTargetMeasurement) {
      return
    }

    setSavingMeasurementItem(true)
    try {
      await deleteConstructionMeasurementItem({ bridge, itemId: item.id })
      bridge?.feedback?.success?.("Item de serviço removido.")
      await loadMeasurementItems(itemsTargetMeasurement.id)
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover o item de serviço.")
    } finally {
      setSavingMeasurementItem(false)
    }
  }

  const handleCreateInspection = async (itemId, inspectionForm) => {
    if (!String(inspectionForm.description ?? "").trim()) {
      bridge?.feedback?.warning?.("Informe o que será verificado.")
      return false
    }

    setSavingMeasurementItem(true)
    try {
      await createConstructionMeasurementInspection({ bridge, itemId, inspectionData: inspectionForm })
      bridge?.feedback?.success?.("Item de inspeção adicionado.")
      await loadMeasurementItems(itemsTargetMeasurement.id)
      return true
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível adicionar o item de inspeção.")
      return false
    } finally {
      setSavingMeasurementItem(false)
    }
  }

  const handleVerifyInspection = async (inspection, checkNumber, status) => {
    setSavingMeasurementItem(true)
    try {
      await verifyConstructionMeasurementInspection({
        bridge,
        inspectionId: inspection.id,
        checkNumber,
        status,
      })
      bridge?.feedback?.success?.(
        checkNumber === 1 ? "Primeira verificação registrada." : "Segunda verificação registrada."
      )
      await loadMeasurementItems(itemsTargetMeasurement.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível registrar a verificação.")
    } finally {
      setSavingMeasurementItem(false)
    }
  }

  const handleDeleteInspection = async (inspection) => {
    setSavingMeasurementItem(true)
    try {
      await deleteConstructionMeasurementInspection({ bridge, inspectionId: inspection.id })
      await loadMeasurementItems(itemsTargetMeasurement.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover o item de inspeção.")
    } finally {
      setSavingMeasurementItem(false)
    }
  }

  const handleCreateOccurrence = async (itemId, occurrenceForm) => {
    if (!String(occurrenceForm.problem ?? "").trim()) {
      bridge?.feedback?.warning?.("Descreva o problema encontrado.")
      return false
    }

    setSavingMeasurementItem(true)
    try {
      await createConstructionMeasurementOccurrence({ bridge, itemId, occurrenceData: occurrenceForm })
      bridge?.feedback?.success?.("Ocorrência registrada.")
      await loadMeasurementItems(itemsTargetMeasurement.id)
      return true
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível registrar a ocorrência.")
      return false
    } finally {
      setSavingMeasurementItem(false)
    }
  }

  const handleResolveOccurrence = async (occurrence, solution) => {
    if (!String(solution ?? "").trim()) {
      bridge?.feedback?.warning?.("Descreva a solução antes de resolver a ocorrência.")
      return false
    }

    setSavingMeasurementItem(true)
    try {
      await updateConstructionMeasurementOccurrence({
        bridge,
        occurrenceId: occurrence.id,
        occurrenceData: { status: "resolved", solution },
      })
      bridge?.feedback?.success?.("Ocorrência resolvida.")
      await loadMeasurementItems(itemsTargetMeasurement.id)
      return true
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível resolver a ocorrência.")
      return false
    } finally {
      setSavingMeasurementItem(false)
    }
  }

  const handleDeleteOccurrence = async (occurrence) => {
    setSavingMeasurementItem(true)
    try {
      await deleteConstructionMeasurementOccurrence({ bridge, occurrenceId: occurrence.id })
      await loadMeasurementItems(itemsTargetMeasurement.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover a ocorrência.")
    } finally {
      setSavingMeasurementItem(false)
    }
  }

  const handleSubmitMeasurement = async (measurement) => {
    try {
      await submitConstructionMeasurement({ bridge, measurementId: measurement.id })
      bridge?.feedback?.success?.("Medição enviada para aprovação.")
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível enviar a medição para aprovação.")
    }
  }

  const openCreateMeasurement = (unit = null) => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de criar medições.")
      return
    }

    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    const measurementScope = unit
      ? measurements.filter((measurement) => measurement.unitId === unit.id)
      : measurements
    const nextSequenceNumber = measurementScope.length
      ? Math.max(...measurementScope.map((measurement) => Number(measurement.sequenceNumber || 0))) + 1
      : 1

    setMeasurementModalMode("create")
    setEditingMeasurementId(null)
    setMeasurementForm({
      ...defaultMeasurementForm,
      unitId: unit?.id ?? selectedUnit?.id ?? units[0]?.id ?? "",
      schedulePhaseId: schedulePhases[0]?.id ?? "",
      sequenceNumber: String(nextSequenceNumber),
    })
    setIsMeasurementModalOpen(true)
  }

  const openEditMeasurement = (measurement) => {
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    setMeasurementModalMode("edit")
    setEditingMeasurementId(measurement.id)
    setMeasurementForm({
      code: measurement.code ?? "",
      unitId: measurement.unitId ?? "",
      schedulePhaseId: measurement.schedulePhaseId ?? "",
      sequenceNumber: measurement.sequenceNumber === null || measurement.sequenceNumber === undefined
        ? ""
        : String(measurement.sequenceNumber),
      measurementType: measurement.measurementType ?? "",
      competenceDate: measurement.competenceDate ? String(measurement.competenceDate).slice(0, 10) : "",
      description: measurement.description ?? "",
      grossAmount: measurement.grossAmount === null || measurement.grossAmount === undefined ? "" : String(measurement.grossAmount),
      retentionsAmount:
        measurement.retentionsAmount === null || measurement.retentionsAmount === undefined
          ? "0"
          : String(measurement.retentionsAmount),
      netAmount: measurement.netAmount === null || measurement.netAmount === undefined ? "" : String(measurement.netAmount),
      measuredAmount:
        measurement.measuredAmount === null || measurement.measuredAmount === undefined
          ? ""
          : String(measurement.measuredAmount),
      dueDate: measurement.dueDate ? String(measurement.dueDate).slice(0, 10) : "",
      supplierPersonId: measurement.supplierPersonId ?? "",
      documentType: measurement.documentType ?? "",
      documentNumber: measurement.documentNumber ?? "",
    })
    setIsMeasurementModalOpen(true)
  }

  const closeMeasurementModal = () => {
    if (submittingMeasurement) {
      return
    }

    setIsMeasurementModalOpen(false)
    setEditingMeasurementId(null)
    setMeasurementForm(defaultMeasurementForm)
  }

  const handleMeasurementFieldChange = (field, value) => {
    setMeasurementForm((currentForm) => ({ ...currentForm, [field]: value }))
  }

  const handleMeasurementSubmit = async (event) => {
    event.preventDefault()

    const validationError = requiredMeasurementFieldError(measurementForm)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de salvar medições.")
      return
    }

    setSubmittingMeasurement(true)
    try {
      if (measurementModalMode === "create") {
        await createConstructionMeasurement({
          bridge,
          projectId: activeProjectId,
          measurementData: measurementForm,
        })
        bridge?.feedback?.success?.("Medição criada com sucesso.")
      } else if (editingMeasurementId) {
        await updateConstructionMeasurement({
          bridge,
          measurementId: editingMeasurementId,
          measurementData: measurementForm,
        })
        bridge?.feedback?.success?.("Medição atualizada com sucesso.")
      }

      closeMeasurementModal()
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível salvar a medição.")
    } finally {
      setSubmittingMeasurement(false)
    }
  }

  const handleDeleteMeasurement = async (measurement) => {
    const confirmed = window.confirm(`Deseja remover a medição ${measurement.code}?`)
    if (!confirmed) {
      return
    }

    try {
      await deleteConstructionMeasurement({ bridge, measurementId: measurement.id })
      bridge?.feedback?.success?.("Medição removida com sucesso.")
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover a medição.")
    }
  }

  const handleApproveMeasurement = async (measurement) => {
    const confirmed = window.confirm(`Deseja aprovar a medição ${measurement.code}?`)
    if (!confirmed) {
      return
    }

    try {
      await approveConstructionMeasurement({ bridge, measurementId: measurement.id })
      bridge?.feedback?.success?.("Medição aprovada com sucesso.")
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível aprovar a medição.")
    }
  }

  const openRejectMeasurement = (measurement) => {
    setRejectMeasurementTarget(measurement)
    setRejectMeasurementForm({
      reason: measurement.rejectionReason ?? "",
    })
  }

  const closeRejectMeasurementModal = () => {
    if (submittingMeasurementReject) {
      return
    }

    setRejectMeasurementTarget(null)
    setRejectMeasurementForm(defaultMeasurementRejectForm)
  }

  const handleRejectMeasurementChange = (field, value) => {
    setRejectMeasurementForm((currentForm) => ({ ...currentForm, [field]: value }))
  }

  const handleRejectMeasurementSubmit = async (event) => {
    event.preventDefault()

    if (!rejectMeasurementTarget) {
      return
    }

    setSubmittingMeasurementReject(true)
    try {
      await rejectConstructionMeasurement({
        bridge,
        measurementId: rejectMeasurementTarget.id,
        reason: rejectMeasurementForm.reason,
      })
      bridge?.feedback?.success?.("Medição rejeitada com sucesso.")
      closeRejectMeasurementModal()
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível rejeitar a medição.")
    } finally {
      setSubmittingMeasurementReject(false)
    }
  }

  const openCreateProcurement = () => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de criar requisições.")
      return
    }

    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    setProcurementModalMode("create")
    setEditingProcurementId(null)
    setProcurementForm(defaultProcurementForm)
    setIsProcurementModalOpen(true)
  }

  const openEditProcurement = (procurementRequest) => {
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }

    setProcurementModalMode("edit")
    setEditingProcurementId(procurementRequest.id)
    setProcurementForm(toFormProcurement(procurementRequest))
    setIsProcurementModalOpen(true)
  }

  const closeProcurementModal = () => {
    if (submittingProcurement) {
      return
    }

    setIsProcurementModalOpen(false)
    setEditingProcurementId(null)
    setProcurementForm(defaultProcurementForm)
  }

  const handleProcurementFieldChange = (field, value) => {
    setProcurementForm((currentForm) => ({ ...currentForm, [field]: value }))
  }

  const handleProcurementSubmit = async (event) => {
    event.preventDefault()

    const validationError = requiredProcurementFieldError(procurementForm)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Abra uma obra antes de salvar requisições.")
      return
    }

    setSubmittingProcurement(true)
    try {
      if (procurementModalMode === "create") {
        await createConstructionProcurementRequest({
          bridge,
          projectId: activeProjectId,
          procurementData: procurementForm,
        })
        bridge?.feedback?.success?.("Requisição criada com sucesso.")
      } else if (editingProcurementId) {
        await updateConstructionProcurementRequest({
          bridge,
          procurementRequestId: editingProcurementId,
          procurementData: procurementForm,
        })
        bridge?.feedback?.success?.("Requisição atualizada com sucesso.")
      }

      closeProcurementModal()
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível salvar a requisição.")
    } finally {
      setSubmittingProcurement(false)
    }
  }

  const handleDeleteProcurement = async (procurementRequest) => {
    const confirmed = window.confirm(`Deseja remover a requisição ${procurementRequest.code}?`)
    if (!confirmed) {
      return
    }

    try {
      await deleteConstructionProcurementRequest({
        bridge,
        procurementRequestId: procurementRequest.id,
      })
      bridge?.feedback?.success?.("Requisição removida com sucesso.")
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover a requisição.")
    }
  }

  const handleSubmitProcurement = async (procurementRequest) => {
    const confirmed = window.confirm(`Deseja enviar a requisição ${procurementRequest.code} para aprovação?`)
    if (!confirmed) {
      return
    }

    try {
      await submitConstructionProcurementRequest({
        bridge,
        procurementRequestId: procurementRequest.id,
      })
      bridge?.feedback?.success?.("Requisição enviada para aprovação.")
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível enviar a requisição.")
    }
  }

  const handleApproveProcurement = async (procurementRequest) => {
    const confirmed = window.confirm(`Deseja aprovar a requisição ${procurementRequest.code}?`)
    if (!confirmed) {
      return
    }

    try {
      await approveConstructionProcurementRequest({
        bridge,
        procurementRequestId: procurementRequest.id,
      })
      bridge?.feedback?.success?.("Requisição aprovada com sucesso.")
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível aprovar a requisição.")
    }
  }

  const openRejectProcurement = (procurementRequest) => {
    setRejectProcurementTarget(procurementRequest)
    setRejectProcurementForm({
      reason: procurementRequest.rejectionReason ?? "",
    })
  }

  const closeRejectProcurementModal = () => {
    if (submittingProcurementReject) {
      return
    }

    setRejectProcurementTarget(null)
    setRejectProcurementForm(defaultProcurementRejectForm)
  }

  const handleRejectProcurementChange = (field, value) => {
    setRejectProcurementForm((currentForm) => ({ ...currentForm, [field]: value }))
  }

  const handleRejectProcurementSubmit = async (event) => {
    event.preventDefault()

    if (!rejectProcurementTarget) {
      return
    }

    setSubmittingProcurementReject(true)
    try {
      await rejectConstructionProcurementRequest({
        bridge,
        procurementRequestId: rejectProcurementTarget.id,
        reason: rejectProcurementForm.reason,
      })
      bridge?.feedback?.success?.("Requisição rejeitada com sucesso.")
      closeRejectProcurementModal()
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível rejeitar a requisição.")
    } finally {
      setSubmittingProcurementReject(false)
    }
  }

  return (
    <main className={styles.page} data-theme={bridge?.theme ?? "light"}>
      <section className={styles.pageHeader}>
        <div className={styles.header}>
          <div className={styles.left}>
            <nav className={styles.breadcrumb} aria-label="Navegação">
              <span className={styles.breadcrumbLink}>Inicio</span>
              <span className={styles.breadcrumbItem}>
                <span className={styles.separator}>/</span>
                <span className={styles.breadcrumbCurrent}>Obras</span>
              </span>
            </nav>
            <h1 className={styles.title}>Obras</h1>
          </div>
          {viewMode === "projects" ? (
            <div className={styles.heroActions}>
              <button type="button" className={styles.primaryButton} onClick={openCreateProject}>
                <Plus size={18} />
                Nova obra
              </button>
              <button type="button" className={styles.secondaryButton} onClick={loadProjects} disabled={loading}>
                <RefreshCw size={16} className={loading ? styles.spinIcon : undefined} />
                Recarregar
              </button>
            </div>
          ) : null}
        </div>

        <div className={styles.metricsGrid}>
          {summaryItems.map((item) => {
            const Icon = item.icon
            return (
              <article className={`${styles.metricCard} ${styles[item.tone] ?? ""}`} key={item.label}>
                <div className={styles.metricIconWrap}>
                  <Icon size={20} />
                </div>
                <div className={styles.metricContent}>
                  <p className={styles.metricLabel}>{item.label}</p>
                  <p className={styles.metricValue}>{item.value}</p>
                  <p className={styles.metricHint}>{item.hint}</p>
                </div>
              </article>
            )
          })}
        </div>
      </section>

      {viewMode === "projects" ? (
        <>
          <section className={styles.filtersCard}>
            <div className={styles.filtersGrid}>
              <label className={styles.filterControl}>
                <span>Buscar</span>
                <input
                  type="text"
                  value={filters.search}
                  onChange={(event) => handleFilterChange("search", event.target.value)}
                  placeholder="Código, nome ou CNPJ"
                />
              </label>
              <label className={styles.filterControl}>
                <span>Status</span>
                <select value={filters.status} onChange={(event) => handleFilterChange("status", event.target.value)}>
                  <option value="">Todos</option>
                  {statusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.filterControl}>
                <span>Inicio inicial</span>
                <input
                  type="date"
                  value={filters.startDate}
                  onChange={(event) => handleFilterChange("startDate", event.target.value)}
                />
              </label>
              <label className={styles.filterControl}>
                <span>Inicio final</span>
                <input
                  type="date"
                  value={filters.endDate}
                  onChange={(event) => handleFilterChange("endDate", event.target.value)}
                />
              </label>
            </div>
            {hasActiveFilters ? (
              <div className={styles.filtersFooter}>
                <button type="button" className={styles.secondaryButton} onClick={clearFilters}>
                  Limpar filtros
                </button>
              </div>
            ) : null}
          </section>

          <DomainCard
            title="Cadastro de obras"
            subtitle="Abra uma obra para gerenciar blocos, unidades, cronograma, medições e requisições."
            content={
              <ProjectList
                projects={visibleProjects}
                loading={loading}
                error={error}
                onRetry={loadProjects}
                onOpenDetails={openProjectDetail}
                onEdit={openEditProject}
                onDelete={handleDeleteProject}
              />
            }
            footer={
              <span className={styles.paginationSummary}>
                Mostrando {visibleProjects.length} de {totalProjects} obras
              </span>
            }
          />
        </>
      ) : null}

      {viewMode === "projectDetail" && selectedProject ? (
        <>
          <ProjectDetailHeader
            project={selectedProject}
            units={units}
            schedulePhases={schedulePhases}
            onBack={closeProjectDetail}
            onEdit={openEditProject}
            onRefresh={reloadProjectDetail}
            loading={loading}
          />

          <section className={styles.tabCard}>
            <div className={styles.tabList}>
              {projectDetailTabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <button
                    key={tab.id}
                    type="button"
                    className={`${styles.tabButton} ${projectDetailTab === tab.id ? styles.tabButtonActive : ""}`}
                    onClick={() => setProjectDetailTab(tab.id)}
                  >
                    <Icon size={16} />
                    {tab.label}
                  </button>
                )
              })}
            </div>
          </section>

          {projectDetailTab === "overview" ? (
            <DomainCard
              title="Resumo operacional"
              subtitle="Indicadores da obra aberta com comercial, medições e suprimentos."
              content={
                <OverviewPanel
                  selectedProject={selectedProject}
                  units={units}
                  schedulePhases={schedulePhases}
                  measurements={measurements}
                  procurementRequests={procurementRequests}
                  summary={projectSummary}
                  loadingSummary={loadingProjectSummary}
                  summaryError={projectSummaryError}
                  onRetrySummary={() => loadProjectSummary(selectedProject.id)}
                />
              }
            />
          ) : null}

          {projectDetailTab === "blocks" ? (
            <DomainCard
              title="Blocos/Torres"
              subtitle="CRUD da obra aberta com código, status e total de pavimentos."
              action={
                <button type="button" className={styles.primaryButton} onClick={openCreateBlock}>
                  <Plus size={16} />
                  Novo bloco
                </button>
              }
              content={
                <BlocksList
                  blocks={blocks}
                  loading={loadingBlocks}
                  error={blockError}
                  onRetry={loadBlocks}
                  onEdit={openEditBlock}
                  onDelete={handleDeleteBlock}
                />
              }
            />
          ) : null}

          {projectDetailTab === "units" ? (
            <DomainCard
              title={selectedUnit ? `Unidade ${selectedUnit.code}` : "Unidades"}
              subtitle={
                selectedUnit
                  ? "Detalhe operacional e financeiro da unidade selecionada."
                  : "Inventário comercial com reserva, liberação, medições e venda por unidade."
              }
              action={
                selectedUnit ? (
                  <button type="button" className={styles.secondaryButton} onClick={closeUnitDetail}>
                    <ChevronLeft size={16} />
                    Voltar para unidades
                  </button>
                ) : (
                  <button type="button" className={styles.primaryButton} onClick={openCreateUnit}>
                    <Plus size={16} />
                    Nova unidade
                  </button>
                )
              }
              content={
                selectedUnit ? (
                  <UnitDetailPanel
                    unit={selectedUnit}
                    blocks={blocks}
                    measurements={selectedUnitMeasurements}
                    schedulePhases={schedulePhases}
                    activeTab={unitDetailTab}
                    loadingMeasurements={loadingMeasurements}
                    measurementError={measurementError}
                    onTabChange={setUnitDetailTab}
                    onEdit={openEditUnit}
                    onReserve={openReserveUnitModal}
                    onRelease={handleReleaseUnit}
                    onSale={openSaleUnitModal}
                    onCreateMeasurement={openCreateMeasurement}
                    onRetryMeasurements={loadMeasurements}
                    onEditMeasurement={openEditMeasurement}
                    onDeleteMeasurement={handleDeleteMeasurement}
                    onApproveMeasurement={handleApproveMeasurement}
                    onOpenMeasurementItems={openMeasurementItems}
                    onSubmitMeasurement={handleSubmitMeasurement}
                    onRejectMeasurement={openRejectMeasurement}
                    paymentPlan={unitPaymentPlan}
                    loadingPaymentPlan={loadingUnitPaymentPlan}
                    paymentPlanError={unitPaymentPlanError}
                    onRetryPaymentPlan={loadUnitPaymentPlan}
                    onEditInstallment={handleOpenEditInstallment}
                    onPayInstallment={handleOpenPayInstallment}
                    onDeleteInstallment={handleDeleteInstallment}
                    onDeleteAdjustment={handleOpenDeleteAdjustment}
                    onCreateInstallment={handleOpenCreateInstallment}
                    people={personSummaries}
                    onCreateCommission={openCommissionModal}
                    onSettleCommission={handleSettleCommission}
                    onDeleteCommission={handleDeleteCommission}
                    onCreateAdjustment={openAdjustmentModal}
                  />
                ) : (
                  <UnitsList
                    units={units}
                    blocks={blocks}
                    loading={loadingUnits}
                    error={unitError}
                    onRetry={loadUnits}
                    onOpenDetails={openUnitDetail}
                    onEdit={openEditUnit}
                    onDelete={handleDeleteUnit}
                    onReserve={openReserveUnitModal}
                    onRelease={handleReleaseUnit}
                    onSale={openSaleUnitModal}
                  />
                )
              }
            />
          ) : null}

          {projectDetailTab === "schedule" ? (
            <DomainCard
              title="Cronograma"
              subtitle={`CRUD de fases com sequência e progresso médio de ${scheduleProgress}%`}
              action={
                <button type="button" className={styles.primaryButton} onClick={openCreateSchedulePhase}>
                  <Plus size={16} />
                  Nova fase
                </button>
              }
              content={
                <ScheduleList
                  phases={schedulePhases}
                  loading={loadingSchedule}
                  error={scheduleError}
                  onRetry={loadSchedulePhases}
                  onEdit={openEditSchedulePhase}
                  onDelete={handleDeleteSchedulePhase}
                />
              }
            />
          ) : null}

          {projectDetailTab === "procurement" ? (
            <DomainCard
              title="Requisições"
              subtitle="Solicitações de compra com fluxo de envio, aprovação e integração ERP."
              action={
                <button type="button" className={styles.primaryButton} onClick={openCreateProcurement}>
                  <Plus size={16} />
                  Nova requisição
                </button>
              }
              content={
                <ProcurementList
                  procurementRequests={procurementRequests}
                  loading={loadingProcurement}
                  error={procurementError}
                  onRetry={loadProcurementRequests}
                  onEdit={openEditProcurement}
                  onDelete={handleDeleteProcurement}
                  onSubmit={handleSubmitProcurement}
                  onApprove={handleApproveProcurement}
                  onReject={openRejectProcurement}
                />
              }
            />
          ) : null}

          {projectDetailTab === "reports" ? (
            <DomainCard
              title="Relatórios"
              subtitle="Carteira, custos medidos, margem estimada e rastreabilidade por unidade."
              content={
                <ReportsPanel
                  units={units}
                  schedulePhases={schedulePhases}
                  measurements={measurements}
                />
              }
            />
          ) : null}

          {projectDetailTab === "integrations" ? (
            <DomainCard
              title="Integrações"
              subtitle="Referências ERP para pessoas, financeiro e compras sincronizadas no módulo."
              content={
                <IntegrationPanel
                  personLookupQuery={personLookupQuery}
                  onPersonLookupQueryChange={handlePersonLookupQueryChange}
                  onPersonLookupSearch={handlePersonLookupSearch}
                  loadingPeople={loadingPersonSummaries}
                  personLookupError={personLookupError}
                  people={personSummaries}
                  measurements={measurements}
                  procurementRequests={procurementRequests}
                  units={units}
                />
              }
            />
          ) : null}
        </>
      ) : null}

      {viewMode === "projectDetail" && !selectedProject ? (
        <DomainCard
          title="Obra não encontrada"
          subtitle="Volte para a lista e abra uma obra cadastrada."
          action={
            <button type="button" className={styles.secondaryButton} onClick={closeProjectDetail}>
              <ChevronLeft size={16} />
              Voltar para obras
            </button>
          }
          content={<div className={styles.empty}>Não foi possível carregar o detalhe da obra.</div>}
        />
      ) : null}

      {isProjectModalOpen ? (
        <ProjectModal
          mode={projectModalMode}
          projectForm={projectForm}
          people={personSummaries}
          loadingPeople={loadingPersonSummaries}
          personLookupError={personLookupError}
          zipLookup={projectZipLookup}
          onClose={closeProjectModal}
          onChange={handleProjectFieldChange}
          receiptTemplates={receiptTemplates}
          receiptTemplatesError={receiptTemplatesError}
          onZipLookup={handleProjectZipLookup}
          onSubmit={handleProjectSubmit}
          loading={submittingProject}
        />
      ) : null}

      {isBlockModalOpen ? (
        <BlockModal
          mode={blockModalMode}
          blockForm={blockForm}
          onClose={closeBlockModal}
          onChange={handleBlockFieldChange}
          onSubmit={handleBlockSubmit}
          loading={submittingBlock}
        />
      ) : null}

      {isUnitModalOpen ? (
        <UnitModal
          mode={unitModalMode}
          unitForm={unitForm}
          blocks={blocks}
          onClose={closeUnitModal}
          onChange={handleUnitFieldChange}
          onSubmit={handleUnitSubmit}
          loading={submittingUnit}
        />
      ) : null}

      {isReserveModalOpen ? (
        <ReserveUnitModal
          reserveForm={reserveUnitForm}
          unit={reserveTargetUnit}
          people={personSummaries}
          onClose={closeReserveUnitModal}
          onChange={handleReserveUnitChange}
          onSubmit={handleReserveUnitSubmit}
          loading={submittingReserve}
        />
      ) : null}

      {isSaleModalOpen ? (
        <SaleUnitModal
          saleForm={saleUnitForm}
          unit={saleTargetUnit}
          people={personSummaries}
          onClose={closeSaleUnitModal}
          onChange={handleSaleUnitChange}
          onSubmit={handleSaleUnitSubmit}
          documentationTypes={documentationTypes}
          loadingDocumentationTypes={loadingDocumentationTypes}
          loading={submittingSale}
        />
      ) : null}

      {isCreateInstallmentOpen ? (
        <CreateInstallmentModal
          unit={selectedUnit}
          form={createInstallmentForm}
          onClose={closeCreateInstallmentModal}
          onChange={handleCreateInstallmentChange}
          onSubmit={handleSubmitCreateInstallment}
          loading={submittingCreateInstallment}
        />
      ) : null}

      {payingInstallment ? (
        <PayInstallmentModal
          installment={payingInstallment}
          form={payInstallmentForm}
          onClose={closePayInstallmentModal}
          onChange={handlePayInstallmentChange}
          onSubmit={handleSubmitPayInstallment}
          loading={submittingInstallmentPayment}
        />
      ) : null}

      {deletingAdjustment ? (
        <DeleteAdjustmentModal
          adjustment={deletingAdjustment}
          reason={deleteAdjustmentReason}
          onClose={closeDeleteAdjustmentModal}
          onChange={setDeleteAdjustmentReason}
          onSubmit={handleSubmitDeleteAdjustment}
          loading={submittingAdjustmentDelete}
        />
      ) : null}

      {isCommissionModalOpen ? (
        <CommissionModal
          unit={selectedUnit}
          commissionForm={commissionForm}
          people={personSummaries}
          loadingPeople={loadingPersonSummaries}
          personLookupError={personLookupError}
          onClose={closeCommissionModal}
          onChange={handleCommissionFormChange}
          onSubmit={handleSubmitCommission}
          loading={submittingCommission}
        />
      ) : null}

      {isAdjustmentModalOpen ? (
        <AdjustmentModal
          unit={selectedUnit}
          adjustmentForm={adjustmentForm}
          onClose={closeAdjustmentModal}
          onChange={handleAdjustmentFormChange}
          onSubmit={handleSubmitAdjustment}
          loading={submittingAdjustment}
        />
      ) : null}

      {editingInstallment ? (
        <EditInstallmentModal
          installment={editingInstallment}
          form={editInstallmentForm}
          onClose={closeEditInstallmentModal}
          onChange={handleEditInstallmentChange}
          onSubmit={handleSubmitEditInstallment}
          loading={savingInstallment}
        />
      ) : null}

      {itemsTargetMeasurement ? (
        <MeasurementItemsModal
          measurement={itemsTargetMeasurement}
          items={measurementItems}
          people={personSummaries}
          serviceTemplates={serviceTemplates}
          loadingServiceTemplates={loadingServiceTemplates}
          importingServiceTemplates={importingServiceTemplates}
          onImportServiceTemplates={handleImportServiceTemplates}
          loading={loadingMeasurementItems}
          error={measurementItemsError}
          saving={savingMeasurementItem}
          onClose={closeMeasurementItems}
          onRetry={() => loadMeasurementItems(itemsTargetMeasurement.id)}
          onCreateItem={handleCreateMeasurementItem}
          onDeleteItem={handleDeleteMeasurementItem}
          onCreateInspection={handleCreateInspection}
          onVerifyInspection={handleVerifyInspection}
          onDeleteInspection={handleDeleteInspection}
          onCreateOccurrence={handleCreateOccurrence}
          onResolveOccurrence={handleResolveOccurrence}
          onDeleteOccurrence={handleDeleteOccurrence}
        />
      ) : null}

      {isMeasurementModalOpen ? (
        <MeasurementModal
          mode={measurementModalMode}
          measurementForm={measurementForm}
          people={personSummaries}
          units={units}
          lockedUnit={measurementForm.unitId ? units.find((unit) => unit.id === measurementForm.unitId) ?? null : null}
          schedulePhases={schedulePhases}
          onClose={closeMeasurementModal}
          onChange={handleMeasurementFieldChange}
          onSubmit={handleMeasurementSubmit}
          loading={submittingMeasurement}
        />
      ) : null}

      {rejectMeasurementTarget ? (
        <RejectMeasurementModal
          measurement={rejectMeasurementTarget}
          rejectForm={rejectMeasurementForm}
          onClose={closeRejectMeasurementModal}
          onChange={handleRejectMeasurementChange}
          onSubmit={handleRejectMeasurementSubmit}
          loading={submittingMeasurementReject}
        />
      ) : null}

      {isProcurementModalOpen ? (
        <ProcurementModal
          mode={procurementModalMode}
          procurementForm={procurementForm}
          people={personSummaries}
          onClose={closeProcurementModal}
          onChange={handleProcurementFieldChange}
          onSubmit={handleProcurementSubmit}
          loading={submittingProcurement}
        />
      ) : null}

      {rejectProcurementTarget ? (
        <RejectProcurementModal
          procurementRequest={rejectProcurementTarget}
          rejectForm={rejectProcurementForm}
          onClose={closeRejectProcurementModal}
          onChange={handleRejectProcurementChange}
          onSubmit={handleRejectProcurementSubmit}
          loading={submittingProcurementReject}
        />
      ) : null}

      {isScheduleModalOpen ? (
        <SchedulePhaseModal
          mode={scheduleModalMode}
          schedulePhaseForm={schedulePhaseForm}
          onClose={closeScheduleModal}
          onChange={handleSchedulePhaseFieldChange}
          onSubmit={handleSchedulePhaseSubmit}
          loading={submittingSchedule}
        />
      ) : null}
    </main>
  )
}

function DomainCard({ title, subtitle, content, footer = null, action = null }) {
  return (
    <div className={`${styles.card} ${styles.tableCard}`}>
      <div className={styles.tableHeaderRow}>
        <div>
          <h2>{title}</h2>
          {subtitle ? <p className={styles.textMuted}>{subtitle}</p> : null}
        </div>
        {action ? <div className={styles.tableHeaderActions}>{action}</div> : null}
      </div>
      {content}
      {footer ? <div className={styles.paginationSlot}>{footer}</div> : null}
    </div>
  )
}

function SummaryMetric({ label, value, hint, tone = null }) {
  const toneClass =
    tone === "positive" ? styles.summaryValuePositive : tone === "negative" ? styles.summaryValueNegative : ""

  return (
    <article className={styles.integrationCard}>
      <h3>{label}</h3>
      <p className={`${styles.metricValue} ${toneClass}`}>{value}</p>
      <p className={styles.metricHint}>{hint}</p>
    </article>
  )
}

function OverviewPanel({
  selectedProject,
  units,
  schedulePhases,
  measurements,
  procurementRequests,
  summary,
  loadingSummary,
  summaryError,
  onRetrySummary,
}) {
  if (!selectedProject) {
    return <div className={styles.empty}>Abra uma obra para visualizar os indicadores.</div>
  }

  const availableUnits = units.filter((unit) => unit.status === "available").length
  const reservedUnits = units.filter((unit) => unit.status === "reserved").length
  const soldUnits = units.filter((unit) => ["sold", "delivered"].includes(unit.status)).length
  const scheduleAverage = schedulePhases.length
    ? Number(
        (
          schedulePhases.reduce((total, phase) => total + Number(phase.progressPercent ?? 0), 0) /
          schedulePhases.length
        ).toFixed(1)
      )
    : 0

  const pendingProcurementApprovals = procurementRequests.filter(
    (procurementRequest) => procurementRequest.status === "pending_approval"
  ).length

  const alerts = []
  if (!selectedProject.analyticCostCenterId) {
    alerts.push("Obra sem centro de custo analítico vinculado.")
  }
  if (!schedulePhases.length) {
    alerts.push("Cronograma ainda não foi cadastrado para a obra.")
  }
  if (pendingProcurementApprovals > 0) {
    alerts.push(`${pendingProcurementApprovals} requisição(ões) aguardando aprovação.`)
  }
  if (measurements.some((measurement) => measurement.status === "rejected")) {
    alerts.push("Existem medições rejeitadas aguardando ajuste.")
  }
  if (summary?.overdueCount > 0) {
    alerts.push(
      `${summary.overdueCount} parcela(s) vencida(s), somando ${formatCurrencyFromNumber(summary.overdueAmount)}.`,
    )
  }
  if (summary?.erpUnavailableReason) {
    alerts.push(`Financeiro do ERP indisponível agora: ${summary.erpUnavailableReason}`)
  }

  if (loadingSummary && !summary) {
    return (
      <div className={styles.empty} aria-busy="true">
        <RefreshCw className={styles.spinIcon} size={16} />
        Carregando o resumo da obra...
      </div>
    )
  }

  if (summaryError && !summary) {
    return (
      <div className={styles.empty}>
        <span>{summaryError}</span>
        <button type="button" className={styles.secondaryButton} onClick={onRetrySummary}>
          <RefreshCw size={16} />
          Tentar novamente
        </button>
      </div>
    )
  }

  const costDifference = Number(summary?.costDifferenceAmount ?? 0)
  const receivableTotal = Number(summary?.receivableTotalAmount ?? 0)
  const receivedAmount = Number(summary?.receivedAmount ?? 0)
  const receivedShare = receivableTotal > 0 ? Math.round((receivedAmount / receivableTotal) * 100) : 0

  return (
    <div className={styles.integrationPanel}>
      <div className={styles.summaryGroup}>
        <span className={styles.summaryGroupTitle}>Unidades</span>
        <div className={styles.integrationGrid}>
          <SummaryMetric
            label="Unidades"
            value={units.length}
            hint="total cadastrado na obra"
          />
          <SummaryMetric
            label="Vendidas"
            value={soldUnits}
            hint={units.length ? `${Math.round((soldUnits / units.length) * 100)}% da obra` : "-"}
          />
          <SummaryMetric label="Reservadas" value={reservedUnits} hint={`${availableUnits} disponível(is)`} />
        </div>
      </div>

      <div className={styles.summaryGroup}>
        <span className={styles.summaryGroupTitle}>Custo</span>
        <div className={styles.integrationGrid}>
          <SummaryMetric
            label="Previsto"
            value={formatCurrencyFromNumber(summary?.plannedCostAmount ?? 0)}
            hint={`${summary?.procurementRequestsCount ?? 0} requisição(ões) de compra`}
          />
          <SummaryMetric
            label="Medido"
            value={formatCurrencyFromNumber(summary?.measuredCostAmount ?? 0)}
            hint={`${summary?.measurementsApprovedCount ?? 0} de ${summary?.measurementsCount ?? 0} medição(ões) aprovada(s)`}
          />
          <SummaryMetric
            label="Diferença"
            value={formatCurrencyFromNumber(costDifference)}
            hint={costDifference >= 0 ? "dentro do previsto" : "acima do previsto"}
            tone={costDifference >= 0 ? "positive" : "negative"}
          />
        </div>
      </div>

      <div className={styles.summaryGroup}>
        <span className={styles.summaryGroupTitle}>Recebimento das unidades</span>
        <div className={styles.integrationGrid}>
          <SummaryMetric
            label="Vendido"
            value={formatCurrencyFromNumber(summary?.unitsSoldAmount ?? 0)}
            hint={`carteira de ${formatCurrencyFromNumber(summary?.unitsTotalAmount ?? 0)}`}
          />
          <SummaryMetric
            label="Recebido"
            value={formatCurrencyFromNumber(receivedAmount)}
            hint={receivableTotal > 0 ? `${receivedShare}% do que foi cobrado` : "nada cobrado ainda"}
            tone={receivedAmount > 0 ? "positive" : null}
          />
          <SummaryMetric
            label="A receber"
            value={formatCurrencyFromNumber(summary?.openAmount ?? 0)}
            hint={
              summary?.overdueCount
                ? `${formatCurrencyFromNumber(summary.overdueAmount)} vencido(s)`
                : "nenhuma parcela vencida"
            }
            tone={summary?.overdueCount ? "negative" : null}
          />
          <SummaryMetric
            label="Descontos"
            value={formatCurrencyFromNumber(summary?.discountAmount ?? 0)}
            hint="concedidos nas vendas"
          />
        </div>
      </div>

      <div className={styles.summaryGroup}>
        <span className={styles.summaryGroupTitle}>Execução</span>
        <div className={styles.integrationGrid}>
          <SummaryMetric
            label="Cronograma"
            value={`${scheduleAverage}%`}
            hint={`${schedulePhases.length} fase(s) cadastrada(s)`}
          />
          <SummaryMetric
            label="Medições pagas"
            value={formatCurrencyFromNumber(summary?.paidCostAmount ?? 0)}
            hint="já liquidadas no contas a pagar"
          />
        </div>
      </div>

      <article className={styles.integrationCard}>
        <h3>Alertas operacionais</h3>
        {alerts.length ? (
          <ul className={styles.alertList}>
            {alerts.map((alert) => (
              <li key={alert}>{alert}</li>
            ))}
          </ul>
        ) : (
          <p className={styles.textMuted}>Sem alertas críticos para a obra aberta.</p>
        )}
      </article>
    </div>
  )
}

function ReportsPanel({ units, schedulePhases, measurements }) {
  const approvedMeasurements = measurements.filter((measurement) => ["approved", "paid"].includes(measurement.status))
  const soldUnits = units.filter((unit) => ["sold", "delivered"].includes(unit.status))
  const inventoryValue = units.reduce((total, unit) => total + Number(unit.salePrice ?? 0), 0)
  const soldRevenue = soldUnits.reduce((total, unit) => total + Number(unit.salePrice ?? 0), 0)
  const measuredCost = approvedMeasurements.reduce(
    (total, measurement) => total + Number(measurement.netAmount ?? measurement.measuredAmount ?? 0),
    0
  )
  const estimatedMargin = soldRevenue - measuredCost
  const linkedReceivables = soldUnits.filter((unit) => unit.externalReceivableId).length
  const linkedPayables = approvedMeasurements.filter((measurement) => measurement.externalAccountsPayableId).length
  const phaseById = new Map(schedulePhases.map((phase) => [phase.id, phase]))
  const unitRows = units.map((unit) => {
    const unitMeasurements = approvedMeasurements.filter((measurement) => measurement.unitId === unit.id)
    const unitMeasuredCost = unitMeasurements.reduce(
      (total, measurement) => total + Number(measurement.netAmount ?? measurement.measuredAmount ?? 0),
      0
    )
    const unitSalePrice = Number(unit.salePrice ?? 0)

    return {
      unit,
      unitMeasuredCost,
      estimatedMargin: unitSalePrice - unitMeasuredCost,
      lastPhaseName: unitMeasurements[0]?.schedulePhaseId
        ? phaseById.get(unitMeasurements[0].schedulePhaseId)?.name ?? "-"
        : "-",
    }
  })
  const phaseRows = schedulePhases.map((phase) => {
    const phaseMeasurements = approvedMeasurements.filter((measurement) => measurement.schedulePhaseId === phase.id)
    const phaseCost = phaseMeasurements.reduce(
      (total, measurement) => total + Number(measurement.netAmount ?? measurement.measuredAmount ?? 0),
      0
    )

    return {
      phase,
      phaseCost,
      measurementsCount: phaseMeasurements.length,
      linkedPayables: phaseMeasurements.filter((measurement) => measurement.externalAccountsPayableId).length,
    }
  })

  const reportMetrics = [
    { label: "Carteira total", value: formatCurrencyFromNumber(inventoryValue), hint: `${units.length} unidade(s)` },
    { label: "Receita vendida", value: formatCurrencyFromNumber(soldRevenue), hint: `${soldUnits.length} venda(s)` },
    { label: "Custo medido", value: formatCurrencyFromNumber(measuredCost), hint: `${linkedPayables} AP vinculada(s)` },
    { label: "Margem estimada", value: formatCurrencyFromNumber(estimatedMargin), hint: `${linkedReceivables} AR vinculada(s)` },
  ]

  return (
    <div className={styles.integrationPanel}>
      <div className={styles.integrationGrid}>
        {reportMetrics.map((item) => (
          <article key={item.label} className={styles.integrationCard}>
            <h3>{item.label}</h3>
            <p className={styles.metricValue}>{item.value}</p>
            <p className={styles.metricHint}>{item.hint}</p>
          </article>
        ))}
      </div>

      <div className={styles.tableHeaderRow}>
        <h2>Resultado por unidade</h2>
        <span className={styles.badgeMuted}>{unitRows.length} unidade(s)</span>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Unidade</th>
              <th>Status</th>
              <th>Receita</th>
              <th>Custo medido</th>
              <th>Margem estimada</th>
              <th>Última etapa medida</th>
              <th>ERP</th>
            </tr>
          </thead>
          <tbody>
            {unitRows.map(({ unit, unitMeasuredCost, estimatedMargin: unitEstimatedMargin, lastPhaseName }) => (
              <tr key={unit.id}>
                <td>
                  <strong>{unit.code}</strong>
                  <p className={styles.rowSecondaryText}>{unit.description || unit.typology || "Sem descrição"}</p>
                </td>
                <td>{unitStatusLabel[unit.status] ?? unit.status}</td>
                <td>{formatCurrencyFromNumber(unit.salePrice ?? 0)}</td>
                <td>{formatCurrencyFromNumber(unitMeasuredCost)}</td>
                <td>{formatCurrencyFromNumber(unitEstimatedMargin)}</td>
                <td>{lastPhaseName}</td>
                <td>
                  {unit.externalReceivableId ? (
                    <span className={styles.badgeSuccess}>AR vinculada</span>
                  ) : (
                    <span className={styles.badgeMuted}>Pendente</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={styles.tableHeaderRow}>
        <h2>Custo por etapa</h2>
        <span className={styles.badgeMuted}>{phaseRows.length} etapa(s)</span>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Etapa</th>
              <th>Progresso</th>
              <th>Medições</th>
              <th>Custo aprovado</th>
              <th>AP vinculadas</th>
            </tr>
          </thead>
          <tbody>
            {phaseRows.map(({ phase, phaseCost, measurementsCount, linkedPayables: phaseLinkedPayables }) => (
              <tr key={phase.id}>
                <td>
                  <strong>{phase.name}</strong>
                  <p className={styles.rowSecondaryText}>Sequência {phase.sequenceOrder}</p>
                </td>
                <td>{phase.progressPercent}%</td>
                <td>{measurementsCount}</td>
                <td>{formatCurrencyFromNumber(phaseCost)}</td>
                <td>{phaseLinkedPayables}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ProjectDetailHeader({ project, units, schedulePhases, onBack, onEdit, onRefresh, loading }) {
  const unitList = units ?? []
  const soldUnits = unitList.filter((unit) => ["sold", "delivered"].includes(unit.status)).length
  const availableUnits = unitList.filter((unit) => unit.status === "available").length
  const portfolioTotal = unitList.reduce((total, unit) => total + Number(unit.salePrice ?? 0), 0)
  const soldTotal = unitList
    .filter((unit) => ["sold", "delivered"].includes(unit.status))
    .reduce((total, unit) => total + Number(unit.salePrice ?? 0), 0)

  const phases = schedulePhases ?? []
  const scheduleProgress = phases.length
    ? Math.round(
        phases.reduce((total, phase) => total + Number(phase.progressPercent ?? 0), 0) / phases.length,
      )
    : null
  const finishedPhases = phases.filter((phase) => phase.status === "completed").length

  const startLabel = formatDate(project.startDate)
  const endLabel = formatDate(project.expectedEndDate)
  const periodLabel =
    startLabel && endLabel
      ? `${startLabel} a ${endLabel}`
      : startLabel || endLabel || "Prazo não informado"
  const periodHint = startLabel && endLabel ? null : startLabel ? "sem fim previsto" : "sem data de início"

  return (
    <section className={styles.detailHeader}>
      <div className={styles.detailHeaderMain}>
        <button type="button" className={styles.secondaryButton} onClick={onBack}>
          <ChevronLeft size={16} />
          Obras
        </button>
        <div className={styles.detailTitleBlock}>
          <div className={styles.detailTitleRow}>
            <h2>{project.name}</h2>
            <span className={`${styles.statusPill} ${styles[`status${project.status}`] || ""}`}>
              {statusLabel[project.status] ?? project.status}
            </span>
            {project.analyticCostCenterId ? null : (
              <span className={styles.badgeMuted} title="A obra ainda não tem centro de custo no ERP">
                Centro de custo pendente
              </span>
            )}
          </div>
          <p className={styles.textMuted}>{project.code}</p>
        </div>
      </div>
      <div className={styles.detailMetaGrid}>
        <DetailMetaItem
          label="Tipo"
          value={projectTypeLabel[project.projectType] ?? project.projectType}
          hint={project.cnpjSpe ? `SPE ${project.cnpjSpe}` : null}
        />
        <DetailMetaItem label="Prazo" value={periodLabel} hint={periodHint} />
        <DetailMetaItem
          label="Unidades"
          value={unitList.length ? `${unitList.length}` : "Nenhuma cadastrada"}
          hint={unitList.length ? `${soldUnits} vendida(s) - ${availableUnits} disponível(is)` : null}
        />
        <DetailMetaItem
          label="Carteira"
          value={formatCurrencyFromNumber(portfolioTotal)}
          hint={soldTotal > 0 ? `${formatCurrencyFromNumber(soldTotal)} já vendido` : "nada vendido ainda"}
        />
        {scheduleProgress !== null ? (
          <DetailMetaItem
            label="Cronograma"
            value={`${scheduleProgress}% concluído`}
            hint={`${finishedPhases} de ${phases.length} etapa(s) finalizada(s)`}
          />
        ) : null}
      </div>
      <div className={styles.detailActions}>
        <button type="button" className={styles.secondaryButton} onClick={() => onEdit(project)}>
          <Pencil size={16} />
          Editar obra
        </button>
        <button type="button" className={styles.secondaryButton} onClick={onRefresh} disabled={loading}>
          <RefreshCw size={16} className={loading ? styles.spinIcon : undefined} />
          Recarregar
        </button>
      </div>
    </section>
  )
}

function DetailMetaItem({ label, value, hint = null }) {
  return (
    <div className={styles.detailMetaItem}>
      <span>{label}</span>
      <strong>{value || "-"}</strong>
      {hint ? <span className={styles.detailMetaHint}>{hint}</span> : null}
    </div>
  )
}

function ProjectList({ projects, loading, error, onRetry, onOpenDetails, onEdit, onDelete }) {
  if (loading) {
    return (
      <div className={styles.tableWrapper} aria-busy="true">
        <div className={styles.empty}>
          <RefreshCw className={styles.spinIcon} size={16} />
          Carregando obras...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>
          <span>{error}</span>
          <button type="button" className={styles.secondaryButton} onClick={onRetry}>
            <RefreshCw size={16} />
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }

  if (!projects.length) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>Nenhuma obra encontrada.</div>
      </div>
    )
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Código</th>
            <th>Obra</th>
            <th>Tipo</th>
            <th>Status</th>
            <th>Inicio</th>
            <th>Centro analítico</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.id}>
              <td>{project.code}</td>
              <td>
                <strong>{project.name}</strong>
                <div className={styles.rowSecondaryText}>{project.cnpjSpe || "-"}</div>
              </td>
              <td>{projectTypeLabel[project.projectType] ?? project.projectType ?? "-"}</td>
              <td>
                <span className={`${styles.statusPill} ${styles[`status${project.status}`] || ""}`}>
                  {statusLabel[project.status] ?? project.status}
                </span>
              </td>
              <td>{formatDate(project.startDate)}</td>
              <td>
                <span className={project.analyticCostCenterId ? styles.badgeSuccess : styles.badgeMuted}>
                  {project.analyticCostCenterId ? "Vinculado" : "Pendente"}
                </span>
              </td>
              <td>
                <RowActionsMenu
                  actions={[
                    {
                      key: "details",
                      label: "Detalhes",
                      icon: Building2,
                      onSelect: () => onOpenDetails(project),
                    },
                    {
                      key: "edit",
                      label: "Editar",
                      icon: Pencil,
                      onSelect: () => onEdit(project),
                    },
                    {
                      key: "delete",
                      label: "Excluir",
                      icon: Trash2,
                      danger: true,
                      dividerBefore: true,
                      onSelect: () => onDelete(project),
                    },
                  ]}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BlocksList({ blocks, loading, error, onRetry, onEdit, onDelete }) {
  if (loading) {
    return (
      <div className={styles.tableWrapper} aria-busy="true">
        <div className={styles.empty}>
          <RefreshCw className={styles.spinIcon} size={16} />
          Carregando blocos...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>
          <span>{error}</span>
          <button type="button" className={styles.secondaryButton} onClick={onRetry}>
            <RefreshCw size={16} />
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }

  if (!blocks.length) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>Nenhum bloco cadastrado para a obra selecionada.</div>
      </div>
    )
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Código</th>
            <th>Nome</th>
            <th>Pavimentos</th>
            <th>Status</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {blocks.map((block) => (
            <tr key={block.id}>
              <td>{block.code}</td>
              <td>{block.name}</td>
              <td>{block.floorsCount ?? "-"}</td>
              <td>
                <span className={`${styles.statusPill} ${styles[`status${block.status}`] || ""}`}>
                  {block.status === "active" ? "Ativo" : "Inativo"}
                </span>
              </td>
              <td>
                <RowActionsMenu
                  actions={[
                    {
                      key: "edit",
                      label: "Editar",
                      icon: Pencil,
                      onSelect: () => onEdit(block),
                    },
                    {
                      key: "delete",
                      label: "Excluir",
                      icon: Trash2,
                      danger: true,
                      dividerBefore: true,
                      onSelect: () => onDelete(block),
                    },
                  ]}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function UnitDetailPanel({
  unit,
  blocks,
  measurements,
  schedulePhases,
  activeTab,
  loadingMeasurements,
  measurementError,
  onTabChange,
  onEdit,
  onReserve,
  onRelease,
  onSale,
  onCreateMeasurement,
  onRetryMeasurements,
  onEditMeasurement,
  onDeleteMeasurement,
  onApproveMeasurement,
  onOpenMeasurementItems,
  onSubmitMeasurement,
  onRejectMeasurement,
  paymentPlan,
  loadingPaymentPlan,
  paymentPlanError,
  onRetryPaymentPlan,
  onEditInstallment,
  onPayInstallment,
  onDeleteInstallment,
  onDeleteAdjustment,
  onCreateInstallment,
  people,
  onCreateCommission,
  onSettleCommission,
  onDeleteCommission,
  onCreateAdjustment,
}) {
  const blockNameById = useMemo(() => {
    return Object.fromEntries(blocks.map((block) => [block.id, `${block.code} - ${block.name}`]))
  }, [blocks])
  const approvedMeasurements = measurements.filter((measurement) => ["approved", "paid"].includes(measurement.status))
  const measuredCost = approvedMeasurements.reduce(
    (total, measurement) => total + Number(measurement.netAmount ?? measurement.measuredAmount ?? 0),
    0
  )
  const openMeasurements = measurements.filter((measurement) => !["approved", "paid"].includes(measurement.status)).length
  const linkedPayables = measurements.filter((measurement) => measurement.externalAccountsPayableId).length
  const estimatedMargin = Number(unit.salePrice ?? 0) - measuredCost
  const canReserve = unit.status === "available"
  const canRelease = unit.status === "reserved"
  const canSale = (unit.status === "available" || unit.status === "reserved") && unit.analyticCostCenterId
  const canEditSale = unit.status === "sold" && Boolean(unit.analyticCostCenterId)

  return (
    <div className={styles.integrationPanel}>
      <div className={styles.scopeHeader}>
        <div className={styles.scopeMeta}>
          <div className={styles.detailTitleRow}>
            <h2>{unit.description || unit.code}</h2>
            <span className={`${styles.statusPill} ${styles[`status${unit.status}`] || ""}`}>
              {unitStatusLabel[unit.status] ?? unit.status}
            </span>
          </div>
          <p className={styles.textMuted}>{unit.unitType}{unit.typology ? ` - ${unit.typology}` : ""}</p>
        </div>
        <div className={styles.tableHeaderActions}>
          <button type="button" className={styles.secondaryButton} onClick={() => onEdit(unit)}>
            <Pencil size={16} />
            Editar
          </button>
          {canReserve ? (
            <button type="button" className={styles.secondaryButton} onClick={() => onReserve(unit)}>
              <Clock size={16} />
              Reservar
            </button>
          ) : null}
          {canRelease ? (
            <button type="button" className={styles.secondaryButton} onClick={() => onRelease(unit)}>
              <Unlock size={16} />
              Liberar
            </button>
          ) : null}
          {canSale ? (
            <button type="button" className={styles.primaryButton} onClick={() => onSale(unit)}>
              <ShoppingCart size={16} />
              Vender
            </button>
          ) : null}
        </div>
      </div>

      <div className={styles.detailMetaGrid}>
        <DetailMetaItem label="Bloco" value={unit.blockId ? blockNameById[unit.blockId] ?? unit.blockId : "-"} />
        <DetailMetaItem label="Centro unidade" value={unit.analyticCostCenterId ? "Vinculado" : "Pendente"} />
        <DetailMetaItem label="Preço" value={formatMoney(unit.salePrice)} />
        <DetailMetaItem
          label="Contrato ERP"
          value={
            unit.externalContractId
              ? translateErpStatus(erpContractStatusLabel, unit.externalContractStatus, "Vinculado")
              : "Pendente"
          }
        />
      </div>

      <section className={styles.tabCard}>
        <div className={styles.tabList}>
          {unitDetailTabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                type="button"
                className={`${styles.tabButton} ${activeTab === tab.id ? styles.tabButtonActive : ""}`}
                onClick={() => onTabChange(tab.id)}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            )
          })}
        </div>
      </section>

      {activeTab === "summary" ? (
        <div className={styles.integrationGrid}>
          <article className={styles.integrationCard}>
            <h3>Custo medido</h3>
            <p className={styles.metricValue}>{formatCurrencyFromNumber(measuredCost)}</p>
            <p className={styles.metricHint}>{linkedPayables} AP vinculada(s)</p>
          </article>
          <article className={styles.integrationCard}>
            <h3>Medições abertas</h3>
            <p className={styles.metricValue}>{openMeasurements}</p>
            <p className={styles.metricHint}>{measurements.length} medição(oes) no total</p>
          </article>
          <article className={styles.integrationCard}>
            <h3>Margem estimada</h3>
            <p className={styles.metricValue}>{formatCurrencyFromNumber(estimatedMargin)}</p>
            <p className={styles.metricHint}>preço menos custo aprovado</p>
          </article>
        </div>
      ) : null}

      {activeTab === "measurements" ? (
        <>
          <div className={styles.tableHeaderRow}>
            <div>
              <h2>Medições da unidade</h2>
              <p className={styles.textMuted}>AP e custos ficam amarrados ao centro analítico desta unidade.</p>
            </div>
            <button type="button" className={styles.primaryButton} onClick={() => onCreateMeasurement(unit)}>
              <Plus size={16} />
              Nova medição
            </button>
          </div>
          <MeasurementsList
            measurements={measurements}
            units={[unit]}
            schedulePhases={schedulePhases}
            loading={loadingMeasurements}
            error={measurementError}
            emptyMessage="Nenhuma medição cadastrada para esta unidade."
            onRetry={onRetryMeasurements}
            onEdit={onEditMeasurement}
            onDelete={onDeleteMeasurement}
            onApprove={onApproveMeasurement}
            onOpenItems={onOpenMeasurementItems}
            onSubmit={onSubmitMeasurement}
            onReject={onRejectMeasurement}
          />
        </>
      ) : null}

      {activeTab === "installments" ? (
        <UnitInstallmentsPanel
          unit={unit}
          plan={paymentPlan}
          loading={loadingPaymentPlan}
          error={paymentPlanError}
          onRetry={() => onRetryPaymentPlan(unit.id)}
          onSale={onSale}
          onEditInstallment={onEditInstallment}
          onPayInstallment={onPayInstallment}
          onDeleteInstallment={onDeleteInstallment}
          onCreateAdjustment={onCreateAdjustment}
          onDeleteAdjustment={onDeleteAdjustment}
          onCreateInstallment={onCreateInstallment}
        />
      ) : null}

      {activeTab === "commissions" ? (
        <UnitCommissionsPanel
          unit={unit}
          plan={paymentPlan}
          people={people}
          loading={loadingPaymentPlan}
          error={paymentPlanError}
          onRetry={() => onRetryPaymentPlan(unit.id)}
          onCreate={onCreateCommission}
          onSettle={onSettleCommission}
          onDelete={onDeleteCommission}
        />
      ) : null}

      {activeTab === "contract" ? (
        <UnitContractPanel
          unit={unit}
          plan={paymentPlan}
          loading={loadingPaymentPlan}
          error={paymentPlanError}
          onRetry={() => onRetryPaymentPlan(unit.id)}
        />
      ) : null}
    </div>
  )
}

function UnitInstallmentsPanel({
  unit,
  plan,
  loading,
  error,
  onRetry,
  onSale,
  onEditInstallment,
  onPayInstallment,
  onDeleteInstallment,
  onCreateAdjustment,
  onDeleteAdjustment,
  onCreateInstallment,
}) {
  const canSale = (unit.status === "available" || unit.status === "reserved") && unit.analyticCostCenterId
  const canEditSale = unit.status === "sold" && Boolean(unit.analyticCostCenterId)

  if (loading) {
    return (
      <div className={styles.empty} aria-busy="true">
        <RefreshCw className={styles.spinIcon} size={16} />
        Carregando composição e parcelas...
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.empty}>
        <span>{error}</span>
        <button type="button" className={styles.secondaryButton} onClick={onRetry}>
          <RefreshCw size={16} />
          Tentar novamente
        </button>
      </div>
    )
  }

  const composition = plan ?? {}
  const paymentPlan = composition.paymentPlan ?? {}
  const sources = composition.sources ?? []
  const installmentSources = sources.filter((source) => source.generatesInstallments)
  const settlementSources = sources.filter((source) => !source.generatesInstallments)
  const documentations = composition.documentations ?? []
  const installments = paymentPlan.installments ?? []
  const adjustments = paymentPlan.adjustments ?? []
  const canCreateAdjustment = Boolean(paymentPlan.contractId)
  const rows = [
    ...installments.map((installment) => ({
      ...installment,
      typeLabel: "Parcela",
      typeHint: "",
      receivableId: null,
      adjustment: null,
    })),
    ...adjustments.flatMap((adjustment, adjustmentIndex) =>
      adjustment.installments.map((installment) => ({
        ...installment,
        typeLabel: adjustments.length > 1 ? `Aditivo ${adjustmentIndex + 1}` : "Aditivo",
        typeHint: adjustment.reason || "",
        receivableId: adjustment.receivableId,
        adjustment,
      })),
    ),
  ].sort((first, second) => String(first.dueDate).localeCompare(String(second.dueDate)))

  return (
    <div className={styles.integrationPanel}>
      <div className={styles.integrationGrid}>
        <article className={styles.integrationCard}>
          <h3>Preço de venda</h3>
          <p className={styles.metricValue}>{formatMoney(composition.salePrice ?? unit.salePrice)}</p>
          <p className={styles.metricHint}>
            {composition.discountAmount > 0 ? `desconto de ${formatMoney(composition.discountAmount)}` : "sem desconto"}
          </p>
        </article>
        <article className={styles.integrationCard}>
          <h3>Liberado pelo banco</h3>
          <p className={styles.metricValue}>{formatMoney(composition.settlementTotal)}</p>
          <p className={styles.metricHint}>subsídio, FGTS e financiamento - não geram parcela</p>
        </article>
        <article className={styles.integrationCard}>
          <h3>Documentação</h3>
          <p className={styles.metricValue}>{formatMoney(composition.documentationTotal)}</p>
          <p className={styles.metricHint}>
            {documentations.length
              ? `${documentations.length} item(ns), diluída no saldo`
              : "sem documentação"}
          </p>
        </article>
        <article className={styles.integrationCard}>
          <h3>Cobrado em parcelas</h3>
          <p className={styles.metricValue}>{formatMoney(composition.installmentTotal)}</p>
          <p className={styles.metricHint}>{installments.length} parcela(s) no contas a receber</p>
        </article>
        <article className={styles.integrationCard}>
          <h3>Sinal do corretor</h3>
          <p className={styles.metricValue}>{formatMoney(composition.commissionTotal)}</p>
          <p className={styles.metricHint}>
            {Number(composition.commissionOffset ?? 0) > 0
              ? `${formatMoney(composition.commissionOffset)} já abatido do saldo`
              : "pago direto ao corretor, fora do contas a receber"}
          </p>
        </article>
        <article className={styles.integrationCard}>
          <h3>Em aberto</h3>
          <p className={styles.metricValue}>{formatMoney(paymentPlan.openTotal)}</p>
          <p className={styles.metricHint}>
            {paymentPlan.overdueCount ? `${paymentPlan.overdueCount} vencida(s)` : "nenhuma vencida"}
            {paymentPlan.paidTotal ? ` - ${formatMoney(paymentPlan.paidTotal)} pago` : ""}
          </p>
        </article>
      </div>

      <div className={styles.card}>
        <strong>Como a venda foi composta</strong>
        <p className={styles.metricHint}>
          O que o banco libera (subsídio, FGTS e financiamento) entra no preço da venda mas não vira parcela: a
          data de pagamento depende da liberação. A <strong>documentação</strong> é cobrada do comprador junto
          do preço. O que sobra do preço mais a documentação, depois do desconto, da entrada e dessas
          liberações, é o <strong>saldo</strong>, e são a entrada e o saldo que o comprador paga em parcelas no
          contas a receber.
        </p>
        {sources.length ? (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Fonte</th>
                  <th>Valor</th>
                  <th>Composição</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {installmentSources.concat(settlementSources).map((source) => (
                  <tr key={source.sourceType}>
                    <td>
                      <strong>{source.label}</strong>
                      <div className={styles.rowSecondaryText}>
                        {source.generatesInstallments ? "cobrado do comprador" : "liberado pelo banco"}
                      </div>
                    </td>
                    <td>{formatMoney(source.amount)}</td>
                    <td>
                      {source.generatesInstallments
                        ? `${source.installments} x ${formatMoney(Number(source.amount ?? 0) / Math.max(source.installments, 1))}`
                        : "a vista, sem parcela"}
                    </td>
                    <td>{source.dueDate ? formatDate(source.dueDate) : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={styles.metricHint}>
            {canSale
              ? "Unidade ainda não vendida - confirme a venda para compor o valor."
              : "Sem composição registrada para esta unidade."}
          </p>
        )}
        {documentations.length ? (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Documentação</th>
                  <th>Valor</th>
                </tr>
              </thead>
              <tbody>
                {documentations.map((documentation) => (
                  <tr key={documentation.id}>
                    <td>{documentation.name}</td>
                    <td>{formatMoney(documentation.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {canSale || canEditSale ? (
          <div className={styles.filtersFooter}>
            <button type="button" className={styles.primaryButton} onClick={() => onSale(unit)}>
              <ShoppingCart size={16} />
              {canEditSale ? "Editar venda" : "Confirmar venda"}
            </button>
          </div>
        ) : null}
      </div>

      <div className={styles.card}>
        <div className={styles.tableHeaderRow}>
          <div>
            <strong>Contas a receber da unidade</strong>
            <p className={styles.metricHint}>
              As duas séries do legado na mesma lista: <strong>Parcela</strong> é o parcelamento da
              venda e <strong>Aditivo</strong> é a cobrança extra de quando o financiamento sai abaixo
              do previsto. Cada tipo tem a sua própria numeração, e o aditivo é um documento separado
              no contas a receber - editar a venda não mexe nele.
            </p>
          </div>
          <div className={styles.tableHeaderActions}>
            {paymentPlan.receivableId ? (
              <button
                type="button"
                className={styles.secondaryButton}
                onClick={() => onCreateInstallment({ receivableId: null, installments })}
              >
                <Plus size={16} />
                Incluir parcela
              </button>
            ) : null}
            {canCreateAdjustment ? (
              <button type="button" className={styles.secondaryButton} onClick={onCreateAdjustment}>
                <Plus size={16} />
                Lançar aditivo
              </button>
            ) : null}
          </div>
        </div>
        {paymentPlan.erpUnavailableReason ? (
          <p className={styles.metricHint}>
            Não foi possível consultar o ERP agora: {paymentPlan.erpUnavailableReason}
          </p>
        ) : null}
        {rows.length ? (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Parcela</th>
                  <th>Origem</th>
                  <th>Vencimento</th>
                  <th>Valor</th>
                  <th>Pago</th>
                  <th>Status</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.typeLabel}</strong>
                      {row.typeHint ? (
                        <div className={styles.rowSecondaryText}>{row.typeHint}</div>
                      ) : null}
                    </td>
                    <td>
                      <strong>
                        {row.installmentNumber}/{row.totalInstallments}
                      </strong>
                    </td>
                    <td>{row.documentNumber || "-"}</td>
                    <td>{formatDate(row.dueDate)}</td>
                    <td>{formatMoney(row.amount)}</td>
                    <td>
                      {row.paymentDate ? formatDate(row.paymentDate) : "-"}
                      <div className={styles.rowSecondaryText}>
                        {row.paidAmount ? formatMoney(row.paidAmount) : ""}
                      </div>
                    </td>
                    <td>
                      <span className={`${styles.statusPill} ${styles[`status${row.status}`] || ""}`}>
                        {receivableInstallmentStatusLabel[row.status] ?? row.status}
                      </span>
                    </td>
                    <td className={styles.actionsCell}>
                      <RowActionsMenu
                        actions={buildInstallmentActions({
                          installment: row,
                          adjustment: row.adjustment,
                          onEditInstallment,
                          onPayInstallment,
                          onDeleteInstallment,
                          onDeleteAdjustment,
                        })}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={styles.metricHint}>
            {unit.externalReceivableId
              ? "O recebível existe no ERP mas não retornou parcelas."
              : "Nenhuma parcela gerada - a venda ainda não foi confirmada ou o ERP não respondeu."}
          </p>
        )}
      </div>
    </div>
  )
}

function buildInstallmentActions({
  installment,
  adjustment,
  onEditInstallment,
  onPayInstallment,
  onDeleteInstallment,
  onDeleteAdjustment,
}) {
  const isPaid = installment.status === "PAID"
  const actions = [
    {
      key: "edit",
      label: "Editar parcela",
      icon: Pencil,
      onSelect: () => onEditInstallment(installment),
    },
  ]

  // Parcela paga não reabre por aqui: o estorno é do Contas a Receber, e a
  // exclusão de uma parcela já recebida apagaria o recebimento junto.
  if (!isPaid) {
    actions.push({
      key: "pay",
      label: "Marcar como pago",
      icon: CheckCircle,
      onSelect: () => onPayInstallment(installment),
    })
    actions.push({
      key: "delete",
      label: "Excluir parcela",
      icon: Trash2,
      danger: true,
      onSelect: () => onDeleteInstallment(installment),
    })
  }

  // O aditivo é um documento inteiro: excluí-lo cancela todas as parcelas dele
  // de uma vez, e é o que se faz quando o aditivo não deveria existir.
  if (adjustment) {
    actions.push({
      key: "delete-adjustment",
      label: "Excluir aditivo inteiro",
      icon: Trash2,
      danger: true,
      onSelect: () => onDeleteAdjustment(adjustment),
    })
  }

  return actions
}

function CreateInstallmentModal({ unit, form, onClose, onChange, onSubmit, loading }) {
  const isAdjustment = Boolean(form.receivableId)

  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Incluir parcela"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Incluir parcela{unit ? ` - unidade ${unit.code}` : ""}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <p className={styles.metricHint}>
            A numeração segue a partir do número informado, e um número que já existe na série é
            recusado. O valor sai do saldo do título que ainda não virou parcela: para cobrar a mais do
            comprador, o caminho é <strong>lançar aditivo</strong>.
          </p>
          {!isAdjustment ? (
            <p className={styles.metricHint}>
              Esta parcela entra na série da <strong>venda</strong> - editar a venda depois refaz as
              parcelas em aberto e ela é reescrita junto. O que precisa sobreviver a isso é aditivo.
            </p>
          ) : null}
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Número da parcela*</span>
              <input
                type="number"
                min="1"
                value={form.startingNumber}
                onChange={(event) => onChange("startingNumber", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Repetir</span>
              <input
                type="number"
                min="1"
                max="60"
                value={form.count}
                onChange={(event) => onChange("count", event.target.value)}
              />
              <small className={styles.fieldHint}>
                gera uma parcela por mês, numerando a partir do número informado
              </small>
            </label>
            <label className={styles.filterControl}>
              <span>Primeiro vencimento*</span>
              <input
                type="date"
                value={form.firstDueDate}
                onChange={(event) => onChange("firstDueDate", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Valor de cada parcela</span>
              <input
                type="text"
                inputMode="decimal"
                value={form.amount}
                onChange={(event) => onChange("amount", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
              />
              <small className={styles.fieldHint}>em branco divide o saldo que falta parcelar</small>
            </label>
          </div>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Incluindo..." : "Incluir parcela"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function PayInstallmentModal({ installment, form, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Marcar parcela como paga"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>
            Baixar parcela {installment?.installmentNumber}/{installment?.totalInstallments}
          </h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <p className={styles.metricHint}>
            Vencimento {formatDate(installment?.dueDate)} - valor da parcela{" "}
            {formatMoney(installment?.amount)}
            {Number(installment?.paidAmount) > 0
              ? `, ja recebido ${formatMoney(installment.paidAmount)}, saldo ${formatMoney(
                  installmentOutstanding(installment),
                )}`
              : ""}
            . Cada recebimento gera o seu lançamento contábil, e o recibo sai provisório enquanto
            sobrar saldo.
          </p>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Forma de pagamento*</span>
              <select
                value={form.paymentMethod}
                onChange={(event) => onChange("paymentMethod", event.target.value)}
                required
              >
                {installmentPaymentMethodOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.filterControl}>
              <span>Data do pagamento</span>
              <input
                type="date"
                value={form.paidAt}
                onChange={(event) => onChange("paidAt", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Valor a receber</span>
              <input
                type="text"
                inputMode="decimal"
                value={form.paidAmount}
                onChange={(event) => onChange("paidAmount", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
              />
            </label>
            <label className={styles.filterControl}>
              <span>Juros</span>
              <input
                type="text"
                inputMode="decimal"
                value={form.interest}
                onChange={(event) => onChange("interest", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
              />
            </label>
            <label className={styles.filterControl}>
              <span>Multa</span>
              <input
                type="text"
                inputMode="decimal"
                value={form.fine}
                onChange={(event) => onChange("fine", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
              />
            </label>
            <label className={styles.filterControl}>
              <span>Desconto</span>
              <input
                type="text"
                inputMode="decimal"
                value={form.discount}
                onChange={(event) => onChange("discount", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
              />
            </label>
            <label className={`${styles.filterControl} ${styles.spanTwoColumns}`}>
              <span>Observação</span>
              <textarea
                className={styles.textarea}
                value={form.observation}
                onChange={(event) => onChange("observation", event.target.value)}
              />
            </label>
          </div>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Baixando..." : "Marcar como pago"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function DeleteAdjustmentModal({ adjustment, reason, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Excluir aditivo"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Excluir aditivo</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <p className={styles.metricHint}>
            {adjustment?.description || "Aditivo da venda"} - {formatMoney(adjustment?.totalAmount)} em{" "}
            {adjustment?.installments?.length ?? 0} parcela(s). Todas as parcelas são canceladas e os
            lançamentos contábeis desfeitos. A justificativa fica na trilha de auditoria do ERP.
          </p>
          <label className={styles.filterControl}>
            <span>Justificativa*</span>
            <textarea
              className={styles.textarea}
              value={reason}
              onChange={(event) => onChange(event.target.value)}
              required
            />
          </label>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading || !reason.trim()}>
              {loading ? "Excluindo..." : "Excluir aditivo"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function UnitCommissionsPanel({
  unit,
  plan,
  people,
  loading,
  error,
  onRetry,
  onCreate,
  onSettle,
  onDelete,
}) {
  if (loading) {
    return (
      <div className={styles.empty} aria-busy="true">
        <RefreshCw className={styles.spinIcon} size={16} />
        Carregando sinal da unidade...
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.empty}>
        <span>{error}</span>
        <button type="button" className={styles.secondaryButton} onClick={onRetry}>
          <RefreshCw size={16} />
          Tentar novamente
        </button>
      </div>
    )
  }

  const composition = plan ?? {}
  const commissions = composition.commissions ?? []
  const personNameById = Object.fromEntries((people ?? []).map((person) => [person.id, person.name]))

  return (
    <div className={styles.integrationPanel}>
      <div className={styles.integrationGrid}>
        <article className={styles.integrationCard}>
          <h3>Sinal lançado</h3>
          <p className={styles.metricValue}>{formatMoney(composition.commissionTotal)}</p>
          <p className={styles.metricHint}>{commissions.length} lançamento(s)</p>
        </article>
        <article className={styles.integrationCard}>
          <h3>Sinal pago ao corretor</h3>
          <p className={styles.metricValue}>{formatMoney(composition.commissionPaidTotal)}</p>
          <p className={styles.metricHint}>o dinheiro não passa pelo caixa da construtora</p>
        </article>
        <article className={styles.integrationCard}>
          <h3>Abatido do saldo</h3>
          <p className={styles.metricValue}>{formatMoney(composition.commissionOffset)}</p>
          <p className={styles.metricHint}>só o sinal pago que compõe a venda</p>
        </article>
      </div>

      <div className={styles.card}>
        <div className={styles.tableHeaderRow}>
          <div>
            <strong>Sinal (comissão do corretor)</strong>
            <p className={styles.metricHint}>
              O sinal é pago pelo comprador direto ao corretor, então não vira conta a receber da
              construtora. Marcado como <strong>&quot;compõe o valor da venda&quot;</strong>, ele faz parte do
              preço: quando pago, reduz o saldo que o comprador ainda deve. Desmarcado, é cobrança por
              fora e o saldo não muda.
            </p>
          </div>
          <button type="button" className={styles.primaryButton} onClick={onCreate}>
            <Plus size={16} />
            Incluir sinal
          </button>
        </div>
        {commissions.length ? (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Parcela</th>
                  <th>Favorecido</th>
                  <th>Vencimento</th>
                  <th>Valor</th>
                  <th>Composição</th>
                  <th>Pagamento</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {commissions.map((commission) => (
                  <tr key={commission.id}>
                    <td>
                      <strong>{commission.sequenceNumber}</strong>
                    </td>
                    <td>
                      {personNameById[commission.beneficiaryPersonId] ?? commission.beneficiaryPersonId}
                      {commission.documentNumber ? (
                        <div className={styles.rowSecondaryText}>{commission.documentNumber}</div>
                      ) : null}
                    </td>
                    <td>{formatDate(commission.dueDate)}</td>
                    <td>{formatMoney(commission.amount)}</td>
                    <td>{commission.composesSalePrice ? "Compõe a venda" : "Cobrado por fora"}</td>
                    <td>
                      {commission.paymentDate ? formatDate(commission.paymentDate) : "Em aberto"}
                    </td>
                    <td className={styles.actionsCell}>
                      <RowActionsMenu
                        actions={[
                          {
                            key: "settle",
                            label: commission.paymentDate ? "Estornar baixa" : "Baixar sinal",
                            icon: CheckCircle,
                            onSelect: () => onSettle(commission),
                          },
                          {
                            key: "delete",
                            label: "Excluir",
                            icon: Trash2,
                            danger: true,
                            onSelect: () => onDelete(commission),
                          },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={styles.metricHint}>
            {unit.status === "sold"
              ? "Nenhum sinal lançado para esta unidade."
              : "Nenhum sinal lançado - o sinal pode ser lançado antes mesmo da venda."}
          </p>
        )}
      </div>
    </div>
  )
}

function CommissionModal({
  unit,
  commissionForm,
  people,
  loadingPeople,
  personLookupError,
  onClose,
  onChange,
  onSubmit,
  loading,
}) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Incluir sinal"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Incluir sinal{unit ? ` - unidade ${unit.code}` : ""}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <PersonIdInput
              label="Corretor favorecido*"
              value={commissionForm.beneficiaryPersonId}
              onChange={(value) => onChange("beneficiaryPersonId", value)}
              people={people}
              required
              loading={loadingPeople}
              error={personLookupError}
              emptyLabel="Selecione o corretor"
            />
            <label className={styles.filterControl}>
              <span>Valor da parcela*</span>
              <input
                type="text"
                inputMode="decimal"
                value={commissionForm.amount}
                onChange={(event) => onChange("amount", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Primeiro vencimento*</span>
              <input
                type="date"
                value={commissionForm.dueDate}
                onChange={(event) => onChange("dueDate", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Repetir</span>
              <input
                type="number"
                min="1"
                max="120"
                value={commissionForm.installments}
                onChange={(event) => onChange("installments", event.target.value)}
              />
              <small className={styles.fieldHint}>gera uma parcela por mês a partir do vencimento</small>
            </label>
            <label className={styles.filterControl}>
              <span>Documento</span>
              <input
                type="text"
                value={commissionForm.documentNumber}
                onChange={(event) => onChange("documentNumber", event.target.value)}
              />
            </label>
            <label className={`${styles.filterControl} ${styles.spanTwoColumns}`}>
              <span>Observação</span>
              <textarea
                className={styles.textarea}
                value={commissionForm.notes}
                onChange={(event) => onChange("notes", event.target.value)}
              />
            </label>
            <label className={`${styles.checkboxControl} ${styles.spanTwoColumns}`}>
              <input
                type="checkbox"
                checked={commissionForm.composesSalePrice}
                onChange={(event) => onChange("composesSalePrice", event.target.checked)}
              />
              <span>
                Compõe o valor da venda
                <small className={styles.fieldHint}>
                  Marcado, o sinal faz parte do preço: quando pago, reduz o saldo que o comprador deve à
                  construtora. Desmarcado, é cobrança por fora e o saldo não muda.
                </small>
              </span>
            </label>
          </div>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Lançando..." : "Lançar sinal"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function AdjustmentModal({ unit, adjustmentForm, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Lançar aditivo"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Lançar aditivo{unit ? ` - unidade ${unit.code}` : ""}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <p className={styles.metricHint}>
            O aditivo é a cobrança extra de quando o financiamento sai abaixo do previsto. Ele vira um
            documento próprio no contas a receber, com numeração separada - editar a venda depois não
            mexe nele.
          </p>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Valor total*</span>
              <input
                type="text"
                inputMode="decimal"
                value={adjustmentForm.amount}
                onChange={(event) => onChange("amount", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Parcelas*</span>
              <input
                type="number"
                min="1"
                max="120"
                value={adjustmentForm.installments}
                onChange={(event) => onChange("installments", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Primeiro vencimento*</span>
              <input
                type="date"
                value={adjustmentForm.firstDueDate}
                onChange={(event) => onChange("firstDueDate", event.target.value)}
                required
              />
            </label>
            <label className={`${styles.filterControl} ${styles.spanTwoColumns}`}>
              <span>Motivo</span>
              <input
                type="text"
                value={adjustmentForm.reason}
                onChange={(event) => onChange("reason", event.target.value)}
                placeholder="Financiamento aprovado abaixo do previsto"
              />
            </label>
          </div>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Lançando..." : "Lançar aditivo"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function UnitContractPanel({ unit, plan, loading, error, onRetry }) {
  if (loading) {
    return (
      <div className={styles.empty} aria-busy="true">
        <RefreshCw className={styles.spinIcon} size={16} />
        Carregando contrato...
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.empty}>
        <span>{error}</span>
        <button type="button" className={styles.secondaryButton} onClick={onRetry}>
          <RefreshCw size={16} />
          Tentar novamente
        </button>
      </div>
    )
  }

  const paymentPlan = plan?.paymentPlan ?? {}

  return (
    <div className={styles.integrationPanel}>
      <div className={styles.integrationGrid}>
        <article className={styles.integrationCard}>
          <h3>Contrato</h3>
          <p className={styles.metricValue}>{paymentPlan.contractCode || "Pendente"}</p>
          <p className={styles.metricHint}>
            {translateErpStatus(erpContractStatusLabel, paymentPlan.contractStatus, "sem status no ERP")}
          </p>
        </article>
        <article className={styles.integrationCard}>
          <h3>Assinatura</h3>
          <p className={styles.metricValue}>
            {unit.contractSignatureDate ? formatDate(unit.contractSignatureDate) : "-"}
          </p>
          <p className={styles.metricHint}>data informada na confirmação da venda</p>
        </article>
        <article className={styles.integrationCard}>
          <h3>Recebível vinculado</h3>
          <p className={styles.metricValue}>{paymentPlan.receivableId ? "Sim" : "Pendente"}</p>
          <p className={styles.metricHint}>
            {translateErpStatus(erpReceivableStatusLabel, paymentPlan.receivableStatus, "sem recebível")}
          </p>
        </article>
      </div>

      {unit.saleNotes ? (
        <div className={styles.card}>
          <strong>Observação da venda</strong>
          <p className={styles.metricHint}>{unit.saleNotes}</p>
        </div>
      ) : null}

      <div className={styles.card}>
        <strong>Conteúdo do contrato</strong>
        {paymentPlan.contractContentHtml ? (
          <div
            className={styles.contractContent}
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: paymentPlan.contractContentHtml }}
          />
        ) : (
          <p className={styles.metricHint}>
            {paymentPlan.contractId
              ? "O contrato existe no ERP mas não trouxe conteúdo."
              : "Nenhum contrato gerado - confirme a venda da unidade."}
          </p>
        )}
      </div>
    </div>
  )
}

const installmentPaymentMethodOptions = [
  { value: "PIX", label: "PIX" },
  { value: "BOLETO", label: "Boleto" },
  { value: "TRANSFER", label: "Transferência" },
  { value: "CASH", label: "Dinheiro" },
  { value: "CREDIT_CARD", label: "Cartão de crédito" },
  { value: "DEBIT_CARD", label: "Cartão de débito" },
]

function EditInstallmentModal({ installment, form, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Editar parcela"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>
            Editar parcela {installment?.installmentNumber}/{installment?.totalInstallments}
          </h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <p className={styles.metricHint}>
            Vencimento e valor são definidos na confirmação da venda e não mudam por aqui.
          </p>

          <label className={styles.filterControl}>
            <span>Forma de pagamento</span>
            <select
              className={styles.select}
              value={form.paymentMethod}
              onChange={(event) => onChange("paymentMethod", event.target.value)}
            >
              <option value="">Selecione</option>
              {installmentPaymentMethodOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.filterControl}>
            <span>Número do documento</span>
            <input
              className={styles.input}
              value={form.documentNumber}
              maxLength={100}
              onChange={(event) => onChange("documentNumber", event.target.value)}
            />
          </label>

          <label className={styles.filterControl}>
            <span>Observação</span>
            <textarea
              className={styles.textarea}
              value={form.observation}
              onChange={(event) => onChange("observation", event.target.value)}
            />
          </label>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Salvando..." : "Salvar parcela"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function RowActionsMenu({ label = "Ações", actions }) {
  const [isOpen, setIsOpen] = useState(false)
  const [menuPosition, setMenuPosition] = useState(null)
  const wrapperRef = useRef(null)

  const visibleActions = actions.filter((action) => action.visible !== false)

  const updateMenuPosition = useCallback(() => {
    if (!wrapperRef.current) {
      return
    }

    const triggerRect = wrapperRef.current.getBoundingClientRect()
    const estimatedHeight = visibleActions.length * 40 + 16
    const opensUpwards = triggerRect.bottom + estimatedHeight > window.innerHeight
    setMenuPosition({
      top: opensUpwards ? Math.max(triggerRect.top - estimatedHeight - 6, 8) : triggerRect.bottom + 6,
      right: Math.max(window.innerWidth - triggerRect.right, 8),
    })
  }, [visibleActions.length])

  useEffect(() => {
    if (!isOpen) {
      return undefined
    }

    updateMenuPosition()

    const handleClickOutside = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    const handleDismiss = () => setIsOpen(false)

    document.addEventListener("mousedown", handleClickOutside)
    window.addEventListener("resize", handleDismiss)
    window.addEventListener("scroll", handleDismiss, true)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
      window.removeEventListener("resize", handleDismiss)
      window.removeEventListener("scroll", handleDismiss, true)
    }
  }, [isOpen, updateMenuPosition])

  if (!visibleActions.length) {
    return <span className={styles.badgeMuted}>-</span>
  }

  const triggerClassName = isOpen
    ? `${styles.actionsTrigger} ${styles.actionsTriggerOpen}`
    : styles.actionsTrigger
  const chevronClassName = isOpen
    ? `${styles.actionsChevron} ${styles.actionsChevronOpen}`
    : styles.actionsChevron

  return (
    <div className={styles.actionsDropdownWrapper} ref={wrapperRef}>
      <button
        type="button"
        className={triggerClassName}
        onClick={() => setIsOpen((previous) => !previous)}
        aria-expanded={isOpen}
        aria-haspopup="menu"
      >
        {label}
        <ChevronDown size={14} className={chevronClassName} />
      </button>

      {isOpen && menuPosition ? (
        <div className={styles.actionsDropdown} role="menu" style={menuPosition}>
          {visibleActions.flatMap((action, index) => {
            const ActionIcon = action.icon
            const itemClassName = action.danger
              ? `${styles.actionsDropdownItem} ${styles.actionsDropdownItemDanger}`
              : styles.actionsDropdownItem
            const renderedAction = (
              <button
                key={action.key}
                type="button"
                role="menuitem"
                className={itemClassName}
                onClick={() => {
                  setIsOpen(false)
                  action.onSelect()
                }}
                disabled={action.disabled}
              >
                {ActionIcon ? <ActionIcon size={16} /> : null}
                <span>{action.label}</span>
              </button>
            )

            if (action.dividerBefore && index > 0) {
              return [
                <div key={`${action.key}-divider`} className={styles.actionsDropdownDivider} />,
                renderedAction,
              ]
            }

            return [renderedAction]
          })}
        </div>
      ) : null}
    </div>
  )
}

function UnitsList({ units, blocks, loading, error, onRetry, onOpenDetails, onEdit, onDelete, onReserve, onRelease, onSale }) {
  const blockNameById = useMemo(() => {
    return Object.fromEntries(blocks.map((block) => [block.id, `${block.code} - ${block.name}`]))
  }, [blocks])

  if (loading) {
    return (
      <div className={styles.tableWrapper} aria-busy="true">
        <div className={styles.empty}>
          <RefreshCw className={styles.spinIcon} size={16} />
          Carregando unidades...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>
          <span>{error}</span>
          <button type="button" className={styles.secondaryButton} onClick={onRetry}>
            <RefreshCw size={16} />
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }

  if (!units.length) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>Nenhuma unidade cadastrada para a obra selecionada.</div>
      </div>
    )
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Descrição</th>
            <th>Tipo</th>
            <th>Bloco</th>
            <th>Status</th>
            <th>Centro unidade</th>
            <th>Preço</th>
            <th>Contrato ERP</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {units.map((unit) => {
            const canReserve = unit.status === "available"
            const canRelease = unit.status === "reserved"
            const canSale = (unit.status === "available" || unit.status === "reserved") && unit.analyticCostCenterId
  const canEditSale = unit.status === "sold" && Boolean(unit.analyticCostCenterId)

            return (
              <tr key={unit.id}>
                <td>
                  <strong>{unit.description || unit.code}</strong>
                  <div className={styles.rowSecondaryText}>{unit.code}</div>
                </td>
                <td>
                  <strong>{unit.unitType}</strong>
                  <div className={styles.rowSecondaryText}>{unit.typology || "-"}</div>
                </td>
                <td>{unit.blockId ? blockNameById[unit.blockId] ?? unit.blockId : "-"}</td>
                <td>
                  <span className={`${styles.statusPill} ${styles[`status${unit.status}`] || ""}`}>
                    {unitStatusLabel[unit.status] ?? unit.status}
                  </span>
                </td>
                <td>
                  <span className={unit.analyticCostCenterId ? styles.badgeSuccess : styles.badgeMuted}>
                    {unit.analyticCostCenterId ? "Vinculado" : "Pendente"}
                  </span>
                </td>
                <td>{formatMoney(unit.salePrice)}</td>
                <td>
                  {unit.externalContractId ? (
                    <div>
                      <div className={styles.rowSecondaryText}>
                        {translateErpStatus(erpContractStatusLabel, unit.externalContractStatus, "Ativo")}
                      </div>
                      <span className={styles.badgeSuccess}>Vinculado</span>
                    </div>
                  ) : (
                    <span className={styles.badgeMuted}>Pendente</span>
                  )}
                </td>
                <td>
                  <RowActionsMenu
                    actions={[
                      {
                        key: "details",
                        label: "Detalhes",
                        icon: Home,
                        onSelect: () => onOpenDetails(unit),
                      },
                      {
                        key: "edit",
                        label: "Editar",
                        icon: Pencil,
                        onSelect: () => onEdit(unit),
                      },
                      {
                        key: "reserve",
                        label: "Reservar",
                        icon: Clock,
                        visible: canReserve,
                        dividerBefore: true,
                        onSelect: () => onReserve(unit),
                      },
                      {
                        key: "release",
                        label: "Liberar reserva",
                        icon: Unlock,
                        visible: canRelease,
                        dividerBefore: true,
                        onSelect: () => onRelease(unit),
                      },
                      {
                        key: "sale",
                        label: canEditSale ? "Editar venda" : "Confirmar venda",
                        icon: ShoppingCart,
                        visible: canSale || canEditSale,
                        dividerBefore: !canReserve && !canRelease,
                        onSelect: () => onSale(unit),
                      },
                      {
                        key: "delete",
                        label: "Excluir",
                        icon: Trash2,
                        danger: true,
                        dividerBefore: true,
                        onSelect: () => onDelete(unit),
                      },
                    ]}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ScheduleList({ phases, loading, error, onRetry, onEdit, onDelete }) {
  if (loading) {
    return (
      <div className={styles.tableWrapper} aria-busy="true">
        <div className={styles.empty}>
          <RefreshCw className={styles.spinIcon} size={16} />
          Carregando cronograma...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>
          <span>{error}</span>
          <button type="button" className={styles.secondaryButton} onClick={onRetry}>
            <RefreshCw size={16} />
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }

  if (!phases.length) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>Nenhuma fase cadastrada para a obra selecionada.</div>
      </div>
    )
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Ordem</th>
            <th>Fase</th>
            <th>Status</th>
            <th>Inicio previsto</th>
            <th>Fim previsto</th>
            <th>Progresso</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {phases.map((phase) => (
            <tr key={phase.id}>
              <td>{phase.sequenceOrder}</td>
              <td>{phase.name}</td>
              <td>
                <span className={`${styles.statusPill} ${styles[`status${phase.status}`] || ""}`}>
                  {scheduleStatusLabel[phase.status] ?? phase.status}
                </span>
              </td>
              <td>{formatDate(phase.plannedStartDate)}</td>
              <td>{formatDate(phase.plannedEndDate)}</td>
              <td>{Number(phase.progressPercent ?? 0)}%</td>
              <td>
                <RowActionsMenu
                  actions={[
                    {
                      key: "edit",
                      label: "Editar",
                      icon: Pencil,
                      onSelect: () => onEdit(phase),
                    },
                    {
                      key: "delete",
                      label: "Excluir",
                      icon: Trash2,
                      danger: true,
                      dividerBefore: true,
                      onSelect: () => onDelete(phase),
                    },
                  ]}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MeasurementsList({
  measurements,
  units,
  schedulePhases,
  loading,
  error,
  emptyMessage = "Nenhuma medição cadastrada para a obra selecionada.",
  onRetry,
  onEdit,
  onDelete,
  onApprove,
  onReject,
  onOpenItems,
  onSubmit,
}) {
  const unitNameById = useMemo(() => {
    return Object.fromEntries(units.map((unit) => [unit.id, `${unit.code} - ${unit.description || unit.unitType}`]))
  }, [units])
  const phaseNameById = useMemo(() => {
    return Object.fromEntries(schedulePhases.map((phase) => [phase.id, phase.name]))
  }, [schedulePhases])

  if (loading) {
    return (
      <div className={styles.tableWrapper} aria-busy="true">
        <div className={styles.empty}>
          <RefreshCw className={styles.spinIcon} size={16} />
          Carregando medições...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>
          <span>{error}</span>
          <button type="button" className={styles.secondaryButton} onClick={onRetry}>
            <RefreshCw size={16} />
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }

  if (!measurements.length) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>{emptyMessage}</div>
      </div>
    )
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Código</th>
            <th>Unidade</th>
            <th>Tipo</th>
            <th>Status</th>
            <th>Itens / inspeção</th>
            <th>Valor líquido</th>
            <th>Vencimento</th>
            <th>Financeiro ERP</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {measurements.map((measurement) => {
            const canSubmit = ["draft", "rejected"].includes(measurement.status)
            const canApprove = ["draft", "submitted", "in_approval", "rejected"].includes(measurement.status)
            const canReject = ["draft", "submitted", "in_approval"].includes(measurement.status)
            const canEdit = measurement.status !== "approved" && measurement.status !== "paid"
            const canDelete = measurement.status !== "approved" && measurement.status !== "paid"

            return (
              <tr key={measurement.id}>
                <td>
                  <strong>{measurement.code}</strong>
                  <div className={styles.rowSecondaryText}>Seq. {measurement.sequenceNumber ?? "-"}</div>
                </td>
                <td>
                  <strong>{measurement.unitId ? unitNameById[measurement.unitId] ?? measurement.unitId : "-"}</strong>
                  <div className={styles.rowSecondaryText}>
                    {measurement.schedulePhaseId ? phaseNameById[measurement.schedulePhaseId] ?? measurement.schedulePhaseId : "-"}
                  </div>
                </td>
                <td>
                  {measurement.measurementType || "-"}
                  <div className={styles.rowSecondaryText}>{measurement.documentType || "-"}</div>
                </td>
                <td>
                  <span className={`${styles.statusPill} ${styles[`status${measurement.status}`] || ""}`}>
                    {measurementStatusLabel[measurement.status] ?? measurement.status}
                  </span>
                  {measurement.approvedByUserId ? (
                    <div className={styles.rowSecondaryText}>aprovada por usuário registrado</div>
                  ) : measurement.submittedByUserId ? (
                    <div className={styles.rowSecondaryText}>aguardando aprovador diferente</div>
                  ) : null}
                </td>
                <td>
                  {measurement.itemsCount ? `${measurement.itemsCount} item(ns)` : "valor único"}
                  <div className={styles.rowSecondaryText}>
                    {measurement.pendingInspectionsCount
                      ? `${measurement.pendingInspectionsCount} verificação(oes) pendente(s)`
                      : "sem verificação pendente"}
                    {measurement.openOccurrencesCount
                      ? ` - ${measurement.openOccurrencesCount} ocorrência(s)`
                      : ""}
                  </div>
                </td>
                <td>{formatMoney(measurement.netAmount ?? measurement.measuredAmount)}</td>
                <td>{formatDate(measurement.dueDate)}</td>
                <td>
                  {measurement.externalAccountsPayableId ? (
                    <div>
                      <div className={styles.rowSecondaryText}>{measurement.externalAccountsPayableStatus || "ativo"}</div>
                      <span className={styles.badgeSuccess}>Vinculado</span>
                    </div>
                  ) : (
                    <span className={styles.badgeMuted}>Pendente</span>
                  )}
                </td>
                <td>
                  <RowActionsMenu
                    actions={[
                      {
                        key: "items",
                        label: "Itens e inspeção",
                        icon: ListChecks,
                        onSelect: () => onOpenItems(measurement),
                      },
                      {
                        key: "edit",
                        label: "Editar",
                        icon: Pencil,
                        visible: canEdit,
                        onSelect: () => onEdit(measurement),
                      },
                      {
                        key: "submit",
                        label: "Enviar para aprovação",
                        icon: Send,
                        visible: canSubmit,
                        dividerBefore: true,
                        onSelect: () => onSubmit(measurement),
                      },
                      {
                        key: "approve",
                        label: "Aprovar",
                        icon: CheckCircle,
                        visible: canApprove,
                        dividerBefore: !canSubmit,
                        onSelect: () => onApprove(measurement),
                      },
                      {
                        key: "reject",
                        label: "Rejeitar",
                        icon: Clock,
                        visible: canReject,
                        onSelect: () => onReject(measurement),
                      },
                      {
                        key: "delete",
                        label: "Excluir",
                        icon: Trash2,
                        danger: true,
                        visible: canDelete,
                        dividerBefore: true,
                        onSelect: () => onDelete(measurement),
                      },
                    ]}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ProcurementList({
  procurementRequests,
  loading,
  error,
  onRetry,
  onEdit,
  onDelete,
  onSubmit,
  onApprove,
  onReject,
}) {
  if (loading) {
    return (
      <div className={styles.tableWrapper} aria-busy="true">
        <div className={styles.empty}>
          <RefreshCw className={styles.spinIcon} size={16} />
          Carregando requisições...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>
          <span>{error}</span>
          <button type="button" className={styles.secondaryButton} onClick={onRetry}>
            <RefreshCw size={16} />
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }

  if (!procurementRequests.length) {
    return (
      <div className={styles.tableWrapper}>
        <div className={styles.empty}>Nenhuma requisição cadastrada para a obra selecionada.</div>
      </div>
    )
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Código</th>
            <th>Requisição</th>
            <th>Status</th>
            <th>Valor estimado</th>
            <th>Necessidade</th>
            <th>Integração ERP</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {procurementRequests.map((procurementRequest) => {
            const canSubmit = ["draft", "rejected"].includes(procurementRequest.status)
            const canApprove = procurementRequest.status === "pending_approval"
            const canReject = ["pending_approval", "draft"].includes(procurementRequest.status)
            const canEdit = ["draft", "rejected"].includes(procurementRequest.status)
            const canDelete = ["draft", "rejected"].includes(procurementRequest.status)

            return (
              <tr key={procurementRequest.id}>
                <td>{procurementRequest.code}</td>
                <td>
                  <strong>{procurementRequest.title}</strong>
                  <div className={styles.rowSecondaryText}>{procurementRequest.description || "-"}</div>
                </td>
                <td>
                  <span className={`${styles.statusPill} ${styles[`status${procurementRequest.status}`] || ""}`}>
                    {procurementStatusLabel[procurementRequest.status] ?? procurementRequest.status}
                  </span>
                </td>
                <td>{formatMoney(procurementRequest.estimatedAmount)}</td>
                <td>{formatDate(procurementRequest.neededByDate)}</td>
                <td>
                  {procurementRequest.externalProcurementId ? (
                    <div>
                      <div className={styles.rowSecondaryText}>{procurementRequest.externalProcurementStatus || "ativa"}</div>
                      <span className={styles.badgeSuccess}>Vinculada</span>
                    </div>
                  ) : (
                    <span className={styles.badgeMuted}>Pendente</span>
                  )}
                </td>
                <td>
                  <RowActionsMenu
                    actions={[
                      {
                        key: "edit",
                        label: "Editar",
                        icon: Pencil,
                        visible: canEdit,
                        onSelect: () => onEdit(procurementRequest),
                      },
                      {
                        key: "submit",
                        label: "Enviar ao ERP",
                        icon: Send,
                        visible: canSubmit,
                        dividerBefore: true,
                        onSelect: () => onSubmit(procurementRequest),
                      },
                      {
                        key: "approve",
                        label: "Aprovar",
                        icon: CheckCircle,
                        visible: canApprove,
                        dividerBefore: !canSubmit,
                        onSelect: () => onApprove(procurementRequest),
                      },
                      {
                        key: "reject",
                        label: "Rejeitar",
                        icon: Clock,
                        visible: canReject,
                        onSelect: () => onReject(procurementRequest),
                      },
                      {
                        key: "delete",
                        label: "Excluir",
                        icon: Trash2,
                        danger: true,
                        visible: canDelete,
                        dividerBefore: true,
                        onSelect: () => onDelete(procurementRequest),
                      },
                    ]}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ProcurementModal({ mode, procurementForm, people, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={mode === "create" ? "Nova requisição" : "Editar requisição"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{mode === "create" ? "Nova requisição" : "Editar requisição"}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Código</span>
              <input
                type="text"
                value={procurementForm.code}
                onChange={(event) => onChange("code", event.target.value)}
                placeholder="Opcional - gerado automaticamente"
              />
            </label>
            <label className={styles.filterControl}>
              <span>Título*</span>
              <input
                type="text"
                value={procurementForm.title}
                onChange={(event) => onChange("title", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Valor estimado*</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={procurementForm.estimatedAmount}
                onChange={(event) => onChange("estimatedAmount", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Necessário até</span>
              <input
                type="date"
                value={procurementForm.neededByDate}
                onChange={(event) => onChange("neededByDate", event.target.value)}
              />
            </label>
            <PersonIdInput
              label="Fornecedor (ID)"
              value={procurementForm.supplierPersonId}
              onChange={(value) => onChange("supplierPersonId", value)}
              people={people}
            />
            <label className={`${styles.filterControl} ${styles.spanTwoColumns}`}>
              <span>Descrição</span>
              <textarea
                className={styles.textarea}
                value={procurementForm.description}
                onChange={(event) => onChange("description", event.target.value)}
              />
            </label>
          </div>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Salvando..." : mode === "create" ? "Criar requisição" : "Salvar alterações"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function RejectProcurementModal({ procurementRequest, rejectForm, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Rejeitar requisição"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Rejeitar requisição {procurementRequest?.code}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <label className={styles.filterControl}>
            <span>Motivo da rejeição</span>
            <textarea
              className={styles.textarea}
              value={rejectForm.reason}
              onChange={(event) => onChange("reason", event.target.value)}
            />
          </label>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Rejeitando..." : "Rejeitar requisição"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function MeasurementModal({
  mode,
  measurementForm,
  people,
  units,
  lockedUnit,
  schedulePhases,
  onClose,
  onChange,
  onSubmit,
  loading,
}) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={mode === "create" ? "Nova medição" : "Editar medição"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{mode === "create" ? "Nova medição" : "Editar medição"}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Código*</span>
              <input
                type="text"
                value={measurementForm.code}
                onChange={(event) => onChange("code", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Sequência</span>
              <input
                type="number"
                min="1"
                value={measurementForm.sequenceNumber}
                onChange={(event) => onChange("sequenceNumber", event.target.value)}
              />
            </label>
            {lockedUnit ? (
              <div className={styles.detailMetaItem}>
                <span>Unidade*</span>
                <strong>
                  {lockedUnit.code} - {lockedUnit.description || lockedUnit.unitType}
                </strong>
              </div>
            ) : (
              <label className={styles.filterControl}>
                <span>Unidade*</span>
                <select value={measurementForm.unitId} onChange={(event) => onChange("unitId", event.target.value)} required>
                  <option value="">Selecione</option>
                  {units.map((unit) => (
                    <option key={unit.id} value={unit.id}>
                      {unit.code} - {unit.description || unit.unitType}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className={styles.filterControl}>
              <span>Etapa*</span>
              <select
                value={measurementForm.schedulePhaseId}
                onChange={(event) => onChange("schedulePhaseId", event.target.value)}
                required
              >
                <option value="">Selecione</option>
                {schedulePhases.map((phase) => (
                  <option key={phase.id} value={phase.id}>
                    {phase.sequenceOrder} - {phase.name}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.filterControl}>
              <span>Tipo</span>
              <input
                type="text"
                value={measurementForm.measurementType}
                onChange={(event) => onChange("measurementType", event.target.value)}
                placeholder="empreiteiro, fornecedor..."
              />
            </label>
            <label className={styles.filterControl}>
              <span>Competência</span>
              <input
                type="date"
                value={measurementForm.competenceDate}
                onChange={(event) => onChange("competenceDate", event.target.value)}
              />
            </label>
            <PersonIdInput
              label="Fornecedor (ID)"
              value={measurementForm.supplierPersonId}
              onChange={(value) => onChange("supplierPersonId", value)}
              people={people}
            />
            <label className={styles.filterControl}>
              <span>Vencimento*</span>
              <input
                type="date"
                value={measurementForm.dueDate}
                onChange={(event) => onChange("dueDate", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Valor bruto*</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={measurementForm.grossAmount}
                onChange={(event) => onChange("grossAmount", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Retenções</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={measurementForm.retentionsAmount}
                onChange={(event) => onChange("retentionsAmount", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Valor líquido</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={measurementForm.netAmount}
                onChange={(event) => onChange("netAmount", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Tipo documento</span>
              <input
                type="text"
                value={measurementForm.documentType}
                onChange={(event) => onChange("documentType", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Número documento</span>
              <input
                type="text"
                value={measurementForm.documentNumber}
                onChange={(event) => onChange("documentNumber", event.target.value)}
              />
            </label>
            <label className={`${styles.filterControl} ${styles.spanTwoColumns}`}>
              <span>Descrição</span>
              <textarea
                className={styles.textarea}
                value={measurementForm.description}
                onChange={(event) => onChange("description", event.target.value)}
              />
            </label>
          </div>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Salvando..." : mode === "create" ? "Criar medição" : "Salvar alterações"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function RejectMeasurementModal({ measurement, rejectForm, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Rejeitar medição"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Rejeitar medição {measurement?.code}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <label className={styles.filterControl}>
            <span>Motivo da rejeição</span>
            <textarea
              className={styles.textarea}
              value={rejectForm.reason}
              onChange={(event) => onChange("reason", event.target.value)}
            />
          </label>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Rejeitando..." : "Rejeitar medição"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function PersonIdInput({
  label,
  value,
  onChange,
  people = [],
  required = false,
  loading = false,
  error = null,
  emptyLabel = "Selecione uma pessoa",
}) {
  const hasSelectedPerson = people.some((person) => person.id === value)

  return (
    <label className={styles.filterControl}>
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        disabled={loading}
      >
        <option value="">{loading ? "Carregando pessoas..." : emptyLabel}</option>
        {value && !hasSelectedPerson ? <option value={value}>Pessoa selecionada</option> : null}
        {people.map((person) => (
          <option key={person.id} value={person.id}>
            {person.name}{person.document ? ` - ${person.document}` : ""}
          </option>
        ))}
      </select>
      {error ? <small className={styles.formError}>{error}</small> : null}
    </label>
  )
}

function IntegrationPanel({
  personLookupQuery,
  onPersonLookupQueryChange,
  onPersonLookupSearch,
  loadingPeople,
  personLookupError,
  people,
  measurements,
  procurementRequests,
  units,
}) {
  const linkedMeasurements = measurements.filter((measurement) => measurement.externalAccountsPayableId).length
  const linkedProcurementRequests = procurementRequests.filter(
    (procurementRequest) => procurementRequest.externalProcurementId
  ).length
  const linkedUnitContracts = units.filter((unit) => unit.externalContractId).length

  return (
    <div className={styles.integrationPanel}>
      <div className={styles.integrationGrid}>
        <article className={styles.integrationCard}>
          <h3>Pessoas ERP</h3>
          <p className={styles.textMuted}>Lookup para vincular comprador e fornecedor nos fluxos operacionais.</p>
          <div className={styles.inlineForm}>
            <input
              type="text"
              value={personLookupQuery}
              onChange={(event) => onPersonLookupQueryChange(event.target.value)}
              placeholder="Buscar por nome, documento ou telefone"
            />
            <button type="button" className={styles.secondaryButton} onClick={onPersonLookupSearch} disabled={loadingPeople}>
              {loadingPeople ? "Buscando..." : "Buscar"}
            </button>
          </div>
          {personLookupError ? <p className={styles.formError}>{personLookupError}</p> : null}
          <p className={styles.rowSecondaryText}>{people.length} pessoa(s) carregada(s)</p>
        </article>

        <article className={styles.integrationCard}>
          <h3>Financeiro ERP</h3>
          <p className={styles.textMuted}>Sincronização de medições aprovadas com contas a pagar.</p>
          <p className={styles.metricValue}>{linkedMeasurements}</p>
          <p className={styles.metricHint}>medições com documento financeiro vinculado</p>
        </article>

        <article className={styles.integrationCard}>
          <h3>Compras ERP</h3>
          <p className={styles.textMuted}>Requisições enviadas para a fila de compras.</p>
          <p className={styles.metricValue}>{linkedProcurementRequests}</p>
          <p className={styles.metricHint}>requisições vinculadas externamente</p>
        </article>

        <article className={styles.integrationCard}>
          <h3>Contratos ERP</h3>
          <p className={styles.textMuted}>Unidades vendidas com contrato e recebíveis vinculados.</p>
          <p className={styles.metricValue}>{linkedUnitContracts}</p>
          <p className={styles.metricHint}>unidades com contrato sincronizado</p>
        </article>
      </div>
    </div>
  )
}

function ProjectModal({
  mode,
  projectForm,
  people,
  loadingPeople,
  personLookupError,
  zipLookup,
  receiptTemplates,
  receiptTemplatesError,
  onClose,
  onChange,
  onZipLookup,
  onSubmit,
  loading,
}) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={mode === "create" ? "Nova obra" : "Editar obra"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{mode === "create" ? "Nova obra" : "Editar obra"}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Código*</span>
              <input
                type="text"
                value={projectForm.code}
                onChange={(event) => onChange("code", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Nome*</span>
              <input
                type="text"
                value={projectForm.name}
                onChange={(event) => onChange("name", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Status*</span>
              <select value={projectForm.status} onChange={(event) => onChange("status", event.target.value)} required>
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.filterControl}>
              <span>Tipo*</span>
              <select
                value={projectForm.projectType}
                onChange={(event) => onChange("projectType", event.target.value)}
                required
              >
                {projectTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <PersonIdInput
              label="Cliente/Contratante ERP"
              value={projectForm.customerPersonId}
              onChange={(value) => onChange("customerPersonId", value)}
              people={people}
              loading={loadingPeople}
              error={personLookupError}
              emptyLabel="Sem cliente vinculado"
            />
            <label className={styles.filterControl}>
              <span>CNPJ SPE</span>
              <input
                type="text"
                value={projectForm.cnpjSpe}
                onChange={(event) => onChange("cnpjSpe", event.target.value)}
                placeholder="00.000.000/0000-00"
              />
            </label>
            <label className={styles.filterControl}>
              <span>Data de inicio</span>
              <input
                type="date"
                value={projectForm.startDate}
                onChange={(event) => onChange("startDate", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Data prevista de fim</span>
              <input
                type="date"
                value={projectForm.expectedEndDate}
                onChange={(event) => onChange("expectedEndDate", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Data real de fim</span>
              <input
                type="date"
                value={projectForm.actualEndDate}
                onChange={(event) => onChange("actualEndDate", event.target.value)}
              />
            </label>
            <label className={`${styles.filterControl} ${styles.spanTwoColumns}`}>
              <span>Descrição</span>
              <textarea
                className={styles.textarea}
                value={projectForm.description}
                onChange={(event) => onChange("description", event.target.value)}
              />
            </label>
          </div>

          <h4 className={styles.sectionTitle}>Modelos de recibo</h4>
          <p className={styles.metricHint}>
            Escolhidos na obra e herdados pelas unidades. O modelo da venda vale para as parcelas e para
            os aditivos, que dividem o mesmo contrato; o do sinal é copiado no lançamento, então trocar o
            modelo aqui depois não reescreve o que já foi lançado.
          </p>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Recibo de parcela e aditivo</span>
              <select
                value={projectForm.receiptTemplateId}
                onChange={(event) => onChange("receiptTemplateId", event.target.value)}
              >
                <option value="">Layout padrão do ERP</option>
                {(receiptTemplates ?? []).map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.filterControl}>
              <span>Recibo do sinal</span>
              <select
                value={projectForm.commissionReceiptTemplateId}
                onChange={(event) => onChange("commissionReceiptTemplateId", event.target.value)}
              >
                <option value="">Layout padrão do ERP</option>
                {(receiptTemplates ?? []).map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {receiptTemplatesError ? (
            <small className={styles.formError}>{receiptTemplatesError}</small>
          ) : null}

          <h4 className={styles.sectionTitle}>Endereço</h4>
          <div className={styles.formGrid}>
            <label className={`${styles.filterControl} ${styles.spanTwoColumns}`}>
              <span>Logradouro</span>
              <input
                type="text"
                value={projectForm.addressStreet}
                onChange={(event) => onChange("addressStreet", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Número</span>
              <input
                type="text"
                value={projectForm.addressNumber}
                onChange={(event) => onChange("addressNumber", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Bairro</span>
              <input
                type="text"
                value={projectForm.addressDistrict}
                onChange={(event) => onChange("addressDistrict", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Cidade</span>
              <input
                type="text"
                value={projectForm.addressCity}
                onChange={(event) => onChange("addressCity", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>UF</span>
              <input
                type="text"
                value={projectForm.addressState}
                onChange={(event) => onChange("addressState", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>CEP</span>
              <input
                type="text"
                value={projectForm.addressZipCode}
                onChange={(event) => onChange("addressZipCode", event.target.value)}
                onBlur={onZipLookup}
                inputMode="numeric"
                placeholder="00000-000"
              />
              {zipLookup?.loading ? <small className={styles.fieldHint}>Buscando CEP...</small> : null}
              {zipLookup?.error ? <small className={styles.formError}>{zipLookup.error}</small> : null}
            </label>
          </div>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Salvando..." : mode === "create" ? "Criar obra" : "Salvar alterações"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function BlockModal({ mode, blockForm, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={mode === "create" ? "Novo bloco" : "Editar bloco"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{mode === "create" ? "Novo bloco" : "Editar bloco"}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Código*</span>
              <input
                type="text"
                value={blockForm.code}
                onChange={(event) => onChange("code", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Nome*</span>
              <input
                type="text"
                value={blockForm.name}
                onChange={(event) => onChange("name", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Status*</span>
              <select value={blockForm.status} onChange={(event) => onChange("status", event.target.value)} required>
                {blockStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.filterControl}>
              <span>Pavimentos</span>
              <input
                type="number"
                min="0"
                value={blockForm.floorsCount}
                onChange={(event) => onChange("floorsCount", event.target.value)}
              />
            </label>
          </div>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Salvando..." : mode === "create" ? "Criar bloco" : "Salvar alterações"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function UnitModal({ mode, unitForm, blocks, onClose, onChange, onSubmit, loading }) {
  const unitQuantity = Number(unitForm.quantity)
  const submitLabel = mode === "create" && unitQuantity > 1 ? `Criar ${unitQuantity} unidades` : "Criar unidade"

  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={mode === "create" ? "Nova unidade" : "Editar unidade"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{mode === "create" ? "Nova unidade" : "Editar unidade"}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            {mode === "create" ? (
              <>
                <label className={styles.filterControl}>
                  <span>Quantidade*</span>
                  <input
                    type="number"
                    min="1"
                    max={MAX_UNIT_BATCH_SIZE}
                    step="1"
                    value={unitForm.quantity}
                    onChange={(event) => onChange("quantity", event.target.value)}
                    required
                  />
                </label>
                <label className={styles.filterControl}>
                  <span>Descrição base*</span>
                  <input
                    type="text"
                    value={unitForm.description}
                    onChange={(event) => onChange("description", event.target.value)}
                    placeholder={DEFAULT_UNIT_DESCRIPTION}
                    required
                  />
                </label>
              </>
            ) : (
              <>
                <label className={styles.filterControl}>
                  <span>Código*</span>
                  <input
                    type="text"
                    value={unitForm.code}
                    onChange={(event) => onChange("code", event.target.value)}
                    required
                  />
                </label>
                <label className={styles.filterControl}>
                  <span>Descrição</span>
                  <input
                    type="text"
                    value={unitForm.description}
                    onChange={(event) => onChange("description", event.target.value)}
                  />
                </label>
              </>
            )}
            <label className={styles.filterControl}>
              <span>Tipo*</span>
              <input
                type="text"
                value={unitForm.unitType}
                onChange={(event) => onChange("unitType", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Tipologia</span>
              <input
                type="text"
                value={unitForm.typology}
                onChange={(event) => onChange("typology", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Bloco</span>
              <select value={unitForm.blockId} onChange={(event) => onChange("blockId", event.target.value)}>
                <option value="">Sem bloco</option>
                {blocks.map((block) => (
                  <option key={block.id} value={block.id}>
                    {block.code} - {block.name}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.filterControl}>
              <span>Andar</span>
              <input type="text" value={unitForm.floor} onChange={(event) => onChange("floor", event.target.value)} />
            </label>
            <label className={styles.filterControl}>
              <span>Área privativa</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={unitForm.privateArea}
                onChange={(event) => onChange("privateArea", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Área total</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={unitForm.totalArea}
                onChange={(event) => onChange("totalArea", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Preço de venda</span>
              <input
                type="text"
                inputMode="decimal"
                value={unitForm.salePrice}
                onChange={(event) => onChange("salePrice", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
              />
            </label>
            <label className={styles.filterControl}>
              <span>Status*</span>
              <select value={unitForm.status} onChange={(event) => onChange("status", event.target.value)} required>
                {unitStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Salvando..." : mode === "create" ? submitLabel : "Salvar alterações"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function ReserveUnitModal({ reserveForm, unit, people, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Reservar unidade"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Reservar unidade {unit?.code}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <PersonIdInput
              label="Comprador (ID)*"
              value={reserveForm.buyerPersonId}
              onChange={(value) => onChange("buyerPersonId", value)}
              people={people}
              required
            />
            <label className={styles.filterControl}>
              <span>Expira em</span>
              <input
                type="date"
                value={reserveForm.reservationExpiresAt}
                onChange={(event) => onChange("reservationExpiresAt", event.target.value)}
              />
            </label>
          </div>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Reservando..." : "Reservar unidade"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function SaleUnitModal({
  saleForm,
  unit,
  people,
  onClose,
  onChange,
  onSubmit,
  documentationTypes,
  loadingDocumentationTypes,
  loading,
}) {
  const isEditing = unit?.status === "sold"
  const grossSalePrice = parseCurrencyFormValue(saleForm.salePrice)
  const discountAmount = parseCurrencyFormValue(saleForm.discountAmount)
  const netSalePrice = Math.max(grossSalePrice - discountAmount, 0)

  const sources = salePaymentSourceDefinitions.map((definition) => {
    const amountValue = parseCurrencyFormValue(saleForm[definition.amountField])
    const installments = Math.max(Number(saleForm[definition.installmentsField] || 1), 1)
    const generatesInstallments = SALE_INSTALLMENT_SOURCE_TYPES.includes(definition.sourceType)
    return {
      ...definition,
      amountValue,
      installments,
      generatesInstallments,
      installmentAmount: generatesInstallments && installments > 0 ? amountValue / installments : amountValue,
    }
  })

  const installmentSources = sources.filter((source) => source.generatesInstallments)
  const settlementSources = sources.filter((source) => !source.generatesInstallments)
  const downPaymentTotal = installmentSources.reduce((total, source) => total + source.amountValue, 0)
  const settlementTotal = settlementSources.reduce((total, source) => total + source.amountValue, 0)

  const documentationRows = saleForm.documentations ?? []
  const documentationTotal = sumSaleDocumentations(buildSaleDocumentationsFromForm(saleForm))

  // SALDO = preço + documentação - desconto - entrada - financiamento - FGTS - subsídio.
  // É a conta do legado (Dwelling/Resume.cshtml), e é o saldo que vira parcela.
  // A documentação é repasse cobrado do comprador: não vira parcela própria,
  // dilui no saldo.
  const balance =
    grossSalePrice + documentationTotal - discountAmount - downPaymentTotal - settlementTotal
  const balanceInstallments = Math.max(Number(saleForm.installments || 1), 1)
  const balanceInstallmentAmount = balance > 0 ? balance / balanceInstallments : 0

  const receivableTotal = downPaymentTotal + Math.max(balance, 0)
  const installmentCount =
    installmentSources
      .filter((source) => source.amountValue > 0)
      .reduce((total, source) => total + source.installments, 0) +
    (balance > 0 ? balanceInstallments : 0)
  const exceedsPrice = grossSalePrice > 0 && balance < -0.01

  const changeDocumentationRow = (key, changes) => {
    onChange(
      "documentations",
      documentationRows.map((row) => (row.key === key ? { ...row, ...changes } : row)),
    )
  }

  const removeDocumentationRow = (key) => {
    onChange(
      "documentations",
      documentationRows.filter((row) => row.key !== key),
    )
  }

  const addDocumentationRow = () => {
    onChange("documentations", [...documentationRows, makeSaleDocumentationRow()])
  }

  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={isEditing ? "Editar venda da unidade" : "Confirmar venda da unidade"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>
            {isEditing ? "Editar venda da unidade" : "Confirmar venda da unidade"} {unit?.code}
          </h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          {isEditing ? (
            <p className={styles.metricHint}>
              Salvar reescreve o contrato e refaz as parcelas <strong>em aberto</strong> desta unidade. As
              parcelas já pagas são preservadas e o que restar é redistribuído.
            </p>
          ) : null}
          <div className={styles.formGrid}>
            <PersonIdInput
              label="Comprador*"
              value={saleForm.buyerPersonId}
              onChange={(value) => onChange("buyerPersonId", value)}
              people={people}
              required
            />
            <PersonIdInput
              label="Comprador secundário"
              value={saleForm.secondaryBuyerPersonId}
              onChange={(value) => onChange("secondaryBuyerPersonId", value)}
              people={people}
              emptyLabel="Sem comprador secundário"
            />
            <PersonIdInput
              label="Corretor"
              value={saleForm.brokerPersonId}
              onChange={(value) => onChange("brokerPersonId", value)}
              people={people}
              emptyLabel="Sem corretor"
            />
            <label className={styles.filterControl}>
              <span>Preço da venda*</span>
              <input
                type="text"
                inputMode="decimal"
                value={saleForm.salePrice}
                onChange={(event) => onChange("salePrice", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
              />
            </label>
            <label className={styles.filterControl}>
              <span>Desconto</span>
              <input
                type="text"
                inputMode="decimal"
                value={saleForm.discountAmount}
                onChange={(event) => onChange("discountAmount", formatCurrencyInput(event.target.value))}
                placeholder="0,00"
              />
            </label>
            <label className={styles.filterControl}>
              <span>Assinatura do contrato</span>
              <input
                type="date"
                value={saleForm.contractSignatureDate}
                onChange={(event) => onChange("contractSignatureDate", event.target.value)}
              />
            </label>
          </div>

          <div className={styles.card}>
            <div className={styles.scopeMeta}>
              <strong>Documentação</strong>
              <span className={styles.metricHint}>
                Avaliação, prefeitura, cartório, IPTU e outras taxas cobradas do comprador.{" "}
                <strong>Entram no saldo devedor.</strong>
              </span>
            </div>
            {documentationRows.map((documentationRow) => (
              <div key={documentationRow.key} className={styles.formGrid}>
                <div className={styles.filterControl}>
                  <span>Tipo</span>
                  <CreatableCombobox
                    allowCreate
                    items={documentationTypes}
                    loading={loadingDocumentationTypes}
                    placeholder="Escolha ou digite um novo tipo"
                    emptyMessage="Nenhum tipo cadastrado."
                    notFoundMessage="Nenhum tipo encontrado."
                    value={
                      documentationRow.documentationTypeName
                        ? {
                            id: documentationRow.documentationTypeId || null,
                            name: documentationRow.documentationTypeName,
                          }
                        : null
                    }
                    onChange={(documentationType) =>
                      changeDocumentationRow(documentationRow.key, {
                        documentationTypeId: documentationType?.id ?? "",
                        documentationTypeName: documentationType?.name ?? "",
                      })
                    }
                  />
                </div>
                <label className={styles.filterControl}>
                  <span>Valor</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={documentationRow.amount}
                    onChange={(event) =>
                      changeDocumentationRow(documentationRow.key, {
                        amount: formatCurrencyInput(event.target.value),
                      })
                    }
                    placeholder="0,00"
                  />
                </label>
                <div className={styles.filterControl}>
                  <span>&nbsp;</span>
                  <button
                    type="button"
                    className={styles.secondaryButton}
                    onClick={() => removeDocumentationRow(documentationRow.key)}
                  >
                    <Trash2 size={16} />
                    Remover
                  </button>
                </div>
              </div>
            ))}
            <div className={styles.formGrid}>
              <div className={styles.filterControl}>
                <span>&nbsp;</span>
                <button type="button" className={styles.secondaryButton} onClick={addDocumentationRow}>
                  <Plus size={16} />
                  Incluir documentação
                </button>
              </div>
              <div className={styles.filterControl}>
                <span>Total da documentação</span>
                <strong className={styles.installmentPreview}>
                  {documentationTotal > 0 ? formatMoney(documentationTotal) : "-"}
                </strong>
              </div>
            </div>
          </div>

          <div className={styles.card}>
            <div className={styles.scopeMeta}>
              <strong>Liberado pelo banco</strong>
              <span className={styles.metricHint}>
                Compoe o preço da venda e <strong>não gera parcela</strong>: a data de pagamento depende da
                liberação, então a data informada e apenas a previsão.
              </span>
            </div>
            {settlementSources.map((source) => (
              <div key={source.sourceType} className={styles.formGrid}>
                <label className={styles.filterControl}>
                  <span>{source.label}</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={saleForm[source.amountField]}
                    onChange={(event) =>
                      onChange(source.amountField, formatCurrencyInput(event.target.value))
                    }
                    placeholder="0,00"
                  />
                </label>
                <label className={styles.filterControl}>
                  <span>Previsão de liberação</span>
                  <input
                    type="date"
                    value={saleForm[source.dueDateField]}
                    onChange={(event) => onChange(source.dueDateField, event.target.value)}
                  />
                </label>
                <div className={styles.filterControl}>
                  <span>Entra na venda como</span>
                  <strong className={styles.installmentPreview}>
                    {source.amountValue > 0 ? `${formatMoney(source.amountValue)} a vista` : "-"}
                  </strong>
                </div>
              </div>
            ))}
          </div>

          <div className={styles.card}>
            <div className={styles.scopeMeta}>
              <strong>Cobrado do comprador</strong>
              <span className={styles.metricHint}>
                Gera contas a receber. O valor informado e o <strong>total da fonte</strong> e e dividido pela
                quantidade de parcelas. O <strong>saldo</strong> abaixo e o que sobra depois da documentação e
                das liberações do banco informadas acima.
              </span>
            </div>
            {installmentSources.map((source) => (
              <div key={source.sourceType} className={styles.formGrid}>
                <label className={styles.filterControl}>
                  <span>{source.label} - valor total</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={saleForm[source.amountField]}
                    onChange={(event) =>
                      onChange(source.amountField, formatCurrencyInput(event.target.value))
                    }
                    placeholder="0,00"
                  />
                </label>
                <label className={styles.filterControl}>
                  <span>Parcelas</span>
                  <input
                    type="number"
                    min="1"
                    max="120"
                    value={saleForm[source.installmentsField]}
                    onChange={(event) => onChange(source.installmentsField, event.target.value)}
                  />
                </label>
                <label className={styles.filterControl}>
                  <span>1o vencimento</span>
                  <input
                    type="date"
                    value={saleForm[source.dueDateField]}
                    onChange={(event) => onChange(source.dueDateField, event.target.value)}
                  />
                </label>
                <div className={styles.filterControl}>
                  <span>Fica</span>
                  <strong className={styles.installmentPreview}>
                    {source.amountValue > 0
                      ? `${source.installments} x ${formatMoney(source.installmentAmount)}`
                      : "-"}
                  </strong>
                </div>
              </div>
            ))}

            <div className={styles.formGrid}>
              <div className={styles.filterControl}>
                <span>Saldo devedor</span>
                <strong className={styles.installmentPreview}>
                  {grossSalePrice > 0 ? formatMoney(Math.max(balance, 0)) : "-"}
                </strong>
                <span className={styles.rowSecondaryText}>
                  preço + documentação - desconto - entrada - liberações do banco
                </span>
              </div>
              <label className={styles.filterControl}>
                <span>Parcelas</span>
                <input
                  type="number"
                  min="1"
                  max="120"
                  value={saleForm.installments}
                  onChange={(event) => onChange("installments", event.target.value)}
                />
              </label>
              <label className={styles.filterControl}>
                <span>1o vencimento</span>
                <input
                  type="date"
                  value={saleForm.firstDueDate}
                  onChange={(event) => onChange("firstDueDate", event.target.value)}
                />
              </label>
              <div className={styles.filterControl}>
                <span>Fica</span>
                <strong className={styles.installmentPreview}>
                  {balance > 0 ? `${balanceInstallments} x ${formatMoney(balanceInstallmentAmount)}` : "-"}
                </strong>
              </div>
            </div>
          </div>

          <label className={styles.filterControl}>
            <span>Observação</span>
            <textarea
              rows={3}
              value={saleForm.saleNotes}
              onChange={(event) => onChange("saleNotes", event.target.value)}
              placeholder="Condições acordadas, pendências, referências do contrato"
            />
          </label>

          <div className={styles.card}>
            <strong>Composição da venda</strong>
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <tbody>
                  <tr>
                    <td>Preço da venda</td>
                    <td className={styles.textRight}>{formatMoney(grossSalePrice)}</td>
                  </tr>
                  <tr>
                    <td>Documentação</td>
                    <td className={styles.textRight}>+ {formatMoney(documentationTotal)}</td>
                  </tr>
                  <tr>
                    <td>Desconto</td>
                    <td className={styles.textRight}>- {formatMoney(discountAmount)}</td>
                  </tr>
                  <tr>
                    <td>Liberado pelo banco (subsídio + FGTS + financiamento)</td>
                    <td className={styles.textRight}>- {formatMoney(settlementTotal)}</td>
                  </tr>
                  <tr>
                    <td>Entrada</td>
                    <td className={styles.textRight}>- {formatMoney(downPaymentTotal)}</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Saldo devedor</strong>
                      <div className={styles.rowSecondaryText}>o que sobra e vira parcela</div>
                    </td>
                    <td className={styles.textRight}>
                      <strong>{formatMoney(Math.max(balance, 0))}</strong>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Cobrado do comprador (entrada + saldo)</strong>
                      <div className={styles.rowSecondaryText}>
                        {installmentCount ? `${installmentCount} parcela(s) no total` : "nenhuma parcela"}
                      </div>
                    </td>
                    <td className={styles.textRight}>
                      <strong>{formatMoney(receivableTotal)}</strong>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <span className={exceedsPrice ? styles.badgeMuted : styles.badgeSuccess}>
              {grossSalePrice <= 0
                ? "Informe o preço da venda"
                : exceedsPrice
                  ? `Composição excede o preço mais a documentação em ${formatMoney(Math.abs(balance))}`
                  : `Cobrança do comprador: ${formatMoney(receivableTotal)}`}
            </span>
          </div>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading
                ? isEditing
                  ? "Salvando..."
                  : "Confirmando..."
                : isEditing
                  ? "Salvar venda"
                  : "Confirmar venda"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function MeasurementItemsModal({
  measurement,
  items,
  people,
  serviceTemplates,
  loadingServiceTemplates,
  importingServiceTemplates,
  onImportServiceTemplates,
  loading,
  error,
  saving,
  onClose,
  onRetry,
  onCreateItem,
  onDeleteItem,
  onCreateInspection,
  onVerifyInspection,
  onDeleteInspection,
  onCreateOccurrence,
  onResolveOccurrence,
  onDeleteOccurrence,
}) {
  const [itemForm, setItemForm] = useState(defaultMeasurementItemForm)
  const [expandedItemId, setExpandedItemId] = useState(null)

  const selectedTemplate = serviceTemplates.find((template) => template.id === itemForm.serviceTemplateId)
  const selectedTemplateName = selectedTemplate?.name ?? ""

  const isLocked = measurement.status === "approved" || measurement.status === "paid"
  const itemsTotal = items.reduce((total, item) => total + Number(item.amount ?? 0), 0)
  const pendingChecks = items.reduce(
    (total, item) =>
      total + item.inspections.filter((inspection) => !inspection.isDoubleChecked).length,
    0
  )
  const openOccurrences = items.reduce(
    (total, item) => total + item.occurrences.filter((occurrence) => occurrence.status === "open").length,
    0
  )

  const handleItemChange = (field, value) => {
    setItemForm((currentForm) => ({ ...currentForm, [field]: value }))
  }

  const handleItemSubmit = async (event) => {
    event.preventDefault()
    const created = await onCreateItem(itemForm)
    if (created) {
      setItemForm(defaultMeasurementItemForm)
    }
  }

  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={`Itens da medição ${measurement.code}`}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Itens da medição {measurement.code}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={saving}>
            Fechar
          </button>
        </header>
        <div className={styles.modalBody}>
          <div className={styles.integrationGrid}>
            <article className={styles.integrationCard}>
              <h3>Total dos itens</h3>
              <p className={styles.metricValue}>{formatMoney(itemsTotal)}</p>
              <p className={styles.metricHint}>{items.length} item(ns) de serviço</p>
            </article>
            <article className={styles.integrationCard}>
              <h3>Verificações pendentes</h3>
              <p className={styles.metricValue}>{pendingChecks}</p>
              <p className={styles.metricHint}>dupla verificação incompleta</p>
            </article>
            <article className={styles.integrationCard}>
              <h3>Ocorrências abertas</h3>
              <p className={styles.metricValue}>{openOccurrences}</p>
              <p className={styles.metricHint}>problema sem solução registrada</p>
            </article>
          </div>

          {isLocked ? (
            <p className={styles.metricHint}>
              Medição {measurementStatusLabel[measurement.status] ?? measurement.status} - itens em somente leitura.
            </p>
          ) : (
            <form className={styles.card} onSubmit={handleItemSubmit}>
              <div className={styles.scopeHeader}>
                <div className={styles.scopeMeta}>
                  <strong>Novo serviço medido</strong>
                  <span className={styles.metricHint}>
                    {loadingServiceTemplates
                      ? "Carregando catálogo de serviços..."
                      : serviceTemplates.length
                        ? `${serviceTemplates.length} serviço(s) no catálogo, com os itens de inspeção da planilha da Caixa`
                        : "Catálogo vazio - importe a planilha de verificação de serviço (FVS) da Caixa"}
                  </span>
                </div>
                <label className={styles.secondaryButton}>
                  <Upload size={16} />
                  {importingServiceTemplates ? "Importando..." : "Importar planilha (FVS)"}
                  <input
                    type="file"
                    accept=".xlsx,.xlsm"
                    multiple
                    hidden
                    disabled={importingServiceTemplates}
                    onChange={(event) => {
                      void onImportServiceTemplates(event.target.files)
                      event.target.value = ""
                    }}
                  />
                </label>
              </div>
              <div className={styles.formGrid}>
                <label className={styles.filterControl}>
                  <span>Serviço do catálogo</span>
                  <select
                    value={itemForm.serviceTemplateId}
                    onChange={(event) => handleItemChange("serviceTemplateId", event.target.value)}
                    disabled={loadingServiceTemplates}
                  >
                    <option value="">
                      {serviceTemplates.length ? "Serviço fora do catálogo" : "Catálogo vazio"}
                    </option>
                    {serviceTemplates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name} ({template.items.length} item(ns) de inspeção)
                      </option>
                    ))}
                  </select>
                </label>
                <label className={styles.filterControl}>
                  <span>{itemForm.serviceTemplateId ? "Descrição (opcional)" : "Serviço medido*"}</span>
                  <input
                    type="text"
                    value={itemForm.description}
                    onChange={(event) => handleItemChange("description", event.target.value)}
                    placeholder={
                      itemForm.serviceTemplateId
                        ? selectedTemplateName || "Usa o nome do serviço do catálogo"
                        : "Alvenaria de vedação do pavimento 3"
                    }
                    required={!itemForm.serviceTemplateId}
                  />
                </label>
                <label className={styles.filterControl}>
                  <span>Valor*</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={itemForm.amount}
                    onChange={(event) => handleItemChange("amount", formatCurrencyInput(event.target.value))}
                    placeholder="0,00"
                    required
                  />
                </label>
                <label className={styles.filterControl}>
                  <span>Produto / referência</span>
                  <input
                    type="text"
                    value={itemForm.productDescription}
                    onChange={(event) => handleItemChange("productDescription", event.target.value)}
                    placeholder="Código ou nome do serviço no cadastro"
                  />
                </label>
                <label className={styles.filterControl}>
                  <span>Inicio</span>
                  <input
                    type="date"
                    value={itemForm.startDate}
                    onChange={(event) => handleItemChange("startDate", event.target.value)}
                  />
                </label>
                <label className={styles.filterControl}>
                  <span>Fim</span>
                  <input
                    type="date"
                    value={itemForm.endDate}
                    onChange={(event) => handleItemChange("endDate", event.target.value)}
                  />
                </label>
                <PersonIdInput
                  label="Conferente"
                  value={itemForm.inspectorPersonId}
                  onChange={(value) => handleItemChange("inspectorPersonId", value)}
                  people={people}
                  emptyLabel="Sem conferente"
                />
              </div>
              <div className={styles.filtersFooter}>
                <button type="submit" className={styles.primaryButton} disabled={saving}>
                  <Plus size={16} />
                  Adicionar item
                </button>
              </div>
            </form>
          )}

          {loading ? (
            <div className={styles.empty}>
              <RefreshCw className={styles.spinIcon} size={16} />
              Carregando itens...
            </div>
          ) : error ? (
            <div className={styles.empty}>
              <span>{error}</span>
              <button type="button" className={styles.secondaryButton} onClick={onRetry}>
                <RefreshCw size={16} />
                Tentar novamente
              </button>
            </div>
          ) : !items.length ? (
            <div className={styles.empty}>
              Nenhum item de serviço lancado. Sem itens, a medição vale o valor único informado no cadastro.
            </div>
          ) : (
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Seq.</th>
                    <th>Serviço</th>
                    <th>Período</th>
                    <th>Valor</th>
                    <th>Inspeção</th>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <MeasurementItemRow
                      key={item.id}
                      item={item}
                      people={people}
                      isLocked={isLocked}
                      saving={saving}
                      expanded={expandedItemId === item.id}
                      onToggle={() => setExpandedItemId(expandedItemId === item.id ? null : item.id)}
                      onDeleteItem={onDeleteItem}
                      onCreateInspection={onCreateInspection}
                      onVerifyInspection={onVerifyInspection}
                      onDeleteInspection={onDeleteInspection}
                      onCreateOccurrence={onCreateOccurrence}
                      onResolveOccurrence={onResolveOccurrence}
                      onDeleteOccurrence={onDeleteOccurrence}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function MeasurementItemRow({
  item,
  people,
  isLocked,
  saving,
  expanded,
  onToggle,
  onDeleteItem,
  onCreateInspection,
  onVerifyInspection,
  onDeleteInspection,
  onCreateOccurrence,
  onResolveOccurrence,
  onDeleteOccurrence,
}) {
  const [inspectionForm, setInspectionForm] = useState(defaultInspectionForm)
  const [occurrenceForm, setOccurrenceForm] = useState(defaultOccurrenceForm)
  const [solutionDrafts, setSolutionDrafts] = useState({})

  const inspectorNameById = useMemo(
    () => Object.fromEntries(people.map((person) => [person.id, person.name])),
    [people]
  )

  const handleInspectionSubmit = async (event) => {
    event.preventDefault()
    const created = await onCreateInspection(item.id, inspectionForm)
    if (created) {
      setInspectionForm(defaultInspectionForm)
    }
  }

  const handleOccurrenceSubmit = async (event) => {
    event.preventDefault()
    const created = await onCreateOccurrence(item.id, occurrenceForm)
    if (created) {
      setOccurrenceForm(defaultOccurrenceForm)
    }
  }

  return (
    <>
      <tr>
        <td>{item.sequenceNumber}</td>
        <td>
          <strong>{item.description}</strong>
          <div className={styles.rowSecondaryText}>{item.productDescription || "sem referência de produto"}</div>
        </td>
        <td>
          {item.startDate ? formatDate(item.startDate) : "-"}
          <div className={styles.rowSecondaryText}>{item.endDate ? formatDate(item.endDate) : "em aberto"}</div>
        </td>
        <td>{formatMoney(item.amount)}</td>
        <td>
          <span className={styles.statusPill}>
            {inspectionStatusLabel[item.inspectionStatus] ?? item.inspectionStatus}
          </span>
          <div className={styles.rowSecondaryText}>
            {item.inspections.length} verificação(oes) - {item.occurrences.filter((o) => o.status === "open").length} ocorrência(s) aberta(s)
          </div>
        </td>
        <td>
          <div className={styles.rowActions}>
            <button type="button" className={styles.iconButton} onClick={onToggle}>
              <ShieldCheck size={14} />
              {expanded ? "Recolher" : "Inspeção"}
            </button>
            {isLocked ? null : (
              <button
                type="button"
                className={`${styles.iconButton} ${styles.dangerButton}`}
                onClick={() => onDeleteItem(item)}
                disabled={saving}
              >
                <Trash2 size={14} />
                Excluir
              </button>
            )}
          </div>
        </td>
      </tr>
      {expanded ? (
        <tr>
          <td colSpan={6}>
            <div className={styles.card}>
              <strong>Itens de inspeção</strong>
              {item.inspections.length ? (
                <div className={styles.tableWrapper}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Seq.</th>
                        <th>Verificação</th>
                        <th>Metodo</th>
                        <th>1a conferência</th>
                        <th>2a conferência</th>
                        <th>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {item.inspections.map((inspection) => (
                        <tr key={inspection.id}>
                          <td>{inspection.sequenceNumber}</td>
                          <td>{inspection.description}</td>
                          <td>{inspection.verificationMethod || "-"}</td>
                          <td>
                            <span className={styles.statusPill}>
                              {inspectionStatusLabel[inspection.firstStatus] ?? inspection.firstStatus}
                            </span>
                            <div className={styles.rowSecondaryText}>
                              {inspection.firstStatusAt ? formatDate(inspection.firstStatusAt) : "não conferido"}
                            </div>
                          </td>
                          <td>
                            <span className={styles.statusPill}>
                              {inspectionStatusLabel[inspection.secondStatus] ?? inspection.secondStatus}
                            </span>
                            <div className={styles.rowSecondaryText}>
                              {inspection.secondStatusAt ? formatDate(inspection.secondStatusAt) : "não conferido"}
                            </div>
                          </td>
                          <td>
                            <div className={styles.rowActions}>
                              {isLocked ? null : (
                                <>
                                  {inspection.firstStatus === "pending" ? (
                                    <>
                                      <button
                                        type="button"
                                        className={styles.iconButton}
                                        onClick={() => onVerifyInspection(inspection, 1, "compliant")}
                                        disabled={saving}
                                      >
                                        <CheckCircle size={14} />
                                        1a OK
                                      </button>
                                      <button
                                        type="button"
                                        className={styles.iconButton}
                                        onClick={() => onVerifyInspection(inspection, 1, "non_compliant")}
                                        disabled={saving}
                                      >
                                        <TriangleAlert size={14} />
                                        1a NOK
                                      </button>
                                    </>
                                  ) : inspection.secondStatus === "pending" ? (
                                    <>
                                      <button
                                        type="button"
                                        className={styles.iconButton}
                                        onClick={() => onVerifyInspection(inspection, 2, "compliant")}
                                        disabled={saving}
                                      >
                                        <CheckCircle size={14} />
                                        2a OK
                                      </button>
                                      <button
                                        type="button"
                                        className={styles.iconButton}
                                        onClick={() => onVerifyInspection(inspection, 2, "non_compliant")}
                                        disabled={saving}
                                      >
                                        <TriangleAlert size={14} />
                                        2a NOK
                                      </button>
                                    </>
                                  ) : (
                                    <span className={styles.badgeSuccess}>Dupla verificação concluída</span>
                                  )}
                                  <button
                                    type="button"
                                    className={`${styles.iconButton} ${styles.dangerButton}`}
                                    onClick={() => onDeleteInspection(inspection)}
                                    disabled={saving}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className={styles.metricHint}>Nenhum item de inspeção cadastrado.</p>
              )}

              {isLocked ? null : (
                <form className={styles.formGrid} onSubmit={handleInspectionSubmit}>
                  <label className={styles.filterControl}>
                    <span>Nova verificação*</span>
                    <input
                      type="text"
                      value={inspectionForm.description}
                      onChange={(event) =>
                        setInspectionForm((form) => ({ ...form, description: event.target.value }))
                      }
                      placeholder="Prumo e alinhamento"
                      required
                    />
                  </label>
                  <label className={styles.filterControl}>
                    <span>Metodo</span>
                    <input
                      type="text"
                      value={inspectionForm.verificationMethod}
                      onChange={(event) =>
                        setInspectionForm((form) => ({ ...form, verificationMethod: event.target.value }))
                      }
                      placeholder="Régua de 2m em 3 pontos"
                    />
                  </label>
                  <label className={styles.filterControl}>
                    <span>&nbsp;</span>
                    <button type="submit" className={styles.primaryButton} disabled={saving}>
                      <Plus size={16} />
                      Adicionar verificação
                    </button>
                  </label>
                </form>
              )}

              <strong>Ocorrências</strong>
              {item.occurrences.length ? (
                <div className={styles.tableWrapper}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Seq.</th>
                        <th>Problema</th>
                        <th>Solução</th>
                        <th>Status</th>
                        <th>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {item.occurrences.map((occurrence) => (
                        <tr key={occurrence.id}>
                          <td>{occurrence.sequenceNumber}</td>
                          <td>
                            {occurrence.problem}
                            <div className={styles.rowSecondaryText}>
                              {occurrence.openedAt ? formatDate(occurrence.openedAt) : "-"}
                              {occurrence.inspectorPersonId
                                ? ` - ${inspectorNameById[occurrence.inspectorPersonId] ?? "conferente"}`
                                : ""}
                            </div>
                          </td>
                          <td>
                            {occurrence.status === "open" && !isLocked ? (
                              <input
                                type="text"
                                value={solutionDrafts[occurrence.id] ?? ""}
                                onChange={(event) =>
                                  setSolutionDrafts((drafts) => ({
                                    ...drafts,
                                    [occurrence.id]: event.target.value,
                                  }))
                                }
                                placeholder="Descreva a solução"
                              />
                            ) : (
                              occurrence.solution || "-"
                            )}
                          </td>
                          <td>
                            <span className={styles.statusPill}>
                              {occurrenceStatusLabel[occurrence.status] ?? occurrence.status}
                            </span>
                            <div className={styles.rowSecondaryText}>
                              {occurrence.closedAt ? formatDate(occurrence.closedAt) : ""}
                            </div>
                          </td>
                          <td>
                            <div className={styles.rowActions}>
                              {isLocked ? null : (
                                <>
                                  {occurrence.status === "open" ? (
                                    <button
                                      type="button"
                                      className={styles.iconButton}
                                      onClick={async () => {
                                        const resolved = await onResolveOccurrence(
                                          occurrence,
                                          solutionDrafts[occurrence.id] ?? ""
                                        )
                                        if (resolved) {
                                          setSolutionDrafts((drafts) => ({ ...drafts, [occurrence.id]: "" }))
                                        }
                                      }}
                                      disabled={saving}
                                    >
                                      <CheckCircle size={14} />
                                      Resolver
                                    </button>
                                  ) : null}
                                  <button
                                    type="button"
                                    className={`${styles.iconButton} ${styles.dangerButton}`}
                                    onClick={() => onDeleteOccurrence(occurrence)}
                                    disabled={saving}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className={styles.metricHint}>Nenhuma ocorrência registrada.</p>
              )}

              {isLocked ? null : (
                <form className={styles.formGrid} onSubmit={handleOccurrenceSubmit}>
                  <label className={styles.filterControl}>
                    <span>Novo problema*</span>
                    <input
                      type="text"
                      value={occurrenceForm.problem}
                      onChange={(event) =>
                        setOccurrenceForm((form) => ({ ...form, problem: event.target.value }))
                      }
                      placeholder="Trinca na alvenaria junto ao pilar"
                      required
                    />
                  </label>
                  <label className={styles.filterControl}>
                    <span>Solução (opcional)</span>
                    <input
                      type="text"
                      value={occurrenceForm.solution}
                      onChange={(event) =>
                        setOccurrenceForm((form) => ({ ...form, solution: event.target.value }))
                      }
                      placeholder="Deixe vazio para registrar só o problema"
                    />
                  </label>
                  <label className={styles.filterControl}>
                    <span>&nbsp;</span>
                    <button type="submit" className={styles.primaryButton} disabled={saving}>
                      <Plus size={16} />
                      Registrar ocorrência
                    </button>
                  </label>
                </form>
              )}
            </div>
          </td>
        </tr>
      ) : null}
    </>
  )
}

function SchedulePhaseModal({ mode, schedulePhaseForm, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={mode === "create" ? "Nova fase" : "Editar fase"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{mode === "create" ? "Nova fase" : "Editar fase"}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Nome*</span>
              <input
                type="text"
                value={schedulePhaseForm.name}
                onChange={(event) => onChange("name", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Ordem*</span>
              <input
                type="number"
                min="1"
                value={schedulePhaseForm.sequenceOrder}
                onChange={(event) => onChange("sequenceOrder", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Status*</span>
              <select
                value={schedulePhaseForm.status}
                onChange={(event) => onChange("status", event.target.value)}
                required
              >
                {scheduleStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.filterControl}>
              <span>Progresso (%)</span>
              <input
                type="number"
                min="0"
                max="100"
                value={schedulePhaseForm.progressPercent}
                onChange={(event) => onChange("progressPercent", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Inicio previsto</span>
              <input
                type="date"
                value={schedulePhaseForm.plannedStartDate}
                onChange={(event) => onChange("plannedStartDate", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Fim previsto</span>
              <input
                type="date"
                value={schedulePhaseForm.plannedEndDate}
                onChange={(event) => onChange("plannedEndDate", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Inicio real</span>
              <input
                type="date"
                value={schedulePhaseForm.actualStartDate}
                onChange={(event) => onChange("actualStartDate", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Fim real</span>
              <input
                type="date"
                value={schedulePhaseForm.actualEndDate}
                onChange={(event) => onChange("actualEndDate", event.target.value)}
              />
            </label>
          </div>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Salvando..." : mode === "create" ? "Criar fase" : "Salvar alterações"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function formatDate(value) {
  if (!value) {
    return "-"
  }

  const parsedDate = new Date(value)
  if (Number.isNaN(parsedDate.getTime())) {
    return "-"
  }

  return dateFormatter.format(parsedDate)
}

function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-"
  }

  return moneyFormatter.format(Number(value))
}
