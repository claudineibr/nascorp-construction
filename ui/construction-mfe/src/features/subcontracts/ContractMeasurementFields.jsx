import { useEffect, useState } from "react";
import { InfoTip } from "../../components/InfoTip";
import { subcontractRequest } from "../../services/constructionApi";
import { formatBusinessDate } from "../../utils/brazilDate.js";
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
          setRows(result.items.filter((row) => row.status === "RELEASED" && row.pricing_mode !== "GLOBAL"));
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
  const [pinned] = useState(() => ({ contractId: form.subcontractId, versionId: form.subcontractVersionId }));
  const [pinnedTerms, setPinnedTerms] = useState(null);
  useEffect(() => {
    let active = true;
    if (!pinned.contractId || !pinned.versionId) return;
    subcontractRequest({
      bridge,
      path: `/subcontracts/${pinned.contractId}?version_id=${pinned.versionId}`,
    })
      .then((sheet) => {
        if (active) setPinnedTerms({ valid_from: sheet.valid_from, valid_to: sheet.valid_to });
      })
      .catch((failure) => {
        if (active) setError(failure.message);
      });
    return () => {
      active = false;
    };
  }, [bridge, pinned]);
  const choose = (contractId) => {
    const row = rows.find((candidate) => candidate.id === contractId);
    onChange("subcontractId", row?.id ?? "");
    if (!row) onChange("competenceDate", "");
    onChange("purpose", row ? "CONTRACT" : "SERVICE");
    if (row) {
      onChange("supplierPersonId", row.supplier_person_id);
      if (!form.documentType?.trim()) onChange("documentType", "NFS-e");
    }
  };
  const usesPinnedTerms = Boolean(pinnedTerms) && form.subcontractId === pinned.contractId;
  const terms = usesPinnedTerms ? pinnedTerms : rows.find((row) => row.id === form.subcontractId);
  const hint = form.purpose === "CONTROL"
    ? "OS de controle físico: registre serviços e FVS sem valor próprio. A DNF pode pagar um conjunto de OS depois."
    : form.purpose === "CONTRACT"
      ? "Informe somente quantidades executadas. O contrato fornece empreiteiro, serviços e preços."
      : "Serviço avulso: crie a medição sem informar valores. Depois, em Itens e inspeção, informe o valor de cada serviço; a soma calcula o total da medição. Retenções podem ser informadas na edição, após incluir os serviços. Não consome saldo de contrato.";
  return (
    <fieldset className={`${styles.panel} ${styles.contractBox}`}>
      <legend>
        Finalidade da medição
        <InfoTip floating label="Sobre a finalidade da medição">
          Vincule quando o serviço faz parte de um contrato liberado na aba
          Empreitada: o valor sai do preço contratado e a aprovação consome o
          saldo. Sem contrato, escolha serviço avulso com pagamento próprio ou OS de controle sem valor próprio.
          <br /><br />{hint}
          {form.subcontractId && <>
            <br /><br />O fornecedor é o empreiteiro do contrato e não pode ser alterado
              nesta medição. Após criar, informe as quantidades em Itens e inspeção;
              os totais serão calculados pelos preços contratados e exibidos nos
              detalhes. O líquido inclui a parcela futura de caução.
            <br /><br />Retenções identificadas, documento fiscal e parcelas são conferidos
              no lançamento do título no financeiro, após a aprovação da medição.
          </>}
        </InfoTip>
      </legend>
      <label>
        Finalidade*
        <select value={form.purpose ?? (form.subcontractId ? "CONTRACT" : "SERVICE")}
          onChange={(event) => {
            const purpose = event.target.value;
            onChange("purpose", purpose);
            if (purpose !== "CONTRACT") {
              onChange("subcontractId", "");
              onChange("competenceDate", "");
            }
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
      {form.subcontractId && (
        <label>
          <span>Competência* <InfoTip floating label="Como informar a competência da medição">
            A competência precisa estar dentro da vigência do contrato ou da versão usada nesta medição.
          </InfoTip></span>
          <input
            type="date"
            required
            min={terms?.valid_from ?? undefined}
            max={terms?.valid_to ?? undefined}
            value={form.competenceDate ?? ""}
            onChange={(event) => onChange("competenceDate", event.target.value)}
          />
          {terms && (
            <span className={styles.hint}>
              {usesPinnedTerms ? "Vigência da versão usada nesta medição" : "Vigência do contrato"}:{" "}
              {formatBusinessDate(terms.valid_from)} a {formatBusinessDate(terms.valid_to)}.
            </span>
          )}
        </label>
      )}
      {form.purpose === "CONTRACT" && !loading && !error && !rows.length && (
        <p className={styles.hint}>Nenhum contrato liberado disponível. Cadastre e libere a planilha na aba Empreitada antes de medir por contrato.</p>
      )}
    </fieldset>
  );
}
