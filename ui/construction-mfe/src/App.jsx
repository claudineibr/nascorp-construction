import { useCallback, useEffect, useMemo, useState } from "react"
import { Building2, CheckCircle, Clock, Home, Plus, RefreshCw } from "lucide-react"
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
  completed: "Concluída",
  canceled: "Cancelada",
}

const statusOptions = Object.entries(statusLabel).map(([value, label]) => ({ value, label }))
const dateFormatter = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" })

export default function ConstructionApp({ bridge: providedBridge } = {}) {
  const bridge = useMemo(() => providedBridge ?? resolveConstructionBridge(), [providedBridge])
  const [filters, setFilters] = useState(defaultFilters)
  const [projects, setProjects] = useState([])
  const [totalProjects, setTotalProjects] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadProjects = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await listConstructionProjects({ bridge })
      setProjects(result.items)
      setTotalProjects(result.total)
    } catch (requestError) {
      const message = requestError?.message ?? "Não foi possível carregar as obras."
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [bridge])

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
        hint: "sem vínculo analítico",
        icon: Clock,
        tone: "warning",
      },
      {
        label: "Unidades",
        value: "0",
        hint: "próxima etapa",
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
    bridge?.feedback?.warning?.("O formulário de nova obra ainda não está disponível.")
  }

  return (
    <main className={styles.page} data-theme={bridge?.theme ?? "light"}>
      <section className={styles.pageHeader}>
        <div className={styles.header}>
          <div className={styles.left}>
            <nav className={styles.breadcrumb} aria-label="Navegação">
              <span className={styles.breadcrumbLink}>Início</span>
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

      <section className={styles.filtersCard}>
        <div className={styles.filtersGrid}>
          <label className={styles.filterControl}>
            <span>Buscar</span>
            <input
              type="text"
              value={filters.search}
              onChange={(event) => handleFilterChange("search", event.target.value)}
              placeholder="Código ou nome da obra"
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
            <span>Início inicial</span>
            <input
              type="date"
              value={filters.startDate}
              onChange={(event) => handleFilterChange("startDate", event.target.value)}
            />
          </label>
          <label className={styles.filterControl}>
            <span>Início final</span>
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

      <div className={`${styles.card} ${styles.tableCard}`}>
        <div className={styles.tableHeaderRow}>
          <h2>Projetos</h2>
          <span className={styles.badgeMuted}>{visibleProjects.length} registros</span>
        </div>
        <ProjectList projects={visibleProjects} loading={loading} error={error} onRetry={loadProjects} />
        <div className={styles.paginationSlot}>
          <span className={styles.paginationSummary}>
            Mostrando {visibleProjects.length} de {totalProjects} obras
          </span>
        </div>
      </div>
    </main>
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
            <th>Código</th>
            <th>Obra</th>
            <th>Status</th>
            <th>Início</th>
            <th>Previsão</th>
            <th>Centro analítico</th>
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