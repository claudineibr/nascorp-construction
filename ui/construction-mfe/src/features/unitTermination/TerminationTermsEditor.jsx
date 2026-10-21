import { Plus, X } from "lucide-react"

import appStyles from "../../App.module.css"
import styles from "./unitTermination.module.css"
import { formatCurrencyInput } from "../../utils/currencyInput.js"

export const TERMINATION_DEDUCTION_TYPES = [
  { value: "PERCENT_OF_PAID", label: "Multa sobre o valor pago (%)" },
  { value: "PERCENT_OF_CONTRACT", label: "Percentual sobre o valor do contrato (%)" },
  { value: "FRUITION", label: "Taxa de fruição (% ao mês sobre o contrato)" },
  { value: "BROKERAGE", label: "Comissão de corretagem (R$)" },
  { value: "FIXED", label: "Valor fixo (R$)" },
]

const MONEY_TYPES = ["FIXED", "BROKERAGE"]

export const emptyTerminationTerms = () => ({ deductions: [], minimumRefundPercent: "", refundDeadlineDays: "" })

const percentInput = (value) => String(value ?? "").replace(/[^0-9,]/g, "").replace(/,(?=.*,)/g, "")

export function TerminationTermsEditor({ terms, onChange, hasSegregatedAssets = false, disabled = false }) {
  const current = terms ?? emptyTerminationTerms()
  const deductions = current.deductions ?? []
  const ceiling = hasSegregatedAssets ? 50 : 25

  const update = (changes) => onChange({ ...current, ...changes })
  const updateDeduction = (index, changes) =>
    update({ deductions: deductions.map((row, position) => (position === index ? { ...row, ...changes } : row)) })
  const removeDeduction = (index) => update({ deductions: deductions.filter((_, position) => position !== index) })
  const addDeduction = () => update({ deductions: [...deductions, { type: "PERCENT_OF_PAID", value: "", label: "" }] })

  return (
    <div className={styles.termsEditor}>
      <p className={appStyles.metricHint}>
        Deduções aplicadas sobre o que o comprador pagou quando a venda for distratada. A multa sobre o valor pago
        fica limitada a {ceiling}% ({hasSegregatedAssets ? "obra com" : "obra sem"} patrimônio de afetação).
      </p>
      {deductions.map((deduction, index) => {
        const isMoney = MONEY_TYPES.includes(deduction.type)
        return (
          <div key={index} className={styles.deductionRow}>
            <label className={appStyles.filterControl}>
              <span>Tipo de dedução*</span>
              <select
                value={deduction.type}
                disabled={disabled}
                onChange={(event) => updateDeduction(index, { type: event.target.value, value: "" })}
              >
                {TERMINATION_DEDUCTION_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={appStyles.filterControl}>
              <span>{isMoney ? "Valor*" : "Percentual*"}</span>
              <input
                type="text"
                inputMode="decimal"
                placeholder={isMoney ? "0,00" : "0"}
                value={deduction.value}
                disabled={disabled}
                onChange={(event) =>
                  updateDeduction(index, {
                    value: isMoney ? formatCurrencyInput(event.target.value) : percentInput(event.target.value),
                  })
                }
              />
            </label>
            <label className={appStyles.filterControl}>
              <span>Descrição</span>
              <input
                type="text"
                maxLength={120}
                value={deduction.label}
                disabled={disabled}
                placeholder="Opcional"
                onChange={(event) => updateDeduction(index, { label: event.target.value })}
              />
            </label>
            <button
              type="button"
              className={`${appStyles.iconButton} ${appStyles.dangerButton} ${styles.removeDeduction}`}
              title="Remover dedução"
              aria-label="Remover dedução"
              disabled={disabled}
              onClick={() => removeDeduction(index)}
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        )
      })}
      <div className={styles.termsFooter}>
        <button type="button" className={appStyles.secondaryButton} onClick={addDeduction} disabled={disabled}>
          <Plus size={16} aria-hidden="true" />
          Adicionar dedução
        </button>
      </div>
      <div className={appStyles.formGrid}>
        <label className={appStyles.filterControl}>
          <span>Mínimo a devolver (% do pago)</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="0"
            value={current.minimumRefundPercent}
            disabled={disabled}
            onChange={(event) => update({ minimumRefundPercent: percentInput(event.target.value) })}
          />
        </label>
        <label className={appStyles.filterControl}>
          <span>Prazo de devolução (dias)</span>
          <input
            type="text"
            inputMode="numeric"
            placeholder="0"
            value={current.refundDeadlineDays}
            disabled={disabled}
            onChange={(event) => update({ refundDeadlineDays: event.target.value.replace(/\D/g, "").slice(0, 4) })}
          />
        </label>
      </div>
    </div>
  )
}
