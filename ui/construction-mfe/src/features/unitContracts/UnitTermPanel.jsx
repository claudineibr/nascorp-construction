import { useCallback, useEffect, useState } from "react";
import { FileText, PenLine, Printer, RefreshCcw, Save } from "lucide-react";
import { unitTermRequest } from "../../services/unitTerms.js";
import { Dialog } from "../subcontracts/DirectBillsSection.jsx";
import styles from "./UnitContractPanel.module.css";
import termStyles from "./UnitTermPanel.module.css";

const origins = { legacy: "Legado", generation: "Gerado", manual: "Manual" };

export function UnitTermPanel({ bridge, unit, kind }) {
  const title = kind === "delivery_term" ? "Termo de entrega" : "TCD";
  const [history, setHistory] = useState({ items: [], current_version_id: null });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [city, setCity] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [editor, setEditor] = useState(null);
  const [printing, setPrinting] = useState(null);
  const canRead = bridge?.canRead?.("contract") === true;
  const canCreate = bridge?.canCreate?.("contract") === true;
  const canUpdate = bridge?.canUpdate?.("contract") === true;
  const report = useCallback((error) => bridge?.feedback?.error?.(error.message), [bridge]);
  const request = useCallback((path, body) => unitTermRequest(bridge, unit.id, kind, path, body), [bridge, unit.id, kind]);
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await request("/versions");
      setHistory(result);
      setSelected(result.items.find((row) => row.id === result.current_version_id) ?? null);
      setFailed(false);
    } catch (error) { setFailed(true); report(error); }
    finally { setLoading(false); }
  }, [request, report]);
  useEffect(() => { if (canRead) refresh(); }, [canRead, refresh]);
  const open = async (mode) => {
    setBusy(true);
    try {
      const context = mode === "template" ? await request("/template")
        : mode === "edit" ? await request(`/versions/${selected.id}/edit-context`)
          : await request("/preview", { city, jurisdiction });
      setEditor({ ...context, mode, city, jurisdiction,
        current_version_id: context.current_version_id ?? history.current_version_id });
    } catch (error) { report(error); }
    finally { setBusy(false); }
  };
  const saved = async () => {
    setEditor(null);
    await refresh();
    bridge?.feedback?.success?.("Termo preservado em uma nova versão.");
  };
  const printLoaded = async (frame) => {
    let timeout;
    try {
      await Promise.race([
        Promise.all([frame.contentDocument.fonts.ready, ...Array.from(frame.contentDocument.images, (image) => image.decode())]),
        new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error("As imagens do termo não carregaram.")), 15000); }),
      ]);
      frame.contentWindow.addEventListener("afterprint", () => setPrinting(null), { once: true });
      frame.contentWindow.focus();
      frame.contentWindow.print();
    } catch (error) { setPrinting(null); report(error); }
    finally { clearTimeout(timeout); setBusy(false); }
  };
  if (!canRead) return <p>Você não tem permissão para consultar termos de contrato.</p>;
  if (loading) return <p aria-busy="true">Carregando versões do termo...</p>;
  return <section className={styles.panel}>
    <div className={styles.actions}>
      <button type="button" className={styles.secondaryButton} onClick={refresh} disabled={busy}>
        <RefreshCcw size={16} aria-hidden="true" />{failed ? "Tentar novamente" : "Atualizar histórico"}
      </button>
      {canCreate && <button type="button" className={styles.primaryButton} onClick={() => open("generate")} disabled={busy || failed}>
        <FileText size={16} aria-hidden="true" />Gerar {title}
      </button>}
      {canUpdate && <button type="button" className={styles.secondaryButton} onClick={() => open("template")} disabled={busy}>
        <PenLine size={16} aria-hidden="true" />Editar modelo da empresa
      </button>}
    </div>
    {canCreate && <fieldset className={styles.fields} disabled={busy}>
      <label className={styles.field}><span>Cidade *</span><input value={city} maxLength={180}
        placeholder="Usar a cidade da obra" onChange={(event) => setCity(event.target.value)} /></label>
      {kind === "debt_confession" && <label className={styles.field}><span>Foro *</span>
        <input value={jurisdiction} maxLength={180} onChange={(event) => setJurisdiction(event.target.value)} /></label>}
    </fieldset>}
    {kind === "debt_confession" && <p>O TCD usa o saldo em aberto das parcelas da venda e dos aditivos, com os vencimentos originais.
      Sinal e documentação ficam fora. A emissão do termo não altera cobranças.</p>}
    <div className={styles.card}>
      <h3>Histórico de versões</h3>
      {!history.items.length ? <p>Nenhuma versão disponível.</p> : <div className={styles.tableWrapper}><table>
        <thead><tr><th>Versão</th><th>Origem</th><th>Quem salvou</th><th>Quando</th><th>Motivo</th></tr></thead>
        <tbody>{history.items.map((row) => <tr key={row.id}>
          <td><button type="button" className={styles.secondaryButton} onClick={() => setSelected(row)}>{row.version_number}</button></td>
          <td>{origins[row.type] ?? row.type}</td><td>{row.created_by_name}</td>
          <td>{row.type === "legacy" ? "Importado em " : ""}{new Date(`${row.applied_at}Z`).toLocaleString("pt-BR")}</td>
          <td>{row.reason || "-"}</td>
        </tr>)}</tbody>
      </table></div>}
    </div>
    {selected && <div className={styles.card}>
      <h3>{title} - versão {selected.version_number}</h3>
      <div className={styles.actions}>
        {canUpdate && <button type="button" className={styles.secondaryButton} onClick={() => open("edit")} disabled={busy}>
          <PenLine size={16} aria-hidden="true" />Editar texto
        </button>}
        <button type="button" className={styles.secondaryButton} disabled={busy} onClick={() => { setBusy(true); setPrinting(selected); }}>
          <Printer size={16} aria-hidden="true" />Imprimir termo
        </button>
      </div>
      <p>Na impressão, escolha a impressora ou Salvar como PDF. Documentos salvos preservam os dados usados naquela versão.</p>
      <iframe className={styles.document} title={`${title} versão ${selected.version_number}`} sandbox="" srcDoc={selected.content_html} />
    </div>}
    {printing && <iframe key={printing.id} className={styles.printDocument} title="Impressão do termo"
      sandbox="allow-same-origin allow-modals" srcDoc={printing.content_html} onLoad={(event) => printLoaded(event.currentTarget)} aria-hidden="true" tabIndex={-1} />}
    {editor && <TermEditor bridge={bridge} title={title} context={editor} request={request}
      onClose={() => setEditor(null)} onSaved={saved} />}
  </section>;
}

