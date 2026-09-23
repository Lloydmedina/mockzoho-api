<script setup lang="ts">
import { ref, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import TopBar from './components/TopBar.vue'
import { useAuthStore } from './stores/auth'
import { useModulesStore } from './stores/modules'

const auth = useAuthStore()
const modules = useModulesStore()
const sidebarOpen = ref(true)

watch(() => auth.token, (t) => {
  if (t) modules.load()
}, { immediate: true })

function toggleSidebar() { sidebarOpen.value = !sidebarOpen.value }
</script>

<template>
  <div class="app-layout" v-if="auth.token">
    <Sidebar :open="sidebarOpen" :schemas="modules.schemas" />
    <div class="main-area" :class="{ expanded: !sidebarOpen }">
      <TopBar @toggle-sidebar="toggleSidebar" :sidebar-open="sidebarOpen" />
      <div class="content-area">
        <router-view />
      </div>
    </div>
  </div>
  <router-view v-else />
</template>
