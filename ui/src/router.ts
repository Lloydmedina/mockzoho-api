import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'

export const router = createRouter({
  history: createWebHistory('/ui/'),
  routes: [
    { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
    { path: '/:module', name: 'module', component: () => import('./views/ModuleView.vue'), props: true },
    { path: '/:module/new', name: 'create', component: () => import('./views/DetailView.vue'), props: true },
    { path: '/:module/:id', name: 'detail', component: () => import('./views/DetailView.vue'), props: true },
    { path: '/', redirect: { name: 'module', params: { module: 'Cases' } } },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!auth.token && to.name !== 'login') return { name: 'login' }
})
