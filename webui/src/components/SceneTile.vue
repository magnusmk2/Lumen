<script setup>
import { computed } from 'vue'
import { sceneGradient } from '../lib/colors.js'
import { useI18n } from '../composables/useI18n.js'

const { t } = useI18n()

const props = defineProps({
  scene: { type: Object, required: true }, // { id, name, actions: [{ color, bri, on }] }
  height: { type: String, default: '54px' },
  showEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['recall', 'edit'])

const PILL_LINE = 'var(--pill-line)'

const background = computed(() => sceneGradient(props.scene.actions, PILL_LINE))
</script>

<template>
  <div class="tile" :style="{ height, background }" @click="emit('recall', scene)">
    <button v-help="t('help_edit')"
      v-if="showEdit"
      type="button"
      class="edit-chip"
      @click.stop="emit('edit', scene)"
    >
      {{ t('edit_btn') }}
    </button>
    <div class="name-strip">{{ scene.name }}</div>
  </div>
</template>

<style scoped>
.tile {
  position: relative;
  border-radius: 9px;
  border: 1px solid rgba(0, 0, 0, 0.25);
  overflow: hidden;
  cursor: pointer;
  display: flex;
  align-items: flex-end;
}
.name-strip {
  width: 100%;
  padding: 4px 7px;
  background: rgba(6, 7, 9, 0.62);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.edit-chip {
  position: absolute;
  top: 6px;
  right: 6px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: rgba(6, 7, 9, 0.55);
  color: #fff;
  border: none;
  border-radius: 5px;
  padding: 2px 6px;
  cursor: pointer;
}
</style>
