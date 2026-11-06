<script setup>
import { useI18n } from '../../composables/useI18n.js'
const { t } = useI18n()
import { computed } from 'vue'

const props = defineProps({
  help: { type: String, default: '' },
  disabledReason: { type: String, default: '' },
  modelValue: { type: Boolean, required: true },
  width: { type: Number, default: 44 },
  height: { type: Number, default: 24 },
  knob: { type: Number, default: 18 },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const knobLeft = computed(() => (props.modelValue ? props.width - props.knob - 3 : 3))

function onClick() {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
}
</script>

<template>
  <button v-help="{action: help || t(modelValue ? 'help_off' : 'help_on'), reason: disabledReason || t('help_busy')}"
    type="button"
    class="toggle"
    :class="{ on: modelValue, disabled }"
    :style="{ width: width + 'px', height: height + 'px', borderRadius: height / 2 + 'px' }"
    :disabled="disabled"
    @click="onClick"
  >
    <span
      class="knob"
      :style="{
        width: knob + 'px',
        height: knob + 'px',
        borderRadius: knob / 2 + 'px',
        top: (height - knob) / 2 + 'px',
        left: knobLeft + 'px',
      }"
    />
  </button>
</template>

<style scoped>
.toggle {
  position: relative;
  border: none;
  padding: 0;
  background: var(--toggle-off);
  cursor: pointer;
  flex: none;
}
.toggle.on {
  background: var(--accent);
}
.toggle.disabled {
  cursor: default;
  opacity: 0.5;
}
.knob {
  position: absolute;
  background: #fff;
  transition: left 0.12s ease;
}
</style>
