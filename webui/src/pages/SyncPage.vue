<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import ContentPreview from '../components/ContentPreview.vue'
import LiveChannelPreview from '../components/LiveChannelPreview.vue'
import MappingEditor from '../components/MappingEditor.vue'
import DragBar from '../components/base/DragBar.vue'
import { useI18n } from '../composables/useI18n.js'
import {
  apiReady,
  store,
  initSync,
  syncPreview,
  startSync,
  stopSync,
  setSyncOutput,
  setSyncSaturation,
  setSyncFps,
  getSyncMapping,
  refreshSyncStatus,
  chooseSyncArea,
} from '../store/index.js'

const { t } = useI18n()

const FPS_OPTIONS = [20, 25, 30, 40, 50]
const PLACEHOLDER = 'var(--inset)'

const errorMsg = ref('')
const mappingData = ref(null), editor = ref(false), loading = ref(false), fpsBusy = ref(false), toggleBusy = ref(false)
const canStart = computed(() => !!mappingData.value && !mappingData.value.problem && !loading.value && store.sync.outputs.includes(store.sync.output) && store.sync.areas.some(a=>a.id===store.sync.configId))
const sortedChannels = computed(() => mappingData.value?.topology.channels || [])
const previewColors = ref([])
const boostPct = computed(() => Math.round((store.sync.saturation - 1) * 50))

let previewTimer = null, alive = true, statusBusy = false, mapRequest = 0

onMounted(async () => {
  try {
    await apiReady()
    await initSync()
    await loadMapping()
    if (alive) {
      previewTimer = setInterval(poll, 250)
      await poll()
    }
  } catch (e) { errorMsg.value = String(e) }
})
onUnmounted(() => { alive = false; mapRequest++; clearInterval(previewTimer) })
async function loadMapping() {
  const request = ++mapRequest
  loading.value = true
  try {
    const result = await getSyncMapping()
    if (!alive || request !== mapRequest) return
    if (result.error) { errorMsg.value = result.error; mappingData.value = null }
    else { mappingData.value = result; errorMsg.value = result.problem || '' }
  } catch (e) { if (alive) errorMsg.value = String(e) }
  finally { if (alive && request === mapRequest) loading.value = false }
}
async function poll() {
  if (statusBusy || !alive) return
  statusBusy = true
  try {
    const status = await refreshSyncStatus()
    if (!alive) return
    if (status.error) errorMsg.value = status.error
    previewColors.value = status.running ? await syncPreview() : []
  } catch (e) { if (alive) errorMsg.value = String(e) }
  finally { statusBusy = false }
}
async function onToggle() {
  if (toggleBusy.value) return
  toggleBusy.value = true
  errorMsg.value = ''
  try {
    const res = store.sync.running ? await stopSync() : await startSync()
    if (res.error) errorMsg.value = res.error
    await poll()
  } catch (e) { errorMsg.value = String(e) }
  finally { toggleBusy.value = false }
}
async function changeContext(change) {
  if (loading.value) return
  loading.value = true
  try {
    const result = await change()
    if (result?.error) errorMsg.value = result.error
    else await loadMapping()
  } catch (e) { errorMsg.value = String(e) }
  finally { loading.value = false }
}
async function onOutputChange(e) {
  await changeContext(() => setSyncOutput(e.target.value))
}
async function onAreaChange(e) {
  await changeContext(() => chooseSyncArea(e.target.value))
}
async function reloadContext() {
  await changeContext(async () => { await initSync(true) })
  if (!previewTimer && alive) previewTimer = setInterval(poll, 250)
}
function openEditor(event) { event.currentTarget.focus(); editor.value = true }
async function saved() { editor.value = false; await loadMapping() }

function commitBoost(pct) {
  setSyncSaturation(Math.round((1 + pct / 50) * 10) / 10)
}

