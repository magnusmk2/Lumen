<script setup>
import { useI18n } from '../../composables/useI18n.js'
const { t } = useI18n()
defineProps({ modelValue: { type: Boolean, required: true } })
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <button v-help="t('help_member')"
    type="button"
    class="checkbox"
    :class="{ checked: modelValue }"
    @click="emit('update:modelValue', !modelValue)"
  >
    <svg v-if="modelValue" viewBox="0 0 18 18" width="12" height="12">
      <path d="M4 9l3 3 7-7" fill="none" stroke="var(--on-accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>
</template>

<style scoped>
.checkbox {
  width: 18px;
  height: 18px;
  border-radius: 5px;
  border: 1px solid var(--toggle-off);
  background: var(--inset);
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex: none;
}
.checkbox.checked {
  background: var(--accent);
  border-color: var(--accent);
}
</style>
