import { defineStore } from 'pinia';
import { ref, watch } from 'vue';
import { entryName } from '../../frontend-shared/api';
const key = `takeaway-cart:${entryName}`;
export const useCart = defineStore('cart', () => {
  let saved: Record<string, number> = {};
  try {
    const raw = JSON.parse(localStorage.getItem(key) || '{}');
    if (raw && typeof raw === 'object' && !Array.isArray(raw))
      for (const [id, quantity] of Object.entries(raw))
        if (/^\d+$/.test(id) && Number.isInteger(quantity) && Number(quantity) > 0 && Number(quantity) <= 99) saved[id] = Number(quantity);
  } catch { /* A fresh cart is safe when storage is unavailable. */ }
  const quantities = ref(saved);
  watch(quantities, value => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* In-memory cart remains usable. */ } }, { deep: true });
  function change(id: number, delta: number, maximum = 99) {
    const next = Math.min(maximum, Math.max(0, (quantities.value[id] || 0) + delta));
    if (next) quantities.value[id] = next;
    else delete quantities.value[id];
  }
  function clear() { quantities.value = {}; }
  return { quantities, change, clear };
});
