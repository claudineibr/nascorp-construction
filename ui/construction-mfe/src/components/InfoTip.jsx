import { useId, useLayoutEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { Info } from "lucide-react"

import styles from "./InfoTip.module.css"

export function InfoTip({ label, children, floating = false }) {
  const tooltipId = useId()
  const triggerRef = useRef(null)
  const tooltipRef = useRef(null)
  const [open, setOpen] = useState(false)

  useLayoutEffect(() => {
    if (!floating || !open || !triggerRef.current || !tooltipRef.current) return undefined
    const rect = triggerRef.current.getBoundingClientRect()
    const tooltip = tooltipRef.current
    const viewport = window.visualViewport
    const topEdge = (viewport?.offsetTop ?? 0) + 8
    const leftEdge = (viewport?.offsetLeft ?? 0) + 8
    const width = Math.min(360, (viewport?.width ?? window.innerWidth) - 16)
    tooltip.style.setProperty("--info-width", `${width}px`)
    const height = tooltip.getBoundingClientRect().height
    const bottomEdge = topEdge + (viewport?.height ?? window.innerHeight) - 16
    const top = rect.bottom + 8 + height > bottomEdge ? rect.top - height - 8 : rect.bottom + 8
    const left = Math.max(leftEdge, Math.min(rect.left, leftEdge + (viewport?.width ?? window.innerWidth) - width - 16))
    tooltip.style.setProperty("--info-top", `${Math.max(topEdge, top)}px`)
    tooltip.style.setProperty("--info-left", `${left}px`)
    const dismiss = () => setOpen(false)
    window.addEventListener("scroll", dismiss, true)
    window.addEventListener("resize", dismiss)
    window.visualViewport?.addEventListener("resize", dismiss)
    return () => {
      window.removeEventListener("scroll", dismiss, true)
      window.removeEventListener("resize", dismiss)
      window.visualViewport?.removeEventListener("resize", dismiss)
    }
  }, [floating, open, children])

  const tooltip = <span id={tooltipId} role="tooltip" ref={tooltipRef}
    className={`${styles.tooltip} ${floating ? styles.floating : ""}`}>
    {children}
  </span>

  return (
    <button type="button" ref={triggerRef} className={styles.infoButton} title={label} aria-label={label}
      aria-describedby={!floating || open ? tooltipId : undefined}
      onMouseEnter={() => { if (floating) setOpen(true) }}
      onMouseLeave={() => { if (floating) setOpen(false) }}
      onFocus={() => { if (floating) setOpen(true) }}
      onBlur={() => { if (floating) setOpen(false) }}
      onKeyDown={(event) => {
        if (floating && event.key === "Escape") {
          event.stopPropagation()
          setOpen(false)
          event.currentTarget.blur()
        }
      }}>
      <Info size={12} aria-hidden="true" />
      {floating ? open && createPortal(tooltip, document.body) : tooltip}
    </button>
  )
}
