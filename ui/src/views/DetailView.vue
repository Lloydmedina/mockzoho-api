<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getRecord, createRecord } from '../api/modules'
import { useModulesStore } from '../stores/modules'
import RecordDetail from '../components/RecordDetail.vue'
import RecordForm from '../components/RecordForm.vue'

const props = defineProps<{ module: string; id?: string }>()
const router = useRouter()
const modules = useModulesStore()
const record = ref<Record<string, any>>({})
const loading = ref(true)
const error = ref('')
const creating = computed(() => !props.id)

async function loadSchema() { await modules.load() }

async function loadRecord() {
  if (!props.id) { loading.value = false; return }
  loading.value = true
  try { record.value = await getRecord(props.module, props.id) }
  catch (e: any) { error.value = e.message }
  finally { loading.value = false }
}

async function save(data: Record<string, any>) {
  try {
    await createRecord(props.module, data)
    router.push(`/${props.module}`)
  } catch (e: any) { error.value = e.message }
}

function goBack() { router.push(`/${props.module}`) }

onMounted(async () => { await loadSchema(); await loadRecord() })
watch(() => props.id, loadRecord)
</script>

<template>
  <div v-if="creating">
    <div class="detail-header">
      <h2>New {{ module }}</h2>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <RecordForm
      :fields="(modules.spec(module)?.fields || []).filter(f => !f.read_only)"
      :record="{}"
      mode="create"
      @save="save"
      @cancel="goBack"
    />
  </div>
  <RecordDetail
    v-else
    :module="module"
    :id="id!"
    :fields="modules.spec(module)?.fields || []"
    :fieldSpecs="modules.spec(module) || {}"
    :relatedLists="modules.spec(module)?.related_lists || []"
  />
</template>
