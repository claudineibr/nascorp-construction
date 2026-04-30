import { useCallback, useEffect, useMemo, useState } from "react"
import { Building2, CalendarDays, Home, Plus, RefreshCw } from "lucide-react"
import styles from "./App.module.css"
import { resolveConstructionBridge } from "./bridge/constructionBridge.js"
import { listConstructionProjects } from "./services/constructionApi.js"

const tabs = [
  { id: "projects", label: "Projetos", icon: Building2 },
  { id: "units", label: "Unidades", icon: Home },
  { id: "schedule", label: "Cronograma", icon: CalendarDays },
]

const statusLabel = {
  draft: "Rascunho",
  active: "Ativa",
  paused: "Pausada",
  completed: "Concluída",
  canceled: "Cancelada",
}

export default function ConstructionApp({ bridge: providedBridge } = {}) {
  const bridge = useMemo(() => providedBridge ?? resolveConstructionBridge(), [providedBridge])
  const [activeTab, setActiveTab] = useState("projects")
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

  const summaryItems = useMemo(
    () => [
      { label: "Empreendimentos", value: totalProjects, icon: Building2 },
      { label: "Unidades", value: "0", icon: Home },
      { label: "Fases", value: "0", icon: CalendarDays },
    ],
    [totalProjects],
  )

  const showCreateWarning = () => {
    bridge?.feedback?.warning?.("Cadastro de obras", "O formulário de nova obra ainda não está disponível.")
  }

  return (
    <main className={styles.page} data-theme={bridge?.theme ?? "light"}>
      <header className={styles.toolbar}>
        <div>
          <span className={styles.eyebrow}>{bridge?.companyContext?.companyName || "NASCORP Construction"}</span>
          <h1>Obras</h1>
        </div>
        <div className={styles.toolbarActions}>
          <button type="button" className={styles.secondaryButton} onClick={loadProjects} disabled={loading}>
            <RefreshCw size={16} />
            Atualizar
          </button>
          <button type="button" className={styles.primaryButton} onClick={showCreateWarning}>
            <Plus size={16} />
            Nova obra
          </button>
        </div>
      </header>

      <section className={styles.summaryGrid} aria-label="Resumo de obras">
        {summaryItems.map((item) => {
          const Icon = item.icon
          return (
            <article className={styles.summaryCard} key={item.label}>
              <Icon size={18} />
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </article>
          )
        })}
      </section>

      <section className={styles.workspace}>
        <div className={styles.tabs} role="tablist" aria-label="Áreas de obras">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const selected = activeTab === tab.id
            return (
              <button
                type="button"
                role="tab"
                aria-selected={selected}
                className={selected ? styles.tabActive : styles.tab}
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            )
          })}
        </div>

        {activeTab === "projects" ? (
          <ProjectList projects={projects} loading={loading} error={error} onRetry={loadProjects} />
        ) : (
          <section className={styles.emptyPanel}>
            <span>{tabs.find((tab) => tab.id === activeTab)?.label}</span>
          </section>
        )}
      </section>
    </main>
  )
}

function ProjectList({ projects, loading, error, onRetry }) {
  if (loading) {
    return (
      <section className={styles.statePanel} aria-busy="true">
        <RefreshCw className={styles.spinIcon} size={18} />
        <span>Carregando obras...</span>
      </section>
    )
  }

  if (error) {
    return (
      <section className={styles.statePanel}>
        <span>{error}</span>
        <button type="button" className={styles.secondaryButton} onClick={onRetry}>
          <RefreshCw size={16} />
          Tentar novamente
        </button>
      </section>
    )
  }

  if (!projects.length) {
    return (
      <section className={styles.emptyPanel}>
        <span>Nenhuma obra cadastrada</span>
      </section>
    )
  }

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Código</th>
            <th>Obra</th>
            <th>Status</th>
            <th>Início</th>
            <th>Centro analítico</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.id}>
              <td>{project.code}</td>
              <td>{project.name}</td>
              <td>{statusLabel[project.status] ?? project.status}</td>
              <td>{formatDate(project.startDate)}</td>
              <td>{project.analyticCostCenterId ? "Vinculado" : "Pendente"}</td>
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

  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(value))
}
