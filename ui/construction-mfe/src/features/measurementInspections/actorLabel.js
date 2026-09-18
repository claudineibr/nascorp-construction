// Nome de quem fez algo, quando o registro só tem o id.
//
// O módulo de Obras não tem tabela de usuários: o nome é resolvido no ERP e
// CONGELADO na linha no momento da gravação. Vem vazio quando o ERP não
// respondeu naquele instante, ou quando o registro é anterior a esta trilha —
// e dizer isso é mais honesto do que um espaço em branco que o leitor precisa
// interpretar.
export function describeActor(record, { legacyNote = "Autor não registrado (anterior à auditoria)" } = {}) {
  const name = record?.actorName || record?.recordedByName
  if (name) {
    return name
  }

  if (record?.source === "migration") {
    return legacyNote
  }

  const id = record?.actorUserId || record?.recordedByUserId
  return id ? `Usuário ${String(id).slice(0, 8)}` : "Autor não identificado"
}

/** Quem foi a campo. Nulo é o caso comum na carga do legado, que não guardava. */
export function describeInspector(round) {
  if (round?.inspectorName) {
    return round.inspectorName
  }

  if (round?.source === "migration") {
    return "Inspetor não registrado (anterior ao registro de rodadas)"
  }

  return round?.inspectorPersonId ? `Pessoa ${String(round.inspectorPersonId).slice(0, 8)}` : ""
}
