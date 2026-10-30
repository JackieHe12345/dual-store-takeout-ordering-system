<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { LocateFixed, MapPin, Plus, Trash2 } from 'lucide-vue-next';
import { api } from './api';

interface Tier { up_to_meters: number; fee_cents: number }
interface Settings {
  store_id: number; address: string; city: string | null; latitude: number; longitude: number;
  coordinate_system: string; delivery_radius_meters: number; delivery_location_confirmed: boolean;
  delivery_fee_tiers: Tier[]; provider_ready: boolean; distance_method: 'straight'; delivery_places: Place[];
}
interface Place { id: string; title: string; address: string; latitude: number; longitude: number; city: string | null; coordinate_system: string }
interface PlaceForm { id: string; title: string; address: string; latitude: string; longitude: string; city: string; coordinate_system: string }
const props = defineProps<{ apiPrefix: string; canWrite: boolean }>();
const emit = defineEmits<{ notice: [message: string]; saved: [settings: Settings] }>();
const loading = ref(false), saving = ref(false), error = ref(''), locationNotice = ref('');
const ready = ref(false), savedSnapshot = ref(''), locatingTarget = ref<string | null>(null);
const form = ref({ address: '', city: '', latitude: '', longitude: '', coordinate_system: 'GCJ_02', confirmed: false, tiers: [] as { km: string; yuan: string }[], places: [] as PlaceForm[] });
const trialKm = ref(''), trialResult = computed(() => {
  if (!trialKm.value.trim()) return '';
  const distance = Number(trialKm.value);
  if (!Number.isFinite(distance) || distance < 0) return '请填写有效距离';
  const tiers = validTiers();
  if (!tiers) return '请先填写完整的费用分档';
  const rawMeters = distance * 1000, roundedMeters = Math.round(rawMeters);
  const meters = Math.abs(rawMeters - roundedMeters) <= 1e-7 ? roundedMeters : rawMeters;
  const tier = tiers.find(t => meters <= t.up_to_meters);
  return tier ? `配送费 ¥${(tier.fee_cents / 100).toFixed(2)}` : '超出配送范围';
});
const dirty = computed(() => ready.value && JSON.stringify(form.value) !== savedSnapshot.value);
const radius = computed(() => form.value.tiers.at(-1)?.km || '—');
let sequence = 0, locationVersion = 0;
function confirmLeave() {
  if (saving.value) { emit('notice', '配送设置正在保存，请稍候'); return false; }
  return !dirty.value || window.confirm('配送设置尚未保存，确定放弃修改？');
}
defineExpose({ confirmLeave, reload: load });
function fill(data: Settings) {
  form.value = { address: data.address, city: data.city || '', latitude: String(data.latitude), longitude: String(data.longitude), coordinate_system: data.coordinate_system.replaceAll('-', '_'), confirmed: data.delivery_location_confirmed,
    tiers: data.delivery_fee_tiers.map(t => ({ km: String(t.up_to_meters / 1000), yuan: (t.fee_cents / 100).toFixed(2) })), places: (data.delivery_places || []).map(p => ({ ...p, city: p.city || '', latitude: String(p.latitude), longitude: String(p.longitude), coordinate_system: p.coordinate_system.replaceAll('-', '_') })) };
  savedSnapshot.value = JSON.stringify(form.value); ready.value = true;
}
async function load() {
  const request = ++sequence, prefix = props.apiPrefix;
  ready.value = false; loading.value = true; error.value = ''; locationNotice.value = ''; cancelLocate();
  try { const data = await api<Settings>(`${prefix}/delivery-settings`); if (request === sequence) fill(data); }
  catch (e) { if (request === sequence) error.value = (e as Error).message; }
  finally { if (request === sequence) loading.value = false; }
}
function cancelLocate() { ++locationVersion; locatingTarget.value = null; }
function locationChanged() { cancelLocate(); form.value.confirmed = false; locationNotice.value = ''; }
watch(() => props.apiPrefix, load, { immediate: true });
function addPlace() {
  const id = globalThis.crypto?.randomUUID?.() || 'place-' + Date.now() + '-' + Math.random().toString(36).slice(2);
  form.value.places.push({ id, title: '', address: '', city: form.value.city, latitude: '', longitude: '', coordinate_system: 'WGS_84' });
}
function deletePlace(index: number) { cancelLocate(); form.value.places.splice(index, 1); }
async function locate(target: 'store' | string) {
  if (!props.canWrite || saving.value) return;
  cancelLocate(); locationNotice.value = ''; error.value = '';
  if (!window.isSecureContext || !navigator.geolocation) { error.value = '当前网址无法使用浏览器定位。请使用 HTTPS 网址，或展开坐标设置手动填写位置。'; return; }
  const version = ++locationVersion, request = sequence;
  locatingTarget.value = target;
  try {
    const point = await new Promise<GeolocationPosition>((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }));
    if (version !== locationVersion || request !== sequence) return;
    if (!Number.isFinite(point.coords.accuracy) || point.coords.accuracy > 200) { error.value = '定位误差较大，请在地点附近重新定位，或手动填写准确坐标。'; return; }
    const destination = target === 'store' ? form.value : form.value.places.find(p => p.id === target.slice(6));
    if (!destination) return;
    destination.latitude = String(point.coords.latitude); destination.longitude = String(point.coords.longitude); destination.coordinate_system = 'WGS_84';
    if (target === 'store') form.value.confirmed = false;
    locationNotice.value = '已获取当前位置，定位精度约 ' + Math.ceil(point.coords.accuracy) + ' 米。请核实位置并保存。';
  } catch (e) {
    if (version !== locationVersion || request !== sequence) return;
    const code = (e as GeolocationPositionError).code;
    error.value = code === 1 ? '定位权限未开启，请允许定位或手动填写坐标。' : code === 3 ? '定位超时，请重试或手动填写坐标。' : '暂时无法定位，请重试或手动填写坐标。';
  } finally { if (version === locationVersion) locatingTarget.value = null; }
}
function validCoordinates(latitude: string, longitude: string) { const lat = Number(latitude), lng = Number(longitude); return !!latitude.trim() && !!longitude.trim() && Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180 && !(lat === 0 && lng === 0); }
function validTiers(): Tier[] | null {
  if (!form.value.tiers.length) return null;
  const result: Tier[] = [];
  for (const row of form.value.tiers) {
    if (!/^\d+(\.\d{1,3})?$/.test(row.km.trim()) || !/^\d+(\.\d{1,2})?$/.test(row.yuan.trim())) return null;
    const meters = Math.round(Number(row.km) * 1000), cents = Math.round(Number(row.yuan) * 100);
    if (meters <= (result.at(-1)?.up_to_meters || 0) || meters > 100000 || cents > 1000000) return null;
    result.push({ up_to_meters: meters, fee_cents: cents });
  }
  return result;
}
async function save() {
  if (saving.value || !props.canWrite || locatingTarget.value) return;
  error.value = '';
  const tiers = validTiers();
  if (!form.value.address.trim() || !form.value.city.trim()) { error.value = '请填写门店地址和所在城市'; return; }
  const lat = Number(form.value.latitude), lng = Number(form.value.longitude);
  if (!validCoordinates(form.value.latitude, form.value.longitude)) { error.value = '请在门店定位，或填写有效的门店坐标'; return; }
  if (!tiers) { error.value = '请填写递增的距离上限（最多 100 公里）和配送费（最多两位小数，每档不超过 10000 元）'; return; }
  for (let index = 0; index < form.value.places.length; index++) {
    const place = form.value.places[index];
    if (!place.title.trim() || !place.address.trim() || !validCoordinates(place.latitude, place.longitude)) { error.value = '请补全第 ' + (index + 1) + ' 个常送地点的名称、地址和有效坐标。'; return; }
  }
  const request = sequence;
  saving.value = true;
  try {
    const data = await api<Settings>(`${props.apiPrefix}/delivery-settings`, { method: 'PATCH', body: JSON.stringify({ address: form.value.address.trim(), city: form.value.city.trim(), latitude: lat, longitude: lng, coordinate_system: form.value.coordinate_system, delivery_radius_meters: tiers.at(-1)!.up_to_meters, delivery_location_confirmed: form.value.confirmed, delivery_fee_tiers: tiers, delivery_places: form.value.places.map(p => ({ ...p, title: p.title.trim(), address: p.address.trim(), city: p.city.trim() || null, latitude: Number(p.latitude), longitude: Number(p.longitude) })) }) });
    if (request !== sequence) return;
    fill(data); emit('notice', '配送设置已保存，顾客重新核算地址时使用新费用'); emit('saved', data);
  } catch (e) { if (request === sequence) error.value = (e as Error).message; }
  finally { if (request === sequence) saving.value = false; }
}
function beforeUnload(event: BeforeUnloadEvent) { if (dirty.value || saving.value) { event.preventDefault(); event.returnValue = ''; } }
window.addEventListener('beforeunload', beforeUnload);
onBeforeUnmount(() => { ++sequence; cancelLocate(); window.removeEventListener('beforeunload', beforeUnload); });
</script>

