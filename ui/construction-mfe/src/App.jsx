import styles from "./App.module.css"
import { resolveConstructionBridge } from "./bridge/constructionBridge.js"


const summaryItems = [
  { label: "Empreendimentos", value: "0" },
  { label: "Unidades", value: "0" },
  { label: "Medições", value: "0" },
]


export default function App() {
  const bridge = resolveConstructionBridge()
  const theme = bridge?.getTheme?.() ?? "light"

  return (
    <main className={styles.page} data-theme={theme}>
      <section className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>NASCORP Construction</span>
          <h1>Obras</h1>
          <p>Fundação operacional do módulo Construction.</p>
        </div>
      </section>

      <section className={styles.summaryGrid} aria-label="Resumo">
        {summaryItems.map((item) => (
          <article className={styles.summaryCard} key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>
    </main>
  )
}