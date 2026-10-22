import { useEffect, useState } from "react";
import { ArrowDownToLine, Plus } from "lucide-react";
import { PersonPicker } from "../../components/PersonPicker";
import { subcontractRequest } from "../../services/constructionApi";
import { money } from "../sharedPayables/SharedPayableLinkModal";
import { quantityLabel } from "./SubcontractItemsTable";
import appStyles from "../../App.module.css";
import styles from "./SubcontractsPanel.module.css";

const number = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

export function ContractMeasureItems({
  bridge,
  measurement,
  items,
  people,
  serviceTemplates,
  saving,
  onCreateItems,
}) {
  const [contract, setContract] = useState(null);
  const [error, setError] = useState("");
  const [quantities, setQuantities] = useState({});
  const [inspectorPersonId, setInspectorPersonId] = useState("");
  const [search, setSearch] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setContract(null);
    setError("");
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
  }, [bridge, measurement.subcontractId, measurement.subcontractVersionId, attempt]);
  const serviceNames = Object.fromEntries(
    (serviceTemplates ?? []).map((service) => [service.id, service.name]),
  );
  const inMeasurement = items.reduce((totals, item) => {
    if (!item.subcontractItemId) return totals;
    totals[item.subcontractItemId] =
      (totals[item.subcontractItemId] ?? 0) + number(item.quantity);
    return totals;
  }, {});
  const rows = (contract?.items ?? [])
    .filter((item) => item.active !== false)
    .map((item) => {
      const serviceName =
        item.service_template_name ?? serviceNames[item.service_template_id] ?? null;
      const unitPrice =
        number(item.material_unit_price) + number(item.labor_unit_price);
      const already = inMeasurement[item.id] ?? 0;
      const available = Math.max(0, number(item.remaining_quantity) - already);
      const quantity = number(quantities[item.id]);
      return { item, serviceName, unitPrice, already, available, quantity };
    });
  const term = search.trim().toLowerCase();
  const visible = term
    ? rows.filter(({ item, serviceName }) =>
        `${serviceName ?? ""} ${item.description}`.toLowerCase().includes(term),
      )
    : rows;
  const filled = rows.filter((row) => row.quantity > 0);
  const over = filled.filter((row) => row.quantity > row.available);
  const total = filled.reduce((sum, row) => sum + row.quantity * row.unitPrice, 0);
  const submit = async (event) => {
    event.preventDefault();
    const created = await onCreateItems(
      filled.map(({ item, quantity }) => ({
        subcontractItemId: item.id,
        quantity: String(quantity),
        description: item.description,
        serviceTemplateId: item.service_template_id ?? "",
        inspectorPersonId,
      })),
    );
    if (created) setQuantities({});
  };
  return (
    <form className={`${appStyles.card} ${styles.panel} ${styles.measureGrid}`} onSubmit={submit}>
      <div className={styles.blockHeader}>
        <div>
          <h4>Itens do contrato {contract ? contract.code : ""}</h4>
          <p className={styles.hint}>
            Se quiser, escolha o inspetor responsável. Informe a quantidade
            medida nas linhas dos serviços executados e clique em Adicionar item
            medido, no fim do quadro. O valor sai do preço contratado, e cada
            linha vira um item da medição com a FVS do serviço.
          </p>
        </div>
      </div>
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
      <div className={styles.inspectorRow}>
        <PersonPicker
          bridge={bridge}
          label="Inspetor responsável"
          value={inspectorPersonId}
          onChange={setInspectorPersonId}
          knownPeople={people}
          emptyLabel="Buscar inspetor pelo nome"
        />
      </div>
      {rows.length > 8 && (
        <label className={styles.searchField}>
          <input
            type="search"
            aria-label="Buscar serviço do contrato"
            placeholder="Buscar serviço do contrato"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      )}
      <div className={styles.itemsWrap}>
        {!contract && !error ? (
          <p className={styles.empty}>Carregando itens do contrato...</p>
        ) : !visible.length ? (
          <p className={styles.empty}>Nenhum item do contrato encontrado.</p>
        ) : (
          <table className={`${styles.table} ${styles.itemsTable} ${styles.measureItemsTable}`}>
            <thead>
              <tr>
                <th>Serviço</th>
                <th>Un.</th>
                <th>Preço / un.</th>
                <th>Nesta medição</th>
                <th>Disponível</th>
                <th>Qtd. medida</th>
                <th>Valor</th>
              </tr>
            </thead>
            <tbody>
              {visible.map(({ item, serviceName, unitPrice, already, available, quantity }) => (
                <tr key={item.id} className={quantity > 0 ? styles.chosen : undefined}>
                  <td>
                    <strong className={styles.serviceName}>
                      {serviceName ?? item.description}
                    </strong>
                    {serviceName && serviceName !== item.description && (
                      <small className={styles.serviceDetail}>{item.description}</small>
                    )}
                  </td>
                  <td>{item.unit_of_measure}</td>
                  <td className={styles.numeric}>{money(unitPrice)}</td>
                  <td className={styles.numeric}>{quantityLabel(already)}</td>
                  <td className={styles.numeric}>{quantityLabel(available)}</td>
                  <td>
                    <div className={styles.quantityCell}>
                      <input
                        aria-label={`Quantidade medida de ${serviceName ?? item.description}`}
                        className={styles.number}
                        type="number"
                        min="0"
                        max={available}
                        step="any"
                        placeholder="0"
                        value={quantities[item.id] ?? ""}
                        disabled={saving || available <= 0 || already > 0}
                        title={already > 0 ? "Já está nesta medição; remova o item para alterar a quantidade" : undefined}
                        onChange={(e) =>
                          setQuantities({ ...quantities, [item.id]: e.target.value })
                        }
                      />
                      <button
                        type="button"
                        className={styles.iconButton}
                        disabled={saving || available <= 0 || already > 0}
                        title="Medir todo o disponível"
                        aria-label={`Medir todo o disponível de ${serviceName ?? item.description}`}
                        onClick={() =>
                          setQuantities({ ...quantities, [item.id]: String(available) })
                        }
                      >
                        <ArrowDownToLine size={16} aria-hidden="true" />
                      </button>
                    </div>
                  </td>
                  <td className={styles.numeric}>
                    {quantity > 0 ? money(quantity * unitPrice) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={6}>
                  {filled.length} serviço(s) com quantidade
                </td>
                <td className={styles.numeric}>{money(total)}</td>
              </tr>
            </tfoot>
          </table>
        )}
      </div>
      {over.length > 0 && (
        <p role="alert" className={styles.alertText}>
          A quantidade medida passa do disponível em {over.length} serviço(s).
        </p>
      )}
      <div className={`${appStyles.filtersFooter} ${styles.measureFooter}`}>
        {!filled.length && (
          <span id="contract-measure-hint" className={styles.hint}>
            Informe a quantidade medida em pelo menos um serviço.
          </span>
        )}
        <button
          type="submit"
          className={appStyles.primaryButton}
          disabled={saving || !filled.length || over.length > 0}
          aria-describedby={!filled.length ? "contract-measure-hint" : undefined}
        >
          <Plus size={16} aria-hidden="true" />
          {filled.length > 1
            ? `Adicionar ${filled.length} itens medidos`
            : "Adicionar item medido"}
        </button>
      </div>
    </form>
  );
}
