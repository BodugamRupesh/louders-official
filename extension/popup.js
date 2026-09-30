const canvas = document.getElementById('stars');
const ctx = canvas.getContext('2d');
function resize() { 
    if (!canvas) return;
    canvas.width = window.innerWidth || 360; 
    canvas.height = window.innerHeight || 580; 
}
window.addEventListener('resize', resize);
resize();

// 3D Perspective Starfield / Audio Nebula
const stars = [];
const numStars = 110;
for (let i = 0; i < numStars; i++) {
    stars.push({
        x: (Math.random() - 0.5) * (canvas.width || 360) * 2,
        y: (Math.random() - 0.5) * (canvas.height || 580) * 2,
        z: Math.random() * (canvas.width || 360),
        radius: Math.random() * 1.4 + 0.6,
        alpha: Math.random() * 0.7 + 0.3,
        hue: Math.random() > 0.6 ? (Math.random() > 0.5 ? 245 : 285) : 195
    });
}

function draw() {
    if (!ctx || !canvas) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;

    for (let s of stars) {
        s.z -= 0.5;
        if (s.z <= 0) {
            s.z = canvas.width;
            s.x = (Math.random() - 0.5) * canvas.width * 2;
            s.y = (Math.random() - 0.5) * canvas.height * 2;
        }

        const k = 220 / s.z;
        const px = s.x * k + cx;
        const py = s.y * k + cy;

        if (px >= 0 && px <= canvas.width && py >= 0 && py <= canvas.height) {
            const size = Math.max(0.4, (1 - s.z / canvas.width) * s.radius * 2);
            const a = Math.min(1, Math.max(0.1, (1 - s.z / canvas.width) * s.alpha));
            ctx.beginPath();
            ctx.arc(px, py, size, 0, 2 * Math.PI);
            ctx.fillStyle = `hsla(${s.hue}, 80%, 75%, ${a})`;
            ctx.fill();
        }
    }
    requestAnimationFrame(draw);
}
draw();

// Tab Switcher
document.querySelectorAll('.tab-btn').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        const target = document.getElementById(tab.dataset.tab);
        if (target) target.classList.add('active');
    });
});

let settings = {
    gain: 1, bass: 0, clearness: 0, pan: 0, reverb: false,
    compressor: 0, distortion: 0, tremolo: 0, flanger: 0,
    vstPreampGain: 1, vstFilters: [],
    vstDllWarmth: 0, vstDllDrive: 0, vstDllBass: 0, vstDllTreble: 0,
    pluginStates: {}
};

const ui = {
    gain: document.getElementById('gain'), gainVal: document.getElementById('gainVal'),
    clearness: document.getElementById('clearness'), clearnessVal: document.getElementById('clearnessVal'),
    compressor: document.getElementById('compressor'), compressorVal: document.getElementById('compressorVal'),
    distortion: document.getElementById('distortion'), distortionVal: document.getElementById('distortionVal'),
    bass: document.getElementById('bass'), bassVal: document.getElementById('bassVal'),
    pan: document.getElementById('pan'), panVal: document.getElementById('panVal'),
    reverb: document.getElementById('reverb'),
    tremolo: document.getElementById('tremolo'), tremoloVal: document.getElementById('tremoloVal'),
    flanger: document.getElementById('flanger'), flangerVal: document.getElementById('flangerVal')
};

function updateTrackFills() {
    [ui.gain, ui.clearness, ui.compressor, ui.distortion, ui.bass, ui.pan, ui.tremolo, ui.flanger].forEach(el => {
        if (!el) return;
        const min = parseFloat(el.min) || 0;
        const max = parseFloat(el.max) || 100;
        const val = parseFloat(el.value) || 0;
        const pct = Math.max(0, Math.min(100, ((val - min) / (max - min)) * 100));
        el.style.setProperty('--pct', pct + '%');
    });
}

if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(['micSettings'], r => {
        if (r.micSettings) settings = { ...settings, ...r.micSettings };
        syncUI();
        scanPlugins(true);
    });
} else { syncUI(); }

