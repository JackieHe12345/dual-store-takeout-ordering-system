<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ArrowLeft, Check, ChevronRight, LocateFixed, MapPin, Pencil, Plus, Search, Trash2, Truck, X } from 'lucide-vue-next';
import { money } from '../../frontend-shared/api';
import { checkDelivery, deliveryAllowed, geolocationPlace, isLocatedPlace, routeDistance, useAddresses, validPlace } from './address';
import type { DeliveryCheck, Place, SavedAddress } from './address.types';

const emit = defineEmits<{ close: []; selected: [] }>();
const book = useAddresses();
const view = ref<'list' | 'edit' | 'places'>('list');
const draft = ref({ id: '', contact: '', phone: '', detail: '', tag: '', isDefault: false });
const selectedPlace = ref<Place | null>(null), pointName = ref(''), pointAddress = ref(''), formError = ref(''), deleteConfirm = ref(false);
const query = ref(''), placeError = ref('');
const locating = ref(false), locationError = ref(''), locationResult = ref<Place | null>(null);
const checks = ref<Record<string, { loading: boolean; result?: DeliveryCheck; error?: string }>>({});
let listController: AbortController | undefined;
let listVersion = 0, locationVersion = 0;
const sortedAddresses = computed(() => [...book.items].sort((a, b) => Number(b.isDefault) - Number(a.isDefault)));
const commonPlaces = computed(() => (Array.isArray(book.config?.places) ? book.config.places : []).filter(validPlace));
const places = computed(() => {
  const keywords = query.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return commonPlaces.value.filter(place => keywords.every(q => `${place.title} ${place.address} ${place.city || ''}`.toLocaleLowerCase().includes(q)));
});
const locatedPoint = computed(() => isLocatedPlace(selectedPlace.value));
function setPoint(place: Place | null) {
  selectedPlace.value = place ? { ...place } : null;
  pointName.value = place && place.title !== '已定位的收货点' ? place.title : '';
  pointAddress.value = place?.address || '';
}
function startNew() {
  cancelLocation();
  draft.value = { id: '', contact: '', phone: '', detail: '', tag: '', isDefault: !book.items.length };
  setPoint(null); formError.value = ''; deleteConfirm.value = false; view.value = 'edit';
  window.scrollTo(0, 0);
}
function edit(address: SavedAddress) {
  cancelLocation();
  draft.value = { id: address.id, contact: address.contact, phone: address.phone, detail: address.detail, tag: address.tag, isDefault: address.isDefault };
  setPoint(address.place); formError.value = ''; deleteConfirm.value = false; view.value = 'edit'; window.scrollTo(0, 0);
}
function openPlaces() {
  cancelLocation(); query.value = ''; placeError.value = ''; locationError.value = '';
  view.value = 'places'; window.scrollTo(0, 0);
}
function manualSearch() { if (view.value === 'list') startNew(); openPlaces(); }
function back() {
  cancelLocation();
  if (view.value === 'places') view.value = 'edit';
  else if (view.value === 'edit') view.value = 'list';
  else emit('close');
  window.scrollTo(0, 0);
}
function choosePlace(place: Place) {
  if (!validPlace(place)) { placeError.value = '这个常送地址的信息不完整，请选择其他地址或联系门店'; return; }
  cancelLocation(); setPoint(place); formError.value = ''; view.value = 'edit'; window.scrollTo(0, 0);
}
function save() {
  const contact = draft.value.contact.trim(), phone = draft.value.phone.replace(/\s/g, ''), detail = draft.value.detail.trim();
  if (!contact) { formError.value = '请填写收货人姓名'; return; }
  if (!/^1[3-9]\d{9}$/.test(phone)) { formError.value = '请填写 11 位中国大陆手机号'; return; }
  if (!selectedPlace.value || !validPlace(selectedPlace.value)) { formError.value = '请选择常送地址，或点击定位确定收货位置'; return; }
  if (locatedPoint.value && !pointName.value.trim()) { formError.value = '请填写定位点所在的小区、街道或建筑名称'; return; }
  if (!detail) { formError.value = '请填写楼栋、楼层或门牌号，方便配送员找到你'; return; }
  if (!draft.value.id && book.items.length >= 50) { formError.value = '当前设备最多保存 50 个地址，请先删除不再使用的地址'; return; }
  const place = { ...selectedPlace.value };
  if (locatedPoint.value) { place.title = pointName.value.trim(); place.address = pointAddress.value.trim(); }
  book.save({ ...draft.value, id: draft.value.id || globalThis.crypto?.randomUUID?.() || `address-${Date.now()}-${Math.random().toString(36).slice(2)}`, contact, phone, detail, place });
  view.value = 'list'; formError.value = ''; window.scrollTo(0, 0);
}
function remove() { if (draft.value.id) book.remove(draft.value.id); deleteConfirm.value = false; view.value = 'list'; }
function select(address: SavedAddress) {
  if (checks.value[address.id]?.result?.within_range === false) return;
  book.selectedId = address.id; emit('selected');
}
function cancelLocation() { ++locationVersion; locating.value = false; }
watch(query, cancelLocation);
async function locate() {
  locationError.value = ''; locationResult.value = null;
  if (!window.isSecureContext) { locationError.value = '当前页面使用 HTTP，浏览器无法定位。请通过 HTTPS 打开，或选择常送地址'; return; }
  if (!navigator.geolocation) { locationError.value = '当前浏览器不支持定位，可以选择常送地址'; return; }
  const version = ++locationVersion; locating.value = true;
  const fromList = view.value === 'list';
  try {
    const position = await new Promise<GeolocationPosition>((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }));
    if (version !== locationVersion) return;
    const result = geolocationPlace(position, book.config?.city || null);
    locationResult.value = result;
    if (fromList) startNew();
    cancelLocation(); setPoint(result); formError.value = ''; view.value = 'edit'; window.scrollTo(0, 0);
  } catch (e) {
    if (version !== locationVersion) return;
    const geolocationError = e as GeolocationPositionError;
    locationError.value = geolocationError.code === 1 ? '定位权限未开启，可以在浏览器设置中允许定位，或选择常送地址' : geolocationError.code === 2 ? '暂时获取不到当前位置，请重试或选择常送地址' : geolocationError.code === 3 ? '定位超时，请重试或选择常送地址' : (e as Error).message || '定位失败，请选择常送地址';
  } finally { if (version === locationVersion) locating.value = false; }
}
async function refreshChecks() {
  const version = ++listVersion; listController?.abort(); listController = new AbortController();
  const signal = listController.signal;
  checks.value = {};
  if (book.configNotice) return;
  const list = [...book.items]; list.forEach(a => { checks.value[a.id] = { loading: true }; });
  let cursor = 0;
  await Promise.all(Array.from({ length: Math.min(3, list.length) }, async () => {
    while (cursor < list.length && version === listVersion) {
      const address = list[cursor++];
      try { const result = await checkDelivery(address.place, signal); if (version === listVersion) checks.value[address.id] = { loading: false, result }; }
      catch (e) { if (version === listVersion) checks.value[address.id] = { loading: false, error: (e as Error).message }; }
    }
  }));
}
watch(() => [book.items.map(a => `${a.id}:${a.place.latitude}:${a.place.longitude}:${a.place.coordinate_system}`).join('|'), book.config, book.configNotice], refreshChecks, { immediate: true });
onMounted(book.loadConfig);
onBeforeUnmount(() => { cancelLocation(); ++listVersion; listController?.abort(); });
</script>

