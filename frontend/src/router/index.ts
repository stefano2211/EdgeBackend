import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import WorkspaceLayout from '../views/workspace/WorkspaceLayout.vue'
import PromptsView from '../views/workspace/PromptsView.vue'
import ToolsView from '../views/workspace/ToolsView.vue'
import EventsView from '../views/EventsView.vue'
import WebhooksSettingsView from '../views/settings/WebhooksSettingsView.vue'
import ReactiveKnowledgeListView from '../views/reactive/ReactiveKnowledgeListView.vue'
import ReactiveKnowledgeDetailView from '../views/reactive/ReactiveKnowledgeDetailView.vue'
import IntegrationsLayout from '../views/integrations/IntegrationsLayout.vue'
import IntegrationCatalogView from '../views/integrations/IntegrationCatalogView.vue'
import IntegrationInstancesView from '../views/integrations/IntegrationInstancesView.vue'
import IntegrationCredentialsView from '../views/integrations/IntegrationCredentialsView.vue'
import IntegrationRegistryView from '../views/integrations/IntegrationRegistryView.vue'


const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        {
            path: '/',
            name: 'home',
            redirect: '/events'
        },
        {
            path: '/login',
            name: 'login',
            component: LoginView,
            meta: { layout: 'auth' }
        },
        {
            path: '/chat',
            name: 'chat',
            component: ChatView,
            meta: { layout: 'main', requiresAuth: true }
        },
        {
            path: '/events',
            name: 'events',
            component: EventsView,
            meta: { layout: 'dashboard', requiresAuth: true }
        },
        {
            path: '/settings/webhooks',
            name: 'settings-webhooks',
            component: WebhooksSettingsView,
            meta: { layout: 'dashboard', requiresAuth: true }
        },
        {
            path: '/workspace',
            component: WorkspaceLayout,
            meta: { layout: 'main', requiresAuth: true },
            redirect: '/workspace/prompts',
            children: [
                {
                    path: 'prompts',
                    name: 'prompts-list',
                    component: PromptsView
                },

                {
                    path: 'tools',
                    name: 'workspace-tools',
                    component: ToolsView
                }
            ]
        },

        {
            path: '/reactive/knowledge',
            name: 'reactive-knowledge',
            component: ReactiveKnowledgeListView,
            meta: { layout: 'dashboard', requiresAuth: true }
        },
        {
            path: '/reactive/knowledge/:id',
            name: 'reactive-knowledge-detail',
            component: ReactiveKnowledgeDetailView,
            props: true,
            meta: { layout: 'dashboard', requiresAuth: true }
        },
        {
            path: '/reactive/database',
            name: 'reactive-database',
            component: () => import('@/views/reactive/ReactiveDatabaseView.vue'),
            meta: { layout: 'dashboard', requiresAuth: true }
        },
        {
            path: '/register',
            name: 'register',
            component: RegisterView,
            meta: { layout: 'auth' }
        },
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
        {
            path: '/database',
            component: () => import('@/views/database/DatabaseLayout.vue'),
            meta: { layout: 'dashboard', requiresAuth: true },
            children: [
                { path: '', redirect: '/database/connections' },
                {
                    path: 'connections',
                    name: 'database-connections',
                    component: () => import('@/views/database/DatabaseConnectionsView.vue'),
                },
            ]
        }
    ],
})

// Auth guard
router.beforeEach((to, _from, next) => {
    const token = localStorage.getItem('token')

    if (to.meta.requiresAuth && !token) {
        // Not authenticated → redirect to login
        next({ name: 'login' })
    } else if ((to.name === 'login' || to.name === 'register') && token) {
        // Already logged in → redirect to operations center (home)
        next({ name: 'events' })
    } else {
        next()
    }
})

export default router