function syncUI() {
    if (ui.gain) {
        ui.gain.value = settings.gain;
        if (ui.gainVal) ui.gainVal.textContent = settings.gain + 'dB';
    }
    if (ui.clearness) {
        ui.clearness.value = settings.clearness;
        if (ui.clearnessVal) ui.clearnessVal.textContent = (settings.clearness > 0 ? '+' : '') + settings.clearness + 'dB';
    }
    if (ui.compressor) {
        ui.compressor.value = settings.compressor || 0;
        if (ui.compressorVal) ui.compressorVal.textContent = (settings.compressor || 0) + '%';
    }
    if (ui.distortion) {
        ui.distortion.value = settings.distortion || 0;
        if (ui.distortionVal) ui.distortionVal.textContent = (settings.distortion || 0) + '%';
    }
    if (ui.bass) {
        ui.bass.value = settings.bass;
        if (ui.bassVal) ui.bassVal.textContent = (settings.bass > 0 ? '+' : '') + settings.bass + 'dB';
    }
    if (ui.pan) {
        ui.pan.value = settings.pan;
        if (ui.panVal) ui.panVal.textContent = settings.pan == 0 ? 'Center' : settings.pan < 0 ? `L ${Math.abs(settings.pan*100).toFixed(0)}%` : `R ${(settings.pan*100).toFixed(0)}%`;
    }
    if (ui.reverb) {
        ui.reverb.checked = settings.reverb;
    }
    if (ui.tremolo) {
        ui.tremolo.value = settings.tremolo || 0;
        if (ui.tremoloVal) ui.tremoloVal.textContent = (settings.tremolo || 0) + '%';
    }
    if (ui.flanger) {
        ui.flanger.value = settings.flanger || 0;
        if (ui.flangerVal) ui.flangerVal.textContent = (settings.flanger || 0) + '%';
    }
    updateTrackFills();
}

function save() {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ micSettings: settings });
    }
    if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.query) {
        chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
            if (tabs && tabs[0] && tabs[0].id) {
                chrome.tabs.sendMessage(tabs[0].id, { type: 'MIC_ENHANCER_UPDATE', settings }).catch(() => {});
            }
        });
    }
}

if (ui.gain) {
    ui.gain.addEventListener('input', e => { 
        settings.gain = parseFloat(e.target.value); 
        if (ui.gainVal) ui.gainVal.textContent = settings.gain + 'dB'; 
        updateTrackFills();
        save(); 
    });
}

if (ui.clearness) {
    ui.clearness.addEventListener('input', e => { 
        settings.clearness = parseInt(e.target.value); 
        if (ui.clearnessVal) ui.clearnessVal.textContent = (settings.clearness > 0 ? '+' : '') + settings.clearness + 'dB'; 
        updateTrackFills();
        save(); 
    });
}

if (ui.compressor) {
    ui.compressor.addEventListener('input', e => { 
        settings.compressor = parseInt(e.target.value); 
        if (ui.compressorVal) ui.compressorVal.textContent = settings.compressor + '%'; 
        updateTrackFills();
        save(); 
    });
}

if (ui.distortion) {
    ui.distortion.addEventListener('input', e => { 
        settings.distortion = parseInt(e.target.value); 
        if (ui.distortionVal) ui.distortionVal.textContent = settings.distortion + '%'; 
        updateTrackFills();
        save(); 
    });
}

if (ui.bass) {
    ui.bass.addEventListener('input', e => { 
        settings.bass = parseInt(e.target.value); 
        if (ui.bassVal) ui.bassVal.textContent = (settings.bass > 0 ? '+' : '') + settings.bass + 'dB'; 
        updateTrackFills();
        save(); 
    });
}

if (ui.pan) {
    ui.pan.addEventListener('input', e => {
        settings.pan = parseFloat(e.target.value);
        if (ui.panVal) ui.panVal.textContent = settings.pan == 0 ? 'Center' : settings.pan < 0 ? `L ${Math.abs(settings.pan*100).toFixed(0)}%` : `R ${(settings.pan*100).toFixed(0)}%`;
        updateTrackFills();
        save();
    });
}

