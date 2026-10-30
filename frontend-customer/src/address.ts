import { defineStore } from 'pinia';
import { computed, ref, watch } from 'vue';
import { api, entryName } from '../../frontend-shared/api';
import type { DeliveryCheck, DeliveryConfig, Place, SavedAddress } from './address.types';

const storageKey = `takeaway-addresses:${entryName}`;
export function validPlace(value: unknown): value is Place {
  if (!value || typeof value !== 'object') return false;
  const p = value as Partial<Place>;
  return typeof p.id === 'string' && !!p.id && typeof p.title === 'string' && !!p.title.trim() && typeof p.address === 'string' &&
    ['WGS_84', 'GCJ_02', 'BD_09'].includes(p.coordinate_system || '') && typeof p.latitude === 'number' && Number.isFinite(p.latitude) && p.latitude >= -90 && p.latitude <= 90 &&
    typeof p.longitude === 'number' && Number.isFinite(p.longitude) && p.longitude >= -180 && p.longitude <= 180 && (p.city === null || typeof p.city === 'string');
}

export const isLocatedPlace = (place: Place | null | undefined) => !!place?.id.startsWith('location:');
export function geolocationPlace(position: Pick<GeolocationPosition, 'coords'>, city: string | null): Place {
  const { latitude, longitude, accuracy } = position.coords;
  if (!Number.isFinite(accuracy) || accuracy < 0 || accuracy > 200) throw new Error('当前定位精度不足，请到开阔处重新定位，或选择常送地址');
  const place: Place = { id: `location:${latitude},${longitude}`, title: '已定位的收货点', address: '', latitude, longitude, coordinate_system: 'WGS_84', city, accuracy_meters: Math.ceil(accuracy) };
  if (!validPlace(place)) throw new Error('无法识别当前位置，请重新定位或选择常送地址');
  return place;
}

function validAddress(value: unknown): value is SavedAddress {
  if (!value || typeof value !== 'object') return false;
  const a = value as Partial<SavedAddress>;
  return typeof a.id === 'string' && typeof a.contact === 'string' && a.contact.length <= 30 && !!a.contact.trim() &&
    typeof a.phone === 'string' && /^1[3-9]\d{9}$/.test(a.phone) && typeof a.detail === 'string' && !!a.detail.trim() &&
    typeof a.tag === 'string' && typeof a.isDefault === 'boolean' && validPlace(a.place);
}
export const deliveryAllowed = (result: DeliveryCheck | null | undefined) => !!result?.available && result.within_range === true && result.delivery_fee_cents !== null;
export const routeDistance = (meters: number) => meters < 1000 ? `${meters} 米` : `${(meters / 1000).toFixed(3).replace(/\.?0+$/, '')} 公里`;
export const useAddresses = defineStore('addresses', () => {
  let initial: SavedAddress[] = [], initialSelection = '';
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
    if (saved && Array.isArray(saved.items)) {
      initial = saved.items.filter(validAddress).slice(0, 50);
      // Normalize defaults and IDs even when an older browser record is malformed.
      initial = initial.filter((a, index, all) => all.findIndex(b => b.id === a.id) === index);
      const defaultIndex = initial.findIndex(a => a.isDefault);
      initial.forEach((a, i) => { a.isDefault = i === defaultIndex; });
      initialSelection = typeof saved.selectedId === 'string' ? saved.selectedId : '';
    }
  } catch { /* The address book remains usable without local storage. */ }
  const items = ref(initial);
  const selectedId = ref(initial.some(a => a.id === initialSelection) ? initialSelection : (initial.find(a => a.isDefault)?.id || initial[0]?.id || ''));
  const selected = computed(() => items.value.find(a => a.id === selectedId.value) || null);
  const storageFailed = ref(false);
  const config = ref<DeliveryConfig | null>(null), configLoading = ref(false), configError = ref('');
  let configRequest = 0;
  watch([items, selectedId], () => {
    try { localStorage.setItem(storageKey, JSON.stringify({ items: items.value, selectedId: selectedId.value })); storageFailed.value = false; }
    catch { storageFailed.value = true; }
  }, { deep: true });
  const configNotice = computed(() => {
    if (configError.value) return configError.value;
    if (!config.value) return configLoading.value ? '正在获取配送设置…' : '暂未获取配送设置';
    if (!config.value.location_confirmed) return '门店尚未确认位置，暂无法计算配送距离';
    if (!config.value.fees_configured) return '门店尚未设置配送费，暂无法确认配送金额';
    return '';
  });
  async function loadConfig() {
    const request = ++configRequest;
    configLoading.value = true; configError.value = '';
    try { const response = await api<DeliveryConfig>('delivery/config'); if (request === configRequest) config.value = response; }
    catch (e) { if (request === configRequest) { config.value = null; configError.value = (e as Error).message; } }
    finally { if (request === configRequest) configLoading.value = false; }
  }
  function save(address: SavedAddress) {
    if (address.isDefault) items.value.forEach(a => { a.isDefault = false; });
    const index = items.value.findIndex(a => a.id === address.id);
    if (index >= 0) items.value[index] = address;
    else items.value.push(address);
    if (!selectedId.value) selectedId.value = address.id;
  }
  function remove(id: string) {
    items.value = items.value.filter(a => a.id !== id);
    if (selectedId.value === id) selectedId.value = items.value.find(a => a.isDefault)?.id || items.value[0]?.id || '';
  }
  function setDefault(id: string) { items.value.forEach(a => { a.isDefault = a.id === id; }); }
  return { items, selectedId, selected, storageFailed, config, configLoading, configError, configNotice, loadConfig, save, remove, setDefault };
});
export async function checkDelivery(place: Place, signal?: AbortSignal): Promise<DeliveryCheck> {
  return api<DeliveryCheck>('delivery/check', { method: 'POST', signal, body: JSON.stringify({ latitude: place.latitude, longitude: place.longitude, coordinate_system: place.coordinate_system }) });
}
