import { getBusinessTimezone } from "../../utils/brazilDate.js"
import { useCallback, useEffect, useId, useState } from "react"
import { Plus, RefreshCw, Printer, Eye, X } from "lucide-react"
import { subcontractRequest, fetchConstructionAddressByZip } from "../../services/constructionApi"
import { Pagination as StandalonePagination } from "../../components/Pagination"
import { maskPhone } from "../../utils/phoneInput"
import { assistancePrintDocument } from "./assistancePrint"
import { ReferencePicker } from "./ReferencePicker"
import { Dialog } from "../subcontracts/DirectBillsSection"
import appStyles from "../../App.module.css"
import styles from "./AssistancePanel.module.css"

const feature = "construction_units"
const statusLabels = { open: "Aberta", completed: "Concluída" }
const stageLabels = {
  analysis: "Análise",
  planning: "Planejamento",
  execution: "Execução",
  inspection: "Inspeção",
  completion: "Pronta para concluir",
  completed: "Concluída",
}
const eventLabels = {
  imported: "Importada",
  created: "Criada",
  updated: "Alterada",
  completed: "Concluída",
  reopened: "Reaberta",
  deleted: "Excluída",
}
const day = (value) => (value ? new Date(value).toLocaleString("pt-BR", { timeZone: getBusinessTimezone() }) : "Não informado")
const localDate = (value) =>
  value
    ? new Date(new Date(value).getTime() - new Date(value).getTimezoneOffset() * 60000).toISOString().slice(0, 16)
    : ""
const instant = (value) => (value ? new Date(value).toISOString() : null)
const empty = (projectId, unitId, user) => ({
  project_id: projectId || "",
  unit_id: unitId || "",
  customer_person_id: "",
  attendant_person_id: user?.personId || "",
  attendant_name: user?.name || user?.email || "Usuário logado",
  analyst_person_id: null,
  opened_at: new Date().toISOString(),
  notes: "",
  contacts: [],
  complaints: [],
  services: [],
  history: [],
})
const pick = (row, keys) => Object.fromEntries(keys.map((key) => [key, row[key] ?? null]))
const payload = (row) => ({
  ...pick(row, [
    "project_id",
    "unit_id",
    "customer_person_id",
    "analyst_person_id",
    "opened_at",
    "notes",
  ]),
  contacts: row.contacts.map((item) => pick(item, ["id", "channel", "detail"])),
  complaints: row.complaints.map((item) =>
    pick(item, ["id", "description", "provenance", "analyzed_by_person_id", "analyzed_at"])
  ),
  services: row.services.map((item) =>
    pick(item, [
      "id",
      "description",
      "complaint_id",
      "due_date",
      "executed_by_person_id",
      "executed_at",
      "inspected_by_person_id",
      "inspected_at",
    ])
  ),
})