if (ui.reverb) {
    ui.reverb.addEventListener('change', e => { 
        settings.reverb = e.target.checked; 
        save(); 
    });
}

if (ui.tremolo) {
    ui.tremolo.addEventListener('input', e => {
        settings.tremolo = parseInt(e.target.value);
        if (ui.tremoloVal) ui.tremoloVal.textContent = settings.tremolo + '%';
        updateTrackFills();
        save();
    });
}

if (ui.flanger) {
    ui.flanger.addEventListener('input', e => {
        settings.flanger = parseInt(e.target.value);
        if (ui.flangerVal) ui.flangerVal.textContent = settings.flanger + '%';
        updateTrackFills();
        save();
    });
}

document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', e => {
        const targetBtn = e.target.closest('.preset-btn');
        if (!targetBtn) return;
        const t = targetBtn.dataset.preset;
        const p = { 
            radio: {gain:100,clearness:-20,compressor:0,distortion:0,bass:-10,pan:0,reverb:false},
            cave: {gain:500,clearness:-5,compressor:20,distortion:0,bass:15,pan:0,reverb:true},
            mega: {gain:1000,clearness:50,compressor:100,distortion:60,bass:-10,pan:0,reverb:false},
            nuke: {gain:1500,clearness:100,compressor:0,distortion:100,bass:30,pan:0,reverb:true},
            reset: {gain:1,clearness:0,compressor:0,distortion:0,bass:0,pan:0,reverb:false} 
        };
        if (p[t]) { settings = { ...settings, ...p[t] }; syncUI(); save(); }
    });
});

const syncVstBtn = document.getElementById('sync-vst-btn');
if (syncVstBtn) {
    syncVstBtn.addEventListener('click', () => scanPlugins(false));
}

function scanPlugins(silent) {
    if (!chrome?.runtime?.getPackageDirectoryEntry) return;
    const st = document.getElementById('vst-count-status');
    if (!silent && st) st.textContent = 'Scanning...';

    chrome.runtime.getPackageDirectoryEntry(root => {
        root.getDirectory('vst plugins', {create:false}, dir => {
            dir.createReader().readEntries(entries => {
                const files = entries.filter(e => e.isFile && e.name !== 'instructions.txt');
                if (st) st.textContent = files.length + ' plugin' + (files.length!==1?'s':'');
                loadFiles(files);
            }, () => { if(st) st.textContent = 'Error'; });
        }, () => { if(st) st.textContent = 'Folder missing'; });
    });
}

function loadFiles(files) {
    let done = 0;
    const found = {};
    if (!files.length) { finish({}); return; }

    files.forEach(entry => {
        const n = entry.name;
        const isApo = /\.(txt|cfg|ini)$/i.test(n);
        if (isApo) {
            entry.file(f => {
                const r = new FileReader();
                r.onloadend = function() {
                    const p = parseAPO(this.result);
                    const old = settings.pluginStates?.[n];
                    found[n] = { enabled: old?.enabled||false, type:'apo', preamp:p.preamp, filters:p.filters };
                    if (++done === files.length) finish(found);
                };
                r.readAsText(f);
            }, () => { if (++done === files.length) finish(found); });
        } else {
            const old = settings.pluginStates?.[n];
            found[n] = { enabled: old?.enabled||false, type:'dll',
                warmth: old?.warmth??30, drive: old?.drive??20, bass: old?.bass??15, treble: old?.treble??10 };
            if (++done === files.length) finish(found);
        }
    });
}

function finish(found) {
    const ps = settings.pluginStates || {};
    for (let k in ps) { if (!found[k]) delete ps[k]; }
    for (let k in found) { if (!ps[k]) ps[k] = found[k]; else { ps[k].type = found[k].type; if (found[k].type==='apo') { ps[k].preamp=found[k].preamp; ps[k].filters=found[k].filters; } } }
    settings.pluginStates = ps;
    save();
    renderList();
    pushPlugins();
}

