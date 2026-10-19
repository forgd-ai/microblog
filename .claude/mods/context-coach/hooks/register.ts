import type { Register } from 'claude-code'

const NUDGES = [
  { at: 80, text: 'Context 80% full. Write progress to PLAN.md now, then /clear and resume from it.' },
  { at: 60, text: 'Context 60% full. Good moment to write state to PLAN.md and plan a /clear.' },
]

const kTokens = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`)

export const register: Register = on => {
  let lastTokens: number | undefined
  const nudged = new Set<number>()

  on('session.measure', ($, e, next) => {
    const { tokens, percent, window } = e.context
    if (tokens === undefined || percent === undefined) return next(e)

    const delta = lastTokens === undefined ? undefined : tokens - lastTokens
    lastTokens = tokens
    const growth = delta === undefined || delta === 0 ? '' : ` (${delta > 0 ? '+' : '-'}${kTokens(Math.abs(delta))} last turn)`
    $.ui.status(`ctx ${percent}% of ${kTokens(window)}${growth}`)

    // Re-arm a nudge once usage falls back under it (after /clear or /compact).
    for (const n of NUDGES) if (percent < n.at) nudged.delete(n.at)
    const due = NUDGES.find(n => percent >= n.at && !nudged.has(n.at))
    if (due) {
      for (const n of NUDGES) if (n.at <= due.at) nudged.add(n.at)
      $.ui.toast(due.text, { timeoutMs: 8000 })
    }
    return next(e)
  })
}
