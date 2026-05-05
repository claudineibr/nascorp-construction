import { useCallback, useEffect, useMemo, useState } from "react"
import {
  Building2,
  CheckCircle,
  Clock,
  FileCog,
  HandCoins,
  Home,
  Layers3,
  ListChecks,
  PackageSearch,
  Pencil,
  Plus,
  RefreshCw,
  Route,
  ShoppingCart,
  Trash2,
  Unlock,
} from "lucide-react"
import styles from "./App.module.css"
import { resolveConstructionBridge } from "./bridge/constructionBridge.js"
import {
  approveConstructionProcurementRequest,
  approveConstructionMeasurement,
  confirmConstructionUnitSale,
  createConstructionBlock,
  createConstructionMeasurement,
  createConstructionProcurementRequest,
  createConstructionProject,
  createConstructionSchedulePhase,
  createConstructionUnit,
  deleteConstructionBlock,
  deleteConstructionMeasurement,
  deleteConstructionProcurementRequest,
  deleteConstructionProject,
  deleteConstructionSchedulePhase,
  deleteConstructionUnit,
  listConstructionBlocks,
  listConstructionMeasurements,
  listConstructionPersonSummaries,
  listConstructionProcurementRequests,
  listConstructionProjects,
  listConstructionSchedulePhases,
  listConstructionUnits,
  rejectConstructionProcurementRequest,
  rejectConstructionMeasurement,
  releaseConstructionUnitReservation,
  reserveConstructionUnit,
  submitConstructionProcurementRequest,
  updateConstructionBlock,
  updateConstructionMeasurement,
  updateConstructionProcurementRequest,
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
  completed: "Concluida",
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
  { value: "completed", label: "Concluida" },
  { value: "cancelled", label: "Cancelada" },
]

const scheduleStatusLabel = Object.fromEntries(scheduleStatusOptions.map((option) => [option.value, option.label]))

const unitStatusOptions = [
  { value: "available", label: "Disponivel" },
  { value: "reserved", label: "Reservada" },
  { value: "sold", label: "Vendida" },
  { value: "delivered", label: "Entregue" },
  { value: "terminated", label: "Distratada" },
  { value: "unavailable", label: "Indisponivel" },
]

const unitStatusLabel = Object.fromEntries(unitStatusOptions.map((option) => [option.value, option.label]))

const measurementStatusOptions = [
  { value: "draft", label: "Rascunho" },
  { value: "submitted", label: "Enviada" },
  { value: "in_approval", label: "Em aprovacao" },
  { value: "approved", label: "Aprovada" },
  { value: "rejected", label: "Rejeitada" },
  { value: "paid", label: "Paga" },
]

const measurementStatusLabel = Object.fromEntries(measurementStatusOptions.map((option) => [option.value, option.label]))

const procurementStatusOptions = [
  { value: "draft", label: "Rascunho" },
  { value: "pending_approval", label: "Aguardando aprovacao" },
  { value: "approved", label: "Aprovada" },
  { value: "rejected", label: "Rejeitada" },
  { value: "sent_to_erp", label: "Enviada ao ERP" },
]

const procurementStatusLabel = Object.fromEntries(procurementStatusOptions.map((option) => [option.value, option.label]))

const domainTabs = [
  { id: "overview", label: "Visao geral", icon: Building2 },
  { id: "projects", label: "Projetos", icon: Layers3 },
  { id: "blocks", label: "Blocos/Torres", icon: Route },
  { id: "units", label: "Unidades", icon: Home },
  { id: "schedule", label: "Cronograma", icon: ListChecks },
  { id: "measurements", label: "Medicoes", icon: HandCoins },
  { id: "procurement", label: "Requisicoes", icon: PackageSearch },
  { id: "integrations", label: "Integracoes", icon: FileCog },
]

const statusOptions = Object.entries(statusLabel)
  .filter(([value]) => value !== "canceled")
  .map(([value, label]) => ({ value, label }))

const dateFormatter = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" })
const moneyFormatter = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" })

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

const defaultUnitForm = {
  code: "",
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

const defaultSaleUnitForm = {
  buyerPersonId: "",
  salePrice: "",
  firstDueDate: "",
  installments: "1",
}

const defaultMeasurementForm = {
  code: "",
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
    addressZipCode: project.address?.zip_code ?? "",
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
    unitType: unit.unitType ?? "",
    typology: unit.typology ?? "",
    blockId: unit.blockId ?? "",
    floor: unit.floor ?? "",
    privateArea: unit.privateArea === null || unit.privateArea === undefined ? "" : String(unit.privateArea),
    totalArea: unit.totalArea === null || unit.totalArea === undefined ? "" : String(unit.totalArea),
    salePrice: unit.salePrice === null || unit.salePrice === undefined ? "" : String(unit.salePrice),
    status: unit.status ?? "available",
  }
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
      zip_code: formProject.addressZipCode,
    },
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
    return "Informe o codigo da obra."
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
    return "Informe o codigo do bloco."
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
    return "Informe uma ordem valida para a fase."
  }

  const progress = Number(formPhase.progressPercent)
  if (Number.isNaN(progress) || progress < 0 || progress > 100) {
    return "O progresso deve estar entre 0 e 100."
  }

  return null
}