function parseAPO(text) {
    let preamp = 0; const filters = [];
    for (let line of text.split(/\r?\n/)) {
        line = line.trim();
        if (!line || line.startsWith('#')) continue;
        const pm = line.match(/Preamp:\s*([+-]?\d*\.?\d+)\s*dB/i);
        if (pm) { preamp = parseFloat(pm[1]); continue; }
        if (/^filter/i.test(line)) {
            if (/\bOFF\b/i.test(line)) continue;
            let type = 'peaking';
            if (/\bPK\b/.test(line)) type='peaking';
            else if (/\bLSC\b/.test(line)) type='lowshelf';
            else if (/\bHSC\b/.test(line)) type='highshelf';
            else if (/\bLP\b/.test(line)) type='lowpass';
            else if (/\bHP\b/.test(line)) type='highpass';
            else if (/\bBP\b/.test(line)) type='bandpass';
            else if (/\bNO\b/.test(line)) type='notch';
            const fc = line.match(/Fc\s+([0-9.]+)/i); const freq = fc ? parseFloat(fc[1]) : 1000;
            const gm = line.match(/Gain\s+([+-]?[0-9.]+)/i); const gain = gm ? parseFloat(gm[1]) : 0;
            const qm = line.match(/Q\s+([0-9.]+)/i); const q = qm ? parseFloat(qm[1]) : 1;
            filters.push({type, frequency:freq, gain, Q:q});
        }
    }
    return {preamp, filters};
}

function renderList() {
    const container = document.getElementById('vst-list');
    if (!container) return;
    container.innerHTML = '';
    const names = Object.keys(settings.pluginStates);
    
    if (!names.length) {
        container.innerHTML = '<div class="no-plugins">No plugins found.<br><span style="font-size:9px;color:#64748b">Place plugins inside "vst plugins/" directory</span></div>';
        return;
    }

    names.forEach(name => {
        const plugin = settings.pluginStates[name];

        const row = document.createElement('div');
        row.className = 'plugin-row';
        row.innerHTML = `
            <div class="plugin-row-left">
                <span class="plugin-arrow">▶</span>
                <span class="plugin-name" title="${name}">${name}</span>
            </div>
            <div class="plugin-row-right">
                <label class="switch">
                    <input type="checkbox" class="ptoggle" data-n="${name}" ${plugin.enabled?'checked':''}>
                    <span class="slider round"></span>
                </label>
            </div>
        `;

        const panel = document.createElement('div');
        panel.className = 'plugin-panel';
        const inner = document.createElement('div');
        inner.className = 'plugin-panel-inner';

        if (plugin.type === 'apo') {
            inner.appendChild(makeSlider(`preamp_${name}`, 'Preamp', plugin.preamp||0, -20, 20, 0.5, 'dB', val => {
                plugin.preamp = val; pushPlugins();
            }));
            if (plugin.filters) {
                plugin.filters.forEach((f, i) => {
                    const tl = f.type.replace('peaking','PK').replace('lowshelf','LSC').replace('highshelf','HSC').replace('lowpass','LP').replace('highpass','HP').replace('bandpass','BP').replace('notch','NO').toUpperCase();
                    inner.appendChild(makeSlider(`freq_${name}_${i}`, `Band ${i+1} (${tl}) Freq`, f.frequency, 20, 20000, 10, 'Hz', val => {
                        f.frequency = val; pushPlugins();
                    }));
                    inner.appendChild(makeSlider(`gain_${name}_${i}`, `Band ${i+1} Gain`, f.gain, -18, 18, 0.5, 'dB', val => {
                        f.gain = val; pushPlugins();
                    }));
                    inner.appendChild(makeSlider(`q_${name}_${i}`, `Band ${i+1} Q`, f.Q, 0.1, 10, 0.1, '', val => {
                        f.Q = val; pushPlugins();
                    }));
                });
            }
        } else {
            [{k:'warmth',l:'Tube Warmth'},{k:'drive',l:'Drive'},{k:'bass',l:'Bass Boost'},{k:'treble',l:'Treble Air'}].forEach(d => {
                inner.appendChild(makeSlider(`dll_${name}_${d.k}`, d.l, plugin[d.k]||0, 0, 100, 1, '%', val => {
                    plugin[d.k] = val; pushPlugins();
                }));
            });
        }

        panel.appendChild(inner);
        container.appendChild(row);
        container.appendChild(panel);

        row.addEventListener('click', e => {
            if (e.target.closest('.switch')) return;
            row.classList.toggle('open');
            panel.classList.toggle('open');
        });
    });

    document.querySelectorAll('.ptoggle').forEach(t => {
        t.addEventListener('change', e => {
            e.stopPropagation();
            settings.pluginStates[e.target.dataset.n].enabled = e.target.checked;
            save(); pushPlugins();
        });
    });
}

