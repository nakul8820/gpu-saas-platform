import axios from "axios";

const BASE_URL = "http://127.0.0.1:8000";

// Create axios instance with base URL
const api = axios.create({
    baseURL: BASE_URL,
    headers: { "Content-Type": "application/json" },
});

// Automatically attach JWT token to every request
api.interceptors.request.use((config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// If token expired, redirect to login
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem("access_token");
            window.location.href = "/";
        }
        return Promise.reject(error);
    }
);

// ── Auth ──────────────────────────────────────────────────
export const authAPI = {
    register: (email: string, password: string, full_name: string) =>
        api.post("/auth/register", { email, password, full_name }),

    login: (email: string, password: string) =>
        api.post("/auth/login", { email, password }),

    me: () => api.get("/auth/me"),
};

// ── Tokens ────────────────────────────────────────────────
export const tokensAPI = {
    getPackages: () => api.get("/tokens/packages"),
    getBalance: () => api.get("/tokens/balance"),
    getHistory: (page = 1) => api.get(`/tokens/history?page=${page}`),
    purchase: (package_id: string) =>
        api.post("/tokens/purchase", { package_id }),
};

// ── Servers ───────────────────────────────────────────────
export const serversAPI = {
    getAvailable: () => api.get("/servers/available"),
    getAll: () => api.get("/servers"),
};

// ── Jobs ──────────────────────────────────────────────────
export const jobsAPI = {
    submit: (data: {
        docker_image: string;
        command?: string[];
        required_vram_mb?: number;
        max_runtime_minutes?: number;
        gpu_count?: number;
        priority?: number;
    }) => api.post("/jobs", data),

    getAll: () => api.get("/jobs"),
    getById: (id: string) => api.get(`/jobs/${id}`),
    getLogs: (id: string) => api.get(`/jobs/${id}/logs`),
};

export default api;