function requiredUnitFieldError(formUnit) {
  if (!String(formUnit.code ?? "").trim()) {
    return "Informe o codigo da unidade."
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

function requiredSaleFieldError(formSale) {
  if (!String(formSale.buyerPersonId ?? "").trim()) {
    return "Informe a pessoa compradora para confirmar a venda."
  }

  if (!String(formSale.firstDueDate ?? "").trim()) {
    return "Informe a data do primeiro vencimento."
  }

  const installments = Number(formSale.installments)
  if (!Number.isInteger(installments) || installments <= 0 || installments > 120) {
    return "Parcelas devem estar entre 1 e 120."
  }

  return null
}

function requiredMeasurementFieldError(formMeasurement) {
  if (!String(formMeasurement.code ?? "").trim()) {
    return "Informe o codigo da medicao."
  }

  if (!String(formMeasurement.dueDate ?? "").trim()) {
    return "Informe a data de vencimento."
  }

  const grossAmount = Number(formMeasurement.grossAmount || 0)
  if (Number.isNaN(grossAmount) || grossAmount <= 0) {
    return "Informe o valor bruto da medicao."
  }

  return null
}

function requiredProcurementFieldError(formProcurement) {
  if (!String(formProcurement.title ?? "").trim()) {
    return "Informe o titulo da requisicao."
  }

  const estimatedAmount = Number(formProcurement.estimatedAmount || 0)
  if (Number.isNaN(estimatedAmount) || estimatedAmount <= 0) {
    return "Informe o valor estimado da requisicao."
  }

  return null
}

export default function ConstructionApp({ bridge: providedBridge } = {}) {
  const bridge = useMemo(() => providedBridge ?? resolveConstructionBridge(), [providedBridge])
  const [activeTab, setActiveTab] = useState("overview")
  const [activeProjectId, setActiveProjectId] = useState(null)

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
  const [saleUnitForm, setSaleUnitForm] = useState(defaultSaleUnitForm)
  const [saleTargetUnit, setSaleTargetUnit] = useState(null)
  const [submittingSale, setSubmittingSale] = useState(false)

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
      setError(requestError?.message ?? "Nao foi possivel carregar as obras.")
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
      return
    }

    const projectExists = projects.some((project) => project.id === activeProjectId)
    if (!activeProjectId || !projectExists) {
      setActiveProjectId(projects[0].id)
    }
  }, [activeProjectId, projects])

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
        hint: "sem vinculo analitico",
        icon: Clock,
        tone: "warning",
      },
      {
        label: "Unidades",
        value: units.length,
        hint: "na obra selecionada",
        icon: Home,
        tone: "muted",
      },
    ]
  }, [projects, totalProjects, units.length, visibleProjects.length])

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
      setBlockError(requestError?.message ?? "Nao foi possivel carregar os blocos.")
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
      setScheduleError(requestError?.message ?? "Nao foi possivel carregar o cronograma.")
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
      setUnitError(requestError?.message ?? "Nao foi possivel carregar as unidades.")
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
      setMeasurementError(requestError?.message ?? "Nao foi possivel carregar as medicoes.")
    } finally {
      setLoadingMeasurements(false)
    }
  }, [activeProjectId, bridge])

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
      setProcurementError(requestError?.message ?? "Nao foi possivel carregar as requisicoes.")
    } finally {
      setLoadingProcurement(false)
    }
  }, [activeProjectId, bridge])

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
        setPersonLookupError(requestError?.message ?? "Nao foi possivel carregar o cadastro de pessoas.")
      } finally {
        setLoadingPersonSummaries(false)
      }
    },
    [bridge]
  )

  useEffect(() => {
    if (activeTab !== "blocks") {
      return
    }

    void loadBlocks()
  }, [activeTab, loadBlocks])

  useEffect(() => {
    if (activeTab !== "schedule") {
      return
    }

    void loadSchedulePhases()
  }, [activeTab, loadSchedulePhases])

  useEffect(() => {
    if (activeTab !== "units") {
      return
    }

    void loadUnits()
    void loadBlocks()
  }, [activeTab, loadBlocks, loadUnits])

  useEffect(() => {
    if (activeTab !== "measurements") {
      return
    }

    void loadMeasurements()
  }, [activeTab, loadMeasurements])

  useEffect(() => {
    if (activeTab !== "procurement") {
      return
    }

    void loadProcurementRequests()
    if (!personSummaries.length) {
      void loadPersonSummaries()
    }
  }, [activeTab, loadPersonSummaries, loadProcurementRequests, personSummaries.length])

  useEffect(() => {
    if (!["units", "measurements"].includes(activeTab)) {
      return
    }

    if (!personSummaries.length) {
      void loadPersonSummaries()
    }
  }, [activeTab, loadPersonSummaries, personSummaries.length])

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

  const openCreateProject = () => {
    setProjectModalMode("create")
    setEditingProjectId(null)
    setProjectForm(defaultProjectForm)
    setIsProjectModalOpen(true)
  }

  const openEditProject = (project) => {
    setProjectModalMode("edit")
    setEditingProjectId(project.id)
    setProjectForm(toFormProject(project))
    setIsProjectModalOpen(true)
  }

  const closeProjectModal = () => {
    if (submittingProject) {
      return
    }

    setIsProjectModalOpen(false)
    setEditingProjectId(null)
    setProjectForm(defaultProjectForm)
  }

  const handleProjectFieldChange = (field, value) => {
    setProjectForm((currentProjectForm) => ({ ...currentProjectForm, [field]: value }))
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
        setActiveProjectId(createdProject.id)
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
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel salvar a obra.")
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
      await loadProjects()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel remover a obra.")
    }
  }

  const openCreateBlock = () => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Selecione uma obra antes de criar blocos.")
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
      bridge?.feedback?.warning?.("Selecione uma obra antes de salvar blocos.")
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
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel salvar o bloco.")
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
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel remover o bloco.")
    }
  }

  const openCreateSchedulePhase = () => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Selecione uma obra antes de criar fases.")
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
      bridge?.feedback?.warning?.("Selecione uma obra antes de salvar fases.")
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
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel salvar a fase.")
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
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel remover a fase.")
    }
  }

  const openCreateUnit = () => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Selecione uma obra antes de criar unidades.")
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

    const validationError = requiredUnitFieldError(unitForm)
    if (validationError) {
      bridge?.feedback?.warning?.(validationError)
      return
    }

    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Selecione uma obra antes de salvar unidades.")
      return
    }

    setSubmittingUnit(true)
    try {
      if (unitModalMode === "create") {
        await createConstructionUnit({
          bridge,
          projectId: activeProjectId,
          unitData: unitForm,
        })
        bridge?.feedback?.success?.("Unidade criada com sucesso.")
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
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel salvar a unidade.")
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
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel remover a unidade.")
    }
  }

  const openReserveUnitModal = (unit) => {
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
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel reservar a unidade.")
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
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel liberar a reserva da unidade.")
    }
  }

  const openSaleUnitModal = (unit) => {
    setSaleTargetUnit(unit)
    setSaleUnitForm({
      ...defaultSaleUnitForm,
      buyerPersonId: unit.buyerPersonId ?? "",
      salePrice: unit.salePrice === null || unit.salePrice === undefined ? "" : String(unit.salePrice),
    })
    setIsSaleModalOpen(true)
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
      await confirmConstructionUnitSale({
        bridge,
        unitId: saleTargetUnit.id,
        saleData: saleUnitForm,
      })
      bridge?.feedback?.success?.("Venda confirmada com sucesso.")
      closeSaleUnitModal()
      await loadUnits()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel confirmar a venda da unidade.")
    } finally {
      setSubmittingSale(false)
    }
  }

  const openCreateMeasurement = () => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Selecione uma obra antes de criar medicoes.")
      return
    }

    const nextSequenceNumber = measurements.length
      ? Math.max(...measurements.map((measurement) => Number(measurement.sequenceNumber || 0))) + 1
      : 1

    setMeasurementModalMode("create")
    setEditingMeasurementId(null)
    setMeasurementForm({
      ...defaultMeasurementForm,
      sequenceNumber: String(nextSequenceNumber),
    })
    setIsMeasurementModalOpen(true)
  }

  const openEditMeasurement = (measurement) => {
    setMeasurementModalMode("edit")
    setEditingMeasurementId(measurement.id)
    setMeasurementForm({
      code: measurement.code ?? "",
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
      bridge?.feedback?.warning?.("Selecione uma obra antes de salvar medicoes.")
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
        bridge?.feedback?.success?.("Medicao criada com sucesso.")
      } else if (editingMeasurementId) {
        await updateConstructionMeasurement({
          bridge,
          measurementId: editingMeasurementId,
          measurementData: measurementForm,
        })
        bridge?.feedback?.success?.("Medicao atualizada com sucesso.")
      }

      closeMeasurementModal()
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel salvar a medicao.")
    } finally {
      setSubmittingMeasurement(false)
    }
  }

  const handleDeleteMeasurement = async (measurement) => {
    const confirmed = window.confirm(`Deseja remover a medicao ${measurement.code}?`)
    if (!confirmed) {
      return
    }

    try {
      await deleteConstructionMeasurement({ bridge, measurementId: measurement.id })
      bridge?.feedback?.success?.("Medicao removida com sucesso.")
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel remover a medicao.")
    }
  }

  const handleApproveMeasurement = async (measurement) => {
    try {
      await approveConstructionMeasurement({ bridge, measurementId: measurement.id })
      bridge?.feedback?.success?.("Medicao aprovada com sucesso.")
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel aprovar a medicao.")
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
      bridge?.feedback?.success?.("Medicao rejeitada com sucesso.")
      closeRejectMeasurementModal()
      await loadMeasurements()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel rejeitar a medicao.")
    } finally {
      setSubmittingMeasurementReject(false)
    }
  }

  const openCreateProcurement = () => {
    if (!activeProjectId) {
      bridge?.feedback?.warning?.("Selecione uma obra antes de criar requisicoes.")
      return
    }

    setProcurementModalMode("create")
    setEditingProcurementId(null)
    setProcurementForm(defaultProcurementForm)
    setIsProcurementModalOpen(true)
  }

  const openEditProcurement = (procurementRequest) => {
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
      bridge?.feedback?.warning?.("Selecione uma obra antes de salvar requisicoes.")
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
        bridge?.feedback?.success?.("Requisicao criada com sucesso.")
      } else if (editingProcurementId) {
        await updateConstructionProcurementRequest({
          bridge,
          procurementRequestId: editingProcurementId,
          procurementData: procurementForm,
        })
        bridge?.feedback?.success?.("Requisicao atualizada com sucesso.")
      }

      closeProcurementModal()
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel salvar a requisicao.")
    } finally {
      setSubmittingProcurement(false)
    }
  }

  const handleDeleteProcurement = async (procurementRequest) => {
    const confirmed = window.confirm(`Deseja remover a requisicao ${procurementRequest.code}?`)
    if (!confirmed) {
      return
    }

    try {
      await deleteConstructionProcurementRequest({
        bridge,
        procurementRequestId: procurementRequest.id,
      })
      bridge?.feedback?.success?.("Requisicao removida com sucesso.")
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel remover a requisicao.")
    }
  }

  const handleSubmitProcurement = async (procurementRequest) => {
    try {
      await submitConstructionProcurementRequest({
        bridge,
        procurementRequestId: procurementRequest.id,
      })
      bridge?.feedback?.success?.("Requisicao enviada para aprovacao.")
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel enviar a requisicao.")
    }
  }

  const handleApproveProcurement = async (procurementRequest) => {
    try {
      await approveConstructionProcurementRequest({
        bridge,
        procurementRequestId: procurementRequest.id,
      })
      bridge?.feedback?.success?.("Requisicao aprovada com sucesso.")
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel aprovar a requisicao.")
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
      bridge?.feedback?.success?.("Requisicao rejeitada com sucesso.")
      closeRejectProcurementModal()
      await loadProcurementRequests()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Nao foi possivel rejeitar a requisicao.")
    } finally {
      setSubmittingProcurementReject(false)
    }
  }

  return (
    <main className={styles.page} data-theme={bridge?.theme ?? "light"}>
      <section className={styles.pageHeader}>
        <div className={styles.header}>
          <div className={styles.left}>
            <nav className={styles.breadcrumb} aria-label="Navegacao">
              <span className={styles.breadcrumbLink}>Inicio</span>
              <span className={styles.breadcrumbItem}>
                <span className={styles.separator}>/</span>
                <span className={styles.breadcrumbCurrent}>Obras</span>
              </span>
            </nav>
            <h1 className={styles.title}>Obras</h1>
          </div>
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

      <section className={styles.tabCard}>
        <div className={styles.tabList}>
          {domainTabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                type="button"
                className={`${styles.tabButton} ${activeTab === tab.id ? styles.tabButtonActive : ""}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            )
          })}
        </div>
      </section>

      <section className={styles.filtersCard}>
        <div className={styles.filtersGrid}>
          <label className={styles.filterControl}>
            <span>Buscar</span>
            <input
              type="text"
              value={filters.search}
              onChange={(event) => handleFilterChange("search", event.target.value)}
              placeholder="Codigo, nome ou CNPJ"
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

      {activeTab === "overview" && (
        <DomainCard
          title="Resumo operacional"
          subtitle="Fundacao visual com CRUD de projetos, blocos, unidades e cronograma."
          content={
            <p className={styles.textMuted}>
              As etapas 2, 3 e 4 habilitaram o CRUD de projetos, blocos, cronograma e unidades com fluxos de reserva,
              liberacao e confirmacao de venda.
            </p>
          }
        />
      )}

      {activeTab === "projects" && (
        <DomainCard
          title="Projetos"
          subtitle="CRUD completo com filtros, criacao, edicao e exclusao."
          content={
            <ProjectList
              projects={visibleProjects}
              loading={loading}
              error={error}
              onRetry={loadProjects}
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
      )}

      {activeTab === "blocks" && (
        <DomainCard
          title="Blocos/Torres"
          subtitle="CRUD por obra com codigo, status e total de pavimentos."
          content={
            <>
              <ProjectScopeHeader
                projects={projects}
                activeProjectId={activeProjectId}
                onProjectChange={setActiveProjectId}
                selectedProject={selectedProject}
                actionLabel="Novo bloco"
                onAction={openCreateBlock}
              />
              <BlocksList
                blocks={blocks}
                loading={loadingBlocks}
                error={blockError}
                onRetry={loadBlocks}
                onEdit={openEditBlock}
                onDelete={handleDeleteBlock}
              />
            </>
          }
        />
      )}

      {activeTab === "units" && (
        <DomainCard
          title="Unidades"
          subtitle="Inventario comercial com reserva, liberacao e confirmacao de venda."
          content={
            <>
              <ProjectScopeHeader
                projects={projects}
                activeProjectId={activeProjectId}
                onProjectChange={setActiveProjectId}
                selectedProject={selectedProject}
                actionLabel="Nova unidade"
                onAction={openCreateUnit}
              />
              <UnitsList
                units={units}
                blocks={blocks}
                loading={loadingUnits}
                error={unitError}
                onRetry={loadUnits}
                onEdit={openEditUnit}
                onDelete={handleDeleteUnit}
                onReserve={openReserveUnitModal}
                onRelease={handleReleaseUnit}
                onSale={openSaleUnitModal}
              />
            </>
          }
        />
      )}

      {activeTab === "schedule" && (
        <DomainCard
          title="Cronograma"
          subtitle={`CRUD de fases com sequencia e progresso medio de ${scheduleProgress}%`}
          content={
            <>
              <ProjectScopeHeader
                projects={projects}
                activeProjectId={activeProjectId}
                onProjectChange={setActiveProjectId}
                selectedProject={selectedProject}
                actionLabel="Nova fase"
                onAction={openCreateSchedulePhase}
              />
              <ScheduleList
                phases={schedulePhases}
                loading={loadingSchedule}
                error={scheduleError}
                onRetry={loadSchedulePhases}
                onEdit={openEditSchedulePhase}
                onDelete={handleDeleteSchedulePhase}
              />
            </>
          }
        />
      )}

      {activeTab === "measurements" && (
        <DomainCard
          title="Medicoes"
          subtitle="Boletins de medicao com aprovacao, rejeicao e snapshot financeiro."
          content={
            <>
              <ProjectScopeHeader
                projects={projects}
                activeProjectId={activeProjectId}
                onProjectChange={setActiveProjectId}
                selectedProject={selectedProject}
                actionLabel="Nova medicao"
                onAction={openCreateMeasurement}
              />
              <MeasurementsList
                measurements={measurements}
                loading={loadingMeasurements}
                error={measurementError}
                onRetry={loadMeasurements}
                onEdit={openEditMeasurement}
                onDelete={handleDeleteMeasurement}
                onApprove={handleApproveMeasurement}
                onReject={openRejectMeasurement}
              />
            </>
          }
        />
      )}
      {activeTab === "procurement" && (
        <DomainCard
          title="Requisicoes"
          subtitle="Solicitacoes de compra com fluxo de envio, aprovacao e integracao ERP."
          content={
            <>
              <ProjectScopeHeader
                projects={projects}
                activeProjectId={activeProjectId}
                onProjectChange={setActiveProjectId}
                selectedProject={selectedProject}
                actionLabel="Nova requisicao"
                onAction={openCreateProcurement}
              />
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
            </>
          }
        />
      )}
      {activeTab === "integrations" && (
        <DomainCard
          title="Integracoes"
          subtitle="Referencias ERP para pessoas, financeiro e compras sincronizadas no modulo."
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
      )}

      {isProjectModalOpen ? (
        <ProjectModal
          mode={projectModalMode}
          projectForm={projectForm}
          onClose={closeProjectModal}
          onChange={handleProjectFieldChange}
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
          loading={submittingSale}
        />
      ) : null}

      {isMeasurementModalOpen ? (
        <MeasurementModal
          mode={measurementModalMode}
          measurementForm={measurementForm}
          people={personSummaries}
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

function DomainCard({ title, subtitle, content, footer = null }) {
  return (
    <div className={`${styles.card} ${styles.tableCard}`}>
      <div className={styles.tableHeaderRow}>
        <div>
          <h2>{title}</h2>
          {subtitle ? <p className={styles.textMuted}>{subtitle}</p> : null}
        </div>
      </div>
      {content}
      {footer ? <div className={styles.paginationSlot}>{footer}</div> : null}
    </div>
  )
}

function PhasePlaceholder({ title, phase }) {
  return (
    <DomainCard
      title={title}
      subtitle={`${phase}: implementacao funcional prevista nas proximas etapas.`}
      content={<div className={styles.empty}>Estrutura pronta para evolucao incremental.</div>}
    />
  )
}

function ProjectScopeHeader({ projects, activeProjectId, onProjectChange, selectedProject, actionLabel, onAction }) {
  return (
    <div className={styles.scopeHeader}>
      <div className={styles.scopeContent}>
        <label className={styles.filterControl}>
          <span>Obra de referencia</span>
          <select value={activeProjectId ?? ""} onChange={(event) => onProjectChange(event.target.value || null)}>
            {!projects.length ? <option value="">Nenhuma obra cadastrada</option> : null}
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.code} - {project.name}
              </option>
            ))}
          </select>
        </label>
        {selectedProject ? (
          <div className={styles.scopeMeta}>
            <span className={`${styles.statusPill} ${styles[`status${selectedProject.status}`] || ""}`}>
              {statusLabel[selectedProject.status] ?? selectedProject.status}
            </span>
            <span className={styles.rowSecondaryText}>Tipo: {projectTypeLabel[selectedProject.projectType]}</span>
          </div>
        ) : null}
      </div>
      <button type="button" className={styles.primaryButton} onClick={onAction}>
        <Plus size={16} />
        {actionLabel}
      </button>
    </div>
  )
}

function ProjectList({ projects, loading, error, onRetry, onEdit, onDelete }) {
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
            <th>Codigo</th>
            <th>Obra</th>
            <th>Tipo</th>
            <th>Status</th>
            <th>Inicio</th>
            <th>Centro analitico</th>
            <th>Acoes</th>
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
                <div className={styles.rowActions}>
                  <button type="button" className={styles.iconButton} onClick={() => onEdit(project)}>
                    <Pencil size={14} />
                    Editar
                  </button>
                  <button
                    type="button"
                    className={`${styles.iconButton} ${styles.dangerButton}`}
                    onClick={() => onDelete(project)}
                  >
                    <Trash2 size={14} />
                    Excluir
                  </button>
                </div>
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
            <th>Codigo</th>
            <th>Nome</th>
            <th>Pavimentos</th>
            <th>Status</th>
            <th>Acoes</th>
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
                <div className={styles.rowActions}>
                  <button type="button" className={styles.iconButton} onClick={() => onEdit(block)}>
                    <Pencil size={14} />
                    Editar
                  </button>
                  <button
                    type="button"
                    className={`${styles.iconButton} ${styles.dangerButton}`}
                    onClick={() => onDelete(block)}
                  >
                    <Trash2 size={14} />
                    Excluir
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function UnitsList({ units, blocks, loading, error, onRetry, onEdit, onDelete, onReserve, onRelease, onSale }) {
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
            <th>Codigo</th>
            <th>Tipo</th>
            <th>Bloco</th>
            <th>Status</th>
            <th>Preco</th>
            <th>Contrato ERP</th>
            <th>Acoes</th>
          </tr>
        </thead>
        <tbody>
          {units.map((unit) => {
            const canReserve = unit.status === "available"
            const canRelease = unit.status === "reserved"
            const canSale = unit.status === "available" || unit.status === "reserved"

            return (
              <tr key={unit.id}>
                <td>{unit.code}</td>
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
                <td>{formatMoney(unit.salePrice)}</td>
                <td>
                  {unit.externalContractId ? (
                    <div>
                      <div className={styles.rowSecondaryText}>{unit.externalContractStatus || "ativo"}</div>
                      <span className={styles.badgeSuccess}>Vinculado</span>
                    </div>
                  ) : (
                    <span className={styles.badgeMuted}>Pendente</span>
                  )}
                </td>
                <td>
                  <div className={styles.rowActions}>
                    <button type="button" className={styles.iconButton} onClick={() => onEdit(unit)}>
                      <Pencil size={14} />
                      Editar
                    </button>
                    {canReserve ? (
                      <button type="button" className={styles.iconButton} onClick={() => onReserve(unit)}>
                        <Clock size={14} />
                        Reservar
                      </button>
                    ) : null}
                    {canRelease ? (
                      <button type="button" className={styles.iconButton} onClick={() => onRelease(unit)}>
                        <Unlock size={14} />
                        Liberar
                      </button>
                    ) : null}
                    {canSale ? (
                      <button type="button" className={styles.iconButton} onClick={() => onSale(unit)}>
                        <ShoppingCart size={14} />
                        Vender
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className={`${styles.iconButton} ${styles.dangerButton}`}
                      onClick={() => onDelete(unit)}
                    >
                      <Trash2 size={14} />
                      Excluir
                    </button>
                  </div>
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
            <th>Acoes</th>
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
                <div className={styles.rowActions}>
                  <button type="button" className={styles.iconButton} onClick={() => onEdit(phase)}>
                    <Pencil size={14} />
                    Editar
                  </button>
                  <button
                    type="button"
                    className={`${styles.iconButton} ${styles.dangerButton}`}
                    onClick={() => onDelete(phase)}
                  >
                    <Trash2 size={14} />
                    Excluir
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MeasurementsList({ measurements, loading, error, onRetry, onEdit, onDelete, onApprove, onReject }) {
  if (loading) {
    return (
      <div className={styles.tableWrapper} aria-busy="true">
        <div className={styles.empty}>
          <RefreshCw className={styles.spinIcon} size={16} />
          Carregando medicoes...
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
        <div className={styles.empty}>Nenhuma medicao cadastrada para a obra selecionada.</div>
      </div>
    )
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Codigo</th>
            <th>Tipo</th>
            <th>Status</th>
            <th>Valor liquido</th>
            <th>Vencimento</th>
            <th>Financeiro ERP</th>
            <th>Acoes</th>
          </tr>
        </thead>
        <tbody>
          {measurements.map((measurement) => {
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
                  {measurement.measurementType || "-"}
                  <div className={styles.rowSecondaryText}>{measurement.documentType || "-"}</div>
                </td>
                <td>
                  <span className={`${styles.statusPill} ${styles[`status${measurement.status}`] || ""}`}>
                    {measurementStatusLabel[measurement.status] ?? measurement.status}
                  </span>
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
                  <div className={styles.rowActions}>
                    {canEdit ? (
                      <button type="button" className={styles.iconButton} onClick={() => onEdit(measurement)}>
                        <Pencil size={14} />
                        Editar
                      </button>
                    ) : null}
                    {canApprove ? (
                      <button type="button" className={styles.iconButton} onClick={() => onApprove(measurement)}>
                        <CheckCircle size={14} />
                        Aprovar
                      </button>
                    ) : null}
                    {canReject ? (
                      <button type="button" className={styles.iconButton} onClick={() => onReject(measurement)}>
                        <Clock size={14} />
                        Rejeitar
                      </button>
                    ) : null}
                    {canDelete ? (
                      <button
                        type="button"
                        className={`${styles.iconButton} ${styles.dangerButton}`}
                        onClick={() => onDelete(measurement)}
                      >
                        <Trash2 size={14} />
                        Excluir
                      </button>
                    ) : null}
                  </div>
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
          Carregando requisicoes...
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
        <div className={styles.empty}>Nenhuma requisicao cadastrada para a obra selecionada.</div>
      </div>
    )
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Codigo</th>
            <th>Requisicao</th>
            <th>Status</th>
            <th>Valor estimado</th>
            <th>Necessidade</th>
            <th>Integracao ERP</th>
            <th>Acoes</th>
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
                  <div className={styles.rowActions}>
                    {canEdit ? (
                      <button type="button" className={styles.iconButton} onClick={() => onEdit(procurementRequest)}>
                        <Pencil size={14} />
                        Editar
                      </button>
                    ) : null}
                    {canSubmit ? (
                      <button type="button" className={styles.iconButton} onClick={() => onSubmit(procurementRequest)}>
                        <RefreshCw size={14} />
                        Enviar
                      </button>
                    ) : null}
                    {canApprove ? (
                      <button type="button" className={styles.iconButton} onClick={() => onApprove(procurementRequest)}>
                        <CheckCircle size={14} />
                        Aprovar
                      </button>
                    ) : null}
                    {canReject ? (
                      <button type="button" className={styles.iconButton} onClick={() => onReject(procurementRequest)}>
                        <Clock size={14} />
                        Rejeitar
                      </button>
                    ) : null}
                    {canDelete ? (
                      <button
                        type="button"
                        className={`${styles.iconButton} ${styles.dangerButton}`}
                        onClick={() => onDelete(procurementRequest)}
                      >
                        <Trash2 size={14} />
                        Excluir
                      </button>
                    ) : null}
                  </div>
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
        aria-label={mode === "create" ? "Nova requisicao" : "Editar requisicao"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{mode === "create" ? "Nova requisicao" : "Editar requisicao"}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Codigo</span>
              <input
                type="text"
                value={procurementForm.code}
                onChange={(event) => onChange("code", event.target.value)}
                placeholder="Opcional - gerado automaticamente"
              />
            </label>
            <label className={styles.filterControl}>
              <span>Titulo*</span>
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
              <span>Necessario ate</span>
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
              <span>Descricao</span>
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
              {loading ? "Salvando..." : mode === "create" ? "Criar requisicao" : "Salvar alteracoes"}
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
        aria-label="Rejeitar requisicao"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Rejeitar requisicao {procurementRequest?.code}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <label className={styles.filterControl}>
            <span>Motivo da rejeicao</span>
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
              {loading ? "Rejeitando..." : "Rejeitar requisicao"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function MeasurementModal({ mode, measurementForm, people, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label={mode === "create" ? "Nova medicao" : "Editar medicao"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{mode === "create" ? "Nova medicao" : "Editar medicao"}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <label className={styles.filterControl}>
              <span>Codigo*</span>
              <input
                type="text"
                value={measurementForm.code}
                onChange={(event) => onChange("code", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Sequencia</span>
              <input
                type="number"
                min="1"
                value={measurementForm.sequenceNumber}
                onChange={(event) => onChange("sequenceNumber", event.target.value)}
              />
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
              <span>Competencia</span>
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
              <span>Retencoes</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={measurementForm.retentionsAmount}
                onChange={(event) => onChange("retentionsAmount", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Valor liquido</span>
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
              <span>Numero documento</span>
              <input
                type="text"
                value={measurementForm.documentNumber}
                onChange={(event) => onChange("documentNumber", event.target.value)}
              />
            </label>
            <label className={`${styles.filterControl} ${styles.spanTwoColumns}`}>
              <span>Descricao</span>
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
              {loading ? "Salvando..." : mode === "create" ? "Criar medicao" : "Salvar alteracoes"}
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
        aria-label="Rejeitar medicao"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Rejeitar medicao {measurement?.code}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <label className={styles.filterControl}>
            <span>Motivo da rejeicao</span>
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
              {loading ? "Rejeitando..." : "Rejeitar medicao"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function PersonIdInput({ label, value, onChange, people, required = false }) {
  return (
    <label className={styles.filterControl}>
      <span>{label}</span>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        list="construction-person-summaries"
        required={required}
        placeholder="Digite ou selecione uma pessoa"
      />
      <datalist id="construction-person-summaries">
        {people.map((person) => (
          <option key={person.id} value={person.id}>
            {person.name}
          </option>
        ))}
      </datalist>
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
          <p className={styles.textMuted}>Sincronizacao de medicoes aprovadas com contas a pagar.</p>
          <p className={styles.metricValue}>{linkedMeasurements}</p>
          <p className={styles.metricHint}>medicoes com documento financeiro vinculado</p>
        </article>

        <article className={styles.integrationCard}>
          <h3>Compras ERP</h3>
          <p className={styles.textMuted}>Requisicoes enviadas para a fila de compras.</p>
          <p className={styles.metricValue}>{linkedProcurementRequests}</p>
          <p className={styles.metricHint}>requisicoes vinculadas externamente</p>
        </article>

        <article className={styles.integrationCard}>
          <h3>Contratos ERP</h3>
          <p className={styles.textMuted}>Unidades vendidas com contrato e recebiveis vinculados.</p>
          <p className={styles.metricValue}>{linkedUnitContracts}</p>
          <p className={styles.metricHint}>unidades com contrato sincronizado</p>
        </article>
      </div>
    </div>
  )
}

function ProjectModal({ mode, projectForm, onClose, onChange, onSubmit, loading }) {
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
              <span>Codigo*</span>
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
            <label className={styles.filterControl}>
              <span>Pessoa responsavel (ID)</span>
              <input
                type="text"
                value={projectForm.customerPersonId}
                onChange={(event) => onChange("customerPersonId", event.target.value)}
                placeholder="UUID da pessoa no ERP"
              />
            </label>
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
              <span>Descricao</span>
              <textarea
                className={styles.textarea}
                value={projectForm.description}
                onChange={(event) => onChange("description", event.target.value)}
              />
            </label>
          </div>

          <h4 className={styles.sectionTitle}>Endereco</h4>
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
              <span>Numero</span>
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
              />
            </label>
          </div>

          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Salvando..." : mode === "create" ? "Criar obra" : "Salvar alteracoes"}
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
              <span>Codigo*</span>
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
              {loading ? "Salvando..." : mode === "create" ? "Criar bloco" : "Salvar alteracoes"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function UnitModal({ mode, unitForm, blocks, onClose, onChange, onSubmit, loading }) {
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
            <label className={styles.filterControl}>
              <span>Codigo*</span>
              <input
                type="text"
                value={unitForm.code}
                onChange={(event) => onChange("code", event.target.value)}
                required
              />
            </label>
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
              <span>Area privativa</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={unitForm.privateArea}
                onChange={(event) => onChange("privateArea", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Area total</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={unitForm.totalArea}
                onChange={(event) => onChange("totalArea", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Preco de venda</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={unitForm.salePrice}
                onChange={(event) => onChange("salePrice", event.target.value)}
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
              {loading ? "Salvando..." : mode === "create" ? "Criar unidade" : "Salvar alteracoes"}
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

function SaleUnitModal({ saleForm, unit, people, onClose, onChange, onSubmit, loading }) {
  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <section
        className={styles.modalCard}
        role="dialog"
        aria-modal="true"
        aria-label="Confirmar venda da unidade"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>Confirmar venda da unidade {unit?.code}</h3>
          <button type="button" className={styles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form className={styles.modalBody} onSubmit={onSubmit}>
          <div className={styles.formGrid}>
            <PersonIdInput
              label="Comprador (ID)*"
              value={saleForm.buyerPersonId}
              onChange={(value) => onChange("buyerPersonId", value)}
              people={people}
              required
            />
            <label className={styles.filterControl}>
              <span>Preco da venda</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={saleForm.salePrice}
                onChange={(event) => onChange("salePrice", event.target.value)}
              />
            </label>
            <label className={styles.filterControl}>
              <span>Primeiro vencimento*</span>
              <input
                type="date"
                value={saleForm.firstDueDate}
                onChange={(event) => onChange("firstDueDate", event.target.value)}
                required
              />
            </label>
            <label className={styles.filterControl}>
              <span>Parcelas*</span>
              <input
                type="number"
                min="1"
                max="120"
                value={saleForm.installments}
                onChange={(event) => onChange("installments", event.target.value)}
                required
              />
            </label>
          </div>
          <footer className={styles.modalFooter}>
            <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" className={styles.primaryButton} disabled={loading}>
              {loading ? "Confirmando..." : "Confirmar venda"}
            </button>
          </footer>
        </form>
      </section>
    </div>
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
              {loading ? "Salvando..." : mode === "create" ? "Criar fase" : "Salvar alteracoes"}
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
