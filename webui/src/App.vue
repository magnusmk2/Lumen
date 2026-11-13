<script setup>
import { computed, onMounted, ref } from 'vue'
import AppTooltip from './components/AppTooltip.vue'
import NavRail from './components/NavRail.vue'
import PageHeader from './components/PageHeader.vue'
import GroupsPage from './pages/GroupsPage.vue'
import ScenesPage from './pages/ScenesPage.vue'
import SyncPage from './pages/SyncPage.vue'
import GroupEditorSheet from './components/GroupEditorSheet.vue'
import SceneEditorSheet from './components/SceneEditorSheet.vue'
import LampSheet from './components/LampSheet.vue'
import PairingScreen from './components/PairingScreen.vue'
import SetupPage from './pages/SetupPage.vue'
import {
  store,
  initSnapshot,
  initSSE,
  loadSnapshot,
  recallScene,
  saveGroup,
  deleteGroup,
  saveScene,
  deleteScene,
} from './store/index.js'
import { initI18n, useI18n } from './composables/useI18n.js'

const { t } = useI18n()

const page = ref('rooms')

onMounted(() => {
  initSnapshot()
  initSSE()
  initI18n()
  // Tray menu hooks (huectl/webapp.py's _setup_tray calls these via evaluate_js).
  window.__lumenTrayRefresh = () => loadSnapshot()
  window.__lumenTraySettings = () => {
    page.value = 'setup'
  }
})
const sheet = ref(null) // null | { type: 'group'|'scene'|'lamp', ... } - see openers below
const rePairing = ref(false) // explicit Setup > Re-pair, distinct from first-run (!store.configured)

function onPaired() {
  rePairing.value = false
  store.configured = true
  loadSnapshot()
}

function navigate(key) {
  page.value = key
  sheet.value = null // rail navigation closes any open sheet
}

function openEditGroup(group) {
  sheet.value = { type: 'group', kind: group.kind === 'zone' ? 'zone' : 'room', isNew: false, group }
}

function handleAdd() {
  if (page.value === 'rooms' || page.value === 'zones') {
    sheet.value = { type: 'group', kind: page.value === 'zones' ? 'zone' : 'room', isNew: true, group: null }
  } else if (page.value === 'scenes' && store.sceneSections.length) {
    openNewScene(store.sceneSections[0])
  }
}

function handleRefresh() {
  loadSnapshot()
}

function onClickLamp({ lamp, group }) {
  sheet.value = { type: 'lamp', lamp, groupName: group.name }
}

const candidates = computed(() => {
  if (!sheet.value) return []
  const seen = new Map()
  for (const g of store.roomGroups) {
    for (const l of g.lamps) {
      if (!seen.has(l.id)) {
        seen.set(l.id, {
          id: l.id,
          name: l.name,
          archetype: l.archetype,
          currentRoomName: g.kind === 'room' ? g.name : null,
        })
      }
    }
  }
  const memberIds = new Set(sheet.value.group?.lamps.map((l) => l.id) ?? [])
  return [...seen.values()].map((c) => ({ ...c, selected: memberIds.has(c.id) }))
})

function closeSheet() {
  sheet.value = null
}

async function onSaveGroup({ name, selectedIds }) {
  const { kind, isNew, group } = sheet.value
  await saveGroup(kind, isNew ? null : group.id, name, selectedIds)
  closeSheet()
}

async function onDeleteGroup() {
  const { kind, group } = sheet.value
  const key = kind === 'zone' ? 'del_zone_msg' : 'del_room_msg'
  if (!window.confirm(t(key, { name: group.name }))) return
  await deleteGroup(kind, group.id)
  closeSheet()
}

function findGroup(kind, id) {
  return (kind === 'zone' ? store.zoneGroups : store.roomGroups).find((g) => g.id === id)
}

function openNewScene(groupLike) {
  const group = findGroup(groupLike.kind, groupLike.id)
  sheet.value = {
    type: 'scene',
    isNew: true,
    scene: null,
    groupId: groupLike.id,
    groupKind: groupLike.kind,
    groupName: groupLike.name,
    lamps: group?.lamps ?? [],
  }
}

function openEditScene(scene) {
  const group = findGroup(scene.groupKind, scene.groupId)
  sheet.value = {
    type: 'scene',
    isNew: false,
    scene,
    groupId: scene.groupId,
    groupKind: scene.groupKind,
    groupName: group?.name ?? '',
    lamps: group?.lamps ?? [],
  }
}

async function onSaveScene({ name }) {
  const { isNew, scene, groupId, groupKind } = sheet.value
  await saveScene(isNew ? null : scene.id, name, groupId, groupKind)
  closeSheet()
}

async function onDeleteScene() {
  const { scene } = sheet.value
  if (!window.confirm(t('del_scene_msg', { name: scene.name }))) return
  await deleteScene(scene.id)
  closeSheet()
}
</script>

<template>
  <AppTooltip />
  <PairingScreen
    v-if="!store.configured || rePairing"
    :can-cancel="rePairing"
    @paired="onPaired"
    @cancel="rePairing = false"
  />
  <div v-else class="app-shell">
    <NavRail :page="page" :bridge-ok="store.bridgeOk" @navigate="navigate" />
    <div class="content">
      <PageHeader :page="page" @add="handleAdd" @refresh="handleRefresh" />
      <div class="scroll-area">
        <GroupsPage
          v-if="page === 'rooms'"
          :groups="store.roomGroups"
          @edit-group="openEditGroup"
          @click-lamp="onClickLamp"
          @new-scene="openNewScene"
        />
        <GroupsPage
          v-else-if="page === 'zones'"
          :groups="store.zoneGroups"
          @edit-group="openEditGroup"
          @click-lamp="onClickLamp"
          @new-scene="openNewScene"
        />
        <ScenesPage
          v-else-if="page === 'scenes'"
          :sections="store.sceneSections"
          @recall-scene="recallScene($event.id)"
          @new-scene="openNewScene"
          @edit-scene="openEditScene"
        />
        <SyncPage v-else-if="page === 'sync'" />
        <SetupPage v-else-if="page === 'setup'" @repair="rePairing = true" />
      </div>
    </div>

    <GroupEditorSheet
      v-if="sheet?.type === 'group'"
      :kind="sheet.kind"
      :is-new="sheet.isNew"
      :initial-name="sheet.group?.name ?? ''"
      :candidates="candidates"
      @save="onSaveGroup"
      @delete="onDeleteGroup"
      @cancel="closeSheet"
    />

    <SceneEditorSheet
      v-if="sheet?.type === 'scene'"
      :is-new="sheet.isNew"
      :initial-name="sheet.scene?.name ?? ''"
      :group-name="sheet.groupName"
      :lamps="sheet.lamps"
      @save="onSaveScene"
      @delete="onDeleteScene"
      @cancel="closeSheet"
    />

    <LampSheet
      v-if="sheet?.type === 'lamp'"
      :lamp="sheet.lamp"
      :group-name="sheet.groupName"
      @close="closeSheet"
    />
  </div>
</template>

<style scoped>
.app-shell {
  position: relative;
  width: 100vw;
  height: 100vh;
  display: flex;
  background: var(--app-bg);
  color: var(--ink);
  font-size: 13px;
  overflow: hidden;
}
.content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.scroll-area {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px 14px 20px;
}
</style>
