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
