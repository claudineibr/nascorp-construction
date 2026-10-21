import { PersonPicker } from "../../components/PersonPicker"

export function InspectorPicker({ bridge, value, valueName, onChange, disabled = false, label = "Inspetor" }) {
  return (
    <PersonPicker
      bridge={bridge}
      label={label}
      value={value}
      knownPeople={value && valueName ? [{ id: value, name: valueName }] : []}
      disabled={disabled}
      emptyLabel="Buscar inspetor pelo nome"
      onChange={(personId, person) => onChange(personId || null, person?.name ?? "")}
    />
  )
}
