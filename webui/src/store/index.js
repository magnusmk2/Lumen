import { reactive } from 'vue'
import { sampleRoomGroups, sampleZoneGroups, sampleSceneSections } from '../data/sample.js'
import { buildViewModel } from '../lib/snapshot.js'
import { xyToHex, mirekToHex } from '../lib/huecolor.js'

export const store = reactive({
  roomGroups: sampleRoomGroups,
  zoneGroups: sampleZoneGroups,
  sceneSections: sampleSceneSections,
  bridgeOk: true,
  configured: true,

  sync: {
    initialized: false,
    sampling: null,
    areas: [],
    state: "idle",
    error: null,
    running: false,
    fps: 30,
    output: '',
    saturation: 1.6,
    configId: null,
    channels: [], // [{ channel_id, name }]
    outputs: [],
  },
})

function api() {
  return window.pywebview?.api ?? null
}

export function apiReady() {
  return new Promise((resolve) => {
    const ready = () => window.pywebview?.api?.get_snapshot
    if (ready()) {
      resolve()
      return
    }
    const timer = setInterval(() => {
      if (ready()) {
        clearInterval(timer)
        resolve()
      }
    }, 100)
  })
}

export async function loadSnapshot() {
  const a = api()
  if (!a?.get_snapshot) return // dev-in-a-plain-browser: keep sample data

  const result = await a.get_snapshot()
  if (result.error === 'not_configured') {
    store.bridgeOk = false
    store.configured = false
    return
  }
  if (result.error) {
    store.bridgeOk = false
    return
  }

  const vm = buildViewModel(result.data)
  store.roomGroups = vm.roomGroups
  store.zoneGroups = vm.zoneGroups
  store.sceneSections = vm.sceneSections
  store.bridgeOk = true
  store.configured = true
}

export function initSnapshot() {
  apiReady().then(loadSnapshot)
}

function findLamp(id) {
  for (const group of [...store.roomGroups, ...store.zoneGroups]) {
    const lamp = group.lamps.find((l) => l.id === id)
    if (lamp) return lamp
  }
  return null
}

let reloadTimer = null
function scheduleReload() {
  clearTimeout(reloadTimer)
  reloadTimer = setTimeout(loadSnapshot, 700)
}

function patchLampFromSSE(fragment) {
  const lamp = findLamp(fragment.id)
  if (!lamp) return
  if (fragment.on) lamp.on = !!fragment.on.on
  if (fragment.dimming) lamp.bri = Math.round(fragment.dimming.brightness)
  if (fragment.color?.xy) lamp.color = xyToHex(fragment.color.xy.x, fragment.color.xy.y, 100)
  else if (fragment.color_temperature?.mirek) lamp.color = mirekToHex(fragment.color_temperature.mirek, 100)
}

/** Call once on app start, alongside initSnapshot(). */
export function initSSE() {
  window.__lumenSSE = (payload) => {
    if (payload.type === 'update') {
      for (const light of payload.lights) patchLampFromSSE(light)
    } else if (payload.type === 'change') {
      scheduleReload()
    }
  }
}

export function updateLampBriLocal(id, bri) {
  const lamp = findLamp(id)
  if (lamp) {
    lamp.bri = bri
    lamp.on = bri > 0
  }
}

export function writeLampOn(id, on) {
  const lamp = findLamp(id)
  if (lamp) lamp.on = on
  api()?.put_light(id, { on: { on } })
}

export function writeLampBri(id, bri) {
  updateLampBriLocal(id, bri)
  const payload = bri > 0 ? { on: { on: true }, dimming: { brightness: bri } } : { on: { on: false } }
  api()?.put_light(id, payload)
}

export function writeLampColor(id, hex, xy) {
  const lamp = findLamp(id)
  if (lamp) {
    lamp.color = hex
    lamp.on = true
  }
  api()?.put_light(id, { on: { on: true }, color: { xy: { x: xy[0], y: xy[1] } } })
}

export function writeLampMirek(id, mirek) {
  const lamp = findLamp(id)
  if (lamp) {
    lamp.color = mirekToHex(mirek, 100)
    lamp.on = true
  }
  api()?.put_light(id, { on: { on: true }, color_temperature: { mirek } })
}

function writeToGroupOrLamps(group, payload) {
  if (group.groupedLightId) {
    api()?.put_grouped_light(group.groupedLightId, payload)
  } else {
    for (const l of group.lamps) api()?.put_light(l.id, payload)
  }
}

export function writeGroupOn(group, on) {
  for (const l of group.lamps) l.on = on
  writeToGroupOrLamps(group, { on: { on } })
}

export function updateGroupBriLocal(group, pct) {
  for (const l of group.lamps) {
    l.bri = pct
    l.on = pct > 0
  }
}

export function writeGroupBri(group, pct) {
  updateGroupBriLocal(group, pct)
  writeToGroupOrLamps(group, pct > 0 ? { on: { on: true }, dimming: { brightness: pct } } : { on: { on: false } })
}

export async function recallScene(sceneId) {
  await api()?.recall_scene(sceneId)
  setTimeout(loadSnapshot, 600)
}

export async function discoverBridge() {
  return (await api()?.discover_bridge()) ?? { error: 'no_api' }
}

export async function startPairing(ip) {
  return (await api()?.start_pairing(ip)) ?? { error: 'no_api' }
}

