import { useEffect, useState } from "react";
import { InfoTip } from "../../components/InfoTip";
import { subcontractRequest } from "../../services/constructionApi";
import {
  currencyDecimal,
  currencyFromNumber,
  formatCurrencyInput,
} from "../../utils/currencyInput";
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
    if (row) onChange("supplierPersonId", row.supplier_person_id);
  };
  const taxes = form.retentionDetails ?? [];
  const hint = form.subcontractId
    ? "Com contrato, o valor bruto sai das quantidades medidas na planilha contratada e a aprovação consome o saldo do contrato."
    : error
      ? "Os contratos de empreitada desta obra não foram carregados. Tente novamente antes de lançar a medição como avulsa."
      : rows.length
      ? "Medição avulsa: não consome saldo de contrato e usa o valor bruto informado abaixo. Deixe zerado quando uma DNF única pagar várias OS."
      : "Esta obra não tem contrato de empreitada liberado: a medição é avulsa e usa o valor bruto informado abaixo. Deixe zerado quando uma DNF única pagar várias OS.";
  return (
    <fieldset className={`${styles.panel} ${styles.contractBox}`}>
      <legend>
        Contrato de empreitada
        <InfoTip label="Quando vincular um contrato de empreitada">
          Vincule quando o serviço faz parte de um contrato liberado na aba
          Empreitada: o valor sai do preço contratado e a aprovação consome o
          saldo. Sem contrato, a medição é avulsa e usa o valor bruto informado.
        </InfoTip>
      </legend>
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
      <label>
        Contrato
        <select
          value={form.subcontractId ?? ""}
          onChange={(e) => choose(e.target.value)}
          disabled={loading || !rows.length}
        >
          <option value="">
            {loading ? "Carregando contratos..." : "Medição avulsa (sem contrato)"}
          </option>
          {rows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.code} · {row.title} · Versão {row.released_version}
            </option>
          ))}
        </select>
      </label>
      <p className={styles.hint}>{hint}</p>
      {form.subcontractId && (
        <>
          <p>
            Informe a competência e o documento fiscal. O bruto será calculado
            pelas quantidades dos itens contratados; o líquido inclui a parcela
            futura de caução.
          </p>
          <h4>Identificação dos tributos retidos</h4>
          {taxes.map((tax, index) => (
            <div className={styles.row} key={index}>
              <label>
                Tributo
                <select
                  value={tax.tax_type}
                  onChange={(e) =>
                    onChange(
                      "retentionDetails",
                      taxes.map((value, position) =>
                        position === index
                          ? { ...value, tax_type: e.target.value }
                          : value,
                      ),
                    )
                  }
                >
                  {["IRRF", "INSS", "ISS", "PIS", "COFINS", "CSLL"].map(
                    (kind) => (
                      <option key={kind} value={kind}>
                        {kind}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label>
                Valor retido*
                <input
                  required
                  type="text"
                  inputMode="decimal"
                  placeholder="0,00"
                  value={tax.tax_amount ? currencyFromNumber(tax.tax_amount) : ""}
                  onChange={(e) => {
                    const masked = formatCurrencyInput(e.target.value);
                    onChange(
                      "retentionDetails",
                      taxes.map((value, position) =>
                        position === index
                          ? { ...value, tax_amount: masked ? currencyDecimal(masked) : "" }
                          : value,
                      ),
                    );
                  }}
                />
              </label>
              <label>
                Vencimento do tributo
                <input
                  type="date"
                  value={tax.due_date ?? ""}
                  onChange={(e) =>
                    onChange(
                      "retentionDetails",
                      taxes.map((value, position) =>
                        position === index
                          ? { ...value, due_date: e.target.value || null }
                          : value,
                      ),
                    )
                  }
                />
              </label>
              <button
                type="button"
                className={appStyles.secondaryButton}
                onClick={() =>
                  onChange(
                    "retentionDetails",
                    taxes.filter((_, position) => position !== index),
                  )
                }
              >
                Remover retenção
              </button>
            </div>
          ))}
          <button
            type="button"
            className={appStyles.secondaryButton}
            onClick={() =>
              onChange("retentionDetails", [
                ...taxes,
                { tax_type: "IRRF", tax_amount: "", due_date: null },
              ])
            }
          >
            Adicionar retenção identificada
          </button>
        </>
      )}
    </fieldset>
  );
}
