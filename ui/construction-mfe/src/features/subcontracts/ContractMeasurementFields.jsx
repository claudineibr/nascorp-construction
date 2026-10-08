import { useEffect, useState } from "react";
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
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    if (!projectId) return;
    subcontractRequest({ bridge, path: `/projects/${projectId}/subcontracts` })
      .then((result) => {
        if (active)
          setRows(result.items.filter((row) => row.status === "RELEASED"));
      })
      .catch((failure) => {
        if (active) setError(failure.message);
      });
    return () => {
      active = false;
    };
  }, [bridge, projectId]);
  const choose = (row) => {
    onChange("subcontractId", row?.id ?? "");
    if (row) onChange("supplierPersonId", row.supplier_person_id);
  };
  const taxes = form.retentionDetails ?? [];
  return (
    <fieldset className={styles.panel}>
      <legend>Contrato de empreitada opcional</legend>
      {error && <p role="alert">{error}</p>}
      <label>
        Buscar contrato liberado
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Código ou título"
        />
      </label>
      <div className={styles.actions}>
        <button
          type="button"
          className={appStyles.secondaryButton}
          onClick={() => choose(null)}
        >
          Medição avulsa
        </button>
        {rows
          .filter((row) =>
            `${row.code} ${row.title}`
              .toLowerCase()
              .includes(search.toLowerCase()),
          )
          .slice(0, 20)
          .map((row) => (
            <button
              type="button"
              key={row.id}
              className={
                form.subcontractId === row.id
                  ? appStyles.primaryButton
                  : appStyles.secondaryButton
              }
              onClick={() => choose(row)}
            >
              {row.code} · {row.title} · Versão {row.released_version}
            </button>
          ))}
      </div>
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
                Valor retido
                <input
                  required
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={tax.tax_amount}
                  onChange={(e) =>
                    onChange(
                      "retentionDetails",
                      taxes.map((value, position) =>
                        position === index
                          ? { ...value, tax_amount: e.target.value }
                          : value,
                      ),
                    )
                  }
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

export function ContractItemFields({ bridge, measurement, form, onChange }) {
  const [contract, setContract] = useState(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    if (!measurement.subcontractId) return;
    subcontractRequest({
      bridge,
      path: `/subcontracts/${measurement.subcontractId}${measurement.subcontractVersionId ? `?version_id=${measurement.subcontractVersionId}` : ""}`,
    })
      .then((value) => {
        if (active) setContract(value);
      })
      .catch((failure) => {
        if (active) setError(failure.message);
      });
    return () => {
      active = false;
    };
  }, [bridge, measurement.subcontractId, measurement.subcontractVersionId]);
  if (!measurement.subcontractId) return null;
  return (
    <fieldset className={styles.panel}>
      <legend>Item da planilha contratada</legend>
      {error && <p role="alert">{error}</p>}
      <label>
        Buscar serviço contratado
        <input value={search} onChange={(e) => setSearch(e.target.value)} />
      </label>
      <div className={styles.actions}>
        {(contract?.items ?? [])
          .filter(
            (item) =>
              item.active &&
              item.description.toLowerCase().includes(search.toLowerCase()),
          )
          .map((item) => (
            <button
              type="button"
              key={item.id}
              className={
                form.subcontractItemId === item.id
                  ? appStyles.primaryButton
                  : appStyles.secondaryButton
              }
              onClick={() => {
                onChange("subcontractItemId", item.id);
                onChange("description", item.description);
              }}
            >
              {item.description} · Saldo {item.remaining_quantity}{" "}
              {item.unit_of_measure} · Material {item.material_unit_price} · Mão
              de obra {item.labor_unit_price}
            </button>
          ))}
      </div>
      <label>
        Quantidade medida
        <input
          required
          type="number"
          min="0.00000001"
          step="0.00000001"
          value={form.quantity ?? ""}
          onChange={(e) => onChange("quantity", e.target.value)}
        />
      </label>
      <p>
        O valor do item será calculado pelo servidor usando a versão da planilha
        vinculada à medição.
      </p>
    </fieldset>
  );
}
