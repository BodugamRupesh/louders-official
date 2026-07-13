/**
 * LOUD Platform - API Integration Client
 * Wraps FastAPI routes with async fetch handlers, local storage JWT injection, and error handler hooks.
 */

const LOUDAPI = (() => {
    const BASE_URL = ''; // Same host

    // Retrieve storage item helper
    const getToken = () => localStorage.getItem('loud_access_token');
    const setToken = (token) => localStorage.setItem('loud_access_token', token);
    const clearToken = () => localStorage.removeItem('loud_access_token');

    // HTTP Request base wrapper
    async function request(endpoint, options = {}) {
        const token = getToken();
        
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const config = {
            ...options,
            headers
        };

        function extractErrorMessage(payload) {
            if (!payload) return null;
            if (typeof payload.message === 'string') return payload.message;

            if (Array.isArray(payload.detail)) {
                return payload.detail
                    .map(item => {
                        if (typeof item === 'string') return item;
                        if (item?.msg) {
                            const location = Array.isArray(item.loc) ? item.loc.join('.') : item.loc;
                            return `${location}: ${item.msg}`;
                        }
                        return JSON.stringify(item);
                    })
                    .join('; ');
            }

            if (typeof payload.detail === 'string') return payload.detail;
            if (typeof payload.detail === 'object' && payload.detail !== null) {
                return JSON.stringify(payload.detail);
            }

            return null;
        }

        function createApiError(response, payload) {
            const message = extractErrorMessage(payload) || response.statusText || 'An error occurred during request execution.';
            const apiError = new Error(message);
            apiError.success = payload?.success ?? false;
            apiError.error_code = payload?.error_code ?? null;
            apiError.status = response.status;
            apiError.payload = payload;
            return apiError;
        }

        function handleHttpError(response, payload) {
            if (response.status === 401 && !endpoint.includes('/auth/login')) {
                clearToken();
                window.dispatchEvent(new CustomEvent('loud-unauthorized'));
            } else if (response.status === 403) {
                window.dispatchEvent(new CustomEvent('loud-forbidden'));
            } else if (response.status === 404) {
                window.dispatchEvent(new CustomEvent('loud-not-found'));
            } else if (response.status === 422) {
                window.dispatchEvent(new CustomEvent('loud-validation-error'));
            } else if (response.status === 500) {
                window.dispatchEvent(new CustomEvent('loud-server-error'));
            }

            throw createApiError(response, payload);
        }

        try {
            const response = await fetch(`${BASE_URL}${endpoint}`, config);
            const text = await response.text();
            const payload = text ? JSON.parse(text) : null;

            if (!response.ok) {
                handleHttpError(response, payload);
            }

            return payload;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    return {
        // Auth Endpoints
        auth: {
            async login(username, password) {
                const res = await request('/api/v1/auth/login', {
                    method: 'POST',
                    body: JSON.stringify({ username, password })
                });
                if (res.access_token) {
                    setToken(res.access_token);
                }
                return res;
            },
            async logout() {
                try {
                    await request('/api/v1/auth/logout', { method: 'POST' });
                } finally {
                    clearToken();
                }
            },
            async me() {
                return request('/api/v1/auth/me', { method: 'GET' });
            },
            async refresh() {
                const res = await request('/api/v1/auth/refresh', { method: 'POST' });
                if (res.access_token) {
                    setToken(res.access_token);
                }
                return res;
            },
            isAuthenticated() {
                return !!getToken();
            }
        },

        // Products Endpoints
        products: {
            async list(activeOnly = false) {
                return request(`/api/v1/products?active_only=${activeOnly}`, { method: 'GET' });
            },
            async search(q) {
                return request(`/api/v1/products/search?q=${encodeURIComponent(q)}`, { method: 'GET' });
            },
            async get(id) {
                return request(`/api/v1/products/${id}`, { method: 'GET' });
            },
            async create(data) {
                return request('/api/v1/products', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
            },
            async update(id, data) {
                return request(`/api/v1/products/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
            },
            async patchStatus(id, status) {
                return request(`/api/v1/products/${id}/status`, {
                    method: 'PATCH',
                    body: JSON.stringify({ status })
                });
            },
            async delete(id) {
                return request(`/api/v1/products/${id}`, { method: 'DELETE' });
            },
            async generateApiKey(id) {
                return request(`/api/v1/products/${id}/generate-api-key`, { method: 'POST' });
            },
            async regenerateApiKey(id) {
                return request(`/api/v1/products/${id}/regenerate-api-key`, { method: 'POST' });
            }
        },

        // Plans Endpoints
        plans: {
            async list(activeOnly = false, page = 1, pageSize = 20) {
                return request(`/api/v1/plans?active_only=${activeOnly}&page=${page}&page_size=${pageSize}`, { method: 'GET' });
            },
            async search(q) {
                return request(`/api/v1/plans/search/query?q=${encodeURIComponent(q)}`, { method: 'GET' });
            },
            async get(id) {
                return request(`/api/v1/plans/${id}`, { method: 'GET' });
            },
            async create(data) {
                return request('/api/v1/plans', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
            },
            async update(id, data) {
                return request(`/api/v1/plans/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
            },
            async patchStatus(id, status) {
                return request(`/api/v1/plans/${id}/status`, {
                    method: 'PATCH',
                    body: JSON.stringify({ status })
                });
            },
            async delete(id) {
                return request(`/api/v1/plans/${id}`, { method: 'DELETE' });
            }
        },

        // Customers Endpoints
        customers: {
            async list(search = null, email = null) {
                let url = '/api/v1/customers';
                const params = [];
                if (search) params.push(`search=${encodeURIComponent(search)}`);
                if (email) params.push(`email=${encodeURIComponent(email)}`);
                if (params.length > 0) url += `?${params.join('&')}`;
                return request(url, { method: 'GET' });
            },
            async search(q) {
                return request(`/api/v1/customers/search?q=${encodeURIComponent(q)}`, { method: 'GET' });
            },
            async get(id) {
                return request(`/api/v1/customers/${id}`, { method: 'GET' });
            },
            async create(data) {
                return request('/api/v1/customers', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
            },
            async update(id, data) {
                return request(`/api/v1/customers/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
            },
            async delete(id) {
                return request(`/api/v1/customers/${id}`, { method: 'DELETE' });
            },
            async getLicenses(id) {
                return request(`/api/v1/customers/${id}/licenses`, { method: 'GET' });
            }
        },

        // Licenses Endpoints
        licenses: {
            async create(data) {
                return request('/api/v1/licenses', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
            },
            async search(filters = {}) {
                let url = '/api/v1/licenses/search';
                const params = [];
                if (filters.q) params.push(`q=${encodeURIComponent(filters.q)}`);
                if (filters.customer_id) params.push(`customer_id=${filters.customer_id}`);
                if (filters.product_id) params.push(`product_id=${filters.product_id}`);
                if (filters.status) params.push(`status=${encodeURIComponent(filters.status)}`);
                if (params.length > 0) url += `?${params.join('&')}`;
                return request(url, { method: 'GET' });
            },
            async delete(id) {
                return request(`/api/v1/licenses/${id}`, { method: 'DELETE' });
            },
            async deleteRevoked(licenseKey) {
                return request('/api/v1/licenses/delete-revoked', {
                    method: 'POST',
                    body: JSON.stringify({ license_key: licenseKey })
                });
            },
            async reactivate(licenseKey) {
                return request('/api/v1/licenses/reactivate', {
                    method: 'POST',
                    body: JSON.stringify({ license_key: licenseKey })
                });
            },
            async activate(data) {
                return request('/api/v1/licenses/activate', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
            },
            async verify(data) {
                return request('/api/v1/licenses/verify', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
            },
            async extend(licenseKey, planId) {
                return request('/api/v1/licenses/extend', {
                    method: 'POST',
                    body: JSON.stringify({ license_key: licenseKey, plan_id: planId })
                });
            },
            async suspend(licenseKey, reason = '') {
                return request('/api/v1/licenses/suspend', {
                    method: 'POST',
                    body: JSON.stringify({ license_key: licenseKey, reason })
                });
            },
            async revoke(licenseKey, reason = '') {
                return request('/api/v1/licenses/revoke', {
                    method: 'POST',
                    body: JSON.stringify({ license_key: licenseKey, reason })
                });
            },
            async resetDevice(licenseKey) {
                return request('/api/v1/licenses/reset-device', {
                    method: 'POST',
                    body: JSON.stringify({ license_key: licenseKey })
                });
            },
            async getActivity(id) {
                return request(`/api/v1/licenses/${id}/activity`, { method: 'GET' });
            },
            async getStats() {
                return request('/api/v1/licenses/stats', { method: 'GET' });
            }
        },

        // Devices Endpoints
        devices: {
            async list(filters = {}) {
                let url = '/api/v1/devices';
                const params = [];
                if (filters.license_id) params.push(`license_id=${filters.license_id}`);
                if (filters.browser) params.push(`browser=${encodeURIComponent(filters.browser)}`);
                if (filters.operating_system) params.push(`operating_system=${encodeURIComponent(filters.operating_system)}`);
                if (params.length > 0) url += `?${params.join('&')}`;
                return request(url, { method: 'GET' });
            },
            async getStats() {
                return request('/api/v1/devices/stats', { method: 'GET' });
            },
            async get(id) {
                return request(`/api/v1/devices/${id}`, { method: 'GET' });
            },
            async register(data) {
                return request('/api/v1/devices/register', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
            },
            async reset(licenseId, deviceUuid) {
                return request('/api/v1/devices/reset', {
                    method: 'POST',
                    body: JSON.stringify({ license_id: licenseId, device_uuid: deviceUuid })
                });
            },
            async update(id, data) {
                return request(`/api/v1/devices/${id}`, {
                    method: 'PATCH',
                    body: JSON.stringify(data)
                });
            },
            async heartbeat(id) {
                return request(`/api/v1/devices/${id}/heartbeat`, { method: 'POST' });
            }
        },

        // Admins Endpoints
        admins: {
            async list() {
                return request('/api/v1/admins', { method: 'GET' });
            },
            async search(query) {
                return request(`/api/v1/admins/search?query=${encodeURIComponent(query)}`, { method: 'GET' });
            },
            async get(id) {
                return request(`/api/v1/admins/${id}`, { method: 'GET' });
            },
            async create(data) {
                return request('/api/v1/admins', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
            },
            async update(id, data) {
                return request(`/api/v1/admins/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
            },
            async delete(id) {
                return request(`/api/v1/admins/${id}`, { method: 'DELETE' });
            },
            async changePassword(oldPassword, newPassword) {
                return request('/api/v1/admins/change-password', {
                    method: 'POST',
                    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
                });
            },
            async resetPassword(adminId, newPassword) {
                return request('/api/v1/admins/reset-password', {
                    method: 'POST',
                    body: JSON.stringify({ admin_id: adminId, new_password: newPassword })
                });
            },
            async getStats() {
                // Resolved /stats route issue by putting stats above /{admin_id} in backend
                return request('/api/v1/admins/stats', { method: 'GET' });
            }
        }
    };
})();
