<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ExternalLink, LogOut, RefreshCw } from 'lucide-vue-next';
import { api, entry, readSession, roleLabel, saveSession } from '../../frontend-shared/api';
import type { Menu, Session } from '../../frontend-shared/types';
import ManagementLogin from '../../frontend-shared/ManagementLogin.vue';
import MenuManager from '../../frontend-shared/MenuManager.vue';
import DeliverySettings from '../../frontend-shared/DeliverySettings.vue';
import CommerceManager from '../../frontend-shared/CommerceManager.vue';
const commerceEnabled=ref(false);
const commerceEditor=ref<InstanceType<typeof CommerceManager>>();
const session = ref<Session | null>(readSession()), menu = ref<Menu | null>(null);
const loading = ref(false), error = ref(''), notice = ref('');
const editor = ref<InstanceType<typeof MenuManager>>();
const deliveryEditor = ref<InstanceType<typeof DeliverySettings>>();
const active = ref<'menu' | 'delivery' | 'commerce'>('menu');
const canWrite = computed(() => !!session.value?.user.permissions.includes('menu:write'));
let sequence = 0, noticeTimer: number | undefined;
const customerUrl = entry.store === 'A' ? '/Adiandiancan/' : '/Bdiandiancan/';
function notify(message: string) { notice.value = message; window.clearTimeout(noticeTimer); noticeTimer = window.setTimeout(() => notice.value = '', 4500); }
async function load() {
  if (!session.value) return;
  const request = ++sequence;
  loading.value = true; error.value = '';
  try { const result = await api<Menu>('staff/menu'); if (request === sequence) menu.value = result; }
  catch (e) { if (request === sequence) error.value = (e as Error).message; }
  finally { if (request === sequence) loading.value = false; }
}
function expired() { ++sequence; saveSession(null); session.value = null; menu.value = null; loading.value = false; error.value = ''; notice.value = ''; window.clearTimeout(noticeTimer); }
function canLeave() { return (!editor.value || editor.value.confirmLeave()) && (!deliveryEditor.value || deliveryEditor.value.confirmLeave()) && (!commerceEditor.value || commerceEditor.value.confirmLeave()); }
function logout() { if (canLeave()) expired(); }
function loggedIn(value: Session) { session.value = value; load(); }
function refresh() { if (canLeave()) { if (active.value === 'delivery' && deliveryEditor.value) deliveryEditor.value.reload(); else load(); } }
function changeTab(tab: 'menu' | 'delivery' | 'commerce') { if (tab !== active.value && canLeave()) active.value = tab; }
function deliverySaved(value: { address: string }) { if (menu.value) menu.value.store.address = value.address; }
onMounted(() => { if (session.value) load(); window.addEventListener('session-expired', expired); });
onMounted(async()=>{try{commerceEnabled.value=(await api<{enabled:boolean}>('commerce/capabilities')).enabled;}catch{}});
onBeforeUnmount(() => { ++sequence; window.removeEventListener('session-expired', expired); window.clearTimeout(noticeTimer); });
</script>
<template>
  <ManagementLogin v-if="!session" :title="`${entry.store} 店 · 店员登录`" hint="使用总管理员分配的门店账号登录。" @login="loggedIn" />
  <div v-else class="mg-app">
    <header class="mg-topbar">
      <div class="mg-brand"><span class="staff-store-code">{{ entry.store }}</span><div><strong>{{ menu?.store.name || `${entry.store} 店` }}</strong><small>门店后台</small></div></div>
      <div class="staff-account"><span>{{ session.user.display_name }}<small>{{ roleLabel(session.user.role_code) }}</small></span><button class="mg-button small" @click="logout"><LogOut :size="15" />退出</button></div>
    </header>
    <nav class="mg-nav" aria-label="门店后台导航"><button :class="{active: active === 'menu'}" @click="changeTab('menu')">菜品管理</button><button :class="{active: active === 'delivery'}" @click="changeTab('delivery')">配送设置</button><button v-if="commerceEnabled" :class="{active:active==='commerce'}" @click="changeTab('commerce')">经营工作台</button></nav>
    <main class="mg-main">
      <CommerceManager v-if="active==='commerce'&&menu" ref="commerceEditor" :menu="menu" :role="session.user.role_code" />
      <div v-if="active!=='commerce'" class="mg-page-heading"><div><h1>{{ active === 'menu' ? '菜品管理' : '配送设置' }}</h1><p class="mg-muted">{{ active === 'menu' ? '管理本店菜单、价格和供应状态' : '设置门店配送起点、距离范围和分段配送费' }}</p></div><div class="staff-actions"><a :href="customerUrl" target="_blank" rel="noopener" class="mg-button"><ExternalLink :size="15" />查看点餐页</a><button class="mg-button" :disabled="loading" @click="refresh"><RefreshCw :size="15" />刷新</button></div></div>
      <p v-if="error" class="mg-error" role="alert">{{ error }} <button class="mg-button small" @click="refresh">重试</button></p>
      <p v-if="loading && !menu" class="mg-panel mg-empty" role="status">正在读取菜单…</p>
      <MenuManager v-if="menu && active === 'menu'" ref="editor" :menu="menu" api-prefix="staff" :can-write="canWrite" :busy="loading" @updated="menu = $event" @notice="notify" />
      <DeliverySettings v-if="menu && active === 'delivery'" ref="deliveryEditor" api-prefix="staff" :can-write="canWrite" @notice="notify" @saved="deliverySaved" />
      <footer v-if="menu" class="staff-footer"><span>{{ menu.store.name }}</span><span>{{ menu.store.address }}</span><span>{{ menu.store.phone }}</span></footer>
    </main>
    <div v-if="notice" class="management-toast" role="status">{{ notice }}</div>
  </div>
</template>
