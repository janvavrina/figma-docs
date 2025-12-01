import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/Dashboard.vue'),
    },
    {
      path: '/files',
      name: 'files',
      component: () => import('../views/FigmaFiles.vue'),
    },
    {
      path: '/docs',
      name: 'docs',
      component: () => import('../views/Documentation.vue'),
    },
    {
      path: '/docs/:id',
      name: 'doc-detail',
      component: () => import('../views/DocDetail.vue'),
    },
    {
      path: '/analyze',
      name: 'analyze',
      component: () => import('../views/Analyze.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/Settings.vue'),
    },
  ],
})

export default router

