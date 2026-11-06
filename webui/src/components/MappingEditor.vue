<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from '../composables/useI18n.js'
import { previewSyncMapping, saveSyncMapping, identifySyncChannel, store } from '../store/index.js'
const props = defineProps({ data: Object })
const emit = defineEmits(['close', 'saved'])
const { t } = useI18n()
const copy = x => JSON.parse(JSON.stringify(x))
const draft = ref(copy(props.data.profile))
const rectangles = ref(copy(props.data.rectangles))
const warnings = ref(props.data.warnings || [])
const error = ref(props.data.problem || '')
const saving = ref(false), pending = ref(false), selected = ref(props.data.topology.channels[0]?.id)
const dialog = ref(null)
const topo = props.data.topology
const previousFocus = document.activeElement
let generation = 0, previewTimer, alive = true
const selectedChannel = computed(() => topo.channels.find(c => c.id === selected.value))
const selectedRect = computed(() => rectangles.value[String(selected.value)] || [0,0,1,1])
const manual = computed(() => Object.hasOwn(draft.value.overrides || {}, String(selected.value)))
const fields = computed(() => {
  const [x,y,r,b] = selectedRect.value
  return [x*100,y*100,(r-x)*100,(b-y)*100]
})
const hasMismatch = computed(() => draft.value.signature !== topo.signature)

function defaultDevice(g) {
  return { mode: 'inherit', strategy: g.coverage_available ? 'coverage' : 'equal', order: [...g.order], reverse: false, start: 0, end: 1 }
}
const usesDesk = computed(() => draft.value.mode === 'desk' || Object.values(draft.value.devices || {}).some(d=>d.mode==='desk'))
function deviceUsesDesk(g) {
  const mode=draft.value.devices[g.id]?.mode || 'inherit'
  return (mode==='inherit' ? draft.value.mode : mode)==='desk'
}
function prepareDevices() {
  draft.value.devices ||= {}
  for (const g of topo.devices) {
    draft.value.devices[g.id] ||= defaultDevice(g)
    draft.value.devices[g.id].mode ||= 'inherit'
  }
}
prepareDevices()
function regenerate() {
  const request = ++generation
  pending.value = true
  clearTimeout(previewTimer)
  previewTimer = setTimeout(async () => {
    try {
      const res = await previewSyncMapping(copy(draft.value))
      if (!alive || request !== generation) return
      error.value = res.error || ''
      if (!res.error) { rectangles.value = res.rectangles; warnings.value = res.warnings }
    } catch (e) { if (alive && request === generation) error.value = String(e) }
    finally { if (alive && request === generation) pending.value = false }
  }, 130)
}
watch(draft, regenerate, { deep: true })
function resetAll() {
  draft.value = { version: 1, signature: topo.signature, mode: 'desk', height: .2, inset: 0, devices: {}, overrides: {} }
  prepareDevices()
}
function rebind() {
  const ids = new Set(topo.channels.map(c => String(c.id)))
  draft.value.signature = topo.signature
  draft.value.overrides = Object.fromEntries(Object.entries(draft.value.overrides || {}).filter(([id]) => ids.has(id)))
  draft.value.devices = {}
  prepareDevices()
}
function resetChannel(id) { delete draft.value.overrides[String(id)] }
function resetDevice(g) {
  draft.value.devices[g.id] = defaultDevice(g)
  g.channels.forEach(resetChannel)
}
function editRect(index, text) {
  const values = [...fields.value]; values[index] = text === '' ? NaN : Number(text)
  const [x,y,w,h] = values.map(v => v/100)
  draft.value.overrides[String(selected.value)] = [x,y,x+w,y+h]
  // Keep invalid inputs visible; the backend rejects Apply until corrected.
  rectangles.value = { ...rectangles.value, [String(selected.value)]: [x,y,x+w,y+h] }
}
function move(g, index, delta) {
  const order = draft.value.devices[g.id].order
  if (index+delta < 0 || index+delta >= order.length) return
  ;[order[index],order[index+delta]] = [order[index+delta],order[index]]
}
async function apply() {
  saving.value = true
  try {
    const res = await saveSyncMapping(copy(draft.value), props.data.revision)
    if (res.error) error.value = res.error
    else emit('saved')
  } catch (e) { error.value = String(e) }
  finally { saving.value = false }
}
async function identify() {
  const res = await identifySyncChannel(selected.value)
  if (res.error) error.value = res.error
}
function onKey(e) {
  if (e.key === 'Escape' && !saving.value) { e.stopPropagation(); emit('close') }
  if (e.key !== 'Tab') return
  const nodes = [...dialog.value.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),[tabindex="0"]')]
  const first=nodes[0], last=nodes.at(-1)
  if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) { e.preventDefault(); last?.focus() }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
}
// Direct movement is optional; exact numeric fields remain the accessible path.
let dragging = null
function dragStart(e, id) {
  if (saving.value || !Number.isFinite(e.clientX)) return
  selected.value = Number(id)
  const svg=e.currentTarget.ownerSVGElement
  dragging={ id:String(id), start:[e.clientX,e.clientY], rect:[...rectangles.value[id]], bounds:svg.getBoundingClientRect() }
  e.preventDefault()
}
function dragMove(e) {
  if (!dragging) return
  const {id,start,rect,bounds}=dragging
  const [x,y,r,b]=rect
  const dx=Math.max(-x,Math.min(1-r,(e.clientX-start[0])/bounds.width))
  const dy=Math.max(-y,Math.min(1-b,(e.clientY-start[1])/bounds.height))
  const next=[x+dx,y+dy,r+dx,b+dy]
  rectangles.value={...rectangles.value,[id]:next}
  draft.value.overrides[id]=next
}
function dragEnd() { dragging=null }
onMounted(async () => {
  await nextTick(); dialog.value?.querySelector('select')?.focus()
  window.addEventListener('pointermove',dragMove); window.addEventListener('pointerup',dragEnd)
  regenerate()
})
onUnmounted(() => {
  alive=false; generation++; clearTimeout(previewTimer)
  window.removeEventListener('pointermove',dragMove); window.removeEventListener('pointerup',dragEnd)
  previousFocus?.focus()
})
const fmt = v => Number.isFinite(v) ? Math.round(v*100)/100 : ''
</script>

