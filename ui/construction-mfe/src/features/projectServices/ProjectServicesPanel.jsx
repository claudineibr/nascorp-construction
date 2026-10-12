import { useCallback, useEffect, useMemo, useState } from "react"
import { RefreshCw, Upload } from "lucide-react"

import appStyles from "../../App.module.css"
import catalogStyles from "../serviceTemplates/ServiceTemplates.module.css"
import styles from "./ProjectServices.module.css"
import { ServiceTemplateImportModal } from "../serviceTemplates/ServiceTemplateImportModal"
import {
  importConstructionProjectServices,
  listConstructionProjectServices,
  listConstructionServiceTemplates,
  replaceConstructionProjectServices,
} from "../../services/constructionApi"

const can = (bridge, method, feature) => (typeof bridge?.[method] === "function" ? bridge[method](feature) : true)

const normalize = (value) =>
  value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()

const byName = (left, right) => left.name.localeCompare(right.name, "pt-BR")

async function fetchProjectServices({ bridge, projectId }) {
  const [projectServices, catalogServices] = await Promise.all([
    listConstructionProjectServices({ bridge, projectId }),
    listConstructionServiceTemplates({ bridge }),
  ])
  const catalogIds = new Set(catalogServices.items.map((template) => template.id))
  const linkedOutsideCatalog = projectServices.items.filter((template) => !catalogIds.has(template.id))
  return {
    services: [...catalogServices.items, ...linkedOutsideCatalog].sort(byName),
    linkedIds: projectServices.items.map((template) => template.id),
  }
}

