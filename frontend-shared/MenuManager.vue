<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { Check, ChevronDown, CircleAlert, ImagePlus, LoaderCircle, Pencil, Plus, RefreshCw, Search, Utensils, X } from 'lucide-vue-next';
import { api, imageFallback, imageUrl, money } from './api';
import type { Category, Dish, Menu } from './types';
import ManagedDialog from './ManagedDialog.vue';

const props = defineProps<{ menu: Menu; apiPrefix: string; canWrite: boolean; busy?: boolean }>();
const emit = defineEmits<{ updated: [menu: Menu]; notice: [message: string] }>();
const currentMenu = ref(props.menu);
watch(() => props.menu, value => { currentMenu.value = value; });
const categories = computed(() => [...currentMenu.value.categories].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id));
const allDishes = computed(() => categories.value.flatMap(category => category.dishes.map(dish => ({ ...dish, categoryName: category.name, categoryEnabled: category.enabled }))));
const selectedCategory = ref<number | null>(null);
const selectedCategoryData = computed(() => categories.value.find(category => category.id === selectedCategory.value));
const search = ref('');
const status = ref<'all' | 'available' | 'sold' | 'disabled'>('all');
const visibleDishes = computed(() => allDishes.value.filter(dish => {
  if (selectedCategory.value !== null && dish.category_id !== selectedCategory.value) return false;
  if (search.value.trim() && !dish.name.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase())) return false;
  if (status.value === 'available' && (!dish.enabled || dish.sold_out || dish.stock === 0 || !dish.categoryEnabled)) return false;
  if (status.value === 'sold' && (!dish.enabled || (!dish.sold_out && dish.stock !== 0))) return false;
  if (status.value === 'disabled' && dish.enabled) return false;
  return true;
}));

const loading = ref(false);
const saving = ref(false);
const uploading = ref(false);
const quickBusy = ref<number | null>(null);
const pageError = ref('');
const refreshNeeded = ref(false);
const formError = ref('');
const imageError = ref('');
const editor = ref<'dish' | 'category' | null>(null);
const editingDishId = ref<number | null>(null);
const editingCategoryId = ref<number | null>(null);
const imageInput = ref<HTMLInputElement>();
const initialSnapshot = ref('');
let mounted = true;

function blankDish() {
  return { name: '', category_id: 0, price: '', original_price: '', image_url: '', description: '', stock: '', sort_order: '0', monthly_sales: '0', enabled: true, sold_out: false, requires_options: false };
}
const dishForm = ref(blankDish());
const categoryForm = ref({ name: '', sort_order: '0', enabled: true });
const editorBusy = computed(() => saving.value || uploading.value);
const operationBusy = computed(() => props.busy || loading.value || saving.value || uploading.value || quickBusy.value !== null);
function snapshot() { return JSON.stringify(editor.value === 'dish' ? dishForm.value : categoryForm.value); }
function hasUnsaved() { return !!editor.value && (editorBusy.value || snapshot() !== initialSnapshot.value); }
function confirmLeave() {
  if (editorBusy.value || quickBusy.value !== null) return false;
  return !hasUnsaved() || window.confirm('还有未保存的修改，确定放弃并离开吗？');
}
defineExpose({ hasUnsaved, confirmLeave });
function beforeUnload(event: BeforeUnloadEvent) { if (hasUnsaved() || quickBusy.value !== null) { event.preventDefault(); event.returnValue = ''; } }
onMounted(() => window.addEventListener('beforeunload', beforeUnload));
onBeforeUnmount(() => { mounted = false; window.removeEventListener('beforeunload', beforeUnload); });

