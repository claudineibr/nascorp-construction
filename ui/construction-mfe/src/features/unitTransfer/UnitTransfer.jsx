import { useCallback, useEffect, useRef, useState } from "react"

import appStyles from "../../App.module.css"
import dialogStyles from "../unitTermination/unitTermination.module.css"
import styles from "./unitTransfer.module.css"
import { UnitBankSlipDialogFrame as DialogFrame } from "../UnitBankSlipsDialog.jsx"
import {
  applyUnitTransfer, listUnitTransfers, previewUnitTransfer, retryUnitTransfer, searchUnitTransferTargets,
} from "../../services/constructionApi.js"
import { formatBRL as money } from "../../utils/currencyInput.js"
import { unitTransferStatusLabels as statusLabels } from "../unitTermination/unitHistory.js"

const targetLabel = (item) => item?.label ?? ""

export function UnitTransferModal({ bridge, unit, onClose, onDone, requestConfirm }) {
  const [target, setTarget] = useState(null)
  const [reason, setReason] = useState("")
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(null)
  const completed = useRef(false)
  const Picker = bridge?.components?.EntitySearchCombobox
  const FieldInfo = bridge?.components?.FieldInfo
  const canTransfer = Boolean(bridge?.canUpdate?.("construction_units") && bridge?.canUpdate?.("receivable"))

  const searchTargets = useCallback(async ({ search }) => {
    const result = await searchUnitTransferTargets({ bridge, unitId: unit.id, search })
    return result.items
  }, [bridge, unit.id])

  const openDestination = useCallback(async (transfer) => {
    setLoading(true)
    try {
      await onDone?.(transfer)
    } catch (error) {
      bridge?.feedback?.error?.("A troca foi concluída, mas não foi possível abrir a unidade de destino. "
        + (error.message ?? "Tente abrir novamente."))
    } finally { setLoading(false) }
  }, [bridge, onDone])

  useEffect(() => {
    if (!submitted || completed.current) return undefined
    let active = true
    let timer
    const poll = async () => {
      try {
        const result = await listUnitTransfers({ bridge, unitId: unit.id })
        const transfer = result.items.find((row) => row.transfer_id === submitted.transfer_id)
        if (!active) return
        if (!transfer) throw new Error("A troca não foi localizada no seu acesso atual.")
        if (transfer.status === "published") {
          completed.current = true
          setSubmitted(transfer)
          bridge?.feedback?.success?.("Troca concluída. Parcelas e pagamentos preservados na unidade de destino.")
          await openDestination(transfer)
        } else if (transfer.status !== submitted.status) setSubmitted(transfer)
      } catch (error) {
        if (active) bridge?.feedback?.error?.(error.message ?? "Não foi possível acompanhar a troca.")
        return
      }
      if (active && !completed.current) timer = setTimeout(poll, 2500)
    }
    timer = setTimeout(poll, 2500)
    return () => { active = false; clearTimeout(timer) }
  }, [bridge, openDestination, submitted, unit.id])

  const calculate = async (event) => {
    event.preventDefault()
    if (!target || reason.trim().length < 5) {
      bridge?.feedback?.warning?.("Escolha a unidade de destino e informe um motivo com pelo menos 5 caracteres.")
      return
    }
    setLoading(true)
    try {
      const result = await previewUnitTransfer({ bridge, unitId: unit.id,
        data: { target_unit_id: target.id, reason: reason.trim(), source_sale_id: unit.currentSaleId } })
      setPreview(result)
    } catch (error) {
      bridge?.feedback?.error?.(error.message ?? "Não foi possível conferir a troca.")
    } finally { setLoading(false) }
  }

  const apply = async () => {
    setLoading(true)
    try {
      const result = await applyUnitTransfer({ bridge, unitId: unit.id, data: {
        target_unit_id: preview.target_unit_id, reason: preview.reason, source_sale_id: preview.source_sale_id,
      } })
      setSubmitted(result)
      setPreview(null)
    } catch (error) {
      try {
        const result = await listUnitTransfers({ bridge, unitId: unit.id })
        const existing = result.items.find((row) => row.source_sale_id === preview.source_sale_id
          && row.target_unit_id === preview.target_unit_id)
        if (existing) {
          setSubmitted(existing)
          setPreview(null)
          return
        }
      } catch (statusError) {
        bridge?.feedback?.error?.("Envio não confirmado e não foi possível consultar a situação da troca: "
          + statusError.message + ". Consulte a aba Histórico, nos detalhes da unidade, antes de tentar novamente.")
        return
      }
      bridge?.feedback?.error?.(error.message ?? "Não foi possível registrar a troca.")
      setPreview(null)
    } finally { setLoading(false) }
  }

  const confirm = () => requestConfirm({
    title: "Confirmar troca de unidade",
    message: `Transferir a venda de ${preview.source_label} para ${target.label}? `
      + "O comprador, os valores, os vencimentos e os pagamentos serão mantidos. A origem ficará disponível. "
      + "As duas unidades ficarão bloqueadas para alterações até a integração financeira concluir.",
    confirmLabel: "Confirmar troca", danger: false, run: apply,
  })

  const retry = async () => {
    setLoading(true)
    try {
      await retryUnitTransfer({ bridge, unitId: unit.id, transferId: submitted.transfer_id })
      setSubmitted((current) => ({ ...current, status: "pending" }))
    } catch (error) {
      bridge?.feedback?.error?.(error.message ?? "Não foi possível reenviar a integração.")
    } finally { setLoading(false) }
  }

  const footer = <div className={dialogStyles.dialogActions}>
    <button type="button" className={appStyles.secondaryButton} disabled={loading} onClick={onClose}>
      {submitted ? "Fechar" : "Cancelar"}
    </button>
    {submitted && ["failed", "dead_letter"].includes(submitted.status) ? (
      <button type="button" className={appStyles.primaryButton} disabled={loading || !canTransfer} onClick={retry}>
        Tentar novamente
      </button>
    ) : submitted?.status === "published" ? (
      <button type="button" className={appStyles.primaryButton} disabled={loading}
        onClick={() => openDestination(submitted)}>
        {loading ? "Abrindo destino..." : "Abrir unidade de destino"}
      </button>
    ) : !submitted && Picker ? (
      <button type={preview ? "button" : "submit"} form="unit-transfer-form"
        className={appStyles.primaryButton} disabled={loading || !canTransfer} onClick={preview ? confirm : undefined}>
        {loading ? "Aguarde..." : preview ? "Confirmar troca" : "Conferir troca"}
      </button>
    ) : null}
  </div>

  return <DialogFrame bridge={bridge} title={`Trocar unidade ${unit.code}`}
    onClose={loading ? () => {} : onClose} footer={footer}>
    {submitted ? <div className={dialogStyles.dialogForm} role="status">
      <strong>{statusLabels[submitted.status] ?? submitted.status}</strong>
      <p>A troca está registrada. A integração preserva as parcelas e os pagamentos existentes.
        Você pode fechar esta janela e acompanhar na aba Histórico, nos detalhes da unidade.</p>
    </div> : <form id="unit-transfer-form" className={dialogStyles.dialogForm} onSubmit={calculate}>
      <fieldset className={`${dialogStyles.dialogForm} ${styles.fields}`} disabled={loading || !canTransfer}>
      <p>O mesmo comprador passa para outra unidade disponível desta empresa, inclusive em outra obra.
        O financeiro atual será mantido, sem diferença de preço.</p>
      <label className={appStyles.filterControl}>
        <span className={styles.fieldLabel}>Unidade de destino *
          {FieldInfo && <FieldInfo label="Unidade de destino"
            description="Mostra unidades disponíveis das obras às quais você tem acesso nesta empresa."
            example="EMP-000005 · CASA 12"
            usage="Digite pelo menos 4 caracteres do código, da descrição ou da obra para buscar no catálogo." />}
        </span>
        {Picker ? <Picker value={target} fetcher={searchTargets} pageSize={50} renderLabel={targetLabel}
          renderOption={targetLabel} buildHaystack={targetLabel} disabled={loading}
          placeholder="Buscar unidade ou obra (4 caracteres)"
          onChange={(value) => { setTarget(value); setPreview(null) }} />
          : <span>Atualize o ERP para carregar o seletor de unidades desta tela.</span>}
      </label>
      <label className={appStyles.filterControl}>Motivo da troca *
        <textarea value={reason} minLength={5} maxLength={1000} required disabled={loading}
          onChange={(event) => { setReason(event.target.value); setPreview(null) }} />
      </label>
      {preview && <table className={dialogStyles.statement}>
        <caption>Conferência do financeiro que será preservado</caption>
        <tbody>
          <tr><th scope="row">Cobranças</th><td>{preview.financial.receivables_count}</td></tr>
          <tr><th scope="row">Parcelas</th><td>{preview.financial.installments_count}</td></tr>
          <tr><th scope="row">Parcelas pagas</th><td>{preview.financial.paid_installments_count}</td></tr>
          <tr><th scope="row">Valor pago</th><td>{money(preview.financial.paid_amount)}</td></tr>
          <tr><th scope="row">Saldo em aberto</th><td>{money(preview.financial.open_amount)}</td></tr>
        </tbody>
      </table>}
      <p>Documentos já emitidos e lançamentos contábeis históricos serão preservados.
        Custos, medições e assistência técnica permanecem no imóvel de origem.</p>
      </fieldset>
    </form>}
  </DialogFrame>
}

