// O vocabulário da FVS da Caixa: o que se afere é CONFORMIDADE com o projeto.
// "Procedente/improcedente" é vocabulário de reclamação e fica reservado para o
// módulo de assistência técnica.
export const roundStatusLabel = {
  compliant: "Conforme",
  non_compliant: "Não conforme",
  waived: "Dispensado",
}

export const lineStateLabel = {
  pending: "Pendente",
  compliant: "Conforme",
  approved_after_reinspection: "Aprovado com reinspeção",
  non_compliant: "Não conforme — aguardando reinspeção",
  waived: "Dispensado de reinspeção",
}

export const itemStatusLabel = {
  pending: "Pendente",
  compliant: "Conforme",
  non_compliant: "Não conforme",
}

/** O estado de exibição da linha, derivado do histórico de rodadas. */
export function deriveLineState(inspection) {
  if (!inspection.roundsCount) {
    return "pending"
  }

  if (inspection.status === "non_compliant") {
    return "non_compliant"
  }

  if (inspection.lastRound?.status === "waived") {
    return "waived"
  }

  return inspection.approvedAfterReinspection ? "approved_after_reinspection" : "compliant"
}

/** Linhas que impedem fechar o item: reprovadas sem reinspeção aprovada. */
export function countBlockingLines(inspections) {
  return (inspections ?? []).filter((inspection) => inspection.status === "non_compliant").length
}

export function countPendingLines(inspections) {
  return (inspections ?? []).filter((inspection) => !inspection.roundsCount).length
}