function closeEditor() {
  if (!confirmLeave()) return;
  editor.value = null;
  formError.value = '';
  imageError.value = '';
}
function startCategory(category?: Category) {
  if (!props.canWrite || operationBusy.value || !confirmLeave()) return;
  editingCategoryId.value = category?.id ?? null;
  categoryForm.value = { name: category?.name || '', sort_order: String(category?.sort_order ?? nextOrder(categories.value)), enabled: category?.enabled ?? true };
  editor.value = 'category';
  formError.value = '';
  initialSnapshot.value = snapshot();
}
function startDish(dish?: Dish) {
  if (!props.canWrite || operationBusy.value || !confirmLeave()) return;
  if (!categories.value.length) { startCategory(); return; }
  editingDishId.value = dish?.id ?? null;
  dishForm.value = dish ? {
    name: dish.name, category_id: dish.category_id, price: (dish.price_cents / 100).toFixed(2),
    original_price: dish.original_price_cents === null ? '' : (dish.original_price_cents / 100).toFixed(2),
    image_url: dish.image_url || '', description: dish.description || '', stock: dish.stock === null ? '' : String(dish.stock),
    sort_order: String(dish.sort_order), monthly_sales: String(dish.monthly_sales), enabled: dish.enabled,
    sold_out: dish.sold_out, requires_options: dish.requires_options,
  } : { ...blankDish(), category_id: selectedCategory.value ?? categories.value[0]!.id, sort_order: String(nextOrder(allDishes.value)) };
  editor.value = 'dish';
  formError.value = '';
  imageError.value = '';
  initialSnapshot.value = snapshot();
}
function nextOrder(items: { sort_order: number }[]) { return items.length ? Math.min(Math.max(...items.map(item => item.sort_order)) + 10, 2147483647) : 0; }
function slug(kind: string) {
  // The deployed IP test environment is plain HTTP, where randomUUID may be unavailable.
  const cryptoApi = globalThis.crypto;
  const values = new Uint32Array(2);
  if (cryptoApi?.getRandomValues) cryptoApi.getRandomValues(values);
  else { values[0] = Math.floor(Math.random() * 0xffffffff); values[1] = Math.floor(Math.random() * 0xffffffff); }
  return `${kind}-${Date.now().toString(36)}-${values[0].toString(36)}${values[1].toString(36)}`;
}
function errorText(error: unknown) { return error instanceof Error ? error.message : '操作未完成，请重试'; }
function integer(value: string, label: string, allowNegative = false): number {
  const text = String(value).trim();
  if (!(allowNegative ? /^-?\d+$/ : /^\d+$/).test(text)) throw new Error(`${label}请填写${allowNegative ? '' : '非负'}整数`);
  const result = Number(text);
  if (!Number.isSafeInteger(result) || result > 2147483647 || result < -2147483648) throw new Error(`${label}超出允许范围`);
  return result;
}
function cents(value: string, label: string): number {
  const text = value.trim();
  if (!/^\d+(?:\.\d{1,2})?$/.test(text)) throw new Error(`${label}请填写有效金额，最多两位小数`);
  const [whole, fraction = ''] = text.split('.');
  const result = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  if (!Number.isSafeInteger(result) || result > 2147483647) throw new Error(`${label}超出允许范围`);
  return result;
}

