/**
 * LOUD Platform - Main Frontend Application SPA Controller
 */

const LOUDApp = (() => {
    // Current application state
    let currentUserProfile = null;
    let charts = {}; // references to Chart.js instances

    // DOM Elements cache
    const el = {
        loader: document.getElementById('global-loader'),
        toastContainer: document.getElementById('toast-container'),
        
        // Views
        viewLanding: document.getElementById('view-landing'),
        viewLogin: document.getElementById('view-login'),
        viewDashboard: document.getElementById('view-dashboard'),
        
        // Sidebar/Header
        sidebarUsername: document.getElementById('sidebar-username'),
        sidebarUserRole: document.getElementById('sidebar-user-role'),
        sidebarUserAvatar: document.getElementById('sidebar-user-avatar'),
        headerUserAvatar: document.getElementById('header-user-avatar'),
        btnLogoutSidebar: document.getElementById('btn-logout-sidebar'),
        panelTitleText: document.getElementById('panel-title-text'),
        
        // Forms
        loginForm: document.getElementById('login-form'),
        productForm: document.getElementById('product-form'),
        planForm: document.getElementById('plan-form'),
        customerForm: document.getElementById('customer-form'),
        licenseForm: document.getElementById('license-form'),
        licenseActionForm: document.getElementById('license-action-form'),
        adminForm: document.getElementById('admin-form'),
        adminResetForm: document.getElementById('admin-reset-form'),
        settingsPasswordForm: document.getElementById('settings-password-form')
    };

    // ==========================================
    // 1. ROUTER & VIEW SWITCHER
    // ==========================================
    const routes = {
        '#/': { view: 'landing', title: 'Home' },
        '#/pricing': { view: 'landing', title: 'Pricing', scroll: 'pricing' },
        '#/how-it-works': { view: 'landing', title: 'How It Works', scroll: 'how-it-works' },
        '#/login': { view: 'login', title: 'Admin Console Login' },
        '#/dashboard/overview': { view: 'dashboard', pane: 'overview', title: 'Overview' },
        '#/dashboard/products': { view: 'dashboard', pane: 'products', title: 'Products' },
        '#/dashboard/plans': { view: 'dashboard', pane: 'plans', title: 'Plans' },
        '#/dashboard/customers': { view: 'dashboard', pane: 'customers', title: 'Customers' },
        '#/dashboard/licenses': { view: 'dashboard', pane: 'licenses', title: 'Licenses' },
        '#/dashboard/devices': { view: 'dashboard', pane: 'devices', title: 'Devices' },
        '#/dashboard/admins': { view: 'dashboard', pane: 'admins', title: 'Admins' },
        '#/dashboard/analytics': { view: 'dashboard', pane: 'analytics', title: 'Analytics' },
        '#/dashboard/settings': { view: 'dashboard', pane: 'settings', title: 'Settings' }
    };

    function handleRouting() {
        const hash = window.location.hash || '#/';
        const route = routes[hash] || routes['#/'];

        // Guard private dashboard routes
        if (route.view === 'dashboard' && !LOUDAPI.auth.isAuthenticated()) {
            showToast('Authentication required.', 'error');
            window.location.hash = '#/login';
            return;
        }

        // Redirect authenticated user away from login
        if (route.view === 'login' && LOUDAPI.auth.isAuthenticated()) {
            window.location.hash = '#/dashboard/overview';
            return;
        }

        // Toggle active main view layout with smooth opacity classes
        document.querySelectorAll('.view-section').forEach(section => {
            section.classList.remove('active');
        });

        if (route.view === 'landing') {
            el.viewLanding.classList.add('active');
            LOUDScene3D.setView('landing');
            if (route.scroll) {
                setTimeout(() => {
                    const target = document.getElementById(route.scroll);
                    if (target) target.scrollIntoView({ behavior: 'smooth' });
                }, 100);
            }
        } else if (route.view === 'login') {
            LOUDScene3D.setView('login');
            el.viewLogin.classList.add('active');
        } else if (route.view === 'dashboard') {
            LOUDScene3D.setView('dashboard');
            el.viewDashboard.classList.add('active');
            
            // Set header title & update breadcrumbs
            el.panelTitleText.innerText = route.title;
            const breadcrumbActive = document.getElementById('breadcrumb-active');
            if (breadcrumbActive) {
                breadcrumbActive.innerText = route.pane.toUpperCase();
            }

            // Highlight sidebar item
            document.querySelectorAll('.sidebar-item').forEach(item => {
                item.classList.remove('active');
                if (item.getAttribute('data-tab') === route.pane) {
                    item.classList.add('active');
                }
            });

            // Toggle active subview pane
            document.querySelectorAll('.subview-pane').forEach(pane => {
                pane.classList.remove('active');
            });
            const activePane = document.getElementById(`subview-${route.pane}`);
            if (activePane) activePane.classList.add('active');

            // Initialize/Refresh view data
            loadDashboardPaneData(route.pane);
        }

        // Re-trigger icon rendering
        if (window.lucide) {
            lucide.createIcons();
        }

        // Reset split text anim markers
        document.querySelectorAll('.login-title, .panel-title, .section-title').forEach(el => el.classList.remove('text-split-done'));

        // Trigger character reveals on title headings
        splitAndAnimateText('.login-title');
        splitAndAnimateText('.panel-title');
        splitAndAnimateText('.section-title');

        // Initialize Card tilting listeners
        initCardTilting();
    }

    // ==========================================
    // 2. TOAST NOTIFICATIONS & LOADER
    // ==========================================
    const activeToastMap = new Map();

    function showToast(message, type = 'success') {
        if (!message) return;
        const now = Date.now();
        const lastSeen = activeToastMap.get(message);
        if (lastSeen && now - lastSeen < 2000) {
            return;
        }
        activeToastMap.set(message, now);
        if (activeToastMap.size > 20) {
            for (const [k, v] of activeToastMap.entries()) {
                if (now - v > 5000) activeToastMap.delete(k);
            }
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        let iconName = 'check-circle';
        if (type === 'error') iconName = 'alert-triangle';
        if (type === 'warning') iconName = 'info';

        toast.innerHTML = `
            <i data-lucide="${iconName}"></i>
            <span>${escapeHTML(message)}</span>
            <div class="toast-progress-bar"></div>
        `;
        
        el.toastContainer.appendChild(toast);
        if (window.lucide) lucide.createIcons();
        
        // Slide-in animation trigger
        setTimeout(() => toast.classList.add('show'), 10);
        
        // Auto remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 450);
        }, 3500);
    }

    let isInitialBootComplete = false;

    // Simulated Boot Scan Logger
    function simulateBootLoader(callback) {
        const consoleLog = document.getElementById('loader-console-log');
        if (!consoleLog) {
            isInitialBootComplete = true;
            callback();
            return;
        }

        const lines = [
            "> Establishing secure socket...",
            "> decryp.lp_05aF...8a protocols: OK",
            "> WebGL 3D environments: OK",
            "> Synchronizing FastAPI nodes: OK",
            "> Verification complete. Booting LOUD..."
        ];

        let index = 0;
        
        function printNext() {
            if (index < lines.length) {
                const line = document.createElement('div');
                line.className = 'console-line';
                line.innerText = lines[index];
                consoleLog.appendChild(line);
                consoleLog.scrollTop = consoleLog.scrollHeight;
                index++;
                setTimeout(printNext, 100);
            } else {
                setTimeout(() => {
                    if (el.loader) {
                        el.loader.style.opacity = '0';
                        setTimeout(() => {
                            el.loader.style.display = 'none';
                            isInitialBootComplete = true;
                            callback();
                        }, 300);
                    } else {
                        isInitialBootComplete = true;
                        callback();
                    }
                }, 150);
            }
        }
        
        printNext();
    }

    function toggleLoader(show) {
        if (!isInitialBootComplete) {
            if (el.loader) {
                if (show) {
                    el.loader.style.display = 'flex';
                    el.loader.style.opacity = '1';
                } else {
                    el.loader.style.opacity = '0';
                    setTimeout(() => el.loader.style.display = 'none', 300);
                }
            }
            return;
        }
        // After initial boot, do not flash full-screen black overlay.
        // Instead, toggle subtle background activity class without blocking views.
        if (show) {
            document.body.classList.add('app-busy');
        } else {
            document.body.classList.remove('app-busy');
        }
    }

    // ==========================================
    // 3. DIALOG MODAL CONTROLLERS
    // ==========================================
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('show'), 10);
        }
    };

    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
            setTimeout(() => modal.style.display = 'none', 300);
        }
    };

    // ==========================================
    // 4. DATA LOADING ROUTINES (DASHBOARD VIEWS)
    // ==========================================
    async function loadDashboardPaneData(pane) {
        try {
            // Verify profile is loaded
            if (!currentUserProfile) {
                currentUserProfile = await LOUDAPI.auth.me();
                updateUserInterface(currentUserProfile);
            }

            switch(pane) {
                case 'overview':
                    await renderOverviewPane();
                    break;
                case 'products':
                    await renderProductsPane();
                    break;
                case 'plans':
                    await renderPlansPane();
                    break;
                case 'customers':
                    await renderCustomersPane();
                    break;
                case 'licenses':
                    await renderLicensesPane();
                    break;
                case 'devices':
                    await renderDevicesPane();
                    break;
                case 'admins':
                    await renderAdminsPane();
                    break;
                case 'analytics':
                    await renderAnalyticsPane();
                    break;
                case 'settings':
                    await renderSettingsPane();
                    break;
            }
        } catch (error) {
            showToast(error.message, 'error');
        }
    }

    function updateUserInterface(profile) {
        const init = profile.username.charAt(0).toUpperCase();
        el.sidebarUsername.innerText = profile.username;
        el.sidebarUserRole.innerText = profile.role;
        el.sidebarUserAvatar.innerText = init;
        el.headerUserAvatar.innerText = init;
    }

    function isOwner() {
        return currentUserProfile?.role === 'owner';
    }

    function isAdminOrOwner() {
        return currentUserProfile?.role === 'owner' || currentUserProfile?.role === 'admin';
    }

    // Metric Count Up utility
    function animateValue(obj, start, end, duration, formatPrefix = '', formatSuffix = '') {
        if (!obj) return;
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            // cubic ease-out
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            const val = start + easeProgress * (end - start);
            
            if (formatPrefix === '$') {
                obj.innerText = formatPrefix + val.toFixed(2) + formatSuffix;
            } else {
                obj.innerText = formatPrefix + Math.floor(val) + formatSuffix;
            }

            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }

    // ------------------------------------------
    // A. OVERVIEW PANE RENDER
    // ------------------------------------------
    async function renderOverviewPane() {
        toggleLoader(true);
        try {
            // Parallel fetches
            const [productsRes, plansRes, licensesRes, devicesRes, devStats, licStats] = await Promise.all([
                LOUDAPI.products.list(),
                LOUDAPI.plans.list(),
                LOUDAPI.licenses.search(),
                LOUDAPI.devices.list(),
                LOUDAPI.devices.getStats(),
                LOUDAPI.licenses.getStats()
            ]);

            // Set metric values with count-up animations
            const activeLicenses = licStats.data?.stats?.active || 0;
            const suspendedLicenses = licStats.data?.stats?.suspended || 0;
            const totalLicenses = licStats.data?.stats?.total || licensesRes.data?.count || 0;
            const licensesToday = licStats.data?.stats?.licenses_created_today || 0;
            const licensesYesterday = licStats.data?.stats?.licenses_created_yesterday || 0;
            const devicesToday = devStats.data?.stats?.devices_registered_today || 0;
            const devicesYesterday = devStats.data?.stats?.devices_registered_yesterday || 0;
            const onlineDevices = devStats.data?.stats?.online_devices || 0;
            const totalDevices = devStats.data?.stats?.total_devices || devicesRes.data?.count || 0;

            animateValue(document.getElementById('stat-licenses'), 0, activeLicenses, 1000);
            document.getElementById('stat-licenses-diff').innerText = `${suspendedLicenses} suspended · ${licensesToday} today · ${licensesYesterday} yesterday`;
            animateValue(document.getElementById('stat-devices'), 0, totalDevices, 1000);
            document.getElementById('stat-devices-diff').innerText = `${onlineDevices} online · ${devicesToday} today · ${devicesYesterday} yesterday`;
            animateValue(document.getElementById('stat-products'), 0, productsRes.data?.count || 0, 1000);
            document.getElementById('stat-revenue-diff').innerText = `${totalLicenses} total licenses · Estimated Monthly MRR`;

            // Compute total pricing estimation based on plans
            let estimatedRevenue = 0;
            const activeLicList = licensesRes.data?.licenses || [];
            activeLicList.forEach(l => {
                if (l.status === 'active' && l.plan_id) {
                    const pl = plansRes.data?.plans?.find(p => p.id === l.plan_id);
                    if (pl) estimatedRevenue += pl.price;
                }
            });
            animateValue(document.getElementById('stat-revenue'), 0, estimatedRevenue, 1200, '$');
            document.getElementById('stat-revenue-diff').innerText = `Estimated Monthly MRR`;

            // Draw Overview Mini Chart with smooth canvas animations
            const ctx = document.getElementById('overview-chart').getContext('2d');
            if (charts.overview) charts.overview.destroy();

            // Create premium area gradient fill
            const chartGrad = ctx.createLinearGradient(0, 0, 0, 300);
            chartGrad.addColorStop(0, 'rgba(34, 211, 238, 0.28)');
            chartGrad.addColorStop(1, 'rgba(34, 211, 238, 0.01)');

            // Populate some chart mocks or real logs
            const labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'];
            const data = [12, 19, 3, 5, 2, 3, activeLicenses];

            charts.overview = new Chart(ctx, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: 'Device Activations',
                        data,
                        borderColor: '#22d3ee',
                        backgroundColor: chartGrad,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: '#22d3ee',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 1.5,
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: '#22d3ee',
                        shadowColor: 'rgba(34, 211, 238, 0.4)',
                        shadowBlur: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 1500,
                        easing: 'easeOutQuart'
                    },
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { grid: { color: 'rgba(255, 255, 255, 0.04)' }, ticks: { color: '#94a3b8' } },
                        x: { grid: { color: 'rgba(255, 255, 255, 0.04)' }, ticks: { color: '#94a3b8' } }
                    }
                }
            });

            // Activity Log
            const stream = document.getElementById('recent-logs-list');
            stream.innerHTML = '';
            
            // Collect activity logs from recent licenses in parallel
            const logArr = [];
            const recentLics = activeLicList.slice(0, 5);
            const actResults = await Promise.all(
                recentLics.map(lic => LOUDAPI.licenses.getActivity(lic.id).catch(() => null))
            );
            actResults.forEach(activity => {
                if (activity?.data?.activity) {
                    logArr.push(...activity.data.activity);
                }
            });

            if (logArr.length === 0) {
                stream.innerHTML = '<div class="stream-empty">No telemetry logged.</div>';
            } else {
                logArr.sort((a,b) => new Date(b.timestamp) - new Date(a.timestamp));
                logArr.slice(0, 5).forEach(log => {
                    const dateStr = new Date(log.timestamp).toLocaleString();
                    const iconColor = log.action === 'activate' ? 'bg-cyan' : 'bg-purple';

                    const item = document.createElement('div');
                    item.className = 'activity-item';
                    item.innerHTML = `
                        <div class="activity-icon-badge ${iconColor} font-sora">L</div>
                        <div class="activity-details">
                            <span class="activity-desc">License action <strong>${escapeHTML(log.action)}</strong> triggered.</span>
                            <span class="activity-time">${dateStr} &bull; IP: ${escapeHTML(log.ip_address || 'Unknown')}</span>
                        </div>
                    `;
                    stream.appendChild(item);
                });
            }
        } finally {
            toggleLoader(false);
        }
    }

    // ------------------------------------------
    // B. PRODUCTS PANE RENDER
    // ------------------------------------------
    async function renderProductsPane() {
        toggleLoader(true);
        try {
            const res = await LOUDAPI.products.list();
            const tbody = document.querySelector('#products-table tbody');
            tbody.innerHTML = '';
            
            const products = res.data?.products || [];
            if (products.length === 0) {
                document.getElementById('products-table-empty').style.display = 'block';
            } else {
                document.getElementById('products-table-empty').style.display = 'none';
                products.forEach(p => {
                    const tr = document.createElement('tr');
                    const hasKey = p.api_key ? true : false;
                    const apiKeyDisp = p.api_key || 'Generate Key';

                    tr.innerHTML = `
                        <td>
                            <div style="font-weight:600; font-size:0.95rem;">${escapeHTML(p.name)}</div>
                            <div style="color:var(--text-secondary); font-size:0.8rem;">${escapeHTML(p.description || 'No description.')}</div>
                        </td>
                        <td class="font-mono">${escapeHTML(p.slug)}</td>
                        <td class="font-mono">${escapeHTML(p.version)}</td>
                        <td>
                            <div class="copy-key-wrapper" style="display:flex; align-items:center; gap:6px;">
                                <span class="font-mono text-cyan key-text" style="max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; user-select: all; text-decoration: underline dotted;" title="Click to view full key" onclick="viewProductKey('${escapeHTML(p.name)}', '${escapeHTML(p.api_key || '')}')">${escapeHTML(apiKeyDisp)}</span>
                                <button class="btn btn-secondary btn-sm" onclick="viewProductKey('${escapeHTML(p.name)}', '${escapeHTML(p.api_key || '')}')" title="View Full Key" ${!hasKey ? 'disabled' : ''} style="padding: 0.22rem 0.55rem; font-size: 0.75rem; display: inline-flex; align-items: center; gap: 4px; border: 1px solid rgba(0,255,200,0.3);">
                                    <i data-lucide="eye" style="width:13px; height:13px;"></i> View
                                </button>
                                <button class="btn btn-primary btn-sm" onclick="copyText('${escapeHTML(p.api_key || '')}')" title="Copy Full API Key" ${!hasKey ? 'disabled' : ''} style="padding: 0.22rem 0.6rem; font-size: 0.75rem; display: inline-flex; align-items: center; gap: 4px; font-weight:600;">
                                    <i data-lucide="copy" style="width:13px; height:13px;"></i> Copy
                                </button>
                                <button class="btn btn-secondary btn-sm" onclick="regenerateProductKey(${p.id})" style="padding: 0.22rem 0.5rem; font-size: 0.75rem;">
                                    ${hasKey ? 'Regen' : 'Generate'}
                                </button>
                            </div>
                        </td>
                        <td>
                            <span class="status-pill active">${escapeHTML(p.status)}</span>
                        </td>
                        <td>
                            <div class="actions-cell">
                                <button class="btn-action-icon edit" onclick="editProduct(${p.id})" title="Edit Product">
                                    <i data-lucide="edit-3"></i>
                                </button>
                                ${isOwner() ? `
                                    <button class="btn-action-icon delete" onclick="deleteProduct(${p.id})" title="Archive Product">
                                        <i data-lucide="archive"></i>
                                    </button>
                                ` : ''}
                            </div>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
                if (window.lucide) lucide.createIcons();
            }
        } finally {
            toggleLoader(false);
        }
    }

    window.editProduct = async function(id) {
        try {
            const res = await LOUDAPI.products.get(id);
            const p = res.data?.product;
            if (p) {
                document.getElementById('product-form-id').value = p.id;
                document.getElementById('product-name').value = p.name;
                document.getElementById('product-slug').value = p.slug;
                document.getElementById('product-slug').disabled = true; // Slug cannot be changed once created
                document.getElementById('product-version').value = p.version;
                document.getElementById('product-description').value = p.description || '';
                document.getElementById('product-status').value = p.status;
                document.getElementById('product-status-group').style.display = 'block';
                
                document.getElementById('product-modal-title').innerText = 'Edit Product';
                openModal('modal-product');
            }
        } catch(e) {
            showToast(e.message, 'error');
        }
    };

    window.deleteProduct = async function(id) {
        if (confirm('Are you sure you want to archive this product? This action is permanent.')) {
            try {
                await LOUDAPI.products.delete(id);
                showToast('Product archived successfully.');
                renderProductsPane();
            } catch(e) {
                showToast(e.message, 'error');
            }
        }
    };

    window.regenerateProductKey = async function(id) {
        if (!confirm('Are you sure you want to regenerate this Product API Key? Any client or extension using the current key will need to be updated with the new one.')) {
            return;
        }
        try {
            const res = await LOUDAPI.products.regenerateApiKey(id);
            const newKey = res.data?.api_key;
            showToast('Product API key regenerated.');
            await renderProductsPane();
            if (newKey) {
                viewProductKey(`Product #${id}`, newKey);
            }
        } catch(e) {
            showToast(e.message, 'error');
        }
    };

    // ------------------------------------------
    // C. PLANS PANE RENDER
    // ------------------------------------------
    async function renderPlansPane() {
        toggleLoader(true);
        try {
            const res = await LOUDAPI.plans.list();
            const tbody = document.querySelector('#plans-table tbody');
            tbody.innerHTML = '';

            const plans = res.data?.plans || [];
            if (plans.length === 0) {
                document.getElementById('plans-table-empty').style.display = 'block';
            } else {
                document.getElementById('plans-table-empty').style.display = 'none';
                plans.forEach(p => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="font-weight:600;">${escapeHTML(p.name)}</td>
                        <td class="font-mono">${p.duration_days} days</td>
                        <td class="font-mono">${p.max_devices} max</td>
                        <td class="font-mono text-emerald">$${p.price.toFixed(2)}</td>
                        <td>
                            <span class="status-pill active">${escapeHTML(p.status)}</span>
                        </td>
                        <td>
                            <div class="actions-cell">
                                <button class="btn-action-icon edit" onclick="editPlan(${p.id})" title="Edit Plan">
                                    <i data-lucide="edit-3"></i>
                                </button>
                                ${isOwner() ? `
                                    <button class="btn-action-icon delete" onclick="deletePlan(${p.id})" title="Delete Plan">
                                        <i data-lucide="trash-2"></i>
                                    </button>
                                ` : ''}
                            </div>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } finally {
            toggleLoader(false);
        }
    }

    window.editPlan = async function(id) {
        try {
            const res = await LOUDAPI.plans.get(id);
            const p = res.data?.plan;
            if (p) {
                document.getElementById('plan-form-id').value = p.id;
                document.getElementById('plan-name').value = p.name;
                document.getElementById('plan-duration').value = p.duration_days;
                document.getElementById('plan-max-devices').value = p.max_devices;
                document.getElementById('plan-price').value = p.price;
                document.getElementById('plan-status').value = p.status;
                document.getElementById('plan-status-group').style.display = 'block';

                document.getElementById('plan-modal-title').innerText = 'Edit Plan';
                openModal('modal-plan');
            }
        } catch(e) {
            showToast(e.message, 'error');
        }
    };

    window.deletePlan = async function(id) {
        if (confirm('Are you sure you want to retire this plan? It will no longer be assignable to new licenses.')) {
            try {
                await LOUDAPI.plans.delete(id);
                showToast('Plan retired.');
                renderPlansPane();
            } catch(e) {
                showToast(e.message, 'error');
            }
        }
    };

    // ------------------------------------------
    // D. CUSTOMERS PANE RENDER
    // ------------------------------------------
    let pendingDeleteCustomerId = null;

    async function renderCustomersPane() {
        toggleLoader(true);
        try {
            const res = await LOUDAPI.customers.list();
            const tbody = document.querySelector('#customers-table tbody');
            tbody.innerHTML = '';

            const customers = res.data?.customers || [];
            if (customers.length === 0) {
                document.getElementById('customers-table-empty').style.display = 'block';
            } else {
                document.getElementById('customers-table-empty').style.display = 'none';
                customers.forEach(c => {
                    const tr = document.createElement('tr');
                    tr.id = `customer-row-${c.id}`;
                    const dateStr = new Date(c.created_at).toLocaleDateString();

                    // License key display
                    let licenseDisplay = '<span style="color:var(--text-secondary); font-size:0.85rem;">None</span>';
                    if (c.primary_license_key) {
                        licenseDisplay = `
                            <div style="display:flex; align-items:center; gap:6px;">
                                <span class="font-mono text-cyan" style="font-size:0.82rem; font-weight:600; letter-spacing:0.5px;">${escapeHTML(c.primary_license_key)}</span>
                                <button class="btn-action-icon" onclick="copyText('${escapeHTML(c.primary_license_key)}')" title="Copy License Key" style="padding:2px; height:auto; width:auto; border:none; background:transparent;">
                                    <i data-lucide="copy" style="width:13px; height:13px; color:var(--text-secondary);"></i>
                                </button>
                            </div>
                        `;
                    }

                    // Status display
                    const licStatus = (c.primary_license_status || 'unlicensed').toLowerCase();
                    const statusClass = (licStatus === 'active') ? 'active' : (licStatus === 'suspended') ? 'suspended' : (licStatus === 'revoked') ? 'revoked' : (licStatus === 'expired') ? 'expired' : '';
                    const statusDisplay = `<span class="status-pill ${statusClass}" style="text-transform:capitalize; font-size:0.75rem; padding: 3px 8px;">${escapeHTML(licStatus)}</span>`;

                    // Expiry display
                    let expiryDisplay = '<span style="color:var(--text-secondary); font-size:0.85rem;">N/A</span>';
                    if (c.primary_license_expiry) {
                        expiryDisplay = `<span class="font-mono" style="font-size:0.85rem;">${new Date(c.primary_license_expiry).toLocaleDateString()}</span>`;
                    }

                    // Device display
                    let deviceDisplay = '<span style="color:var(--text-secondary); font-size:0.85rem;">0 / 1</span>';
                    if (c.primary_license_key) {
                        deviceDisplay = `<span class="font-mono" style="font-size:0.85rem;">${c.primary_license_devices || 0} / ${c.primary_license_max_devices || 1}</span>`;
                    }

                    tr.innerHTML = `
                        <td>
                            <div style="font-weight:600; font-size:0.95rem; color:var(--text-primary);">${escapeHTML(c.name)}</div>
                            ${c.phone ? `<div style="color:var(--text-secondary); font-size:0.75rem;">${escapeHTML(c.phone)}</div>` : ''}
                        </td>
                        <td>
                            <div class="font-mono" style="font-size:0.85rem; color:var(--text-secondary);">${escapeHTML(c.email)}</div>
                        </td>
                        <td>${licenseDisplay}</td>
                        <td>${statusDisplay}</td>
                        <td>${expiryDisplay}</td>
                        <td>${deviceDisplay}</td>
                        <td class="font-mono" style="font-size:0.85rem;">${dateStr}</td>
                        <td>
                            <div class="actions-cell" style="display:flex; align-items:center; gap:6px;">
                                <button class="btn btn-secondary btn-sm" onclick="viewCustomerDetails(${c.id})" title="View Customer Details and Licenses" style="padding: 4px 8px; font-size: 0.8rem; display:inline-flex; align-items:center; gap:4px;">
                                    <i data-lucide="eye" style="width:13px; height:13px;"></i> View
                                </button>
                                <button class="btn-action-icon edit" onclick="editCustomer(${c.id})" title="Edit Customer">
                                    <i data-lucide="edit-3"></i>
                                </button>
                                <button class="btn-action-icon delete" onclick="promptDeleteCustomer(${c.id}, '${escapeHTML(c.name).replace(/'/g, "\\'")}', '${escapeHTML(c.email).replace(/'/g, "\\'")}')" title="Delete Customer" style="color:var(--color-danger);">
                                    <i data-lucide="trash-2"></i>
                                </button>
                            </div>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
                if (window.lucide) lucide.createIcons();
            }
        } catch (err) {
            console.error('Failed to load customers:', err);
            showToast('Failed to load customers: ' + (err.message || 'Unknown error'), 'error');
            const tbody = document.querySelector('#customers-table tbody');
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 2rem; color: var(--color-danger);">Error loading customer records. Please check server connection.</td></tr>`;
            }
        } finally {
            toggleLoader(false);
        }
    }

    window.promptDeleteCustomer = function(id, name = '', email = '') {
        pendingDeleteCustomerId = id;
        const nameEl = document.getElementById('delete-customer-target-name');
        const emailEl = document.getElementById('delete-customer-target-email');
        const idEl = document.getElementById('delete-customer-target-id');

        if (nameEl) nameEl.textContent = name || 'Customer';
        if (emailEl) emailEl.textContent = email || '';
        if (idEl) idEl.textContent = `Customer ID: #${id}`;

        openModal('modal-delete-customer');
        if (window.lucide) lucide.createIcons();
    };

    window.confirmDeleteCustomer = async function() {
        if (!pendingDeleteCustomerId) return;
        const targetId = pendingDeleteCustomerId;
        const btn = document.getElementById('btn-confirm-delete-customer');
        if (btn) btn.disabled = true;

        try {
            await LOUDAPI.customers.delete(targetId);
            showToast('Customer deleted successfully.');
            closeModal('modal-delete-customer');
            closeModal('modal-customer');
            closeModal('modal-customer-details');

            await renderCustomersPane();
        } catch(e) {
            showToast(e.message || 'Failed to delete customer', 'error');
        } finally {
            if (btn) btn.disabled = false;
            pendingDeleteCustomerId = null;
        }
    };

    window.deleteCustomer = function(id, name = '', email = '') {
        promptDeleteCustomer(id, name, email);
    };

    window.editCustomer = async function(id) {
        try {
            const res = await LOUDAPI.customers.get(id);
            const c = res.data?.customer;
            if (c) {
                document.getElementById('customer-form-id').value = c.id;
                document.getElementById('customer-name').value = c.name;
                document.getElementById('customer-email').value = c.email;
                document.getElementById('customer-phone').value = c.phone || '';
                document.getElementById('customer-notes').value = c.notes || '';

                const delBtn = document.getElementById('btn-delete-customer-from-form');
                if (delBtn) {
                    delBtn.style.display = 'inline-flex';
                    delBtn.onclick = () => {
                        promptDeleteCustomer(c.id, c.name, c.email);
                    };
                }

                document.getElementById('customer-modal-title').innerText = 'Edit Customer';
                openModal('modal-customer');
            }
        } catch(e) {
            showToast(e.message, 'error');
        }
    };

    window.viewCustomerDetails = async function(id) {
        try {
            const [custRes, licRes] = await Promise.all([
                LOUDAPI.customers.get(id),
                LOUDAPI.customers.getLicenses(id)
            ]);

            const c = custRes.data?.customer;
            const licenses = licRes.data?.licenses || [];

            if (c) {
                document.getElementById('customer-details-title').innerText = `Customer: ${c.name}`;
                document.getElementById('cust-det-email').innerText = c.email;
                document.getElementById('cust-det-phone').innerText = c.phone || 'None';
                document.getElementById('cust-det-created').innerText = new Date(c.created_at).toLocaleString();

                const notesWrap = document.getElementById('cust-det-notes-wrapper');
                if (c.notes) {
                    notesWrap.style.display = 'block';
                    document.getElementById('cust-det-notes').innerText = c.notes;
                } else {
                    notesWrap.style.display = 'none';
                }

                const tbody = document.querySelector('#customer-licenses-table tbody');
                tbody.innerHTML = '';

                if (licenses.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No licenses issued.</td></tr>';
                } else {
                    licenses.forEach(l => {
                        const tr = document.createElement('tr');
                        const expStr = new Date(l.expires_at).toLocaleDateString();
                        const statusClass = l.status === 'active' ? 'active' : l.status;

                        tr.innerHTML = `
                            <td class="font-mono text-cyan" style="font-weight:500;">${l.license_key}</td>
                            <td>Product ID: ${l.product_id}</td>
                            <td>${l.activated_device_count}</td>
                            <td>${expStr}</td>
                            <td><span class="status-pill ${statusClass}">${l.status}</span></td>
                        `;
                        tbody.appendChild(tr);
                    });
                }

                const delModalBtn = document.getElementById('btn-delete-customer-from-modal');
                if (delModalBtn) {
                    delModalBtn.onclick = () => {
                        promptDeleteCustomer(c.id, c.name, c.email);
                    };
                }

                openModal('modal-customer-details');
            }
        } catch(e) {
            showToast(e.message, 'error');
        }
    };

    // ------------------------------------------
    // E. LICENSES PANE RENDER
    // ------------------------------------------
    async function renderLicensesPane() {
        toggleLoader(true);
        try {
            const [productsRes, licensesRes] = await Promise.all([
                LOUDAPI.products.list(),
                LOUDAPI.licenses.search()
            ]);

            // Populate Product Filter Dropdown
            const filterProd = document.getElementById('filter-license-product');
            const products = productsRes.data?.products || [];
            filterProd.innerHTML = '<option value="">All Products</option>';
            products.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.innerText = p.name;
                filterProd.appendChild(opt);
            });

            // Populate issue selects on forms
            populateLicenseIssueDropdowns(products);

            // Populate table list
            populateLicensesTable(licensesRes.data?.licenses || []);

        } finally {
            toggleLoader(false);
        }
    }

    function populateLicensesTable(licenses) {
        const tbody = document.querySelector('#licenses-table tbody');
        tbody.innerHTML = '';

        if (licenses.length === 0) {
            document.getElementById('licenses-table-empty').style.display = 'block';
        } else {
            document.getElementById('licenses-table-empty').style.display = 'none';
            licenses.forEach(l => {
                const tr = document.createElement('tr');
                const expStr = new Date(l.expires_at).toLocaleDateString();
                const statusClass = l.status === 'active' ? 'active' : l.status;

                tr.innerHTML = `
                    <td>
                        <div class="copy-key-wrapper">
                            <span class="font-mono text-cyan key-text">${l.license_key}</span>
                            <button class="btn-action-icon" onclick="copyText('${l.license_key}')" title="Copy Key">
                                <i data-lucide="copy" style="width:14px; height:14px;"></i>
                            </button>
                        </div>
                    </td>
                    <td>
                        <div style="font-weight:600;">Product ID: ${l.product_id}</div>
                        <div style="color:var(--text-secondary); font-size:0.8rem;">Plan ID: ${l.plan_id}</div>
                    </td>
                    <td class="font-mono">Customer ID: ${l.customer_id}</td>
                    <td class="font-mono">${l.activated_device_count}</td>
                    <td class="font-mono">${expStr}</td>
                    <td>
                        <span class="status-pill ${statusClass}">${l.status}</span>
                    </td>
                    <td>
                        <div class="actions-cell">
                            <button class="btn-action-icon edit" onclick="viewLicenseDetails(${l.id}, '${l.license_key}')" title="View Details">
                                <i data-lucide="eye"></i>
                            </button>
                            <button class="btn-action-icon extend" onclick="openLicenseAction('extend', '${l.license_key}')" title="Extend License">
                                <i data-lucide="calendar-plus"></i>
                            </button>
                            ${l.status === 'active' ? `
                                <button class="btn-action-icon lock" onclick="openLicenseAction('suspend', '${l.license_key}')" title="Suspend License">
                                    <i data-lucide="slash"></i>
                                </button>
                            ` : ''}
                            ${l.status === 'suspended' ? `
                                <button class="btn-action-icon" onclick="reactivateLicense('${l.license_key}')" title="Reactivate License" style="color:var(--color-success);">
                                    <i data-lucide="play"></i>
                                </button>
                            ` : ''}
                            ${l.status !== 'revoked' ? `
                                <button class="btn-action-icon delete" onclick="openLicenseAction('revoke', '${l.license_key}')" title="Revoke License">
                                    <i data-lucide="x-circle"></i>
                                </button>
                            ` : ''}
                            ${isOwner() && l.status !== 'revoked' ? `
                                <button class="btn-action-icon delete" onclick="deleteLicense(${l.id}, '${l.license_key}')" title="Delete License">
                                    <i data-lucide="trash-2"></i>
                                </button>
                            ` : ''}
                            ${l.status === 'revoked' && isAdminOrOwner() ? `
                                <button class="btn-action-icon delete" onclick="deleteRevokedLicense('${l.license_key}')" title="Delete Revoked License" style="color:var(--color-danger);">
                                    <i data-lucide="trash-2"></i>
                                </button>
                            ` : ''}
                            <button class="btn-action-icon" onclick="resetLicenseHardware('${l.license_key}')" title="Reset Bound Hardware" style="color:var(--accent-secondary);">
                                <i data-lucide="refresh-cw"></i>
                            </button>
                        </div>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
        if (window.lucide) lucide.createIcons();
    }

    async function populateLicenseIssueDropdowns(products) {
        const prodSelect = document.getElementById('license-product-select');
        const custSelect = document.getElementById('license-customer-select');
        const planSelect = document.getElementById('license-plan-select');

        prodSelect.innerHTML = '<option value="">Choose a product...</option>';
        custSelect.innerHTML = '<option value="">Choose a customer...</option>';
        planSelect.innerHTML = '<option value="">Choose a plan...</option>';

        // Products options
        products.forEach(p => {
            if (p.status === 'active') {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.innerText = p.name;
                prodSelect.appendChild(opt);
            }
        });

        // Customers options
        try {
            const custRes = await LOUDAPI.customers.list();
            const customers = custRes.data?.customers || [];
            customers.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                opt.innerText = `${c.name} (${c.email})`;
                custSelect.appendChild(opt);
            });
        } catch(e) {}

        // Plans options
        try {
            const plansRes = await LOUDAPI.plans.list(true);
            const plans = plansRes.data?.plans || [];
            plans.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.innerText = `${p.name} ($${p.price.toFixed(2)})`;
                planSelect.appendChild(opt);
            });
        } catch(e) {}
    }

    window.viewLicenseDetails = async function(id, key) {
        try {
            const [activityRes, devicesRes, searchRes] = await Promise.all([
                LOUDAPI.licenses.getActivity(id),
                LOUDAPI.devices.list({ license_id: id }),
                LOUDAPI.licenses.search({ q: key })
            ]);

            document.getElementById('license-details-title').innerText = `License security console`;
            document.getElementById('lic-det-product').innerText = `ID: ${id}`;
            document.getElementById('lic-det-customer').innerText = 'Attached Client';
            document.getElementById('lic-det-expires').innerText = '...';

            const l = searchRes.data?.licenses?.[0];
            let maxDevices = 1;
            if (l && l.plan_id) {
                document.getElementById('lic-det-expires').innerText = new Date(l.expires_at).toLocaleString();
                try {
                    const planRes = await LOUDAPI.plans.get(l.plan_id);
                    if (planRes.data?.plan) {
                        maxDevices = planRes.data.plan.max_devices || 1;
                    }
                } catch(e) {}
            }

            // Update Console hologram elements
            const activeCount = Math.max(l?.activated_device_count ?? 0, devicesRes.data?.count ?? 0, (devicesRes.data?.devices || []).length);
            const percentage = Math.min((activeCount / maxDevices) * 100, 100);
            document.getElementById('lic-console-seat-fill').style.width = `${percentage}%`;
            document.getElementById('lic-console-seat-text').innerText = `${activeCount} / ${maxDevices} seats occupied`;
            
            const healthDot = document.getElementById('lic-health-dot');
            const healthTxt = document.getElementById('lic-console-health-text');
            const cardStatus = document.getElementById('lic-console-card-status');
            document.getElementById('lic-console-card-key').innerText = key;

            if (l) {
                cardStatus.innerText = l.status.toUpperCase();
                if (l.status === 'active') {
                    healthDot.className = 'health-pulse-dot bg-cyan';
                    healthTxt.innerText = 'SECURE';
                    healthTxt.style.color = 'var(--accent-secondary)';
                } else {
                    healthDot.className = 'health-pulse-dot bg-purple'; // custom visual warning
                    healthTxt.innerText = l.status.toUpperCase();
                    healthTxt.style.color = 'var(--color-danger)';
                }
            }

            // Populate bound hardware devices
            const tbody = document.querySelector('#lic-det-devices-table tbody');
            tbody.innerHTML = '';
            const devices = devicesRes.data?.devices || [];
            if (devices.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hardware registered.</td></tr>';
            } else {
                devices.forEach(d => {
                    const tr = document.createElement('tr');
                    const lastSeen = new Date(d.last_seen).toLocaleString();
                    tr.innerHTML = `
                        <td class="font-mono text-cyan" style="font-size:0.8rem;">${d.device_uuid}</td>
                        <td>${escapeHTML(d.browser)} / ${escapeHTML(d.operating_system || 'Unknown')}</td>
                        <td class="font-mono">${escapeHTML(d.extension_version || '1.0.0')}</td>
                        <td class="font-mono" style="font-size:0.8rem;">${lastSeen}</td>
                        <td>
                            <button class="btn btn-danger btn-sm" onclick="debindDevice(${id}, '${d.device_uuid}')" style="padding: 0.15rem 0.4rem; font-size: 0.75rem;">
                                Unbind
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            // Populate Activity telemetry logs
            const stream = document.getElementById('lic-det-logs-stream');
            stream.innerHTML = '';
            const logs = activityRes.data?.activity || [];
            if (logs.length === 0) {
                stream.innerHTML = '<div class="stream-empty">No telemetry transactions logged for this license.</div>';
            } else {
                logs.forEach(log => {
                    const dateStr = new Date(log.timestamp).toLocaleString();
                    const iconColor = log.action === 'activate' ? 'bg-cyan' : 'bg-purple';

                    const item = document.createElement('div');
                    item.className = 'activity-item';
                    item.innerHTML = `
                        <div class="activity-icon-badge ${iconColor} font-sora">L</div>
                        <div class="activity-details">
                            <span class="activity-desc">License action <strong>${escapeHTML(log.action)}</strong> triggered.</span>
                            <span class="activity-time">${dateStr} &bull; IP: ${escapeHTML(log.ip_address || 'Unknown')} &bull; UserAgent: ${escapeHTML(log.browser || 'Unknown')}</span>
                        </div>
                    `;
                    stream.appendChild(item);
                });
            }

            openModal('modal-license-details');
        } catch(e) {
            showToast(e.message, 'error');
        }
    };

    window.debindDevice = async function(licenseId, deviceUuid) {
        if (confirm(`Are you sure you want to unbind device ${deviceUuid}?`)) {
            try {
                await LOUDAPI.devices.reset(licenseId, deviceUuid);
                showToast('Device unbound successfully.');
                closeModal('modal-license-details');
                renderLicensesPane();
            } catch(e) {
                showToast(e.message, 'error');
            }
        }
    };

    window.openLicenseAction = async function(type, licenseKey) {
        document.getElementById('license-action-key').value = licenseKey;
        document.getElementById('license-action-type').value = type;

        const planGrp = document.getElementById('license-action-plan-group');
        const reasonGrp = document.getElementById('license-action-reason-group');
        
        planGrp.style.display = 'none';
        reasonGrp.style.display = 'none';

        if (type === 'extend') {
            document.getElementById('license-action-title').innerText = 'Extend License Validity';
            planGrp.style.display = 'block';

            // Populate plans list
            const planSelect = document.getElementById('license-action-plan');
            planSelect.innerHTML = '<option value="">Select Extension Plan...</option>';
            try {
                const plansRes = await LOUDAPI.plans.list(true);
                const plans = plansRes.data?.plans || [];
                plans.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.innerText = `${p.name} (${p.duration_days} days - $${p.price.toFixed(2)})`;
                    planSelect.appendChild(opt);
                });
            } catch(e) {}

        } else if (type === 'suspend') {
            document.getElementById('license-action-title').innerText = 'Temporarily Suspend License';
            reasonGrp.style.display = 'block';
        } else if (type === 'revoke') {
            document.getElementById('license-action-title').innerText = 'Revoke License Key';
            reasonGrp.style.display = 'block';
        }

        openModal('modal-license-action');
    };

    window.reactivateLicense = async function(licenseKey) {
        try {
            await LOUDAPI.licenses.reactivate(licenseKey);
            showToast('License key reactivated.');
            renderLicensesPane();
        } catch(e) {
            showToast(e.message, 'error');
        }
    };

    window.resetLicenseHardware = async function(licenseKey) {
        if (confirm(`Are you sure you want to reset all bound devices for license ${licenseKey}?`)) {
            try {
                await LOUDAPI.licenses.resetDevice(licenseKey);
                showToast('Bound device registrations reset successfully.');
                renderLicensesPane();
            } catch(e) {
                showToast(e.message, 'error');
            }
        }
    };

    window.deleteLicense = async function(id, licenseKey) {
        if (!confirm(`Are you sure you want to permanently delete license ${licenseKey}? This cannot be undone.`)) {
            return;
        }

        try {
            await LOUDAPI.licenses.delete(id);
            showToast('License deleted successfully.');
            renderLicensesPane();
        } catch (e) {
            showToast(e.message, 'error');
        }
    };

    window.deleteRevokedLicense = async function(licenseKey) {
        if (!confirm(`Are you sure you want to permanently delete revoked license ${licenseKey}? This cannot be undone.`)) {
            return;
        }

        try {
            await LOUDAPI.licenses.deleteRevoked(licenseKey);
            showToast('Revoked license deleted successfully.');
            renderLicensesPane();
        } catch (e) {
            showToast(e.message, 'error');
        }
    };

    // ------------------------------------------
    // F. DEVICES PANE RENDER
    // ------------------------------------------
    async function renderDevicesPane() {
        toggleLoader(true);
        try {
            const res = await LOUDAPI.devices.list();
            const tbody = document.querySelector('#devices-table tbody');
            tbody.innerHTML = '';

            const devices = res.data?.devices || [];
            if (devices.length === 0) {
                document.getElementById('devices-table-empty').style.display = 'block';
            } else {
                document.getElementById('devices-table-empty').style.display = 'none';
                devices.forEach(d => {
                    const tr = document.createElement('tr');
                    const lastSeen = new Date(d.last_seen).toLocaleString();

                    tr.innerHTML = `
                        <td class="font-mono text-cyan" style="font-size:0.8rem;">${d.device_uuid}</td>
                        <td class="font-mono">License ID: ${d.license_id}</td>
                        <td>${escapeHTML(d.browser)} / ${escapeHTML(d.operating_system || 'Unknown')}</td>
                        <td class="font-mono">${escapeHTML(d.extension_version || '1.0.0')}</td>
                        <td class="font-mono" style="font-size:0.8rem;">${lastSeen}</td>
                        <td>
                            <button class="btn btn-danger btn-sm" onclick="debindDevice(${d.license_id}, '${d.device_uuid}')">
                                Unbind Node
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } finally {
            toggleLoader(false);
        }
    }

    // ------------------------------------------
    // G. ADMINS PANE RENDER
    // ------------------------------------------
    async function renderAdminsPane() {
        toggleLoader(true);
        try {
            const res = await LOUDAPI.admins.list();
            const tbody = document.querySelector('#admins-table tbody');
            tbody.innerHTML = '';

            const admins = res.data?.admins || [];
            if (admins.length === 0) {
                document.getElementById('admins-table-empty').style.display = 'block';
            } else {
                document.getElementById('admins-table-empty').style.display = 'none';
                admins.forEach(a => {
                    const tr = document.createElement('tr');
                    const dateStr = new Date(a.created_at).toLocaleDateString();
                    const isSelf = currentUserProfile && currentUserProfile.id === a.id;

                    tr.innerHTML = `
                        <td style="font-weight:600;">${escapeHTML(a.username)}</td>
                        <td class="font-sora text-purple uppercase" style="font-size:0.8rem;">${escapeHTML(a.role)}</td>
                        <td class="font-mono">${dateStr}</td>
                        <td>
                            <div class="actions-cell">
                                <button class="btn-action-icon edit" onclick="editAdmin(${a.id})" title="Edit Admin" ${isSelf ? 'disabled' : ''}>
                                    <i data-lucide="edit-3"></i>
                                </button>
                                <button class="btn-action-icon lock" onclick="resetAdminPasswordModal(${a.id}, '${escapeHTML(a.username)}')" title="Reset Password" ${isSelf ? 'disabled' : ''}>
                                    <i data-lucide="key-round"></i>
                                </button>
                                <button class="btn-action-icon delete" onclick="deleteAdmin(${a.id})" title="Delete Admin" ${isSelf ? 'disabled' : ''}>
                                    <i data-lucide="trash-2"></i>
                                </button>
                            </div>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } finally {
            toggleLoader(false);
        }
    }

    window.editAdmin = async function(id) {
        try {
            const res = await LOUDAPI.admins.get(id);
            const a = res.data?.admin;
            if (a) {
                document.getElementById('admin-form-id').value = a.id;
                document.getElementById('admin-username').value = a.username;
                document.getElementById('admin-username').disabled = true; // cannot rename admin id
                document.getElementById('admin-role').value = a.role;
                document.getElementById('admin-password-group').style.display = 'none'; // hide password on edit
                document.getElementById('admin-password').required = false;

                document.getElementById('admin-modal-title').innerText = 'Edit Admin Settings';
                openModal('modal-admin');
            }
        } catch(e) {
            showToast(e.message, 'error');
        }
    };

    window.resetAdminPasswordModal = function(id, username) {
        document.getElementById('admin-reset-id').value = id;
        document.getElementById('admin-reset-username').value = username;
        document.getElementById('admin-reset-password').value = '';

        openModal('modal-admin-reset');
    };

    window.deleteAdmin = async function(id) {
        if (confirm('Are you sure you want to remove this administrator? They will instantly lose platform credentials.')) {
            try {
                await LOUDAPI.admins.delete(id);
                showToast('Admin deleted.');
                renderAdminsPane();
            } catch(e) {
                showToast(e.message, 'error');
            }
        }
    };

    // ------------------------------------------
    // H. ANALYTICS PANE RENDER
    // ------------------------------------------
    async function renderAnalyticsPane() {
        toggleLoader(true);
        try {
            // Parallel fetches
            const [licStats, devStats] = await Promise.all([
                LOUDAPI.licenses.getStats(),
                LOUDAPI.devices.getStats()
            ]);

            // 1. Chart: Status Dist
            const stats = licStats.data?.stats || {};
            const statusCtx = document.getElementById('chart-status-dist').getContext('2d');
            if (charts.statusDist) charts.statusDist.destroy();
            charts.statusDist = new Chart(statusCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Active', 'Suspended', 'Revoked', 'Expired'],
                    datasets: [{
                        data: [stats.active || 0, stats.suspended || 0, stats.revoked || 0, stats.expired || 0],
                        backgroundColor: ['#10b981', '#f59e0b', '#ef4444', '#94a3b8'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        animateRotate: true,
                        duration: 1200
                    },
                    plugins: { legend: { labels: { color: '#f8fafc' } } }
                }
            });

            // 2. Chart: Browser share
            const browsers = devStats.data?.stats?.browsers || {};
            const browserCtx = document.getElementById('chart-browser-dist').getContext('2d');
            if (charts.browserShare) charts.browserShare.destroy();
            charts.browserShare = new Chart(browserCtx, {
                type: 'polarArea',
                data: {
                    labels: Object.keys(browsers),
                    datasets: [{
                        data: Object.values(browsers),
                        backgroundColor: ['rgba(34, 211, 238, 0.6)', 'rgba(139, 92, 246, 0.6)', 'rgba(59, 130, 246, 0.6)', 'rgba(16, 185, 129, 0.6)'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        animateScale: true,
                        duration: 1200
                    },
                    plugins: { legend: { labels: { color: '#f8fafc' } } },
                    scales: {
                        r: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { backdropColor: 'transparent', color: '#94a3b8' } }
                    }
                }
            });

            // 3. Chart: Trend
            const trendCtx = document.getElementById('chart-activations-trend').getContext('2d');
            if (charts.trendChart) charts.trendChart.destroy();
            charts.trendChart = new Chart(trendCtx, {
                type: 'bar',
                data: {
                    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                    datasets: [{
                        label: 'Verification heartbeats',
                        data: [65, 59, 80, 81, 56, 55, 40],
                        backgroundColor: '#8b5cf6'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 1200
                    },
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
                    }
                }
            });

        } finally {
            toggleLoader(false);
        }
    }

    // ------------------------------------------
    // I. SETTINGS PANE RENDER
    // ------------------------------------------
    async function renderSettingsPane() {
        if (currentUserProfile) {
            document.getElementById('settings-prof-id').innerText = currentUserProfile.id;
            document.getElementById('settings-prof-username').innerText = currentUserProfile.username;
            document.getElementById('settings-prof-role').innerText = currentUserProfile.role;
            document.getElementById('settings-prof-created').innerText = new Date(currentUserProfile.created_at).toLocaleString();
        }
    }

    // ==========================================
    // 5. REDESIGNED MOTION UTILITIES
    // ==========================================
    
    // Glass Cards interactive perspective mouse-tilt
    function initCardTilting() {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        
        document.querySelectorAll('.card-tilt').forEach(card => {
            card.addEventListener('mousemove', e => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const xc = rect.width / 2;
                const yc = rect.height / 2;
                
                // Tilt degree factors
                const rx = -(y - yc) / 8;
                const ry = (x - xc) / 8;
                
                card.style.setProperty('--rx', `${rx}deg`);
                card.style.setProperty('--ry', `${ry}deg`);
            });

            card.addEventListener('mouseleave', () => {
                card.style.setProperty('--rx', '0deg');
                card.style.setProperty('--ry', '0deg');
            });
        });
    }

    // Viewport entrance IntersectionObserver
    function initScrollReveals() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');
                }
            });
        }, { threshold: 0.15 });

        document.querySelectorAll('.scroll-reveal').forEach(el => observer.observe(el));
    }

    // Character-by-character heading reveal animator
    function splitAndAnimateText(selector) {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        document.querySelectorAll(selector).forEach(el => {
            if (el.classList.contains('text-split-done')) return;
            const text = el.innerText.trim();
            el.innerHTML = '';
            text.split('').forEach((char, i) => {
                const span = document.createElement('span');
                span.innerText = char === ' ' ? '\u00A0' : char;
                span.style.display = 'inline-block';
                span.style.opacity = '0';
                span.style.transform = 'translateY(10px) scale(0.8)';
                span.style.filter = 'blur(4px)';
                span.style.transition = 'opacity 0.6s, transform 0.6s, filter 0.6s';
                span.style.transitionDelay = `${i * 0.02}s`;
                el.appendChild(span);
                
                // Trigger transition on next tick
                setTimeout(() => {
                    span.style.opacity = '1';
                    span.style.transform = 'translateY(0) scale(1)';
                    span.style.filter = 'blur(0)';
                }, 50);
            });
            el.classList.add('text-split-done');
        });
    }

    // ==========================================
    // 6. EVENT HANDLERS & REGISTRATION
    // ==========================================
    function registerEvents() {
        // Global auth unauthorized interceptor
        window.addEventListener('loud-unauthorized', () => {
            currentUserProfile = null;
            showToast('Session has ended. Please log in again.', 'warning');
            window.location.hash = '#/login';
        });

        // 1. Handle Login Form Submit
        el.loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('login-username').value.trim();
            const password = el.loginForm.querySelector('input[type="password"]').value;
            
            toggleLoader(true);
            try {
                await LOUDAPI.auth.login(username, password);
                showToast('Successfully logged in.');
                currentUserProfile = null; // force profile reload
                window.location.hash = '#/dashboard/overview';
            } catch(error) {
                showToast(error.message, 'error');
            } finally {
                toggleLoader(false);
            }
        });

        // 2. Handle Logout Button
        el.btnLogoutSidebar.addEventListener('click', async () => {
            toggleLoader(true);
            try {
                await LOUDAPI.auth.logout();
                currentUserProfile = null;
                showToast('Logged out successfully.');
                window.location.hash = '#/';
            } catch(e) {
                showToast(e.message, 'error');
            } finally {
                toggleLoader(false);
            }
        });

        // 3. Product Add trigger
        document.getElementById('btn-create-product').addEventListener('click', () => {
            document.getElementById('product-form-id').value = '';
            document.getElementById('product-name').value = '';
            document.getElementById('product-slug').value = '';
            document.getElementById('product-slug').disabled = false;
            document.getElementById('product-version').value = '1.0.0';
            document.getElementById('product-description').value = '';
            document.getElementById('product-status-group').style.display = 'none';

            document.getElementById('product-modal-title').innerText = 'Add Product';
            openModal('modal-product');
        });

        // Product Form Submit
        el.productForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('product-form-id').value;
            const data = {
                name: document.getElementById('product-name').value.trim(),
                slug: document.getElementById('product-slug').value.trim(),
                version: document.getElementById('product-version').value.trim(),
                description: document.getElementById('product-description').value.trim()
            };

            try {
                if (id) {
                    data.status = document.getElementById('product-status').value;
                    await LOUDAPI.products.update(id, data);
                    showToast('Product settings updated.');
                } else {
                    await LOUDAPI.products.create(data);
                    showToast('Product added successfully.');
                }
                closeModal('modal-product');
                renderProductsPane();
            } catch(err) {
                showToast(err.message, 'error');
            }
        });

        // 4. Plan Add trigger
        document.getElementById('btn-create-plan').addEventListener('click', () => {
            document.getElementById('plan-form-id').value = '';
            document.getElementById('plan-name').value = '';
            document.getElementById('plan-duration').value = '';
            document.getElementById('plan-max-devices').value = '1';
            document.getElementById('plan-price').value = '0.00';
            document.getElementById('plan-status-group').style.display = 'none';

            document.getElementById('plan-modal-title').innerText = 'Create Plan';
            openModal('modal-plan');
        });

        // Plan Form Submit
        el.planForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('plan-form-id').value;
            const data = {
                name: document.getElementById('plan-name').value.trim(),
                duration_days: parseInt(document.getElementById('plan-duration').value),
                max_devices: parseInt(document.getElementById('plan-max-devices').value),
                price: parseFloat(document.getElementById('plan-price').value)
            };

            try {
                if (id) {
                    data.status = document.getElementById('plan-status').value;
                    await LOUDAPI.plans.update(id, data);
                    showToast('Billing plan updated.');
                } else {
                    await LOUDAPI.plans.create(data);
                    showToast('Billing plan created.');
                }
                closeModal('modal-plan');
                renderPlansPane();
            } catch(err) {
                showToast(err.message, 'error');
            }
        });

        // 5. Customer Add trigger
        document.getElementById('btn-create-customer').addEventListener('click', () => {
            document.getElementById('customer-form-id').value = '';
            document.getElementById('customer-name').value = '';
            document.getElementById('customer-email').value = '';
            document.getElementById('customer-phone').value = '';
            document.getElementById('customer-notes').value = '';

            const delBtn = document.getElementById('btn-delete-customer-from-form');
            if (delBtn) delBtn.style.display = 'none';

            document.getElementById('customer-modal-title').innerText = 'Add Customer';
            openModal('modal-customer');
        });

        // Customer Form Submit
        el.customerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('customer-form-id').value;
            const phoneVal = document.getElementById('customer-phone').value.trim();
            const notesVal = document.getElementById('customer-notes').value.trim();
            const data = {
                name: document.getElementById('customer-name').value.trim(),
                email: document.getElementById('customer-email').value.trim(),
                phone: phoneVal || null,
                notes: notesVal || null
            };

            try {
                if (id) {
                    await LOUDAPI.customers.update(id, data);
                    showToast('Customer information updated.');
                } else {
                    await LOUDAPI.customers.create(data);
                    showToast('Customer profile registered.');
                }
                closeModal('modal-customer');
                renderCustomersPane();
            } catch(err) {
                showToast(err.message, 'error');
            }
        });

        // Delete Customer confirmation button click handler
        const btnConfirmDelCustomer = document.getElementById('btn-confirm-delete-customer');
        if (btnConfirmDelCustomer) {
            btnConfirmDelCustomer.addEventListener('click', confirmDeleteCustomer);
        }

        // 6. License Issue triggers
        const triggerLicenseIssue = () => {
            openModal('modal-license');
        };
        document.getElementById('quick-issue-license').addEventListener('click', triggerLicenseIssue);
        document.getElementById('btn-issue-license-pane').addEventListener('click', triggerLicenseIssue);

        // License Generate Submit
        el.licenseForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = {
                product_id: parseInt(document.getElementById('license-product-select').value),
                customer_id: parseInt(document.getElementById('license-customer-select').value),
                plan_id: parseInt(document.getElementById('license-plan-select').value)
            };

            try {
                await LOUDAPI.licenses.create(data);
                showToast('License key generated.');
                closeModal('modal-license');
                renderLicensesPane();
            } catch(err) {
                showToast(err.message, 'error');
            }
        });

        // License Action forms (Extend / Suspend / Revoke)
        el.licenseActionForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const key = document.getElementById('license-action-key').value;
            const type = document.getElementById('license-action-type').value;

            try {
                if (type === 'extend') {
                    const planId = parseInt(document.getElementById('license-action-plan').value);
                    await LOUDAPI.licenses.extend(key, planId);
                    showToast('License validity extended.');
                } else if (type === 'suspend') {
                    const reason = document.getElementById('license-action-reason').value.trim();
                    await LOUDAPI.licenses.suspend(key, reason);
                    showToast('License status set to suspended.');
                } else if (type === 'revoke') {
                    const reason = document.getElementById('license-action-reason').value.trim();
                    await LOUDAPI.licenses.revoke(key, reason);
                    showToast('License key revoked.');
                }
                closeModal('modal-license-action');
                renderLicensesPane();
            } catch(err) {
                showToast(err.message, 'error');
            }
        });

        // 7. Admin Add trigger
        document.getElementById('btn-create-admin').addEventListener('click', () => {
            document.getElementById('admin-form-id').value = '';
            document.getElementById('admin-username').value = '';
            document.getElementById('admin-username').disabled = false;
            document.getElementById('admin-password').value = '';
            document.getElementById('admin-password').required = true;
            document.getElementById('admin-password-group').style.display = 'block';
            document.getElementById('admin-role').value = 'support';

            document.getElementById('admin-modal-title').innerText = 'Create Admin User';
            openModal('modal-admin');
        });

        // Admin Form Submit
        el.adminForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('admin-form-id').value;
            
            try {
                if (id) {
                    const data = {
                        role: document.getElementById('admin-role').value
                    };
                    await LOUDAPI.admins.update(id, data);
                    showToast('Admin role updated.');
                } else {
                    const data = {
                        username: document.getElementById('admin-username').value.trim(),
                        password: document.getElementById('admin-password').value,
                        role: document.getElementById('admin-role').value
                    };
                    await LOUDAPI.admins.create(data);
                    showToast('Admin user created successfully.');
                }
                closeModal('modal-admin');
                renderAdminsPane();
            } catch(err) {
                showToast(err.message, 'error');
            }
        });

        // Admin password reset Submit
        el.adminResetForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const adminId = parseInt(document.getElementById('admin-reset-id').value);
            const pass = document.getElementById('admin-reset-password').value;

            try {
                await LOUDAPI.admins.resetPassword(adminId, pass);
                showToast('Admin password reset successfully.');
                closeModal('modal-admin-reset');
            } catch(err) {
                showToast(err.message, 'error');
            }
        });

        // 8. Settings change password Submit
        el.settingsPasswordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const oldPass = document.getElementById('settings-old-pass').value;
            const newPass = document.getElementById('settings-new-pass').value;

            try {
                await LOUDAPI.admins.changePassword(oldPass, newPass);
                showToast('Your account password has been updated.');
                el.settingsPasswordForm.reset();
            } catch(err) {
                showToast(err.message, 'error');
            }
        });

        // 9. Filters logic
        document.getElementById('filter-license-product').addEventListener('change', runLicenseFiltering);
        document.getElementById('filter-license-status').addEventListener('change', runLicenseFiltering);
        document.getElementById('search-licenses-input').addEventListener('input', debounce(runLicenseFiltering, 300));
        
        async function runLicenseFiltering() {
            const product_id = document.getElementById('filter-license-product').value;
            const status = document.getElementById('filter-license-status').value;
            const q = document.getElementById('search-licenses-input').value.trim();

            toggleLoader(true);
            try {
                const res = await LOUDAPI.licenses.search({
                    product_id: product_id ? parseInt(product_id) : null,
                    status: status || null,
                    q: q || null
                });
                populateLicensesTable(res.data?.licenses || []);
            } catch(e) {
                showToast(e.message, 'error');
            } finally {
                toggleLoader(false);
            }
        }

        // Live table search filters
        setupLiveSearch('search-products-input', 'products-table', 0);
        setupLiveSearch('search-plans-input', 'plans-table', 0);
        setupLiveSearch('search-customers-input', 'customers-table');
        setupLiveSearch('search-devices-input', 'devices-table', 0);
        setupLiveSearch('search-admins-input', 'admins-table', 0);

        // FAQ Accordion listeners
        document.querySelectorAll('.faq-item').forEach(item => {
            item.addEventListener('click', () => {
                const isActive = item.classList.contains('active');
                document.querySelectorAll('.faq-item').forEach(el => el.classList.remove('active'));
                if (!isActive) {
                    item.classList.add('active');
                }
            });
        });
    }

    function setupLiveSearch(inputId, tableId, searchColIndex = null) {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        input.addEventListener('input', () => {
            const query = input.value.toLowerCase().trim();
            const rows = document.querySelectorAll(`#${tableId} tbody tr`);
            
            rows.forEach(row => {
                if (row.cells.length <= 1) return;
                let text = '';
                if (searchColIndex !== null && searchColIndex !== undefined) {
                    const cell = row.cells[searchColIndex];
                    text = cell ? cell.innerText.toLowerCase() : '';
                } else {
                    text = row.innerText.toLowerCase();
                }
                if (!query || text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // Helper functions
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    function escapeHTML(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    window.copyText = function(text) {
        if (!text) {
            showToast('No key to copy.', 'warning');
            return;
        }
        function fallbackCopy(str) {
            const ta = document.createElement('textarea');
            ta.value = str;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            try {
                document.execCommand('copy');
                showToast('Key copied to clipboard!');
            } catch (e) {
                showToast('Failed to copy key.', 'error');
            }
            document.body.removeChild(ta);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('Key copied to clipboard!');
            }).catch(() => {
                fallbackCopy(text);
            });
        } else {
            fallbackCopy(text);
        }
    };

    window.viewProductKey = function(name, key) {
        if (!key) {
            showToast('No API key generated for this product.', 'warning');
            return;
        }
        const modal = document.getElementById('modal-view-product-key');
        if (!modal) {
            window.prompt(`Product API Key for ${name} (Ctrl+C to copy):`, key);
            return;
        }
        document.getElementById('view-key-modal-title').textContent = `${name} - API Key`;
        const input = document.getElementById('view-key-modal-input');
        input.value = key;
        openModal('modal-view-product-key');
        if (window.lucide) lucide.createIcons();
        setTimeout(() => {
            input.focus();
            input.select();
        }, 80);
    };

    window.copyProductKeyFromModal = function() {
        const input = document.getElementById('view-key-modal-input');
        if (input && input.value) {
            copyText(input.value);
        }
    };

    // ==========================================
    // 7. INITIALIZATION BLOCK
    // ==========================================
    function init() {
        // Start WebGL Scene in the background immediately
        LOUDScene3D.init();

        // Run simulated loader progress sequence
        simulateBootLoader(() => {
            // Bind routing handler
            window.addEventListener('hashchange', handleRouting);

            // Bind events
            registerEvents();

            // Perform first routing
            handleRouting();

            // Bind Scroll entrance triggers
            initScrollReveals();
        });
    }

    return {
        init
    };
})();

// Bootstrap the app on load
window.addEventListener('DOMContentLoaded', LOUDApp.init);