function makeSlider(id, labelText, value, min, max, step, unit, onChange) {
    const grp = document.createElement('div');
    grp.className = 'control-card';
    const valText = unit === 'dB' ? ((value > 0 ? '+' : '') + value + 'dB') : unit === 'Hz' ? (value + 'Hz') : (value + unit);
    grp.innerHTML = `
        <div class="card-head">
            <label for="${id}" class="ctrl-label"><span class="ctrl-icon-dot"></span> ${labelText}</label>
            <div class="lcd-badge" id="${id}_v">${valText}</div>
        </div>
        <div class="slider-groove">
            <input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${value}">
        </div>
    `;
    const slider = grp.querySelector('input');
    const updateLocalFill = () => {
        const pct = Math.max(0, Math.min(100, ((slider.value - min) / (max - min)) * 100));
        slider.style.setProperty('--pct', pct + '%');
    };
    updateLocalFill();
    slider.addEventListener('input', e => {
        const v = parseFloat(e.target.value);
        const el = document.getElementById(id + '_v');
        if (el) el.textContent = unit === 'dB' ? ((v > 0 ? '+' : '') + v + 'dB') : unit === 'Hz' ? (v + 'Hz') : (v + unit);
        updateLocalFill();
        onChange(v);
    });
    return grp;
}

function pushPlugins() {
    let preamp = 0; const filters = [];
    let w=0, d=0, b=0, t=0;
    for (let n in settings.pluginStates) {
        const p = settings.pluginStates[n];
        if (!p.enabled) continue;
        if (p.type === 'apo') {
            preamp += p.preamp || 0;
            if (p.filters) filters.push(...p.filters);
        } else {
            w = Math.max(w, p.warmth||0);
            d = Math.max(d, p.drive||0);
            b = Math.max(b, p.bass||0);
            t = Math.max(t, p.treble||0);
        }
    }
    settings.vstPreampGain = Math.pow(10, preamp/20);
    settings.vstFilters = filters.slice(0, 32);
    settings.vstDllWarmth = w; settings.vstDllDrive = d;
    settings.vstDllBass = b; settings.vstDllTreble = t;
    save();
}

/* ===================================================
   LICENSE MANAGEMENT CONTROLLER
   =================================================== */

const licUI = {
    pill: document.getElementById('licenseStatusPill'),
    led: document.getElementById('licenseLed'),
    pillText: document.getElementById('licensePillText'),
    dspLock: document.getElementById('dspLockOverlay'),
    lockBtn: document.getElementById('lockActivateBtn'),
    modal: document.getElementById('licenseModal'),
    modalTitle: document.getElementById('modalTitle'),
    modalClose: document.getElementById('modalCloseBtn'),
    alertBox: document.getElementById('licAlertBox'),
    activateView: document.getElementById('licActivateView'),
    activeView: document.getElementById('licActiveView'),
    emailInput: document.getElementById('licEmail'),
    keyInput: document.getElementById('licKey'),
    serverUrlInput: document.getElementById('licServerUrl'),
    productKeyInput: document.getElementById('licProductKey'),
    submitBtn: document.getElementById('licSubmitActivateBtn'),
    submitBtnText: document.getElementById('licSubmitBtnText'),
    verifyBtn: document.getElementById('licVerifyBtn'),
    deactivateBtn: document.getElementById('licDeactivateBtn'),
    activeKey: document.getElementById('licActiveKeyDisplay'),
    activeEmail: document.getElementById('licActiveEmailDisplay'),
    activeStatus: document.getElementById('licActiveStatusDisplay'),
    activeExpires: document.getElementById('licActiveExpiresDisplay'),
    activeDevice: document.getElementById('licActiveDeviceDisplay'),
    expiryTag: document.getElementById('licExpiryTag'),
    footerStatus: document.getElementById('footerStatusText')
};

