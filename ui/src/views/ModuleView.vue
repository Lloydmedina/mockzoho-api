<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { listRecords, createRecord, updateRecord, deleteRecord } from '../api/modules'
import { useModulesStore, type FieldSpec } from '../stores/modules'
import FieldInput from '../components/FieldInput.vue'

const props = defineProps<{ module: string }>()
const router = useRouter()
const modules = useModulesStore()

const records = ref<any[]>([])
const loading = ref(false)
const listError = ref('')
const page = ref(1)
const perPage = ref(20)
const moreRecords = ref(false)
const sortBy = ref('Modified_Time')
const sortOrder = ref('desc')
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formData = ref<Record<string, any>>({})
const editingId = ref<string | null>(null)
const formError = ref('')
const formSaving = ref(false)

const SYSTEM = ['id', 'Created_Time', 'Modified_Time', 'Created_By', 'Modified_By', 'Owner']

const moduleSpec = computed(() => modules.spec(props.module))
const displayFields = computed(() => (moduleSpec.value?.fields || []).slice(0, 7).map(f => f.api_name))
const formFields = computed(() => (moduleSpec.value?.fields || []).filter((f: FieldSpec) =>
  !f.read_only && !SYSTEM.includes(f.api_name)
))

async function load() {
  if (!props.module) return
  loading.value = true
  listError.value = ''
  try {
    await modules.load()
    const fields = displayFields.value.length > 0
      ? displayFields.value.join(',')
      : 'id'
    const data = await listRecords(props.module, {
      fields,
      page: page.value,
      per_page: perPage.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    })
    records.value = data.data || []
    moreRecords.value = data.info?.more_records || false
  } catch (e: any) {
    records.value = []
    listError.value = e.message || 'Failed to load records'
  } finally {
    loading.value = false
  }
}

function sort(field: string) {
  if (sortBy.value === field) sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  else { sortBy.value = field; sortOrder.value = 'asc' }
  load()
}

function openRecord(id: string) {
  router.push(`/${props.module}/${id}`)
}

function openCreate() {
  formMode.value = 'create'
  formData.value = {}
  editingId.value = null
  formError.value = ''
  formVisible.value = true
}

function openEdit(record: any) {
  formMode.value = 'edit'
  formData.value = { ...record }
  editingId.value = record.id
  formError.value = ''
  formVisible.value = true
}

function closeForm() {
  formVisible.value = false
  formData.value = {}
  editingId.value = null
  formError.value = ''
}

async function save() {
  formSaving.value = true
  formError.value = ''
  try {
    const types = Object.fromEntries((moduleSpec.value?.fields || []).map(f => [f.api_name, f.type]))
    const data: Record<string, any> = {}
    for (const f of formFields.value) {
      let v = formData.value[f.api_name]
      if (v === undefined || v === '') continue
      if (types[f.api_name] === 'integer') v = parseInt(v, 10)
      else if (types[f.api_name] === 'double') v = parseFloat(v)
      if (Number.isNaN(v)) continue
      data[f.api_name] = v
    }
    if (formMode.value === 'edit' && editingId.value) {
      await updateRecord(props.module, editingId.value, data)
    } else {
      await createRecord(props.module, data)
    }
    closeForm()
    await load()
  } catch (e: any) { formError.value = e.message }
  finally { formSaving.value = false }
}

async function doDelete(id: string) {
  if (!confirm('Delete this record?')) return
  await deleteRecord(props.module, id)
  await load()
}

function fmtVal(val: any): string {
  if (val == null) return ''
  if (typeof val === 'object') return val.name || val.id || JSON.stringify(val)
  return String(val)
}

onMounted(load)
watch(() => props.module, () => {
  if (!props.module) return
  page.value = 1
  closeForm()
  load()
})
</script>

<template>
  <div class="split-view">
    <!-- Left panel: Form (40%) -->
    <div class="form-panel" :class="{ hidden: !formVisible }">
      <div v-if="formVisible" class="form-content">
        <div class="form-header">
          <h3>{{ formMode === 'create' ? 'New' : 'Edit' }} {{ module }}</h3>
          <button class="btn-close" @click="closeForm">&times;</button>
        </div>
        <div v-if="formError" class="form-error">{{ formError }}</div>
        <div class="form-grid">
          <div v-for="f in formFields" :key="f.api_name" class="form-field">
            <label>{{ f.api_name }}<span v-if="f.required" class="req">*</span></label>
            <FieldInput :field="f" v-model="formData[f.api_name]" />
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-save" @click="save" :disabled="formSaving">
            {{ formSaving ? 'Saving...' : 'Save' }}
          </button>
          <button class="btn-cancel" @click="closeForm">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Right panel: List/Table (60%) -->
    <div class="list-panel" :class="{ full: !formVisible }">
      <div class="list-toolbar">
        <button class="btn-create" @click="openCreate">+ Create</button>
      </div>
      <div v-if="loading" class="loading">Loading...</div>
      <div v-else-if="listError" class="error">{{ listError }}</div>
      <div v-else-if="records.length === 0" class="empty">No records found</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th v-for="f in displayFields" :key="f" @click="sort(f)" :class="{ sorted: sortBy === f }">
              {{ f }}
              <span v-if="sortBy === f">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td v-for="f in displayFields" :key="f" @click="openRecord(r.id)">{{ fmtVal(r[f]) }}</td>
            <td class="actions-cell">
              <button class="btn-row-edit" @click.stop="openEdit(r)">Edit</button>
              <button class="btn-row-delete" @click.stop="doDelete(r.id)">Del</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="pagination">
        <button :disabled="page === 1" @click="page--; load()">← Prev</button>
        <span>Page {{ page }}</span>
        <button :disabled="!moreRecords" @click="page++; load()">Next →</button>
      </div>
    </div>
  </div>
</template>
