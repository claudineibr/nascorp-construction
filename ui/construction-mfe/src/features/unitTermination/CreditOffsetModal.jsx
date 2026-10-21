import { useEffect, useState } from "react"

import appStyles from "../../App.module.css"
import { brazilTodayISO } from "../../utils/brazilDate.js"
import { currencyFromNumber, formatBRL as money } from "../../utils/currencyInput.js"
import {
  listConstructionUnitBuyerCredits,
  offsetConstructionUnitInstallmentWithCredit,
} from "../../services/constructionApi.js"
import { installmentOutstanding } from "../unitInstallments.js"

export function CreditOffsetModal({ bridge, unit, installment, onClose, onDone }) {
  const outstanding = Math.round(installmentOutstanding(installment) * 100) / 100
  const amount = currencyFromNumber(outstanding)
  const [credits, setCredits] = useState(null)
  const [paidAt, setPaidAt] = useState(brazilTodayISO())
  const [observation, setObservation] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    listConstructionUnitBuyerCredits({ bridge, unitId: unit.id })
      .then((payload) => {
        if (active) setCredits(payload)
      })
      .catch((requestError) => {
        if (!active) return
        setCredits({ items: [], open_total: "0" })
        bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível consultar o saldo credor do comprador.")
      })
    return () => {
      active = false
    }
  }, [bridge, unit.id])

  const available = Number(credits?.open_total ?? 0)
  const insufficient = credits != null && available < outstanding

  const submit = async (event) => {
    event.preventDefault()
    if (!paidAt || outstanding <= 0) {
      bridge?.feedback?.warning?.("Informe a data do abatimento.")
      return
    }
    setLoading(true)
    try {
      await offsetConstructionUnitInstallmentWithCredit({
        bridge,
        unitId: unit.id,
        installmentNumber: installment.installmentNumber,
        receivableId: installment.receivableId,
        amount,
        paidAt,
        observation,
      })
      bridge?.feedback?.success?.("Parcela baixada com o saldo credor do comprador.")
      await onDone?.()
    } catch (requestError) {
      bridge?.feedback?.error?.(requestError?.message ?? "Não foi possível abater o saldo credor.")
    } finally {
      setLoading(false)
    }
  }

  const title = `Abater saldo credor na parcela ${installment.installmentNumber}`
  return (
    <div className={appStyles.modalOverlay} role="presentation" onClick={loading ? undefined : onClose}>
      <section className={appStyles.modalCard} role="dialog" aria-modal="true" aria-label={title}
        onClick={(event) => event.stopPropagation()}>
        <header className={appStyles.modalHeader}>
          <h3>{title}</h3>
          <button type="button" className={appStyles.closeButton} onClick={onClose} disabled={loading}>Fechar</button>
        </header>
        <form className={appStyles.modalBody} onSubmit={submit}>
          <p className={appStyles.metricHint}>
            {credits == null
              ? "Consultando o saldo credor do comprador..."
              : `Saldo credor disponível do comprador: ${money(available)}. O abatimento quita a parcela inteira, ` +
                "pelo saldo dela."}
          </p>
          {insufficient ? (
            <p className={appStyles.metricHint} role="alert">
              O saldo credor do comprador não cobre o saldo da parcela ({money(outstanding)}).
            </p>
          ) : null}
          <div className={appStyles.formGrid}>
            <label className={appStyles.filterControl}>
              <span>Valor</span>
              <input type="text" inputMode="decimal" value={amount} readOnly disabled
                title="O valor é o saldo da parcela" />
            </label>
            <label className={appStyles.filterControl}>
              <span>Data do abatimento*</span>
              <input type="date" value={paidAt} disabled={loading} onChange={(event) => setPaidAt(event.target.value)} />
            </label>
            <label className={`${appStyles.filterControl} ${appStyles.spanTwoColumns}`}>
              <span>Observação</span>
              <input type="text" maxLength={500} value={observation} disabled={loading}
                onChange={(event) => setObservation(event.target.value)} />
            </label>
          </div>
          <footer className={appStyles.modalFooter}>
            <button type="button" className={appStyles.secondaryButton} onClick={onClose} disabled={loading}>Cancelar</button>
            <button type="submit" className={appStyles.primaryButton}
              disabled={loading || credits == null || available <= 0 || insufficient || outstanding <= 0}>
              {loading ? "Abatendo..." : "Abater saldo credor"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}
