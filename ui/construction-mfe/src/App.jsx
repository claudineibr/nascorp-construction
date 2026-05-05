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
  Plus,
  RefreshCw,
  Route,
} from "lucide-react"
import styles from "./App.module.css"
import { resolveConstructionBridge } from "./bridge/constructionBridge.js"
import { listConstructionProjects } from "./services/constructionApi.js"

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
  canceled: "Cancelada",
}

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

const statusOptions = Object.entries(statusLabel).map(([value, label]) => ({ value, label }))
const dateFormatter = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" })

export default function ConstructionApp({ bridge: providedBridge } = {}) {
  const bridge = useMemo(() => providedBridge ?? resolveConstructionBridge(), [providedBridge])
  const [activeTab, setActiveTab] = useState("overview")
  const [filters, setFilters] = useState(defaultFilters)
  const [projects, setProjects] = useState([])
  const [totalProjects, setTotalProjects] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

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
        ? [project.code, project.name].some((value) => String(value ?? "").toLowerCase().includes(searchTerm))
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

  const showCreateWarning = () => {
    bridge?.feedback?.warning?.("A criacao completa sera habilitada na Fase 2.")
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
            <button type="button" className={styles.primaryButton} onClick={showCreateWarning}>
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
              placeholder="Codigo ou nome da obra"
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
              A Fase 1 preparou client centralizado, abas de dominio e estrutura visual para evoluir os CRUDs das
              proximas fases sem acoplamento com internals do ERP.
            </p>
          }
        />
      )}

      {activeTab === "projects" && (
        <DomainCard
          title="Projetos"
          subtitle="Listagem ativa. Criacao e edicao completas entram na Fase 2."
          content={<ProjectList projects={visibleProjects} loading={loading} error={error} onRetry={loadProjects} />}
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

function ProjectList({ projects, loading, error, onRetry }) {
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
            <th>Status</th>
            <th>Inicio</th>
            <th>Previsao</th>
            <th>Centro analitico</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.id}>
              <td>{project.code}</td>
              <td>{project.name}</td>
              <td>
                <span className={`${styles.statusPill} ${styles[`status${project.status}`] || ""}`}>
                  {statusLabel[project.status] ?? project.status}
                </span>
              </td>
              <td>{formatDate(project.startDate)}</td>
              <td>{formatDate(project.expectedEndDate)}</td>
              <td>
                <span className={project.analyticCostCenterId ? styles.badgeSuccess : styles.badgeMuted}>
                  {project.analyticCostCenterId ? "Vinculado" : "Pendente"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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
