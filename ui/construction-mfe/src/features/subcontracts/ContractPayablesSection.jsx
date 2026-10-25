import { useState } from "react";
import { FilePlus2, Link2 } from "lucide-react";
import { InfoTip } from "../../components/InfoTip";
import { SharedPayableLinkModal } from "../sharedPayables/SharedPayableLinkModal";
import appStyles from "../../App.module.css";
import styles from "./SubcontractsPanel.module.css";

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
    <section className={styles.block}>
      <div className={styles.blockHeader}>
        <div>
          <h4>Títulos das medições do contrato
          <InfoTip floating label="Como criar e vincular o título do contrato">
            Use Criar título no ERP, selecione as medições e preencha o lançamento.
            Ao salvar, o título será vinculado automaticamente às medições selecionadas.{" "}
            {globalMode
              ? "Crie o título com o valor do contrato ou vincule um título existente às OS que ele paga. O valor não pode passar do saldo. Após o vínculo, o contrato global é encerrado para novos lançamentos."
              : "A medição de contrato não recebe título próprio. Depois de aprovar as medições, vincule aqui o título do empreiteiro que as paga: a soma dos líquidos das medições marcadas precisa ser igual ao líquido do título (valor menos os tributos retidos)."}{" "}
            Os títulos vinculados aparecem também no quadro Títulos da empreitada, onde
            {globalMode ? "Ver OS cobertas é somente consulta; cancele o título no ERP para liberar as OS." : "Ver OS cobertas permite remover OS deles."}
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
            Vincular título às medições
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
