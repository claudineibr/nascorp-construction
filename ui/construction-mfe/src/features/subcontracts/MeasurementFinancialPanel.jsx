import { useCallback, useEffect, useRef, useState } from "react";
import { Trash2 } from "lucide-react";
import { subcontractRequest } from "../../services/constructionApi";
import { money } from "../sharedPayables/SharedPayableLinkModal";
import {
  currencyDecimal,
  currencyFromNumber,
  formatCurrencyInput,
} from "../../utils/currencyInput";
import appStyles from "../../App.module.css";
import styles from "./SubcontractsPanel.module.css";

const deductionStatus = {
  DRAFT: "A descontar na aprovação",
  POSTED: "Descontado",
  REVERSED: "Estornado",
};

export function MeasurementFinancialPanel({ bridge, measurement, onRefresh }) {
  const [bills, setBills] = useState([]);
  const [deductions, setDeductions] = useState([]);
  const [chosenId, setChosenId] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  const load = useCallback(async () => {
    if (!measurement.subcontractId) return;
    try {
      const [credits, discounts] = await Promise.all([
        subcontractRequest({
          bridge,
          path: `/subcontracts/${measurement.subcontractId}/direct-bills`,
        }),
        subcontractRequest({
          bridge,
          path: `/measurements/${measurement.id}/direct-billing-deductions`,
        }),
      ]);
      if (alive.current) {
        setBills(credits.items);
        setDeductions(discounts.items);
        setError("");
      }
    } catch (failure) {
      if (alive.current) setError(failure.message);
    }
  }, [bridge, measurement.id, measurement.subcontractId]);
  useEffect(() => {
    alive.current = true;
    load();
    return () => {
      alive.current = false;
    };
  }, [load]);
  const execute = async (path, method, body, message) => {
    setBusy(true);
    try {
      await subcontractRequest({ bridge, path, method, body });
      if (!alive.current) return false;
      bridge.feedback?.success?.(message);
      await load();
      await onRefresh?.();
      return true;
    } catch (failure) {
      if (!alive.current) return false;
      if (bridge.feedback?.error) {
        bridge.feedback.error(failure.message);
      } else {
        setError(failure.message);
      }
      return false;
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  if (!measurement.subcontractId) return null;
  const editable = ["draft", "rejected"].includes(measurement.status);
  const available = bills.filter((bill) => Number(bill.remaining_amount) > 0);
  const showDirectBilling = deductions.length > 0 || (editable && available.length > 0);
  const chosen = available.find((bill) => bill.id === chosenId);
  const choose = (billId) => {
    setChosenId(billId);
    const bill = available.find((row) => row.id === billId);
    setAmount(bill ? String(bill.remaining_amount) : "");
  };
  return (
    <>
      {error && (
        <p role="alert" className={styles.alertText}>
          {error}
        </p>
      )}
      {showDirectBilling && (
        <section className={`${styles.panel} ${styles.block}`}>
          <div className={styles.blockHeader}>
            <div>
              <h4>Material faturado diretamente</h4>
              <p className={styles.hint}>
                Quando a construtora comprou material para o empreiteiro, o
                título desse material fica como crédito no contrato (aba
                Empreitada). Aqui você desconta desse crédito a parte usada nesta
                medição: o valor sai do bruto do título da medição. O desconto
                não pode passar do material dos itens medidos e só é efetivado
                na aprovação.
              </p>
            </div>
          </div>
          {deductions.length > 0 && (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Título de material</th>
                    <th>Valor descontado</th>
                    <th>Situação</th>
                    <th aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {deductions.map((row) => {
                    const bill = bills.find((item) => item.id === row.direct_bill_id);
                    return (
                      <tr key={row.id}>
                        <td>{bill?.snapshot?.document_number ?? "Título de material"}</td>
                        <td className={styles.numeric}>{money(row.amount)}</td>
                        <td>{deductionStatus[row.status] ?? row.status}</td>
                        <td>
                          {editable && row.status !== "POSTED" && (
                            <button
                              type="button"
                              className={styles.iconButton}
                              disabled={busy}
                              title="Remover desconto"
                              aria-label="Remover desconto"
                              onClick={() =>
                                execute(
                                  `/measurements/${measurement.id}/direct-billing-deductions/${row.id}`,
                                  "DELETE",
                                  null,
                                  "Desconto removido da medição.",
                                )
                              }
                            >
                              <Trash2 size={16} aria-hidden="true" />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {editable && available.length > 0 && (
            <form
              className={styles.fields}
              onSubmit={async (event) => {
                event.preventDefault();
                if (
                  await execute(
                    `/measurements/${measurement.id}/direct-billing-deductions`,
                    "PUT",
                    { direct_bill_id: chosenId, amount },
                    "Desconto de material vinculado à medição.",
                  )
                ) {
                  setChosenId("");
                  setAmount("");
                }
              }}
            >
              <label>
                Crédito de material do contrato*
                <select
                  className={styles.select}
                  required
                  value={chosenId}
                  onChange={(e) => choose(e.target.value)}
                >
                  <option value="">Escolha o título de material</option>
                  {available.map((bill) => (
                    <option key={bill.id} value={bill.id}>
                      Título {bill.snapshot?.document_number ?? "sem número"} ·
                      disponível {money(bill.remaining_amount)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Valor a descontar*
                <input
                  required
                  type="text"
                  inputMode="decimal"
                  placeholder="0,00"
                  value={amount ? currencyFromNumber(amount) : ""}
                  onChange={(e) => {
                    const masked = formatCurrencyInput(e.target.value);
                    setAmount(masked ? currencyDecimal(masked) : "");
                  }}
                />
              </label>
              <div className={styles.fieldAction}>
                <button
                  className={appStyles.primaryButton}
                  disabled={busy || !chosen || !(Number(amount) > 0)}
                >
                  Descontar nesta medição
                </button>
              </div>
            </form>
          )}
        </section>
      )}
      {measurement.status === "approved" && (
        <section className={`${styles.panel} ${styles.block}`}>
          <div className={styles.blockHeader}>
            <div>
              <h4>Estorno do contrato</h4>
              <p className={styles.hint}>
                {measurement.externalAccountsPayableShared
                  ? "A medição está numa DNF do contrato. Remova-a da DNF em DNFs da empreitada (Ver OS cobertas) antes de estornar; a DNF continua no ERP."
                  : measurement.externalAccountsPayableId
                  ? "Cancela o título vinculado à medição no ERP e devolve ao contrato a quantidade medida e o crédito de material descontado. A devolução só acontece depois que o ERP confirma o cancelamento; pagamentos precisam ser estornados no financeiro antes."
                  : "A medição ainda não tem título vinculado: o estorno devolve na hora ao contrato a quantidade medida e o crédito de material descontado, e a medição fica rejeitada."}
              </p>
            </div>
          </div>
          {measurement.reversalPending && (
            <p role="status" className={styles.guide}>
              Estorno solicitado. Quantidades e créditos continuam consumidos
              até o ERP confirmar o cancelamento.
            </p>
          )}
          <div className={styles.fields}>
            <label className={styles.wide}>
              Justificativa do estorno*
              <textarea
                minLength={15}
                maxLength={1000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              <span className={styles.hint}>Mínimo de 15 caracteres.</span>
            </label>
          </div>
          <div className={styles.actions}>
            <button
              type="button"
              className={`${appStyles.secondaryButton} ${appStyles.dangerButton}`}
              disabled={busy || reason.trim().length < 15 || measurement.externalAccountsPayableShared}
              title={measurement.externalAccountsPayableShared ? "Remova a medição da DNF do contrato antes de estornar" : undefined}
              onClick={() =>
                execute(
                  `/measurements/${measurement.id}/reverse-contract-consumption`,
                  "POST",
                  { reason },
                  measurement.externalAccountsPayableId ? "Estorno solicitado ao ERP." : "Estorno concluído: saldo devolvido ao contrato.",
                )
              }
            >
              {measurement.reversalPending
                ? "Tentar estorno novamente"
                : measurement.externalAccountsPayableId
                  ? "Solicitar estorno financeiro e contratual"
                  : "Estornar medição do contrato"}
            </button>
          </div>
        </section>
      )}
    </>
  );
}
