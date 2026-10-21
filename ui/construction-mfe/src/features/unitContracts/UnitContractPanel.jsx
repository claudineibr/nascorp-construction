import { useCallback, useEffect, useState } from "react";
import { Printer, FileText, RefreshCcw, CheckCircle, PenLine, Download } from "lucide-react";
import { downloadUnitContract, unitContractRequest } from "../../services/unitContracts.js";
import { ContractTemplateField } from "./ContractTemplateField.jsx";
import { UnitContractManualEdit } from "./UnitContractManualEdit.jsx";
import { Dialog } from "../subcontracts/DirectBillsSection.jsx";
import styles from "./UnitContractPanel.module.css";

const origin = { generation: "Geração", regeneration: "Regeração", legacy: "Legado", initial: "Inicial", manual: "Manual", adjustment: "Reajuste", signature: "Assinatura" };
const status = { draft: "Minuta", signed: "Assinado", sent: "Enviado", active: "Ativo", canceled: "Cancelado" };
const labels = { primary: "Comprador principal", secondary: "Segundo comprador", metragem: "Metragem do empreendimento",
  lote: "Lote", matricula: "Matrícula", creci: "CRECI", corretor: "Corretor", dataentrega: "Entrega prevista",
  vendedor: "Razão social do vendedor", vendedor_documento: "CNPJ do vendedor", vendedor_endereco: "Endereço do vendedor",
  representante: "Representante", representante_estado_civil: "Estado civil do representante",
  representante_cpf: "CPF do representante", representante_rg: "RG do representante", foro: "Foro", cidade_contrato: "Cidade do contrato" };

function variableLabel(key) {
  if (labels[key]) return labels[key];
  const parts = { nome: "Nome", documento: "CPF/CNPJ", estadocivil: "Estado civil", rg: "RG", contatos: "Contatos",
    logradouro: "Endereço", cidade: "Cidade", estado: "Estado", nacionalidade: "Nacionalidade" };
  for (const [prefix, label] of [["comprador_", "comprador principal"], ["segundo_comprador_", "segundo comprador"]]) {
    if (key.startsWith(prefix)) return `${parts[key.slice(prefix.length)] ?? key.slice(prefix.length)} do ${label}`;
  }
  return key.replaceAll("_", " ");
}

