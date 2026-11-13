<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { store, setSyncPreferences } from '../store/index.js'
import { useI18n } from '../composables/useI18n.js'
const props=defineProps({disabled:Boolean})
const emit=defineEmits(['busy'])
const {t}=useI18n()
const draft=reactive({}), busy=ref(false), error=ref('')
watch(()=>store.sync.preferences,p=>Object.assign(draft,p),{deep:true,immediate:true})
const unavailable=computed(()=>props.disabled || busy.value || store.sync.running)
const sceneValid=computed(()=>store.sync.stopScenes.some(s=>s.id===draft.stop_scene))
async function save(patch){
  if(unavailable.value)return
  busy.value=true;emit('busy',true);error.value=''
  try{
    const res=await setSyncPreferences(patch)
    if(res.error)error.value=res.error
  }finally{Object.assign(draft,store.sync.preferences);busy.value=false;emit('busy',false)}
}
</script>
<template>
  <details class="session-controls">
    <summary>{{ t('session_title') }}</summary>
    <p class="help">{{ store.sync.running ? t('session_stop_first') : t('session_help') }}</p>
    <label class="check"><input id="sync-on-launch" v-model="draft.start_on_launch" type="checkbox" :disabled="unavailable" aria-describedby="sync-on-launch-help" @change="save({start_on_launch:draft.start_on_launch})" />{{ t('sync_on_launch') }}</label>
    <p id="sync-on-launch-help" class="help">{{ t('sync_on_launch_help') }}</p>
    <label class="check"><input id="quit-lights-off" v-model="draft.quit_lights_off" type="checkbox" :disabled="unavailable" aria-describedby="quit-lights-off-help" @change="save({quit_lights_off:draft.quit_lights_off})" />{{ t('quit_lights_off') }}</label>
    <p id="quit-lights-off-help" class="help">{{ t('quit_lights_off_help') }}</p>
    <label>{{ t('capture_quality') }}
      <select id="capture-quality" v-model="draft.quality" :disabled="unavailable" @change="save({quality:draft.quality})">
        <option value="economy">{{ t('quality_economy') }}</option><option value="balanced">{{ t('quality_balanced') }}</option><option value="detailed">{{ t('quality_detailed') }}</option>
      </select>
    </label>
    <p class="help">{{ t('capture_quality_help') }}</p>
    <label class="check"><input id="portal-remember" v-model="draft.portal_remember" type="checkbox" :disabled="unavailable || (store.sync.portal.version<4 && !draft.portal_remember)" @change="save({portal_remember:draft.portal_remember})" />{{ t('portal_remember') }}</label>
    <p class="help">{{ t(store.sync.portal.version>=4 ? 'portal_remember_help' : 'portal_no_persistence') }}</p>
    <p class="help">{{ t(store.sync.portal.types & 2 ? 'portal_window_yes' : 'portal_window_no') }}</p>
    <label>{{ t('finish_scene_label') }}
      <select id="stop-scene" v-model="draft.stop_scene" :disabled="unavailable || !store.sync.stopScenes.length" @change="save({stop_scene:draft.stop_scene})">
        <option :value="null">{{ t('finish_choose_scene') }}</option>
        <option v-for="s in store.sync.stopScenes" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </label>
    <p class="help">{{ t(store.sync.stopScenes.length ? 'finish_scene_help' : 'finish_no_scenes') }}</p>
    <label>{{ t('finish_label') }}
      <select id="stop-behavior" v-model="draft.stop_behavior" :disabled="unavailable" @change="save({stop_behavior:draft.stop_behavior})">
        <option value="leave">{{ t('finish_leave') }}</option><option value="restore">{{ t('finish_restore') }}</option><option value="scene" :disabled="!sceneValid">{{ t('finish_scene') }}</option>
      </select>
    </label>
    <p class="help">{{ t('finish_help') }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </details>
</template>
<style scoped>
.session-controls{padding:10px 0;color:var(--ink-2);font-size:14px}summary{cursor:pointer;padding:8px 0}label{display:flex;flex-direction:column;gap:7px;margin:12px 0}.check{flex-direction:row;align-items:center}.help{font-size:13px;line-height:1.5;color:var(--ink-3);margin:6px 0}select{appearance:none;font:inherit;color:var(--ink);background:var(--inset);border:1px solid var(--panel-line);border-radius:7px;padding:8px;width:100%;min-width:0}option{background:var(--inset);color:var(--ink)}select:disabled,input:disabled{opacity:.5}summary:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.error{color:var(--danger);font-size:13px}
</style>
