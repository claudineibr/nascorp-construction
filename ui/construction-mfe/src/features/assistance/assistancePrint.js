import { formatBusinessDate } from "../../utils/brazilDate.js"
import styles from "./AssistancePrint.module.css"
import stylesheet from "./AssistancePrint.module.css?inline"
import pageStylesheet from "./AssistancePrintPage.module.css?inline"
import { maskPhone } from "../../utils/phoneInput"

const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char])
  )
const date = (value) => (value ? formatBusinessDate(value) : "")
const unique = (values) => [...new Set(values.filter(Boolean))].join(", ")
const signature = (name, label, when = "") =>
  `<td><div class="${styles.signatureName}">${escape(name)}</div>${escape(label)}<div class="${
    styles.signatureDate
  }">${escape(when)}</div>Data</td>`

export const assistancePrintDocument = ({ sat, people, city, company_name, company_logo_url }, companyName = "") => {
  const name = company_name || companyName
  const brand = company_logo_url
    ? `<img class="${styles.companyLogo}" src="${escape(company_logo_url)}" alt="${escape(name)}">`
    : escape(name)
  const customer = people[sat.customer_person_id] || sat.customer_name || ""
  const names = (ids) => unique(ids.map((id) => people[id]))
  const phone = sat.contacts.find(
    (contact) => ["phone", "whatsapp"].includes(contact.channel) && contact.detail
  )?.detail
  const complaints = sat.complaints.length ? sat.complaints : [{}]
  const services = sat.services.length ? sat.services : [{}]
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>SAT ${escape(
    sat.number
  )}</title><style>${pageStylesheet}${stylesheet}</style></head>
<body class="${styles.page}"><main class="${styles.sheet}">
<table class="${styles.header}"><tr><th class="${
    styles.company
  }">${brand}</th><th>SOLICITAÇÃO DE ASSISTÊNCIA TÉCNICA - SAT</th></tr></table>
<table><tr><td>Cliente: ${escape(customer)}</td><td>SAT nº ${escape(sat.number)}</td></tr><tr><td>Fone: ${escape(
    phone ? maskPhone(phone) : ""
  )}</td><td>Abertura: ${escape(date(sat.opened_at))}</td></tr><tr><td>Obra: ${escape(
    sat.project_name
  )}</td><td>Unidade: ${escape(sat.unit_code)}</td></tr><tr><td colspan="2">Cidade: ${escape(city)}</td></tr></table>
<table><thead><tr><th class="${styles.item}">ITEM</th><th>RECLAMAÇÃO</th><th class="${
    styles.provenance
  }">PROCEDENTE?</th></tr></thead><tbody>${complaints
    .map(
      (item, index) =>
        `<tr><td class="${styles.item}">${escape(item.original_number ?? index + 1)}</td><td>${escape(
          item.description
        )}</td><td>${escape({ valid: "Sim", invalid: "Não", pending: "Em análise" }[item.provenance])}</td></tr>`
    )
    .join("")}</tbody></table>
<p class="${styles.declaration}">Eu, ${escape(
    customer
  )}, autorizo a empresa a realizar as correções das irregularidades acima descritas, se procedentes. Estou ciente de que será cobrada visita técnica caso as reclamações não sejam procedentes ou não sejam de responsabilidade da construtora.</p>
<table class="${styles.signatures}"><tr>${signature(customer, "Cliente")}${signature(
    people[sat.attendant_person_id],
    "Responsável Atendimento",
    date(sat.opened_at)
  )}${signature(
    names([sat.analyst_person_id, ...sat.complaints.map((item) => item.analyzed_by_person_id)]),
    "Responsável Análise",
    unique(sat.complaints.map((item) => date(item.analyzed_at)))
  )}</tr></table>
<table><thead><tr><th class="${styles.item}">ITEM</th><th>SERVIÇOS A SEREM REALIZADOS</th><th class="${
    styles.due
  }">PRAZO</th></tr></thead><tbody>${services
    .map(
      (item, index) =>
        `<tr><td class="${styles.item}">${escape(item.original_number ?? index + 1)}</td><td>${escape(
          item.description
        )}</td><td>${escape(
          item.due_date ? formatBusinessDate(item.due_date) : ""
        )}</td></tr>`
    )
    .join("")}</tbody></table>
<p class="${styles.declaration}">Eu, ${escape(
    customer
  )}, declaro que as irregularidades do imóvel descritas acima foram totalmente regularizadas, sendo que não tenho nada mais a reclamar.</p>
<table class="${styles.notes}"><thead><tr><th>OBSERVAÇÕES</th></tr></thead><tbody><tr><td>${escape(
    sat.notes
  )}</td></tr>${Array.from({ length: 4 }, () => "<tr><td></td></tr>").join("")}</tbody></table>
<table class="${styles.signatures}"><tr>${signature(
    names(sat.services.map((item) => item.executed_by_person_id)),
    "Responsável Serviço",
    unique(sat.services.map((item) => date(item.executed_at)))
  )}${signature(
    names(sat.services.map((item) => item.inspected_by_person_id)),
    "Inspecionado Por",
    unique(sat.services.map((item) => date(item.inspected_at)))
  )}${signature(customer, "Cliente", date(sat.completed_at))}</tr></table>
</main></body></html>`
}
