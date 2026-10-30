import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import '../../frontend-shared/base.css';
import './style.css';
import './address.css';
createApp(App).use(createPinia()).mount('#app');
