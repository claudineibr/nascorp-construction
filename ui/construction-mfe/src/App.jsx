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
  createConstructionProject,
  deleteConstructionProject,
  listConstructionProjects,
  updateConstructionProject,
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

export default function ConstructionApp({ bridge: providedBridge } = {}) {
  const bridge = useMemo(() => providedBridge ?? resolveConstructionBridge(), [providedBridge])
  const [activeTab, setActiveTab] = useState("overview")
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
        await createConstructionProject({ bridge, projectData })
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
          subtitle="Base pronta para CRUD completo por dominio."
          content={
            <p className={styles.textMuted}>
              A Fase 2 habilitou o CRUD de projetos com novos campos contratuais para suportar integracoes futuras com
              blocos, unidades e ERP.
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

      {activeTab === "blocks" && <PhasePlaceholder title="Blocos e Torres" phase="Fase 3" />}
      {activeTab === "units" && <PhasePlaceholder title="Unidades" phase="Fase 4" />}
      {activeTab === "schedule" && <PhasePlaceholder title="Cronograma" phase="Fase 3" />}
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