async function reload(message?: string) {
  if (loading.value) return;
  loading.value = true;
  pageError.value = '';
  try {
    const menu = await api<Menu>(`${props.apiPrefix}/menu`);
    if (!mounted) return;
    currentMenu.value = menu;
    if (selectedCategory.value !== null && !menu.categories.some(category => category.id === selectedCategory.value)) selectedCategory.value = null;
    refreshNeeded.value = false;
    emit('updated', menu);
    if (message) emit('notice', message);
  } catch (error) {
    if (mounted) {
      refreshNeeded.value = true;
      pageError.value = message ? `${message}，但最新菜单加载失败。请刷新后继续。${errorText(error)}` : errorText(error);
    }
  } finally { if (mounted) loading.value = false; }
}
async function saveCategory() {
  if (!props.canWrite || editorBusy.value) return;
  formError.value = '';
  let body: Record<string, unknown>;
  try {
    const name = categoryForm.value.name.trim();
    if (!name || name.length > 80) throw new Error('分类名称需要 1–80 个字');
    body = { name, sort_order: integer(categoryForm.value.sort_order, '分类排序', true), enabled: categoryForm.value.enabled };
    if (editingCategoryId.value === null) body.slug = slug('category');
  } catch (error) { formError.value = errorText(error); return; }
  saving.value = true;
  try {
    const id = editingCategoryId.value;
    await api(`${props.apiPrefix}/categories${id === null ? '' : `/${id}`}`, { method: id === null ? 'POST' : 'PATCH', body: JSON.stringify(body) });
    if (!mounted) return;
    editor.value = null;
    await reload('分类已保存');
  } catch (error) { if (mounted) formError.value = errorText(error); }
  finally { if (mounted) saving.value = false; }
}
async function saveDish() {
  if (!props.canWrite || editorBusy.value) return;
  formError.value = '';
  let body: Record<string, unknown>;
  try {
    const form = dishForm.value;
    const name = form.name.trim();
    if (!name || name.length > 120) throw new Error('菜品名称需要 1–120 个字');
    if (!categories.value.some(category => category.id === Number(form.category_id))) throw new Error('请选择菜品分类');
    const price = cents(form.price, '售价');
    const original = form.original_price.trim() ? cents(form.original_price, '原价') : null;
    if (original !== null && original < price) throw new Error('原价不能低于售价，不需要显示原价时可留空');
    body = {
      name, category_id: Number(form.category_id), price_cents: price, original_price_cents: original,
      image_url: form.image_url || null, description: form.description.trim() || null,
      stock: String(form.stock).trim() ? integer(form.stock, '库存') : null,
      monthly_sales: integer(form.monthly_sales, '月售数量'), sort_order: integer(form.sort_order, '菜品排序', true),
      enabled: form.enabled, sold_out: form.sold_out, requires_options: form.requires_options,
    };
    if (editingDishId.value === null) body.slug = slug('dish');
  } catch (error) { formError.value = errorText(error); return; }
  saving.value = true;
  try {
    const id = editingDishId.value;
    await api(`${props.apiPrefix}/dishes${id === null ? '' : `/${id}`}`, { method: id === null ? 'POST' : 'PATCH', body: JSON.stringify(body) });
    if (!mounted) return;
    editor.value = null;
    await reload('菜品已保存');
  } catch (error) { if (mounted) formError.value = errorText(error); }
  finally { if (mounted) saving.value = false; }
}
async function quickChange(dish: Dish, field: 'enabled' | 'sold_out') {
  if (!props.canWrite || operationBusy.value || refreshNeeded.value) return;
  quickBusy.value = dish.id;
  pageError.value = '';
  try {
    const value = !dish[field];
    await api(`${props.apiPrefix}/dishes/${dish.id}`, { method: 'PATCH', body: JSON.stringify({ [field]: value }) });
    await reload(field === 'enabled' ? (value ? '菜品已上架' : '菜品已下架') : (value ? '菜品已标记售罄' : '已取消售罄标记'));
  } catch (error) { if (mounted) pageError.value = errorText(error); }
  finally { if (mounted) quickBusy.value = null; }
}
async function uploadImage(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file || !props.canWrite || editorBusy.value) return;
  imageError.value = '';
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { imageError.value = '请选择 JPG、PNG 或 WebP 图片'; return; }
  if (file.size > 5 * 1024 * 1024) { imageError.value = '图片不能超过 5 MB，请压缩后重试'; return; }
  uploading.value = true;
  try {
    const data = new FormData();
    data.append('file', file);
    const result = await api<{ url: string }>(`${props.apiPrefix}/images`, { method: 'POST', body: data });
    if (mounted) dishForm.value.image_url = result.url;
  } catch (error) { if (mounted) imageError.value = errorText(error); }
  finally { if (mounted) uploading.value = false; }
}
function resetFilters() { search.value = ''; status.value = 'all'; }
</script>

