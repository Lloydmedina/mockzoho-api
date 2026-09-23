<script setup lang="ts">
import { ref, watch } from 'vue'
import FieldInput from './FieldInput.vue'

const props = defineProps<{
  fields: any[]
  record: Record<string, any>
  mode: 'create' | 'edit'
}>()
const emit = defineEmits<{ save: [Record<string, any>]; cancel: [] }>()

const form = ref<Record<string, any>>({ ...props.record })

watch(() => props.record, (r) => { form.value = { ...r } })

function save() {
  const data: Record<string, any> = {}
  for (const f of props.fields) {
    if (form.value[f.api_name] !== undefined && form.value[f.api_name] !== '') {
      data[f.api_name] = form.value[f.api_name]
    }
  }
  if (props.mode === 'edit') data.id = props.record.id
  emit('save', data)
}
</script>

<template>
  <div class="record-form">
    <div class="form-grid">
      <div v-for="f in fields" :key="f.api_name" class="form-field">
        <label>{{ f.api_name }}<span v-if="f.required" class="req">*</span></label>
        <FieldInput :field="f" v-model="form[f.api_name]" />
      </div>
    </div>
    <div class="form-actions">
      <button class="btn-save" @click="save">Save</button>
      <button class="btn-cancel" @click="$emit('cancel')">Cancel</button>
    </div>
  </div>
</template>
