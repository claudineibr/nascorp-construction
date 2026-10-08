import { useEffect, useState } from "react";
import { subcontractRequest } from "../../services/constructionApi";
import appStyles from "../../App.module.css";
import styles from "./SubcontractsPanel.module.css";

export function MaterialDocumentPicker({
  bridge,
  projectId,
  onSelect,
  selectedId,
  disabled,
}) {
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const timer = setTimeout(
      () =>
        subcontractRequest({
          bridge,
          path: `/projects/${projectId}/direct-billing-documents?search=${encodeURIComponent(search)}`,
        })
          .then((result) => {
            if (active) {
              setRows(result.items);
              setError("");
            }
          })
          .catch((failure) => {
            if (active) setError(failure.message);
          }),
      400,
    );
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [bridge, projectId, search]);
  return (
    <fieldset className={styles.panel}>
      <legend>Título de material aprovado da obra</legend>
      <label>
        Buscar número ou fornecedor
        <input
          disabled={disabled}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <div className={styles.actions}>
        {rows.map((row) => (
          <button
            type="button"
            key={row.id}
            disabled={disabled}
            className={
              selectedId === row.id
                ? appStyles.primaryButton
                : appStyles.secondaryButton
            }
            onClick={() => onSelect(row)}
          >
            {row.document_number ?? "Sem número"} · {row.supplier_name} ·{" "}
            {Number(row.amount).toLocaleString("pt-BR", {
              style: "currency",
              currency: "BRL",
            })}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
