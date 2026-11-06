<script setup>
import { onMounted, ref } from 'vue'
import Icon from '../components/icons/Icon.vue'
import FieldInput from '../components/base/FieldInput.vue'
import AppButton from '../components/base/AppButton.vue'
import ToggleSwitch from '../components/base/ToggleSwitch.vue'
import { useTheme } from '../composables/useTheme.js'
import { useI18n } from '../composables/useI18n.js'
import { store, apiReady, loadConfig, saveSettings, setBridgeIp, disconnectBridge } from '../store/index.js'

const emit = defineEmits(['repair'])

const { theme } = useTheme()
const { t, setLang } = useI18n()

const config = ref({ bridge_ip: '', has_client_key: false, columns: 2, language: 'en', start_minimized: false })
const changingIp = ref(false)
const newIp = ref('')

onMounted(async () => {
  await apiReady()
  config.value = await loadConfig()
  setLang(config.value.language) // config.json is authoritative on load
})

async function confirmChangeIp() {
  if (!newIp.value.trim()) return
  await setBridgeIp(newIp.value.trim())
  config.value.bridge_ip = newIp.value.trim()
  changingIp.value = false
}

async function onDisconnect() {
  if (!window.confirm(t('disconnect_confirm_msg'))) return
  await disconnectBridge()
}

function setLanguage(code) {
  config.value.language = code
  setLang(code)
  saveSettings({ language: code })
}

function setColumns(n) {
  config.value.columns = n
  saveSettings({ columns: n })
}

function setStartMinimized(value) {
  config.value.start_minimized = value
  saveSettings({ start_minimized: value })
}
</script>

<template>
  <div class="setup-page">
    <div class="card">
      <div class="bridge-row">
        <span class="dot" :style="{ background: store.bridgeOk ? 'var(--ok)' : 'var(--danger)' }" />
        <span class="ip">{{ config.bridge_ip }}</span>
        <span class="note">CLIP v2 &middot; {{ config.has_client_key ? t('paired_label') : t('no_client_key_label') }}</span>
      </div>
      <FieldInput v-if="changingIp" v-model="newIp" placeholder="192.168.x.x" />
      <div class="bridge-actions">
        <AppButton v-help="{ action: t('help_change_ip'), reason: t('help_busy') }" v-if="!changingIp" variant="pill" @click="changingIp = true; newIp = config.bridge_ip">{{ t('change_ip_btn') }}</AppButton>
        <AppButton v-help="{ action: t('help_confirm_ip'), reason: t('help_busy') }" v-else variant="pill" @click="confirmChangeIp">{{ t('confirm_btn') }}</AppButton>
        <AppButton v-help="{ action: t('help_repair'), reason: t('help_busy') }" variant="pill" @click="emit('repair')">{{ t('repair_short_btn') }}</AppButton>
        <AppButton v-help="{ action: t('help_disconnect'), reason: t('help_busy') }" variant="danger" @click="onDisconnect">{{ t('disconnect_short_btn') }}</AppButton>
      </div>
    </div>

    <div class="card appearance">
      <div class="row">
        <span class="label">{{ t('theme_label') }}</span>
        <div class="chips">
          <button v-help="{ action: t('help_theme'), reason: t('help_busy') }" type="button" class="chip" :class="{ selected: theme === 'dark' }" @click="theme = 'dark'">
            <Icon name="moon" :size="13" /> {{ t('theme_dark') }}
          </button>
          <button v-help="{ action: t('help_theme'), reason: t('help_busy') }" type="button" class="chip" :class="{ selected: theme === 'light' }" @click="theme = 'light'">
            <Icon name="sun" :size="13" /> {{ t('theme_light') }}
          </button>
        </div>
      </div>

      <div class="row">
        <span class="label">{{ t('language_label') }}</span>
        <div class="chips">
          <button v-help="{ action: t('help_language'), reason: t('help_busy') }" type="button" class="chip" :class="{ selected: config.language === 'en' }" @click="setLanguage('en')">English</button>
          <button v-help="{ action: t('help_language'), reason: t('help_busy') }" type="button" class="chip" :class="{ selected: config.language === 'fr' }" @click="setLanguage('fr')">Francais</button>
        </div>
      </div>

      <div class="row">
        <span class="label">{{ t('columns_label') }}</span>
        <div class="chips">
          <button
            v-help="{ action: t('help_columns'), reason: t('help_busy') }"
            v-for="n in [1, 2, 3, 4]"
            :key="n"
            type="button"
            class="chip mono"
            :class="{ selected: config.columns === n }"
            @click="setColumns(n)"
          >
            {{ n }}
          </button>
        </div>
      </div>

      <div class="row">
        <span class="label">{{ t('start_min_label') }}</span>
        <ToggleSwitch :help="t('help_minimized')" :model-value="config.start_minimized" :width="38" :height="21" :knob="15" @update:model-value="setStartMinimized" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.setup-page {
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
.bridge-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 3px;
  flex: none;
}
.ip {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  color: var(--ink);
  flex: 1;
}
.note {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--ink-4);
}
.bridge-actions {
  display: flex;
  gap: 6px;
}
.bridge-actions :deep(.btn) {
  flex: 1;
  border-radius: 8px;
  padding: 7px;
  font-size: 12px;
}
.appearance {
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
.chips {
  display: flex;
  gap: 6px;
}
.chip {
  padding: 5px 11px;
  border-radius: 6px;
  font-size: 12px;
  background: var(--inset);
  color: var(--ink-3);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}
.chip.mono {
  font-family: 'IBM Plex Mono', monospace;
  width: 26px;
  justify-content: center;
  padding: 5px 0;
}
.chip.selected {
  background: var(--accent);
  color: var(--on-accent);
}
</style>
