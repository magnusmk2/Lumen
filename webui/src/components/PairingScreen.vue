<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import AppMark from './icons/AppMark.vue'
import FieldInput from './base/FieldInput.vue'
import AppButton from './base/AppButton.vue'
import { apiReady, discoverBridge, startPairing, pairStatus } from '../store/index.js'
import { useI18n } from '../composables/useI18n.js'

const { t } = useI18n()

const props = defineProps({
  canCancel: { type: Boolean, default: false },
})
const emit = defineEmits(['paired', 'cancel'])

const ip = ref('')
const discoveryDone = ref(false)
const manualMode = ref(false)
const pairing = ref(false)
const countdown = ref(30)
const errorMsg = ref('')

let pollTimer = null

onMounted(async () => {
  await apiReady()
  const result = await discoverBridge()
  if (result.ip) ip.value = result.ip
  discoveryDone.value = true
})

onUnmounted(() => clearInterval(pollTimer))

async function onPair() {
  const target = ip.value.trim()
  if (!target) return
  errorMsg.value = ''
  pairing.value = true
  countdown.value = 30
  const res = await startPairing(target)
  if (res.error) {
    errorMsg.value = res.error
    pairing.value = false
    return
  }
  pollTimer = setInterval(async () => {
    const s = await pairStatus()
    if (s.status === 'waiting') {
      countdown.value = s.seconds_left
    } else if (s.status === 'success') {
      clearInterval(pollTimer)
      emit('paired')
    } else if (s.status === 'error') {
      clearInterval(pollTimer)
      pairing.value = false
      errorMsg.value = s.message
    }
  }, 1000)
}
</script>

<template>
  <div class="pairing-screen">
    <AppMark :size="34" />
    <div class="heading">
      <div class="title">{{ t('pairing_title') }}</div>
      <div class="subtitle">{{ t('pairing_subtitle') }}</div>
    </div>

    <div class="steps">
      <div class="step" :class="ip ? 'done' : 'active'">
        <span class="index">1</span>
        <span class="text">{{ ip ? t('step_found') : (discoveryDone ? t('none_found') : t('searching')) }}</span>
        <span class="value">{{ ip }}</span>
      </div>
      <div class="step" :class="pairing ? 'active' : 'pending'">
        <span class="index">2</span>
        <span class="text">{{ t('step_press') }}</span>
        <span v-if="pairing" class="value">{{ t('seconds_left_fmt', { s: countdown }) }}</span>
      </div>
      <div class="step pending">
        <span class="index">3</span>
        <span class="text">{{ t('step_keys') }}</span>
      </div>
    </div>

    <div class="progress"><div class="fill" :style="{ width: (pairing ? (countdown / 30) * 100 : 0) + '%' }" /></div>

    <div v-if="errorMsg" class="error">{{ errorMsg }}</div>

    <FieldInput v-if="manualMode" v-model="ip" placeholder="192.168.x.x" />

    <div class="footer">
      <AppButton v-help="{ action: t('help_manual_ip'), reason: pairing ? t('help_busy') : t('help_ip_missing') }" variant="pill" @click="manualMode = !manualMode">{{ t('enter_ip_manually_btn') }}</AppButton>
      <AppButton v-help="{ action: t('help_pair'), reason: pairing ? t('help_busy') : t('help_ip_missing') }" variant="accent" :disabled="pairing || !ip" @click="onPair">{{ t('pair') }}</AppButton>
    </div>

    <button v-help="{ action: t('help_nav_setup'), reason: pairing ? t('help_busy') : t('help_ip_missing') }" v-if="canCancel" type="button" class="cancel-link" @click="emit('cancel')">{{ t('cancel') }}</button>
  </div>
</template>

<style scoped>
.pairing-screen {
  width: 100vw;
  height: 100vh;
  padding: 40px 44px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 22px;
  background: var(--app-bg);
  color: var(--ink);
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 13px;
}
.heading {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.title {
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.subtitle {
  font-size: 14px;
  color: var(--ink-3);
}
.steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 11px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
}
.step .index {
  width: 16px;
  flex: none;
  text-align: center;
}
.step .text {
  flex: 1;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 13px;
}
.step.done {
  background: var(--panel);
  border: 1px solid var(--panel-line);
}
.step.done .index {
  color: var(--ok);
}
.step.done .value {
  color: var(--ink-2);
  font-size: 12px;
}
.step.active {
  border: 1px solid var(--pill-line);
}
.step.active .index,
.step.active .value {
  color: var(--accent-text);
}
.step.pending {
  background: var(--row-off);
  border: 1px solid var(--line);
  color: var(--ink-4);
}
.step.pending .index {
  color: var(--ink-4);
}
.progress {
  height: 4px;
  border-radius: 2px;
  background: var(--line);
  overflow: hidden;
}
.progress .fill {
  height: 100%;
  background: var(--accent);
  transition: width 1s linear;
}
.error {
  font-size: 12px;
  color: var(--danger);
}
.footer {
  display: flex;
  gap: 8px;
}
.footer :deep(.btn) {
  flex: 1;
  border-radius: 10px;
  padding: 11px;
}
.cancel-link {
  align-self: center;
  background: none;
  border: none;
  color: var(--ink-4);
  font-size: 12px;
  cursor: pointer;
}
</style>
