<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getRecord, getRelated, updateRecord, deleteRecord } from '../api/modules'
import RecordForm from './RecordForm.vue'

const props = defineProps<{
  module: string
  id: string
  fields: any[]
  fieldSpecs: Record<string, any>
  relatedLists: string[]
}>()

const router = useRouter()
const record = ref<Record<string, any>>({})
const related = ref<Record<string, any[]>>({})
const loading = ref(true)
const editing = ref(false)
const error = ref('')

const nonSystemFields = computed(() => props.fields.filter((f: any) => !['id', 'Created_Time', 'Modified_Time', 'Created_By', 'Modified_By', 'Owner'].includes(f.api_name)))

async function load() {
  loading.value = true
  editing.value = false
  try {
    record.value = await getRecord(props.module, props.id)
    for (const name of props.relatedLists) {
      try { related.value[name] = await getRelated(props.module, props.id, name) } catch { related.value[name] = [] }
    }
  } catch (e: any) { error.value = e.message } finally { loading.value = false }
}

async function save(data: Record<string, any>) {
  try {
    await updateRecord(props.module, props.id, data)
    editing.value = false
    await load()
  } catch (e: any) { error.value = e.message }
}

async function doDelete() {
  if (!confirm('Delete this record?')) return
  await deleteRecord(props.module, props.id)
  router.push(`/${props.module}`)
}

function fmtVal(val: any): string {
  if (val == null) return ''
  if (typeof val === 'object') return val.name || val.id || JSON.stringify(val)
  return String(val)
}

onMounted(load)
</script>

<template>
  <div class="detail-view">
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else>
      <div class="detail-header">
        <button class="btn-back" @click="router.push(`/${module}`)">← Back</button>
        <h2>{{ record.Subject || record.Name || record.Product_Name || record.id }}</h2>
        <div class="detail-actions">
          <button v-if="!editing" class="btn-edit" @click="editing = true">Edit</button>
          <button class="btn-delete" @click="doDelete">Delete</button>
        </div>
      </div>

      <div v-if="editing" class="edit-section">
        <RecordForm :fields="nonSystemFields" :record="record" mode="edit" @save="save" @cancel="editing = false" />
      </div>

      <div v-else class="field-sections">
        <div class="field-section">
          <h3>Record Information</h3>
          <div class="field-grid">
            <div v-for="f in fields" :key="f.api_name" class="field-row">
              <span class="field-label">{{ f.api_name }}</span>
              <span class="field-value">{{ fmtVal(record[f.api_name]) }}</span>
            </div>
          </div>
        </div>

        <div v-for="(items, name) in related" :key="name" class="field-section">
          <h3>{{ name }} ({{ items.length }})</h3>
          <div v-if="items.length === 0" class="empty-related">No related records</div>
          <table v-else class="related-table">
            <thead>
              <tr><th v-for="key in Object.keys(items[0]).slice(0, 5)" :key="key">{{ key }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.id">
                <td v-for="key in Object.keys(item).slice(0, 5)" :key="key">{{ fmtVal(item[key]) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
