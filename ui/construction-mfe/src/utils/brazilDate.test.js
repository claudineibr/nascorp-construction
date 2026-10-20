import assert from "node:assert/strict"
import test from "node:test"
import { brazilTodayISO, setBusinessTimezone, formatBusinessDate } from "./brazilDate.js"

const at = (t, instant) => {
  t.mock.timers.enable({ apis: ["Date"], now: new Date(instant) })
}

test("das 21h às 23h59 de Brasília ainda é o mesmo dia, embora o UTC já tenha virado", (t) => {
  at(t, "2026-10-21T00:00:00Z")
  assert.equal(brazilTodayISO(), "2026-10-20")
  t.mock.timers.setTime(new Date("2026-10-21T02:59:59Z").getTime())
  assert.equal(brazilTodayISO(), "2026-10-20")
})

test("a meia-noite de Brasília vira o dia", (t) => {
  at(t, "2026-10-21T03:00:00Z")
  assert.equal(brazilTodayISO(), "2026-10-21")
})

test("a data da empresa de MS permanece no dia anterior até sua meia-noite", (t) => {
  at(t, "2027-01-01T03:30:00Z")
  setBusinessTimezone("America/Campo_Grande")
  t.after(() => setBusinessTimezone("America/Sao_Paulo"))
  assert.equal(brazilTodayISO(), "2026-12-31")
  assert.equal(formatBusinessDate("2027-01-01"), "01/01/2027")
  assert.equal(formatBusinessDate("2027-01-01T03:30:00Z"), "31/12/2026")
})
