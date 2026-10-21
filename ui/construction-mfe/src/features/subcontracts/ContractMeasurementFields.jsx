import { useEffect, useState } from "react";
import { InfoTip } from "../../components/InfoTip";
import { subcontractRequest } from "../../services/constructionApi";
import styles from "./SubcontractsPanel.module.css";
import appStyles from "../../App.module.css";

export function ContractMeasurementFields({
  bridge,
  projectId,
  form,
  onChange,
}) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    if (!projectId) return;
    setLoading(true);
    setError("");
    subcontractRequest({ bridge, path: `/projects/${projectId}/subcontracts` })
      .then((result) => {
        if (active)
          setRows(result.items.filter((row) => row.status === "RELEASED"));
      })
      .catch((failure) => {
        if (active) setError(failure.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [bridge, projectId, attempt]);
  const choose = (contractId) => {
    const row = rows.find((candidate) => candidate.id === contractId);
    onChange("subcontractId", row?.id ?? "");
    onChange("purpose", row ? "CONTRACT" : "SERVICE");
    if (row) {
      onChange("supplierPersonId", row.supplier_person_id);
      if (!form.documentType?.trim()) onChange("documentType", "NFS-e");
    }
  };
  const hint = form.purpose === "CONTROL"
    ? "OS de controle físico: registre serviços e FVS sem valor próprio. A DNF pode pagar um conjunto de OS depois."
    : form.purpose === "CONTRACT"
      ? "Informe somente quantidades executadas. O contrato fornece empreiteiro, serviços e preços."
      : "Serviço avulso: informe o valor próprio do serviço; não consome saldo de contrato.";
  return (
    <fieldset className={`${styles.panel} ${styles.contractBox}`}>
      <legend>
        Finalidade da medição
        <InfoTip label="Quando vincular um contrato de empreitada">
          Vincule quando o serviço faz parte de um contrato liberado na aba
          Empreitada: o valor sai do preço contratado e a aprovação consome o
          saldo. Sem contrato, escolha serviço avulso com pagamento próprio ou OS de controle sem valor próprio.
        </InfoTip>
      </legend>
      <label>
        Finalidade*
        <select value={form.purpose ?? (form.subcontractId ? "CONTRACT" : "SERVICE")}
          onChange={(event) => {
            const purpose = event.target.value;
            onChange("purpose", purpose);
            if (purpose !== "CONTRACT") onChange("subcontractId", "");
            if (purpose !== "SERVICE") {
              onChange("grossAmount", "0,00");
              onChange("retentionsAmount", "0,00");
              onChange("netAmount", "0,00");
              onChange("measuredAmount", "0");
            }
          }}>
          <option value="SERVICE">Serviço avulso com pagamento próprio</option>
          <option value="CONTRACT">Medição de contrato de empreitada</option>
          <option value="CONTROL">OS de controle (sem valor próprio)</option>
        </select>
      </label>
      {error && (
        <div className={styles.loadError} role="alert">
          <span>{error}</span>
          <button
            type="button"
            className={appStyles.secondaryButton}
            onClick={() => setAttempt((value) => value + 1)}
          >
            Tentar novamente
          </button>
        </div>
      )}
      {form.purpose === "CONTRACT" && <label>
        Contrato*
        <select required
          value={form.subcontractId ?? ""}
          onChange={(e) => choose(e.target.value)}
          disabled={loading}
        >
          <option value="">
            {loading ? "Carregando contratos..." : "Selecione um contrato liberado"}
          </option>
          {rows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.code} · {row.title} · Versão {row.released_version}
            </option>
          ))}
        </select>
      </label>}
      <p className={styles.hint}>{hint}</p>
      {form.purpose === "CONTRACT" && !loading && !error && !rows.length && (
        <p className={styles.hint}>Nenhum contrato liberado disponível. Cadastre e libere a planilha na aba Empreitada antes de medir por contrato.</p>
      )}
      {form.subcontractId && (
        <>
          <p>
            O fornecedor é o empreiteiro do contrato e não pode ser alterado
            nesta medição. Após criar, informe as quantidades em Itens e inspeção;
            os totais serão calculados pelos preços contratados e exibidos nos
            detalhes. O líquido inclui a parcela futura de caução.
          </p>
          <p className={styles.hint}>
            Retenções identificadas, documento fiscal e parcelas são conferidos
            no lançamento do título no financeiro, após a aprovação da medição.
          </p>
        </>
      )}
    </fieldset>
  );
}