<template>
  <Teleport to="body">
    <div class="mapping-overlay" @click.self="!saving && emit('close')">
      <section ref="dialog" class="mapping-dialog" role="dialog" aria-modal="true" aria-labelledby="mapping-title" tabindex="-1" @keydown="onKey">
        <header><h2 id="mapping-title">{{ t('map_title') }}</h2><button :disabled="saving" @click="emit('close')">{{ t('map_cancel') }}</button></header>
        <div class="body">
          <p class="muted">{{ topo.name }} · {{ store.sync.output==='portal-selection' ? t('map_portal') : store.sync.output }}</p>
          <p v-if="hasMismatch" role="alert">{{ t('map_changed') }} <button @click="rebind">{{ t('map_rebind') }}</button></p>
          <label>{{ t('map_preset') }}<select v-model="draft.mode"><option value="legacy">{{ t('map_legacy') }}</option><option value="desk">{{ t('map_desk') }}</option></select></label>
          <div class="diagram" :style="{ aspectRatio: data.aspect || 16/9, width: 'min(100%, '+(300*(data.aspect || 16/9))+'px)' }">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" :aria-label="t('map_diagram')">
              <rect width="100" height="100" fill="var(--inset)" />
              <g v-for="ch in topo.channels" :key="ch.id">
                <rect v-if="rectangles[ch.id]?.every(Number.isFinite)" :x="rectangles[ch.id][0]*100" :y="rectangles[ch.id][1]*100" :width="(rectangles[ch.id][2]-rectangles[ch.id][0])*100" :height="(rectangles[ch.id][3]-rectangles[ch.id][1])*100" :class="{chosen:selected === ch.id}" @pointerdown="dragStart($event,ch.id)" />
              </g>
            </svg>
            <button v-for="ch in topo.channels" :key="'label'+ch.id" class="region-label" :class="{active:selected===ch.id}" :style="{left:((rectangles[ch.id][0]+rectangles[ch.id][2])*50)+'%',top:((rectangles[ch.id][1]+rectangles[ch.id][3])*50)+'%'}" @click="selected=ch.id" :aria-label="t('map_channel',{id:ch.id})">{{ ch.id }}</button>
            <span class="diagram-note">{{ t('map_diagram') }}</span>
          </div>
          <p class="muted small">{{ t('map_capture_note') }}</p>
          <div v-if="usesDesk" class="two">
            <label>{{ t('map_height') }} (%)<input type="number" min="5" max="100" :value="fmt(draft.height*100)" @input="draft.height=Number($event.target.value)/100" /></label>
            <label>{{ t('map_inset') }} (%)<input type="number" min="0" max="95" :value="fmt(draft.inset*100)" @input="draft.inset=Number($event.target.value)/100" /></label>
          </div>
          <fieldset v-for="g in topo.devices" :key="g.id">
            <legend>{{ g.name }}</legend>
            <p class="muted small">{{ t('map_capabilities',{channels:g.channels.length,segments:g.segments}) }}</p>
            <label v-if="draft.devices[g.id]">{{ t('map_device_layout') }}<select v-model="draft.devices[g.id].mode"><option value="inherit">{{ t('map_inherit') }}</option><option value="legacy">{{ t('map_legacy') }}</option><option value="desk">{{ t('map_desk') }}</option></select></label>
            <template v-if="deviceUsesDesk(g) && draft.devices[g.id]">
              <label>{{ t('map_widths') }}<select v-model="draft.devices[g.id].strategy"><option value="coverage" :disabled="!g.coverage_available">{{ t('map_reported') }}</option><option value="equal">{{ t('map_equal') }}</option></select></label>
              <p class="muted small">{{ g.coverage_available ? t('map_verify_coverage') : t('map_no_coverage') }}</p>
              <label class="check"><input v-model="draft.devices[g.id].reverse" type="checkbox" />{{ t('map_reverse') }}</label>
              <div class="two"><label>{{ t('map_source_start') }} (%)<input type="number" min="0" max="100" :value="fmt(draft.devices[g.id].start*100)" @input="draft.devices[g.id].start=Number($event.target.value)/100" /></label><label>{{ t('map_source_end') }} (%)<input type="number" min="0" max="100" :value="fmt(draft.devices[g.id].end*100)" @input="draft.devices[g.id].end=Number($event.target.value)/100" /></label></div>
              <div v-for="(id,i) in draft.devices[g.id].order" :key="id" class="channel-row">
                <button :class="{active:selected===id}" @click="selected=id">{{ t('map_channel',{id}) }} · {{ draft.overrides[id] ? t('map_manual') : t('map_auto') }}</button>
                <button :disabled="i===0" :aria-label="t('map_move_left')" @click="move(g,i,-1)">←</button><button :disabled="i===g.channels.length-1" :aria-label="t('map_move_right')" @click="move(g,i,1)">→</button>
              </div>
            </template>
            <button @click="resetDevice(g)">{{ t('map_reset_device') }}</button>
          </fieldset>
          <label>{{ t('map_selected') }}<select v-model="selected"><option v-for="ch in topo.channels" :key="ch.id" :value="ch.id">{{ ch.name }} · {{ t('map_channel',{id:ch.id}) }}</option></select></label>
          <div class="two">
            <label v-for="(key,i) in ['map_left','map_top','map_width','map_rect_height']" :key="key">{{ t(key) }} (%)<input type="number" min="0" max="100" step="0.1" :value="fmt(fields[i])" @input="editRect(i,$event.target.value)" /></label>
          </div>
          <div class="actions"><span class="muted">{{ manual ? t('map_manual') : t('map_auto') }}</span><button @click="resetChannel(selected)">{{ t('map_reset_channel') }}</button><button :disabled="store.sync.running" @click="identify">{{ t('map_identify') }}</button></div>
          <p class="small muted">{{ t('map_identify_note') }}</p>
          <p v-for="w in warnings" :key="w" class="warning">{{ t('map_warning_'+w) }}</p>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
        </div>
        <footer><button :disabled="saving" @click="resetAll">{{ t('map_reset_all') }}</button><span /><button :disabled="saving" @click="emit('close')">{{ t('map_cancel') }}</button><button class="primary" :disabled="saving || pending || !!error || hasMismatch" @click="apply">{{ saving ? t('map_saving') : t('map_apply') }}</button></footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.mapping-overlay{position:fixed;inset:0;z-index:100;background:var(--overlay);display:flex;align-items:flex-end;justify-content:center;color:var(--ink);font:16px 'IBM Plex Sans',sans-serif}