<template>
  <div class="delivery-settings">
    <p v-if="loading" class="mg-panel mg-empty" role="status">正在读取配送设置…</p>
    <p v-if="error" class="mg-error" role="alert">{{ error }} <button v-if="!ready" class="mg-button" @click="load">重试</button></p>
    <template v-if="ready">
      <p class="mg-notice">直线距离在系统内计算，无需地图 Key。顾客可选择下方常送地点，或在收货地点点击定位。</p>
      <p v-if="locationNotice" class="mg-notice" role="status">{{ locationNotice }}</p>
      <p v-if="!canWrite" class="mg-notice">当前账号可查看配送设置。请使用门店管理员账号调整。</p>
      <form @submit.prevent="save" @input="cancelLocate">
        <fieldset :disabled="!canWrite || saving" class="delivery-fieldset">
          <section class="mg-panel">
            <div class="delivery-section-title"><MapPin :size="19" /><h2>配送起点</h2></div>
            <p class="mg-hint">按门店与收货地点的直线距离计费。请站在门店定位，或填写已核实的坐标。</p>
            <div class="delivery-location-grid">
              <label class="mg-field"><span>所在城市</span><input v-model="form.city" maxlength="80" placeholder="例如：中山市" required @input="locationChanged"><small>填写本店服务的城市</small></label>
              <div class="mg-field"><span>门店位置</span><button type="button" class="mg-button" :disabled="!!locatingTarget" @click="locate('store')"><LocateFixed :size="16" />{{ locatingTarget === 'store' ? '正在定位…' : '在门店定位' }}</button><small>只在点击后请求定位权限；需要 HTTPS 网址。也可手动填写坐标。</small>
              </div>
            </div>
            <label class="mg-field"><span>门店详细地址</span><input v-model="form.address" maxlength="500" required placeholder="请输入门店详细地址" @input="locationChanged"></label>
            <details class="delivery-coordinates"><summary>查看或手动填写门店坐标</summary><label class="mg-field"><span>坐标来源</span><select v-model="form.coordinate_system" @change="locationChanged"><option value="GCJ_02">腾讯 / 高德地图 · GCJ-02</option><option value="WGS_84">GPS 原始定位 · WGS-84</option><option value="BD_09">百度地图 · BD-09</option></select></label><div class="mg-form-grid"><label class="mg-field"><span>纬度</span><input v-model="form.latitude" inputmode="decimal" @input="locationChanged"></label><label class="mg-field"><span>经度</span><input v-model="form.longitude" inputmode="decimal" @input="locationChanged"></label></div></details>
            <label class="mg-check delivery-confirm"><input v-model="form.confirmed" type="checkbox"><span>已确认上述地点为本店实际配送起点</span></label>
            <p v-if="!form.confirmed" class="mg-hint">确认门店地点后，顾客地址才能计算配送范围。</p>
          </section>
          <section class="mg-panel delivery-common-places">
            <div class="delivery-section-title"><h2>常送地点</h2><button v-if="canWrite" type="button" class="mg-button small" :disabled="form.places.length >= 100" @click="addPlace"><Plus :size="15" />添加地点</button></div>
            <p class="mg-hint">录入常送的小区、学校或写字楼。顾客可搜索选择这些地点，再填写楼栋和门牌号。</p>
            <p v-if="!form.places.length" class="delivery-no-tiers">暂无常送地点。点击“添加地点”开始，每个地点的坐标只需校准一次。</p>
            <article v-for="(place, index) in form.places" :key="place.id" class="delivery-common-place">
              <div class="delivery-place-heading"><strong>{{ place.title || ('地点 ' + (index + 1)) }}</strong><button v-if="canWrite" type="button" class="mg-button small danger" :aria-label="'删除常送地点' + (index + 1)" @click="deletePlace(index)"><Trash2 :size="15" />删除</button></div>
              <div class="mg-form-grid"><label class="mg-field"><span>地点名称</span><input v-model="place.title" required maxlength="120" :aria-label="'常送地点' + (index + 1) + '名称'" placeholder="例如：某某花园"></label><label class="mg-field"><span>所在城市</span><input v-model="place.city" maxlength="80" :aria-label="'常送地点' + (index + 1) + '城市'" placeholder="城市"></label></div>
              <label class="mg-field"><span>地点地址</span><input v-model="place.address" required maxlength="500" :aria-label="'常送地点' + (index + 1) + '地址'" placeholder="街道、小区或学校地址"></label>
              <div class="delivery-place-position"><button v-if="canWrite" type="button" class="mg-button small" :disabled="!!locatingTarget" @click="locate('place:' + place.id)"><LocateFixed :size="15" />{{ locatingTarget === 'place:' + place.id ? '正在定位…' : '在此地点定位' }}</button><span class="mg-hint">{{ place.latitude && place.longitude ? '坐标已填写，请核实地点位置' : '请在地点现场定位，或展开坐标设置手动填写' }}</span></div>
              <details class="delivery-coordinates"><summary>填写或查看此地点坐标</summary><label class="mg-field"><span>坐标来源</span><select v-model="place.coordinate_system" :aria-label="'常送地点' + (index + 1) + '坐标来源'"><option value="WGS_84">GPS 原始定位 · WGS-84</option><option value="GCJ_02">腾讯 / 高德地图 · GCJ-02</option><option value="BD_09">百度地图 · BD-09</option></select></label><div class="mg-form-grid"><label class="mg-field"><span>纬度</span><input v-model="place.latitude" :aria-label="'常送地点' + (index + 1) + '纬度'" inputmode="decimal"></label><label class="mg-field"><span>经度</span><input v-model="place.longitude" :aria-label="'常送地点' + (index + 1) + '经度'" inputmode="decimal"></label></div></details>
            </article>
          </section>
          <section class="mg-panel delivery-fees">
            <div class="delivery-section-title"><h2>按距离设置配送费</h2><button v-if="canWrite" type="button" class="mg-button small" :disabled="form.tiers.length >= 30" @click="form.tiers.push({ km: '', yuan: '' })"><Plus :size="15" />增加一档</button></div>
            <p class="mg-hint">距离上限从小到大填写，最后一档就是最远配送距离。刚好到达上限时，按该档收费。</p>
            <div v-if="!form.tiers.length" class="delivery-no-tiers">尚未设置配送费，点击“增加一档”开始。</div>
            <div v-for="(tier, index) in form.tiers" :key="index" class="delivery-tier-row">
              <div class="delivery-tier-start">{{ index ? `超过 ${form.tiers[index - 1].km || '…'} 公里` : '从门店出发' }}</div>
              <label class="delivery-unit-field"><span>至</span><input v-model="tier.km" inputmode="decimal" :aria-label="`第${index + 1}档距离上限`" placeholder="公里" required><span>公里</span></label>
              <label class="delivery-unit-field"><span>¥</span><input v-model="tier.yuan" inputmode="decimal" :aria-label="`第${index + 1}档配送费`" placeholder="费用" required><span>元</span></label>
              <button v-if="canWrite" type="button" class="mg-button small danger" :aria-label="`删除第${index + 1}档`" @click="form.tiers.splice(index, 1)"><Trash2 :size="15" /></button>
            </div>
            <p class="delivery-radius">最远配送 <strong>{{ radius }} 公里</strong>，超过该距离显示“超出配送范围”。</p>
          </section>
          <section class="mg-panel delivery-trial"><div><h2>费用试算</h2><p class="mg-hint">输入直线距离，预览当前表单的收费规则。</p></div><label class="delivery-unit-field"><input v-model="trialKm" inputmode="decimal" aria-label="试算直线距离" placeholder="直线距离"><span>公里</span></label><strong role="status">{{ trialResult }}</strong></section>
          <div v-if="canWrite" class="delivery-save"><span class="mg-muted">{{ dirty ? '有修改尚未保存' : '所有修改已保存' }}</span><button class="mg-button primary" :disabled="saving || !!locatingTarget || !dirty">{{ saving ? '正在保存…' : '保存配送设置' }}</button></div>
        </fieldset>
      </form>
    </template>
  </div>