let currentLicenseState = null;

function showLicenseAlert(msg, type = 'error') {
    if (!licUI.alertBox) return;
    licUI.alertBox.className = `lic-alert-box alert-${type}`;
    licUI.alertBox.textContent = msg;
    licUI.alertBox.style.display = 'block';
}

function clearLicenseAlert() {
    if (!licUI.alertBox) return;
    licUI.alertBox.style.display = 'none';
    licUI.alertBox.textContent = '';
}

function maskLicenseKey(key) {
    if (!key || key.length < 10) return key || '••••';
    const parts = key.split('-');
    if (parts.length >= 4) {
        return `${parts[0]}-${parts[1]}-••••-••••-${parts[parts.length - 1]}`;
    }
    return key.slice(0, 5) + '••••' + key.slice(-4);
}

function formatLicenseDate(isoStr) {
    if (!isoStr) return 'N/A';
    try {
        const d = new Date(isoStr);
        if (d.getFullYear() > 2200) return 'Lifetime / Permanent';
        return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
        return isoStr;
    }
}

async function refreshLicenseUI() {
    if (typeof LicenseManager === 'undefined') return;

    try {
        currentLicenseState = await LicenseManager.getLicenseState();
    } catch (e) {
        currentLicenseState = { isLicensed: false, status: 'unlicensed' };
    }

    const isLic = !!(currentLicenseState && currentLicenseState.isLicensed);
    settings.isLicensed = isLic;
    save();

    if (isLic) {
        // Active Pro State
        if (licUI.pill) {
            licUI.pill.className = 'license-status-pill active';
            licUI.pill.title = 'License Active (PRO) - Click to manage';
        }
        if (licUI.led) {
            licUI.led.className = 'license-led led-green';
        }
        if (licUI.pillText) {
            const days = currentLicenseState.daysRemaining;
            if (days !== undefined && days < 90000) {
                licUI.pillText.textContent = `${days}D LEFT`;
            } else {
                licUI.pillText.textContent = 'PRO ACTIVE';
            }
        }
        if (licUI.dspLock) {
            licUI.dspLock.style.display = 'none';
        }
        if (licUI.footerStatus) {
            licUI.footerStatus.textContent = 'PRO ENGINE ACTIVE';
        }

        // Populate Active Modal View
        if (licUI.activeKey) licUI.activeKey.textContent = maskLicenseKey(currentLicenseState.licenseKey);
        if (licUI.activeEmail) licUI.activeEmail.textContent = currentLicenseState.customerEmail || 'Registered User';
        if (licUI.activeStatus) licUI.activeStatus.textContent = (currentLicenseState.status || 'Active').toUpperCase();
        if (licUI.activeExpires) licUI.activeExpires.textContent = formatLicenseDate(currentLicenseState.expiresAt);
        if (licUI.activeDevice) {
            const devId = currentLicenseState.deviceUuid || 'Current Machine';
            licUI.activeDevice.textContent = devId.length > 18 ? devId.slice(0, 16) + '…' : devId;
        }
        if (licUI.expiryTag) {
            licUI.expiryTag.textContent = formatLicenseDate(currentLicenseState.expiresAt);
        }
    } else {
        // Unlicensed State
        if (licUI.pill) {
            licUI.pill.className = 'license-status-pill unlicensed';
            licUI.pill.title = 'Unlicensed - Click to activate';
        }
        if (licUI.led) {
            licUI.led.className = 'license-led led-red';
        }
        if (licUI.pillText) {
            licUI.pillText.textContent = 'ACTIVATE';
        }
        if (licUI.dspLock) {
            licUI.dspLock.style.display = 'flex';
        }
        if (licUI.footerStatus) {
            licUI.footerStatus.textContent = 'LICENSE REQUIRED';
        }
    }
}