<template>
  <div class="address-page">
    <header class="address-header"><button class="icon-btn" :aria-label="view === 'list' ? '返回' : '返回上一步'" @click="back"><ArrowLeft :size="23" /></button><h1>{{ view === 'list' ? '选择收货地址' : view === 'places' ? '选择所在地址' : draft.id ? '编辑收货地址' : '新增收货地址' }}</h1><span class="header-spacer"></span></header>
    <template v-if="view === 'list'">
      <section class="location-block">
        <div class="address-section-heading"><h2>当前定位</h2><button class="relocate" :disabled="locating" @click="locate"><LocateFixed :size="15" />{{ locating ? '正在定位…' : '重新定位' }}</button></div>
        <button class="current-location" :disabled="locating" @click="locate"><MapPin :size="20" /><span><strong>{{ locationResult?.title || '点击获取当前位置' }}</strong><small>仅在点击后申请定位权限</small></span><ChevronRight :size="18" /></button>
        <div v-if="locationError" class="address-alert" role="status"><p>{{ locationError }}</p><button @click="manualSearch">选择常送地址<ChevronRight :size="14" /></button></div>
      </section>
      <section class="address-list-section">
        <div class="address-section-heading"><h2>我的收货地址</h2><span>{{ book.items.length }} 个地址</span></div>
        <p v-if="book.configNotice" class="address-config-notice" role="status">{{ book.configNotice }}<button v-if="!book.configLoading" @click="book.loadConfig">重试</button></p>
        <div v-if="!book.items.length" class="address-empty"><div class="empty-map-icon"><MapPin :size="30" /></div><h3>还没有收货地址</h3><p>选择常送地点，或定位添加新地址</p><button class="address-primary" @click="startNew"><Plus :size="17" />添加收货地址</button></div>
        <article v-for="address in sortedAddresses" :key="address.id" class="saved-address" :class="{ 'address-selected': book.selectedId === address.id, 'address-outside': checks[address.id]?.result?.within_range === false }">
          <button class="address-select-button" :disabled="checks[address.id]?.result?.within_range === false" :aria-label="`选择${address.place.title} ${address.detail}`" @click="select(address)"><span class="address-choice"><Check v-if="book.selectedId === address.id" :size="15" /></span><div class="saved-address-copy"><div class="address-title-line"><span v-if="address.isDefault" class="address-default">默认</span><span v-if="address.tag" class="address-tag">{{ address.tag }}</span><h3>{{ address.place.title }}</h3></div><p class="address-street">{{ address.place.address }} {{ address.detail }}</p><p class="address-contact">{{ address.contact }} <span>{{ address.phone }}</span></p><p v-if="checks[address.id]?.loading" class="address-route">正在计算直线距离…</p><p v-else-if="deliveryAllowed(checks[address.id]?.result)" class="address-route"><Truck :size="12" />直线距离 {{ routeDistance(checks[address.id].result!.distance_meters!) }}<span>配送费 ¥{{ money(checks[address.id].result!.delivery_fee_cents!) }}</span></p><p v-else-if="checks[address.id]?.result?.within_range === false" class="address-route outside">超出本店配送范围<span v-if="checks[address.id].result!.distance_meters !== null">直线距离 {{ routeDistance(checks[address.id].result!.distance_meters!) }}</span></p><p v-else-if="checks[address.id]?.error || checks[address.id]?.result?.reason" class="address-route outside">{{ checks[address.id]?.error || checks[address.id]?.result?.reason }}</p></div></button>
          <button class="address-edit-button" :aria-label="`编辑${address.place.title}`" @click="edit(address)"><Pencil :size="18" /></button><button v-if="!address.isDefault" class="set-default-button" @click="book.setDefault(address.id)">设为默认</button>
        </article>
      </section>
      <p class="address-storage-note">地址仅保存在当前设备 · 仅用于当前门店入口</p><p v-if="book.storageFailed" class="address-alert">浏览器未能保存地址，关闭页面后可能丢失，请检查存储权限。</p><footer class="address-bottom"><button class="address-primary" @click="startNew"><Plus :size="20" />新增收货地址</button></footer>
    </template>
    <template v-else-if="view === 'edit'">
      <form class="address-editor" @submit.prevent="save">
        <section class="address-form-card">
          <label class="address-field"><span>收货人</span><input v-model="draft.contact" placeholder="请输入收货人姓名" autocomplete="name" maxlength="30"></label>
          <label class="address-field"><span>手机号</span><input v-model="draft.phone" type="tel" inputmode="tel" placeholder="请输入手机号码" autocomplete="tel" maxlength="15"></label>
          <div class="address-field"><span>所在地址</span><button type="button" class="address-place-picker" @click="openPlaces"><span><strong :class="{ placeholder: !selectedPlace }">{{ selectedPlace?.title || '选择常送地址 / 定位' }}</strong><small v-if="selectedPlace">{{ selectedPlace.address || (locatedPoint ? '已确定定位点，请补充详细地址' : '') }}</small></span><ChevronRight :size="18" /></button></div>
          <template v-if="locatedPoint"><label class="address-field"><span>小区/街道</span><input v-model="pointName" placeholder="请输入小区、街道或建筑名称" autocomplete="address-line1" maxlength="100"></label><label class="address-field"><span>补充地址</span><input v-model="pointAddress" placeholder="道路、社区等（选填）" maxlength="200"></label></template>
          <label class="address-field address-detail-field"><span>门牌号</span><input v-model="draft.detail" placeholder="例：3 号楼 2 单元 501 室" maxlength="100" autocomplete="address-line2"></label>
          <div class="address-field address-tags"><span>标签</span><div><button v-for="tag in ['家', '公司', '学校']" :key="tag" type="button" :class="{ active: draft.tag === tag }" @click="draft.tag = draft.tag === tag ? '' : tag">{{ tag }}</button></div></div>
        </section>
        <p v-if="locatedPoint" class="located-point-note"><LocateFixed :size="15" /><span>已确定收货定位点<span v-if="selectedPlace?.accuracy_meters !== undefined">，精度约 {{ selectedPlace.accuracy_meters }} 米</span>。补充地址文字不会改变计费位置；需要换地点时，请重新定位或选择常送地址。</span></p>
        <label class="address-default-field"><span><strong>设为默认收货地址</strong><small>下次点餐优先使用此地址</small></span><input v-model="draft.isDefault" type="checkbox"><span class="address-toggle" aria-hidden="true"></span></label>
        <p v-if="formError" class="address-alert" role="alert">{{ formError }}</p><p class="address-storage-note">地址仅保存在当前设备</p><button class="address-primary save-address" type="submit">保存地址</button><button v-if="draft.id" type="button" class="delete-address" @click="deleteConfirm = true"><Trash2 :size="16" />删除收货地址</button><div v-if="deleteConfirm" class="address-delete-confirm" role="alert"><p>删除后需重新添加此地址。</p><button type="button" @click="deleteConfirm = false">取消</button><button type="button" class="danger" @click="remove">确认删除</button></div>
      </form>
    </template>
    <template v-else>
      <section class="place-search">
        <div class="common-place-heading"><h2>门店常送地址</h2><span v-if="book.config?.city">{{ book.config.city }}</span></div>
        <div class="poi-search"><Search :size="19" /><input v-model="query" type="search" aria-label="搜索常送地址" placeholder="搜索小区、写字楼、学校" maxlength="80" autofocus><button v-if="query" class="icon-btn" aria-label="清空搜索" @click="query = ''"><X :size="17" /></button></div>
        <button class="use-location" :disabled="locating" @click="locate"><LocateFixed :size="17" />{{ locating ? '正在获取当前位置…' : '使用当前位置，添加新地址' }}</button><p v-if="locationError" class="address-alert" role="status">{{ locationError }}</p><p class="place-hint">选择门店已登记的地点，再补充门牌号。其他地点可使用当前位置添加。</p>
      </section>
      <section class="place-results" aria-live="polite">
        <p v-if="book.configLoading && !book.config" class="place-search-state">正在读取常送地址…</p>
        <div v-else-if="book.configError" class="address-alert" role="alert"><p>{{ book.configError }}</p><button @click="book.loadConfig">重新加载常送地址</button></div>
        <p v-else-if="placeError" class="address-alert" role="alert">{{ placeError }}</p>
        <p v-else-if="!commonPlaces.length" class="place-search-state">门店还没有添加常送地址<br><small>可使用当前位置添加，或联系门店</small></p>
        <p v-else-if="!places.length" class="place-search-state">常送地址中没有找到这个地点<br><small>换个关键词，或使用当前位置添加</small></p>
        <button v-for="place in places" :key="place.id" class="place-result" @click="choosePlace(place)"><MapPin :size="19" /><span><strong>{{ place.title }}</strong><small v-if="place.address">{{ place.address }}</small></span><ChevronRight :size="17" /></button>
      </section>
    </template>
  </div>
</template>
