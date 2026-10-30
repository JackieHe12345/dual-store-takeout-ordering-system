<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { X } from 'lucide-vue-next';
defineProps<{ title: string; wide?: boolean }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLElement>();
const previous = document.activeElement as HTMLElement | null;
const oldOverflow = document.body.style.overflow;
function key(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close');
  if (event.key !== 'Tab') return;
  const elements = [...(dialog.value?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]') || [])].filter(e => e.getClientRects().length);
  const first = elements[0], last = elements.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
}
onMounted(async () => { document.body.style.overflow = 'hidden'; document.addEventListener('keydown', key); await nextTick(); dialog.value?.focus(); });
onBeforeUnmount(() => { document.body.style.overflow = oldOverflow; document.removeEventListener('keydown', key); previous?.focus(); });
</script>
<template>
  <Teleport to="body"><div class="modal-backdrop" @click.self="emit('close')"><section ref="dialog" class="modal" :class="{ wide }" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1">
    <header class="modal-header"><h2>{{ title }}</h2><button class="icon-btn" aria-label="关闭" @click="emit('close')"><X :size="21" /></button></header>
    <slot />
  </section></div></Teleport>
</template>
