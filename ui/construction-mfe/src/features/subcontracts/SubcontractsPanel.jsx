import { useCallback, useEffect, useRef, useState } from "react";
import { PersonPicker } from "../../components/PersonPicker";
import { ProductPicker } from "../../components/ProductPicker";
import { subcontractRequest } from "../../services/constructionApi";
import { MaterialDocumentPicker } from "./MaterialDocumentPicker";
import appStyles from "../../App.module.css";
import styles from "./SubcontractsPanel.module.css";

const statusLabels = {
  DRAFT: "Em preparação",
  RELEASED: "Liberado",
  CLOSED: "Encerrado",
  CANCELED: "Cancelado",
};
const emptyItem = () => ({
  description: "",
  unit_of_measure: "UN",
  quantity: "1",
  material_unit_price: "0",
  labor_unit_price: "0",
});
const emptyContract = () => ({
  code: "",
  title: "",
  supplier_person_id: "",
  valid_from: "",
  valid_to: "",
  retention_rate: "0",
  escrow_rate: "0",
  escrow_due_date: "",
  notes: "",
  items: [emptyItem()],
});

export function SubcontractsPanel({ bridge, projectId }) {
  return (
    <SubcontractsWorkspace
      key={`${bridge.companyContext?.companyId}:${projectId}:${bridge.token}`}
      bridge={bridge}
      projectId={projectId}
    />
  );
}

