import { useState } from "react"

import appStyles from "../../App.module.css"
import styles from "./unitTermination.module.css"
import { formatBRL as money, formatCurrencyInput } from "../../utils/currencyInput.js"
import { brazilTodayISO, formatBusinessDate as formatDate } from "../../utils/brazilDate.js"
import { previewConstructionUnitTermination, terminateConstructionUnit } from "../../services/constructionApi.js"

export function UnitTerminationModal({ bridge, unit, onClose, onDone, requestConfirm }) {
  const [form, setForm] = useState({
    terminationDate: brazilTodayISO(),
    reason: "",
    notes: "",
    additionalRefund: "",
    destination: "credit",
    refundFirstDueDate: "",
    refundInstallments: "1",
  })
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)

  const change = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }))
    if (["terminationDate", "additionalRefund"].includes(field)) setPreview(null)
  }

  const calculate = async (event) => {
    event?.preventDefault?.()
    if (!form.terminationDate || !form.reason.trim()) {
      bridge?.feedback?.warning?.("Informe a data e o motivo do distrato.")
      return
    }
    setLoading(true)
    try {
      const result = await previewConstructionUnitTermination({ bridge, unitId: unit.id, terminationData: form })
      setPreview(result)
      if (result?.suggested_refund_due_date && !form.refundFirstDueDate) {
        setForm((current) => ({ ...current, refundFirstDueDate: result.suggested_refund_due_date }))
      }
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível calcular o distrato.")
    } finally {
      setLoading(false)
    }
  }

  const apply = async () => {
    setLoading(true)
    try {
      await terminateConstructionUnit({
        bridge,
        unitId: unit.id,
        terminationData: { ...form, previewVersion: preview?.version },
      })
      bridge?.feedback?.success?.(
        form.destination === "refund"
          ? "Distrato registrado. A restituição foi lançada no Contas a Pagar."
          : "Distrato registrado. O valor a devolver ficou como saldo credor do comprador.",
      )
      await onDone?.()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível registrar o distrato.")
      setPreview(null)
    } finally {
      setLoading(false)
    }
  }

  const askConfirmation = () => {
    if (form.destination === "refund" && (!form.refundFirstDueDate || Number(form.refundInstallments || 0) < 1)) {
      bridge?.feedback?.warning?.("Informe o 1º vencimento e as parcelas da restituição.")
      return
    }
    requestConfirm({
      title: `Distratar a unidade ${unit.code}`,
      message:
        `As parcelas em aberto (${money(preview.open_amount)}) serão baixadas por distrato, o contrato será ` +
        `cancelado e a unidade volta para Disponível. Valor a devolver ao comprador: ${money(preview.refund_amount)}.`,
      confirmLabel: "Distratar",
      run: apply,
    })
  }

  const blockers = preview?.blockers ?? []
  const installments = preview?.installments ?? []
  const canceled = installments.filter((row) => row.action === "CANCEL").length
  const reduced = installments.filter((row) => row.action === "REDUCE").length

  return (
    <div className={appStyles.modalOverlay} role="presentation" onClick={loading ? undefined : onClose}>
      <section
        className={`${appStyles.modalCard} ${appStyles.modalCardWide}`}
        role="dialog"
        aria-modal="true"
        aria-label={`Distratar a unidade ${unit.code}`}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={appStyles.modalHeader}>
          <h3>Distratar a unidade {unit.code}</h3>
          <button type="button" className={appStyles.closeButton} onClick={onClose} disabled={loading}>
            Fechar
          </button>
        </header>
        <form id="unit-termination-form" className={appStyles.modalBody} onSubmit={calculate}>
          <div className={appStyles.formGrid}>
            <label className={appStyles.filterControl}>
              <span>Data do distrato*</span>
              <input
                type="date"
                required
                value={form.terminationDate}
                disabled={loading}
                onChange={(event) => change("terminationDate", event.target.value)}
              />
            </label>
            <label className={`${appStyles.filterControl} ${appStyles.spanTwoColumns}`}>
              <span>Motivo*</span>
              <input
                type="text"
                required
                maxLength={500}
                value={form.reason}
                disabled={loading}
                onChange={(event) => change("reason", event.target.value)}
              />
            </label>
            <label className={`${appStyles.filterControl} ${appStyles.spanTwoColumns}`}>
              <span>Observação</span>
              <textarea
                className={appStyles.textarea}
                maxLength={2000}
                value={form.notes}
                disabled={loading}
                onChange={(event) => change("notes", event.target.value)}
              />
            </label>
            <label className={appStyles.filterControl}>
              <span>Reembolso adicional</span>
              <input
                type="text"
                inputMode="decimal"
                placeholder="0,00"
                value={form.additionalRefund}
                disabled={loading}
                onChange={(event) => change("additionalRefund", formatCurrencyInput(event.target.value))}
              />
            </label>
          </div>

          {preview ? (
            <>
              <div className={appStyles.card}>
                <div className={appStyles.scopeMeta}>
                  <strong>Demonstrativo do distrato</strong>
                  <span className={appStyles.metricHint}>
                    Comprador: {preview.person_name ?? "-"}. Deduções pelas regras de rescisão da venda.
                  </span>
                </div>
                <table className={styles.statement}>
                  <tbody>
                    <tr>
                      <td>Valor do contrato</td>
                      <td>{money(preview.contract_amount)}</td>
                    </tr>
                    <tr>
                      <td>Recebido do comprador até {formatDate(preview.termination_date)}</td>
                      <td>{money(preview.paid_amount)}</td>
                    </tr>
                    {(preview.deductions ?? []).map((line, index) => (
                      <tr key={`${line.type}-${index}`}>
                        <td>
                          (-) {line.label}
                          {line.months != null ? ` — ${line.months} mês(es)` : ""}
                        </td>
                        <td>{money(-Number(line.amount))}</td>
                      </tr>
                    ))}
                    {preview.minimum_applied ? (
                      <tr className={styles.statementMuted}>
                        <td>Mínimo a devolver aplicado</td>
                        <td>{money(preview.minimum_refund)}</td>
                      </tr>
                    ) : null}
                    {Number(preview.additional_refund) > 0 ? (
                      <tr>
                        <td>(+) Reembolso adicional</td>
                        <td>{money(preview.additional_refund)}</td>
                      </tr>
                    ) : null}
                    <tr className={styles.statementTotal}>
                      <td>Valor a devolver</td>
                      <td>{money(preview.refund_amount)}</td>
                    </tr>
                    <tr className={styles.statementMuted}>
                      <td>Parcelas em aberto a baixar por distrato ({canceled} baixada(s), {reduced} reduzida(s))</td>
                      <td>{money(preview.open_amount)}</td>
                    </tr>
                    {Number(preview.broker_signal_amount) > 0 ? (
                      <tr className={styles.statementMuted}>
                        <td>Sinal pago ao corretor (não entra no valor a devolver)</td>
                        <td>{money(preview.broker_signal_amount)}</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>

              {blockers.length ? (
                <div className={styles.blockers} role="alert">
                  <strong>O distrato não pode ser aplicado ainda:</strong>
                  <ul>
                    {blockers.map((blocker) => (
                      <li key={blocker.code}>
                        {blocker.message}
                        {blocker.code === "ACTIVE_BANK_SLIP" ? (
                          <span className={appStyles.metricHint}>
                            {" "}
                            Peça a baixa pela aba Parcelas da unidade (boletos{" "}
                            {(blocker.details ?? []).map((slip) => slip.our_number).join(", ")}).
                          </span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className={appStyles.card}>
                  <div className={appStyles.scopeMeta}>
                    <strong>Destino do valor a devolver</strong>
                  </div>
                  <div className={styles.destination} role="radiogroup" aria-label="Destino do valor a devolver">
                    <label>
                      <input
                        type="radio"
                        name="termination-destination"
                        checked={form.destination === "credit"}
                        disabled={loading}
                        onChange={() => change("destination", "credit")}
                      />
                      Manter como saldo credor
                    </label>
                    <label>
                      <input
                        type="radio"
                        name="termination-destination"
                        checked={form.destination === "refund"}
                        disabled={loading || Number(preview.refund_amount) <= 0}
                        onChange={() => change("destination", "refund")}
                      />
                      Gerar restituição agora
                    </label>
                  </div>
                  {form.destination === "refund" ? (
                    <div className={appStyles.formGrid}>
                      <label className={appStyles.filterControl}>
                        <span>1º vencimento*</span>
                        <input
                          type="date"
                          value={form.refundFirstDueDate}
                          disabled={loading}
                          onChange={(event) => change("refundFirstDueDate", event.target.value)}
                        />
                      </label>
                      <label className={appStyles.filterControl}>
                        <span>Parcelas*</span>
                        <input
                          type="text"
                          inputMode="numeric"
                          value={form.refundInstallments}
                          disabled={loading}
                          onChange={(event) =>
                            change("refundInstallments", event.target.value.replace(/\D/g, "").slice(0, 3))
                          }
                        />
                      </label>
                    </div>
                  ) : (
                    <p className={appStyles.metricHint}>
                      O valor fica como saldo credor do comprador, para restituir depois em Obras &gt; Saldos
                      Credores ou abater numa nova compra.
                    </p>
                  )}
                </div>
              )}
            </>
          ) : null}
        </form>
        <footer className={appStyles.modalFooter}>
          <button type="button" className={appStyles.secondaryButton} onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          {preview && !blockers.length ? (
            <button
              type="button"
              className={`${appStyles.secondaryButton} ${appStyles.dangerButton}`}
              onClick={askConfirmation}
              disabled={loading}
            >
              Distratar
            </button>
          ) : (
            <button type="submit" form="unit-termination-form" className={appStyles.primaryButton} disabled={loading}>
              {loading ? "Calculando..." : "Calcular demonstrativo"}
            </button>
          )}
        </footer>
      </section>
    </div>
  )
}