function openLicenseModal() {
    clearLicenseAlert();
    if (!licUI.modal) return;
    licUI.modal.style.display = 'flex';

    // Populate server and product key from saved state if available
    if (currentLicenseState) {
        if (licUI.serverUrlInput && currentLicenseState.serverUrl) {
            licUI.serverUrlInput.value = currentLicenseState.serverUrl;
        }
        if (licUI.productKeyInput && currentLicenseState.productApiKey) {
            licUI.productKeyInput.value = currentLicenseState.productApiKey;
        }
        if (licUI.emailInput && !licUI.emailInput.value && currentLicenseState.customerEmail) {
            licUI.emailInput.value = currentLicenseState.customerEmail;
        }
        if (licUI.keyInput && !licUI.keyInput.value && currentLicenseState.licenseKey) {
            licUI.keyInput.value = currentLicenseState.licenseKey;
        }
    }

    const isLic = !!(currentLicenseState && currentLicenseState.isLicensed);
    if (isLic) {
        if (licUI.modalTitle) licUI.modalTitle.textContent = 'SUBSCRIPTION DETAILS';
        if (licUI.activateView) licUI.activateView.style.display = 'none';
        if (licUI.activeView) licUI.activeView.style.display = 'block';
    } else {
        if (licUI.modalTitle) licUI.modalTitle.textContent = 'LICENSE ACTIVATION';
        if (licUI.activateView) licUI.activateView.style.display = 'block';
        if (licUI.activeView) licUI.activeView.style.display = 'none';
        if (licUI.emailInput && !licUI.emailInput.value) {
            licUI.emailInput.focus();
        }
    }
}

function closeLicenseModal() {
    if (!licUI.modal) return;
    licUI.modal.style.display = 'none';
    clearLicenseAlert();
}

// Persist server settings changes
if (licUI.serverUrlInput) {
    licUI.serverUrlInput.addEventListener('change', async (e) => {
        const val = e.target.value.trim();
        const state = await LicenseManager.getLicenseState();
        state.serverUrl = val;
        await LicenseManager.setLicenseState(state);
    });
}
if (licUI.productKeyInput) {
    licUI.productKeyInput.addEventListener('change', async (e) => {
        const val = e.target.value.trim();
        const state = await LicenseManager.getLicenseState();
        state.productApiKey = val;
        await LicenseManager.setLicenseState(state);
    });
}

// Auto-format license key as LP-XX-XXXX-XXXX-XXXX
if (licUI.keyInput) {
    licUI.keyInput.addEventListener('input', (e) => {
        let val = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
        if (val.length > 20) val = val.slice(0, 20);
        
        const chunks = [];
        if (val.length > 0) chunks.push(val.slice(0, 2));
        if (val.length > 2) chunks.push(val.slice(2, 4));
        if (val.length > 4) chunks.push(val.slice(4, 8));
        if (val.length > 8) chunks.push(val.slice(8, 12));
        if (val.length > 12) chunks.push(val.slice(12, 16));
        if (val.length > 16) chunks.push(val.slice(16, 20));
        
        e.target.value = chunks.join('-');
    });
}

// Open modal triggers
if (licUI.pill) {
    licUI.pill.addEventListener('click', openLicenseModal);
}
if (licUI.lockBtn) {
    licUI.lockBtn.addEventListener('click', openLicenseModal);
}
if (licUI.modalClose) {
    licUI.modalClose.addEventListener('click', closeLicenseModal);
}

// Click backdrop to close
if (licUI.modal) {
    licUI.modal.addEventListener('click', (e) => {
        if (e.target === licUI.modal) closeLicenseModal();
    });
}

