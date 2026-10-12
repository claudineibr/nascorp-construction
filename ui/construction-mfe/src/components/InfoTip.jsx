import { useId } from "react"
import { Info } from "lucide-react"

import styles from "./InfoTip.module.css"

export function InfoTip({ label, children }) {
  const tooltipId = useId()

  return (
    <button type="button" className={styles.infoButton} aria-label={label} aria-describedby={tooltipId}>
      <Info size={12} aria-hidden="true" />
      <span id={tooltipId} role="tooltip" className={styles.tooltip}>
        {children}
      </span>
    </button>
  )
}