export async function pairStatus() {
  return (await api()?.pair_status()) ?? { status: 'idle' }
}

export async function loadConfig() {
  return (await api()?.get_config()) ?? {}
}

export async function saveSettings(patch) {
  return (await api()?.save_settings(patch)) ?? { error: 'no_api' }
}

export async function setBridgeIp(ip) {
  await api()?.set_bridge_ip(ip)
  await loadSnapshot()
}

export async function disconnectBridge() {
  await api()?.disconnect()
  store.configured = false
  store.bridgeOk = false
}

export async function saveGroup(kind, groupId, name, lightIds) {
  const res = (await api()?.save_group(kind, groupId, name, lightIds)) ?? { error: 'no_api' }
  if (!res.error) await loadSnapshot()
  return res
}

export async function deleteGroup(kind, groupId) {
  const res = (await api()?.delete_group(kind, groupId)) ?? { error: 'no_api' }
  if (!res.error) await loadSnapshot()
  return res
}

export async function saveScene(sceneId, name, groupId, groupKind) {
  const res = (await api()?.save_scene(sceneId, name, groupId, groupKind)) ?? { error: 'no_api' }
  if (!res.error) await loadSnapshot()
  return res
}

export async function deleteScene(sceneId) {
  const res = (await api()?.delete_scene(sceneId)) ?? { error: 'no_api' }
  if (!res.error) await loadSnapshot()
  return res
}

async function listEntertainmentConfigs() {
  return (await api()?.list_entertainment_configs()) ?? { error: 'no_api' }
}

async function getChannelNames(configId) {
  const result = await api()?.get_channel_names(configId)
  return result?.data ?? []
}

async function listOutputs() {
  const result = await api()?.list_outputs()
  return result?.data ?? []
}

async function syncStatus() {
  return (await api()?.sync_status()) ?? { running: false, error: null }
}

export async function syncPreview() {
  const result = await api()?.sync_preview()
  return result?.colors ?? []
}


export async function initSync(force = false) {
  if (store.sync.initialized && !force) return
  const cfgs = await listEntertainmentConfigs()
  if (cfgs.error) throw new Error(cfgs.error)
  const cfg = await loadConfig()
  const status = await syncStatus()
  store.sync.areas = cfgs.data || []
  store.sync.configId = status.running && status.area ? status.area : (cfg.sync_area_id || store.sync.areas[0]?.id || null)
  store.sync.channels = store.sync.configId ? await getChannelNames(store.sync.configId) : []
  store.sync.outputs = await listOutputs()
  store.sync.output = status.running && status.output ? status.output : (cfg.sync_output || store.sync.outputs[0] || '')
  store.sync.saturation = cfg.sync_saturation ?? 1.6
  store.sync.fps = status.running ? status.fps : (cfg.sync_fps ?? 30)
  store.sync.running = status.running
  store.sync.state = status.state || 'idle'
  store.sync.error = status.error
  store.sync.initialized = true
}

export async function startSync() {
  const { output, saturation, fps, configId } = store.sync
  const res = (await api()?.start_sync(output, saturation, fps, configId)) ?? { error: 'no_api' }
  if (!res.error) { store.sync.running = true; store.sync.state = "starting" }
  return res
}

export async function stopSync() {
  const res = (await api()?.stop_sync()) ?? { error: 'no_api' }
  await refreshSyncStatus()
  return res
}

export async function setSyncOutput(output) {
  if (store.sync.running) return { error: 'Stop sync before changing monitor' }
  const res = await saveSettings({ sync_output: output })
  if (!res.error) store.sync.output = output
  return res
}

export function setSyncSaturation(saturation) {
  store.sync.saturation = saturation
  saveSettings({ sync_saturation: saturation })
  if (store.sync.running) api()?.set_sync_saturation(saturation)
}

export async function setSyncFps(fps) {
  store.sync.fps = fps
  saveSettings({ sync_fps: fps })
  if (store.sync.running) {
    // "Changing fps requires stop/start" - redesign/README.md
    await stopSync()
    const res = await startSync()
    if (res.error) return res
  }
  return { ok: true }
}

export async function getSyncMapping() {
  return await api()?.get_sync_mapping(store.sync.configId, store.sync.output) ?? { error: 'no_api' }
}
export async function previewSyncMapping(profile) {
  return await api()?.preview_sync_mapping(store.sync.configId, store.sync.output, profile) ?? { error: 'no_api' }
}
export async function saveSyncMapping(profile, revision) {
  return await api()?.save_sync_mapping(store.sync.configId, store.sync.output, profile, revision) ?? { error: 'no_api' }
}
export async function identifySyncChannel(channel) {
  return await api()?.identify_sync_channel(store.sync.configId, channel) ?? { error: 'no_api' }
}
export async function refreshSyncStatus() {
  const status = await syncStatus()
  Object.assign(store.sync, { running: status.running, state: status.state || 'idle', error: status.error, sampling: status.sampling || null })
  return status
}
export async function chooseSyncArea(id) {
  if (store.sync.running) return { error: 'Stop sync before changing area' }
  const channels = await getChannelNames(id)
  const res = await saveSettings({ sync_area_id: id })
  if (!res.error) {
    store.sync.configId = id
    store.sync.channels = channels
  }
  return res
}