async function setFps(n) {
  if (fpsBusy.value) return
  fpsBusy.value = true
  try {
    const res = await setSyncFps(n)
    if (res.error) errorMsg.value = res.error
  } catch (e) { errorMsg.value = String(e) }
  finally { fpsBusy.value = false }
}
</script>

<template>
  <div class="sync-page">
    <div class="card">
      <label class="context-label">{{ t('map_area') }}
        <select :value="store.sync.configId" :disabled="store.sync.running || loading || fpsBusy || toggleBusy" @change="onAreaChange"><option v-if="!store.sync.areas.some(a=>a.id===store.sync.configId)" :value="store.sync.configId" disabled>{{ t('map_unavailable') }}</option><option v-for="area in store.sync.areas" :key="area.id" :value="area.id">{{ area.name }}</option></select>
      </label>
      <div class="label-row"><span>{{ t('map_title') }}</span><button v-help="{ action: t('help_topology'), reason: loading || fpsBusy || toggleBusy ? t('help_busy') : !mappingData ? t('help_no_mapping') : mappingData.problem || t('help_display_missing') }" :disabled="loading" @click="reloadContext">{{ t('map_refresh') }}</button></div>
      <div v-if="mappingData" class="mapping-screen" :style="{aspectRatio:mappingData.aspect || 16/9,width:'min(100%, '+(250*(mappingData.aspect || 16/9))+'px)'}">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" :aria-label="t('map_diagram')">
          <rect width="100" height="100" fill="var(--inset)" />
          <rect v-for="(ch,i) in sortedChannels" :key="ch.id" :x="mappingData.rectangles[ch.id][0]*100" :y="mappingData.rectangles[ch.id][1]*100" :width="(mappingData.rectangles[ch.id][2]-mappingData.rectangles[ch.id][0])*100" :height="(mappingData.rectangles[ch.id][3]-mappingData.rectangles[ch.id][1])*100" :fill="previewColors[i] || 'var(--accent)'" :fill-opacity="store.sync.state === 'running' ? .8 : .25" stroke="var(--ink-3)" stroke-width="1" vector-effect="non-scaling-stroke" />
        </svg>
      </div>
      <ContentPreview :sampling="store.sync.state === 'running' ? store.sync.sampling : null" :aspect="mappingData?.aspect || 16/9" />
      <LiveChannelPreview :channels="sortedChannels" :colors="previewColors" :running="store.sync.state === 'running'" />
      <button v-help="{ action: t('help_mapping'), reason: loading || fpsBusy || toggleBusy ? t('help_busy') : !mappingData ? t('help_no_mapping') : mappingData.problem || t('help_display_missing') }" :disabled="!mappingData || loading || fpsBusy || toggleBusy" @click="openEditor">{{ t('map_edit') }}</button>
      <p class="note">{{ t('map_capture_note') }}</p>
    </div>
    <MappingEditor v-if="editor && mappingData" :data="mappingData" :live-colors="previewColors" :live-running="store.sync.state === 'running'" @close="editor=false" @saved="saved" />

    <div class="card options">
      <div class="row">
        <span class="label">{{ t('sync_monitor') }}</span>
        <select class="output-select" :value="store.sync.output" :disabled="store.sync.running || loading || fpsBusy || toggleBusy" @change="onOutputChange">
          <option v-if="!store.sync.outputs.includes(store.sync.output)" :value="store.sync.output" disabled>{{ store.sync.output }} ({{ t('map_unavailable') }})</option>
          <option v-for="o in store.sync.outputs" :key="o" :value="o">{{ o==='portal-selection' ? t('map_portal') : o }}</option>
        </select>
      </div>

      <div class="row">
        <span class="label">{{ t('sync_saturation') }}</span>
        <DragBar
          class="boost-slider"
          :model-value="boostPct"
          fill="var(--accent)"
          height="8px"
          radius="4px"
          @update:model-value="setSyncSaturation(Math.round((1 + $event / 50) * 10) / 10)"
          @change="commitBoost"
        />
        <span class="boost-value">{{ store.sync.saturation.toFixed(1) }}</span>
      </div>

      <div class="row">
        <span class="label">{{ t('sync_fps_label') }}</span>
        <div class="fps-chips">
          <button
            v-help="{ action: t('help_fps'), reason: t('help_busy') }"
            v-for="n in FPS_OPTIONS"
            :key="n"
            type="button"
            class="fps-chip"
            :disabled="fpsBusy || loading || ['starting','stopping','identifying'].includes(store.sync.state)"
            :class="{ selected: store.sync.fps === n }"
            @click="setFps(n)"
          >
            {{ n }}
          </button>
        </div>
      </div>
    </div>

    <button v-help="{ action: t(store.sync.running ? 'help_stop' : 'help_start'), reason: fpsBusy || toggleBusy || loading || store.sync.state === 'stopping' ? t('help_busy') : !mappingData ? t('help_no_mapping') : mappingData.problem || t('help_display_missing') }" type="button" class="primary-action" :class="{ running: store.sync.running }" :disabled="(!store.sync.running && !canStart) || store.sync.state === 'stopping' || fpsBusy || toggleBusy" @click="onToggle">
      {{ store.sync.running ? t('sync_stop_full') : t('sync_start_full') }}
    </button>

    <div v-if="errorMsg" class="error">{{ errorMsg }}</div>
    <div class="note" role="status" aria-live="polite">{{ t('map_state_'+store.sync.state) }}</div>
  </div>