</template>

<style scoped>
.delivery-settings { max-width: 1040px; }
.delivery-fieldset { padding: 0; margin: 0; border: 0; min-width: 0; }
.delivery-section-title { display: flex; align-items: center; gap: 10px; justify-content: space-between; }
.delivery-section-title > svg { color: var(--mg-green); }
.delivery-section-title > h2 { margin-right: auto; }
.delivery-location-grid { display: grid; grid-template-columns: minmax(140px, 1fr) minmax(220px, 2fr); gap: 20px; margin: 24px 0 20px; }
.delivery-location-grid .mg-field { margin: 0; }
.delivery-location-grid label[for] { display: block; margin-bottom: 8px; font-size: 13px; font-weight: 550; }
.delivery-search { display: flex; align-items: center; position: relative; }
.delivery-search svg { position: absolute; left: 12px; color: #77867d; }
.delivery-search input { padding-left: 37px; }
.delivery-place-results { border: 1px solid var(--mg-line); border-radius: 6px; max-height: 280px; overflow: auto; margin-top: 8px; }
.delivery-place-results button { display: block; width: 100%; padding: 12px; text-align: left; border-bottom: 1px solid var(--mg-line); }
.delivery-place-results button:last-child { border: 0; }
.delivery-place-results button:hover { background: var(--mg-green-soft); }
.delivery-place-results strong,.delivery-place-results small { display: block; line-height: 1.6; }
.delivery-place-results small { color: var(--mg-muted); font-size: 12px; }
.delivery-coordinates { margin-top: 18px; font-size: 12px; color: var(--mg-muted); }
.delivery-coordinates summary { cursor: pointer; padding: 8px 0; }
.delivery-coordinates .mg-form-grid { margin-top: 12px; }
.delivery-confirm { margin-top: 18px; }
.delivery-no-tiers { padding: 24px 0; color: var(--mg-muted); }
.delivery-common-place { border: 1px solid var(--mg-line); border-radius: 6px; padding: 18px; margin-top: 18px; }
.delivery-place-heading { display: flex; justify-content: space-between; align-items: center; gap: 14px; margin-bottom: 18px; }
.delivery-place-heading > strong { overflow-wrap: anywhere; min-width: 0; }
.delivery-common-place > .mg-field { margin-top: 18px; }
.delivery-place-position { display: flex; align-items: center; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
.delivery-place-position .mg-hint { margin: 0; }
.delivery-tier-row { display: grid; grid-template-columns: minmax(150px, 1.1fr) minmax(170px, 1fr) minmax(150px, 1fr) auto; align-items: center; gap: 18px; border-bottom: 1px solid var(--mg-line); padding: 18px 0; }
.delivery-tier-start { font-size: 13px; }
.delivery-unit-field { display: flex; align-items: center; gap: 8px; min-width: 0; }
.delivery-unit-field span { flex-shrink: 0; color: var(--mg-muted); font-size: 12px; }
.delivery-unit-field input { min-width: 0; }
.delivery-radius { margin-top: 18px; font-size: 13px; color: var(--mg-muted); line-height: 1.7; }
.delivery-radius strong { color: var(--mg-green); }
.delivery-trial { display: grid; grid-template-columns: 1.5fr 1fr 1fr; align-items: center; gap: 24px; }
.delivery-trial > strong { font-size: 14px; color: var(--mg-green); }
.delivery-save { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-top: 24px; font-size: 12px; }
@media (max-width: 760px) { .delivery-tier-row { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 10px; }.delivery-tier-start { grid-column: 1/-1; }.delivery-location-grid,.delivery-trial { grid-template-columns: 1fr; gap: 18px; }.delivery-unit-field { gap: 5px; }.delivery-tier-row input { padding: 9px; }.delivery-save { flex-wrap: wrap; } }
@media (max-width: 460px) { .delivery-common-place { padding: 14px; } }
</style>
