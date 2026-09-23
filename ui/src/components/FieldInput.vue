<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

const props = defineProps<{
  field: any
  modelValue: any
}>()
const emit = defineEmits<{ 'update:modelValue': [any] }>()

const val = ref(props.modelValue)

watch(() => props.modelValue, (v) => { val.value = v })

function update() { emit('update:modelValue', val.value) }

onMounted(() => { val.value = props.modelValue })
</script>

<template>
  <input
    v-if="['string', 'email', 'phone'].includes(field.type)"
    v-model="val" @input="update" :type="field.type === 'email' ? 'email' : field.type === 'phone' ? 'tel' : 'text'"
    class="field-input"
  />
  <textarea
    v-else-if="field.type === 'text'"
    v-model="val" @input="update" class="field-input"
  />
  <input
    v-else-if="field.type === 'integer'"
    v-model="val" @input="update" type="number" class="field-input"
  />
  <input
    v-else-if="field.type === 'double'"
    v-model="val" @input="update" type="number" step="0.01" class="field-input"
  />
  <input
    v-else-if="field.type === 'boolean'"
    :checked="val" @change="val = ($event.target as HTMLInputElement).checked; update()"
    type="checkbox" class="field-checkbox"
  />
  <input
    v-else-if="field.type === 'datetime' || field.type === 'date'"
    v-model="val" @input="update" type="datetime-local" class="field-input"
  />
  <select
    v-else-if="field.type === 'picklist'"
    v-model="val" @change="update" class="field-input"
  >
    <option value="">—</option>
    <option v-for="opt in field.picklist_values" :key="opt" :value="opt">{{ opt }}</option>
  </select>
  <input
    v-else-if="field.type === 'lookup'"
    v-model="val" @input="update" type="text" class="field-input"
    :placeholder="`Lookup ID (${field.lookup_module})`"
  />
  <input v-else v-model="val" @input="update" type="text" class="field-input" />
</template>
