<script setup>
import { reactive, ref } from 'vue'
import Sheet from './Sheet.vue'
import FieldInput from './base/FieldInput.vue'
import Checkbox from './base/Checkbox.vue'
import AppButton from './base/AppButton.vue'
import Icon from './icons/Icon.vue'
import { lampKind } from '../lib/lampKind.js'
import { useI18n } from '../composables/useI18n.js'

const props = defineProps({
  kind: { type: String, required: true }, // 'room' | 'zone'
  isNew: { type: Boolean, default: false },
  initialName: { type: String, default: '' },
  // { id, name, archetype, selected, currentRoomName? }
  candidates: { type: Array, required: true },
})
const emit = defineEmits(['save', 'cancel', 'delete'])

const { t } = useI18n()

const HINT_KEY = { room: 'room_hint', zone: 'zone_hint' }
const MEMBER_LABEL_KEY = { room: 'room_devices', zone: 'zone_lights' }
const NEW_TITLE_KEY = { room: 'title_new_room', zone: 'title_new_zone' }
const BADGE_KEY = { room: 'badge_room', zone: 'badge_zone' }

const name = ref(props.initialName)
const members = reactive(props.candidates.map((c) => ({ ...c })))

function toggle(member) {
  member.selected = !member.selected
}

function save() {
  emit('save', { name: name.value, selectedIds: members.filter((m) => m.selected).map((m) => m.id) })
}
</script>

<template>
  <Sheet @close="emit('cancel')">
    <div class="header">
      <div class="title">{{ isNew ? t(NEW_TITLE_KEY[kind]) : t('edit_group_title_fmt', { name: initialName }) }}</div>
      <span class="badge" :style="{ color: `var(--badge-${kind})`, borderColor: `var(--badge-${kind})` }">{{ t(BADGE_KEY[kind]) }}</span>
    </div>
    <div class="hint">{{ t(HINT_KEY[kind]) }}</div>

    <div class="field-block">
      <label class="field-label">{{ t('name') }}</label>
      <FieldInput v-model="name" :placeholder="t('name')" />
    </div>

    <div class="field-block">
      <label class="field-label">{{ t(MEMBER_LABEL_KEY[kind]).toUpperCase() }}</label>
      <div class="member-list">
        <div
          v-for="m in members"
          :key="m.id"
          class="member-row"
          :class="{ selected: m.selected }"
          @click="toggle(m)"
        >
          <Checkbox :model-value="m.selected" @update:model-value="toggle(m)" />
          <Icon :name="lampKind(m.archetype)" :size="18" style="color: var(--ink-3)" />
          <span class="member-name">{{ m.name }}</span>
          <span v-if="kind === 'room' && m.currentRoomName" class="in-room">{{ t('in_room_fmt', { room: m.currentRoomName }) }}</span>
        </div>
      </div>
    </div>

    <div class="footer">
      <AppButton v-help="{ action: t('help_delete'), reason: t('help_busy') }" v-if="!isNew" variant="danger" @click="emit('delete')">{{ t('delete_btn') }}</AppButton>
      <div class="spacer" />
      <AppButton v-help="{ action: t('help_cancel'), reason: t('help_busy') }" variant="pill" @click="emit('cancel')">{{ t('cancel') }}</AppButton>
      <AppButton v-help="{ action: t('help_save'), reason: t('help_busy') }" variant="accent" @click="save">{{ t('save') }}</AppButton>
    </div>
  </Sheet>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
}
.badge {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid;
  flex: none;
}
.hint {
  font-size: 11px;
  color: var(--ink-4);
  text-wrap: pretty;
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
}
.member-list {
  max-height: 250px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.member-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 9px;
  background: var(--row-off);
  cursor: pointer;
}
.member-row.selected {
  background: var(--pill);
}
.member-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.in-room {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--ink-4);
  flex: none;
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