</template>

<style scoped>
.mapping-screen{margin:auto;border:1px solid var(--panel-line);border-radius:8px;overflow:hidden}.mapping-screen svg{width:100%;height:100%;display:block}.context-label{display:flex;flex-direction:column;gap:6px}select,button{font:inherit}select{appearance:none;background:var(--inset);color:var(--ink)}option{background:var(--inset);color:var(--ink)}button{cursor:pointer;color:var(--ink);background:var(--inset);border:1px solid var(--panel-line);border-radius:7px;padding:8px}button:disabled{opacity:.5;cursor:default}button:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.context-label select{background:var(--inset);color:var(--ink);padding:8px;border:1px solid var(--panel-line);border-radius:7px}.label-row{display:flex;align-items:center;justify-content:space-between}.note{line-height:1.5}@media(prefers-reduced-motion:reduce){*{transition:none!important}}

.sync-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card {
  border: 1px solid var(--panel-line);
  border-radius: 12px;
  background: var(--panel);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.label-row {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--ink-4);
}
.preview {
  height: 104px;
  border-radius: 9px;
  display: grid;
  overflow: hidden;
}
.preview-block {
  transition: background 0.15s linear;
}
.channel-grid {
  display: grid;
  gap: 6px;
}
.channel-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.channel-bar {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  transition: background 0.15s linear;
}
.channel-name {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  color: var(--ink-4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.options {
  gap: 12px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.label {
  flex: 1;
  color: var(--ink-2);
}
.output-select {
  background: var(--inset);
  border: 1px solid var(--panel-line);
  border-radius: 8px;
  padding: 5px 10px;
  font-size: 12px;
  font-family: inherit;
  color: var(--ink-2);
}
.boost-slider {
  width: 150px;
  flex: none;
}
.boost-value {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  width: 30px;
  text-align: right;
  color: var(--ink-2);
}
.fps-chips {
  display: flex;
  gap: 6px;
}
.fps-chip {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--inset);
  color: var(--ink-3);
  border: none;
  cursor: pointer;
}
.fps-chip.selected {
  background: var(--accent);
  color: var(--on-accent);
}
.primary-action {
  border-radius: 10px;
  padding: 12px;
  text-align: center;
  font-weight: 600;
  border: none;
  cursor: pointer;
  background: var(--accent);
  color: var(--on-accent);
}
.primary-action.running {
  background: var(--danger-bg);
  color: var(--danger);
}
.error {
  font-size: 12px;
  color: var(--danger);
}
.note {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  color: var(--ink-4);
}
</style>
