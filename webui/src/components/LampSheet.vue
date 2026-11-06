<script setup>
import { computed, ref } from 'vue'
import Sheet from './Sheet.vue'
import Icon from './icons/Icon.vue'
import ToggleSwitch from './base/ToggleSwitch.vue'
import DragBar from './base/DragBar.vue'
import { lampKind } from '../lib/lampKind.js'
import { dimmed, hexToRgb, hsvToRgb, rgbToHueSat, rgbToHex } from '../lib/colors.js'
import { rgbToXy, mirekToHex } from '../lib/huecolor.js'
import { writeLampOn, updateLampBriLocal, writeLampBri, writeLampColor, writeLampMirek } from '../store/index.js'
import { useI18n } from '../composables/useI18n.js'

const { t } = useI18n()

const props = defineProps({
  lamp: { type: Object, required: true },
  groupName: { type: String, default: '' },
})
const emit = defineEmits(['close'])

// Colour wheel geometry - redesign/README.md "Lamp sheet": R=84, centre 93,93,
// hue 0 at 3 o'clock, increasing clockwise (conic-gradient(from 90deg, ...)).
const R = 84
const CENTER = 93
const WHITES = [500, 400, 346, 286, 233, 182, 153].map((mirek) => ({ mirek, hex: mirekToHex(mirek, 100) }))

const wheelEl = ref(null)

const handlePos = computed(() => {
  const [h, s] = rgbToHueSat(...hexToRgb(props.lamp.color))
  const rad = (h * Math.PI) / 180
  return { x: CENTER + Math.cos(rad) * s * R, y: CENTER + Math.sin(rad) * s * R }
})

const sliderFill = computed(() => dimmed(props.lamp.color, props.lamp.bri))

function onWheelDown(e) {
  const rect = wheelEl.value.getBoundingClientRect()

  function apply(ev) {
    const dx = ev.clientX - (rect.left + CENTER)
    const dy = ev.clientY - (rect.top + CENTER)
    const sat = Math.min(1, Math.hypot(dx, dy) / R)
    let hue = (Math.atan2(dy, dx) * 180) / Math.PI
    if (hue < 0) hue += 360
    const rgb = hsvToRgb(hue, sat, 1)
    const hex = rgbToHex(rgb)
    const xy = rgbToXy(...rgb)
    writeLampColor(props.lamp.id, hex, xy)
  }
  apply(e)

  function onMove(ev) {
    apply(ev)
  }
  function onUp(ev) {
    apply(ev)
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}
</script>

<template>
  <Sheet @close="emit('close')">
    <div class="header">
      <Icon :name="lampKind(lamp.archetype)" :size="26" :style="{ color: lamp.color }" />
      <div class="title-block">
        <div class="name">{{ lamp.name }}</div>
        <div class="meta">{{ lamp.archetype.toUpperCase() }} &middot; {{ lamp.on ? t('meta_on') : t('meta_off') }}</div>
      </div>
      <ToggleSwitch :model-value="lamp.on" @update:model-value="writeLampOn(lamp.id, $event)" />
      <button v-help="{ action: t('close'), reason: t('help_busy') }" type="button" class="close-btn" @click="emit('close')">{{ t('close') }}</button>
    </div>

    <div class="body">
      <div
        ref="wheelEl"
        class="wheel"
        @pointerdown="onWheelDown"
      >
        <div
          class="handle"
          :style="{ left: handlePos.x + 'px', top: handlePos.y + 'px', background: lamp.color }"
        />
      </div>

      <div class="right-col">
        <div class="brightness-block">
          <div class="label-row">
            <span>{{ t('brightness') }}</span>
            <span class="value">{{ lamp.bri }}%</span>
          </div>
          <DragBar
            :model-value="lamp.bri"
            :fill="sliderFill"
            height="34px"
            radius="10px"
            @update:model-value="updateLampBriLocal(lamp.id, $event)"
            @change="writeLampBri(lamp.id, $event)"
          />
        </div>

        <div class="whites-block">
          <div class="label-row"><span>{{ t('white') }}</span></div>
          <div class="whites-row">
            <button
              v-help="{ action: t('help_white', {kelvin: Math.round(1000000 / w.mirek)}), reason: t('help_busy') }"
              v-for="w in WHITES"
              :key="w.mirek"
              type="button"
              class="swatch"
              :style="{ background: w.hex }"
              @click="writeLampMirek(lamp.id, w.mirek)"
            />
          </div>
        </div>

        <div class="in-block">
          <div class="label-row"><span>{{ t('in_label') }}</span></div>
          <div class="in-value">{{ groupName }}</div>
        </div>
      </div>
    </div>
  </Sheet>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.title-block {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
}
.meta {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--ink-4);
}
.close-btn {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-3);
  border: 1px solid var(--pill-line);
  border-radius: 6px;
  padding: 3px 7px;
  background: transparent;
  cursor: pointer;
}
.body {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.wheel {
  flex: 0 0 186px;
  width: 186px;
  height: 186px;
  border-radius: 93px;
  cursor: crosshair;
  position: relative;
  background:
    radial-gradient(circle at center, #ffffff 0%, rgba(255, 255, 255, 0) 66%),
    conic-gradient(from 90deg, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
}
.handle {
  position: absolute;
  width: 22px;
  height: 22px;
  border-radius: 11px;
  border: 2px solid #fff;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.7);
  margin: -11px 0 0 -11px;
  pointer-events: none;
}
.right-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.label-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-4);
}
.brightness-block .value {
  font-size: 14px;
  color: var(--ink);
}
.brightness-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.whites-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.whites-row {
  display: flex;
  gap: 5px;
}
.swatch {
  flex: 1;
  height: 30px;
  border-radius: 7px;
  border: none;
  padding: 0;
  cursor: pointer;
}
.in-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.in-value {
  font-size: 13px;
  color: var(--ink-2);
}
</style>
