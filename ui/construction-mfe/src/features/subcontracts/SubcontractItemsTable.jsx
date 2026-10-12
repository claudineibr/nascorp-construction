import { Plus, Trash2 } from "lucide-react";
import appStyles from "../../App.module.css";
import { money } from "../sharedPayables/SharedPayableLinkModal";
import { currencyNumber, formatCurrencyInput } from "../../utils/currencyInput";
import styles from "./SubcontractsPanel.module.css";

const amount = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

export const itemTotal = (item) =>
  amount(item.quantity) *
  (currencyNumber(item.material_unit_price) +
    currencyNumber(item.labor_unit_price));

export const quantityLabel = (value) =>
  amount(value).toLocaleString("pt-BR", { maximumFractionDigits: 4 });

export function SubcontractItemsTable({
  items,
  services,
  servicesRestricted,
  disabled,
  onChange,
  onAdd,
  onRemove,
}) {
  const visible = items
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => item.active !== false);
  const total = visible.reduce((sum, { item }) => sum + itemTotal(item), 0);
  const chooseService = (index, serviceId) => {
    const service = services.find((row) => row.id === serviceId);
    const current = items[index];
    const followsService =
      !current.description.trim() ||
      current.description === current.service_template_name;
    onChange(index, {
      service_template_id: serviceId || null,
      service_template_name: service?.name ?? null,
      ...(service && followsService ? { description: service.name } : {}),
    });
  };
  return (
    <div className={styles.itemsBlock}>
      <div className={styles.itemsWrap}>
        <table className={`${styles.table} ${styles.itemsTable}`}>
          <thead>
            <tr>
              <th>{servicesRestricted ? "Serviço da obra*" : "Serviço"}</th>
              <th>Especificação*</th>
              <th>Unidade*</th>
              <th>Qtd. contratada*</th>
              <th>Material / un.*</th>
              <th>Mão de obra / un.*</th>
              <th>Total</th>
              <th>Medido · saldo</th>
              <th aria-label="Ações" />
            </tr>
          </thead>
          <tbody>
            {!visible.length && (
              <tr>
                <td colSpan={9} className={styles.empty}>
                  Nenhum item. Clique em Adicionar item.
                </td>
              </tr>
            )}
            {visible.map(({ item, index }) => {
              const measured = amount(item.consumed_quantity) > 0;
              const knownService = services.some(
                (row) => row.id === item.service_template_id,
              );
              return (
                <tr key={item.id ?? `new-${index}`}>
                  <td>
                    <select
                      aria-label={`Serviço do item ${index + 1}`}
                      value={item.service_template_id ?? ""}
                      required={servicesRestricted}
                      disabled={disabled || measured}
                      title={
                        measured
                          ? "Item já medido: o serviço não pode mudar."
                          : undefined
                      }
                      onChange={(e) => chooseService(index, e.target.value)}
                    >
                      <option value="">
                        {servicesRestricted
                          ? "Escolha o serviço"
                          : "Sem serviço do catálogo"}
                      </option>
                      {item.service_template_id && !knownService && (
                        <option value={item.service_template_id}>
                          {item.service_template_name ?? "Serviço fora da lista"}
                        </option>
                      )}
                      {services.map((service) => (
                        <option key={service.id} value={service.id}>
                          {service.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      aria-label={`Especificação do item ${index + 1}`}
                      required
                      maxLength={500}
                      value={item.description}
                      disabled={disabled}
                      onChange={(e) =>
                        onChange(index, { description: e.target.value })
                      }
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Unidade do item ${index + 1}`}
                      className={styles.narrow}
                      required
                      maxLength={20}
                      value={item.unit_of_measure}
                      disabled={disabled || measured}
                      title={
                        measured
                          ? "Item já medido: a unidade não pode mudar."
                          : undefined
                      }
                      onChange={(e) =>
                        onChange(index, { unit_of_measure: e.target.value })
                      }
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Quantidade contratada do item ${index + 1}`}
                      className={styles.number}
                      required
                      type="number"
                      min={item.consumed_quantity || "0.00000001"}
                      step="any"
                      value={item.quantity}
                      disabled={disabled}
                      onChange={(e) => onChange(index, { quantity: e.target.value })}
                    />
                  </td>
                  {[
                    ["material_unit_price", "Material por unidade"],
                    ["labor_unit_price", "Mão de obra por unidade"],
                  ].map(([key, text]) => (
                    <td key={key}>
                      <input
                        aria-label={`${text} do item ${index + 1}`}
                        className={styles.number}
                        required
                        type="text"
                        inputMode="decimal"
                        placeholder="0,00"
                        value={item[key]}
                        disabled={disabled}
                        onChange={(e) =>
                          onChange(index, {
                            [key]: formatCurrencyInput(e.target.value) || "0,00",
                          })
                        }
                      />
                    </td>
                  ))}
                  <td className={styles.numeric}>{money(itemTotal(item))}</td>
                  <td className={styles.numeric}>
                    {quantityLabel(item.consumed_quantity)} ·{" "}
                    {quantityLabel(
                      amount(item.quantity) - amount(item.consumed_quantity),
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className={styles.iconButton}
                      disabled={disabled || measured}
                      title={
                        measured
                          ? "Item já medido não pode ser removido."
                          : "Remover item"
                      }
                      aria-label={`Remover item ${index + 1}`}
                      onClick={() => onRemove(index)}
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={6}>Total do contrato</td>
              <td className={styles.numeric}>{money(total)}</td>
              <td colSpan={2} />
            </tr>
          </tfoot>
        </table>
      </div>
      {!disabled && (
        <button
          type="button"
          className={appStyles.secondaryButton}
          onClick={onAdd}
        >
          <Plus size={16} aria-hidden="true" />
          Adicionar item
        </button>
      )}
    </div>
  );
}
