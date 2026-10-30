<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ExternalLink, LogOut, Plus, RefreshCw, Search } from 'lucide-vue-next';
import { api, readSession, roleLabel, saveSession } from '../../frontend-shared/api';
import type { Menu, Session, Store, User } from '../../frontend-shared/types';
import ManagementLogin from '../../frontend-shared/ManagementLogin.vue';
import MenuManager from '../../frontend-shared/MenuManager.vue';
import ManagedDialog from '../../frontend-shared/ManagedDialog.vue';
import DeliverySettings from '../../frontend-shared/DeliverySettings.vue';
import CommerceManager from '../../frontend-shared/CommerceManager.vue';
const commerceEnabled=ref(false);
const commerceEditor=ref<InstanceType<typeof CommerceManager>>();

const session = ref<Session | null>(readSession());
const stores = ref<Store[]>([]), selectedId = ref<number | null>(null), menu = ref<Menu | null>(null);
const users = ref<User[]>([]), active = ref<'menu' | 'users' | 'delivery' | 'commerce'>('menu');
const loading = ref(false), usersLoading = ref(false), error = ref(''), usersError = ref(''), notice = ref('');
const editor = ref<InstanceType<typeof MenuManager>>();
const deliveryEditor = ref<InstanceType<typeof DeliverySettings>>();
const query = ref(''), userStore = ref('all'), showUser = ref(false), saving = ref(false), formError = ref(''), updatingUser = ref<number | null>(null);
const newUser = () => ({ username: '', display_name: '', password: '', role_code: 'STORE_ADMIN', store_id: selectedId.value || stores.value[0]?.id || 0 });
const form = ref(newUser());
let sequence = 0, noticeTimer: number | undefined, usersSequence = 0, sessionEpoch = 0;
const currentStore = computed(() => stores.value.find(s => s.id === selectedId.value));
const customerUrl = computed(() => ({ 'shengfuji': '/Adiandiancan/', 'shengsheng-fast-food': '/Bdiandiancan/', 'store-a': '/Adiandiancan/', 'store-b': '/Bdiandiancan/' } as Record<string, string>)[currentStore.value?.slug || ''] || null);
const filteredUsers = computed(() => users.value.filter(u => (userStore.value === 'all' || String(u.store_id) === userStore.value) && `${u.username} ${u.display_name}`.toLowerCase().includes(query.value.trim().toLowerCase())));
function notify(message: string) { notice.value = message; window.clearTimeout(noticeTimer); noticeTimer = window.setTimeout(() => notice.value = '', 4500); }
async function loadStores() {
  if (!session.value) return;
  const request = ++sequence;
  loading.value = true; error.value = '';
  try {
    const result = await api<Store[]>('admin/stores');
    if (request !== sequence) return;
    stores.value = result;
    const saved = Number(sessionStorage.getItem('takeaway-admin-store'));
    selectedId.value = stores.value.some(s => s.id === saved) ? saved : stores.value[0]?.id || null;
    if (selectedId.value !== null) await loadMenu();
  } catch (e) { if (request === sequence) error.value = (e as Error).message; }
  finally { if (request === sequence) loading.value = false; }
}
async function loadMenu() {
  if (!session.value || selectedId.value === null) return;
  const id = selectedId.value, request = ++sequence;
  loading.value = true; error.value = '';
  try { const value = await api<Menu>(`admin/stores/${id}/menu`); if (request === sequence) menu.value = value; }
  catch (e) { if (request === sequence) error.value = (e as Error).message; }
  finally { if (request === sequence) loading.value = false; }
}
async function loadUsers() {
  if (!session.value) return;
  const request = ++usersSequence;
  usersLoading.value = true; usersError.value = '';
  try { const result = await api<User[]>('admin/users'); if (request === usersSequence) users.value = result; }
  catch (e) { if (request === usersSequence) usersError.value = (e as Error).message; }
  finally { if (request === usersSequence) usersLoading.value = false; }
}
function changeStore(event: Event) {
  const select = event.target as HTMLSelectElement;
  if (!canLeave()) { select.value = String(selectedId.value); return; }
  selectedId.value = Number(select.value); sessionStorage.setItem('takeaway-admin-store', select.value);
  menu.value = null; loadMenu();
}
function canLeave() { return (!editor.value || editor.value.confirmLeave()) && (!deliveryEditor.value || deliveryEditor.value.confirmLeave()) && (!commerceEditor.value || commerceEditor.value.confirmLeave()); }
function changeTab(tab: 'menu' | 'users' | 'delivery' | 'commerce') {
  if (tab === active.value || !canLeave()) return;
  active.value = tab;
  if (tab === 'users') loadUsers();
}
function expired() {
  ++sessionEpoch; ++sequence; ++usersSequence; saveSession(null); session.value = null; menu.value = null; stores.value = []; users.value = []; selectedId.value = null;
  loading.value = false; usersLoading.value = false; showUser.value = false; saving.value = false; updatingUser.value = null;
  form.value = newUser(); error.value = ''; usersError.value = ''; formError.value = ''; notice.value = ''; window.clearTimeout(noticeTimer);
}
function logout() {
  if (saving.value) { notify('账号正在创建，请完成后再退出'); return; }
  if (showUser.value && (form.value.username || form.value.display_name || form.value.password) && !window.confirm('账号尚未创建，确定放弃已填写的内容并退出？')) return;
  if (canLeave()) expired();
}
function loggedIn(value: Session) { ++sessionEpoch; session.value = value; active.value = 'menu'; loadStores(); }
function refreshMenu() { if (canLeave()) { if (active.value === 'commerce' && commerceEditor.value) commerceEditor.value.reload(); else if (active.value === 'delivery' && deliveryEditor.value) deliveryEditor.value.reload(); else if (stores.value.length) loadMenu(); else loadStores(); } }
function deliverySaved(value: { address: string }) { if (menu.value) menu.value.store.address = value.address; if (currentStore.value) currentStore.value.address = value.address; }
function openUser() { form.value = newUser(); formError.value = ''; showUser.value = true; }
function closeUser() {
  if (saving.value) return;
  if ((form.value.username || form.value.display_name || form.value.password) && !window.confirm('账号尚未创建，确定放弃已填写的内容？')) return;
  showUser.value = false;
}
async function createUser() {
  if (saving.value || !session.value) return;
  const epoch = sessionEpoch;
  formError.value = '';
  if (!form.value.display_name.trim()) { formError.value = '请填写员工姓名。'; return; }
  saving.value = true;
  try {
    const created = await api<User>('admin/users', { method: 'POST', body: JSON.stringify({ ...form.value, username: form.value.username.trim(), display_name: form.value.display_name.trim() }) });
    if (epoch !== sessionEpoch) return;
    ++usersSequence; usersLoading.value = false;
    users.value = [...users.value.filter(u => u.id !== created.id), created]; showUser.value = false; form.value = newUser(); notify('员工账号已创建');
  } catch (e) { if (epoch === sessionEpoch) formError.value = (e as Error).message; }
  finally { if (epoch === sessionEpoch) saving.value = false; }
}
async function toggleUser(user: User) {
  if (updatingUser.value !== null || !session.value) return;
  const epoch = sessionEpoch;
  if (user.enabled && !window.confirm(`停用「${user.display_name}」（${user.username}）？停用后该账号将无法继续使用后台。`)) return;
  updatingUser.value = user.id; usersError.value = '';
  try {
    const result = await api<User>(`admin/users/${user.id}/enabled`, { method: 'PATCH', body: JSON.stringify({ enabled: !user.enabled }) });
    if (epoch !== sessionEpoch) return;
    ++usersSequence; usersLoading.value = false;
    users.value = users.value.map(u => u.id === result.id ? result : u); notify(result.enabled ? '账号已启用' : '账号已停用');
  } catch (e) { if (epoch === sessionEpoch) usersError.value = (e as Error).message; }
  finally { if (epoch === sessionEpoch) updatingUser.value = null; }
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (showUser.value && (saving.value || form.value.username || form.value.display_name || form.value.password)) { event.preventDefault(); event.returnValue = ''; }
}
onMounted(() => { if (session.value) loadStores(); window.addEventListener('session-expired', expired); window.addEventListener('beforeunload', beforeUnload); });
onMounted(async()=>{try{commerceEnabled.value=(await api<{enabled:boolean}>('commerce/capabilities')).enabled;}catch{}});
onBeforeUnmount(() => { ++sessionEpoch; ++sequence; ++usersSequence; window.removeEventListener('session-expired', expired); window.removeEventListener('beforeunload', beforeUnload); window.clearTimeout(noticeTimer); });
</script>
<template>
  <ManagementLogin v-if="!session" title="总管理登录" hint="管理两家门店的菜品与员工账号。" @login="loggedIn" />
  <div v-else class="mg-app">
    <header class="mg-topbar">
      <div class="mg-brand"><span class="admin-mark">店</span><strong>门店管理</strong><span class="mg-badge neutral">总管理</span></div>
      <nav class="mg-nav" aria-label="后台导航"><button :class="{active: active === 'menu'}" @click="changeTab('menu')">菜品管理</button><button :class="{active: active === 'delivery'}" @click="changeTab('delivery')">配送设置</button><button :class="{active: active === 'users'}" @click="changeTab('users')">员工账号</button><button v-if="commerceEnabled" :class="{active:active==='commerce'}" @click="changeTab('commerce')">经营工作台</button></nav>
      <div class="mg-topbar-actions"><span class="admin-name">{{ session.user.display_name }}</span><button class="mg-button small" @click="logout"><LogOut :size="15" />退出</button></div>
    </header>
    <main class="mg-main">
      <template v-if="active !== 'users'">
        <div class="mg-page-heading"><div><h1>{{ active === 'commerce' ? '经营工作台' : active === 'menu' ? '菜品管理' : '配送设置' }}</h1><p class="mg-muted">{{ active === 'commerce' ? '管理订单、会员、营销与跨门店统计' : active === 'menu' ? '选择门店，维护分类、菜品和售价' : '选择门店，调整配送范围与各距离档位的费用' }}</p></div><div class="mg-actions"><a v-if="customerUrl" :href="customerUrl" target="_blank" rel="noopener" class="mg-button"><ExternalLink :size="15" />查看点餐页</a><button class="mg-button" :disabled="loading" @click="refreshMenu"><RefreshCw :size="15" />刷新</button></div></div>
        <div v-if="stores.length" class="store-strip">
          <label for="store-select">当前门店</label><select id="store-select" :value="selectedId" @change="changeStore"><option v-for="store in stores" :key="store.id" :value="store.id">{{ store.name }}</option></select>
          <span class="store-address">{{ currentStore?.address }}</span><span class="store-phone">{{ currentStore?.phone }}</span>
        </div>
        <p v-if="error" class="mg-error" role="alert">{{ error }} <button class="mg-button small" @click="refreshMenu">重试</button></p>
        <div v-if="loading && !menu" class="mg-panel mg-empty" role="status">正在读取菜单…</div>
        <MenuManager v-if="active === 'menu' && menu && menu.store.id === selectedId" :key="menu.store.id" ref="editor" :menu="menu" :api-prefix="`admin/stores/${menu.store.id}`" :can-write="true" :busy="loading" @updated="menu = $event" @notice="notify" />
        <DeliverySettings v-if="active === 'delivery' && menu && menu.store.id === selectedId" :key="menu.store.id" ref="deliveryEditor" :api-prefix="`admin/stores/${menu.store.id}`" :can-write="true" @notice="notify" @saved="deliverySaved" />
        <CommerceManager v-if="active==='commerce'&&menu&&menu.store.id===selectedId" :key="menu.store.id" ref="commerceEditor" :menu="menu" :role="session.user.role_code" />
        <div v-if="!loading && !error && !stores.length" class="mg-panel mg-empty">暂无门店，请联系系统维护人员配置门店。</div>
      </template>
      <template v-else>
        <div class="mg-page-heading"><div><h1>员工账号</h1><p class="mg-muted">按门店分配账号，为员工设置合适的操作权限</p></div><button class="mg-button primary" :disabled="!stores.length" @click="openUser"><Plus :size="16" />新增员工</button></div>
        <section class="accounts-section" aria-label="员工账号列表">
          <div class="user-tools"><label class="user-search"><Search :size="16" /><input v-model="query" placeholder="搜索姓名或账号" aria-label="搜索姓名或账号"></label><select v-model="userStore" aria-label="筛选所属门店"><option value="all">全部门店</option><option v-for="store in stores" :key="store.id" :value="String(store.id)">{{ store.name }}</option></select><button class="mg-button" :disabled="usersLoading" @click="loadUsers"><RefreshCw :size="15" />刷新</button></div>
          <p v-if="usersError" class="mg-error" role="alert">{{ usersError }} <button class="mg-button small" @click="loadUsers">重试</button></p>
          <p v-if="usersLoading && !users.length" class="mg-empty" role="status">正在读取账号…</p>
          <div v-else class="mg-table-wrap accounts-table-wrap">
            <table class="mg-table users-table">
              <thead><tr><th scope="col">员工 / 账号</th><th scope="col">所属门店</th><th scope="col">权限</th><th scope="col">状态</th><th scope="col" class="user-operation">操作</th></tr></thead>
              <tbody>
                <tr v-for="user in filteredUsers" :key="user.id" class="user-row">
                  <td class="user-identity" data-label="员工 / 账号"><strong>{{ user.display_name }}</strong><small>{{ user.username }}</small></td>
                  <td class="user-store" data-label="所属门店">{{ user.store_id === null ? '所有门店' : stores.find(s => s.id === user.store_id)?.name || '门店信息待加载' }}</td>
                  <td class="user-role" data-label="权限"><span>{{ roleLabel(user.role_code) }}</span><small>{{ user.role_code === 'SUPER_ADMIN' ? '管理所有门店与账号' : user.permissions.includes('menu:write') ? '可编辑本店菜单' : '可查看本店菜单' }}</small></td>
                  <td class="user-status" data-label="状态"><span class="mg-badge" :class="{neutral: !user.enabled}">{{ user.enabled ? '正常' : '已停用' }}</span></td>
                  <td class="user-operation" data-label="操作"><span v-if="user.id === session.user.id" class="mg-muted">当前账号</span><button v-else class="mg-button small" :class="{danger: user.enabled}" :disabled="updatingUser !== null" @click="toggleUser(user)">{{ updatingUser === user.id ? '处理中…' : user.enabled ? '停用' : '启用' }}</button></td>
                </tr>
                <tr v-if="!filteredUsers.length" class="empty-users"><td colspan="5" class="mg-empty">没有符合条件的账号</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <p class="accounts-note mg-muted">门店管理员维护本店业务；订单员接单与核销；后厨处理制作；配送员处理配送。员工离职时可停用账号。</p>
      </template>
    </main>
    <ManagedDialog v-if="showUser" title="新增员工账号" :busy="saving" @close="closeUser">
      <form @submit.prevent="createUser"><fieldset :disabled="saving" class="account-fieldset">
        <label class="mg-field"><span>员工姓名</span><input v-model="form.display_name" required maxlength="120" autocomplete="off" placeholder="例如：王店长"></label>
        <div class="mg-form-grid"><label class="mg-field"><span>登录账号</span><input v-model="form.username" required minlength="3" maxlength="80" pattern="[A-Za-z0-9_.-]+" autocomplete="off" placeholder="字母、数字或下划线"></label><label class="mg-field"><span>所属门店</span><select v-model.number="form.store_id" required><option v-for="store in stores" :key="store.id" :value="store.id">{{ store.name }}</option></select></label></div>
        <label class="mg-field"><span>初始密码</span><input v-model="form.password" type="password" required minlength="12" maxlength="256" autocomplete="new-password" placeholder="至少 12 位"></label>
        <label class="mg-field"><span>操作权限</span><select v-model="form.role_code"><option value="STORE_ADMIN">门店管理员 · 可编辑菜单</option><option value="ORDER_OPERATOR">订单操作员 · 接单与核销</option><option value="KITCHEN_OPERATOR">后厨操作员 · 制作与出餐</option><option value="DELIVERY_OPERATOR">配送操作员 · 配送订单</option></select></label>
        <p v-if="formError" class="mg-error" role="alert">{{ formError }}</p>
        <div class="account-actions"><button type="button" class="mg-button" @click="closeUser">取消</button><button class="mg-button primary">{{ saving ? '正在创建…' : '创建账号' }}</button></div>
      </fieldset></form>
    </ManagedDialog>
    <div v-if="notice" class="management-toast" role="status">{{ notice }}</div>
  </div>
</template>
