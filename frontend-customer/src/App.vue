<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '../../frontend-shared/api';
import LegacyApp from './LegacyApp.vue';
import CommerceCustomer from './CommerceCustomer.vue';
const ready=ref(false),enabled=ref(false);
onMounted(async()=>{try{enabled.value=(await api<{enabled:boolean}>('commerce/capabilities')).enabled;}catch{enabled.value=false;}finally{ready.value=true;}});
</script>
<template><CommerceCustomer v-if="ready&&enabled"/><LegacyApp v-else-if="ready"/><p v-else style="text-align:center;padding:40px">正在加载门店…</p></template>
