const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const { createRequire } = require("node:module")
const test = require("node:test")

const root = path.resolve(__dirname, "../../../../../..")
const req = createRequire(path.join(root, "src/ui/nascorp-erp-ui/package.json"))
const React = req("react")
const { renderToStaticMarkup } = req("react-dom/server")
const { JSDOM } = req("jsdom")
const esbuild = req("esbuild")
const source = fs.readFileSync(process.env.PROJECT_UI_SOURCE_PATH || path.join(__dirname, "../src/App.jsx"), "utf8").replace(/\r\n/g, "\n")
const menus = []
const context = {
  require: req,
  styles: new Proxy({}, { get: (_, key) => key }),
  statusOptions: [], projectTypeOptions: [],
  useId: React.useId,
  UnitBankSlipDialogFrame: ({ children }) => children,
  InfoTip: () => null,
  PersonPicker: () => null,
  TerminationTermsEditor: () => null,
  ContractTemplateField: () => React.createElement("label", { className: "field" }, "Template de contrato", React.createElement("input")),
  RowActionsMenu: ({ actions }) => { menus.push(actions); return null },
  formatMoney: String, formatDate: String, NOTHING_LEFT_TO_CHARGE: "Sem saldo",
}
for (const icon of ["RefreshCw", "Plus", "CheckCircle", "FileText", "Trash2"]) context[icon] = () => null
vm.createContext(context)
vm.runInContext(source.slice(source.indexOf("const PROJECT_FIELD_HELP ="), source.indexOf("function ProjectModal(")), context)
for (const name of ["ProjectModal", "UnitCommissionsPanel"]) {
  const start = source.indexOf(`function ${name}(`)
  const end = source.indexOf("\nfunction ", start + 1)
  vm.runInContext(esbuild.transformSync(source.slice(start, end), { loader: "jsx", jsx: "automatic", format: "cjs" }).code, context)
}

test("project address starts with CEP and retains lookup on blur", () => {
  const html = renderToStaticMarkup(React.createElement(context.ProjectModal, {
    mode: "edit", projectForm: {}, people: [], onChange() {}, onZipLookup() {},
  }))
  const document = new JSDOM(html).window.document
  const section = [...document.querySelectorAll("h4")].find(element => element.textContent === "Endereço")
  assert.deepEqual(
    [...section.nextElementSibling.querySelectorAll("label span")].map(element => element.textContent),
    ["CEP", "Logradouro", "Número", "Bairro", "Cidade", "UF", "Código IBGE do município", "Latitude", "Longitude"],
  )
  assert.equal(section.nextElementSibling.querySelector("input").placeholder, "00000-000")
})

test("project groups subjects and shows the business-day field only for enabled billing", () => {
  for (const [canConfigureNfseReceivables, autoNfseReceivable] of [[true, true], [true, false], [false, true]]) {
    const html = renderToStaticMarkup(React.createElement(context.ProjectModal, {
      mode: "edit", canConfigureNfseReceivables,
      projectForm: { autoNfseReceivable, nfseReceivableDueDays: "0" }, people: [],
    }))
    const document = new JSDOM(html).window.document
    const groups = [...document.querySelectorAll("fieldset > section[aria-labelledby]")]
    assert.deepEqual(
      groups.map(group => document.getElementById(group.getAttribute("aria-labelledby")).textContent),
      ["Identificação", "Prazos", "Dados fiscais e faturamento", "Contrato de venda", "Configurações de distrato",
        "Modelos de recibo", "Endereço"],
    )
    const billing = groups[2]
    assert.match(billing.textContent, /CNO/)
    assert.equal(Boolean(billing.querySelector('input[type="checkbox"]')), canConfigureNfseReceivables)
    const days = billing.querySelector('input[type="number"]')
    assert.equal(Boolean(days), canConfigureNfseReceivables && autoNfseReceivable)
    if (days) {
      assert.match(days.closest("label").textContent, /Dias úteis para vencimento/)
      assert.equal(days.value, "0")
      assert.equal(days.min, "0")
      assert.equal(days.max, "365")
      assert.equal(days.required, true)
    }
  }
})

test("signal receipt requires payment, respects read access and targets its own row", () => {
  const commission = { id: "signal", sequenceNumber: 1, beneficiaryPersonId: "broker", amount: 1500 }
  let selected
  for (const paid of [false, true]) {
    for (const allowed of [false, true]) {
      menus.length = 0
      const row = { ...commission, paymentDate: paid ? "2026-10-01" : null }
      renderToStaticMarkup(React.createElement(context.UnitCommissionsPanel, {
        unit: { status: "sold" }, people: [], plan: { commissions: [row] },
        onReceipt: allowed ? value => { selected = value } : null,
      }))
      const receipt = menus[0].find(action => action.key === "receipt")
      assert.equal(Boolean(receipt), allowed)
      if (receipt) {
        assert.equal(receipt.label, "Baixar recibo")
        assert.equal(receipt.disabled, !paid)
        if (paid) { receipt.onSelect(); assert.equal(selected, row) }
        else assert.ok(receipt.title)
      }
    }
  }
})
