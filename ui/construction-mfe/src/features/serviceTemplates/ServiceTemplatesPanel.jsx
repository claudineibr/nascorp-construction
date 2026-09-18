import { useCallback, useEffect, useState } from "react"
import { History, Pencil, Plus, RefreshCw, ToggleLeft, ToggleRight, Trash2, Upload } from "lucide-react"

import appStyles from "../../App.module.css"
import styles from "./ServiceTemplates.module.css"
import { ServiceTemplateEditor } from "./ServiceTemplateEditor"
import { ServiceTemplateHistoryModal } from "./ServiceTemplateHistoryModal"
import { ServiceTemplateImportModal } from "./ServiceTemplateImportModal"
import {
  createConstructionServiceTemplate,
  deleteConstructionServiceTemplate,
  importConstructionServiceTemplates,
  listConstructionServiceTemplates,
  replaceConstructionServiceTemplate,
  updateConstructionServiceTemplate,
} from "../../services/constructionApi"

const SEARCH_DEBOUNCE_MS = 400

export function ServiceTemplatesPanel({ bridge }) {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [reloadKey, setReloadKey] = useState(0)
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importResults, setImportResults] = useState([])
  const [pendingDeletion, setPendingDeletion] = useState(null)
  const [historyTemplate, setHistoryTemplate] = useState(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [search])

  const loadTemplates = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const response = await listConstructionServiceTemplates({
        bridge,
        search: debouncedSearch || null,
        onlyActive: statusFilter === "active",
        onlyDeleted: statusFilter === "deleted",
      })
      setTemplates(response.items)
    } catch (loadError) {
      setError(loadError?.message ?? "Não foi possível carregar o catálogo de serviços.")
    } finally {
      setLoading(false)
    }
  }, [bridge, debouncedSearch, statusFilter])

  useEffect(() => {
    loadTemplates()
  }, [loadTemplates, reloadKey])

  const openCreateEditor = () => {
    setEditingTemplate(null)
    setEditorOpen(true)
  }

  const openEditEditor = (template) => {
    setEditingTemplate(template)
    setEditorOpen(true)
  }

  const closeEditor = () => {
    setEditorOpen(false)
    setEditingTemplate(null)
  }

  const handleSubmit = async (templateData) => {
    setSubmitting(true)
    try {
      if (editingTemplate) {
        await replaceConstructionServiceTemplate({
          bridge,
          serviceTemplateId: editingTemplate.id,
          templateData,
        })
        bridge?.feedback?.success?.("Serviço atualizado.")
      } else {
        await createConstructionServiceTemplate({ bridge, templateData })
        bridge?.feedback?.success?.("Serviço cadastrado.")
      }

      closeEditor()
      setReloadKey((value) => value + 1)
    } catch (submitError) {
      bridge?.feedback?.error?.(submitError?.message ?? "Não foi possível salvar o serviço.")
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleActive = async (template) => {
    try {
      await updateConstructionServiceTemplate({
        bridge,
        serviceTemplateId: template.id,
        templateData: { name: template.name, productId: template.productId, isActive: !template.isActive },
      })
      bridge?.feedback?.success?.(template.isActive ? "Serviço desativado." : "Serviço reativado.")
      setReloadKey((value) => value + 1)
    } catch (toggleError) {
      bridge?.feedback?.error?.(toggleError?.message ?? "Não foi possível alterar o serviço.")
    }
  }

  const handleDelete = async () => {
    if (!pendingDeletion) {
      return
    }

    setSubmitting(true)
    try {
      await deleteConstructionServiceTemplate({ bridge, serviceTemplateId: pendingDeletion.id })
      bridge?.feedback?.success?.("Serviço excluído do catálogo.")
      setPendingDeletion(null)
      setReloadKey((value) => value + 1)
    } catch (deleteError) {
      bridge?.feedback?.error?.(deleteError?.message ?? "Não foi possível excluir o serviço.")
    } finally {
      setSubmitting(false)
    }
  }

  const handleImport = async (files) => {
    setImporting(true)
    try {
      const response = await importConstructionServiceTemplates({ bridge, files })
      setImportResults(response.results)
      bridge?.feedback?.success?.(
        `${response.created} criado(s), ${response.updated} atualizado(s), ` +
          `${response.skipped} já existia(m), ${response.failed} com falha.`,
      )
      setReloadKey((value) => value + 1)
    } catch (importError) {
      bridge?.feedback?.error?.(importError?.message ?? "Não foi possível importar as planilhas.")
    } finally {
      setImporting(false)
    }
  }

  const closeImport = () => {
    setImportOpen(false)
    setImportResults([])
  }

  return (
    <section className={styles.panel}>
      <div className={appStyles.heroActions}>
        <button type="button" className={appStyles.primaryButton} onClick={openCreateEditor}>
          <Plus size={16} />
          Novo serviço
        </button>
        <button type="button" className={appStyles.secondaryButton} onClick={() => setImportOpen(true)}>
          <Upload size={16} />
          Importar planilha (FVS)
        </button>
        <button
          type="button"
          className={appStyles.secondaryButton}
          onClick={() => setReloadKey((value) => value + 1)}
          disabled={loading}
        >
          <RefreshCw size={15} className={loading ? appStyles.spinIcon : undefined} />
          Recarregar
        </button>
      </div>

      <div className={styles.filters}>
        <div className={styles.field}>
          <label htmlFor="service-template-search">Buscar</label>
          <input
            id="service-template-search"
            className={styles.input}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Nome do serviço"
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="service-template-status">Situação</label>
          <select
            id="service-template-status"
            className={styles.select}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">Todos</option>
            <option value="active">Somente ativos</option>
            <option value="deleted">Excluídos</option>
          </select>
        </div>
      </div>

      <div className={styles.tableWrapper}>
        {loading ? (
          <p className={styles.loading}>Carregando catálogo...</p>
        ) : error ? (
          <p className={styles.empty}>{error}</p>
        ) : templates.length === 0 ? (
          <p className={styles.empty}>
            {statusFilter === "deleted"
              ? "Nenhum serviço foi excluído do catálogo."
              : "Nenhum serviço cadastrado. Crie um serviço ou importe as fichas de verificação."}
          </p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.colName}>Serviço</th>
                <th className={styles.colCount}>Seções</th>
                <th className={styles.colCount}>Itens</th>
                <th>Origem</th>
                <th className={styles.colStatus}>Situação</th>
                <th className={styles.colActions} aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {templates.map((template) => (
                <tr key={template.id}>
                  <td className={styles.colName}>{template.name}</td>
                  <td className={styles.colCount}>{template.sections.length}</td>
                  <td className={styles.colCount}>{template.items.length}</td>
                  <td className={styles.colSource} title={template.sourceFileName || "Manual"}>
                    {template.sourceFileName || "Manual"}
                  </td>
                  <td className={styles.colStatus}>
                    <span
                      className={`${styles.badge} ${
                        template.deletedAt
                          ? styles.badgeDeleted
                          : template.isActive
                            ? styles.badgeActive
                            : styles.badgeInactive
                      }`}
                    >
                      {template.deletedAt ? "Excluído" : template.isActive ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className={styles.colActions}>
                    <div className={styles.rowActions}>
                      <button
                        type="button"
                        className={styles.iconButton}
                        onClick={() => setHistoryTemplate(template)}
                        aria-label={`Histórico de ${template.name}`}
                        title="Histórico"
                      >
                        <History size={15} />
                      </button>
                      {template.deletedAt ? null : (
                        <>
                          <button
                            type="button"
                            className={styles.iconButton}
                            onClick={() => openEditEditor(template)}
                            aria-label={`Editar ${template.name}`}
                            title="Editar"
                          >
                            <Pencil size={15} />
                          </button>
                          <button
                            type="button"
                            className={styles.textButton}
                            onClick={() => handleToggleActive(template)}
                          >
                            {template.isActive ? <ToggleLeft size={15} /> : <ToggleRight size={15} />}
                            {template.isActive ? "Desativar" : "Ativar"}
                          </button>
                          <button
                            type="button"
                            className={`${styles.iconButton} ${styles.dangerIconButton}`}
                            onClick={() => setPendingDeletion(template)}
                            aria-label={`Excluir ${template.name}`}
                            title="Excluir"
                          >
                            <Trash2 size={15} />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editorOpen ? (
        <ServiceTemplateEditor
          template={editingTemplate}
          submitting={submitting}
          onCancel={closeEditor}
          onSubmit={handleSubmit}
        />
      ) : null}

      {importOpen ? (
        <ServiceTemplateImportModal
          bridge={bridge}
          submitting={importing}
          results={importResults}
          onClose={closeImport}
          onImport={handleImport}
        />
      ) : null}

      {historyTemplate ? (
        <ServiceTemplateHistoryModal
          bridge={bridge}
          template={historyTemplate}
          onClose={() => setHistoryTemplate(null)}
        />
      ) : null}

      {pendingDeletion ? (
        <div className={appStyles.modalOverlay} role="dialog" aria-modal="true">
          <div className={appStyles.modalCard}>
            <header className={appStyles.modalHeader}>
              <h3>Excluir serviço</h3>
              <button
                type="button"
                className={appStyles.closeButton}
                onClick={() => setPendingDeletion(null)}
              >
                Fechar
              </button>
            </header>
            <div className={appStyles.modalBody}>
              <p>
                Excluir <strong>{pendingDeletion.name}</strong> do catálogo? O serviço sai das telas mas
                continua registrado: o histórico guarda quem o excluiu e como a ficha estava. Serviços já
                usados em medição não podem ser excluídos — nesse caso, desative.
              </p>
              <div className={appStyles.modalFooter}>
                <button
                  type="button"
                  className={appStyles.secondaryButton}
                  onClick={() => setPendingDeletion(null)}
                  disabled={submitting}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className={appStyles.dangerButton}
                  onClick={handleDelete}
                  disabled={submitting}
                >
                  {submitting ? "Excluindo..." : "Excluir"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}
