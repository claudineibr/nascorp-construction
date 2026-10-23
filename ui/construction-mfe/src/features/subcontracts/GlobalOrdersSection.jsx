import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { InfoTip } from "../../components/InfoTip";
import { subcontractRequest } from "../../services/constructionApi";
import { ZeroValueOrders, day } from "../sharedPayables/ZeroValueOrders";
import { Dialog } from "./DirectBillsSection";
import appStyles from "../../App.module.css";
import styles from "./SubcontractsPanel.module.css";

const statusLabels = {
  draft: "Rascunho",
  submitted: "Enviada",
  in_approval: "Em aprovação",
  approved: "Aprovada",
  rejected: "Rejeitada",
  paid: "Paga",
};

export function GlobalOrdersSection({ bridge, projectId, contract, canUpdate, onChanged }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);
  const released = contract.status === "RELEASED";

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
  }, [load]);

  const submit = async (path, measurementIds, message) => {
    setBusy(true);
    try {
      await subcontractRequest({ bridge, path, method: "POST", body: { measurement_ids: measurementIds } });
      bridge?.feedback?.success?.(message);
      await load();
      onChanged?.();
      return true;
    } catch (failure) {
      bridge?.feedback?.error?.(failure.message);
      return false;
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.block}>
      <div className={styles.blockHeader}>
        <div>
          <h4>OS do contrato
          <InfoTip floating label="Sobre as OS do contrato">
            OS sem valor do empreiteiro que este contrato paga, inclusive as
            importadas do sistema anterior. A OS mantém os serviços e a FVS;
            o valor fica no contrato e nas DNFs.
          </InfoTip></h4>
        </div>
        {canUpdate && (
          <button
            type="button"
            className={appStyles.secondaryButton}
            disabled={busy || !released}
            title={released ? undefined : "Disponível com o contrato liberado."}
            onClick={() => {
              setSelected(new Set());
              setAdding(true);
            }}
          >
            <Plus size={16} aria-hidden="true" />
            Vincular OS sem valor
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className={styles.alertText}>
          {error}
        </p>
      )}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>OS</th>
              <th>Unidade</th>
              <th>Situação</th>
              <th>Vencimento</th>
              <th>DNF</th>
              <th aria-label="Ações" />
            </tr>
          </thead>
          <tbody>
            {!rows.length && (
              <tr>
                <td colSpan={6} className={styles.empty}>
                  {loading ? "Carregando..." : "Nenhuma OS vinculada a este contrato."}
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
                <td>{row.external_accounts_payable_id ? "Vinculada" : "Sem DNF"}</td>
                <td>
                  {canUpdate && (
                    <button
                      type="button"
                      className={styles.iconButton}
                      disabled={busy || Boolean(row.external_accounts_payable_id)}
                      title={row.external_accounts_payable_id ? "Remova a OS da DNF antes de tirá-la do contrato" : `Tirar a OS ${row.code} do contrato`}
                      aria-label={`Tirar a OS ${row.code} do contrato`}
                      onClick={() => setRemoving(row)}
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {adding && (
        <Dialog title={`Vincular OS sem valor ao contrato ${contract.code}`} wide busy={busy} onClose={() => setAdding(false)}>
          <p className={styles.hint}>
            Aparecem as OS aprovadas, sem valor, sem título e sem contrato do empreiteiro deste contrato. OS em rascunho ou em aprovação entram depois de aprovadas.
          </p>
          <ZeroValueOrders
            bridge={bridge}
            projectId={projectId}
            supplierPersonId={contract.supplier_person_id}
            selected={selected}
            onSelectedChange={setSelected}
            disabled={busy}
          />
          <div className={appStyles.modalFooter}>
            <button type="button" className={appStyles.secondaryButton} disabled={busy} onClick={() => setAdding(false)}>
              Cancelar
            </button>
            <button
              type="button"
              className={appStyles.primaryButton}
              disabled={busy || !selected.size}
              onClick={async () => {
                if (await submit(`/subcontracts/${contract.id}/orders`, [...selected], `${selected.size} OS vinculada(s) ao contrato.`)) {
                  setAdding(false);
                }
              }}
            >
              {busy ? "Vinculando..." : `Vincular ${selected.size} OS ao contrato`}
            </button>
          </div>
        </Dialog>
      )}
      {removing && (
        <Dialog title="Tirar OS do contrato" busy={busy} onClose={() => setRemoving(null)}>
          <p>
            Tirar a OS {removing.sequence_number ?? "-"} ({removing.code}) do contrato {contract.code}? Ela volta a
            aparecer como OS sem valor e pode ir para outra DNF ou outro contrato.
          </p>
          <div className={appStyles.modalFooter}>
            <button type="button" className={appStyles.secondaryButton} disabled={busy} onClick={() => setRemoving(null)}>
              Cancelar
            </button>
            <button
              type="button"
              className={`${appStyles.secondaryButton} ${appStyles.dangerButton}`}
              disabled={busy}
              onClick={async () => {
                if (await submit(`/subcontracts/${contract.id}/orders/remove`, [removing.id], "OS retirada do contrato.")) {
                  setRemoving(null);
                }
              }}
            >
              {busy ? "Retirando..." : "Tirar do contrato"}
            </button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
