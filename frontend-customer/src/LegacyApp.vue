<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ArrowLeft, ArrowRight, Check, ChevronRight, CookingPot, Flame, Heart, MapPin, Minus, Phone, Plus, Search, ShoppingBag, ShoppingCart, Soup, Store as StoreIcon, Trash2, Truck, UtensilsCrossed, X } from 'lucide-vue-next';
import { api, entry, imageFallback, imageUrl, money } from '../../frontend-shared/api';
import type { Category, Dish, Menu } from '../../frontend-shared/types';
import Modal from '../../frontend-shared/Modal.vue';
import { useCart } from './cart';
import AddressBook from './AddressBook.vue';
import { checkDelivery, deliveryAllowed, routeDistance, useAddresses } from './address';
import type { DeliveryCheck } from './address.types';

const menu = ref<Menu | null>(null), loading = ref(true), error = ref('');
const cart = useCart();
const activeCategory = ref<number | 'store'>(0), search = ref(''), searching = ref(false);
const panel = ref<'cart' | 'orders' | null>(null), selectedDish = ref<Dish | null>(null);
const pageFromHash = () => location.hash === '#checkout' ? 'checkout' : location.hash === '#addresses' ? 'addresses' : 'menu';
const currentPage = ref(pageFromHash()), addressReturn = ref('menu');
const addresses = useAddresses();
const deliveryResult = ref<DeliveryCheck | null>(null), deliveryLoading = ref(false), deliveryError = ref('');
let deliveryController: AbortController | undefined, deliveryVersion = 0;
const fulfillment = ref('pickup'), contactName = ref(''), phone = ref(''), toast = ref('');
let toastTimer: ReturnType<typeof setTimeout>;
let observer: IntersectionObserver | undefined;
const dishes = computed(() => menu.value?.categories.flatMap(c => c.dishes) || []);
const visibleCategories = computed(() => (menu.value?.categories || []).map(c => ({ ...c, dishes: c.dishes.filter(d => `${d.name}${d.description || ''}`.includes(search.value.trim())) })).filter(c => !search.value || c.dishes.length));
const lines = computed(() => dishes.value.filter(d => cart.quantities[d.id] && d.enabled && !d.sold_out && d.stock !== 0 && !d.requires_options).map(d => ({ dish: d, quantity: Math.min(cart.quantities[d.id], d.stock ?? 99) })));
const quantity = computed(() => lines.value.reduce((sum, l) => sum + l.quantity, 0));
const total = computed(() => lines.value.reduce((sum, l) => sum + l.dish.price_cents * l.quantity, 0));
const deliveryFee = computed(() => fulfillment.value === 'delivery' && deliveryAllowed(deliveryResult.value) ? deliveryResult.value!.delivery_fee_cents : null);
const checkoutTotal = computed(() => total.value + (deliveryFee.value ?? 0));
const storeName = computed(() => menu.value?.store.name || (entry.store === 'A' ? '升福记' : '升升快餐'));
const tel = computed(() => `tel:${menu.value?.store.phone.replace(/[^\d+]/g, '') || ''}`);
function notify(text: string) { toast.value = text; clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.value = '', 2600); }
function change(dish: Dish, delta: number) {
  if (delta > 0 && dish.requires_options) { selectedDish.value = dish; return; }
  if (delta > 0 && (dish.sold_out || dish.stock === 0)) { notify('这道菜暂时售罄了'); return; }
  const max = Math.min(dish.stock ?? 99, 99);
  if (delta > 0 && (cart.quantities[dish.id] || 0) >= max) { notify('已达到可选数量'); return; }
  cart.change(dish.id, delta, max);
}
function categoryIcon(category: Category) {
  if (/热销/.test(category.name)) return Flame;
  if (/汤|小食/.test(category.name)) return Soup;
  if (/推荐/.test(category.name)) return Heart;
  return CookingPot;
}
async function load() {
  loading.value = true; error.value = '';
  try {
    menu.value = await api<Menu>('menu');
    activeCategory.value = menu.value.categories[0]?.id || 'store';
    document.title = `${menu.value.store.name} · 点餐`;
    const valid = new Set(dishes.value.filter(d => !d.sold_out && d.stock !== 0 && !d.requires_options).map(d => String(d.id)));
    for (const id of Object.keys(cart.quantities)) if (!valid.has(id)) delete cart.quantities[id];
  } catch (e) { error.value = (e as Error).message; }
  finally { loading.value = false; await nextTick(); observe(); }
}
function navigate(page: string) { location.hash = page === 'menu' ? '' : page; currentPage.value = page; window.scrollTo(0, 0); }
function hashChanged() { currentPage.value = pageFromHash(); nextTick(observe); }
function openAddresses() { addressReturn.value = currentPage.value === 'checkout' ? 'checkout' : 'menu'; navigate('addresses'); }
function closeAddresses() { navigate(addressReturn.value); }
async function refreshDelivery() {
  const version = ++deliveryVersion; deliveryController?.abort();
  deliveryResult.value = null; deliveryError.value = ''; deliveryLoading.value = false;
  if (fulfillment.value !== 'delivery' || currentPage.value !== 'checkout' || !addresses.selected) return;
  if (addresses.configNotice) { deliveryError.value = addresses.configNotice; return; }
  deliveryController = new AbortController(); deliveryLoading.value = true;
  try { const result = await checkDelivery(addresses.selected.place, deliveryController.signal); if (version === deliveryVersion) deliveryResult.value = result; }
  catch (e) { if (version === deliveryVersion) deliveryError.value = (e as Error).message; }
  finally { if (version === deliveryVersion) deliveryLoading.value = false; }
}
async function reloadDelivery() { await addresses.loadConfig(); await refreshDelivery(); }
watch(() => [fulfillment.value, currentPage.value, addresses.selected?.id, addresses.selected?.place.latitude, addresses.selected?.place.longitude, addresses.selected?.place.coordinate_system, addresses.config, addresses.configNotice], refreshDelivery);
function observe() {
  observer?.disconnect();
  observer = new IntersectionObserver(entries => {
    const top = entries.filter(e => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
    if (top) activeCategory.value = Number((top.target as HTMLElement).dataset.category);
  }, { rootMargin: '-190px 0px -50% 0px', threshold: 0 });
  document.querySelectorAll('[data-category]').forEach(el => observer?.observe(el));
}
async function chooseCategory(id: number | 'store') {
  activeCategory.value = id;
  if (id === 'store') { observer?.disconnect(); return; }
  if (search.value) search.value = '';
  await nextTick(); observe(); document.getElementById(`category-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
onMounted(() => { load(); addresses.loadConfig(); window.addEventListener('hashchange', hashChanged); });
onBeforeUnmount(() => { ++deliveryVersion; deliveryController?.abort(); observer?.disconnect(); clearTimeout(toastTimer); window.removeEventListener('hashchange', hashChanged); });
</script>

<template>
  <main class="customer-app">
    <template v-if="currentPage === 'menu'">
      <header class="store-header">
        <div class="brand-line"><div><span class="small-eyebrow">用心做好 · 每一餐</span><h1>{{ storeName }}<span class="store-seal">好食</span></h1></div><div class="header-actions"><button class="order-query" @click="panel = 'orders'">查询订单</button><button class="icon-btn" aria-label="搜索菜品" @click="searching = !searching"><Search :size="23" /></button></div></div>
        <div class="store-meta"><a :href="tel"><Phone :size="12" />{{ menu?.store.phone || '正在加载门店信息' }}</a><span>现点现做 · 美味到家</span></div>
        <button class="menu-address-entry" @click="openAddresses"><MapPin :size="14" /><span>{{ addresses.selected ? `${addresses.selected.place.title} ${addresses.selected.detail}` : '添加收货地址，查看配送范围' }}</span><ChevronRight :size="14" /></button>
        <div v-if="searching" class="search-box"><Search :size="18" /><input v-model="search" type="search" aria-label="搜索菜名" placeholder="今天想吃点什么？"><button class="icon-btn" aria-label="关闭搜索" @click="searching = false; search = ''"><X :size="17" /></button></div>
      </header>
      <div class="welcome-strip"><UtensilsCrossed :size="15" /><span>一餐热乎的，刚刚好。</span><span class="strip-flower">✳</span></div>
      <div v-if="loading" class="empty-state">正在为你准备菜单…</div>
      <div v-else-if="error" class="load-error"><p class="error">{{ error }}</p><button class="secondary" @click="load">重新加载</button></div>
      <div v-else class="menu-layout">
        <nav class="category-nav" aria-label="菜品分类"><button v-for="category in menu?.categories" :key="category.id" :class="{ active: activeCategory === category.id }" @click="chooseCategory(category.id)"><component :is="categoryIcon(category)" :size="19" :stroke-width="1.7" /><span>{{ category.name }}</span></button><button :class="{ active: activeCategory === 'store' }" @click="chooseCategory('store')"><StoreIcon :size="19" :stroke-width="1.7" /><span>门店信息</span></button></nav>
        <div class="menu-content">
          <section v-if="activeCategory === 'store'" class="store-information"><div class="store-emblem"><Soup :size="34" /></div><h2>{{ storeName }}</h2><p>认真做好每一餐，<br>把熟悉的好味道留给你。</p><div><MapPin :size="18" /><span>{{ menu?.store.address }}</span></div><a :href="tel"><Phone :size="18" />{{ menu?.store.phone }}</a></section>
          <template v-else>
            <section v-for="category in visibleCategories" :id="`category-${category.id}`" :key="category.id" :data-category="category.id" class="dish-section"><div class="category-heading"><h2>{{ category.name }}</h2><span>{{ category.dishes.length }} 款美味</span></div>
              <article v-for="dish in category.dishes" :key="dish.id" class="dish-card" :class="{ unavailable: dish.sold_out || dish.stock === 0 }">
                <button class="dish-picture" :aria-label="`查看${dish.name}`" @click="selectedDish = dish"><img :src="imageUrl(dish.image_url)" :alt="dish.name" loading="lazy" @error="imageFallback"><span v-if="dish.sold_out || dish.stock === 0" class="sold-out">已售罄</span></button>
                <div class="dish-description"><button class="dish-title" @click="selectedDish = dish">{{ dish.name }}</button><p>{{ dish.description }}</p><span class="dish-sales">{{ dish.monthly_sales > 0 ? `月售 ${dish.monthly_sales}` : '现点现做' }}</span><div class="dish-bottom"><strong class="price"><small>¥</small>{{ money(dish.price_cents) }}<span v-if="dish.requires_options"> 起</span></strong><div v-if="!dish.requires_options" class="quantity-control"><template v-if="cart.quantities[dish.id]"><button class="minus-btn" :aria-label="`减少${dish.name}`" @click="change(dish, -1)"><Minus :size="15" /></button><span>{{ cart.quantities[dish.id] }}</span></template><button class="plus-btn" :disabled="dish.sold_out || dish.stock === 0" :aria-label="`添加${dish.name}`" @click="change(dish, 1)"><Plus :size="19" /></button></div><button v-else class="choose-options" @click="selectedDish = dish">选规格</button></div></div>
              </article><p v-if="!category.dishes.length" class="category-empty">新菜准备中，看看其他分类吧</p>
            </section><div v-if="!visibleCategories.length" class="empty-state">没有找到这道菜<br>试试其他关键词吧</div><p class="menu-end">— 好好吃饭，开心每一天 —</p>
          </template>
        </div>
      </div>
      <footer class="cart-bar"><button class="cart-summary" aria-label="查看购物车" @click="panel = 'cart'"><span class="cart-circle"><ShoppingCart :size="25" /><b v-if="quantity">{{ quantity }}</b></span><span><strong>¥{{ money(total) }}</strong><small>{{ quantity ? '已选好，幸福的一餐' : '挑几道喜欢的菜吧' }}</small></span></button><button class="checkout-btn" :disabled="!quantity" @click="navigate('checkout')">去结算<span v-if="quantity">（{{ quantity }}）</span><ArrowRight :size="17" /></button></footer>
    </template>

    <template v-else-if="currentPage === 'checkout'">
      <header class="page-header"><button class="icon-btn" aria-label="返回菜单" @click="navigate('menu')"><ArrowLeft :size="23" /></button><h1>去结算</h1><span class="header-spacer"></span></header>
      <div class="checkout-content"><div class="checkout-store"><h2>{{ storeName }}</h2><a :href="tel">{{ menu?.store.phone }}</a></div>
        <section class="checkout-card"><h2>选择取餐方式</h2><button v-for="option in [{ value: 'pickup', label: '到店自提', text: '提前选好，到店取餐', icon: ShoppingBag }, { value: 'dinein', label: '来店内就餐', text: '热乎上桌，慢慢享用', icon: UtensilsCrossed }, { value: 'delivery', label: '外送', text: '送到身边，享受美味', icon: Truck }]" :key="option.value" class="fulfillment-option" :class="{ selected: fulfillment === option.value }" @click="fulfillment = option.value"><span class="fulfillment-icon"><component :is="option.icon" :size="25" /></span><span><strong>{{ option.label }}</strong><small>{{ option.text }}</small></span><span class="radio-circle"><Check v-if="fulfillment === option.value" :size="15" /></span></button></section>
        <section class="checkout-card"><h2>{{ fulfillment === 'delivery' ? '配送信息' : '取餐信息' }}</h2><template v-if="fulfillment === 'delivery'"><button class="checkout-address-card" @click="openAddresses"><MapPin :size="22" /><span v-if="addresses.selected"><strong>{{ addresses.selected.place.title }} {{ addresses.selected.detail }}</strong><small>{{ addresses.selected.place.address }}</small><span class="checkout-address-person">{{ addresses.selected.contact }} · {{ addresses.selected.phone }}</span></span><span v-else><strong>请选择收货地址</strong><small>自动计算直线距离和配送费</small></span><ChevronRight :size="20" /></button><div class="checkout-delivery-status" aria-live="polite"><p v-if="deliveryLoading">正在计算直线距离和配送费…</p><template v-else-if="deliveryAllowed(deliveryResult)"><p class="delivery-valid"><Check :size="15" />本店可配送 · 直线距离 {{ routeDistance(deliveryResult!.distance_meters!) }}</p><div><span>配送费</span><strong>¥{{ money(deliveryResult!.delivery_fee_cents!) }}</strong></div></template><p v-else-if="deliveryResult || deliveryError" class="delivery-unavailable">{{ deliveryError || (deliveryResult?.within_range === false ? '超出本店配送范围，请更换收货地址' : deliveryResult?.reason || '暂时无法确认配送，请联系门店') }}<span v-if="deliveryResult?.within_range === false && deliveryResult.distance_meters !== null">直线距离 {{ routeDistance(deliveryResult.distance_meters) }} · 配送范围 {{ routeDistance(deliveryResult.radius_meters) }}</span></p><p v-else-if="addresses.configNotice" class="delivery-unavailable">{{ addresses.configNotice }}</p><p v-else>选好地址后显示直线距离与配送费</p><button v-if="addresses.selected || addresses.configNotice" class="refresh-delivery" :disabled="deliveryLoading || addresses.configLoading" @click="reloadDelivery">{{ deliveryLoading || addresses.configLoading ? '正在刷新…' : '重新计算' }}</button></div></template><template v-else><label class="form-field"><span>联系人</span><input v-model="contactName" placeholder="请输入姓名" autocomplete="name" maxlength="30"></label><label class="form-field"><span>手机号</span><input v-model="phone" inputmode="tel" placeholder="请输入联系电话" autocomplete="tel" maxlength="20"></label></template></section>
        <section class="checkout-card"><div v-for="line in lines" :key="line.dish.id" class="checkout-line"><img :src="imageUrl(line.dish.image_url)" :alt="line.dish.name" @error="imageFallback"><div><h3>{{ line.dish.name }}</h3><span class="muted">× {{ line.quantity }}</span></div><strong class="price">¥{{ money(line.dish.price_cents * line.quantity) }}</strong></div><div v-if="!lines.length" class="empty-state">购物车还是空的</div><div class="checkout-subtotal"><span>商品合计</span><span>¥{{ money(total) }}</span></div><div v-if="fulfillment === 'delivery'" class="checkout-subtotal"><span>配送费</span><span>{{ deliveryFee !== null ? `¥${money(deliveryFee)}` : '待确认' }}</span></div><div class="total-row"><strong>{{ fulfillment === 'delivery' && deliveryFee === null ? '商品金额' : '预计合计' }}</strong><strong class="price">¥{{ money(checkoutTotal) }}</strong></div><p class="checkout-note">{{ fulfillment === 'delivery' ? '配送费按门店当前距离档位计算；包装费与优惠以门店确认金额为准。' : '包装费及优惠以门店确认金额为准。' }}</p></section>
        <p class="inline-notice">在线下单暂未开放，你可以联系门店确认取餐。</p><a class="primary contact-order" :href="tel"><Phone :size="18" />联系门店</a><button class="back-to-menu" @click="navigate('menu')">继续挑选菜品</button>
      </div>
    </template>

    <AddressBook v-if="currentPage === 'addresses'" @close="closeAddresses" @selected="closeAddresses" />

    <Modal v-if="panel === 'cart'" title="已选商品" @close="panel = null"><div v-if="!lines.length" class="empty-state"><ShoppingBag :size="35" /><p>购物车还是空的<br>挑几道喜欢的菜吧</p></div><template v-else><button class="clear-cart" @click="cart.clear()"><Trash2 :size="14" />清空购物车</button><div v-for="line in lines" :key="line.dish.id" class="cart-line"><img :src="imageUrl(line.dish.image_url)" :alt="line.dish.name" @error="imageFallback"><div><h3>{{ line.dish.name }}</h3><strong class="price">¥{{ money(line.dish.price_cents) }}</strong></div><div class="quantity-control"><button class="minus-btn" :aria-label="`减少${line.dish.name}`" @click="change(line.dish, -1)"><Minus :size="15" /></button><span>{{ line.quantity }}</span><button class="plus-btn" :aria-label="`添加${line.dish.name}`" @click="change(line.dish, 1)"><Plus :size="18" /></button></div></div><div class="modal-actions"><button class="primary" @click="panel = null; navigate('checkout')">去结算 · ¥{{ money(total) }}<ChevronRight :size="17" /></button></div></template></Modal>
    <Modal v-if="selectedDish" :title="selectedDish.name" @close="selectedDish = null"><img class="dish-detail-image" :src="imageUrl(selectedDish.image_url)" :alt="selectedDish.name" @error="imageFallback"><p class="dish-detail-text">{{ selectedDish.description || '每一份都用心准备。' }}</p><strong class="detail-price price">¥{{ money(selectedDish.price_cents) }}</strong><p v-if="selectedDish.requires_options" class="inline-notice">此菜品的规格暂未开放选购，请联系门店。</p><div class="modal-actions"><button class="primary" :disabled="selectedDish.requires_options || selectedDish.sold_out || selectedDish.stock === 0" @click="change(selectedDish, 1); selectedDish = null">加入购物车<Plus :size="17" /></button></div></Modal>
    <Modal v-if="panel === 'orders'" title="查询订单" @close="panel = null"><div class="order-unavailable"><ShoppingBag :size="34" /><h3>订单查询暂未开放</h3><p>如需确认订单或取餐信息，<br>请直接联系 {{ storeName }}。</p><a class="primary" :href="tel"><Phone :size="17" />联系门店</a></div></Modal>
    <div v-if="toast" class="toast" role="status">{{ toast }}</div>
  </main>
</template>
