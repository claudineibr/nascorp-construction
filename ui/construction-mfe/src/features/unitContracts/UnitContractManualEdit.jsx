import { useState } from "react";
import { Save } from "lucide-react";
import { unitContractRequest } from "../../services/unitContracts.js";
import { Dialog } from "../subcontracts/DirectBillsSection.jsx";
import styles from "./UnitContractPanel.module.css";

export function UnitContractManualEdit({ bridge, unitId, context, onClose, onSaved }) {
  const [content, setContent] = useState(context.content_html);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const Editor = bridge?.components?.RichTextEditor;
  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await unitContractRequest(bridge, `/${unitId}/edit`, {
        version_id: context.version_id, current_version_id: context.current_version_id,
        content_html: content, reason: reason.trim(),
      });
      await onSaved();
    } catch (error) { bridge?.feedback?.error?.(error.message); }
    finally { setSaving(false); }
  };
  return <Dialog title="Editar texto do contrato" wide busy={saving} onClose={onClose}>
    {!Editor ? <p>O editor visual está indisponível. Reabra o módulo Obras dentro do ERP.</p> :
      <form className={styles.panel} onSubmit={save}>
        <p>A edição salva uma nova minuta com seu nome e preserva a versão original e suas assinaturas.
          O texto editado não altera os dados da venda nem os valores financeiros.</p>
        <div className={styles.field}><span>Conteúdo do contrato *</span>
          <Editor value={content} onChange={(event) => setContent(event.target.value)} disabled={saving} />
        </div>
        <label className={styles.field}><span>Motivo da edição *</span>
          <input required maxLength={255} value={reason} onChange={(event) => setReason(event.target.value)} disabled={saving} />
        </label>
        <details><summary>Conferir prévia do texto editado</summary>
          <iframe className={styles.document} title="Prévia da edição manual" sandbox="" srcDoc={content} />
        </details>
        <div className={styles.actions}>
          <button type="button" className={styles.secondaryButton} onClick={onClose} disabled={saving}>Cancelar</button>
          <button type="submit" className={styles.primaryButton} disabled={saving || !reason.trim() || !content.trim()}>
            <Save size={16} aria-hidden="true" />{saving ? "Salvando..." : "Salvar nova versão"}
          </button>
        </div>
      </form>}
  </Dialog>;
}
