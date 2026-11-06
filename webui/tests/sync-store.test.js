import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { store, initSync, setSyncOutput, chooseSyncArea } from '../src/store/index.js'
let api
beforeEach(() => {
  store.sync.initialized = false
  store.sync.running = false
  store.sync.configId = 'old'
  store.sync.output = 'old-monitor'
  api = {
    list_entertainment_configs: async () => ({ data: [{ id: 'new', name: 'Desk' }] }),
    get_config: async () => ({ sync_area_id: 'new', sync_output: 'DP-3' }),
    get_channel_names: async () => ({ data: [{ channel_id: 7, name: 'Strip' }] }),
    list_outputs: async () => ({ data: ['DP-3'] }),
    sync_status: async () => ({ running: false, state: 'idle' }),
    save_settings: async () => ({ ok: true }),
  }
  globalThis.window = { pywebview: { api } }
})
test('failed monitor save preserves the displayed profile context', async () => {
  api.save_settings = async () => ({ error: 'disk full' })
  assert.equal((await setSyncOutput('DP-3')).error, 'disk full')
  assert.equal(store.sync.output, 'old-monitor')
})
test('monitor context changes only after persistence completes', async () => {
  let finish
  api.save_settings = () => new Promise(resolve => { finish = resolve })
  const pending = setSyncOutput('DP-3')
  assert.equal(store.sync.output, 'old-monitor')
  finish({ ok: true }); await pending
  assert.equal(store.sync.output, 'DP-3')
})
test('failed area save preserves the selected area', async () => {
  api.save_settings = async () => ({ error: 'disk full' })
  assert.equal((await chooseSyncArea('new')).error, 'disk full')
  assert.equal(store.sync.configId, 'old')
})
test('live capture context cannot be changed through the store', async () => {
  store.sync.running = true
  assert.ok((await chooseSyncArea('new')).error)
  assert.ok((await setSyncOutput('DP-3')).error)
})
test('failed discovery can be retried without reopening the application', async () => {
  api.list_entertainment_configs = async () => ({ error: 'offline' })
  await assert.rejects(initSync(), /offline/)
  assert.equal(store.sync.initialized, false)
  api.list_entertainment_configs = async () => ({ data: [{ id: 'new' }] })
  await initSync()
  assert.equal(store.sync.configId, 'new')
})
test('explicit refresh discovers newly connected monitors', async () => {
  await initSync()
  api.list_outputs = async () => ({ data: ['DP-3', 'DP-4'] })
  await initSync(true)
  assert.deepEqual([...store.sync.outputs], ['DP-3', 'DP-4'])
})
test('refresh preserves active worker context over stale saved preferences', async () => {
  api.sync_status = async () => ({ running: true, state: 'running', fps: 25, area: 'active', output: 'active-monitor' })
  await initSync()
  assert.equal(store.sync.configId, 'active')
  assert.equal(store.sync.output, 'active-monitor')
  assert.equal(store.sync.fps, 25)
})

test('sampling telemetry updates atomically and clears when the source disappears', async () => {
  const { refreshSyncStatus } = await import('../src/store/index.js')
  const sampling={enabled:true,crop:[0,.1,1,.9],rectangles:{'7':[0,.7,1,.9]},revision:4}
  api.sync_status=async()=>({running:true,state:'running',sampling})
  await refreshSyncStatus()
  assert.deepEqual(JSON.parse(JSON.stringify(store.sync.sampling)),sampling)
  api.sync_status=async()=>({running:false,state:'idle'})
  await refreshSyncStatus()
  assert.equal(store.sync.sampling,null)
})

test('failed processing persistence preserves visible settings', async () => {
  const {setSyncProcessing}=await import('../src/store/index.js')
  store.sync.processing={saturation:1.6,brightness:1,gamma:1,response_ms:0}
  api.set_sync_processing=async()=>({error:'disk full'})
  assert.equal((await setSyncProcessing({brightness:.5})).error,'disk full')
  assert.equal(store.sync.processing.brightness,1)
})
test('rapid processing edits are serialized and preserve partial patches', async () => {
  const {setSyncProcessing}=await import('../src/store/index.js')
  let finish, calls=0, saved={saturation:1.6,brightness:1,gamma:1,response_ms:0}
  api.set_sync_processing=async patch=>{
    calls++
    if(calls===1)await new Promise(resolve=>{finish=resolve})
    saved={...saved,...patch};return {ok:true,processing:{...saved}}
  }
  const first=setSyncProcessing({response_ms:300}), second=setSyncProcessing({gamma:1.5})
  await new Promise(resolve=>setImmediate(resolve))
  assert.equal(calls,1)
  finish();await Promise.all([first,second])
  assert.equal(store.sync.processing.response_ms,300)
  assert.equal(store.sync.processing.gamma,1.5)
})
test('refresh uses active processing rather than stale saved controls', async () => {
  const options={saturation:2,brightness:.7,gamma:1.5,response_ms:250}
  api.sync_status=async()=>({running:true,state:'running',fps:30,processing:options})
  await initSync()
  assert.deepEqual(JSON.parse(JSON.stringify(store.sync.processing)),options)
  assert.equal(store.sync.saturation,2)
})