export function AssistancePanel({ bridge, projectId = null, unitId = null }) {
  const formId = useId()
  const can = (method) => bridge?.[method]?.(feature) === true
  const [filters, setFilters] = useState({
    project_id: projectId || "",
    unit_id: unitId || "",
    status: "",
    overdue: "",
    customer_person_id: "",
    responsible_person_id: "",
    opened_from: "",
    opened_to: "",
  })
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [data, setData] = useState({ items: [], total: 0, total_pages: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [draft, setDraft] = useState(null)
  const [creating, setCreating] = useState(false)
  const [savedPayload, setSavedPayload] = useState("")
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState("general")
  const [reason, setReason] = useState("")
  const [reopening, setReopening] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [printing, setPrinting] = useState(null)
  const RowActionsMenu = bridge.components?.RowActionsMenu
  const Pagination = bridge.components?.Pagination || StandalonePagination
  const ConfirmDialog = bridge.components?.ConfirmDialog
  const PageHeader = bridge.components?.PageHeader
  const actionClasses = bridge.actionClasses || {
    primary: appStyles.primaryButton,
    secondary: appStyles.secondaryButton,
  }
  const editorActionClasses = {
    primary: styles.modalPrimaryButton,
    secondary: styles.modalSecondaryButton,
  }
  const closeEditor = () => {
    if (busy) return
    setDraft(null)
    setCreating(false)
    setReopening(false)
    setReason("")
  }
  const readable = can("canRead")
  const editable = draft && (draft.id ? can("canUpdate") && draft.status === "open" : can("canCreate"))
  const dirty = draft?.id && JSON.stringify(payload(draft)) !== savedPayload
  const load = useCallback(async () => {
    if (!bridge.canRead?.(feature)) return
    setLoading(true)
    setError("")
    try {
      const query = new URLSearchParams({ page, page_size: pageSize })
      for (const [key, value] of Object.entries(filters)) {
        if (value !== "")
          query.set(
            key,
            key === "opened_from"
              ? instant(`${value}T00:00`)
              : key === "opened_to"
              ? instant(`${value}T23:59:59.999`)
              : value
          )
      }
      setData(
        await subcontractRequest({
          bridge,
          path: `/assistance-requests?${query}`,
        })
      )
    } catch (err) {
      setError(err.message)
      bridge.feedback?.error?.(err.message)
    } finally {
      setLoading(false)
    }
  }, [bridge, filters, page, pageSize])
  useEffect(() => {
    load()
  }, [load])
  const filter = (key, value) => {
    setPage(1)
    setFilters((old) => ({
      ...old,
      [key]: value || "",
      ...(key === "project_id" ? { unit_id: "" } : {}),
    }))
  }
  const change = (key, value) => setDraft((old) => ({ ...old, [key]: value }))
  const changeItem = (group, index, key, value) =>
    change(
      group,
      draft[group].map((item, position) => (position === index ? { ...item, [key]: value } : item))
    )
  const remove = (group, index) =>
    setDraft((old) => {
      const removedId = old[group][index].id
      return {
        ...old,
        [group]: old[group].filter((_, position) => position !== index),
        ...(group === "complaints" && removedId
          ? {
              services: old.services.map((item) =>
                item.complaint_id === removedId ? { ...item, complaint_id: null } : item
              ),
            }
          : {}),
      }
    })
  const open = async (row) => {
    try {
      const result = await subcontractRequest({
        bridge,
        path: `/assistance-requests/${row.id}`,
      })
      setCreating(false)
      setDraft(result)
      setSavedPayload(JSON.stringify(payload(result)))
      setTab("general")
      setReason("")
    } catch (err) {
      bridge.feedback?.error?.(err.message)
    }
  }
  const print = async (row) => {
    setBusy(true)
    try {
      const context = await subcontractRequest({ bridge, path: `/assistance-requests/${row.id}/print-context` })
      if (!context.city && context.zip_code) {
        const address = await fetchConstructionAddressByZip({ bridge, zipCode: context.zip_code })
        context.city = address.city
      }
      if (!context.city) throw new Error("Informe um CEP válido no endereço da obra para imprimir a cidade na SAT.")
      setPrinting({ id: row.id, html: assistancePrintDocument(context, bridge.companyContext?.companyName) })
    } catch (err) {
      setBusy(false)
      bridge.feedback?.error?.(err.message)
    }
  }
  const printLoaded = async (frame) => {
    let timeout
    try {
      const ready = Promise.all([
        frame.contentDocument.fonts?.ready,
        ...Array.from(frame.contentDocument.images, (image) => image.decode()),
      ])
      await Promise.race([
        ready,
        new Promise((_, reject) => {
          timeout = setTimeout(() => reject(new Error("O logo da empresa não carregou.")), 15000)
        }),
      ])
      frame.contentWindow.addEventListener("afterprint", () => setPrinting(null), { once: true })
      frame.contentWindow.focus()
      frame.contentWindow.print()
    } catch (err) {
      setPrinting(null)
      bridge.feedback?.error?.(
        "Não foi possível carregar o logo ou imprimir a SAT. Confira o logo no cadastro da empresa e tente novamente."
      )
    } finally {
      clearTimeout(timeout)
      setBusy(false)
    }
  }
  const save = async (event) => {
    event.preventDefault()
    if (draft.id && !dirty) {
      bridge.feedback?.success?.("Nenhuma alteração para salvar.")
      return
    }
    setBusy(true)
    try {
      const result = await subcontractRequest({
        bridge,
        path: `/assistance-requests${draft.id ? `/${draft.id}` : ""}`,
        method: draft.id ? "PUT" : "POST",
        body: payload(draft),
      })
      setDraft(creating ? null : result)
      setCreating(false)
      setSavedPayload(JSON.stringify(payload(result)))
      bridge.feedback?.success?.("SAT salva.")
      await load()
    } catch (err) {
      bridge.feedback?.error?.(err.message)
    } finally {
      setBusy(false)
    }
  }
  const transition = async (action) => {
    setBusy(true)
    try {
      const result = await subcontractRequest({
        bridge,
        path: `/assistance-requests/${draft.id}${action === "delete" ? "" : `/${action}`}`,
        method: action === "delete" ? "DELETE" : "POST",
        body: action === "reopen" ? { justification: reason } : null,
      })
      setDraft(action === "delete" ? null : result)
      setDeleting(false)
      setReopening(false)
      setReason("")
      await load()
      bridge.feedback?.success?.("Atendimento atualizado.")
    } catch (err) {
      bridge.feedback?.error?.(err.message)
    } finally {
      setBusy(false)
    }
  }
  const resolveUnit = useCallback((item) => {
    setDraft((old) => {
      if (!old || old.id || old.unit_id !== item.id || old.resolved_unit_id === item.id) return old
      return {
        ...old,
        customer_person_id: item.buyer_person_id || old.customer_person_id,
        unit_buyer_person_id: item.buyer_person_id,
        resolved_unit_id: item.id,
      }
    })
  }, [])
  const person = (label, key) => (
    <ReferencePicker
      bridge={bridge}
      kind="person"
      label={label}
      value={draft[key]}
      onChange={(value) =>
        setDraft((old) => ({
          ...old,
          [key]: value,
        }))
      }
      disabled={!editable || busy}
      required={key === "customer_person_id"}
    />
  )
  const pageActions = (
    <div className={styles.headerActions}>
      {can("canCreate") ? (
        <button
          className={actionClasses.primary}
          type="button"
          onClick={() => {
            setCreating(true)
            setDraft(empty(projectId, unitId, bridge.user))
            setTab("general")
          }}
        >
          <Plus size={16} aria-hidden="true" /> Nova SAT
        </button>
      ) : null}
      <button className={actionClasses.secondary} type="button" onClick={load} disabled={loading}>
        <RefreshCw size={16} aria-hidden="true" /> Atualizar
      </button>
    </div>
  )

  const editorFooter = draft ? (
    <div className={styles.editorFooter} role="group" aria-label="Ações da SAT">
      <button className={styles.modalSecondaryButton} type="button" onClick={closeEditor} disabled={busy}>
        {creating ? "Cancelar" : "Fechar detalhe"}
      </button>
      {editable ? (
        <button className={editorActionClasses.primary} type="submit" form={formId} disabled={busy}>
          Salvar SAT
        </button>
      ) : null}
      {draft.id ? (
        <div className={styles.actions}>
          {can("canUpdate") && draft.status === "open" ? (
            <button
              type="button"
              className={editorActionClasses.primary}
              disabled={busy || dirty}
              title={dirty ? "Salve as alterações antes de concluir" : "Concluir atendimento"}
              onClick={() => transition("complete")}
            >
              Concluir SAT
            </button>
          ) : null}
          {can("canUpdate") && draft.status === "completed" ? (
            <button
              type="button"
              className={editorActionClasses.secondary}
              disabled={busy}
              onClick={() => { setReason(""); setReopening(true) }}
            >
              Reabrir SAT
            </button>
          ) : null}
          {can("canDelete") ? (
            <button
              type="button"
              className={editorActionClasses.secondary}
              disabled={busy}
              onClick={() => setDeleting(true)}
            >
              Excluir SAT
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  ) : null
  if (!readable) return <p>Seu perfil não tem permissão para consultar assistência técnica.</p>
  return (
    <section className={styles.panel}>
      {PageHeader && !unitId ? (
        <PageHeader
          actions={pageActions}
          title="Assistência técnica"
          breadcrumb={[{ label: "Obras", path: "/construction" }, { label: "Assistência técnica" }]}
        />
      ) : (
        <div className={styles.header}>
          <h2>Assistência técnica</h2>
          {pageActions}
        </div>
      )}
      {!unitId ? (
        <div className={`${styles.card} ${styles.grid}`}>
          <ReferencePicker
            bridge={bridge}
            kind="project"
            label="Obra"
            value={filters.project_id}
            onChange={(id) => filter("project_id", id)}
            disabled={Boolean(projectId)}
          />
          <ReferencePicker
            bridge={bridge}
            kind="unit"
            label="Unidade e comprador"
            value={filters.unit_id}
            projectId={filters.project_id}
            onChange={(id) => filter("unit_id", id)}
            disabled={Boolean(unitId)}
          />
          <ReferencePicker
            bridge={bridge}
            kind="person"
            label="Comprador / solicitante"
            value={filters.customer_person_id}
            onChange={(id) => filter("customer_person_id", id)}
          />
          <ReferencePicker
            bridge={bridge}
            kind="person"
            label="Responsável"
            value={filters.responsible_person_id}
            onChange={(id) => filter("responsible_person_id", id)}
          />
          <label className={styles.field}>
            <span>Situação</span>
            <select value={filters.status} onChange={(e) => filter("status", e.target.value)}>
              <option value="">Todas</option>
              <option value="open">Aberta</option>
              <option value="completed">Concluída</option>
            </select>
          </label>
          <label className={styles.field}>
            <span>Atraso</span>
            <select value={filters.overdue} onChange={(e) => filter("overdue", e.target.value)}>
              <option value="">Todos</option>
              <option value="true">Com atraso</option>
              <option value="false">Sem atraso</option>
            </select>
          </label>
          {["opened_from", "opened_to"].map((key, i) => (
            <label key={key} className={styles.field}>
              <span>{i ? "Abertura até" : "Abertura de"}</span>
              <input type="date" value={filters[key]} onChange={(e) => filter(key, e.target.value)} />
            </label>
          ))}
        </div>
      ) : null}
      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          {loading ? (
            <p>Carregando atendimentos...</p>
          ) : error ? (
            <button type="button" onClick={load}>
              Tentar novamente
            </button>
          ) : !data.items.length ? (
            <p className={styles.emptyState}>Nenhum atendimento encontrado.</p>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  {["SAT", "Obra", "Unidade", "Comprador / solicitante", "Situação / etapa", "Ações"].map((text) => (
                    <th key={text}>{text}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.number}</td>
                    <td>{row.project_name}</td>
                    <td>{row.unit_code}</td>
                    <td>{row.customer_name}</td>
                    <td>
                      {statusLabels[row.status]} · {stageLabels[row.pending_stage]}
                      {row.overdue ? " · Em atraso" : ""}
                    </td>
                    <td>
                      <div className={styles.rowActions}>
                        {RowActionsMenu ? (
                          <RowActionsMenu
                            disabled={busy}
                            actions={[
                              { key: "details", label: "Detalhes", icon: Eye, onSelect: () => open(row) },
                              { key: "print", label: "Imprimir", icon: Printer, onSelect: () => print(row) },
                            ]}
                          />
                        ) : (
                          <>
                            <button
                              className={actionClasses.secondary}
                              type="button"
                              onClick={() => open(row)}
                              disabled={busy}
                            >
                              Detalhes
                            </button>
                            <button
                              className={actionClasses.secondary}
                              type="button"
                              onClick={() => print(row)}
                              disabled={busy}
                            >
                              Imprimir
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
        <div className={styles.paginationSlot}>
          <Pagination
            currentPage={page}
            pageSize={pageSize}
            totalItems={data.total}
            totalPages={data.total_pages}
            isLoading={loading}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size)
              setPage(1)
            }}
            pageSizeOptions={[10, 20, 50, 100]}
          />
        </div>
      </div>
      {printing ? (
        <iframe
          key={printing.id}
          className={styles.printDocument}
          title="Impressão da SAT"
          sandbox="allow-same-origin allow-modals"
          srcDoc={printing.html}
          onLoad={(event) => printLoaded(event.currentTarget)}
        />
      ) : null}
      {draft ? (
        <AssistanceEditorSurface
          bridge={bridge}
          title={creating ? "Nova SAT" : `SAT ${draft.number} · ${statusLabels[draft.status]}`}
          busy={busy}
          onClose={closeEditor}
          footer={editorFooter}
          closeOnEsc={!reopening && !deleting}
        >
          <nav className={appStyles.tabList}>
            {[
              ["general", "Dados gerais e contatos"],
              ["complaints", "Reclamações"],
              ["services", "Serviços"],
              ["history", "Histórico"],
            ].map(([key, label]) => (
              <button
                type="button"
                className={`${appStyles.tabButton} ${tab === key ? appStyles.tabButtonActive : ""}`}
                key={key}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
          </nav>
          <form id={formId} onSubmit={save}>
            <fieldset disabled={!editable || busy}>
              {tab === "general" ? (
                <>
                  <div className={styles.grid}>
                    <ReferencePicker
                      bridge={bridge}
                      kind="project"
                      label="Obra"
                      value={draft.project_id}
                      onChange={(id) => {
                        setDraft((old) => ({
                          ...old,
                          project_id: id,
                          unit_id: "",
                          customer_person_id: "",
                          unit_buyer_person_id: null,
                          resolved_unit_id: null,
                        }))
                      }}
                      disabled={Boolean(draft.id || projectId)}
                      required
                    />
                    <ReferencePicker
                      bridge={bridge}
                      kind="unit"
                      label="Unidade e comprador"
                      value={draft.unit_id}
                      projectId={draft.project_id}
                      onChange={(id, item) =>
                        setDraft((old) => ({
                          ...old,
                          unit_id: id,
                          customer_person_id: item?.buyer_person_id || "",
                          unit_buyer_person_id: item?.buyer_person_id || null,
                          resolved_unit_id: id,
                        }))
                      }
                      onResolve={resolveUnit}
                      displayName={
                        draft.id && draft.unit_code
                          ? `${draft.unit_code} - ${draft.customer_name || "Comprador não informado"}`
                          : undefined
                      }
                      disabled={Boolean(draft.id || unitId)}
                      required
                    />
                    {!draft.id && !draft.unit_buyer_person_id ? person("Solicitante", "customer_person_id") : null}
                    <label className={styles.field}>
                      <span>Responsável pelo atendimento *</span>
                      <input
                        value={draft.attendant_name || "Não informado"}
                        title={draft.attendant_name || "Não informado"}
                        disabled
                        readOnly
                      />
                    </label>
                    {person("Responsável pela análise", "analyst_person_id")}
                    <label className={styles.field}>
                      <span>Abertura *</span>
                      <input
                        type="datetime-local"
                        required
                        value={localDate(draft.opened_at)}
                        onChange={(e) => change("opened_at", instant(e.target.value))}
                      />
                    </label>
                  </div>
                  <label className={styles.field}>
                    <span>Observação</span>
                    <textarea value={draft.notes || ""} onChange={(e) => change("notes", e.target.value)} />
                  </label>
                  <h4>Contatos</h4>
                  {draft.contacts.map((contact, index) => (
                    <div className={styles.grid} key={contact.id || index}>
                      <label className={styles.field}>
                        <span>Canal *</span>
                        <select
                          value={contact.channel}
                          onChange={(e) => changeItem("contacts", index, "channel", e.target.value)}
                        >
                          <option value="whatsapp">WhatsApp</option>
                          <option value="phone">Telefone</option>
                          <option value="in_person">Pessoal</option>
                        </select>
                      </label>
                      <label className={styles.field}>
                        <span>Detalhe do contato</span>
                        <div className={styles.clearableField}>
                          <input
                            type={contact.channel === "in_person" ? "text" : "tel"}
                            inputMode={contact.channel === "in_person" ? "text" : "tel"}
                            placeholder={contact.channel === "in_person" ? "Detalhe do atendimento" : "(00) 00000-0000"}
                            value={contact.channel === "in_person" ? contact.detail || "" : maskPhone(contact.detail)}
                            onChange={(e) =>
                              changeItem(
                                "contacts",
                                index,
                                "detail",
                                contact.channel === "in_person" ? e.target.value : maskPhone(e.target.value)
                              )
                            }
                          />
                          <RemoveFieldButton
                            label="Remover contato"
                            disabled={!editable || busy}
                            onClick={() => remove("contacts", index)}
                          />
                        </div>
                      </label>
                    </div>
                  ))}
                  <button
                    type="button"
                    className={`${editorActionClasses.secondary} ${styles.addButton}`}
                    onClick={() => change("contacts", [...draft.contacts, { channel: "whatsapp", detail: "" }])}
                  >
                    Adicionar contato
                  </button>
                </>
              ) : null}
              {tab === "complaints" ? (
                <>
                  <p>Salve as reclamações novas como Pendentes antes de registrar a análise.</p>
                  {draft.complaints.map((item, index) => (
                    <div className={styles.item} key={item.id || index}>
                      <h4>Reclamação {item.original_number ?? index + 1}</h4>
                      <label className={styles.field}>
                        <span>Descrição *</span>
                        <div className={styles.clearableField}>
                          <textarea
                            required={!item.source_id}
                            value={item.description}
                            onChange={(e) => changeItem("complaints", index, "description", e.target.value)}
                          />
                          <RemoveFieldButton
                            label="Remover reclamação"
                            disabled={!editable || busy}
                            onClick={() => remove("complaints", index)}
                          />
                        </div>
                      </label>
                      <div className={styles.grid}>
                        <label className={styles.field}>
                          <span>Procedência</span>
                          <select
                            value={item.provenance}
                            disabled={!item.id}
                            onChange={(e) => changeItem("complaints", index, "provenance", e.target.value)}
                          >
                            <option value="pending">Pendente</option>
                            <option value="valid">Procedente</option>
                            <option value="invalid">Improcedente</option>
                          </select>
                        </label>
                        <ReferencePicker
                          bridge={bridge}
                          kind="person"
                          label="Analisado por"
                          value={item.analyzed_by_person_id}
                          onChange={(id) => changeItem("complaints", index, "analyzed_by_person_id", id)}
                          disabled={!item.id}
                        />
                        <label className={styles.field}>
                          <span>Analisado em</span>
                          <input
                            type="datetime-local"
                            value={localDate(item.analyzed_at)}
                            disabled={!item.id}
                            onChange={(e) => changeItem("complaints", index, "analyzed_at", instant(e.target.value))}
                          />
                        </label>
                      </div>
                    </div>
                  ))}
                  <button
                    type="button"
                    className={`${editorActionClasses.secondary} ${styles.addButton}`}
                    onClick={() =>
                      change("complaints", [...draft.complaints, { description: "", provenance: "pending" }])
                    }
                  >
                    Adicionar reclamação
                  </button>
                </>
              ) : null}
              {tab === "services" ? (
                <>
                  {draft.services.map((item, index) => (
                    <div className={styles.item} key={item.id || index}>
                      <h4>Serviço {item.original_number ?? index + 1}</h4>
                      <label className={styles.field}>
                        <span>Descrição *</span>
                        <div className={styles.clearableField}>
                          <textarea
                            required={!item.source_id}
                            value={item.description}
                            onChange={(e) => changeItem("services", index, "description", e.target.value)}
                          />
                          <RemoveFieldButton
                            label="Remover serviço"
                            disabled={!editable || busy}
                            onClick={() => remove("services", index)}
                          />
                        </div>
                      </label>
                      <div className={styles.grid}>
                        <label className={styles.field}>
                          <span>Reclamação atendida</span>
                          <select
                            value={item.complaint_id || ""}
                            onChange={(e) => changeItem("services", index, "complaint_id", e.target.value || null)}
                          >
                            <option value="">Sem vínculo</option>
                            {draft.complaints
                              .filter((c) => c.id)
                              .map((c) => (
                                <option key={c.id} value={c.id}>
                                  {c.description}
                                </option>
                              ))}
                          </select>
                        </label>
                        <label className={styles.field}>
                          <span>Prazo</span>
                          <input
                            type="date"
                            value={item.due_date || ""}
                            onChange={(e) => changeItem("services", index, "due_date", e.target.value || null)}
                          />
                        </label>
                        {[
                          ["executed", "Execução"],
                          ["inspected", "Inspeção"],
                        ].map(([key, label]) => (
                          <div className={styles.schedule} key={key}>
                            <ReferencePicker
                              bridge={bridge}
                              kind="person"
                              label={`Responsável pela ${label.toLowerCase()}`}
                              value={item[`${key}_by_person_id`]}
                              onChange={(id) => changeItem("services", index, `${key}_by_person_id`, id)}
                            />
                            <label className={styles.field}>
                              <span>Data de {label.toLowerCase()}</span>
                              <input
                                type="datetime-local"
                                value={localDate(item[`${key}_at`])}
                                onChange={(e) => changeItem("services", index, `${key}_at`, instant(e.target.value))}
                              />
                            </label>
                          </div>
                        ))}
                      </div>
                      {item.legacy_data?.caveats?.length ? (
                        <p>
                          Ressalvas históricas:{" "}
                          {item.legacy_data.caveats
                            .map((c) => (c === "invalid_due_date" ? "prazo ausente" : c))
                            .join("; ")}
                        </p>
                      ) : null}
                    </div>
                  ))}
                  <button
                    type="button"
                    className={`${editorActionClasses.secondary} ${styles.addButton}`}
                    onClick={() => change("services", [...draft.services, { description: "" }])}
                  >
                    Adicionar serviço
                  </button>
                </>
              ) : null}
            </fieldset>
          </form>
          {tab === "history" ? (
            <section className={styles.history}>
              <h4>Histórico de alterações</h4>
              {draft.history.map((event) => (
                <div className={styles.historyEvent} key={event.id}>
                  <strong>{eventLabels[event.action] || event.action}</strong> · {day(event.created_at)}
                  {event.payload.justification ? <p>{event.payload.justification}</p> : null}
                  {event.action === "completed" || event.action === "reopened" ? (
                    <p>Encerramento anterior: {day(event.payload.completed_at)}</p>
                  ) : null}
                </div>
              ))}
              {draft.legacy_data ? (
                <>
                  <h4>Dados históricos do atendimento</h4>
                  <p>Última alteração: {day(draft.legacy_data.source.data_alteracao)}</p>
                  <p>Execução registrada no atendimento: {day(draft.legacy_data.source.data_servico)}</p>
                  <p>Inspeção registrada no atendimento: {day(draft.legacy_data.source.data_inspecao)}</p>
                  <ReferencePicker
                    bridge={bridge}
                    kind="person"
                    label="Executor histórico"
                    value={draft.legacy_data.execution_person_id}
                    disabled
                  />
                  <ReferencePicker
                    bridge={bridge}
                    kind="person"
                    label="Inspetor histórico"
                    value={draft.legacy_data.inspection_person_id}
                    disabled
                  />
                  <p>
                    Registros históricos podem ter etapas incompletas. Confirme a análise das reclamações antes de
                    concluir um atendimento reaberto.
                  </p>
                </>
              ) : null}
            </section>
          ) : null}
        </AssistanceEditorSurface>
      ) : null}
      {reopening && draft?.status === "completed" && ConfirmDialog ? (
        <ConfirmDialog
          isOpen
          title="Reabrir SAT"
          message="Informe o motivo da reabertura com pelo menos 10 caracteres. Ele será registrado no histórico."
          confirmLabel="Confirmar reabertura"
          reasonLabel="Justificativa da reabertura *"
          reasonValue={reason}
          onReasonChange={setReason}
          reasonMinLength={10}
          confirmDisabled={reason.trim().length < 10}
          onConfirm={() => transition("reopen")}
          onCancel={() => { if (!busy) { setReopening(false); setReason("") } }}
          loading={busy}
        />
      ) : null}
      {reopening && draft?.status === "completed" && !ConfirmDialog ? (
        <AssistanceEditorSurface
          bridge={bridge}
          title="Reabrir SAT"
          dialogMaxWidth={520}
          busy={busy}
          onClose={() => { if (!busy) { setReopening(false); setReason("") } }}
          footer={<>
            <button type="button" className={styles.modalSecondaryButton} disabled={busy}
              onClick={() => { setReopening(false); setReason("") }}>Cancelar</button>
            <button type="button" className={styles.modalPrimaryButton}
              disabled={busy || reason.trim().length < 10} onClick={() => transition("reopen")}>
              Confirmar reabertura
            </button>
          </>}
        >
          <label className={styles.field}>
            <span>Justificativa da reabertura *</span>
            <textarea rows={4} value={reason} onChange={(event) => setReason(event.target.value)}
              minLength={10} disabled={busy} />
          </label>
          <p>Informe pelo menos 10 caracteres. O motivo será registrado no histórico.</p>
        </AssistanceEditorSurface>
      ) : null}
      {deleting && ConfirmDialog ? (
        <ConfirmDialog
          isOpen
          title="Excluir SAT"
          message="Confirma a exclusão deste atendimento? O histórico será preservado."
          variant="danger"
          onConfirm={() => transition("delete")}
          onCancel={() => setDeleting(false)}
          loading={busy}
        />
      ) : null}
      {deleting && !ConfirmDialog ? (
        <Dialog title="Excluir SAT" busy={busy} onClose={() => setDeleting(false)}>
          <p>Exclusão disponível no ERP integrado.</p>
        </Dialog>
      ) : null}
    </section>
  )
}

function AssistanceEditorSurface({ bridge, title, busy, onClose, footer, children, dialogMaxWidth = 1100, closeOnEsc = true }) {
  const Modal = bridge.components?.Modal
  const content = <div className={styles.editor}>{children}</div>
  return Modal ? (
    <Modal
      isOpen
      title={title}
      onClose={onClose}
      closeOnEsc={closeOnEsc && !busy}
      closeOnOverlayClick={!busy}
      dialogMaxWidth={dialogMaxWidth}
      footer={footer}
    >
      {content}
    </Modal>
  ) : (
    <Dialog title={title} wide={dialogMaxWidth > 600} busy={busy} onClose={onClose}>
      {content}
      <div className={styles.fallbackFooter}>{footer}</div>
    </Dialog>
  )
}

function RemoveFieldButton({ label, disabled, onClick }) {
  return (
    <button
      className={styles.removeButton}
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
    >
      <X size={16} aria-hidden="true" />
    </button>
  )
}
