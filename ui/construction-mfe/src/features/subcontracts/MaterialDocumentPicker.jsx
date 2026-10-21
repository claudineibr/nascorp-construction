import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { subcontractRequest } from "../../services/constructionApi";
import { money } from "../sharedPayables/SharedPayableLinkModal";
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true);
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
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 400);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [bridge, projectId, search]);
  return (
    <div className={styles.picker}>
      <label className={styles.searchField}>
        <Search size={15} aria-hidden="true" />
        <input
          type="search"
          aria-label="Buscar título por número ou fornecedor"
          placeholder="Buscar por número ou fornecedor"
          disabled={disabled}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      {error && (
        <p role="alert" className={styles.alertText}>
          {error}
        </p>
      )}
      <div className={styles.pickerTable}>
        {loading ? (
          <p className={styles.empty}>Buscando títulos de material...</p>
        ) : !rows.length ? (
          <p className={styles.empty}>
            Nenhum título de material aprovado nesta obra
            {search ? " para essa busca" : ""}.
          </p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th aria-label="Escolher" />
                <th>Título</th>
                <th>Fornecedor</th>
                <th>Valor</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  className={selectedId === row.id ? styles.chosen : undefined}
                >
                  <td>
                    <input
                      type="radio"
                      name="material-document"
                      aria-label={`Escolher o título ${row.document_number ?? "sem número"}`}
                      checked={selectedId === row.id}
                      disabled={disabled}
                      onChange={() => onSelect(row)}
                    />
                  </td>
                  <td>{row.document_number ?? "Sem número"}</td>
                  <td>{row.supplier_name ?? "-"}</td>
                  <td className={styles.numeric}>{money(row.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
