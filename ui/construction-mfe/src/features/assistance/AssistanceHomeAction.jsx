import { AssistancePanel } from "./AssistancePanel"
import { setBusinessTimezone } from "../../utils/brazilDate"

export default function AssistanceHomeAction({ bridge, onClose, onChanged }) {
  setBusinessTimezone(bridge.companyContext?.timezone)
  return <AssistancePanel bridge={bridge} embedded onClose={onClose} onChanged={onChanged} />
}
