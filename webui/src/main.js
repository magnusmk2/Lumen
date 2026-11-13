import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import { helpDirective } from './lib/help.js'

createApp(App).directive('help', helpDirective).mount('#app')