export function UnitContractPanel({ bridge, unit }) {
  const [history, setHistory] = useState({ items: [], differences: {} });
  const [preview, setPreview] = useState(null);
  const [selected, setSelected] = useState(null);
  const [templateId, setTemplateId] = useState("");
  const [manualFields, setManualFields] = useState({});
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [divergent, setDivergent] = useState([]);
  const [signing, setSigning] = useState(false);
  const [signatureRole, setSignatureRole] = useState("customer");
  const [signedDate, setSignedDate] = useState("");
  const [printing, setPrinting] = useState(null);
  const [downloading, setDownloading] = useState(null);
  const [editing, setEditing] = useState(null);
  const canRead = bridge?.canRead?.("contract") === true;
  const canGenerate = bridge?.canCreate?.("contract") === true && ["sold", "delivered"].includes(unit.status);
  const report = useCallback((error) => bridge?.feedback?.error?.(error.message), [bridge]);
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await unitContractRequest(bridge, `/${unit.id}/versions`);
      setHistory(result);
      setSelected(result.items.find((row) => row.id === result.current_version_id) ?? result.items[0] ?? null);
      setFailed(false);
      if (result.items.some((row) => row.data?.variables)) {
        const context = await unitContractRequest(bridge, `/${unit.id}/context`);
        setDivergent(context.divergent_fields);
      }
    } catch (error) { setFailed(true); report(error); }
    finally { setLoading(false); }
  }, [bridge, unit.id, report]);
  useEffect(() => { if (canRead) refresh(); }, [canRead, refresh]);
  const review = async () => {
    setBusy(true);
    try {
      const result = await unitContractRequest(bridge, `/${unit.id}/preview`, {
        template_id: templateId || null, manual_fields: manualFields, reason: reason || null });
      setPreview(result);
      setTemplateId(result.template_id);
      setManualFields(result.manual_fields);
    } catch (error) { report(error); }
    finally { setBusy(false); }
  };
  const generate = async () => {
    setBusy(true);
    try {
      await unitContractRequest(bridge, `/${unit.id}/generate`, {
        template_id: preview.template_id, manual_fields: manualFields, reason: reason || null,
        context_hash: preview.context_hash });
      setPreview(null);
      await refresh();
      bridge?.feedback?.success?.("Nova versão do contrato preservada.");
    } catch (error) { report(error); }
    finally { setBusy(false); }
  };
  const sign = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await unitContractRequest(bridge, `/${unit.id}/sign`, {
        version_id: selected.id, role: signatureRole, signed_date: signedDate });
      setSigning(false);
      await refresh();
      bridge?.feedback?.success?.("Assinatura registrada na versão do contrato.");
    } catch (error) { report(error); }
    finally { setBusy(false); }
  };
  const printVersion = (version) => {
    setBusy(true);
    setPrinting(version);
  };
  const editVersion = async (version) => {
    setBusy(true);
    try {
      const context = await unitContractRequest(bridge, `/${unit.id}/versions/${version.id}/edit-context`);
      setEditing(context);
    } catch (error) { report(error); }
    finally { setBusy(false); }
  };
  const downloadVersion = async (version, kind) => {
    setBusy(true);
    setDownloading(kind);
    let url;
    let link;
    try {
      const blob = await downloadUnitContract(bridge, unit.id, version.id, kind);
      url = URL.createObjectURL(blob);
      link = document.createElement("a");
      link.href = url;
      link.download = `contrato-${unit.code || unit.id}-v${version.version_number}.${kind}`;
      document.body.appendChild(link);
      link.click();
    } catch (error) { report(error); }
    finally {
      link?.remove();
      if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
      setDownloading(null);
      setBusy(false);
    }
  };
  const printLoaded = async (frame) => {
    let timeout;
    try {
      const ready = Promise.all([
        frame.contentDocument.fonts.ready,
        ...Array.from(frame.contentDocument.images, (image) => image.decode()),
      ]);
      await Promise.race([ready, new Promise((_, reject) => {
        timeout = setTimeout(() => reject(new Error("As imagens do contrato não carregaram. Tente imprimir novamente.")), 15000);
      })]);
      frame.contentWindow.addEventListener("afterprint", () => setPrinting(null), { once: true });
      frame.contentWindow.focus();
      frame.contentWindow.print();
    } catch (error) {
      setPrinting(null);
      report(new Error("Não foi possível carregar as imagens ou imprimir o contrato. Atualize o histórico e tente novamente."));
    } finally {
      clearTimeout(timeout);
      setBusy(false);
    }
  };
  if (!canRead) return <p>Você não tem permissão para consultar contratos.</p>;
  if (loading) return <p aria-busy="true">Carregando versões do contrato...</p>;
  const hasDocument = history.items.some((row) => row.html_hash);
  const changes = selected ? history.differences[selected.id] ?? {} : {};
  return <section className={styles.panel}>
    {divergent.length > 0 && <p>Os dados atuais diferem do último documento. Revise e gere outra versão: {divergent.map((key) => variableLabel(key)).join(", ")}.</p>}
    <div className={styles.actions}>
      <button type="button" className={styles.secondaryButton} onClick={refresh} disabled={busy}>
        <RefreshCcw size={16} aria-hidden="true" />{failed ? "Tentar novamente" : "Atualizar histórico"}
      </button>
      {canGenerate && <button type="button" className={styles.primaryButton} onClick={review} disabled={busy}>
        <FileText size={16} aria-hidden="true" />{hasDocument ? "Regerar contrato" : "Gerar contrato"}
      </button>}
    </div>
    {canGenerate && <fieldset disabled={busy} className={styles.fields}>
      <ContractTemplateField bridge={bridge} value={templateId} onChange={(value) => { setTemplateId(value); setPreview(null); }} />
      {hasDocument && <label className={styles.field}><span>Motivo da regeração *</span>
        <input value={reason} maxLength={255} onChange={(event) => { setReason(event.target.value); setPreview(null); }} />
      </label>}
    </fieldset>}
    {preview && <div className={styles.card}>
      <h3>Prévia do contrato</h3>
      {preview.divergent_fields.length > 0 && <p>Os dados atuais diferem da última geração: {preview.divergent_fields.map((key) => variableLabel(key)).join(", ")}.</p>}
      <div className={styles.fields}>{[...new Set([...preview.pending_fields, ...Object.keys(preview.manual_fields)])].map((key) =>
        <label key={key} className={styles.field}><span>{variableLabel(key)} *</span>
          <input value={manualFields[key] ?? ""} onChange={(event) => {
            setManualFields({ ...manualFields, [key]: event.target.value });
            setPreview({ ...preview, context_hash: "" });
          }} />
        </label>)}</div>
      <iframe className={styles.document} title="Prévia do contrato" sandbox="" srcDoc={preview.content_html} />
      <div className={styles.actions}>
        <button type="button" className={styles.secondaryButton} onClick={review} disabled={busy}>
          <RefreshCcw size={16} aria-hidden="true" />Atualizar prévia
        </button>
        <button type="button" className={styles.primaryButton} onClick={generate}
          disabled={busy || preview.pending_fields.length > 0 || !preview.context_hash || (hasDocument && !reason.trim())}>
          <CheckCircle size={16} aria-hidden="true" />Confirmar geração
        </button>
      </div>
    </div>}
    <div className={styles.card}>
      <h3>Histórico de versões</h3>
      {!history.items.length ? <p>Nenhuma versão disponível. Confirme a venda da unidade antes de gerar.</p> : <div className={styles.tableWrapper}><table>
        <thead><tr><th>Versão</th><th>Origem</th><th>Template</th><th>Quem gerou</th><th>Quando</th><th>Situação</th><th>Motivo</th><th>Impressão</th></tr></thead>
        <tbody>{history.items.map((row) => <tr key={row.id}>
          <td><button type="button" className={styles.secondaryButton} onClick={() => setSelected(row)}>{row.version_number}</button></td>
          <td>{origin[row.type] ?? row.type}</td><td>{row.template_name || "Não informado"}</td><td>{row.created_by_name || "Não informado"}</td>
          <td>{row.type === "legacy" ? "Data legada não informada; importado em " : ""}{new Date(`${row.applied_at}Z`).toLocaleString("pt-BR")}</td>
          <td>{status[row.status] ?? row.status}</td><td>{row.reason || "-"}</td>
          <td><button type="button" className={styles.secondaryButton} onClick={() => printVersion(row)} disabled={busy || !row.content_html}>
            <Printer size={16} aria-hidden="true" />Imprimir contrato
          </button></td>
        </tr>)}</tbody>
      </table></div>}
    </div>
    {selected && <div className={styles.card}>
      <h3>Documento da versão {selected.version_number}</h3>
      <div className={styles.actions}>
        {bridge?.canUpdate?.("contract") && selected.content_html &&
          <button type="button" className={styles.secondaryButton} onClick={() => editVersion(selected)} disabled={busy}>
            <PenLine size={16} aria-hidden="true" />Editar texto
          </button>}
        {selected.pdf_hash && <button type="button" className={styles.secondaryButton}
          onClick={() => downloadVersion(selected, "pdf")} disabled={busy}>
          <Download size={16} aria-hidden="true" />{downloading === "pdf" ? "Baixando PDF..." : "Baixar PDF"}
        </button>}
        {selected.docx_hash && <button type="button" className={styles.secondaryButton}
          onClick={() => downloadVersion(selected, "docx")} disabled={busy}>
          <Download size={16} aria-hidden="true" />{downloading === "docx" ? "Baixando Word..." : "Baixar Word"}
        </button>}
        <button type="button" className={styles.secondaryButton} onClick={() => printVersion(selected)} disabled={busy || !selected.content_html}>
          <Printer size={16} aria-hidden="true" />Imprimir contrato
        </button>
        {selected.id === history.current_version_id && selected.html_hash && ["draft", "sent"].includes(selected.status) && bridge?.canUpdate?.("contract") &&
          <button type="button" className={styles.primaryButton} onClick={() => setSigning(true)} disabled={busy}>
            <PenLine size={16} aria-hidden="true" />Registrar assinatura
          </button>}
      </div>
      <p>Na impressão, escolha a impressora ou Salvar como PDF.</p>
      {selected.data?.manual_edit && <p>Edição manual baseada na versão {selected.data.edited_from_version_number}.
        Consulte essa versão no histórico para comparar o texto.</p>}
      <iframe className={styles.document} title={`Contrato versão ${selected.version_number}`} sandbox="" srcDoc={selected.content_html} />
      <details><summary>Diferenças das variáveis</summary>{Object.entries(changes).map(([key, value]) =>
        <p key={key}><strong>{variableLabel(key)}</strong>: {value.previous ?? "Não informado"} → {value.current ?? "Não informado"}</p>)}</details>
    </div>}
    {printing && <iframe key={printing.id} className={styles.printDocument} title={`Impressão do contrato versão ${printing.version_number}`}
      sandbox="allow-same-origin allow-modals" srcDoc={printing.content_html} onLoad={(event) => printLoaded(event.currentTarget)}
      aria-hidden="true" tabIndex={-1} />}
    {editing && <UnitContractManualEdit key={editing.version_id} bridge={bridge} unitId={unit.id} context={editing}
      onClose={() => setEditing(null)} onSaved={async () => {
        setEditing(null);
        setPreview(null);
        await refresh();
        bridge?.feedback?.success?.("Edição salva em uma nova versão do contrato.");
      }} />}
    {signing && <Dialog title="Registrar assinatura da versão" busy={busy} onClose={() => setSigning(false)}>
      <form className={styles.panel} onSubmit={sign}>
        <p>Registre a assinatura já realizada no documento da versão {selected.version_number}.</p>
        <label className={styles.field}><span>Parte que assinou *</span><select value={signatureRole} onChange={(event) => setSignatureRole(event.target.value)} disabled={busy}>
          <option value="customer">Comprador</option><option value="company">Empresa</option>
        </select></label>
        <label className={styles.field}><span>Data da assinatura *</span><input type="date" required value={signedDate} onChange={(event) => setSignedDate(event.target.value)} disabled={busy} /></label>
        <div className={styles.actions}>
          <button type="button" className={styles.secondaryButton} onClick={() => setSigning(false)} disabled={busy}>Cancelar</button>
          <button type="submit" className={styles.primaryButton} disabled={busy || !signedDate}>
            <CheckCircle size={16} aria-hidden="true" />Confirmar registro
          </button>
        </div>
      </form>
    </Dialog>}
  </section>;
}
