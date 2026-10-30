<script setup lang="ts">
import { ref } from 'vue';
import { api, saveSession } from './api';
import type { Session } from './types';
defineProps<{ title: string; hint: string }>();
const emit = defineEmits<{ login: [session: Session] }>();
const username = ref(''), password = ref(''), error = ref(''), loading = ref(false);
async function login() {
  if (loading.value) return;
  loading.value = true; error.value = '';
  try {
    const result = await api<Session>('auth/login', { method: 'POST', body: JSON.stringify({ username: username.value.trim(), password: password.value }) });
    saveSession(result); password.value = ''; emit('login', result);
  } catch (e) { error.value = (e as Error).message; }
  finally { loading.value = false; }
}
</script>
<template>
  <main class="mg-auth">
    <section class="mg-auth-card">
      <p class="login-kicker">门店管理</p>
      <h1>{{ title }}</h1><p class="mg-muted login-hint">{{ hint }}</p>
      <form @submit.prevent="login">
        <label class="mg-field"><span>账号</span><input v-model="username" required autocomplete="username" :disabled="loading" autofocus></label>
        <label class="mg-field"><span>密码</span><input v-model="password" required minlength="8" maxlength="256" type="password" autocomplete="current-password" :disabled="loading"></label>
        <p v-if="error" class="mg-error" role="alert">{{ error }}</p>
        <button class="mg-button primary login-submit" :disabled="loading">{{ loading ? '正在登录…' : '登录' }}</button>
      </form>
    </section>
  </main>
</template>
<style scoped>
.login-kicker{font-size:12px;letter-spacing:2px;color:#52645b;margin-bottom:14px}.login-hint{margin:10px 0 30px;line-height:1.6}.login-submit{width:100%;margin-top:8px}
</style>