.mapping-dialog{background:var(--sheet);border:1px solid var(--sheet-line);border-radius:16px 16px 0 0;width:min(700px,100%);max-height:94vh;display:flex;flex-direction:column;outline:none}
header,footer{display:flex;gap:10px;align-items:center;padding:14px 18px;flex:none}header{justify-content:space-between;border-bottom:1px solid var(--sheet-line)}footer{border-top:1px solid var(--sheet-line)}footer span{flex:1}h2{font-size:21px;margin:0}.body{padding:0 18px 16px;overflow:auto;min-height:0}label{display:flex;flex-direction:column;gap:6px;margin:12px 0}.check{flex-direction:row;align-items:center}.check input{width:auto}input,select,button{font:inherit;color:var(--ink);background:var(--inset);border:1px solid var(--panel-line);border-radius:7px;padding:9px;min-width:0}input,select{width:100%}select{appearance:none;background:var(--inset);color:var(--ink)}option{background:var(--inset);color:var(--ink)}button{cursor:pointer;min-height:40px}button:disabled{opacity:.5;cursor:default}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.primary{background:var(--accent);color:var(--on-accent)}.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}.diagram{position:relative;border:1px solid var(--panel-line);border-radius:7px;overflow:hidden;margin-top:15px}.diagram{margin-left:auto;margin-right:auto}.region-label{position:absolute;transform:translate(-50%,-50%);padding:2px 5px;min-height:24px;font-size:13px;line-height:1;z-index:2}.diagram svg{width:100%;height:100%;display:block}.diagram g rect{fill:var(--accent);fill-opacity:.1;stroke:var(--ink-3);stroke-width:1;vector-effect:non-scaling-stroke;cursor:move}.diagram g rect.chosen{stroke:var(--accent);stroke-width:3;fill-opacity:.2}.diagram-note{position:absolute;top:8px;left:8px;font-size:12px;color:var(--ink-3);pointer-events:none}.muted{color:var(--ink-3)}.small{font-size:13px;line-height:1.5}.error{color:var(--danger)}.warning{color:var(--accent-text);font-size:14px}fieldset{border:1px solid var(--panel-line);border-radius:9px;margin:16px 0;padding:12px}legend{padding:0 5px}.channel-row,.actions{display:flex;gap:7px;align-items:center;margin:7px 0;flex-wrap:wrap}.channel-row button:first-child{flex:1;text-align:left}.active{border-color:var(--accent)}@media(max-width:420px){.two{grid-template-columns:1fr}.mapping-dialog{max-height:98vh}footer{flex-wrap:wrap}}@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
