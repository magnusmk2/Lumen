<script setup>
import { computed } from 'vue'
import { useI18n } from '../composables/useI18n.js'
const props = defineProps({ channels: { type: Array, default: () => [] }, colors: { type: Array, default: () => [] }, running: Boolean })
const { t } = useI18n()
const displayed = computed(() => props.channels.map((ch, index) => ({ ...ch, color: props.colors[index] }))
  .sort((a,b) => (a.position?.x || 0) - (b.position?.x || 0) || a.id-b.id))
</script>
<template>
  <section class="live-preview" :aria-label="t('map_live_title')">
    <div class="heading">{{ t('map_live_title') }}</div>
    <div class="swatches">
      <div v-for="ch in displayed" :key="ch.id" class="channel">
        <div class="swatch" :style="{background:running && ch.color ? ch.color : 'var(--inset)'}" />
        <div class="caption">{{ t('map_channel',{id:ch.id}) }}</div>
        <div class="value">{{ running && ch.color ? ch.color.toUpperCase() : '—' }}</div>
      </div>
    </div>
    <p>{{ running && colors.length ? t('map_live_applied') : t('map_live_start') }}</p>
  </section>
</template>
<style scoped>
.live-preview{border:1px solid var(--panel-line);border-radius:9px;padding:12px;margin:10px 0;color:var(--ink)}.heading{font-size:14px;font-weight:600;margin-bottom:10px}.swatches{display:flex;gap:8px;overflow-x:auto;padding-bottom:3px}.channel{flex:1;min-width:65px}.swatch{height:44px;border:1px solid var(--ink-4);border-radius:6px;transition:background-color .15s linear}.caption{font-size:12px;color:var(--ink-2);margin-top:6px}.value{font:11px 'IBM Plex Mono',monospace;color:var(--ink-3);margin-top:3px}p{margin:10px 0 0;font-size:12px;line-height:1.5;color:var(--ink-3)}@media(prefers-reduced-motion:reduce){.swatch{transition:none}}
</style>
