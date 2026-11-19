import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { FileText, RefreshCw } from "lucide-react";
import { InfoTip } from "../../components/InfoTip";
import { PersonPicker } from "../../components/PersonPicker";
import {
  listConstructionServiceTemplates,
  subcontractRequest,
} from "../../services/constructionApi";
import { money } from "../sharedPayables/SharedPayableLinkModal";
import { day } from "../sharedPayables/ZeroValueOrders";
import { Dialog, DirectBillsSection } from "./DirectBillsSection";
import { ContractPayablesSection } from "./ContractPayablesSection";
import { SharedPayablesCardTitle, SharedPayablesSection } from "../sharedPayables/SharedPayablesSection";
import { GlobalOrdersSection } from "./GlobalOrdersSection";
import { SubcontractItemsTable, itemTotal } from "./SubcontractItemsTable";
import { currencyDecimal, currencyFromNumber, currencyNumber, formatCurrencyInput } from "../../utils/currencyInput";
import appStyles from "../../App.module.css";
import styles from "./SubcontractsPanel.module.css";

const statusLabels = {
  DRAFT: "Em preparação",
  RELEASED: "Liberado",
  CLOSED: "Encerrado",
  CANCELED: "Cancelado",
};
const statusTone = {
  DRAFT: appStyles.statusdraft,
  RELEASED: appStyles.statusapproved,
  CLOSED: appStyles.statuscompleted,
  CANCELED: appStyles.statuscanceled,
};
const REASON_MIN = 15;
const emptyItem = () => ({
  service_template_id: null,
  service_template_name: null,
  description: "",
  unit_of_measure: "UN",
  quantity: "1",
  material_unit_price: "0,00",
  labor_unit_price: "0,00",
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
  pricing_mode: "ITEMIZED",
  global_amount: "",
  items: [emptyItem()],
});
const plain = (value) => String(Number(value ?? 0));
const toDraft = (contract) => ({
  ...contract,
  retention_rate: plain(contract.retention_rate),
  escrow_rate: plain(contract.escrow_rate),
  pricing_mode: contract.pricing_mode ?? "ITEMIZED",
  global_amount: contract.global_amount ? currencyFromNumber(contract.global_amount) : "",
  items: contract.items.map((item) => ({
    ...item,
    quantity: plain(item.quantity),
    material_unit_price: currencyFromNumber(item.material_unit_price),
    labor_unit_price: currencyFromNumber(item.labor_unit_price),
  })),
});

const sheetPayload = (draft) => {
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
    ].map((key) => [key,
      ["retention_rate", "escrow_rate"].includes(key)
        ? plain(draft[key]) : draft[key] ?? "",
    ]),
  );
  body.escrow_due_date = draft.escrow_due_date || null;
  body.pricing_mode = draft.pricing_mode ?? "ITEMIZED";
  body.global_amount = body.pricing_mode !== "ITEMIZED" ? currencyDecimal(draft.global_amount) : null;
  body.items = body.pricing_mode !== "ITEMIZED" ? [] : draft.items
    .filter((item) => item.active !== false)
    .map((item) => Object.fromEntries(
      [
        "id",
        "product_id",
        "service_template_id",
        "description",
        "unit_of_measure",
        "quantity",
        "material_unit_price",
        "labor_unit_price",
      ].filter((key) => item[key] != null).map((key) => [key,
        key.endsWith("_unit_price") ? currencyDecimal(item[key])
          : key === "quantity" ? plain(item[key]) : item[key],
      ]),
    ));
  return body;
};

function StatusPill({ status, version }) {
  return (
    <span className={`${appStyles.statusPill} ${statusTone[status] ?? ""}`}>
      {statusLabels[status] ?? status}
      {status !== "DRAFT" && version ? ` · versão ${version}` : ""}
    </span>
  );
}

