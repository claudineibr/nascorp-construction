import { useState } from "react";
import { Link2 } from "lucide-react";
import { SharedPayableLinkModal } from "../sharedPayables/SharedPayableLinkModal";
import appStyles from "../../App.module.css";
import styles from "./SubcontractsPanel.module.css";

export function ContractPayablesSection({ bridge, projectId, contract, canUpdate, dirty = false, onChanged }) {
  const [linking, setLinking] = useState(false);
  const globalMode = contract.pricing_mode === "GLOBAL";
  const blocker = !contract.released_version || contract.status === "CANCELED"
    ? "Disponível depois de liberar a versão."
    : dirty
      ? "Salve as alterações do contrato antes de vincular a DNF."
      : "";
  return (
    <section className={styles.block}>
      <div className={styles.blockHeader}>
        <div>
          <h4>DNF das medições do contrato</h4>
          <p className={styles.hint}>
            {globalMode
              ? "Lance no Contas a Pagar a DNF do empreiteiro e vincule-a aqui às OS do contrato que ela paga. O valor da DNF entra no pago do contrato e não pode passar do saldo."
              : "A medição de contrato não recebe título próprio. Depois de aprovar as medições, vincule aqui a DNF do empreiteiro que as paga: a soma dos líquidos das medições marcadas precisa ser igual ao líquido da DNF (valor menos os tributos retidos)."}{" "}
            As DNFs vinculadas aparecem também no quadro DNFs da empreitada, onde
            Ver OS cobertas permite remover OS delas.
          </p>
        </div>
        {canUpdate && (
          <button
            type="button"
            className={appStyles.secondaryButton}
            disabled={Boolean(blocker)}
            title={blocker || undefined}
            onClick={() => setLinking(true)}
          >
            <Link2 size={16} aria-hidden="true" />
            Vincular DNF às medições
          </button>
        )}
      </div>
      {linking && (
        <SharedPayableLinkModal
          bridge={bridge}
          projectId={projectId}
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
    </section>
  );
}
