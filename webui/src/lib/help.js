// Shared help metadata. Disabled controls retain native disabled semantics.
let serial = 0
const records = new WeakMap()
export const HELP_EVENT = 'lumen-help-update'

export function helpInfo(value, disabled = false) {
  const data = typeof value === 'string' ? { action: value } : value || {}
  return { action: String(data.action || ''), reason: disabled ? String(data.reason || '') : '' }
}

function update(el, binding) {
  const info = helpInfo(binding.value, el.disabled || el.getAttribute('aria-disabled') === 'true')
  let record = records.get(el)
  if (!record) {
    const description = document.createElement('span')
    description.id = `lumen-help-${++serial}`
    description.className = 'help-description'
    document.body.append(description)
    record = { description, autoLabel: !el.textContent.trim() && !el.hasAttribute('aria-label') }
    records.set(el, record)
    el.setAttribute('aria-describedby', [el.getAttribute('aria-describedby'), description.id].filter(Boolean).join(' '))
  }
  const changed = el.dataset.helpAction !== info.action || el.dataset.helpReason !== info.reason
  el.dataset.helpAction = info.action
  el.dataset.helpReason = info.reason
  record.description.textContent = [info.action, info.reason].filter(Boolean).join(' ')
  if (record.autoLabel) el.setAttribute('aria-label', info.action)
  if (changed) document.dispatchEvent(new CustomEvent(HELP_EVENT, { detail: { el } }))
}
export const helpDirective = {
  mounted: update,
  updated: update,
  beforeUnmount(el) {
    document.dispatchEvent(new CustomEvent(HELP_EVENT, { detail: { el, removed: true } }))
    const record = records.get(el)
    if (record) {
      record.description.remove()
      const ids = (el.getAttribute('aria-describedby') || '').split(' ').filter(id => id && id !== record.description.id)
      if (ids.length) el.setAttribute('aria-describedby', ids.join(' '))
      else el.removeAttribute('aria-describedby')
    }
    records.delete(el)
  },
}

export function helpTargetAt(doc, x, y) {
  const hit = doc.elementFromPoint(x, y)
  if (!hit) return null
  const scope = hit.closest('[role="dialog"], .overlay')
  // Native disabled controls may suppress pointer events. Hit-test them from
  // the surrounding element without wrapping or enabling the control.
  for (const el of doc.querySelectorAll('[data-help-action]:disabled')) {
    if (el.closest('[role="dialog"], .overlay') !== scope) continue
    if (!hit.contains(el) && !el.parentElement?.contains(hit)) continue
    const r = el.getBoundingClientRect()
    if (r.width && r.height && x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return el
  }
  return hit.closest('[data-help-action]')
}