function StatusGuide({ draft, blocker }) {
  if (!draft.id) {
    return (
      <p className={styles.guide}>
        {draft.pricing_mode === "ITEMIZED" ? "Preencha os dados e os itens" : "Preencha os dados e o valor total"} e clique em <strong>Salvar planilha</strong>.
        Depois, libere a versão para que as medições possam usar o contrato.
      </p>
    );
  }
  if (draft.status === "DRAFT") {
    return (
      <p className={styles.guide}>
        {blocker
          ? blocker
          : draft.released_version
            ? `Nova planilha em preparação. As medições ficam bloqueadas até liberar a versão ${draft.released_version + 1}.`
            : "Confira os itens e clique em Liberar versão para que as medições possam usar este contrato."}
      </p>
    );
  }
  if (draft.status === "RELEASED") return null;
  return (
    <p className={styles.guide}>
      Contrato {statusLabels[draft.status]?.toLowerCase()}
      {draft.closure_reason ? `: ${draft.closure_reason.replace(/\.+$/, "")}` : ""}. Somente
      consulta.
    </p>
  );
}

export function SubcontractsCardTitle() {
  return (
    <>
      Contratos de empreitada
      <InfoTip label="Quando usar contrato de empreitada">
        Use quando o empreiteiro tem uma planilha com quantidades e preços
        combinados. A medição vinculada calcula o valor pelo preço do contrato,
        consome o saldo na aprovação e aplica retenção, caução e desconto de
        material faturado direto. Serviço pontual, sem planilha, vira medição
        avulsa em Unidades &gt; Detalhes &gt; Medições.
      </InfoTip>
    </>
  );
}

export function SubcontractsPanel({ bridge, projectId, project, renderActions, RowActionsMenu }) {
  return (
    <SubcontractsWorkspace
      key={`${bridge.companyContext?.companyId}:${projectId}:${bridge.token}`}
      bridge={bridge}
      projectId={projectId}
      project={project}
      renderActions={renderActions}
      RowActionsMenu={RowActionsMenu}
    />
  );
}

