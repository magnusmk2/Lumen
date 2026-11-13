<script setup>
import { computed } from 'vue'
import { useI18n } from '../composables/useI18n.js'
const props = defineProps({ sampling: Object, colors: {type:Array,default:()=>[]}, channels: {type:Array,default:()=>[]}, draftNote: Boolean, aspect: {type: Number, default:16/9} })
const { t } = useI18n()
function color(id){return props.colors[props.channels.findIndex(c=>String(c.id)===String(id))] || 'var(--accent)'}
const displayAspect=computed(()=>props.aspect>0?props.aspect:16/9)
const cropped = computed(() => props.sampling?.crop?.some((v,i)=>v!==[0,0,1,1][i]))
</script>
<template>
  <div v-if="sampling?.crop" class="content-preview">
    <div class="caption">{{ t('bars_live') }}</div>
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" :style="{aspectRatio:displayAspect}" role="img" :aria-label="t(cropped ? 'bars_active' : sampling.enabled ? 'bars_full' : 'bars_off')">
      <rect width="100" height="100" class="outside" />
      <rect :x="sampling.crop[0]*100" :y="sampling.crop[1]*100" :width="(sampling.crop[2]-sampling.crop[0])*100" :height="(sampling.crop[3]-sampling.crop[1])*100" class="picture" />
      <g v-for="(r,id) in sampling.rectangles" :key="id"><rect :style="{fill:color(id)}" :x="r[0]*100" :y="r[1]*100" :width="(r[2]-r[0])*100" :height="(r[3]-r[1])*100" class="region" /><text :x="(r[0]+r[2])*50" :y="(r[1]+r[3])*50" text-anchor="middle" dominant-baseline="central">{{ id }}</text></g>
    </svg>
    <p>{{ t(cropped ? 'bars_active' : sampling.enabled ? 'bars_full' : 'bars_off') }}</p>
    <p v-if="draftNote">{{ t('bars_draft') }}</p>
  </div>
</template>
<style scoped>
.content-preview{margin:12px 0;color:var(--ink-3);font-size:13px;line-height:1.5}.caption{margin-bottom:6px}.content-preview svg{width:100%;max-width:360px;display:block;border:1px solid var(--panel-line);border-radius:7px;overflow:hidden}.outside{fill:var(--inset)}.picture{fill:var(--panel);stroke:var(--ink-3);stroke-width:1;stroke-dasharray:3 2;vector-effect:non-scaling-stroke}.region{fill-opacity:.8;stroke:var(--accent);stroke-width:1;vector-effect:non-scaling-stroke}.content-preview text{font-size:5px;fill:white;paint-order:stroke;stroke:#000;stroke-width:.5px}.content-preview p{margin:5px 0}
</style>
