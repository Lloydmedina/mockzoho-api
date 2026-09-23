<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { resetDatabase } from '../api/modules'

defineEmits<{ 'toggle-sidebar': [] }>()

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

function doLogout() {
  auth.logout()
  router.push('/login')
}

async function doReset() {
  if (confirm('Reset database to seed state?')) {
    await resetDatabase()
    window.location.reload()
  }
}
</script>

<template>
  <header class="topbar">
    <button class="toggle-btn" @click="$emit('toggle-sidebar')">☰</button>
    <h1 class="module-title">{{ route.params.module || 'Dashboard' }}</h1>
    <div class="topbar-actions">
      <button class="btn-reset" @click="doReset" title="Reset DB">↻ Reset</button>
      <button class="btn-logout" @click="doLogout">Logout</button>
    </div>
  </header>
</template>