function SubcontractsWorkspace({ bridge, projectId }) {
  const [rows, setRows] = useState([]);
  const [draft, setDraft] = useState(null);
  const [bills, setBills] = useState([]);
  const [invoice, setInvoice] = useState({
    payable_document_id: "",
    amount: "",
  });
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const alive = useRef(true);
  const request = useCallback(
    (path, method, body) => subcontractRequest({ bridge, path, method, body }),
    [bridge],
  );
  const load = useCallback(async () => {
    try {
      const result = await request(`/projects/${projectId}/subcontracts`);
      if (alive.current) setRows(result.items);
    } catch (failure) {
      if (alive.current) setError(failure.message);
    }
  }, [request, projectId]);
  useEffect(() => {
    alive.current = true;
    load();
    return () => {
      alive.current = false;
    };
  }, [load]);
  const open = async (id) => {
    setBusy(true);
    try {
      const [contract, credits] = await Promise.all([
        request(`/subcontracts/${id}`),
        request(`/subcontracts/${id}/direct-bills`),
      ]);
      if (alive.current) {
        setDraft(contract);
        setBills(credits.items);
        setError("");
      }
    } catch (failure) {
      if (alive.current) setError(failure.message);
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const execute = async (path, method, body, message) => {
    setBusy(true);
    try {
      const result = await request(path, method, body);
      if (!alive.current) return;
      bridge.feedback?.success?.(message);
      setError("");
      if (result.items) setDraft(result);
      await load();
      return result;
    } catch (failure) {
      if (alive.current) setError(failure.message);
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const save = async (event) => {
    event.preventDefault();
    const body = Object.fromEntries(
      [
        "code",
        "title",
        "supplier_person_id",
        "valid_from",
        "valid_to",
        "retention_rate",
        "escrow_rate",
        "notes",
      ].map((key) => [key, draft[key]]),
    );
    body.escrow_due_date = draft.escrow_due_date || null;
    body.items = draft.items
      .filter((item) => item.active !== false)
      .map((item) =>
        Object.fromEntries(
          [
            "id",
            "product_id",
            "description",
            "unit_of_measure",
            "quantity",
            "material_unit_price",
            "labor_unit_price",
          ]
            .filter((key) => item[key] != null)
            .map((key) => [key, item[key]]),
        ),
      );
    await execute(
      draft.id
        ? `/subcontracts/${draft.id}`
        : `/projects/${projectId}/subcontracts`,
      draft.id ? "PUT" : "POST",
      body,
      "Planilha salva em preparação.",
    );
  };
  const patchItem = (index, patch) =>
    setDraft((current) => ({
      ...current,
      items: current.items.map((item, position) =>
        position === index ? { ...item, ...patch } : item,
      ),
    }));
  return (
    <section className={styles.panel}>
      <div className={styles.actions}>
        <button
          type="button"
          className={appStyles.primaryButton}
          onClick={() => {
            setDraft(emptyContract());
            setBills([]);
          }}
        >
          Novo contrato de empreitada
        </button>
        <button
          type="button"
          className={appStyles.secondaryButton}
          disabled={busy}
          onClick={load}
        >
          Atualizar contratos
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Contrato</th>
              <th>Situação</th>
              <th>Versão</th>
              <th>Vigência</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.code}</td>
                <td>{row.title}</td>
                <td>{statusLabels[row.status]}</td>
                <td>{row.released_version}</td>
                <td>
                  {row.valid_from} a {row.valid_to}
                </td>
                <td>
                  <button
                    type="button"
                    className={appStyles.secondaryButton}
                    disabled={busy}
                    onClick={() => open(row.id)}
                  >
                    Consultar planilha
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {draft && (
        <>
          <h3>
            {draft.id
              ? `Contrato ${draft.code} · ${statusLabels[draft.status]}`
              : "Nova planilha"}
          </h3>
          <form onSubmit={save}>
            <div className={styles.fields}>
              <label>
                Código
                <input
                  required
                  maxLength={50}
                  value={draft.code}
                  onChange={(e) => setDraft({ ...draft, code: e.target.value })}
                />
              </label>
              <label>
                Título
                <input
                  required
                  maxLength={255}
                  value={draft.title}
                  onChange={(e) =>
                    setDraft({ ...draft, title: e.target.value })
                  }
                />
              </label>
              <PersonPicker
                bridge={bridge}
                label="Empreiteiro"
                value={draft.supplier_person_id}
                onChange={(value) =>
                  setDraft({ ...draft, supplier_person_id: value })
                }
                businessRole="supplier"
                required
              />
              <label>
                Vigência inicial
                <input
                  required
                  type="date"
                  value={draft.valid_from}
                  onChange={(e) =>
                    setDraft({ ...draft, valid_from: e.target.value })
                  }
                />
              </label>
              <label>
                Vigência final
                <input
                  required
                  type="date"
                  value={draft.valid_to}
                  onChange={(e) =>
                    setDraft({ ...draft, valid_to: e.target.value })
                  }
                />
              </label>
              <label>
                Retenções tributárias (%)
                <input
                  required
                  type="number"
                  min="0"
                  max="99.9999"
                  step="0.0001"
                  value={draft.retention_rate}
                  onChange={(e) =>
                    setDraft({ ...draft, retention_rate: e.target.value })
                  }
                />
              </label>
              <label>
                Caução bruta (%)
                <input
                  required
                  type="number"
                  min="0"
                  max="99.9999"
                  step="0.0001"
                  value={draft.escrow_rate}
                  onChange={(e) =>
                    setDraft({ ...draft, escrow_rate: e.target.value })
                  }
                />
              </label>
              <label>
                Liberação prevista da caução
                <input
                  required={Number(draft.escrow_rate) > 0}
                  type="date"
                  value={draft.escrow_due_date ?? ""}
                  onChange={(e) =>
                    setDraft({ ...draft, escrow_due_date: e.target.value })
                  }
                />
              </label>
              <label>
                Observações
                <textarea
                  maxLength={4000}
                  value={draft.notes ?? ""}
                  onChange={(e) =>
                    setDraft({ ...draft, notes: e.target.value })
                  }
                />
              </label>
            </div>
            <h4>Itens da planilha</h4>
            {draft.items.map(
              (item, index) =>
                item.active !== false && (
                  <fieldset key={item.id ?? index}>
                    <legend>
                      Item {index + 1} · Consumido{" "}
                      {item.consumed_quantity ?? "0"} · Saldo{" "}
                      {item.remaining_quantity ?? item.quantity}
                    </legend>
                    <ProductPicker
                      bridge={bridge}
                      onSelect={(product) =>
                        patchItem(index, {
                          product_id: product.id,
                          description: product.description,
                          unit_of_measure:
                            product.defaultUnitOfMeasure ??
                            product.unitOfMeasure ??
                            item.unit_of_measure,
                        })
                      }
                    />
                    <div className={styles.row}>
                      {[
                        ["description", "Serviço / especificação"],
                        ["unit_of_measure", "Unidade"],
                        ["quantity", "Quantidade contratada"],
                        ["material_unit_price", "Material por unidade"],
                        ["labor_unit_price", "Mão de obra por unidade"],
                      ].map(([key, text]) => (
                        <label key={key}>
                          {text}
                          <input
                            required
                            value={item[key]}
                            onChange={(e) =>
                              patchItem(index, { [key]: e.target.value })
                            }
                          />
                        </label>
                      ))}
                    </div>
                    <button
                      type="button"
                      className={appStyles.secondaryButton}
                      disabled={Number(item.consumed_quantity ?? 0) > 0}
                      onClick={() => patchItem(index, { active: false })}
                    >
                      Remover item não medido
                    </button>
                  </fieldset>
                ),
            )}
            <div className={styles.actions}>
              <button
                type="button"
                className={appStyles.secondaryButton}
                onClick={() =>
                  setDraft({ ...draft, items: [...draft.items, emptyItem()] })
                }
              >
                Adicionar item
              </button>
              <button
                className={appStyles.primaryButton}
                disabled={busy || ["CLOSED", "CANCELED"].includes(draft.status)}
              >
                Salvar planilha
              </button>
            </div>
          </form>
          {draft.id && (
            <div className={styles.actions}>
              {draft.status === "DRAFT" && (
                <button
                  type="button"
                  className={appStyles.primaryButton}
                  disabled={busy}
                  onClick={() =>
                    execute(
                      `/subcontracts/${draft.id}/release`,
                      "POST",
                      null,
                      "Versão da planilha liberada.",
                    )
                  }
                >
                  Liberar versão
                </button>
              )}
              <label>
                Motivo do encerramento
                <input
                  value={reason}
                  minLength={15}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              <button
                type="button"
                className={appStyles.secondaryButton}
                disabled={busy || reason.trim().length < 15}
                onClick={() =>
                  execute(
                    `/subcontracts/${draft.id}/close`,
                    "POST",
                    { reason },
                    "Saldo contratual encerrado.",
                  )
                }
              >
                Encerrar saldo
              </button>
              <button
                type="button"
                className={appStyles.secondaryButton}
                disabled={busy || reason.trim().length < 15}
                onClick={() =>
                  execute(
                    `/subcontracts/${draft.id}/close?cancel=true`,
                    "POST",
                    { reason },
                    "Contrato cancelado.",
                  )
                }
              >
                Cancelar contrato sem consumo
              </button>
              {draft.status === "CLOSED" && (
                <button
                  type="button"
                  className={appStyles.secondaryButton}
                  disabled={busy}
                  onClick={() =>
                    execute(
                      `/subcontracts/${draft.id}/reopen`,
                      "POST",
                      null,
                      "Contrato reaberto.",
                    )
                  }
                >
                  Reabrir saldo
                </button>
              )}
            </div>
          )}
          {draft.id && (
            <>
              <h4>Material faturado diretamente</h4>
              <p>
                Informe o título de material já aprovado no ERP. A operação
                registra o crédito; não cria outra compra ou estoque.
              </p>
              <form
                className={styles.fields}
                onSubmit={async (event) => {
                  event.preventDefault();
                  const result = await execute(
                    `/subcontracts/${draft.id}/direct-bills`,
                    "POST",
                    invoice,
                    "Faturamento direto vinculado.",
                  );
                  if (result && alive.current) await open(draft.id);
                }}
              >
                <MaterialDocumentPicker
                  bridge={bridge}
                  projectId={projectId}
                  selectedId={invoice.payable_document_id}
                  disabled={busy}
                  onSelect={(row) =>
                    setInvoice({
                      payable_document_id: row.id,
                      amount: row.amount,
                    })
                  }
                />
                <label>
                  Valor faturado para a empreitada
                  <input
                    required
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={invoice.amount}
                    onChange={(e) =>
                      setInvoice({ ...invoice, amount: e.target.value })
                    }
                  />
                </label>
                <button
                  className={appStyles.primaryButton}
                  disabled={
                    busy ||
                    !invoice.payable_document_id ||
                    draft.status !== "RELEASED"
                  }
                >
                  Vincular título existente
                </button>
              </form>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Documento</th>
                      <th>Valor</th>
                      <th>Descontado</th>
                      <th>Crédito disponível</th>
                      <th>Ação</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bills.map((bill) => (
                      <tr key={bill.id}>
                        <td>{bill.snapshot.document_number}</td>
                        <td>{bill.amount}</td>
                        <td>{bill.deducted_amount}</td>
                        <td>{bill.remaining_amount}</td>
                        <td>
                          <button
                            type="button"
                            className={appStyles.secondaryButton}
                            disabled={busy || Number(bill.deducted_amount) > 0}
                            onClick={async () => {
                              await execute(
                                `/subcontracts/${draft.id}/direct-bills/${bill.id}`,
                                "DELETE",
                                null,
                                "Vínculo removido.",
                              );
                              if (alive.current) await open(draft.id);
                            }}
                          >
                            Desvincular crédito não usado
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
