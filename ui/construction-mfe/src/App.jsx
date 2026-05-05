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
  Trash2,
} from "lucide-react"
import styles from "./App.module.css"
import { resolveConstructionBridge } from "./bridge/constructionBridge.js"
import {
  createConstructionBlock,
  createConstructionProject,
  createConstructionSchedulePhase,
  deleteConstructionBlock,
  deleteConstructionProject,
  deleteConstructionSchedulePhase,
  listConstructionBlocks,
  listConstructionProjects,
  listConstructionSchedulePhases,
  updateConstructionBlock,
  updateConstructionProject,
  updateConstructionSchedulePhase,
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
      const message = requestError?.message ?? "Nao foi possivel carregar as obras."
      setError(message)
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
        value: "0",
        hint: "proximas fases",
        icon: Home,
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

  const handleFilterChange = (field, value) => {
    setFilters((currentFilters) => ({ ...currentFilters, [field]: value }))
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
        bridge?.feedback?.success?.("Obra criada com sucesso.")
        setActiveProjectId(createdProject.id)
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
          subtitle="Fundacao visual com CRUD de projetos, blocos e cronograma."
          content={
            <p className={styles.textMuted}>
              As etapas 2 e 3 habilitaram o CRUD completo de projetos, blocos e fases do cronograma com foco em
              rastreabilidade operacional por obra.
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

      {activeTab === "units" && <PhasePlaceholder title="Unidades" phase="Fase 4" />}
      {activeTab === "measurements" && <PhasePlaceholder title="Medicoes" phase="Fase 5" />}
      {activeTab === "procurement" && <PhasePlaceholder title="Requisicoes" phase="Fase 6" />}
      {activeTab === "integrations" && <PhasePlaceholder title="Integracoes" phase="Fase 7" />}

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
