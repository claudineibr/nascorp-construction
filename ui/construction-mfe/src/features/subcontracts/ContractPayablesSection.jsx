import { useState } from "react";
import { FilePlus2, Link2 } from "lucide-react";
import { SharedPayableLinkModal } from "../sharedPayables/SharedPayableLinkModal";
import appStyles from "../../App.module.css";
import styles from "../sharedPayables/SharedPayables.module.css";

export function ContractPayablesSection({ bridge, projectId, contract, canUpdate, dirty = false, onChanged }) {
  const [linking, setLinking] = useState(false);
  const globalMode = contract.pricing_mode === "GLOBAL";
  const blocker = globalMode && (contract.status === "CLOSED" || Number(contract.paid_amount) > 0)
    ? "Contrato encerrado para novos lançamentos. Cancele o título no ERP para liberar as OS."
    : !contract.released_version || contract.status === "CANCELED"
    ? "Disponível depois de liberar a versão."
    : dirty
      ? "Salve as alterações do contrato antes de vincular o título."
      : "";
  return (
    <>
        {canUpdate && (
          <div className={styles.paymentActions}>
          {bridge.canCreate?.("accounts_payable") && bridge.canRead?.("construction_projects") && bridge.navigate && (
            <button
              type="button"
              className={appStyles.primaryButton}
              disabled={Boolean(blocker)}
              title={blocker || undefined}
              onClick={() => setLinking("create")}
            >
              <FilePlus2 size={16} aria-hidden="true" />
              Criar título
            </button>
          )}
          <button
            type="button"
            className={appStyles.secondaryButton}
            disabled={Boolean(blocker)}
            title={blocker || undefined}
            onClick={() => setLinking("existing")}
          >
            <Link2 size={16} aria-hidden="true" />
            Vincular título existente
          </button>
          </div>
        )}
      {linking && (
        <SharedPayableLinkModal
          bridge={bridge}
          projectId={projectId}
          creating={linking === "create"}
          contract={{
            id: contract.id,
            code: contract.code,
            supplierPersonId: contract.supplier_person_id,
            pricingMode: contract.pricing_mode,
            remainingAmount: contract.remaining_amount,
          }}
          onClose={() => setLinking(false)}
          onLinked={() => {
            setLinking(false);
            onChanged?.();
          }}
        />
      )}
    </>
  );
}