function SubcontractsWorkspace({ bridge, projectId, project, renderActions, RowActionsMenu }) {
  const canCreate = Boolean(bridge?.canCreate?.("construction_measurements"));
  const canUpdate = Boolean(bridge?.canUpdate?.("construction_measurements"));
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState(null);
  const [savedSheet, setSavedSheet] = useState(null);
  const [payablesRevision, setPayablesRevision] = useState(0);
  const dirty = Boolean(draft && JSON.stringify(sheetPayload(draft)) !== savedSheet);
  const [bills, setBills] = useState([]);
  const [services, setServices] = useState({ items: [], restricted: false });
  const [closure, setClosure] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const alive = useRef(true);
  const request = useCallback(
    (path, method, body) => subcontractRequest({ bridge, path, method, body }),
    [bridge],
  );
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await request(`/projects/${projectId}/subcontracts`);
      if (alive.current) setRows(result.items);
    } catch (failure) {
      if (alive.current) setError(failure.message);
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [request, projectId]);
  useEffect(() => {
    alive.current = true;
    load();
    return () => {
      alive.current = false;
    };
  }, [load]);
  const editing = Boolean(draft);
  useEffect(() => {
    if (!editing) return;
    let active = true;
    listConstructionServiceTemplates({ bridge, projectId })
      .then((result) => {
        if (active) {
          setServices({
            items: result.items,
            restricted: result.restrictedToProject,
          });
        }
      })
      .catch((failure) => {
        if (active) setError(failure.message);
      });
    return () => {
      active = false;
    };
  }, [bridge, projectId, editing]);
  const applySavedContract = (contract) => {
    const next = toDraft(contract);
    setDraft(next);
    setSavedSheet(JSON.stringify(sheetPayload(next)));
  };
  const open = async (id) => {
    setBusy(true);
    try {
      const [contract, credits] = await Promise.all([
        request(`/subcontracts/${id}`),
        request(`/subcontracts/${id}/direct-bills`),
      ]);
      if (alive.current) {
        applySavedContract(contract);
        setBills(credits.items);
        setError("");
      }
    } catch (failure) {
      if (alive.current) setError(failure.message);
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const refreshContract = async () => {
    await Promise.all([open(draft.id), load()]);
  };
  const execute = async (path, method, body, message) => {
    setBusy(true);
    try {
      const result = await request(path, method, body);
      if (!alive.current) return null;
      bridge.feedback?.success?.(message);
      setError("");
      if (result?.items) {
        applySavedContract(result);
      }
      await load();
      return result ?? true;
    } catch (failure) {
      if (!alive.current) return null;
      if (bridge.feedback?.error) {
        bridge.feedback.error(failure.message);
      } else {
        setError(failure.message);
      }
      return null;
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const save = async (event) => {
    event.preventDefault();
    if (draft.id && !dirty) return;
    const body = sheetPayload(draft);
    await execute(
      draft.id
        ? `/subcontracts/${draft.id}`
        : `/projects/${projectId}/subcontracts`,
      draft.id ? "PUT" : "POST",
      body,
      draft.status === "RELEASED"
        ? "Planilha salva. Libere a nova versão para voltar a medir."
        : "Planilha salva em preparação.",
    );
  };
  const patch = (changes) => {
    setDraft((current) => ({ ...current, ...changes }));
  };
  const patchItem = (index, changes) => {
    setDraft((current) => ({
      ...current,
      items: current.items.map((item, position) =>
        position === index ? { ...item, ...changes } : item,
      ),
    }));
  };
  const removeItem = (index) => {
    setDraft((current) => ({
      ...current,
      items: current.items.flatMap((item, position) => {
        if (position !== index) return [item];
        return item.id ? [{ ...item, active: false }] : [];
      }),
    }));
  };
  const closeContract = async (event) => {
    event.preventDefault();
    const cancel = closure === "cancel";
    const result = await execute(
      `/subcontracts/${draft.id}/close${cancel ? "?cancel=true" : ""}`,
      "POST",
      { reason },
      cancel ? "Contrato cancelado." : "Saldo contratual encerrado.",
    );
    if (result) {
      setClosure(null);
      setReason("");
    }
  };
  const readOnly =
    ["CLOSED", "CANCELED"].includes(draft?.status) ||
    !(draft?.id ? canUpdate : canCreate);
  const measuredAny = (draft?.items ?? []).some(
    (item) => Number(item.consumed_quantity ?? 0) > 0,
  );
  const globalMode = draft?.pricing_mode === "GLOBAL";
  const measuredMode = draft?.pricing_mode === "MEASURED";
  const totalMode = globalMode || measuredMode;
  const contractTotal = totalMode
    ? currencyNumber(draft?.global_amount ?? "")
    : (draft?.items ?? [])
      .filter((item) => item.active !== false)
      .reduce((sum, item) => sum + itemTotal(item), 0);
  const releaseBlocker = dirty
    ? "Salve a planilha antes de liberar."
    : contractTotal <= 0
      ? totalMode
        ? "Informe o valor total do contrato global e salve antes de liberar."
        : "O total do contrato está em R$ 0,00. Informe o preço de material ou de mão de obra dos itens e salve antes de liberar."
      : "";
  const contractEditor = draft && (
        <section className={styles.editor}>
          <header className={styles.editorHeader}>
            <div className={styles.editorTitle}>
              <h3>
                {draft.id ? `${draft.code} · ${draft.title}` : "Novo contrato de empreitada"}
              </h3>
              {draft.id && (
                <StatusPill status={draft.status} version={draft.released_version} />
              )}
            </div>
            <div className={styles.actions}>
            {draft.id && canUpdate && draft.status === "DRAFT" && (
              <button type="button" className={appStyles.primaryButton}
                disabled={busy || Boolean(releaseBlocker)} title={releaseBlocker || undefined}
                onClick={() => execute(`/subcontracts/${draft.id}/release`, "POST", null, "Versão da planilha liberada.")}>
                Liberar versão
              </button>
            )}
            {draft.id && canUpdate && draft.status !== "CANCELED" && (
              <RowActionsMenu label="Ações do contrato" busy={busy} actions={[
                { key: "close", label: "Encerrar saldo", visible: draft.status === "RELEASED",
                  disabled: busy, onSelect: () => setClosure("close") },
                { key: "cancel", label: "Cancelar contrato", visible: ["DRAFT", "RELEASED"].includes(draft.status),
                  disabled: busy || measuredAny, danger: true,
                  title: measuredAny ? "Contrato com medição não pode ser cancelado: estorne as medições ou encerre o saldo." : undefined,
                  onSelect: () => setClosure("cancel") },
                { key: "reopen", label: "Reabrir saldo", visible: draft.status === "CLOSED",
                  disabled: busy || (globalMode && Number(draft.paid_amount) > 0),
                  title: globalMode && Number(draft.paid_amount) > 0 ? "Cancele o título no ERP para liberar as OS e o contrato global." : undefined,
                  onSelect: () => execute(`/subcontracts/${draft.id}/reopen`, "POST", null, "Contrato reaberto.") },
              ]} />
            )}
            <button
              type="button"
              className={appStyles.secondaryButton}
              disabled={busy}
              onClick={() => {
                setDraft(null);
                setSavedSheet(null);
              }}
            >
              Fechar
            </button>
            </div>
          </header>
          <StatusGuide draft={draft} blocker={releaseBlocker} />
          <form className={styles.form} onSubmit={save}>
            <details className={styles.block} open={!draft.id}>
              <summary className={styles.contractDetailsToggle}>Dados do contrato</summary>
              <fieldset className={styles.contractFields} disabled={readOnly}>
              <div className={`${styles.fields} ${styles.contractIdentity}`}>
                <label>
                  Código*
                  <input
                    required
                    maxLength={50}
                    value={draft.code}
                    onChange={(e) => patch({ code: e.target.value })}
                  />
                </label>
                <label>
                  Título*
                  <input
                    required
                    maxLength={255}
                    value={draft.title}
                    onChange={(e) => patch({ title: e.target.value })}
                  />
                </label>
                <label>
                  Modalidade*
                  <select
                    required
                    value={draft.pricing_mode ?? "ITEMIZED"}
                    disabled={readOnly || measuredAny || Boolean(draft.released_version)}
                    title={draft.released_version ? "A modalidade não muda depois de liberar o contrato." : undefined}
                    onChange={(e) => patch({ pricing_mode: e.target.value })}
                  >
                    <option value="ITEMIZED">Por planilha de serviços</option>
                    <option value="MEASURED">Valor global por serviços</option>
                    <option value="GLOBAL">Valor global (OS sem valor)</option>
                  </select>
                </label>

                <PersonPicker
                  bridge={bridge}
                  label="Empreiteiro"
                  value={draft.supplier_person_id}
                  onChange={(value) => patch({ supplier_person_id: value })}
                  businessRole="supplier"
                  required
                  disabled={readOnly || measuredAny}
                />
              </div>
              <div className={styles.fields}>
                <label>
                  Vigência inicial*
                  <input
                    required
                    type="date"
                    value={draft.valid_from}
                    onChange={(e) => patch({ valid_from: e.target.value })}
                  />
                </label>
                <label>
                  Vigência final*
                  <input
                    required
                    type="date"
                    value={draft.valid_to}
                    onChange={(e) => patch({ valid_to: e.target.value })}
                  />
                </label>
                {totalMode && (
                  <label>
                    Valor total do contrato*
                    <input
                      required
                      type="text"
                      inputMode="decimal"
                      placeholder="0,00"
                      value={draft.global_amount ?? ""}
                      onChange={(e) => patch({ global_amount: formatCurrencyInput(e.target.value) })}
                    />
                  </label>
                )}
                <label>
                  Retenções tributárias (%)*
                  <input
                    required
                    type="number"
                    min="0"
                    max="99.9999"
                    step="0.0001"
                    value={draft.retention_rate}
                    onChange={(e) => patch({ retention_rate: e.target.value })}
                  />
                </label>
                <label>
                  Caução bruta (%)*
                  <input
                    required
                    type="number"
                    min="0"
                    max="99.9999"
                    step="0.0001"
                    value={draft.escrow_rate}
                    onChange={(e) => patch({ escrow_rate: e.target.value })}
                  />
                </label>
                <label>
                  {Number(draft.escrow_rate) > 0
                    ? "Liberação prevista da caução*"
                    : "Liberação prevista da caução"}
                  <input
                    required={Number(draft.escrow_rate) > 0}
                    type="date"
                    value={draft.escrow_due_date ?? ""}
                    onChange={(e) => patch({ escrow_due_date: e.target.value })}
                  />
                </label>
                <label className={styles.wide}>
                  Observações
                  <textarea
                    maxLength={4000}
                    value={draft.notes ?? ""}
                    onChange={(e) => patch({ notes: e.target.value })}
                  />
                </label>
              </div>
              </fieldset>
            </details>
            {totalMode ? (
              <section className={styles.block}>
                <div className={styles.blockHeader}>
                  <h4>Resumo financeiro
                  <InfoTip floating label="Sobre o contrato por valor global">
                    {measuredMode
                      ? "Defina o valor total e libere o contrato. Em cada medição, escolha o serviço e sua FVS e informe o valor executado. Os serviços lançados reservam o saldo do contrato. Agrupe as medições aprovadas por etapa e período para gerar o título mensal."
                      : "Depois de liberar, vincule as OS sem valor do empreiteiro ao lançar o título em Pagamentos da empreitada."}
                  </InfoTip></h4>
                </div>
                {draft.id && (
                  <dl className={styles.financialSummary}>
                    <div><dt>Valor contratado</dt><dd>{money(draft.total_amount)}</dd></div>
                    <div><dt>{measuredMode ? "Serviços lançados" : "Vinculado em títulos"}</dt><dd>{money(measuredMode ? draft.committed_amount : draft.paid_amount)}</dd></div>
                    <div><dt>Saldo disponível</dt><dd>{money(draft.remaining_amount)}</dd></div>
                  </dl>
                )}
              </section>
            ) : <section className={styles.block}>
              <div className={styles.blockHeader}>
                <h4>Itens da planilha
                <InfoTip floating label="Como preencher os itens da planilha">
                  Cada item é um serviço contratado com quantidade e preço por
                  unidade, separado em material e mão de obra (use 0 quando não
                  houver).
                  {services.restricted
                    ? " Esta obra tem lista de serviços: escolha o serviço de cada item."
                    : ""}
                </InfoTip></h4>
              </div>
              <SubcontractItemsTable
                items={draft.items}
                services={services.items}
                servicesRestricted={services.restricted}
                disabled={readOnly}
                onChange={patchItem}
                onAdd={() => {
                  setDraft((current) => ({
                    ...current,
                    items: [...current.items, emptyItem()],
                  }));
                }}
                onRemove={removeItem}
              />
            </section>}
            {!readOnly && (!draft.id || dirty) && (
              <div className={styles.saveBar}>
                {draft.status === "RELEASED" && (
                  <span className={styles.hint}>
                    Salvar cria uma nova versão em preparação.
                  </span>
                )}
                <button className={appStyles.primaryButton} disabled={busy || (Boolean(draft.id) && !dirty)}>
                  Salvar planilha
                </button>
              </div>
            )}
          </form>
          {draft.id && globalMode && (
            <GlobalOrdersSection
              bridge={bridge}
              contract={draft}
            />
          )}
          {draft.id && !totalMode && (
            <DirectBillsSection
              bridge={bridge}
              projectId={projectId}
              contract={draft}
              bills={bills}
              busy={busy}
              canUpdate={canUpdate}
              onLink={async (invoice) => {
                const result = await execute(
                  `/subcontracts/${draft.id}/direct-bills`,
                  "POST",
                  invoice,
                  "Título de material vinculado ao contrato.",
                );
                if (result && alive.current) await open(draft.id);
                return Boolean(result);
              }}
              onUnlink={async (bill) => {
                const result = await execute(
                  `/subcontracts/${draft.id}/direct-bills/${bill.id}`,
                  "DELETE",
                  null,
                  "Título de material desvinculado.",
                );
                if (result && alive.current) await open(draft.id);
                return Boolean(result);
              }}
            />
          )}
          {draft.id && (
      <section className={styles.block}>
        <SharedPayablesSection
          bridge={bridge}
          projectId={projectId}
          project={project}
          key={draft.id}
          subcontractId={draft.id}
          reloadKey={payablesRevision}
          onChanged={refreshContract}
          contractActions={draft?.id ? <ContractPayablesSection key={draft.id}
            bridge={bridge} projectId={projectId} contract={draft} canUpdate={canUpdate} dirty={dirty}
            onChanged={async () => {
              setPayablesRevision((value) => value + 1);
              await refreshContract();
            }}
          /> : null}
          renderActions={(actions) => <div className={styles.blockHeader}>
            <div>
              <h4><SharedPayablesCardTitle /></h4>
            </div>
            <div className={styles.actions}>{actions}</div>
          </div>}
        />
      </section>
          )}
        </section>
  );
  return (
    <section className={styles.panel}>
      {renderActions(<>
        {canCreate && (
          <button
            type="button"
            className={appStyles.primaryButton}
            disabled={busy}
            onClick={() => {
              setDraft(emptyContract());
              setBills([]);
              setSavedSheet(null);
              setError("");
            }}
          >
            Novo contrato de empreitada
          </button>
        )}
        <button
          type="button"
          className={styles.iconButton}
          disabled={busy || loading}
          onClick={load}
          title="Atualizar contratos"
          aria-label="Atualizar contratos"
        >
          <RefreshCw size={16} aria-hidden="true" />
        </button>
      </>)}
      {error && (
        <p role="alert" className={styles.alertText}>
          {error}
        </p>
      )}
      {draft && !draft.id && contractEditor}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Contrato</th>
              <th>Situação</th>
              <th>Vigência</th>
              <th>Valor contratado</th>
              <th>Saldo</th>
              <th aria-label="Ações" />
            </tr>
          </thead>
          <tbody>
            {!rows.length && (
              <tr>
                <td colSpan={7} className={styles.empty}>
                  {loading
                    ? "Carregando..."
                    : "Nenhum contrato de empreitada nesta obra."}
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <Fragment key={row.id}>
              <tr
                className={`${styles.contractRow} ${draft?.id === row.id ? styles.chosen : ""}`}
              >
                <td data-label="Código">{row.code}</td>
                <td data-label="Contrato">{row.title}</td>
                <td data-label="Situação">
                  <StatusPill status={row.status} version={row.released_version} />
                </td>
                <td data-label="Vigência">
                  {day(row.valid_from)} a {day(row.valid_to)}
                </td>
                <td data-label="Valor contratado" className={styles.numeric}>{money(row.total_amount)}</td>
                <td data-label="Saldo" className={styles.numeric}>{money(row.remaining_amount)}</td>
                <td>
                  <button
                    type="button"
                    className={styles.iconButton}
                    disabled={busy}
                    onClick={() => open(row.id)}
                    aria-expanded={draft?.id === row.id}
                    aria-controls={`contract-${row.id}`}
                    title="Abrir contrato"
                    aria-label={`Abrir o contrato ${row.code}`}
                  >
                    <FileText size={16} aria-hidden="true" />
                  </button>
                </td>
              </tr>
              {draft?.id === row.id && <tr id={`contract-${row.id}`} className={styles.expandedRow}>
                <td colSpan={7} className={styles.expandedCell}>{contractEditor}</td>
              </tr>}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <details className={styles.block}>
        <summary className={styles.contractDetailsToggle}>OS sem contrato</summary>
        <SharedPayablesSection bridge={bridge} projectId={projectId} project={project} withoutContract
          renderActions={(actions) => <div className={styles.blockHeader}>
            <h4>Pagamentos de OS sem contrato</h4><div className={styles.actions}>{actions}</div>
          </div>} />
      </details>
      {closure && draft && (
        <Dialog
          title={closure === "cancel" ? "Cancelar contrato" : "Encerrar saldo"}
          busy={busy}
          onClose={() => setClosure(null)}
        >
          <form className={styles.modalForm} onSubmit={closeContract}>
            <p>
              {closure === "cancel"
                ? `Cancelar o contrato ${draft.code}? Ele deixa de aceitar medições e não pode ser reaberto.`
                : `Encerrar o saldo do contrato ${draft.code}? As medições já aprovadas ficam como estão e o saldo restante deixa de poder ser medido. Dá para reabrir depois.`}
            </p>
            <div className={styles.fields}>
              <label className={styles.wide}>
                Motivo*
                <textarea
                  required
                  minLength={REASON_MIN}
                  maxLength={1000}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
                <span className={styles.hint}>
                  Mínimo de {REASON_MIN} caracteres.
                </span>
              </label>
            </div>
            <div className={appStyles.modalFooter}>
              <button
                type="button"
                className={appStyles.secondaryButton}
                disabled={busy}
                onClick={() => setClosure(null)}
              >
                Voltar
              </button>
              <button
                className={`${appStyles.secondaryButton} ${appStyles.dangerButton}`}
                disabled={busy || reason.trim().length < REASON_MIN}
              >
                {closure === "cancel" ? "Cancelar contrato" : "Encerrar saldo"}
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </section>
  );
}