function TermEditor({ bridge, title, context, request, onClose, onSaved }) {
  const [content, setContent] = useState(context.content_html);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const Editor = bridge?.components?.RichTextEditor;
  const Modal = bridge?.components?.Modal;
  const isTemplate = context.mode === "template";
  const isEdit = context.mode === "edit";
  const formId = `unit-term-${context.mode}`;
  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await request(isTemplate ? "/template" : isEdit ? "/edit" : "/save", isTemplate
        ? { content_html: content, version: context.version }
        : { content_html: content, reason, version_id: context.version_id ?? null,
          current_version_id: context.current_version_id, context_hash: context.context_hash,
          city: context.city, jurisdiction: context.jurisdiction });
      if (isTemplate) {
        onClose();
        bridge?.feedback?.success?.("Modelo salvo. A alteração vale só para novas gerações.");
      } else await onSaved();
    } catch (error) { bridge?.feedback?.error?.(error.message); }
    finally { setBusy(false); }
  };
  const footer = <div className={`${styles.panel} ${styles.actions}`}>
    <button type="button" className={styles.secondaryButton} disabled={busy} onClick={onClose}>Cancelar</button>
    <button type="submit" form={formId} className={styles.primaryButton}
      disabled={busy || !content.trim() || (isEdit && !reason.trim()) || (!Editor && (isEdit || isTemplate))}>
      <Save size={16} aria-hidden="true" />{busy ? "Salvando..." : isTemplate ? "Salvar modelo" : "Salvar nova versão"}
    </button>
  </div>;
  const body = <form id={formId} className={styles.panel} onSubmit={save}>
    <p>{isTemplate ? "Este modelo pertence à empresa. A alteração vale só para novas gerações." : "Salvar preserva uma nova versão e mantém todas as anteriores. O texto não altera o financeiro."}</p>
    {isTemplate && <p>Marcadores disponíveis: {context.placeholders.map((key) => `{{${key}}}`).join(", ")}.</p>}
    {!Editor && <p>O editor visual está indisponível. Reabra o módulo Obras dentro do ERP para editar.</p>}
    <fieldset className={termStyles.editorFields} disabled={busy}>
      {Editor && <div className={styles.field}><span>Conteúdo *</span>
        <Editor value={content} onChange={(event) => setContent(event.target.value)} disabled={busy} /></div>}
      {isEdit && <label className={styles.field}><span>Motivo da edição *</span>
        <input required maxLength={255} value={reason} onChange={(event) => setReason(event.target.value)} /></label>}
    </fieldset>
    <iframe className={styles.document} title={`Prévia de ${title}`} sandbox="" srcDoc={content} />
  </form>;
  const dialogTitle = isTemplate ? `Modelo de ${title}` : isEdit ? `Editar ${title}` : `Prévia de ${title}`;
  return Modal ? <Modal isOpen title={dialogTitle} onClose={() => !busy && onClose()} closeOnEsc={!busy}
    closeOnOverlayClick={!busy} dialogMaxWidth={1100} footer={footer}>{body}</Modal>
    : <Dialog title={dialogTitle} wide busy={busy} onClose={onClose}>{body}{footer}</Dialog>;
}