<template>
  <section class="menu-manager" aria-label="菜单管理">
    <div v-if="!canWrite" class="mg-notice readonly-note"><CircleAlert :size="16" /><span>当前账号只有查看权限。如需修改菜品，请联系门店管理员。</span></div>
    <div v-if="pageError" class="mg-error" role="alert"><span>{{ pageError }}</span><button class="mg-button small" type="button" :disabled="operationBusy" @click="reload()"><RefreshCw :size="14" />重新加载</button></div>
    <div class="menu-layout">
      <aside class="category-sidebar" aria-label="菜品分类">
        <header class="category-heading"><h2>菜品分类</h2><button v-if="canWrite" class="category-add" type="button" :disabled="operationBusy || refreshNeeded" aria-label="新增分类" title="新增分类" @click="startCategory()"><Plus :size="17" /></button></header>
        <nav class="category-list">
          <button class="category-link" :class="{ active: selectedCategory === null }" type="button" @click="selectedCategory = null"><span>全部菜品</span><span class="category-count">{{ allDishes.length }}</span></button>
          <div v-for="category in categories" :key="category.id" class="category-item" :class="{ active: selectedCategory === category.id }">
            <button class="category-link" type="button" @click="selectedCategory = category.id"><span class="category-name">{{ category.name }}<small v-if="!category.enabled">已停用</small></span><span class="category-count">{{ category.dishes.length }}</span></button>
            <button v-if="canWrite" class="category-edit" type="button" :disabled="operationBusy || refreshNeeded" :aria-label="`编辑分类：${category.name}`" :title="`编辑分类：${category.name}`" @click="startCategory(category)"><Pencil :size="13" /></button>
          </div>
        </nav>
        <p v-if="!categories.length" class="no-categories">尚未添加分类</p>
        <div v-if="canWrite" class="category-bottom"><button class="mg-button small" type="button" :disabled="operationBusy || refreshNeeded" @click="startCategory()"><Plus :size="14" />新增分类</button></div>
      </aside>

      <div class="dish-panel">
        <header class="dish-heading"><div><h2>{{ selectedCategoryData?.name || '全部菜品' }}</h2><span class="result-count">{{ visibleDishes.length }} 道菜品</span></div><div class="mg-actions"><button class="mg-button" type="button" :disabled="operationBusy" @click="reload()"><RefreshCw :size="15" :class="{ 'mg-spin': loading }" /><span class="refresh-label">刷新</span></button><button v-if="canWrite" class="mg-button primary" type="button" :disabled="operationBusy || refreshNeeded || !categories.length" @click="startDish()"><Plus :size="16" />新增菜品</button></div></header>
        <div v-if="selectedCategoryData && !selectedCategoryData.enabled" class="category-paused"><CircleAlert :size="15" /><span>此分类已停用，分类下的菜品不会显示在顾客菜单中。</span><button v-if="canWrite" type="button" :disabled="operationBusy || refreshNeeded" @click="startCategory(selectedCategoryData)">编辑分类</button></div>
        <div class="dish-toolbar"><label class="search-field"><Search :size="17" /><input v-model="search" type="search" aria-label="搜索菜品名称" placeholder="搜索菜品名称"><button v-if="search" type="button" class="clear-search" aria-label="清空搜索" @click="search = ''"><X :size="14" /></button></label><label class="status-filter"><span class="sr-only">筛选菜品状态</span><select v-model="status"><option value="all">全部状态</option><option value="available">在售</option><option value="sold">已售罄</option><option value="disabled">已下架</option></select><ChevronDown :size="14" /></label></div>
        <div v-if="!categories.length" class="mg-empty"><Utensils :size="30" /><strong>先创建一个菜品分类</strong><p>按主食、小吃、饮品等分类，方便顾客查找。</p><button v-if="canWrite" class="mg-button primary" type="button" :disabled="operationBusy || refreshNeeded" @click="startCategory()"><Plus :size="15" />新增分类</button></div>
        <div v-else-if="!visibleDishes.length" class="mg-empty"><Search :size="28" /><strong>{{ search || status !== 'all' ? '没有符合条件的菜品' : '这里还没有菜品' }}</strong><p>{{ search || status !== 'all' ? '试试其他名称，或清除筛选条件。' : '添加菜品后，顾客就能在对应分类下查看。' }}</p><button v-if="search || status !== 'all'" class="mg-button" type="button" @click="resetFilters">清除筛选</button><button v-else-if="canWrite" class="mg-button primary" type="button" :disabled="operationBusy || refreshNeeded" @click="startDish()"><Plus :size="15" />新增菜品</button></div>
        <div v-else class="dish-list" :aria-busy="loading">
          <div class="dish-list-head"><span>菜品</span><span>售价</span><span>库存 / 月售</span><span>状态</span><span>操作</span></div>
          <article v-for="dish in visibleDishes" :key="dish.id" class="dish-row" :class="{ 'dish-disabled': !dish.enabled }">
            <div class="dish-identity"><img :src="imageUrl(dish.image_url)" alt="" loading="lazy" @error="imageFallback"><div><h3>{{ dish.name }}</h3><p>{{ dish.categoryName }}</p><span v-if="dish.description" class="dish-description">{{ dish.description }}</span></div></div>
            <div class="dish-price"><span class="mobile-label">售价</span><strong>¥{{ money(dish.price_cents) }}</strong><del v-if="dish.original_price_cents !== null && dish.original_price_cents > dish.price_cents">¥{{ money(dish.original_price_cents) }}</del></div>
            <div class="dish-stock"><span>库存 {{ dish.stock === null ? '不限' : dish.stock }}</span><small>月售 {{ dish.monthly_sales }}</small></div>
            <div class="dish-status"><span class="mg-badge" :class="{ neutral: !dish.enabled || !dish.categoryEnabled, warning: dish.enabled && (dish.sold_out || dish.stock === 0) }">{{ !dish.enabled ? '已下架' : dish.sold_out || dish.stock === 0 ? '已售罄' : !dish.categoryEnabled ? '分类停用' : '在售' }}</span></div>
            <div class="dish-actions"><template v-if="canWrite"><button class="mg-button small edit-dish" type="button" :disabled="operationBusy || refreshNeeded" :aria-label="`编辑菜品：${dish.name}`" @click="startDish(dish)"><Pencil :size="13" />编辑</button><button class="row-action" type="button" :disabled="operationBusy || refreshNeeded" @click="quickChange(dish, 'enabled')">{{ dish.enabled ? '下架' : '上架' }}</button><button v-if="dish.enabled" class="row-action" type="button" :disabled="operationBusy || refreshNeeded || (dish.stock === 0 && !dish.sold_out)" :title="dish.stock === 0 ? '库存为 0，请编辑库存后恢复销售' : undefined" @click="quickChange(dish, 'sold_out')">{{ dish.sold_out ? '取消售罄' : dish.stock === 0 ? '库存为 0' : '售罄' }}</button><LoaderCircle v-if="quickBusy === dish.id" :size="14" class="mg-spin" /></template><span v-else class="read-only-label">只读</span></div>
          </article>
        </div>
      </div>
    </div>

    <ManagedDialog v-if="editor === 'category'" :title="editingCategoryId === null ? '新增分类' : '编辑分类'" :busy="editorBusy" @close="closeEditor">
      <form @submit.prevent="saveCategory">
        <div v-if="formError" class="mg-error" role="alert">{{ formError }}</div>
        <fieldset :disabled="editorBusy" class="editor-fields">
          <label class="mg-field"><span>分类名称 <em>*</em></span><input v-model="categoryForm.name" required maxlength="80" placeholder="例如：招牌主食" autocomplete="off"></label>
          <label class="mg-field"><span>排序</span><input v-model="categoryForm.sort_order" inputmode="numeric" required><small>数字越小，分类越靠前。</small></label>
          <label class="mg-check category-enabled"><input v-model="categoryForm.enabled" type="checkbox">启用此分类</label>
          <p class="mg-hint">停用后，该分类及其菜品不向顾客展示，已有内容会保留。</p>
        </fieldset>
        <footer class="editor-footer"><button class="mg-button" type="button" :disabled="editorBusy" @click="closeEditor">取消</button><button class="mg-button primary" :disabled="editorBusy || !canWrite"><LoaderCircle v-if="saving" :size="15" class="mg-spin" /><Check v-else :size="15" />{{ saving ? '保存中…' : '保存分类' }}</button></footer>
      </form>
    </ManagedDialog>

    <ManagedDialog v-if="editor === 'dish'" :title="editingDishId === null ? '新增菜品' : '编辑菜品'" :busy="editorBusy" wide @close="closeEditor">
      <form @submit.prevent="saveDish">
        <div v-if="formError" class="mg-error" role="alert">{{ formError }}</div>
        <fieldset :disabled="editorBusy" class="editor-fields">
          <div class="mg-form-grid">
            <label class="mg-field"><span>菜品名称 <em>*</em></span><input v-model="dishForm.name" required maxlength="120" placeholder="请输入菜品名称" autocomplete="off"></label>
            <label class="mg-field"><span>所属分类 <em>*</em></span><select v-model.number="dishForm.category_id" required><option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}{{ category.enabled ? '' : '（已停用）' }}</option></select></label>
            <label class="mg-field"><span>售价（元）<em>*</em></span><input v-model="dishForm.price" inputmode="decimal" required placeholder="例如：18.50"><small>最多保留两位小数。</small></label>
            <label class="mg-field"><span>原价（元）</span><input v-model="dishForm.original_price" inputmode="decimal" placeholder="选填"><small>不低于售价，留空则不显示划线价。</small></label>
            <div class="mg-field full"><span>菜品图片</span><div class="image-editor"><div class="image-preview"><img v-if="dishForm.image_url" :src="imageUrl(dishForm.image_url)" alt="菜品图片预览" @error="imageFallback"><ImagePlus v-else :size="25" /></div><div class="image-controls"><input ref="imageInput" class="sr-only" type="file" accept="image/jpeg,image/png,image/webp" aria-label="选择菜品图片" @change="uploadImage"><div class="image-buttons"><button class="mg-button" type="button" :disabled="editorBusy" @click="imageInput?.click()"><LoaderCircle v-if="uploading" :size="15" class="mg-spin" /><ImagePlus v-else :size="15" />{{ uploading ? '上传中…' : dishForm.image_url ? '更换图片' : '上传图片' }}</button><button v-if="dishForm.image_url" class="row-action" type="button" :disabled="editorBusy" @click="dishForm.image_url = ''; imageError = ''">移除</button></div><p class="mg-hint">支持 JPG、PNG、WebP，单张不超过 5 MB。<br>建议使用清晰的方形实拍图。</p></div></div><p v-if="imageError" class="inline-error" role="alert">{{ imageError }}<button class="row-action" type="button" :disabled="editorBusy" @click="imageInput?.click()">重新选择</button></p></div>
            <label class="mg-field full"><span>菜品描述</span><textarea v-model="dishForm.description" rows="3" maxlength="2000" placeholder="介绍食材、口味或份量，方便顾客选择"></textarea></label>
            <label class="mg-field"><span>库存</span><input v-model="dishForm.stock" inputmode="numeric" placeholder="留空表示不限库存"><small>填 0 表示无库存；只能填写非负整数。</small></label>
            <label class="mg-field"><span>月售数量</span><input v-model="dishForm.monthly_sales" inputmode="numeric" required><small>展示在顾客菜单中的月售数量。</small></label>
            <label class="mg-field"><span>排序</span><input v-model="dishForm.sort_order" inputmode="numeric" required><small>数字越小，同分类下展示越靠前。</small></label>
            <div class="mg-field"><span>销售状态</span><div class="sale-controls"><label class="mg-check"><input v-model="dishForm.enabled" type="checkbox">上架菜品</label><label class="mg-check"><input v-model="dishForm.sold_out" type="checkbox">标记售罄</label></div></div>
          </div>
        </fieldset>
        <footer class="editor-footer"><span class="save-hint">保存后同步到本店菜单</span><button class="mg-button" type="button" :disabled="editorBusy" @click="closeEditor">取消</button><button class="mg-button primary" :disabled="editorBusy || !canWrite"><LoaderCircle v-if="saving" :size="15" class="mg-spin" /><Check v-else :size="15" />{{ saving ? '保存中…' : uploading ? '图片上传中…' : '保存菜品' }}</button></footer>
      </form>
    </ManagedDialog>
  </section>
