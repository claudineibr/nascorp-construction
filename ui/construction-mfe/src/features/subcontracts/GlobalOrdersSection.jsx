import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { InfoTip } from "../../components/InfoTip";
import { subcontractRequest } from "../../services/constructionApi";
import { day } from "../sharedPayables/ZeroValueOrders";
import styles from "./SubcontractsPanel.module.css";

const statusLabels = {
  draft: "Rascunho",
  submitted: "Enviada",
  in_approval: "Em aprovação",
  approved: "Aprovada",
  rejected: "Rejeitada",
  paid: "Paga",
};

export function GlobalOrdersSection({ bridge, contract }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await subcontractRequest({ bridge, path: `/subcontracts/${contract.id}/orders` });
      setRows(result.items);
      setError("");
    } catch (failure) {
      setError(failure.message);
    } finally {
      setLoading(false);
    }
  }, [bridge, contract.id]);

  useEffect(() => {
    load();
  }, [load, contract.paid_amount]);

  return (
    <section className={styles.block}>
      <div className={styles.blockHeader}>
        <div>
          <h4>
          <button
            type="button"
            className={styles.accordionToggle}
            aria-expanded={expanded}
            aria-controls={`contract-orders-${contract.id}`}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
            OS do contrato{loading ? "" : ` (${rows.length})`}
          </button>
          <InfoTip floating label="Sobre as OS do contrato">
            Esta lista mostra as OS selecionadas ao lançar o título do contrato global.
            Para liberá-las para outro lançamento, cancele o título no ERP. Não há remoção manual de OS.
          </InfoTip></h4>
        </div>

      </div>
      {error && (
        <p role="alert" className={styles.alertText}>
          {error}
        </p>
      )}
      <div id={`contract-orders-${contract.id}`} hidden={!expanded}>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>OS</th>
              <th>Unidade</th>
              <th>Situação</th>
              <th>Vencimento</th>
              <th>Título</th>
            </tr>
          </thead>
          <tbody>
            {!rows.length && (
              <tr>
                <td colSpan={5} className={styles.empty}>
                  {loading ? "Carregando..." : "Nenhuma OS vinculada ao título deste contrato."}
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  OS {row.sequence_number ?? "-"}
                  <small className={styles.serviceDetail}>{row.code}</small>
                </td>
                <td>{row.unit_code || "-"}</td>
                <td>{statusLabels[row.status] ?? row.status}</td>
                <td>{day(row.due_date)}</td>
                <td>{row.external_accounts_payable_id ? "Vinculado" : "Sem título"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </div>
    </section>
  );
}
