<script setup lang="ts">
import { computed, ref } from 'vue'
import type { FieldSpec, ModuleSpec } from '../stores/modules'

const props = defineProps<{ module: string; spec: ModuleSpec | null }>()

const open = ref(false)
const copied = ref(false)

const SYSTEM = ['id', 'Created_Time', 'Modified_Time', 'Created_By', 'Modified_By', 'Owner']

const payloadFields = computed(() =>
  (props.spec?.fields || []).filter((f: FieldSpec) => !f.read_only && !SYSTEM.includes(f.api_name))
)

function sampleValue(f: FieldSpec): any {
  switch (f.type) {
    case 'integer': return 10
    case 'double': return 99.99
    case 'boolean': return true
    case 'date': return '2026-09-25'
    case 'datetime': return '2026-09-25T10:00:00+00:00'
    case 'email': return 'john.doe@example.com'
    case 'phone': return '+1-555-0100'
    case 'picklist': return f.picklist_values[0] || ''
    case 'lookup': return { id: '4876000000000001', name: `${f.lookup_module} record` }
    case 'text': return 'Sample description text'
    default: return `Sample ${f.api_name}`
  }
}

const samplePayload = computed(() => {
  const record: Record<string, any> = {}
  for (const f of payloadFields.value) record[f.api_name] = sampleValue(f)
  return JSON.stringify({ data: [record] }, null, 2)
})

function fieldDetails(f: FieldSpec): string {
  if (f.type === 'picklist') return f.picklist_values.join(' | ')
  if (f.type === 'lookup') return `lookup → ${f.lookup_module} ({"id": "..."} or id string)`
  return ''
}

async function copySample() {
  try {
    await navigator.clipboard.writeText(samplePayload.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 1500)
  } catch { /* clipboard unavailable */ }
}
</script>

<template>
  <div class="schema-accordion">
    <button class="schema-header" @click="open = !open">
      <span class="schema-caret">{{ open ? '▾' : '▸' }}</span> schema
    </button>
    <div v-if="open" class="schema-body">
      <template v-if="spec">
        <div class="schema-section">
          <h4>Required payload</h4>
          <p class="schema-endpoint">
            <code>POST /crm/v3/{{ module }}</code> — body: <code>{ "data": [ &lt;record&gt; ] }</code>
          </p>
          <table class="schema-table">
            <thead>
              <tr><th>Field</th><th>Type</th><th>Required</th><th>Details</th></tr>
            </thead>
            <tbody>
              <tr v-for="f in payloadFields" :key="f.api_name">
                <td><code>{{ f.api_name }}</code></td>
                <td>{{ f.type }}</td>
                <td><span v-if="f.required" class="req">*</span>{{ f.required ? ' required' : '—' }}</td>
                <td class="schema-details">{{ fieldDetails(f) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="schema-section">
          <h4>Sample payload <button class="btn-copy" @click="copySample">{{ copied ? 'Copied!' : 'Copy' }}</button></h4>
          <pre class="schema-pre">{{ samplePayload }}</pre>
        </div>
      </template>
      <div v-else class="schema-empty">Schema unavailable</div>
    </div>
  </div>
</template>
