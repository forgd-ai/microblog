import { test, expect } from 'claude-code/testing'

const measure = (tokens: number) => ({
  context: { tokens, window: 200000, percent: Math.round((tokens / 200000) * 100) },
  rateLimits: [],
  changed: ['context' as const],
})

test('status shows percent and per-turn growth; nudges fire once per crossing and re-arm', async ($, on) => {
  const statuses: (string | undefined)[] = []
  const toasts: string[] = []
  on('ui.status', (_$, e) => { statuses.push(e.text); return { value: undefined } as never })
  on('ui.toast', (_$, e) => { toasts.push(e.text); return { value: undefined } as never })
  on('session.measure', (_$, e) => ({ changed: e.changed }))

  await $.session.measure(measure(20000))
  expect(statuses.at(-1)).toBe('ctx 10% of 200.0k')
  await $.session.measure(measure(24500))
  expect(statuses.at(-1)).toBe('ctx 12% of 200.0k (+4.5k last turn)')
  expect(toasts.length).toBe(0)

  await $.session.measure(measure(125000)) // 63%
  await $.session.measure(measure(130000)) // still 65%, no repeat
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toContain('60%')

  await $.session.measure(measure(170000)) // 85%
  expect(toasts.length).toBe(2)
  expect(toasts[1]).toContain('80%')

  await $.session.measure(measure(10000)) // after /clear
  expect(statuses.at(-1)).toBe('ctx 5% of 200.0k (-160.0k last turn)')
  await $.session.measure(measure(180000)) // jump straight past 80: one toast, not two
  expect(toasts.length).toBe(3)
  expect(toasts[2]).toContain('80%')
})

test('stays quiet before the first response reports a fill', async ($, on) => {
  const statuses: (string | undefined)[] = []
  on('ui.status', (_$, e) => { statuses.push(e.text); return { value: undefined } as never })
  on('session.measure', (_$, e) => ({ changed: e.changed }))
  await $.session.measure({ context: { window: 200000 }, rateLimits: [], changed: ['context'] })
  expect(statuses.length).toBe(0)
})
