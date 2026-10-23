import { useState } from "react";
import { FilePlus2, Link2 } from "lucide-react";
import { InfoTip } from "../../components/InfoTip";
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
          <h4>DNF das medições do contrato
          <InfoTip floating label="Como criar e vincular a DNF do contrato">
            Use Criar título no ERP, selecione as medições e preencha o lançamento.
            Ao salvar, a DNF será vinculada automaticamente às medições selecionadas.{" "}
            {globalMode
              ? "Lance no Contas a Pagar a DNF do empreiteiro e vincule-a aqui às OS do contrato que ela paga. O valor da DNF entra no pago do contrato e não pode passar do saldo."
              : "A medição de contrato não recebe título próprio. Depois de aprovar as medições, vincule aqui a DNF do empreiteiro que as paga: a soma dos líquidos das medições marcadas precisa ser igual ao líquido da DNF (valor menos os tributos retidos)."}{" "}
            As DNFs vinculadas aparecem também no quadro DNFs da empreitada, onde
            Ver OS cobertas permite remover OS delas.
          </InfoTip></h4>
        </div>
        {canUpdate && (
          <div className={styles.actions}>
          {bridge.canCreate?.("accounts_payable") && bridge.canRead?.("construction_projects") && bridge.navigate && (
            <button
              type="button"
              className={appStyles.primaryButton}
              disabled={Boolean(blocker)}
              title={blocker || undefined}
              onClick={() => setLinking("create")}
            >
              <FilePlus2 size={16} aria-hidden="true" />
              Criar título no ERP
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
            Vincular DNF às medições
          </button>
          </div>
        )}
      </div>
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
    </section>
  );
}
