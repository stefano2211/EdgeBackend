import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import EventsView from '../views/EventsView.vue'
import WorkspaceLayout from '../views/workspace/WorkspaceLayout.vue'
import PromptsView from '../views/workspace/PromptsView.vue'
import ToolsView from '../views/workspace/ToolsView.vue'
import WebhooksSettingsView from '../views/settings/WebhooksSettingsView.vue'
import ReactiveKnowledgeListView from '../views/reactive/ReactiveKnowledgeListView.vue'
import ReactiveKnowledgeDetailView from '../views/reactive/ReactiveKnowledgeDetailView.vue'
import IntegrationsLayout from '../views/integrations/IntegrationsLayout.vue'
import IntegrationCatalogView from '../views/integrations/IntegrationCatalogView.vue'
import IntegrationInstancesView from '../views/integrations/IntegrationInstancesView.vue'
import IntegrationCredentialsView from '../views/integrations/IntegrationCredentialsView.vue'
import IntegrationRegistryView from '../views/integrations/IntegrationRegistryView.vue'
import AdminUsersView from '../views/admin/AdminUsersView.vue'
import AdminAnalyticsView from '../views/admin/AdminAnalyticsView.vue'
import AdminSettingsView from '../views/admin/AdminSettingsView.vue'

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        // ── Root redirect ──────────────────────────────────────────────
        {
            path: '/',
            name: 'home',
            redirect: '/dashboard'
        },

        // ── Core ─────────────────────────────────────────────────────────
        {
            path: '/dashboard',
            name: 'dashboard',
            component: () => import('@/views/DashboardView.vue'),
            meta: { layout: 'dashboard', requiresAuth: true }
        },
        {
            path: '/login',
            name: 'login',
            component: LoginView,
            meta: { layout: 'auth' }
        },
        {
            path: '/register',
            name: 'register',
            component: RegisterView,
            meta: { layout: 'auth' }
        },
        {
            path: '/chat',
            name: 'chat',
            component: ChatView,
            meta: { layout: 'main', requiresAuth: true }
        },

        // ── Operations ───────────────────────────────────────────────────
        {
            path: '/operations',
            name: 'operations',
            component: EventsView,
            meta: { layout: 'dashboard', requiresAuth: true }
        },

        // ── Resources ────────────────────────────────────────────────────
        {
            path: '/resources/knowledge',
            name: 'resources-knowledge',
            component: ReactiveKnowledgeListView,
            meta: { layout: 'dashboard', requiresAuth: true }
        },
        {
            path: '/resources/knowledge/:id',
            name: 'resources-knowledge-detail',
            component: ReactiveKnowledgeDetailView,
            props: true,
            meta: { layout: 'dashboard', requiresAuth: true }
        },

        // ── Connections (was /database) ──────────────────────────────────
        {
            path: '/connections',
            name: 'connections',
            component: () => import('@/views/database/DatabaseConnectionsView.vue'),
            meta: { layout: 'dashboard', requiresAuth: true }
        },

        // ── Config (was /workspace + /settings/webhooks) ─────────────────
        {
            path: '/config',
            component: WorkspaceLayout,
            meta: { layout: 'main', requiresAuth: true },
            redirect: '/config/prompts',
            children: [
                {
                    path: 'prompts',
                    name: 'config-prompts',
                    component: PromptsView
                },
                {
                    path: 'tools',
                    name: 'config-tools',
                    component: ToolsView
                }
            ]
        },
        {
            path: '/config/webhooks',
            name: 'config-webhooks',
            component: WebhooksSettingsView,
            meta: { layout: 'dashboard', requiresAuth: true }
        },

        // ── Integrations ─────────────────────────────────────────────────
        {
            path: '/integrations',
            component: IntegrationsLayout,
            meta: { layout: 'dashboard', requiresAuth: true },
            redirect: '/integrations/catalog',
            children: [
                {
                    path: 'catalog',
                    name: 'integration-catalog',
                    component: IntegrationCatalogView
                },
                {
                    path: 'instances',
                    name: 'integration-instances',
                    component: IntegrationInstancesView
                },
                {
                    path: 'credentials',
                    name: 'integration-credentials',
                    component: IntegrationCredentialsView
                },
                {
                    path: 'registry',
                    name: 'integration-registry',
                    component: IntegrationRegistryView
                }
            ]
        },

        // ── Admin ────────────────────────────────────────────────────────
        {
            path: '/admin/users',
            name: 'admin-users',
            component: AdminUsersView,
            meta: { layout: 'dashboard', requiresAuth: true }
        },
        {
            path: '/admin/analytics',
            name: 'admin-analytics',
            component: AdminAnalyticsView,
            meta: { layout: 'dashboard', requiresAuth: true }
        },
        {
            path: '/admin/settings',
            name: 'admin-settings',
            component: AdminSettingsView,
            meta: { layout: 'dashboard', requiresAuth: true }
        },

        // ── Backwards compatibility redirects ────────────────────────────
        { path: '/events', redirect: '/operations' },
        { path: '/events/:pathMatch(.*)*', redirect: '/operations' },
        { path: '/database', redirect: '/connections' },
        { path: '/database/:pathMatch(.*)*', redirect: '/connections' },
        { path: '/settings/webhooks', redirect: '/config/webhooks' },
        { path: '/workspace', redirect: '/config' },
        { path: '/workspace/:pathMatch(.*)*', redirect: '/config' },
        { path: '/reactive/knowledge', redirect: '/resources/knowledge' },
        { path: '/reactive/knowledge/:id', redirect: '/resources/knowledge/:id' },
        { path: '/reactive/database', redirect: '/connections' },
    ],
})

// Auth guard
router.beforeEach((to, _from, next) => {
    const token = localStorage.getItem('token')

    if (to.meta.requiresAuth && !token) {
        next({ name: 'login' })
    } else if ((to.name === 'login' || to.name === 'register') && token) {
        next({ name: 'dashboard' })
    } else {
        next()
    }
})

export default router