</template>

<style scoped>
.menu-manager{min-width:0}.readonly-note{justify-content:flex-start;margin-top:0}.readonly-note svg{flex-shrink:0}.menu-layout{display:grid;grid-template-columns:190px minmax(0,1fr);gap:20px;align-items:start}.category-sidebar{background:white;border:1px solid var(--mg-line);border-radius:6px;overflow:hidden}.category-heading{display:flex;align-items:center;justify-content:space-between;padding:17px 15px 12px}.category-heading h2{font-size:13px;font-weight:650;color:#5f7166}.category-add{display:flex;align-items:center;justify-content:center;width:27px;height:27px;border:1px solid #dce5de;border-radius:5px;color:var(--mg-green)}.category-list{padding:0 8px 10px}.category-link{width:100%;min-height:42px;text-align:left;display:flex;align-items:center;justify-content:space-between;gap:6px;padding:10px;border-radius:5px;font-size:13px;color:#4a5d50}.category-link.active,.category-item.active{background:#edf5ef;color:#21634b}.category-link:hover,.category-item:hover{background:#f3f7f4}.category-item{display:flex;align-items:center;border-radius:5px}.category-item .category-link{flex:1;min-width:0;padding-right:4px}.category-count{font-size:11px;color:#819087;font-variant-numeric:tabular-nums}.category-name{overflow-wrap:anywhere;line-height:1.5}.category-name small{display:block;color:#909b94;font-size:10px;font-weight:400}.category-edit{display:flex;align-items:center;justify-content:center;flex-shrink:0;width:25px;height:29px;padding:0;color:#87968c;margin-right:3px}.category-edit:hover{color:#21634b}.category-bottom{border-top:1px solid #e5ebe6;padding:12px 15px}.no-categories{font-size:12px;color:#89968c;padding:0 18px 20px}.dish-panel{min-width:0;background:white;border:1px solid var(--mg-line);border-radius:6px;overflow:hidden}.dish-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:19px 21px 17px}.dish-heading>div:first-child{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}.dish-heading h2{font-size:17px;font-weight:650}.result-count{font-size:12px;color:#89968d}.dish-toolbar{display:flex;align-items:center;gap:12px;padding:0 21px 19px}.search-field{position:relative;display:flex;align-items:center;max-width:330px;flex:1;color:#829086}.search-field>svg{position:absolute;left:12px;pointer-events:none}.search-field input{padding-left:37px;padding-right:32px;min-height:38px;font-size:13px}.search-field input::-webkit-search-cancel-button{display:none}.clear-search{position:absolute;right:9px;display:flex;align-items:center;justify-content:center;padding:4px;color:#708177}.status-filter{position:relative;display:block;width:132px;flex-shrink:0}.status-filter select{appearance:none;padding-right:29px;min-height:38px;font-size:13px}.status-filter>svg{position:absolute;right:10px;top:13px;pointer-events:none;color:#738277}.category-paused{display:flex;align-items:center;gap:8px;margin:0 21px 17px;padding:10px 12px;background:#faf6ec;border:1px solid #eee2ca;border-radius:5px;color:#866834;font-size:12px;line-height:1.6}.category-paused>svg{flex-shrink:0}.category-paused button{font-size:12px;text-decoration:underline;white-space:nowrap;margin-left:auto}.dish-list-head,.dish-row{display:grid;grid-template-columns:minmax(180px,1fr) 82px 100px 77px 168px;align-items:center;gap:14px;padding:15px 21px}.dish-list-head{background:#f7f9f7;color:#738277;font-size:12px;padding-top:11px;padding-bottom:11px;border-top:1px solid #e5ebe6;border-bottom:1px solid #e5ebe6}.dish-row{border-bottom:1px solid #e9eeea;min-height:103px}.dish-row:last-child{border-bottom:0}.dish-identity{display:flex;align-items:center;gap:13px;min-width:0}.dish-identity img{width:62px;height:62px;flex-shrink:0;border-radius:5px;background:#f3f5f3;border:1px solid #e8ece9;object-fit:cover}.dish-identity>div{min-width:0}.dish-identity h3{font-size:14px;font-weight:600;line-height:1.5;overflow-wrap:anywhere}.dish-identity p{font-size:12px;color:#819085;margin-top:4px}.dish-description{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11px;color:#98a198;margin-top:5px;max-width:250px}.dish-price{font-variant-numeric:tabular-nums}.dish-price strong{font-size:15px;font-weight:600;color:#2e4335}.dish-price del{display:block;font-size:11px;color:#99a298;margin-top:5px}.dish-stock{font-size:12px;color:#5f7466;line-height:1.7}.dish-stock small{display:block;color:#8c9a90;font-size:11px;margin-top:3px}.dish-status{display:flex}.dish-actions{display:flex;align-items:center;justify-content:flex-start;flex-wrap:wrap;gap:8px}.row-action{font-size:12px;color:#557562;padding:5px 1px;line-height:1.5;white-space:nowrap}.row-action:hover:not(:disabled){text-decoration:underline}.row-action:disabled{opacity:.4;cursor:not-allowed}.read-only-label{font-size:12px;color:#8d9990}.dish-disabled .dish-identity img{opacity:.65}.dish-disabled .dish-identity h3{color:#8b958d}.mobile-label{display:none}.mg-empty>svg{margin:0 auto 12px;color:#9caea1}.editor-fields{border:0;padding:0;margin:0;min-width:0}.editor-fields em{color:#a55245;font-style:normal;margin-left:3px}.editor-footer{display:flex;align-items:center;justify-content:flex-end;gap:10px;margin-top:24px;padding-top:20px;border-top:1px solid #e1e8e2}.save-hint{margin-right:auto;font-size:12px;color:#849387}.category-enabled{margin-top:20px}.sale-controls{display:flex;gap:20px;align-items:center;min-height:40px;flex-wrap:wrap}.image-editor{display:flex;align-items:center;gap:18px}.image-preview{width:100px;height:100px;display:flex;align-items:center;justify-content:center;background:#f6f8f6;border:1px solid #dfe7e0;border-radius:5px;flex-shrink:0;color:#95a69a;overflow:hidden}.image-preview img{width:100%;height:100%;object-fit:cover}.image-buttons{display:flex;align-items:center;gap:13px;flex-wrap:wrap}.inline-error{font-size:12px;color:#a44236;margin-top:9px;line-height:1.6}.inline-error button{margin-left:8px}.image-controls{min-width:0}.image-controls .mg-hint{margin-top:9px}
@media(min-width:1500px){.dish-list-head,.dish-row{grid-template-columns:minmax(230px,1fr) 100px 115px 90px 180px;gap:20px}}
@media(max-width:1180px){.menu-layout{grid-template-columns:165px minmax(0,1fr);gap:15px}.dish-list-head,.dish-row{grid-template-columns:minmax(160px,1fr) 72px 83px 70px 125px;gap:10px;padding-left:17px;padding-right:17px}.dish-identity img{width:53px;height:53px}.dish-actions{gap:6px}.dish-actions .edit-dish{flex-basis:75px}.dish-stock{font-size:11px}.dish-heading{padding-left:17px;padding-right:17px}.dish-toolbar{padding-left:17px;padding-right:17px}.dish-description{max-width:165px}}
@media(max-width:960px){.menu-layout{grid-template-columns:1fr;gap:14px}.category-heading{padding:12px 14px 4px}.category-heading .category-add{height:26px}.category-list{display:flex;align-items:center;gap:6px;overflow:auto;padding:7px 10px 10px}.category-link{width:auto;min-height:35px;white-space:nowrap;gap:12px;padding:7px 10px}.category-item{flex-shrink:0}.category-item .category-link{padding-right:6px}.category-name small{display:inline;margin-left:5px}.category-bottom{display:none}.no-categories{padding:5px 15px 12px}.dish-list-head,.dish-row{grid-template-columns:minmax(180px,1fr) 86px 100px 83px 166px}.dish-actions .edit-dish{flex-basis:auto}.dish-actions{gap:9px}.dish-identity img{width:58px;height:58px}}
@media(max-width:760px){.dish-list-head{display:none}.dish-row{grid-template-columns:minmax(0,1fr) auto;gap:9px 14px;padding:17px;border-top:1px solid #e9eeea;border-bottom:0}.dish-identity{grid-column:1;grid-row:1;align-self:start}.dish-identity h3{font-size:14px}.dish-identity img{width:58px;height:58px}.dish-description{max-width:100%}.dish-price{grid-column:2;grid-row:1;align-self:center;text-align:right}.dish-stock{grid-column:1;grid-row:2;display:flex;gap:14px;padding-left:71px;font-size:11px}.dish-stock small{display:inline;margin:0}.dish-status{grid-column:2;grid-row:2;justify-content:flex-end}.dish-actions{grid-column:1/-1;grid-row:3;justify-content:flex-end;margin-top:3px;gap:17px}.dish-actions .edit-dish{margin-right:auto}.dish-heading{padding:16px}.dish-heading h2{font-size:16px}.dish-heading>div:first-child{gap:7px}.dish-toolbar{padding:0 16px 16px;gap:10px}.search-field{max-width:none}.status-filter{width:118px}.category-paused{margin:0 16px 15px;flex-wrap:wrap}.save-hint{display:none}}
@media(max-width:430px){.dish-heading{gap:8px}.dish-heading .mg-actions{gap:7px}.dish-heading .mg-button{padding:8px 10px;font-size:12px}.dish-heading .mg-button:not(.primary){padding:8px}.refresh-label{display:none}.dish-heading>div:first-child{display:block}.result-count{display:block;margin-top:5px;font-size:11px}.dish-identity{gap:10px}.dish-stock{padding-left:0;margin-top:3px}.dish-actions{margin-top:7px}.image-editor{gap:12px}.image-preview{width:86px;height:86px}.image-controls .mg-hint{font-size:11px}.image-controls .mg-button{padding:7px 10px}.editor-footer{gap:8px}}
</style>
