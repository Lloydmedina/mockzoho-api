<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listRecords } from '../api/modules'

const props = defineProps<{
  module: string
  fields: string[]
  fieldSpecs: Record<string, any>
}>()

const router = useRouter()
const records = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const perPage = ref(20)
const moreRecords = ref(false)
const sortBy = ref('Modified_Time')
const sortOrder = ref('desc')

const displayFields = computed(() => props.fields.slice(0, 7))

async function load() {
  loading.value = true
  try {
    const data = await listRecords(props.module, {
      fields: displayFields.value.join(','),
      page: page.value,
      per_page: perPage.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    })
    records.value = data.data || []
    moreRecords.value = data.info?.more_records || false
  } catch (e) {
    records.value = []
  } finally {
    loading.value = false
  }
}

function sort(field: string) {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = field
    sortOrder.value = 'asc'
  }
  load()
}

function openRecord(id: string) {
  router.push(`/${props.module}/${id}`)
}

function fmtVal(val: any): string {
  if (val == null) return ''
  if (typeof val === 'object') return val.name || val.id || JSON.stringify(val)
  return String(val)
}

onMounted(load)
watch(() => props.module, load)
</script>

<template>
  <div class="list-view">
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="records.length === 0" class="empty">No records found</div>
    <table v-else class="data-table">
      <thead>
        <tr>
          <th v-for="f in displayFields" :key="f" @click="sort(f)" :class="{ sorted: sortBy === f }">
            {{ f }}
            <span v-if="sortBy === f">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in records" :key="r.id" @click="openRecord(r.id)">
          <td v-for="f in displayFields" :key="f">{{ fmtVal(r[f]) }}</td>
        </tr>
      </tbody>
    </table>
    <div class="pagination">
      <button :disabled="page === 1" @click="page--; load()">← Prev</button>
      <span>Page {{ page }}</span>
      <button :disabled="!moreRecords" @click="page++; load()">Next →</button>
    </div>
  </div>
</template>
