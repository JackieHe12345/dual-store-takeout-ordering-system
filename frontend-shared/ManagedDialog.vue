<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { X } from 'lucide-vue-next';

const props = defineProps<{ title: string; busy?: boolean; wide?: boolean }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLElement>();
const previous = document.activeElement as HTMLElement | null;
const oldOverflow = document.body.style.overflow;

function close() { if (!props.busy) emit('close'); }
function key(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); close(); }
  if (event.key !== 'Tab') return;
  const elements = [...(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]') || [])].filter(element => element.getClientRects().length);
  const first = elements[0], last = elements.at(-1);
  if (!first) { event.preventDefault(); dialog.value?.focus(); }
  else if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
onMounted(async () => {
  document.body.style.overflow = 'hidden';
  document.addEventListener('keydown', key);
  await nextTick();
  dialog.value?.focus();
});
onBeforeUnmount(() => {
  document.body.style.overflow = oldOverflow;
  document.removeEventListener('keydown', key);
  if (previous?.isConnected) previous.focus();
});
</script>

<template>
  <Teleport to="body">
    <div class="mg-dialog-backdrop" @click.self="close">
      <section ref="dialog" class="mg-dialog" :class="{ wide }" role="dialog" aria-modal="true" :aria-label="title" :aria-busy="busy" tabindex="-1">
        <header class="dialog-heading"><h2>{{ title }}</h2><button class="dialog-close" type="button" aria-label="关闭编辑窗口" :disabled="busy" @click="close"><X :size="20" /></button></header>
        <slot />
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.mg-dialog-backdrop{position:fixed;inset:0;z-index:100;background:#18281f66;display:flex;align-items:center;justify-content:center;padding:24px}
.mg-dialog{width:100%;max-width:460px;max-height:calc(100dvh - 48px);overflow:auto;background:#fff;border:1px solid #d6dfd9;border-radius:6px;box-shadow:0 12px 48px #15281d21;outline:none;padding:24px;color:#26332e}
.mg-dialog.wide{max-width:720px}.dialog-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:24px}.dialog-heading h2{font-size:19px;font-weight:650;margin:0}.dialog-close{width:32px;height:32px;display:flex;align-items:center;justify-content:center;border-radius:5px;color:#69776e}.dialog-close:hover:not(:disabled){background:#f1f5f2}.dialog-close:disabled{opacity:.4;cursor:not-allowed}
@media(max-width:600px){.mg-dialog-backdrop{padding:12px}.mg-dialog{padding:20px;max-height:calc(100dvh - 24px)}.dialog-heading{margin-bottom:21px}}
</style>
