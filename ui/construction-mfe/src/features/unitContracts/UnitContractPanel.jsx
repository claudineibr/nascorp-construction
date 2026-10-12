import { useCallback, useEffect, useState } from "react";
import { Download, FileText, RefreshCw } from "lucide-react";
import { unitContractRequest, downloadUnitContract } from "../../services/unitContracts.js";
import { ContractTemplateField } from "./ContractTemplateField.jsx";
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
  const download = async (version, kind) => {
    setBusy(true);
    try {
      const blob = await downloadUnitContract(bridge, unit.id, version.id, kind);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `contrato-v${version.version_number}.${kind}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) { report(error); }
    finally { setBusy(false); }
  };
  if (!canRead) return <p>Você não tem permissão para consultar contratos.</p>;
  if (loading) return <p aria-busy="true">Carregando versões do contrato...</p>;
  const hasDocument = history.items.some((row) => row.html_hash);
  const changes = selected ? history.differences[selected.id] ?? {} : {};
  return <section className={styles.panel}>
    {divergent.length > 0 && <p>Os dados atuais diferem do último documento. Revise e gere outra versão: {divergent.map((key) => variableLabel(key)).join(", ")}.</p>}
    <div className={styles.actions}>
      <button type="button" className={styles.secondaryButton} onClick={refresh} disabled={busy}>
        <RefreshCw size={16} aria-hidden="true" />{failed ? "Tentar novamente" : "Atualizar histórico"}
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
        <button type="button" className={styles.secondaryButton} onClick={review} disabled={busy}>Atualizar prévia</button>
        <button type="button" className={styles.primaryButton} onClick={generate}
          disabled={busy || preview.pending_fields.length > 0 || !preview.context_hash || (hasDocument && !reason.trim())}>
          Confirmar geração
        </button>
      </div>
    </div>}
    <div className={styles.card}>
      <h3>Histórico de versões</h3>
      {!history.items.length ? <p>Nenhuma versão disponível. Confirme a venda da unidade antes de gerar.</p> : <div className={styles.tableWrapper}><table>
        <thead><tr><th>Versão</th><th>Origem</th><th>Template</th><th>Quem gerou</th><th>Quando</th><th>Situação</th><th>Motivo</th><th>Arquivos</th></tr></thead>
        <tbody>{history.items.map((row) => <tr key={row.id}>
          <td><button type="button" className={styles.secondaryButton} onClick={() => setSelected(row)}>{row.version_number}</button></td>
          <td>{origin[row.type] ?? row.type}</td><td>{row.template_name || "Não informado"}</td><td>{row.created_by_name || "Não informado"}</td>
          <td>{row.type === "legacy" ? "Data legada não informada; importado em " : ""}{new Date(`${row.applied_at}Z`).toLocaleString("pt-BR")}</td>
          <td>{status[row.status] ?? row.status}</td><td>{row.reason || "—"}</td>
          <td><div className={styles.actions}>{["html", "pdf", "docx"].filter((kind) => row[`${kind}_hash`]).map((kind) =>
            <button type="button" key={kind} className={styles.secondaryButton} onClick={() => download(row, kind)} disabled={busy}>
              <Download size={16} aria-hidden="true" />{kind === "docx" ? "Word" : kind.toUpperCase()}
            </button>)}</div></td>
        </tr>)}</tbody>
      </table></div>}
    </div>
    {selected && <div className={styles.card}>
      <h3>Documento da versão {selected.version_number}</h3>
      {selected.id === history.current_version_id && selected.html_hash && ["draft", "sent"].includes(selected.status) && bridge?.canUpdate?.("contract") &&
        <button type="button" className={styles.secondaryButton} onClick={() => setSigning(true)} disabled={busy}>
          Registrar assinatura
        </button>}
      <iframe className={styles.document} title={`Contrato versão ${selected.version_number}`} sandbox="" srcDoc={selected.content_html} />
      <details><summary>Diferenças das variáveis</summary>{Object.entries(changes).map(([key, value]) =>
        <p key={key}><strong>{variableLabel(key)}</strong>: {value.previous ?? "Não informado"} → {value.current ?? "Não informado"}</p>)}</details>
    </div>}
    {signing && <Dialog title="Registrar assinatura da versão" busy={busy} onClose={() => setSigning(false)}>
      <form className={styles.panel} onSubmit={sign}>
        <p>Registre a assinatura já realizada no documento da versão {selected.version_number}.</p>
        <label className={styles.field}><span>Parte que assinou *</span><select value={signatureRole} onChange={(event) => setSignatureRole(event.target.value)} disabled={busy}>
          <option value="customer">Comprador</option><option value="company">Empresa</option>
        </select></label>
        <label className={styles.field}><span>Data da assinatura *</span><input type="date" required value={signedDate} onChange={(event) => setSignedDate(event.target.value)} disabled={busy} /></label>
        <div className={styles.actions}>
          <button type="button" className={styles.secondaryButton} onClick={() => setSigning(false)} disabled={busy}>Cancelar</button>
          <button type="submit" className={styles.primaryButton} disabled={busy || !signedDate}>Confirmar registro</button>
        </div>
      </form>
    </Dialog>}
  </section>;
}