// Activate Form Submission
if (licUI.submitBtn) {
    licUI.submitBtn.addEventListener('click', async () => {
        const email = licUI.emailInput?.value?.trim();
        const key = licUI.keyInput?.value?.trim();
        const serverUrl = licUI.serverUrlInput?.value?.trim() || 'http://127.0.0.1:8000';
        const productKey = licUI.productKeyInput?.value?.trim();

        if (!email) {
            showLicenseAlert('Please enter the customer email address used during purchase.', 'error');
            licUI.emailInput?.focus();
            return;
        }

        if (!key || key.length < 12) {
            showLicenseAlert('Please enter a valid license key (e.g. LP-26-XXXX-XXXX-XXXX).', 'error');
            licUI.keyInput?.focus();
            return;
        }

        clearLicenseAlert();
        licUI.submitBtn.disabled = true;
        if (licUI.submitBtnText) licUI.submitBtnText.textContent = 'CONNECTING TO SERVER...';

        try {
            const newState = await LicenseManager.activateLicense({
                customerEmail: email,
                licenseKey: key,
                serverUrl: serverUrl,
                productApiKey: productKey
            });

            showLicenseAlert('✓ License activated successfully! DSP Engine unlocked.', 'success');
            await refreshLicenseUI();

            setTimeout(() => {
                if (licUI.activateView) licUI.activateView.style.display = 'none';
                if (licUI.activeView) licUI.activeView.style.display = 'block';
                if (licUI.modalTitle) licUI.modalTitle.textContent = 'SUBSCRIPTION DETAILS';
                clearLicenseAlert();
            }, 1200);

        } catch (err) {
            showLicenseAlert(err.message || 'Activation failed. Please check your credentials.', 'error');
        } finally {
            licUI.submitBtn.disabled = false;
            if (licUI.submitBtnText) licUI.submitBtnText.textContent = 'ACTIVATE DEVICE';
        }
    });
}

// Verify Button Handler
if (licUI.verifyBtn) {
    licUI.verifyBtn.addEventListener('click', async () => {
        licUI.verifyBtn.disabled = true;
        licUI.verifyBtn.textContent = 'VERIFYING...';
        clearLicenseAlert();

        try {
            const res = await LicenseManager.verifyLicense();
            if (res.isLicensed) {
                showLicenseAlert('✓ License is verified and active.', 'success');
            } else {
                showLicenseAlert('Notice: License verification failed or expired.', 'error');
            }
            await refreshLicenseUI();
        } catch (err) {
            showLicenseAlert('Connection error while verifying license.', 'error');
        } finally {
            licUI.verifyBtn.disabled = false;
            licUI.verifyBtn.textContent = 'SYNC / VERIFY';
        }
    });
}

// Deactivate Button Handler
if (licUI.deactivateBtn) {
    licUI.deactivateBtn.addEventListener('click', async () => {
        const confirmDeactivate = confirm(
            'Deactivate this device?\n\n' +
            'This will unlink this browser from your license so you can use it on another computer.\n' +
            'Audio DSP processing will be disabled.'
        );

        if (!confirmDeactivate) return;

        licUI.deactivateBtn.disabled = true;
        licUI.deactivateBtn.textContent = 'DEACTIVATING...';

        try {
            await LicenseManager.deactivateLicense();
            showLicenseAlert('Device deactivated. License unlinked.', 'info');
            await refreshLicenseUI();

            setTimeout(() => {
                if (licUI.activateView) licUI.activateView.style.display = 'block';
                if (licUI.activeView) licUI.activeView.style.display = 'none';
                if (licUI.modalTitle) licUI.modalTitle.textContent = 'LICENSE ACTIVATION';
                clearLicenseAlert();
            }, 1000);
        } catch (err) {
            showLicenseAlert(err.message || 'Failed to deactivate device.', 'error');
        } finally {
            licUI.deactivateBtn.disabled = false;
            licUI.deactivateBtn.textContent = 'DEACTIVATE';
        }
    });
}

// Listen for storage changes from background worker
if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.onChanged) {
    chrome.storage.onChanged.addListener((changes, namespace) => {
        if (namespace === 'local' && changes.louders_license_state) {
            refreshLicenseUI();
        }
    });
}

// Initialize License on load
refreshLicenseUI();

