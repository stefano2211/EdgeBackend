import axios from 'axios'

// Create a configured Axios instance
// In dev mode, requests go through Vite's proxy (baseURL = '').
// In production, VITE_API_URL points to the real backend.
const api = axios.create({
    baseURL: import.meta.env.PROD ? (import.meta.env.VITE_API_URL || '') : '',
    timeout: 60000,
    headers: {
        'Content-Type': 'application/json',
    },
})

// Request Interceptor: Inject Auth Token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token')
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// Response Interceptor: Handle global errors (e.g., 401 Unauthorized)
api.interceptors.response.use(
    (response) => {
        return response
    },
    (error) => {
        if (error.response?.status === 401) {
            // Auto-logout logic could go here
            localStorage.removeItem('token')
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)

export default api
