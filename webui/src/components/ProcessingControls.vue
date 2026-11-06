<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { store, setSyncProcessing } from '../store/index.js'
import { useI18n } from '../composables/useI18n.js'
const props = defineProps({disabled:Boolean})
const emit = defineEmits(['busy'])
const { t } = useI18n()
const busy=ref(false), error=ref(''), values=reactive({})
const fields=[
  {key:'saturation',label:'sync_saturation',help:'colour_saturation_help',min:0,max:4,step:.1,scale:1},
  {key:'response_ms',label:'colour_response',help:'colour_response_help',min:0,max:2000,step:25,scale:1},
  {key:'brightness',label:'colour_brightness',help:'colour_brightness_help',min:0,max:100,step:1,scale:100},
  {key:'gamma',label:'colour_gamma',help:'colour_gamma_help',min:.1,max:5,step:.1,scale:1},
]
const unavailable=computed(()=>busy.value || props.disabled || ['starting','stopping','identifying'].includes(store.sync.state))
function restore(){ for(const f of fields)values[f.key]=Math.round(store.sync.processing[f.key]*f.scale*100)/100 }
watch(()=>store.sync.processing, restore,{deep:true,immediate:true})
async function commit(field){
  if(unavailable.value){restore();return}
  await save({[field.key]:values[field.key] === '' ? null : Number(values[field.key])/field.scale})
}
async function save(patch){
  busy.value=true;emit('busy',true);error.value=''
  try{
    const res=await setSyncProcessing(patch)
    if(res.error)error.value=res.error
  }finally{busy.value=false;emit('busy',false);restore()}
}
function reset(){return save({saturation:1.6,brightness:1,gamma:1,response_ms:0})}
</script>
<template>
  <div class="processing-controls" :aria-busy="busy">
    <template v-for="field in fields.slice(0,1)" :key="field.key">
      <div class="processing-row">
        <label :for="'processing-'+field.key">{{ t(field.label) }}</label>
        <input :id="'processing-'+field.key" v-model.number="values[field.key]" type="range" :min="field.min" :max="field.max" :step="field.step" :disabled="unavailable" :aria-describedby="'processing-help-'+field.key" @change="commit(field)" />
        <input v-model.number="values[field.key]" type="number" :min="field.min" :max="field.max" :step="field.step" :disabled="unavailable" :aria-label="t(field.label)" :aria-describedby="'processing-help-'+field.key" @change="commit(field)" />
      </div>
      <p :id="'processing-help-'+field.key" class="help">{{ t(field.help) }}</p>
    </template>
    <details>
      <summary>{{ t('colour_title') }}</summary>
      <template v-for="field in fields.slice(1)" :key="field.key">
        <div class="processing-row">
          <label :for="'processing-'+field.key">{{ t(field.label) }}</label>
          <input :id="'processing-'+field.key" v-model.number="values[field.key]" type="range" :min="field.min" :max="field.max" :step="field.step" :disabled="unavailable" :aria-describedby="'processing-help-'+field.key" @change="commit(field)" />
          <input v-model.number="values[field.key]" type="number" :min="field.min" :max="field.max" :step="field.step" :disabled="unavailable" :aria-label="t(field.label)" :aria-describedby="'processing-help-'+field.key" @change="commit(field)" />
        </div>
        <p :id="'processing-help-'+field.key" class="help">{{ t(field.help) }}</p>
      </template>
      <button v-help="{action:t('colour_reset_help'),reason:t('help_busy')}" type="button" :disabled="unavailable" @click="reset">{{ t('colour_reset') }}</button>
    </details>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p class="help">{{ t('colour_live_help') }}</p>
  </div>
</template>
<style scoped>
.processing-controls{padding:10px 0;border-top:1px solid var(--panel-line);border-bottom:1px solid var(--panel-line)}.processing-row{display:grid;grid-template-columns:minmax(100px,1fr) minmax(70px,1fr) 76px;gap:12px;align-items:center;margin-top:10px;color:var(--ink-2);font-size:13px}.processing-row input{min-width:0;width:100%;accent-color:var(--accent);font:inherit;color:var(--ink);box-sizing:border-box}.processing-row input[type=number]{padding:7px 5px;background:var(--inset);border:1px solid var(--panel-line);border-radius:6px}.help{font-size:13px;color:var(--ink-3);line-height:1.5;margin:6px 0 10px}.error{color:var(--danger);font-size:13px}summary{cursor:pointer;color:var(--ink-2);font-size:14px;padding:8px 0}button{font:inherit;color:var(--ink);background:var(--inset);padding:8px 12px;border:1px solid var(--panel-line);border-radius:7px;cursor:pointer}button:disabled,input:disabled{opacity:.5}input:focus-visible,summary:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}@media(max-width:460px){.processing-row{grid-template-columns:minmax(70px,1fr) 76px}.processing-row label{grid-column:1/-1}}
</style>
