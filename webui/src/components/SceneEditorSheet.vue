<script setup>
import { ref } from 'vue'
import Sheet from './Sheet.vue'
import FieldInput from './base/FieldInput.vue'
import AppButton from './base/AppButton.vue'
import { useI18n } from '../composables/useI18n.js'

const props = defineProps({
  isNew: { type: Boolean, default: false },
  initialName: { type: String, default: '' },
  groupName: { type: String, default: '' },
  lamps: { type: Array, required: true }, // current group.lamps - read-only "captured from"
})
const emit = defineEmits(['save', 'cancel', 'delete'])

const { t } = useI18n()

const name = ref(props.initialName)

function save() {
  emit('save', { name: name.value })
}
</script>

<template>
  <Sheet @close="emit('cancel')">
    <div class="title">
      {{ isNew ? t('new_scene_title_fmt', { group: groupName }) : t('title_edit_scene') }}
    </div>

    <div class="field-block">
      <label class="field-label">{{ t('name') }}</label>
      <FieldInput v-model="name" :placeholder="t('name')" />
    </div>

    <div class="field-block">
      <label class="field-label">{{ t('captured_from_label') }}</label>
      <div class="lamp-list">
        <div v-for="lamp in lamps" :key="lamp.id" class="lamp-row">
          <div class="swatch" :style="{ background: lamp.color }" />
          <span class="lamp-name">{{ lamp.name }}</span>
          <span class="lamp-state">{{ lamp.on ? `${lamp.bri}%` : t('state_off') }}</span>
        </div>
      </div>
    </div>

    <div class="note">{{ t('scene_editor_note') }}</div>

    <div class="footer">
      <AppButton v-help="{ action: t('help_delete'), reason: t('help_busy') }" v-if="!isNew" variant="danger" @click="emit('delete')">{{ t('delete_btn') }}</AppButton>
      <div class="spacer" />
      <AppButton v-help="{ action: t('help_cancel'), reason: t('help_busy') }" variant="pill" @click="emit('cancel')">{{ t('cancel') }}</AppButton>
      <AppButton v-help="{ action: t('help_save'), reason: t('help_busy') }" variant="accent" @click="save">{{ t('save_scene_btn') }}</AppButton>
    </div>
  </Sheet>
</template>

<style scoped>
.title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
}
.field-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--ink-4);
  text-transform: uppercase;
}
.lamp-list {
  max-height: 250px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.lamp-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 9px;
  background: var(--panel);
}
.swatch {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  flex: none;
}
.lamp-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lamp-state {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--ink-4);
  flex: none;
}
.note {
  font-size: 12px;
  color: var(--ink-4);
}
.footer {
  display: flex;
  align-items: center;
  gap: 8px;
}
.spacer {
  flex: 1;
}
</style>
