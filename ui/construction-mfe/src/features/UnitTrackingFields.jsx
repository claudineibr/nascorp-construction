const fields = [
  ["correspondent", "Correspondente", "text"],
  ["correspondentDate", "Data correspondente", "date"],
  ["clientSituation", "Situação do cliente", "select", ["Não responde", "Com restrição"]],
  ["clientSituationDate", "Data situação", "date"],
  ["processStatus", "Processo", "select", ["Banco", "Prefeitura", "Cartório", "Pagamento banco", "Concluído"]],
  ["processStatusDate", "Data processo", "date"],
]

export function UnitTrackingFields({ values, onChange, className }) {
  return fields.map(([name, label, type, options]) => (
    <label key={name} className={className}>
      <span>{label}</span>
      {type === "select" ? (
        <select value={values[name] || ""} onChange={(event) => onChange(name, event.target.value)}>
          <option value="">Não informado</option>
          {options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      ) : (
        <input type={type} maxLength={type === "text" ? 120 : undefined}
          value={values[name] || ""} onChange={(event) => onChange(name, event.target.value)} />
      )}
    </label>
  ))
}
