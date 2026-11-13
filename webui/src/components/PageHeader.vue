<script setup>
import Icon from './icons/Icon.vue'
import { useI18n } from '../composables/useI18n.js'

const HEADERS = {
  rooms: { kickerKey: 'kicker_rooms', titleKey: 'nav_rooms', addLabelKey: 'add_room' },
  zones: { kickerKey: 'kicker_zones', titleKey: 'nav_zones', addLabelKey: 'add_zone' },
  scenes: { kickerKey: 'kicker_scenes', titleKey: 'nav_scenes', addLabelKey: 'scene_default' },
  sync: { kickerKey: 'kicker_sync', titleKey: 'sync_hdr', addLabelKey: null },
  setup: { kickerKey: 'kicker_setup', titleKey: 'nav_setup', addLabelKey: null },
}

defineProps({ page: { type: String, required: true } })
defineEmits(['add', 'refresh'])

const { t } = useI18n()
</script>

<template>
  <header class="page-header">
    <div class="left">
      <div class="kicker">{{ t(HEADERS[page].kickerKey) }}</div>
      <div class="title">{{ t(HEADERS[page].titleKey) }}</div>
    </div>
    <button v-help="{ action: t('help_add'), reason: t('help_busy') }" v-if="HEADERS[page].addLabelKey" type="button" class="add-btn" @click="$emit('add')">
      <Icon name="plus" :size="12" />
      {{ t(HEADERS[page].addLabelKey) }}
    </button>
    <button v-help="{ action: t('help_refresh'), reason: t('help_busy') }" type="button" class="refresh-btn" @click="$emit('refresh')">
      <Icon name="refresh" :size="15" />
    </button>
  </header>
</template>

<style scoped>
.page-header {
  padding: 16px 16px 12px;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  border-bottom: 1px solid var(--line);
}
.left {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.kicker {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-4);
}
.title {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--ink);
}
.add-btn,
.refresh-btn {
  background: var(--pill);
  border: 1px solid var(--pill-line);
  border-radius: 8px;
  color: var(--ink-2);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}
.add-btn {
  padding: 6px 11px;
  font-size: 12px;
  font-family: inherit;
}
.refresh-btn {
  width: 34px;
  height: 30px;
  justify-content: center;
  flex: none;
}
</style>