export function ProjectServicesPanel({ bridge, projectId }) {
  const [services, setServices] = useState([])
  const [savedIds, setSavedIds] = useState(() => new Set())
  const [draftIds, setDraftIds] = useState(() => new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [filter, setFilter] = useState("")
  const [onlySelected, setOnlySelected] = useState(false)
  const [saving, setSaving] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importResults, setImportResults] = useState([])
  const [confirmClear, setConfirmClear] = useState(false)
  const canEdit = can(bridge, "canUpdate", "construction_projects")
  const canImport = canEdit && can(bridge, "canCreate", "construction_measurements")
  const showOnlySelected = onlySelected || !canEdit

  const load = useCallback(async () => {
    if (!projectId) return
    setLoading(true)
    setError("")
    try {
      const { services: loaded, linkedIds } = await fetchProjectServices({ bridge, projectId })
      setServices(loaded)
      setSavedIds(new Set(linkedIds))
      setDraftIds(new Set(linkedIds))
    } catch (loadError) {
      setError(loadError?.message ?? "Não foi possível carregar os serviços da obra.")
    } finally {
      setLoading(false)
    }
  }, [bridge, projectId])

  useEffect(() => {
    load()
  }, [load])

  const activeCount = useMemo(() => services.filter((template) => template.isActive).length, [services])

  const visibleServices = useMemo(() => {
    const term = normalize(filter.trim())
    return services.filter(
      (template) =>
        (!showOnlySelected || draftIds.has(template.id)) && (!term || normalize(template.name).includes(term)),
    )
  }, [services, filter, showOnlySelected, draftIds])

  const addedCount = useMemo(() => [...draftIds].filter((id) => !savedIds.has(id)).length, [draftIds, savedIds])
  const removedCount = useMemo(() => [...savedIds].filter((id) => !draftIds.has(id)).length, [draftIds, savedIds])
  const dirty = addedCount > 0 || removedCount > 0

  const toggle = (templateId) => {
    setDraftIds((current) => {
      const next = new Set(current)
      if (next.has(templateId)) {
        next.delete(templateId)
      } else {
        next.add(templateId)
      }
      return next
    })
  }

  const markVisible = (checked) => {
    setDraftIds((current) => {
      const next = new Set(current)
      for (const template of visibleServices) {
        if (checked && (template.isActive || savedIds.has(template.id))) {
          next.add(template.id)
        } else if (!checked) {
          next.delete(template.id)
        }
      }
      return next
    })
  }

  const save = async ({ confirmed = false } = {}) => {
    if (!confirmed && draftIds.size === 0 && savedIds.size > 0) {
      setConfirmClear(true)
      return
    }
    setConfirmClear(false)
    setSaving(true)
    try {
      const response = await replaceConstructionProjectServices({
        bridge,
        projectId,
        serviceTemplateIds: [...draftIds],
      })
      const linkedIds = response.items.map((template) => template.id)
      setSavedIds(new Set(linkedIds))
      setDraftIds(new Set(linkedIds))
      bridge?.feedback?.success?.(
        linkedIds.length
          ? `Seleção salva: as medições desta obra passam a oferecer ${linkedIds.length} serviço(s).`
          : "Seleção limpa: as medições desta obra voltam a mostrar todo o catálogo.",
      )
    } catch (saveError) {
      bridge?.feedback?.error?.(saveError?.message ?? "Não foi possível salvar os serviços da obra.")
    } finally {
      setSaving(false)
    }
  }

  const handleImport = async (files) => {
    setImporting(true)
    try {
      const response = await importConstructionProjectServices({ bridge, projectId, files })
      setImportResults(response.results)
      const importedIds = response.results
        .filter((result) => result.linked && result.serviceTemplateId)
        .map((result) => result.serviceTemplateId)
      const { services: loaded, linkedIds } = await fetchProjectServices({ bridge, projectId })
      setServices(loaded)
      setSavedIds(new Set(linkedIds))
      setDraftIds((current) => new Set([...current, ...importedIds]))
      bridge?.feedback?.success?.(
        `${importedIds.length} serviço(s) vinculado(s) à obra; ${response.created} novo(s) no catálogo, ` +
          `${response.failed} com falha.`,
      )
    } catch (importError) {
      bridge?.feedback?.error?.(importError?.message ?? "Não foi possível importar as fichas.")
    } finally {
      setImporting(false)
    }
  }

  const busy = saving || importing

  return (
    <section className={catalogStyles.panel}>
      <p className={styles.notice}>
        {savedIds.size
          ? `As medições desta obra só oferecem os ${savedIds.size} serviço(s) marcados.`
          : `Nenhum serviço marcado: as medições desta obra mostram todo o catálogo (${activeCount} serviço(s)).`}
      </p>

      {loading ? (
        <p className={catalogStyles.loading}>Carregando serviços da obra...</p>
      ) : error ? (
        <div className={styles.stateBox}>
          <p className={catalogStyles.empty}>{error}</p>
          <button type="button" className={appStyles.secondaryButton} onClick={load}>
            <RefreshCw size={15} aria-hidden="true" />
            Tentar novamente
          </button>
        </div>
      ) : (
        <div className={styles.selector}>
          <div className={styles.toolbar}>
            <div className={styles.filterField}>
              <label htmlFor="project-service-filter">Filtrar serviços</label>
              <input
                id="project-service-filter"
                className={catalogStyles.input}
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="Digite parte do nome"
                autoComplete="off"
              />
            </div>
            <span className={styles.counter}>
              {draftIds.size} de {services.length} marcado(s)
            </span>
            <div className={styles.toolbarActions}>
              {canImport ? (
                <button
                  type="button"
                  className={appStyles.secondaryButton}
                  onClick={() => setImportOpen(true)}
                  disabled={busy}
                >
                  <Upload size={16} aria-hidden="true" />
                  Enviar FVS (criar serviço)
                </button>
              ) : null}
              <button
                type="button"
                className={catalogStyles.iconButton}
                onClick={load}
                disabled={busy}
                title="Recarregar"
                aria-label="Recarregar"
              >
                <RefreshCw size={15} aria-hidden="true" />
              </button>
            </div>
          </div>

          {canEdit ? (
            <div className={styles.bulkActions}>
              <button
                type="button"
                className={catalogStyles.textButton}
                onClick={() => markVisible(true)}
                disabled={busy || !visibleServices.length}
              >
                Marcar visíveis
              </button>
              <button
                type="button"
                className={catalogStyles.textButton}
                onClick={() => markVisible(false)}
                disabled={busy || !visibleServices.length}
              >
                Desmarcar visíveis
              </button>
              <label className={styles.onlySelected}>
                <input
                  type="checkbox"
                  checked={onlySelected}
                  onChange={(event) => setOnlySelected(event.target.checked)}
                />
                Só os marcados
              </label>
            </div>
          ) : null}

          <div className={styles.optionList} role="group" aria-label="Serviços do catálogo">
            {services.length === 0 ? (
              <p className={catalogStyles.empty}>Catálogo vazio: envie uma FVS para criar o primeiro serviço.</p>
            ) : visibleServices.length === 0 ? (
              <p className={catalogStyles.empty}>
                {showOnlySelected && !filter.trim()
                  ? "Nenhum serviço marcado para esta obra."
                  : "Nenhum serviço com esse nome."}
              </p>
            ) : (
              visibleServices.map((template) => {
                const checked = draftIds.has(template.id)
                const blocked = !template.isActive && !savedIds.has(template.id)
                return (
                  <label
                    key={template.id}
                    className={`${styles.option} ${checked ? styles.optionChecked : ""}`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(template.id)}
                      disabled={!canEdit || busy || blocked}
                    />
                    <span className={styles.optionName}>{template.name}</span>
                    {template.isActive ? null : (
                      <span className={`${catalogStyles.badge} ${catalogStyles.badgeInactive}`}>
                        Inativo no catálogo
                      </span>
                    )}
                    <span className={styles.optionCount}>{template.items.length} item(ns) de inspeção</span>
                  </label>
                )
              })
            )}
          </div>

          {canEdit ? (
            <div className={styles.footer}>
              <span className={styles.pending}>
                {dirty ? `Alterações não salvas: +${addedCount}, −${removedCount}` : "Nenhuma alteração pendente"}
              </span>
              <div className={styles.footerActions}>
                <button
                  type="button"
                  className={appStyles.secondaryButton}
                  onClick={() => setDraftIds(new Set(savedIds))}
                  disabled={!dirty || busy}
                >
                  Descartar
                </button>
                <button
                  type="button"
                  className={appStyles.primaryButton}
                  onClick={() => save()}
                  disabled={!dirty || busy}
                >
                  {saving ? "Salvando..." : "Salvar seleção"}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {importOpen ? (
        <ServiceTemplateImportModal
          bridge={bridge}
          title="Enviar FVS para criar serviço"
          submitting={importing}
          results={importResults}
          onClose={() => {
            setImportOpen(false)
            setImportResults([])
          }}
          onImport={handleImport}
        />
      ) : null}

      {confirmClear ? (
        <div className={appStyles.modalOverlay} role="dialog" aria-modal="true">
          <div className={appStyles.modalCard}>
            <header className={appStyles.modalHeader}>
              <h3>Desmarcar todos os serviços</h3>
              <button type="button" className={appStyles.closeButton} onClick={() => setConfirmClear(false)}>
                Fechar
              </button>
            </header>
            <div className={appStyles.modalBody}>
              <p>
                Sem nenhum serviço marcado, as medições desta obra voltam a mostrar todo o catálogo. O que já foi
                medido não muda.
              </p>
              <div className={appStyles.modalFooter}>
                <button
                  type="button"
                  className={appStyles.secondaryButton}
                  onClick={() => setConfirmClear(false)}
                  disabled={saving}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className={appStyles.dangerButton}
                  onClick={() => save({ confirmed: true })}
                  disabled={saving}
                >
                  {saving ? "Salvando..." : "Desmarcar todos"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}
