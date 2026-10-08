import { useCallback, useEffect, useRef, useState } from "react";
import { subcontractRequest } from "../../services/constructionApi";
import appStyles from "../../App.module.css";
import styles from "./SubcontractsPanel.module.css";

export function MeasurementFinancialPanel({ bridge, measurement, onRefresh }) {
  const [bills, setBills] = useState([]);
  const [deductions, setDeductions] = useState([]);
  const [chosen, setChosen] = useState(null);
  const [amount, setAmount] = useState("");
  const [search, setSearch] = useState("");
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
  const execute = async (path, method, body) => {
    setBusy(true);
    try {
      await subcontractRequest({ bridge, path, method, body });
      if (!alive.current) return;
      setError("");
      await load();
      await onRefresh?.();
    } catch (failure) {
      if (alive.current) setError(failure.message);
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  if (!measurement.subcontractId) return null;
  const editable = ["draft", "rejected"].includes(measurement.status);
  return (
    <section className={styles.panel}>
      <h4>Faturamento direto e estorno contratual</h4>
      <p>
        Bruto {measurement.grossAmount ?? "0"} · Material faturado diretamente{" "}
        {measurement.directBillingAmount ?? "0"} · Retenções{" "}
        {measurement.retentionsAmount ?? "0"} · Caução bruta{" "}
        {measurement.escrowAmount ?? "0"}
      </p>
      {error && <p role="alert">{error}</p>}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Desconto</th>
              <th>Valor</th>
              <th>Situação</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody>
            {deductions.map((row) => (
              <tr key={row.id}>
                <td>Material faturado diretamente</td>
                <td>{row.amount}</td>
                <td>
                  {
                    {
                      DRAFT: "Em preparação",
                      POSTED: "Consumido",
                      REVERSED: "Estornado",
                    }[row.status]
                  }
                </td>
                <td>
                  {editable && row.status !== "POSTED" && (
                    <button
                      type="button"
                      className={appStyles.secondaryButton}
                      disabled={busy}
                      onClick={() =>
                        execute(
                          `/measurements/${measurement.id}/direct-billing-deductions/${row.id}`,
                          "DELETE",
                          null,
                        )
                      }
                    >
                      Remover desconto
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editable && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            execute(
              `/measurements/${measurement.id}/direct-billing-deductions`,
              "PUT",
              { direct_bill_id: chosen?.id, amount },
            );
          }}
        >
          <label>
            Buscar crédito por documento
            <input value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <div className={styles.actions}>
            {bills
              .filter((bill) =>
                String(bill.snapshot.document_number ?? "").includes(search),
              )
              .map((bill) => (
                <button
                  type="button"
                  key={bill.id}
                  className={
                    chosen?.id === bill.id
                      ? appStyles.primaryButton
                      : appStyles.secondaryButton
                  }
                  onClick={() => {
                    setChosen(bill);
                    setAmount(bill.remaining_amount);
                  }}
                >
                  Documento {bill.snapshot.document_number} · Crédito{" "}
                  {bill.remaining_amount}
                </button>
              ))}
          </div>
          <label>
            Valor a descontar
            <input
              required
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
          <button
            className={appStyles.primaryButton}
            disabled={busy || !chosen}
          >
            Vincular desconto à medição
          </button>
        </form>
      )}
      {measurement.status === "approved" && (
        <>
          {measurement.reversalPending && (
            <p role="status">
              Estorno solicitado. Quantidades e créditos permanecem consumidos
              até o ERP confirmar o cancelamento; pagamentos precisam ser
              estornados no financeiro.
            </p>
          )}
          <label>
            Justificativa do estorno
            <input
              minLength={15}
              maxLength={1000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <button
            type="button"
            className={appStyles.secondaryButton}
            disabled={busy || reason.trim().length < 15}
            onClick={() =>
              execute(
                `/measurements/${measurement.id}/reverse-contract-consumption`,
                "POST",
                { reason },
              )
            }
          >
            {measurement.reversalPending
              ? "Tentar estorno novamente"
              : "Solicitar estorno financeiro e contratual"}
          </button>
        </>
      )}
    </section>
  );
}
