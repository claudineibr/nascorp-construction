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
  RotateCcw,
  Route,
  Send,
  ShieldCheck,
  Upload,
  ShoppingCart,
  Trash2,
  Unlock,
} from "lucide-react"
import styles from "./App.module.css"
import CreatableCombobox from "./components/CreatableCombobox.jsx"
import { InspectionChecklist } from "./features/measurementInspections/InspectionChecklist"
import {
  countBlockingLines,
  countPendingLines,
  itemStatusLabel,
} from "./features/measurementInspections/inspectionVocabulary"
import { ServiceTemplatesPanel } from "./features/serviceTemplates/ServiceTemplatesPanel.jsx"
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
  listErpCompanyBankAccounts,
  listErpPaymentMethods,
  reverseConstructionUnitInstallment,
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

// A forma ingenua (`toISOString().slice(0, 10)`) devolve a data em UTC, e o
// arquivo ja tinha quatro copias dela.
const todayISO = () => {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

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

const defaultCommissionForm = {
  beneficiaryPersonId: "",
  amount: "",
  dueDate: "",
  installments: "1",
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

// Um diálogo so por parcela: a baixa por N formas absorveu os campos que o
// "Editar parcela" tinha (numero do documento e observacao).
const defaultPayInstallmentForm = {
  lines: [],
  interest: "",
  fine: "",
  discount: "",
  observation: "",
  documentNumber: "",
}

let installmentLineSeq = 0
const newInstallmentLine = (defaults = {}) => ({
  key: `installment-line-${(installmentLineSeq += 1)}`,
  paymentMethod: defaults.paymentMethod ?? "",
  amount: defaults.amount ?? "",
  paidAt: defaults.paidAt || todayISO(),
  documentNumber: "",
  companyBankAccountId: defaults.companyBankAccountId ?? "",
})

// O rodape da regra da tela: o que foi lancado, o que ha para receber e o que
// falta. O botao so destrava quando falta zero -- e o servidor refaz a mesma
// conta sob lock, entao a tela nunca e a autoridade.
const installmentClosing = (installment, form) => {
  const posted = (form.lines ?? []).reduce(
    (total, line) => total + parseCurrencyToNumber(line.amount),
    0,
  )
  const due = Math.max(
    0,
    installmentOutstanding(installment)
      + parseCurrencyToNumber(form.interest)
      + parseCurrencyToNumber(form.fine)
      - parseCurrencyToNumber(form.discount),
  )
  return { posted, due, missing: due - posted, closes: Math.abs(due - posted) < 0.005 }
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

// Saldo zerado: cobrar mais exigiria um valor que a venda nao tem. Os botoes
// ficam visiveis e desabilitados -- some-los esconderia que a acao existe.
const NOTHING_LEFT_TO_CHARGE =
  "Saldo devedor zerado: tudo que o comprador deve já está lançado. Para cobrar a mais, aumente o preço da venda ou inclua uma documentação."

// A ancora do saldo sai das fontes gravadas. Venda antiga nao tem fonte
// nenhuma -- a tabela so passou a ser preenchida depois que elas foram
// confirmadas -- e ai o unico registro do plano que sobrou sao as proprias
// parcelas do contas a receber. Sem esse fallback o formulario reabre zerado,
// e como a secao some na edicao ninguem ve que zerou: salvar refaz o plano
// inteiro em silencio.
function saleFormFieldsFromPlan(plan) {
  const fields = saleFormFieldsFromSources(plan?.sources)
  if (String(fields.firstDueDate ?? "").trim()) {
    return fields
  }

  const dated = (plan?.paymentPlan?.installments ?? []).filter((installment) =>
    String(installment.dueDate ?? "").trim(),
  )
  if (!dated.length) {
    return fields
  }

  // Preferimos as em aberto: sao elas que serao refeitas, entao e a data da
  // primeira delas que o usuario reconhece como "o proximo vencimento".
  const open = dated.filter((installment) => installment.status !== "PAID")
  const anchor = open.length ? open : dated
  const ordered = [...anchor].sort((first, second) =>
    String(first.dueDate).localeCompare(String(second.dueDate)),
  )

  return { ...fields, firstDueDate: ordered[0].dueDate, installments: String(ordered.length) }
}

// Soma meses numa data ISO sem passar por fuso: "2026-11-10" + 5 = "2027-04-10".
// Dia que nao existe no mes de destino cai no ultimo dia dele (31/01 + 1 = 28/02),
// que e como o parcelamento do ERP trata a virada.
function addMonthsToIsoDate(value, months) {
  const [year, month, day] = String(value ?? "")
    .split("-")
    .map(Number)
  if (!year || !month || !day) {
    return ""
  }

  const target = new Date(Date.UTC(year, month - 1 + months, 1))
  const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate()
  target.setUTCDate(Math.min(day, lastDay))

  return target.toISOString().slice(0, 10)
}

// O saldo so comeca a ser cobrado depois que a entrada termina -- cobrar os dois
// no mesmo mes dobraria a prestacao do comprador. Sem entrada, o saldo comeca um
// mes depois da ultima previsao de liberacao do banco, que e quando a construtora
// sabe o quanto sobrou para financiar direto.
function suggestBalanceDueDate(formSale) {
  const downPaymentAmount = parseCurrencyFormValue(formSale.downPaymentAmount)
  const downPaymentDueDate = String(formSale.downPaymentDueDate ?? "").trim()
  if (downPaymentAmount > 0 && downPaymentDueDate) {
    const installments = Math.max(Number(formSale.downPaymentInstallments || 1), 1)
    return addMonthsToIsoDate(downPaymentDueDate, installments)
  }

  const settlementDueDates = salePaymentSourceDefinitions
    .filter((definition) => !SALE_INSTALLMENT_SOURCE_TYPES.includes(definition.sourceType))
    .filter((definition) => parseCurrencyFormValue(formSale[definition.amountField]) > 0)
    .map((definition) => String(formSale[definition.dueDateField] ?? "").trim())
    .filter(Boolean)
    .sort()

  if (settlementDueDates.length) {
    return addMonthsToIsoDate(settlementDueDates[settlementDueDates.length - 1], 1)
  }

  return ""
}

// O vencimento do saldo saiu da tela: ninguém digita mais. Ele é derivado da
// data que a venda já tem, e quem quiser outro plano usa Refazer plano de
// pagamento depois -- que é onde parcelas e vencimento continuam editáveis.
function resolveBalanceDueDate(formSale) {
  const informed = String(formSale.firstDueDate ?? "").trim()
  if (informed) {
    return informed
  }

  const suggested = suggestBalanceDueDate(formSale)
  if (suggested) {
    return suggested
  }

  const signatureDate = String(formSale.contractSignatureDate ?? "").trim()
  if (signatureDate) {
    return addMonthsToIsoDate(signatureDate, 1)
  }

  return ""
}

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

function requiredSaleFieldError(formSale, { isEditing = false } = {}) {
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
  for (const paymentSource of paymentSources) {
    if (!String(paymentSource.dueDate ?? "").trim()) {
      return `Informe o vencimento de ${paymentSource.label}.`
    }

    const sourceInstallments = Number(paymentSource.installments)
    if (!Number.isInteger(sourceInstallments) || sourceInstallments <= 0 || sourceInstallments > 120) {
      return `Parcelas de ${paymentSource.label} devem estar entre 1 e 120.`
    }

    if (
      !SALE_INSTALLMENT_SOURCE_TYPES.includes(paymentSource.sourceType) &&
      Number(paymentSource.installments) > 1
    ) {
      return `${paymentSource.label} depende de liberação do banco e não pode ser parcelado.`
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

  // O saldo é validado sempre que existe, e não só quando nenhuma fonte foi
  // informada. Antes o retorno era antecipado assim que havia qualquer fonte,
  // e por isso venda com entrada era gravada sem que o vencimento do saldo
  // fosse conferido -- o saldo ia para o banco com a data da entrada junto.
  if (balance <= 0.01) {
    return null
  }

  // O vencimento do saldo não tem campo na tela: ele é derivado em
  // resolveBalanceDueDate e só falta aqui se a venda não tiver nenhuma data de
  // onde partir, o que exige refazer o plano.
  if (!String(formSale.firstDueDate ?? "").trim() && !resolveBalanceDueDate(formSale)) {
    return "Esta venda não tem nenhuma data de onde partir o parcelamento. Informe o vencimento da entrada ou das liberações do banco."
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
  // Estado da carga da composição gravada. "failed" trava o salvar de
  // propósito: sem ela o payload iria sem entrada nem saldo, e o backend
  // recomporia o plano por cima das parcelas em aberto.
  const [saleComposition, setSaleComposition] = useState({
    status: "ready",
    receivableTotal: null,
    commissionOffset: 0,
  })

  const [isRebuildPlanModalOpen, setIsRebuildPlanModalOpen] = useState(false)
  const [rebuildPlanUnit, setRebuildPlanUnit] = useState(null)
  const [rebuildPlanForm, setRebuildPlanForm] = useState(defaultSaleUnitForm)
  const [rebuildPlanComposition, setRebuildPlanComposition] = useState({
    balance: 0,
    paidTotal: 0,
    paidCount: 0,
  })
  const [submittingRebuildPlan, setSubmittingRebuildPlan] = useState(false)
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
  const [paymentMethodOptions, setPaymentMethodOptions] = useState([])
  const [companyBankAccounts, setCompanyBankAccounts] = useState([])
  const [confirmRequest, setConfirmRequest] = useState(null)
  const [confirmRunning, setConfirmRunning] = useState(false)
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

  const handleDeleteProject = (project) => {
    setConfirmRequest({
      title: `Remover a obra ${project.code}`,
      message: `${project.name} sai da lista, junto com o que estiver pendurado nela.`,
      confirmLabel: "Remover obra",
      run: () => runDeleteProject(project),
    })
  }

  const runDeleteProject = async (project) => {
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

  const handleDeleteBlock = (block) => {
    setConfirmRequest({
      title: `Remover o bloco ${block.code}`,
      message: `${block.name} sai da obra.`,
      confirmLabel: "Remover bloco",
      run: () => runDeleteBlock(block),
    })
  }

  const runDeleteBlock = async (block) => {
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

  const handleDeleteSchedulePhase = (phase) => {
    setConfirmRequest({
      title: "Remover fase do cronograma",
      message: `A fase "${phase.name}" sai do cronograma da obra.`,
      confirmLabel: "Remover fase",
      run: () => runDeleteSchedulePhase(phase),
    })
  }

  const runDeleteSchedulePhase = async (phase) => {
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

  const handleDeleteUnit = (unit) => {
    setConfirmRequest({
      title: `Remover a unidade ${unit.code}`,
      message: "A unidade sai da obra, junto com o que estiver ligado a ela.",
      confirmLabel: "Remover unidade",
      run: () => runDeleteUnit(unit),
    })
  }

  const runDeleteUnit = async (unit) => {
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

  const handleReleaseUnit = (unit) => {
    setConfirmRequest({
      title: `Liberar a reserva da unidade ${unit.code}`,
      message: "A unidade volta a ficar disponível e o interessado perde a reserva.",
      confirmLabel: "Liberar reserva",
      run: () => runReleaseUnit(unit),
    })
  }

  const runReleaseUnit = async (unit) => {
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
      setSaleComposition({ status: "ready", receivableTotal: null, commissionOffset: 0 })
      return
    }

    // Venda já confirmada: o formulário tem de abrir com a composição que está
    // valendo, senão editar o comprador zeraria os valores sem avisar. Enquanto
    // ela não chega o salvar fica travado -- na edição a composição não tem
    // campo visível, então um form pela metade passaria despercebido.
    setSaleComposition({ status: "loading", receivableTotal: null, commissionOffset: 0 })
    try {
      const plan = await getConstructionUnitPaymentPlan({ bridge, unitId: unit.id })
      setSaleUnitForm((current) => ({
        ...current,
        ...saleFormFieldsFromPlan(plan),
        documentations: (plan.documentations ?? []).map((documentation) => ({
          key: nextSaleDocumentationKey(),
          documentationTypeId: documentation.documentationTypeId ?? "",
          documentationTypeName: documentation.name ?? "",
          amount: formatCurrencyFromNumber(documentation.amount),
        })),
      }))
      setSaleComposition({
        status: "ready",
        receivableTotal: plan.paymentPlan?.receivableTotalAmount ?? null,
        commissionOffset: Number(plan.commissionOffset ?? 0),
      })
    } catch (requestError) {
      setSaleComposition({ status: "failed", receivableTotal: null, commissionOffset: 0 })
      bridge?.feedback?.warning?.(
        requestError?.message ?? "Não foi possível carregar a composição atual da venda.",
      )
    }
  }

  const openRebuildPlanModal = async (unit) => {
    setRebuildPlanUnit(unit)
    setRebuildPlanForm(defaultSaleUnitForm)
    setRebuildPlanComposition({ balance: 0, paidTotal: 0, paidCount: 0 })
    setIsRebuildPlanModalOpen(true)

    try {
      const plan = await getConstructionUnitPaymentPlan({ bridge, unitId: unit.id })
      const planFields = saleFormFieldsFromPlan(plan)

      // O que ja foi pago e historico e nao entra no plano novo. O formulario
      // trabalha sobre o RESTANTE -- e o numero que interessa a quem esta
      // reparcelando --, e o submit recompoe o total antes de enviar: o
      // confirm-sale continua recebendo a venda inteira, senao ela encolheria
      // a cada reparcelamento.
      const paidInstallments = (plan.paymentPlan?.installments ?? []).filter(
        (installment) => installment.status === "PAID",
      )
      const paidTotal = paidInstallments.reduce(
        (total, installment) => total + Number(installment.paidAmount ?? installment.amount ?? 0),
        0,
      )
      const paidCount = paidInstallments.length
      const remainingFields = paidCount
        ? {
            downPaymentAmount: formatCurrencyFromNumber(
              Math.max(parseCurrencyFormValue(planFields.downPaymentAmount) - paidTotal, 0),
            ),
            downPaymentInstallments: String(
              Math.max(Number(planFields.downPaymentInstallments || 1) - paidCount, 1),
            ),
          }
        : {}

      // Refazer o plano reenvia a venda inteira pelo confirm-sale: o que nao se
      // edita aqui precisa ir junto exatamente como esta gravado, senao some.
      setRebuildPlanForm({
        ...defaultSaleUnitForm,
        buyerPersonId: unit.buyerPersonId ?? "",
        secondaryBuyerPersonId: unit.secondaryBuyerPersonId ?? "",
        brokerPersonId: unit.brokerPersonId ?? "",
        salePrice: formatCurrencyFromNumber(unit.salePrice),
        discountAmount: formatCurrencyFromNumber(unit.discountAmount),
        contractSignatureDate: unit.contractSignatureDate ?? "",
        saleNotes: unit.saleNotes ?? "",
        ...planFields,
        ...remainingFields,
        documentations: (plan.documentations ?? []).map((documentation) => ({
          key: nextSaleDocumentationKey(),
          documentationTypeId: documentation.documentationTypeId ?? "",
          documentationTypeName: documentation.name ?? "",
          amount: formatCurrencyFromNumber(documentation.amount),
        })),
      })
      // Mesma conta do backend, menos a entrada -- que é editável aqui e sai do
      // formulário: preço + documentação - desconto - banco - sinal que compõe.
      setRebuildPlanComposition({
        balance:
          Number(plan.totalCharged ?? 0) -
          Number(plan.settlementTotal ?? 0) -
          Number(plan.commissionOffset ?? 0),
        paidTotal,
        paidCount,
      })
    } catch (requestError) {
      setIsRebuildPlanModalOpen(false)
      setRebuildPlanUnit(null)
      bridge?.feedback?.error?.(
        requestError?.message ?? "Não foi possível carregar a composição atual da venda.",
      )
    }
  }

  const closeRebuildPlanModal = () => {
    if (submittingRebuildPlan) {
      return
    }

    setIsRebuildPlanModalOpen(false)
    setRebuildPlanUnit(null)
    setRebuildPlanForm(defaultSaleUnitForm)
    setRebuildPlanComposition({ balance: 0, paidTotal: 0, paidCount: 0 })
  }

  const handleRebuildPlanChange = (field, value) => {
    setRebuildPlanForm((currentForm) => ({ ...currentForm, [field]: value }))
  }

  const handleRebuildPlanSubmit = async (event) => {
    event.preventDefault()

    if (!rebuildPlanUnit) {
      return
    }

    // O formulario mostra o restante; o confirm-sale espera a venda inteira. As
    // parcelas pagas voltam para o total aqui -- o backend as reconhece pela
    // posicao e recria so o que vem depois delas.
    const { paidTotal, paidCount } = rebuildPlanComposition
    const saleForm = paidCount
      ? {
          ...rebuildPlanForm,
          downPaymentAmount: formatCurrencyFromNumber(
            parseCurrencyFormValue(rebuildPlanForm.downPaymentAmount) + Number(paidTotal ?? 0),
          ),
          downPaymentInstallments: String(
            Math.max(Number(rebuildPlanForm.downPaymentInstallments || 1), 1) + Number(paidCount),
          ),
        }
      : rebuildPlanForm

    const validationError = requiredSaleFieldError(saleForm)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    setSubmittingRebuildPlan(true)
    try {
      await confirmConstructionUnitSale({
        bridge,
        unitId: rebuildPlanUnit.id,
        saleData: {
          ...saleForm,
          firstDueDate: resolveBalanceDueDate(saleForm),
          paymentSources: buildSalePaymentSourcesFromForm(saleForm),
          documentations: buildSaleDocumentationsFromForm(saleForm),
        },
      })
      bridge?.feedback?.success?.("Plano de pagamento refeito.")
      setIsRebuildPlanModalOpen(false)
      setRebuildPlanUnit(null)
      setRebuildPlanForm(defaultSaleUnitForm)
      await loadUnitPaymentPlan(rebuildPlanUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(
        requestError?.message ?? "Não foi possível refazer o plano de pagamento.",
      )
    } finally {
      setSubmittingRebuildPlan(false)
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
    if (!paymentMethodOptions.length) {
      void loadSettlementOptions()
    }
    setPayingInstallment(installment)
    const hasPayments = (installment.payments?.length ?? 0) > 0
    const agreedExtras = hasPayments
      ? 0
      : (Number(installment.interest) || 0)
        + (Number(installment.fine) || 0)
        - (Number(installment.discount) || 0)
    const outstanding = installmentOutstanding(installment) + agreedExtras
    setPayInstallmentForm({
      ...defaultPayInstallmentForm,
      // Uma linha ja semeada com o saldo: a baixa de uma forma so fica a um
      // clique, e quem recebeu em duas divide a partir dai.
      lines:
        outstanding > 0
          ? [
              newInstallmentLine({
                paymentMethod: installment.paymentMethod || "",
                amount: formatCurrencyFromNumber(outstanding),
              }),
            ]
          : [],
      // O combinado da parcela so vale no PRIMEIRO recebimento -- e a mesma
      // regra do servidor. Com recebimento anterior, os campos nascem vazios.
      interest: hasPayments ? "" : formatCurrencyFromNumber(installment.interest) || "",
      fine: hasPayments ? "" : formatCurrencyFromNumber(installment.fine) || "",
      discount: hasPayments ? "" : formatCurrencyFromNumber(installment.discount) || "",
      documentNumber: installment.documentNumber ?? "",
      observation: installment.observation ?? "",
    })
  }

  const handlePayInstallmentLineChange = (key, field, value) => {
    setPayInstallmentForm((current) => ({
      ...current,
      lines: current.lines.map((line) => (line.key === key ? { ...line, [field]: value } : line)),
    }))
  }

  const handleAddPayInstallmentLine = () => {
    setPayInstallmentForm((current) => {
      // A linha nova herda a data da anterior: dinheiro que chega em duas formas
      // costuma chegar no mesmo dia, e quando nao chega o operador troca o campo.
      const previous = current.lines[current.lines.length - 1]
      const { missing } = installmentClosing(payingInstallment, current)
      return {
        ...current,
        lines: [
          ...current.lines,
          // A linha nova herda data E conta da anterior: dinheiro que chega em
          // duas formas costuma chegar no mesmo dia e no mesmo banco.
          newInstallmentLine({
            paidAt: previous?.paidAt,
            companyBankAccountId: previous?.companyBankAccountId,
            amount: missing > 0 ? formatCurrencyFromNumber(missing) : "",
          }),
        ],
      }
    })
  }

  const handleRemovePayInstallmentLine = (key) => {
    setPayInstallmentForm((current) => ({
      ...current,
      lines: current.lines.filter((line) => line.key !== key),
    }))
  }

  // O diálogo fundido guarda o que o "Editar parcela" guardava. Sem esta porta,
  // corrigir o numero do documento de uma parcela em aberto exigiria baixa-la.
  const handleSaveInstallmentData = async () => {
    if (!payingInstallment || !selectedUnit) {
      return
    }

    // So viaja o que o usuario mexeu: o PATCH do ERP trata ausente como
    // "mantem", e mandar o valor atual de volta marcaria a parcela como
    // alterada na auditoria sem nada ter mudado.
    const changes = {}
    if (payInstallmentForm.documentNumber !== (payingInstallment.documentNumber ?? "")) {
      changes.document_number = payInstallmentForm.documentNumber
    }
    if (payInstallmentForm.observation !== (payingInstallment.observation ?? "")) {
      changes.observation = payInstallmentForm.observation
    }

    if (!Object.keys(changes).length) {
      bridge?.feedback?.warning?.("Nenhuma alteração para salvar nesta parcela.")
      return
    }

    setSubmittingInstallmentPayment(true)
    try {
      await updateConstructionUnitInstallment({
        bridge,
        unitId: selectedUnit.id,
        installmentNumber: payingInstallment.installmentNumber,
        receivableId: payingInstallment.receivableId ?? null,
        changes,
      })
      bridge?.feedback?.success?.("Parcela atualizada.")
      setPayingInstallment(null)
      setPayInstallmentForm(defaultPayInstallmentForm)
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível editar a parcela.")
    } finally {
      setSubmittingInstallmentPayment(false)
    }
  }

  const handleReverseInstallment = (installment) => {
    if (!selectedUnit) {
      return
    }

    setConfirmRequest({
      title: `Estornar baixa da parcela ${installment.installmentNumber}`,
      message:
        "Todos os recebimentos da parcela são apagados e ela volta a ficar em aberto. Os "
        + "lançamentos contábeis saem junto.",
      confirmLabel: "Estornar baixa",
      run: async () => {
        try {
          await reverseConstructionUnitInstallment({
            bridge,
            unitId: selectedUnit.id,
            installmentNumber: installment.installmentNumber,
            receivableId: installment.receivableId ?? null,
          })
          bridge?.feedback?.success?.("Baixa estornada. A parcela voltou a ficar em aberto.")
          await loadUnitPaymentPlan(selectedUnit.id)
        } catch (requestError) {
          bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível estornar a baixa.")
        }
      },
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

    const { closes } = installmentClosing(payingInstallment, payInstallmentForm)
    if (!closes) {
      bridge?.feedback?.warning?.(
        "A soma das formas de recebimento precisa fechar o valor a receber.",
      )
      return
    }

    setSubmittingInstallmentPayment(true)
    try {
      await payConstructionUnitInstallment({
        bridge,
        unitId: selectedUnit.id,
        installmentNumber: payingInstallment.installmentNumber,
        receivableId: payingInstallment.receivableId ?? null,
        paymentData: {
          ...payInstallmentForm,
          payments: payInstallmentForm.lines.map((line) => ({
            paymentMethod: line.paymentMethod,
            amount: line.amount,
            paidAt: line.paidAt,
            documentNumber: line.documentNumber || payInstallmentForm.documentNumber,
            companyBankAccountId: line.companyBankAccountId,
          })),
        },
      })
      bridge?.feedback?.success?.("Parcela baixada.")
      setPayingInstallment(null)
      setPayInstallmentForm(defaultPayInstallmentForm)
      await loadUnitPaymentPlan(selectedUnit.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível baixar a parcela.")
    } finally {
      setSubmittingInstallmentPayment(false)
    }
  }

  const runConfirmedAction = async () => {
    if (!confirmRequest || confirmRunning) {
      return
    }

    setConfirmRunning(true)
    try {
      await confirmRequest.run()
    } finally {
      setConfirmRunning(false)
      setConfirmRequest(null)
    }
  }

  const handleDeleteInstallment = (installment) => {
    if (!selectedUnit) {
      return
    }

    setConfirmRequest({
      title: `Excluir parcela ${installment.installmentNumber} ${
        installment.receivableId ? "do aditivo" : "da venda"
      }`,
      message:
        "A parcela é cancelada e os lançamentos contábeis dela são desfeitos. As outras parcelas "
        + "continuam como estão.",
      confirmLabel: "Excluir parcela",
      run: async () => {
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
      },
    })
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
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível incluir o sinal.")
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

  const handleDeleteCommission = (commission) => {
    if (!selectedUnit) {
      return
    }

    // Sem confirmação um clique em "Excluir" -- vizinho de "Baixar sinal" no
    // mesmo menu -- destruía o lançamento na hora, e o sinal não tem de onde
    // ser recuperado.
    setConfirmRequest({
      title: `Excluir sinal ${commission.sequenceNumber ?? ""}`.trim(),
      message:
        "O sinal compõe o valor da venda: excluir devolve esse valor ao saldo devedor da unidade.",
      confirmLabel: "Excluir sinal",
      run: async () => {
        try {
          await deleteConstructionUnitCommission({ bridge, commissionId: commission.id })
          bridge?.feedback?.success?.("Sinal removido.")
          await loadUnitPaymentPlan(selectedUnit.id)
        } catch (requestError) {
          bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover o sinal.")
        }
      },
    })
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
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível incluir o aditivo.")
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
    setSaleComposition({ status: "ready", receivableTotal: null, commissionOffset: 0 })
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

    if (saleComposition.status === "loading") {
      bridge?.feedback?.warning?.("Aguarde: a composição atual da venda ainda está carregando.")
      return
    }

    if (saleComposition.status === "failed") {
      bridge?.feedback?.error?.(
        "A composição atual da venda não foi carregada. Feche e abra novamente: salvar agora refaria as parcelas em aberto com dados incompletos.",
      )
      return
    }

    const validationError = requiredSaleFieldError(saleUnitForm, {
      isEditing: saleTargetUnit.status === "sold",
    })
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
          firstDueDate: resolveBalanceDueDate(saleUnitForm),
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

  // As formas de recebimento e as contas bancarias vem do financeiro: enquanto a
  // lista de formas morava aqui, uma forma nova so aparecia na tela com deploy do
  // MFE — e com o rótulo escrito de novo, livre para divergir do recibo.
  //
  // Carregadas na primeira abertura do diálogo, nao na montagem do modulo: quem
  // nunca baixa parcela nao paga por elas.
  const loadSettlementOptions = useCallback(async () => {
    const [methods, accounts] = await Promise.all([
      listErpPaymentMethods({ bridge }).catch(() => []),
      listErpCompanyBankAccounts({ bridge }).catch(() => []),
    ])
    setPaymentMethodOptions(methods)
    setCompanyBankAccounts(accounts)
  }, [bridge])

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

  const handleVerifyInspection = async (inspection, { status, comment, inspectorPersonId, openOccurrence }) => {
    setSavingMeasurementItem(true)
    try {
      const updated = await verifyConstructionMeasurementInspection({
        bridge,
        inspectionId: inspection.id,
        status,
        comment,
        inspectorPersonId,
        openOccurrence,
      })
      bridge?.feedback?.success?.(
        updated.roundsCount > 1 ? "Reinspeção registrada." : "Verificação registrada."
      )
      await loadMeasurementItems(itemsTargetMeasurement.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível registrar a verificação.")
    } finally {
      setSavingMeasurementItem(false)
    }
  }

  // Um unico recarregamento no fim. Recarregar a lista a cada linha faria a
  // ficha inteira piscar por varios segundos no 3G da obra.
  const handleVerifyAllPendingInspections = async (item, { inspectorPersonId }) => {
    const pending = (item.inspections ?? []).filter((inspection) => !inspection.roundsCount)
    if (pending.length === 0) {
      return
    }

    setSavingMeasurementItem(true)
    try {
      for (const inspection of pending) {
        await verifyConstructionMeasurementInspection({
          bridge,
          inspectionId: inspection.id,
          status: "compliant",
          inspectorPersonId,
        })
      }
      bridge?.feedback?.success?.(`${pending.length} linha(s) marcada(s) como conforme.`)
      await loadMeasurementItems(itemsTargetMeasurement.id)
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível registrar as verificações.")
      await loadMeasurementItems(itemsTargetMeasurement.id)
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

  const handleDeleteMeasurement = (measurement) => {
    setConfirmRequest({
      title: `Remover a medição ${measurement.code}`,
      message: "A medição sai da obra e deixa de contar no avanço.",
      confirmLabel: "Remover medição",
      run: () => runDeleteMeasurement(measurement),
    })
  }

  const runDeleteMeasurement = async (measurement) => {
    try {
      await deleteConstructionMeasurement({ bridge, measurementId: measurement.id })
      bridge?.feedback?.success?.("Medição removida com sucesso.")
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível remover a medição.")
    }
  }

  const handleApproveMeasurement = (measurement) => {
    setConfirmRequest({
      title: `Aprovar a medição ${measurement.code}`,
      message: "A medição passa a valer e conta no avanço da obra.",
      confirmLabel: "Aprovar medição",
      danger: false,
      run: () => runApproveMeasurement(measurement),
    })
  }

  const runApproveMeasurement = async (measurement) => {
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

  const handleDeleteProcurement = (procurementRequest) => {
    setConfirmRequest({
      title: `Remover a requisição ${procurementRequest.code}`,
      message: "A requisição sai da lista com todos os itens dela.",
      confirmLabel: "Remover requisição",
      run: () => runDeleteProcurement(procurementRequest),
    })
  }

  const runDeleteProcurement = async (procurementRequest) => {
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

  const handleSubmitProcurement = (procurementRequest) => {
    setConfirmRequest({
      title: `Enviar a requisição ${procurementRequest.code} para aprovação`,
      message: "A requisição sai da sua mão e vai para quem aprova. Até a resposta ela fica parada.",
      confirmLabel: "Enviar para aprovação",
      danger: false,
      run: () => runSubmitProcurement(procurementRequest),
    })
  }

  const runSubmitProcurement = async (procurementRequest) => {
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

  const handleApproveProcurement = (procurementRequest) => {
    setConfirmRequest({
      title: `Aprovar a requisição ${procurementRequest.code}`,
      message: "A requisição fica liberada para a compra seguir.",
      confirmLabel: "Aprovar requisição",
      danger: false,
      run: () => runApproveProcurement(procurementRequest),
    })
  }

  const runApproveProcurement = async (procurementRequest) => {
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
              {viewMode === "serviceTemplates" ? (
                <span className={styles.breadcrumbItem}>
                  <span className={styles.separator}>/</span>
                  <span className={styles.breadcrumbCurrent}>Catálogo de serviços</span>
                </span>
              ) : null}
            </nav>
            <h1 className={styles.title}>{viewMode === "serviceTemplates" ? "Catálogo de serviços" : "Obras"}</h1>
          </div>
          {viewMode === "projects" ? (
            <div className={styles.heroActions}>
              <button type="button" className={styles.primaryButton} onClick={openCreateProject}>
                <Plus size={18} />
                Nova obra
              </button>
              <button
                type="button"
                className={styles.secondaryButton}
                onClick={() => setViewMode("serviceTemplates")}
              >
                <ListChecks size={16} />
                Catálogo de serviços
              </button>
              <button type="button" className={styles.secondaryButton} onClick={loadProjects} disabled={loading}>
                <RefreshCw size={16} className={loading ? styles.spinIcon : undefined} />
                Recarregar
              </button>
            </div>
          ) : null}
          {viewMode === "serviceTemplates" ? (
            <div className={styles.heroActions}>
              <button type="button" className={styles.secondaryButton} onClick={() => setViewMode("projects")}>
                <ChevronLeft size={16} />
                Voltar para obras
              </button>
            </div>
          ) : null}
        </div>

        {viewMode === "serviceTemplates" ? null : (
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
        )}
      </section>

      {viewMode === "serviceTemplates" ? (
        <DomainCard
          subtitle="Fichas de verificação usadas nas medições. Valem para todas as obras da empresa."
          content={<ServiceTemplatesPanel bridge={bridge} />}
        />
      ) : null}

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
                    onReverseInstallment={handleReverseInstallment}
                    onPayInstallment={handleOpenPayInstallment}
                    onDeleteInstallment={handleDeleteInstallment}
                    onDeleteAdjustment={handleOpenDeleteAdjustment}
                    onCreateInstallment={handleOpenCreateInstallment}
                    onRebuildPlan={openRebuildPlanModal}
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
          composition={saleComposition}
        />
      ) : null}

      {isRebuildPlanModalOpen && rebuildPlanUnit ? (
        <RebuildSalePlanModal
          unit={rebuildPlanUnit}
          form={rebuildPlanForm}
          composition={rebuildPlanComposition}
          onClose={closeRebuildPlanModal}
          onChange={handleRebuildPlanChange}
          onSubmit={handleRebuildPlanSubmit}
          loading={submittingRebuildPlan}
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
          paymentMethods={paymentMethodOptions}
          bankAccounts={companyBankAccounts}
          onClose={closePayInstallmentModal}
          onChange={handlePayInstallmentChange}
          onLineChange={handlePayInstallmentLineChange}
          onAddLine={handleAddPayInstallmentLine}
          onRemoveLine={handleRemovePayInstallmentLine}
          onSaveData={handleSaveInstallmentData}
          onSubmit={handleSubmitPayInstallment}
          loading={submittingInstallmentPayment}
        />
      ) : null}

      {confirmRequest ? (
        <ConfirmModal
          title={confirmRequest.title}
          message={confirmRequest.message}
          confirmLabel={confirmRequest.confirmLabel}
          danger={confirmRequest.danger !== false}
          loading={confirmRunning}
          onCancel={() => (confirmRunning ? null : setConfirmRequest(null))}
          onConfirm={runConfirmedAction}
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

      {itemsTargetMeasurement ? (
        <MeasurementItemsModal
          bridge={bridge}
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
          onVerifyAllPendingInspections={handleVerifyAllPendingInspections}
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
          {title ? <h2>{title}</h2> : null}
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
  onReverseInstallment,
  onPayInstallment,
  onDeleteInstallment,
  onDeleteAdjustment,
  onCreateInstallment,
  onRebuildPlan,
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
          <button type="button" className={styles.primaryButton} onClick={() => onEdit(unit)}>
            <Pencil size={16} />
            Editar unidade
          </button>
          {canEditSale ? (
            <button type="button" className={styles.primaryButton} onClick={() => onSale(unit)}>
              <ShoppingCart size={16} />
              Editar venda
            </button>
          ) : null}
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

      {activeTab === "summary" ? (
        <UnitSaleCompositionCard unit={unit} plan={paymentPlan} />
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
          onReverseInstallment={onReverseInstallment}
          onPayInstallment={onPayInstallment}
          onDeleteInstallment={onDeleteInstallment}
          onCreateAdjustment={onCreateAdjustment}
          onDeleteAdjustment={onDeleteAdjustment}
          onCreateInstallment={onCreateInstallment}
          onRebuildPlan={onRebuildPlan}
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

// A composicao vive na aba Resumo: ela descreve a venda, nao as parcelas, e
// ocupava metade da tela de Parcelas empurrando o contas a receber para baixo.
function UnitSaleCompositionCard({ unit, plan }) {
  const canSale = (unit.status === "available" || unit.status === "reserved") && unit.analyticCostCenterId

  const composition = plan ?? {}
  const sources = composition.sources ?? []
  const installmentSources = sources.filter((source) => source.generatesInstallments)
  // O saldo nao gera parcela, mas tambem nao e liberacao de banco: e divida do
  // comprador esperando virar sinal ou aditivo. Separar os dois evita a tela
  // dizer que o banco cobre o que o comprador ainda deve.
  const balanceSources = sources.filter(
    (source) => !source.generatesInstallments && SALE_BALANCE_SOURCE_TYPES.includes(source.sourceType),
  )
  const settlementSources = sources.filter(
    (source) => !source.generatesInstallments && !SALE_BALANCE_SOURCE_TYPES.includes(source.sourceType),
  )
  const documentations = composition.documentations ?? []
  const commissions = composition.commissions ?? []
  const commissionOffset = Number(composition.commissionOffset ?? 0)
  const orderedSources = installmentSources.concat(settlementSources, balanceSources)

  return (
    <div className={styles.card}>
      <strong>Como a venda foi composta</strong>
      <p className={styles.metricHint}>
        O que o banco libera (subsídio, FGTS e financiamento) entra no preço da venda mas não vira parcela: a
        data de pagamento depende da liberação. A <strong>documentação</strong> é cobrada do comprador junto
        do preço. O <strong>sinal</strong> também compõe a venda, mas é pago direto ao corretor e por isso não
        entra no contas a receber. O que sobra depois de tudo isso é o <strong>saldo</strong>, que não vira
        parcela sozinho: quem o cobra é um sinal novo ou um aditivo. Só a <strong>entrada</strong> gera as
        parcelas do contas a receber.
      </p>
      {sources.length || commissions.length ? (
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
              {orderedSources.map((source) => {
                const isBalance = SALE_BALANCE_SOURCE_TYPES.includes(source.sourceType)
                return (
                  <tr key={source.sourceType}>
                    <td>
                      <strong>{source.label}</strong>
                      <div className={styles.rowSecondaryText}>
                        {source.generatesInstallments
                          ? "cobrado do comprador"
                          : isBalance
                            ? "ainda sem cobrança lançada"
                            : "liberado pelo banco"}
                      </div>
                    </td>
                    <td>{formatMoney(source.amount)}</td>
                    <td>
                      {source.generatesInstallments
                        ? `${source.installments} x ${formatMoney(Number(source.amount ?? 0) / Math.max(source.installments, 1))}`
                        : isBalance
                          ? "lance sinal ou aditivo"
                          : "a vista, sem parcela"}
                    </td>
                    <td>{source.dueDate ? formatDate(source.dueDate) : "-"}</td>
                  </tr>
                )
              })}
              {commissionOffset > 0 ? (
                <tr>
                  <td>
                    <strong>Sinal</strong>
                    <div className={styles.rowSecondaryText}>
                      pago ao corretor, fora do contas a receber
                    </div>
                  </td>
                  <td>{formatMoney(commissionOffset)}</td>
                  <td>
                    {commissions.length > 1
                      ? `${commissions.length} lançamentos`
                      : "1 lançamento"}
                  </td>
                  <td>
                    {commissions.length && commissions[0].dueDate
                      ? formatDate(commissions[0].dueDate)
                      : "-"}
                  </td>
                </tr>
              ) : null}
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
  onReverseInstallment,
  onPayInstallment,
  onDeleteInstallment,
  onCreateAdjustment,
  onDeleteAdjustment,
  onCreateInstallment,
  onRebuildPlan,
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
  // Saldo zerado significa que tudo que o comprador deve ja esta lancado.
  // Cobrar mais exigiria um valor que a venda nao tem, entao a acao some em vez
  // de deixar o usuario montar a cobranca e levar recusa no final.
  const hasBalanceToCharge = unit.status !== "sold" || Number(composition.balanceTotal ?? 0) > 0
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
        <div className={styles.tableHeaderRow}>
          <div>
            <strong>Contas a receber da unidade</strong>
            <p className={styles.metricHint}>
              <strong>Parcela</strong> é o parcelamento da
              venda e <strong>Aditivo</strong> é a cobrança extra de quando o financiamento sai abaixo
              do previsto. Cada tipo tem a sua própria numeração, e o aditivo é um documento separado
              no contas a receber - editar a venda não mexe nele.
            </p>
          </div>
          <div className={styles.tableHeaderActions}>
            {canEditSale ? (
              <button type="button" className={styles.primaryButton} onClick={() => onRebuildPlan(unit)}>
                <ShoppingCart size={16} />
                Refazer plano de pagamento
              </button>
            ) : null}
            {paymentPlan.receivableId ? (
              <span title={hasBalanceToCharge ? undefined : NOTHING_LEFT_TO_CHARGE}>
                <button
                  type="button"
                  className={styles.primaryButton}
                  disabled={!hasBalanceToCharge}
                  onClick={() => onCreateInstallment({ receivableId: null, installments })}
                >
                  <Plus size={16} />
                  Incluir parcela
                </button>
              </span>
            ) : null}
            {canCreateAdjustment ? (
              <span title={hasBalanceToCharge ? undefined : NOTHING_LEFT_TO_CHARGE}>
                <button
                  type="button"
                  className={styles.primaryButton}
                  disabled={!hasBalanceToCharge}
                  onClick={onCreateAdjustment}
                >
                  <Plus size={16} />
                  Incluir aditivo
                </button>
              </span>
            ) : null}
          </div>
        </div>
        {paymentPlan.erpUnavailableReason ? (
          <p className={styles.metricHint}>
            Não foi possível consultar o ERP agora: {paymentPlan.erpUnavailableReason}
          </p>
        ) : null}
        {!hasBalanceToCharge ? (
          <p className={styles.metricHint}>
            Saldo devedor zerado: tudo que o comprador deve já está lançado, então não há parcela nem
            aditivo a incluir. Para cobrar a mais, aumente o preço da venda ou inclua uma documentação.
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
                          onReverseInstallment,
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
  onReverseInstallment,
  onPayInstallment,
  onDeleteInstallment,
  onDeleteAdjustment,
}) {
  const isPaid = installment.status === "PAID"
  const hasPayments = (installment.payments?.length ?? 0) > 0
  // D11: recibo emitido tranca a parcela. Os itens ficam visiveis e
  // desabilitados, para o operador entender que a acao existe e por que nao
  // cabe mais aqui.
  const receiptIssued = Boolean(installment.hasIssuedReceipt)
  const actions = []

  // Um diálogo so por parcela: "Baixar parcela" abre a composicao por formas e
  // carrega tambem o numero do documento e a observacao, que antes moravam num
  // "Editar parcela" separado.
  if (!isPaid) {
    actions.push({
      key: "pay",
      label: "Baixar parcela",
      icon: CheckCircle,
      onSelect: () => onPayInstallment(installment),
    })
    actions.push({
      key: "delete",
      label: "Excluir parcela",
      icon: Trash2,
      danger: true,
      disabled: receiptIssued,
      title: receiptIssued ? RECEIPT_ISSUED_HINT : undefined,
      onSelect: () => onDeleteInstallment(installment),
    })
  }

  // O estorno mora aqui desde o plano 15: a tela da unidade concentra a baixa
  // multi-forma, e mandar o operador ao Contas a Receber para corrigir supunha
  // uma permissao que ele pode nao ter.
  if (hasPayments) {
    actions.push({
      key: "reverse",
      label: "Estornar baixa",
      icon: RotateCcw,
      danger: true,
      disabled: receiptIssued,
      title: receiptIssued ? RECEIPT_ISSUED_HINT : undefined,
      onSelect: () => onReverseInstallment(installment),
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
            comprador, o caminho é <strong>incluir aditivo</strong>.
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

// Refazer o plano e a unica intencao que o modal de venda nao atende mais: la a
// composicao e somente leitura, para que corrigir um dado cadastral nao mexa em
// parcela sem querer. Quem quer mexer declara isso aqui.
function RebuildSalePlanModal({ unit, form, composition, onClose, onChange, onSubmit, loading }) {
  // O formulario guarda o RESTANTE a parcelar, nao o total da entrada: quem
  // abre esta tela quer saber o que ainda vai ser cobrado. O total volta a ser
  // montado no submit.
  const remainingAmount = parseCurrencyFormValue(form.downPaymentAmount)
  const remainingInstallments = Math.max(Number(form.downPaymentInstallments || 1), 1)
  const paidTotal = Number(composition.paidTotal ?? 0)
  const paidCount = Number(composition.paidCount ?? 0)
  const hasPaidInstallments = paidCount > 0
  const downPaymentAmount = remainingAmount + paidTotal
  const balance = Math.max(Number(composition.balance ?? 0) - downPaymentAmount, 0)
  const remainingInstallmentAmount =
    remainingInstallments > 0 ? remainingAmount / remainingInstallments : 0
  // O backend descarta as posicoes ja quitadas do plano, entao as parcelas
  // novas comecam tantos meses depois da data informada quantas forem as pagas.
  const firstNewDueDate = hasPaidInstallments
    ? addMonthsToIsoDate(form.downPaymentDueDate, paidCount)
    : form.downPaymentDueDate

  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Refazer plano de pagamento"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Refazer plano de pagamento{unit ? ` - unidade ${unit.code}` : ""}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <p className={styles.metricHint}>
            As parcelas <strong>em aberto</strong> são apagadas e recriadas com o que você definir aqui. As
            parcelas já pagas são preservadas e só o saldo restante é redistribuído. Vencimentos ajustados à
            mão numa parcela em aberto são perdidos.
          </p>
          <p className={styles.metricHint}>
            O restante da venda - comprador, preço, desconto, documentação e liberações do banco - fica como
            está. Para alterar esses, use <strong>Editar venda</strong>.
          </p>
          {hasPaidInstallments ? (
            <p className={styles.metricHint}>
              Já pagas: <strong>{paidCount} parcela(s)</strong> somando{" "}
              <strong>{formatMoney(paidTotal)}</strong>. Elas não são alteradas, e o valor a parcelar fica
              travado: depois do primeiro pagamento a venda virou histórico, e cobrar a mais é{" "}
              <strong>aditivo</strong> ou <strong>sinal</strong>.
            </p>
          ) : null}
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>{hasPaidInstallments ? "A parcelar - restante" : "Entrada - valor total"}</span>
              {hasPaidInstallments ? (
                <>
                  <strong className={styles.installmentPreview}>{formatMoney(remainingAmount)}</strong>
                  <span className={styles.rowSecondaryText}>
                    entrada de {formatMoney(downPaymentAmount)} - {formatMoney(paidTotal)} já pagos
                  </span>
                </>
              ) : (
                <input
                  type="text"
                  inputMode="decimal"
                  value={form.downPaymentAmount}
                  onChange={(event) => onChange("downPaymentAmount", formatCurrencyInput(event.target.value))}
                  placeholder="0,00"
                />
              )}
            </label>
            <label className={styles.filterControl}>
              <span>{hasPaidInstallments ? "Parcelas do restante" : "Parcelas da entrada"}</span>
              <input
                type="number"
                min="1"
                max="120"
                value={form.downPaymentInstallments}
                onChange={(event) => onChange("downPaymentInstallments", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>1o vencimento da entrada</span>
              <input
                type="date"
                value={form.downPaymentDueDate}
                onChange={(event) => onChange("downPaymentDueDate", event.target.value)}
              />
              {hasPaidInstallments ? (
                <span className={styles.rowSecondaryText}>
                  as parcelas novas começam em {formatDate(firstNewDueDate)}
                </span>
              ) : null}
            </label>
            <div className={styles.filterControl}>
              <span>Fica</span>
              <strong className={styles.installmentPreview}>
                {remainingAmount <= 0
                  ? "-"
                  : `${remainingInstallments} x ${formatMoney(remainingInstallmentAmount)}`}
              </strong>
            </div>
          </div>
          <div className={styles.formGrid}>
            <div className={styles.filterControl}>
              <span>Saldo devedor</span>
              <strong className={styles.installmentPreview}>{formatMoney(balance)}</strong>
              <span className={styles.rowSecondaryText}>
                preço + documentação - desconto - entrada - liberações do banco
              </span>
            </div>
            <div className={styles.filterControl}>
              <span>Como é cobrado</span>
              <strong className={styles.installmentPreview}>
                {balance > 0 ? "sinal ou aditivo" : "-"}
              </strong>
              <span className={styles.rowSecondaryText}>
                o saldo não vira parcela: lance o sinal ou um aditivo quando for cobrá-lo
              </span>
            </div>
          </div>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Refazendo..." : "Refazer plano"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function PayInstallmentModal({
  installment,
  form,
  paymentMethods,
  bankAccounts,
  onClose,
  onChange,
  onLineChange,
  onAddLine,
  onRemoveLine,
  onSaveData,
  onSubmit,
  loading,
}) {
  const { posted, due, missing, closes } = installmentClosing(installment, form)
  const everyLineIsFilled = form.lines.every(
    (line) => line.paymentMethod && parseCurrencyToNumber(line.amount) > 0,
  )
  const locked = Boolean(installment?.hasIssuedReceipt)
  const existingPayments = installment?.payments ?? []
  const labelOfMethod = (value) =>
    paymentMethods.find((option) => option.value === value)?.label ?? value ?? ""

  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Baixar parcela"
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
            . A baixa só é aceita quando a soma das formas fecha o valor a receber.
          </p>

          {existingPayments.length ? (
            <div className={styles.formGrid}>
              <p className={`${styles.metricHint} ${styles.spanTwoColumns}`}>
                Já lançado nesta parcela:{" "}
                {existingPayments
                  .map(
                    (payment) =>
                      `${labelOfMethod(payment.paymentMethod)} `
                      + `${formatMoney(payment.netAmount ?? payment.amount)}`
                      + (payment.paidAt ? ` em ${formatDate(payment.paidAt)}` : ""),
                  )
                  .join(" + ")}
                .
              </p>
            </div>
          ) : null}

          {locked ? (
            <p className={styles.metricHint}>
              A parcela já tem recibo definitivo emitido — o número saiu do talão e o documento
              existe. A baixa é definitiva: não aceita alteração, estorno nem exclusão. Qualquer
              acerto tem que virar um lançamento novo.
            </p>
          ) : (
            <>
              {form.lines.map((line) => (
                <div className={styles.formGrid} key={line.key}>
                  <label className={styles.filterControl}>
                    <span>Forma de recebimento*</span>
                    <select
                      value={line.paymentMethod}
                      onChange={(event) => onLineChange(line.key, "paymentMethod", event.target.value)}
                      required
                    >
                      <option value="">Selecione</option>
                      {paymentMethods.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className={styles.filterControl}>
                    <span>Valor recebido*</span>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={line.amount}
                      onChange={(event) =>
                        onLineChange(line.key, "amount", formatCurrencyInput(event.target.value))
                      }
                      placeholder="0,00"
                      required
                    />
                  </label>
                  <label className={styles.filterControl}>
                    <span>Data</span>
                    <input
                      type="date"
                      value={line.paidAt}
                      onChange={(event) => onLineChange(line.key, "paidAt", event.target.value)}
                    />
                  </label>
                  <label className={styles.filterControl}>
                    <span>Nº do documento</span>
                    <input
                      type="text"
                      maxLength={100}
                      value={line.documentNumber}
                      onChange={(event) => onLineChange(line.key, "documentNumber", event.target.value)}
                    />
                  </label>
                  <label className={styles.filterControl}>
                    <span>Conta bancária</span>
                    <select
                      value={line.companyBankAccountId}
                      onChange={(event) =>
                        onLineChange(line.key, "companyBankAccountId", event.target.value)
                      }
                    >
                      <option value="">Herdar da parcela</option>
                      {bankAccounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className={styles.filterControl}>
                    <span>&nbsp;</span>
                    <button
                      type="button"
                      className={styles.secondaryButton}
                      onClick={() => onRemoveLine(line.key)}
                      disabled={form.lines.length === 1}
                    >
                      Remover forma
                    </button>
                  </div>
                </div>
              ))}

              <button type="button" className={styles.primaryButton} onClick={onAddLine}>
                <Plus size={16} />
                Incluir forma de recebimento
              </button>

              <div className={styles.formGrid}>
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
                <label className={styles.filterControl}>
                  <span>Nº do documento da parcela</span>
                  <input
                    type="text"
                    maxLength={100}
                    value={form.documentNumber}
                    onChange={(event) => onChange("documentNumber", event.target.value)}
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

              <p className={styles.metricHint} data-testid="installment-closing">
                Lançado {formatMoney(posted)} · A receber {formatMoney(due)} · Falta{" "}
                {formatMoney(Math.abs(missing))}
                {missing < -0.005 ? " a mais" : ""}
              </p>
            </>
          )}

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={onSaveData}
              disabled={loading || locked}
            >
              Salvar dados da parcela
            </button>
            <button
              type="submit"
              className={styles.primaryButton}
              disabled={loading || locked || !closes || !everyLineIsFilled || !form.lines.length}
              title={closes ? undefined : "A soma das formas precisa fechar o valor a receber."}
            >
              {loading ? "Baixando..." : "Baixar parcela"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

const RECEIPT_ISSUED_HINT =
  "Recibo já emitido: a parcela não pode mais ser alterada, estornada nem excluída."

function ConfirmModal({ title, message, confirmLabel, danger, onCancel, onConfirm, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onCancel}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{title}</h3>
          <button type="button" className={styles.closeButton} onClick={onCancel} disabled={loading}>
            Fechar
          </button>
        </header>
        <div className={styles.modalBody}>
          <p className={styles.metricHint}>{message}</p>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onCancel} disabled={loading}>
              Cancelar
            </button>
            <button
              type="button"
              className={
                danger ? `${styles.secondaryButton} ${styles.dangerButton}` : styles.primaryButton
              }
              onClick={onConfirm}
              disabled={loading}
            >
              {loading ? "Processando..." : confirmLabel}
            </button>
          </footer>
        </div>
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
  // Antes da venda nao ha composicao, e o sinal costuma ser lancado justamente
  // nessa fase. Depois de vendida, saldo zerado quer dizer que nao sobrou o que
  // cobrar do comprador.
  const hasBalanceToCharge = unit.status !== "sold" || Number(composition.balanceTotal ?? 0) > 0

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
              O sinal é pago pelo comprador direto ao corretor, então não passa pelo caixa da
              construtora e não vira conta a receber. Ele <strong>sempre compõe o valor da venda</strong>:
              ao ser lançado, já reduz o saldo que o comprador ainda deve.
            </p>
          </div>
          <span title={hasBalanceToCharge ? undefined : NOTHING_LEFT_TO_CHARGE}>
            <button
              type="button"
              className={styles.primaryButton}
              disabled={!hasBalanceToCharge}
              onClick={onCreate}
            >
              <Plus size={16} />
              Incluir sinal
            </button>
          </span>
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
          </div>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Incluindo..." : "Incluir sinal"}
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
        aria-label="Incluir aditivo"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Incluir aditivo{unit ? ` - unidade ${unit.code}` : ""}</h3>
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
              {loading ? "Incluindo..." : "Incluir aditivo"}
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
                title={action.title}
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
              warnUnqualified
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
              warnUnqualified
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

const QUALIFICATION_WARNINGS = {
  none: "Este fornecedor nunca foi qualificado. A obra pode seguir, mas a auditoria da Caixa pede a avaliacao registrada.",
  expired: "A qualificacao deste fornecedor venceu. Registre uma nova avaliacao no cadastro da pessoa.",
  rejected: "Este fornecedor foi REPROVADO na qualificacao. Confirme com o responsavel antes de seguir.",
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
  warnUnqualified = false,
}) {
  const hasSelectedPerson = people.some((person) => person.id === value)
  const selectedPerson = people.find((person) => person.id === value) ?? null

  // Avisa, nao bloqueia: no legado 69 fornecedores compraram sem qualificacao
  // nenhuma, em 359 pedidos. Barrar de saida trancaria a operacao.
  // O aviso so aparece com fornecedor escolhido -- nao a cada salvamento.
  const qualificationWarning =
    warnUnqualified && selectedPerson
      ? QUALIFICATION_WARNINGS[selectedPerson.qualificationStatus ?? "none"] ?? null
      : null

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
      {qualificationWarning ? (
        <small className={styles.qualificationWarning} data-testid="qualification-warning">
          {qualificationWarning}
        </small>
      ) : null}
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
  composition = { status: "ready", receivableTotal: null },
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

  // SALDO = preço + documentação - desconto - entrada - financiamento - FGTS
  //         - subsídio - sinal.
  // É a conta do legado (Dwelling/Resume.cshtml). A documentação é repasse
  // cobrado do comprador: não vira parcela própria, dilui no saldo. O sinal
  // faltava aqui: o backend já o abatia e a tela não, então uma venda com
  // sinal lançado exibia saldo devedor que não existia mais.
  const commissionOffset = Number(composition.commissionOffset ?? 0)
  const balance =
    grossSalePrice
    + documentationTotal
    - discountAmount
    - downPaymentTotal
    - settlementTotal
    - commissionOffset
  const balanceInstallments = Math.max(Number(saleForm.installments || 1), 1)
  const balanceInstallmentAmount = balance > 0 ? balance / balanceInstallments : 0

  const downPaymentSummaryInstallments = installmentSources
    .filter((source) => source.amountValue > 0)
    .reduce((total, source) => total + source.installments, 0)

  // Tudo que o comprador deve pela unidade. O sinal entra porque e dinheiro que
  // ele paga pela venda -- so nao passa pelo contas a receber, por ser pago
  // direto ao corretor.
  const receivableTotal = downPaymentTotal + commissionOffset + Math.max(balance, 0)
  const installmentCount =
    installmentSources
      .filter((source) => source.amountValue > 0)
      .reduce((total, source) => total + source.installments, 0) +
    (balance > 0 ? balanceInstallments : 0)
  const exceedsPrice = grossSalePrice > 0 && balance < -0.01

  const compositionFailed = isEditing && composition.status === "failed"
  const compositionLoading = isEditing && composition.status === "loading"
  // Venda e contas a receber podem ter saído de sincronia (venda gravada antes
  // das fontes serem persistidas, parcela removida à mão). Salvar realinha os
  // dois, e um salto de valor aqui não pode passar sem o usuário ver.
  const divergesFromReceivable =
    isEditing &&
    composition.status === "ready" &&
    composition.receivableTotal != null &&
    Math.abs(Number(composition.receivableTotal) - receivableTotal) > 0.01

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
          {compositionFailed ? (
            <p className={styles.metricHint}>
              <strong>A composição atual da venda não foi carregada.</strong> Feche e abra novamente: salvar
              agora refaria as parcelas em aberto com dados incompletos.
            </p>
          ) : null}
          {divergesFromReceivable ? (
            <p className={styles.metricHint}>
              <strong>Atenção:</strong> o contas a receber desta unidade está em{" "}
              {formatMoney(composition.receivableTotal)} e a composição acima soma{" "}
              {formatMoney(receivableTotal)}. Salvar vai ajustar o total para{" "}
              {formatMoney(receivableTotal)} e refazer as parcelas em aberto. Confira antes de continuar.
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
                <button type="button" className={styles.primaryButton} onClick={addDocumentationRow}>
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

          {isEditing ? (
            <div className={styles.card}>
              <div className={styles.scopeMeta}>
                <strong>Cobrado do comprador</strong>
                <span className={styles.metricHint}>
                  Definido quando a venda foi confirmada e mantido como está ao salvar. Para alterar entrada,
                  quantidade de parcelas ou vencimento, use <strong>Refazer plano de pagamento</strong> na aba
                  Parcelas.
                </span>
              </div>
              <div className={styles.formGrid}>
                <div className={styles.filterControl}>
                  <span>Entrada</span>
                  <strong className={styles.installmentPreview}>
                    {downPaymentTotal > 0
                      ? `${formatMoney(downPaymentTotal)} em ${downPaymentSummaryInstallments}x`
                      : "-"}
                  </strong>
                </div>
                <div className={styles.filterControl}>
                  <span>Saldo devedor</span>
                  <strong className={styles.installmentPreview}>
                    {balance > 0 ? `${balanceInstallments} x ${formatMoney(balanceInstallmentAmount)}` : "-"}
                  </strong>
                  <span className={styles.rowSecondaryText}>
                    preço + documentação - desconto - entrada - liberações do banco - sinal
                  </span>
                </div>
                <div className={styles.filterControl}>
                  <span>1o vencimento do saldo</span>
                  <strong className={styles.installmentPreview}>
                    {saleForm.firstDueDate ? formatDate(saleForm.firstDueDate) : "não definido"}
                  </strong>
                </div>
              </div>
            </div>
          ) : (
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
                  preço + documentação - desconto - entrada - liberações do banco - sinal
                </span>
              </div>
              <div className={styles.filterControl}>
                <span>Parcelamento do saldo</span>
                <strong className={styles.installmentPreview}>
                  {balance > 0 ? `${balanceInstallments} x ${formatMoney(balanceInstallmentAmount)}` : "-"}
                </strong>
                <span className={styles.rowSecondaryText}>
                  o saldo nasce em parcela única; para dividir, use Refazer plano de pagamento na aba
                  Parcelas
                </span>
              </div>
            </div>
          </div>
          )}

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
                      Sinal
                      <div className={styles.rowSecondaryText}>pago ao corretor, fora do contas a receber</div>
                    </td>
                    <td className={styles.textRight}>- {formatMoney(commissionOffset)}</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Saldo devedor</strong>
                      <div className={styles.rowSecondaryText}>ainda sem cobrança lançada</div>
                    </td>
                    <td className={styles.textRight}>
                      <strong>{formatMoney(Math.max(balance, 0))}</strong>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Total devido pelo comprador (entrada + sinal + saldo)</strong>
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
            <button
              type="submit"
              className={styles.primaryButton}
              disabled={loading || compositionLoading || compositionFailed}
            >
              {compositionLoading
                ? "Carregando composição..."
                : loading
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
  bridge,
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
  onVerifyAllPendingInspections,
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
  // O que importa agora e o que BLOQUEIA o envio: linha reprovada sem
  // reinspecao aprovada. O pendente vira o numero secundario.
  const blockingLines = items.reduce((total, item) => total + countBlockingLines(item.inspections), 0)
  const pendingLines = items.reduce((total, item) => total + countPendingLines(item.inspections), 0)
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
              <h3>Linhas bloqueando</h3>
              <p className={styles.metricValue}>{blockingLines}</p>
              <p className={styles.metricHint}>
                reprovadas sem reinspeção aprovada · {pendingLines} ainda não verificada(s)
              </p>
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
                  label="Inspetor responsável"
                  value={itemForm.inspectorPersonId}
                  onChange={(value) => handleItemChange("inspectorPersonId", value)}
                  people={people}
                  emptyLabel="Sem inspetor"
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
                      bridge={bridge}
                      item={item}
                      people={people}
                      isLocked={isLocked}
                      saving={saving}
                      expanded={expandedItemId === item.id}
                      onToggle={() => setExpandedItemId(expandedItemId === item.id ? null : item.id)}
                      onDeleteItem={onDeleteItem}
                      onCreateInspection={onCreateInspection}
                      onVerifyInspection={onVerifyInspection}
                      onVerifyAllPendingInspections={onVerifyAllPendingInspections}
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
  bridge,
  item,
  people,
  isLocked,
  saving,
  expanded,
  onToggle,
  onDeleteItem,
  onCreateInspection,
  onVerifyInspection,
  onVerifyAllPendingInspections,
  onDeleteInspection,
  onCreateOccurrence,
  onResolveOccurrence,
  onDeleteOccurrence,
}) {
  const [occurrenceForm, setOccurrenceForm] = useState(defaultOccurrenceForm)
  const [solutionDrafts, setSolutionDrafts] = useState({})

  const inspectorNameById = useMemo(
    () => Object.fromEntries(people.map((person) => [person.id, person.name])),
    [people]
  )

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
            {itemStatusLabel[item.inspectionStatus] ?? item.inspectionStatus}
          </span>
          <div className={styles.rowSecondaryText}>
            {item.inspections.length} linha(s) · {countBlockingLines(item.inspections)} aguardando reinspeção ·{" "}
            {item.occurrences.filter((o) => o.status === "open").length} ocorrência(s) aberta(s)
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
              <strong>Ficha de verificação de serviço (FVS)</strong>
              <InspectionChecklist
                bridge={bridge}
                item={item}
                people={people}
                saving={saving}
                isLocked={isLocked}
                // O MFE nao recebe as permissoes do usuario pelo bridge, entao
                // quem barra a dispensa e a API (400 com mensagem explicita) --
                // mesmo padrao das outras recusas de regra deste modulo.
                canWaive
                onVerifyInspection={onVerifyInspection}
                onVerifyAllPending={onVerifyAllPendingInspections}
                onDeleteInspection={onDeleteInspection}
                onCreateInspection={(lineData) => onCreateInspection(item.id, lineData)}
              />

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
                                ? ` - ${inspectorNameById[occurrence.inspectorPersonId] ?? "inspetor"}`
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
                                    aria-label="Excluir ocorrência"
                                    title="Excluir ocorrência"
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
