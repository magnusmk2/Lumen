<script setup>
import AppMark from './icons/AppMark.vue'
import Icon from './icons/Icon.vue'
import { useTheme } from '../composables/useTheme.js'
import { useI18n } from '../composables/useI18n.js'

defineProps({
  page: { type: String, required: true },
  bridgeOk: { type: Boolean, default: true },
})
const emit = defineEmits(['navigate'])

const { theme, toggle } = useTheme()
const { t } = useI18n()

const NAV_ITEMS = [
  { key: 'rooms', labelKey: 'nav_rooms' },
  { key: 'zones', labelKey: 'nav_zones' },
  { key: 'scenes', labelKey: 'nav_scenes' },
  { key: 'sync', labelKey: 'nav_sync' },
  { key: 'setup', labelKey: 'nav_setup' },
]
</script>

<template>
  <nav class="rail">
    <div class="app-mark">
      <AppMark :size="26" />
    </div>

    <button

      v-help="{ action: t('help_nav_' + item.key), reason: t('help_busy') }"

      v-for="item in NAV_ITEMS"
      :key="item.key"
      type="button"
      class="nav-item"
      :class="{ active: page === item.key }"
      @click="emit('navigate', item.key)"
    >
      <Icon :name="item.key" :size="18" />
      <span class="label">{{ t(item.labelKey) }}</span>
    </button>

    <div class="spacer" />

    <button v-help="{ action: t('help_toggle_theme'), reason: t('help_busy') }" type="button" class="theme-btn" @click="toggle">
      <Icon :name="theme === 'dark' ? 'moon' : 'sun'" :size="16" />
      <span class="label">{{ theme === 'dark' ? t('theme_dark') : t('theme_light') }}</span>
    </button>

    <div class="bridge-status">
      <span class="dot" :style="{ background: bridgeOk ? 'var(--ok)' : 'var(--danger)' }" />
      <span>{{ t('bridge_label') }}</span>
    </div>
  </nav>
</template>

<style scoped>
.rail {
  flex: 0 0 78px;
  background: var(--rail-bg);
  border-right: 1px solid var(--line);
  padding: 14px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.app-mark {
  padding-bottom: 16px;
  display: flex;
  justify-content: center;
}
.nav-item,
.theme-btn {
  padding: 9px 0;
  margin: 0 8px;
  border-radius: 9px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  border: none;
  background: transparent;
  color: var(--ink-4);
  font-family: inherit;
}
.nav-item .label,
.theme-btn .label {
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 600;
}
.nav-item.active {
  background: var(--pill);
  color: var(--accent-text);
}
.spacer {
  flex: 1;
}
.theme-btn {
  background: var(--pill);
  border: 1px solid var(--pill-line);
  margin: 0 8px 10px;
  color: var(--ink-3);
}
.bridge-status {
  margin: 0 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  color: var(--ink-5);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.06em;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 3px;
}
</style>
