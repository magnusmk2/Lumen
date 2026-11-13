<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { HELP_EVENT, helpTargetAt } from '../lib/help.js'
import { useI18n } from '../composables/useI18n.js'
const { t } = useI18n()
const visible = ref(false), action = ref(''), reason = ref(''), box = ref(null)
const left = ref(8), top = ref(8)
let active = null, dismissed = null, timer
function hide() { clearTimeout(timer); visible.value = false; active = null }
async function show(el) {
  if (active !== el || !el.isConnected || !el.dataset.helpAction) return
  action.value = el.dataset.helpAction
  reason.value = el.dataset.helpReason || ''
  visible.value = true
  await nextTick()
  if (!box.value || !active) return
  const r = el.getBoundingClientRect(), b = box.value.getBoundingClientRect()
  left.value = Math.max(8, Math.min(innerWidth - b.width - 8, r.left + (r.width - b.width)/2))
  top.value = r.bottom + b.height + 10 < innerHeight ? r.bottom + 8 : Math.max(8, r.top - b.height - 8)
}
function enter(el, immediate = false) {
  if (el !== dismissed) dismissed = null
  if (!el || el === dismissed) { hide(); return }
  if (el === active) return
  hide(); active = el
  if (immediate) show(el)
  else timer = setTimeout(() => show(el), 350)
}
function pointer(e) { enter(helpTargetAt(document, e.clientX, e.clientY)) }
function focus(e) { enter(e.target.closest?.('[data-help-action]'), true) }
function update(e) {
  if (e.detail.el !== active) return
  if (e.detail.removed) hide()
  else if (visible.value) show(active)
}
function key(e) {
  if (e.key !== 'Escape') return
  if (visible.value) {
    dismissed = active; hide(); e.preventDefault(); e.stopPropagation()
  } else hide()
}
function outside(e) { if (!e.relatedTarget) hide() }
onMounted(() => {
  document.addEventListener('pointermove', pointer, true)
  document.addEventListener('focusin', focus, true)
  document.addEventListener('focusout', hide, true)
  document.addEventListener('pointerdown', hide, true)
  document.addEventListener('scroll', hide, true)
  document.addEventListener('mouseout', outside, true)
  document.addEventListener('keydown', key, true)
  document.addEventListener(HELP_EVENT, update)
  window.addEventListener('blur', hide)
  window.addEventListener('resize', hide)
})
onUnmounted(() => {
  hide()
  document.removeEventListener('pointermove', pointer, true)
  document.removeEventListener('focusin', focus, true)
  document.removeEventListener('focusout', hide, true)
  document.removeEventListener('pointerdown', hide, true)
  document.removeEventListener('scroll', hide, true)
  document.removeEventListener('mouseout', outside, true)
  document.removeEventListener('keydown', key, true)
  document.removeEventListener(HELP_EVENT, update)
  window.removeEventListener('blur', hide)
  window.removeEventListener('resize', hide)
})
</script>
<template>
  <Teleport to="body"><div v-if="visible" ref="box" class="app-tooltip" role="tooltip" :style="{left:left+'px',top:top+'px'}"><div>{{ action }}</div><div v-if="reason" class="reason"><strong>{{ t('help_disabled_label') }}</strong> {{ reason }}</div></div></Teleport>
</template>
<style scoped>
.app-tooltip{position:fixed;z-index:10000;max-width:min(340px,calc(100vw - 16px));padding:10px 12px;background:var(--sheet);color:var(--ink);border:1px solid var(--ink-4);border-radius:8px;box-shadow:0 4px 16px #0004;pointer-events:none;font:14px/1.5 'IBM Plex Sans',sans-serif;overflow-wrap:anywhere}.reason{margin-top:7px;padding-top:7px;border-top:1px solid var(--panel-line);color:var(--ink-2)}
</style>
