<script setup lang="ts">
import { useRouter } from 'vue-router'

defineProps<{ open: boolean; schemas: Record<string, any> }>()
const router = useRouter()

function go(module: string) {
  router.push(`/${module}`)
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: !open }">
    <div class="sidebar-header">
      <span class="logo"></span>
      <span v-if="open" class="brand">Mock Zoho CRM</span>
    </div>
    <nav class="module-nav">
      <div v-for="(_spec, name) in schemas" :key="name" class="module-item" @click="go(name)">
        <span class="icon">-></span>
        <span v-if="open" class="label">{{ name }}</span>
      </div>
    </nav>
    <div v-if="open" class="sidebar-footer">
      <button class="reset-btn" @click="$emit('reset')">Reset DB</button>
    </div>
  </aside>
</template>
