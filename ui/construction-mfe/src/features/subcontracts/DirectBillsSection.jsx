import { useState } from "react";
import { Link2, Unlink } from "lucide-react";
import { InfoTip } from "../../components/InfoTip";
import appStyles from "../../App.module.css";
import { money } from "../sharedPayables/SharedPayableLinkModal";
import {
  currencyDecimal,
  currencyFromNumber,
  currencyNumber,
  formatCurrencyInput,
} from "../../utils/currencyInput";
import { MaterialDocumentPicker } from "./MaterialDocumentPicker";
import styles from "./SubcontractsPanel.module.css";

export function Dialog({ title, wide, busy, onClose, children }) {
  return (
    <div
      className={appStyles.modalOverlay}
      role="presentation"
      onClick={() => !busy && onClose()}
    >
      <section
        className={`${appStyles.modalCard} ${wide ? styles.wideModal : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={appStyles.modalHeader}>
          <h3>{title}</h3>
          <button
            type="button"
            className={appStyles.closeButton}
            onClick={onClose}
            disabled={busy}
          >
            Fechar
          </button>
        </header>
        <div className={appStyles.modalBody}>{children}</div>
      </section>
    </div>
  );
}

export function DirectBillsSection({
  bridge,
  projectId,
  contract,
  bills,
  busy,
  canUpdate,
  onLink,
  onUnlink,
}) {
  const [linking, setLinking] = useState(false);
  const [invoice, setInvoice] = useState({ payable_document_id: "", amount: "" });
  const [unlinkTarget, setUnlinkTarget] = useState(null);
  const released = contract.status === "RELEASED";
  const submit = async (event) => {
    event.preventDefault();
    if (await onLink({ ...invoice, amount: currencyDecimal(invoice.amount) })) {
      setLinking(false);
      setInvoice({ payable_document_id: "", amount: "" });
    }
  };
  return (
    <section className={styles.block}>
      <div className={styles.blockHeader}>
        <div>
          <h4>Material faturado diretamente
          <InfoTip floating label="Sobre o material faturado diretamente">
            Material que a construtora comprou para o empreiteiro e que será
            descontado nas medições. Vincule o título de material já aprovado
            no ERP; isso registra o crédito e não cria outra compra nem
            estoque.
          </InfoTip></h4>
        </div>
        {canUpdate && (
          <button
            type="button"
            className={appStyles.secondaryButton}
            disabled={busy || !released}
            title={
              released ? undefined : "Disponível depois de liberar a versão."
            }
            onClick={() => setLinking(true)}
          >
            <Link2 size={16} aria-hidden="true" />
            Vincular título de material
          </button>
        )}
      </div>
      {!released && !bills.length ? (
        <p className={styles.empty}>Disponível depois de liberar a versão.</p>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Título</th>
                <th>Valor</th>
                <th>Descontado</th>
                <th>Crédito disponível</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {!bills.length && (
                <tr>
                  <td colSpan={5} className={styles.empty}>
                    Nenhum título de material vinculado a este contrato.
                  </td>
                </tr>
              )}
              {bills.map((bill) => {
                const used = Number(bill.deducted_amount) > 0;
                return (
                  <tr key={bill.id}>
                    <td>{bill.snapshot?.document_number ?? "Sem número"}</td>
                    <td className={styles.numeric}>{money(bill.amount)}</td>
                    <td className={styles.numeric}>
                      {money(bill.deducted_amount)}
                    </td>
                    <td className={styles.numeric}>
                      {money(bill.remaining_amount)}
                    </td>
                    <td>
                      {canUpdate && (
                        <button
                          type="button"
                          className={styles.iconButton}
                          disabled={busy || used}
                          title={
                            used
                              ? "Crédito já descontado em medição: estorne o desconto antes."
                              : "Desvincular título"
                          }
                          aria-label={`Desvincular o título ${bill.snapshot?.document_number ?? ""}`}
                          onClick={() => setUnlinkTarget(bill)}
                        >
                          <Unlink size={16} aria-hidden="true" />
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
      {linking && (
        <Dialog
          title="Vincular título de material"
          wide
          busy={busy}
          onClose={() => setLinking(false)}
        >
          <form className={styles.modalForm} onSubmit={submit}>
            <MaterialDocumentPicker
              bridge={bridge}
              projectId={projectId}
              selectedId={invoice.payable_document_id}
              disabled={busy}
              onSelect={(row) =>
                setInvoice({
                  payable_document_id: row.id,
                  amount: currencyFromNumber(row.amount),
                })
              }
            />
            <div className={styles.fields}>
              <label>
                Valor faturado para a empreitada*
                <input
                  required
                  type="text"
                  inputMode="decimal"
                  placeholder="0,00"
                  value={invoice.amount}
                  onChange={(e) =>
                    setInvoice({
                      ...invoice,
                      amount: formatCurrencyInput(e.target.value),
                    })
                  }
                />
              </label>
            </div>
            <div className={appStyles.modalFooter}>
              <button
                type="button"
                className={appStyles.secondaryButton}
                disabled={busy}
                onClick={() => setLinking(false)}
              >
                Cancelar
              </button>
              <button
                className={appStyles.primaryButton}
                disabled={
                  busy ||
                  !invoice.payable_document_id ||
                  currencyNumber(invoice.amount) <= 0
                }
              >
                Vincular título
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {unlinkTarget && (
        <Dialog
          title="Desvincular título de material"
          busy={busy}
          onClose={() => setUnlinkTarget(null)}
        >
          <p>
            Desvincular o título{" "}
            {unlinkTarget.snapshot?.document_number ?? "sem número"} deste
            contrato? O crédito de {money(unlinkTarget.remaining_amount)} deixa
            de ficar disponível para desconto nas medições. O título no ERP não
            muda.
          </p>
          <div className={appStyles.modalFooter}>
            <button
              type="button"
              className={appStyles.secondaryButton}
              disabled={busy}
              onClick={() => setUnlinkTarget(null)}
            >
              Cancelar
            </button>
            <button
              type="button"
              className={`${appStyles.secondaryButton} ${appStyles.dangerButton}`}
              disabled={busy}
              onClick={async () => {
                if (await onUnlink(unlinkTarget)) setUnlinkTarget(null);
              }}
            >
              Desvincular
            </button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
