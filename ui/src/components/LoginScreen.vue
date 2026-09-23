<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getToken } from '../api/modules'

const auth = useAuthStore()
const router = useRouter()

const clientId = ref('1000.MOCKCLIENTID')
const clientSecret = ref('mock_client_secret')
const refreshToken = ref('1000.mockrefreshtoken.refresh')
const error = ref('')
const loading = ref(false)

async function login() {
  loading.value = true
  error.value = ''
  try {
    const data = await getToken({
      grant_type: 'refresh_token',
      client_id: clientId.value,
      client_secret: clientSecret.value,
      refresh_token: refreshToken.value,
    })
    if (data.error) { error.value = data.error; return }
    auth.setToken(data.access_token, data.api_domain || '')
    auth.setCreds({
      client_id: clientId.value,
      client_secret: clientSecret.value,
      refresh_token: refreshToken.value,
    })
    router.push('/Cases')
  } catch (e: any) { error.value = e.message } finally { loading.value = false }
}
</script>

<template>
  <div class="login-screen">
    <div class="login-card">
      <div class="login-header">
        <span class="logo"></span>
        <h1>Mock Zoho CRM</h1>
      </div>
      <p class="login-subtitle">Sign in with your OAuth credentials</p>
      <div v-if="error" class="login-error">{{ error }}</div>
      <form @submit.prevent="login" class="login-form">
        <label>Client ID</label>
        <input v-model="clientId" type="text" placeholder="1000.XXXX" />
        <label>Client Secret</label>
        <input v-model="clientSecret" type="password" />
        <label>Refresh Token</label>
        <input v-model="refreshToken" type="password" />
        <button type="submit" :disabled="loading" class="btn-login">
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>
      <p class="login-hint">Test credentials are prefilled — just click Sign In.</p>
    </div>
  </div>
</template>
