<script setup>
import { computed } from 'vue'
import ToggleSwitch from './base/ToggleSwitch.vue'
import DragBar from './base/DragBar.vue'
import LampRow from './LampRow.vue'
import SceneTile from './SceneTile.vue'
import { groupTint, groupPercent } from '../lib/colors.js'
import { useI18n } from '../composables/useI18n.js'

const { t } = useI18n()

const props = defineProps({
  group: { type: Object, required: true }, // { id, name, kind: 'room'|'zone'|'ungrouped', lamps, scenes }
  expanded: { type: Boolean, default: false },
})
const emit = defineEmits([
  'update:expanded',
  'edit',
  'master-toggle',
  'group-brightness',
  'change:group-brightness',
  'new-scene',
  'recall-scene',
  'click-lamp',
  'update:lamp-on',
  'update:lamp-bri',
  'change:lamp-bri',
])

const BADGE = {
  room: { labelKey: 'badge_room', color: 'var(--badge-room)' },
  zone: { labelKey: 'badge_zone', color: 'var(--badge-zone)' },
  ungrouped: { labelKey: 'badge_ungrouped', color: 'var(--badge-ungrouped)' },
}

const badge = computed(() => BADGE[props.group.kind] ?? BADGE.ungrouped)
const onCount = computed(() => props.group.lamps.filter((l) => l.on).length)
const anyOn = computed(() => onCount.value > 0)
const pct = computed(() => groupPercent(props.group.lamps))
const tint = computed(() => groupTint(props.group.lamps, 'var(--pill-line)'))

function onMasterToggle() {
  emit('master-toggle', !anyOn.value)
}
</script>

<template>
  <div class="card">
    <div class="header">
      <div class="title-block" @click="emit('update:expanded', !expanded)">
        <div class="name">{{ group.name }}</div>
        <span class="badge" :style="{ color: badge.color, borderColor: badge.color }">{{ t(badge.labelKey) }}</span>
        <div class="summary">
          {{ t('on_count_fmt', { on: onCount, total: group.lamps.length }) }} &middot; {{ t('scenes_count_fmt', { n: group.scenes.length }) }}
        </div>
      </div>
      <button v-help="{ action: t('help_edit'), reason: t('help_busy') }" type="button" class="edit-btn" @click="emit('edit', group)">{{ t('edit_btn') }}</button>
      <ToggleSwitch :model-value="anyOn" @update:model-value="onMasterToggle" />
    </div>

    <div class="group-brightness">
      <div class="label-row">
        <span>{{ t('group_label') }}</span>
        <span class="value">{{ pct === null ? t('state_off') : `${pct}%` }}</span>
      </div>
      <DragBar
        :model-value="pct ?? 0"
        :fill="tint"
        height="20px"
        radius="8px"
        @update:model-value="emit('group-brightness', $event)"
        @change="emit('change:group-brightness', $event)"
      />
    </div>

    <div v-if="expanded" class="body">
      <div class="section-head">
        <span>{{ t('scenes_section') }}</span>
        <div class="rule" />
        <button v-help="{ action: t('help_new_scene'), reason: t('help_busy') }" type="button" class="new-action" @click="emit('new-scene', group)">+ {{ t('new_label') }}</button>
      </div>
      <div class="scene-grid">
        <SceneTile
          v-for="scene in group.scenes"
          :key="scene.id"
          :scene="scene"
          height="54px"
          @recall="emit('recall-scene', $event)"
        />
      </div>

      <div class="section-head">
        <span>{{ t('lights_section') }}</span>
        <div class="rule" />
      </div>
      <div class="lamp-list">
        <LampRow
          v-for="lamp in group.lamps"
          :key="lamp.id"
          :lamp="lamp"
          @click-name="emit('click-lamp', { lamp, group })"
          @update:on="emit('update:lamp-on', { id: lamp.id, on: $event })"
          @update:bri="emit('update:lamp-bri', { id: lamp.id, bri: $event })"
          @change:bri="emit('change:lamp-bri', { id: lamp.id, bri: $event })"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  border: 1px solid var(--panel-line);
  border-radius: 12px;
  background: var(--panel);
  overflow: hidden;
}
.header {
  padding: 12px 12px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.title-block {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  cursor: pointer;
}
.name {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.badge {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.1em;
  padding: 1px 5px;
  border-radius: 3px;
  border: 1px solid;
  width: fit-content;
}
.summary {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  color: var(--ink-4);
}
.edit-btn {
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
  flex: none;
}
.group-brightness {
  margin: 0 12px 11px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.label-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--ink-4);
}
.label-row .value {
  color: var(--ink-2);
}
.body {
  border-top: 1px solid var(--line);
  padding: 11px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--ink-4);
}
.section-head .rule {
  flex: 1;
  height: 1px;
  background: var(--line);
}
.new-action {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--accent-text);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}
.scene-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 7px;
}
.lamp-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
</style>
