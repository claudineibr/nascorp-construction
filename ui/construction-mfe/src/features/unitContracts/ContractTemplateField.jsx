import { useEffect, useState, useId } from "react";
import { unitContractRequest } from "../../services/unitContracts.js";
import styles from "./UnitContractPanel.module.css";

export function ContractTemplateField({ bridge, value, onChange, disabled }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const id = useId();
  useEffect(() => {
    if (!bridge?.canRead?.("contract")) return undefined;
    let active = true;
    setLoading(true);
    const timer = setTimeout(() => unitContractRequest(bridge, `/templates?search=${encodeURIComponent(search)}&page_size=25`)
      .then((result) => { if (active) setTemplates(result.items); })
      .catch((error) => { if (active) bridge?.feedback?.error?.(error.message); })
      .finally(() => { if (active) setLoading(false); }), 400);
    return () => { active = false; clearTimeout(timer); };
  }, [bridge, search]);
  useEffect(() => {
    if (!value || !bridge?.canRead?.("contract")) return undefined;
    let active = true;
    unitContractRequest(bridge, `/templates/${value}`)
      .then((result) => { if (active) setSearch(result.name); })
      .catch((error) => { if (active) bridge?.feedback?.error?.(error.message); });
    return () => { active = false; };
  }, [bridge, value]);
  return <label className={styles.field}>
    <span>Template de contrato</span>
    <input list={id} value={search} disabled={disabled || !bridge?.canRead?.("contract")}
      placeholder={loading ? "Carregando modelos..." : "Buscar template publicado"}
      onChange={(event) => {
        setSearch(event.target.value);
        const match = templates.find((row) => row.name === event.target.value);
        onChange(match?.id ?? "");
      }} />
    <datalist id={id}>{templates.map((row) => <option key={row.id} value={row.name} />)}</datalist>
  </label>;
}
