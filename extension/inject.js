const originalGetUserMedia = navigator.mediaDevices ? navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices) : null;

let currentSettings = {
    gain: 1,
    bass: 0,
    clearness: 0,
    pan: 0,
    reverb: false,
    compressor: 0,
    distortion: 0,
    tremolo: 0,
    flanger: 0,
    vstPreampGain: 1.0,
    vstFilters: [],
    vstDllWarmth: 0,
    vstDllDrive: 0,
    vstDllBass: 0,
    vstDllTreble: 0,
    isLicensed: false
};

const activeAudioNodes = new Set();

function createReverbImpulse(audioContext, duration, decay) {
    const sampleRate = audioContext.sampleRate;
    const length = sampleRate * duration;
    const impulse = audioContext.createBuffer(2, length, sampleRate);
    const left = impulse.getChannelData(0);
    const right = impulse.getChannelData(1);

    for (let i = 0; i < length; i++) {
        left[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
        right[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
    }
    return impulse;
}

function makeDistortionCurve(amount) {
    if (amount === 0) return null;
    const k = amount;
    const n_samples = 44100;
    const curve = new Float32Array(n_samples);
    const deg = Math.PI / 180;
    
    const maxVal = (3 + k) * 20 * deg / (Math.PI + k);
    
    for (let i = 0; i < n_samples; ++i) {
        const x = i * 2 / n_samples - 1;
        curve[i] = ((3 + k) * x * 20 * deg / (Math.PI + k * Math.abs(x))) / maxVal;
    }
    return curve;
}

function makeTubeSaturationCurve(drive, warmth) {
    if (drive === 0 && warmth === 0) return null;
    const n_samples = 44100;
    const curve = new Float32Array(n_samples);
    for (let i = 0; i < n_samples; ++i) {
        const x = i * 2 / n_samples - 1;
        const k = 1 + drive * 3;
        let y = Math.tanh(k * x) / Math.tanh(k);
        if (x > 0) {
            y = y * (1 - warmth * 0.15);
        } else {
            y = y * (1 + warmth * 0.15);
        }
        curve[i] = y;
    }
    return curve;
}

window.addEventListener('message', (event) => {
    if (event.source !== window) return;

    if (event.data && event.data.type === 'MIC_ENHANCER_UPDATE') {
        currentSettings = { ...currentSettings, ...event.data.settings };
        
        if (!currentSettings.isLicensed) {
            activeAudioNodes.forEach(nodes => {
                if (nodes.gainNode) nodes.gainNode.gain.value = 1.0;
                if (nodes.bassNode) nodes.bassNode.gain.value = 0;
                if (nodes.clearnessNode) nodes.clearnessNode.gain.value = 0;
                if (nodes.pannerNode) nodes.pannerNode.pan.value = 0;
                if (nodes.reverbMixNode) nodes.reverbMixNode.gain.value = 0;
                if (nodes.dryMixNode) nodes.dryMixNode.gain.value = 1.0;
                if (nodes.compNode) { nodes.compNode.threshold.value = 0; nodes.compNode.ratio.value = 1; }
                if (nodes.distNode) nodes.distNode.curve = null;
                if (nodes.tremoloDepth) nodes.tremoloDepth.gain.value = 0;
                if (nodes.flangerMixNode) nodes.flangerMixNode.gain.value = 0;
                if (nodes.tubeWarmthNode) nodes.tubeWarmthNode.curve = null;
                if (nodes.tubeBassSweetener) nodes.tubeBassSweetener.gain.value = 0;
                if (nodes.tubeAirSweetener) nodes.tubeAirSweetener.gain.value = 0;
                if (nodes.vstPreamp) nodes.vstPreamp.gain.value = 1.0;
                if (nodes.vstFilters) {
                    for (let i = 0; i < nodes.vstFilters.length; i++) {
                        nodes.vstFilters[i].gain.value = 0;
                    }
                }
            });
            return;
        }

        activeAudioNodes.forEach(nodes => {
            nodes.gainNode.gain.value = currentSettings.gain;
            
            nodes.bassNode.gain.value = Math.min(Math.max(currentSettings.bass, -40), 40);
            
            const mappedClearness = currentSettings.clearness > 0 
                ? (currentSettings.clearness / 10000) * 25 
                : Math.max(currentSettings.clearness, -40);
            nodes.clearnessNode.gain.value = mappedClearness;
            
            if (nodes.pannerNode) {
                nodes.pannerNode.pan.value = currentSettings.pan;
            }

            nodes.reverbMixNode.gain.value = currentSettings.reverb ? 0.8 : 0;
            nodes.dryMixNode.gain.value = currentSettings.reverb ? 0.5 : 1;

            nodes.compNode.threshold.value = -50 * (currentSettings.compressor / 100); 
            nodes.compNode.ratio.value = 1 + (19 * (currentSettings.compressor / 100));
            
            nodes.distNode.curve = makeDistortionCurve(currentSettings.distortion * 10);

            nodes.tremoloDepth.gain.value = (currentSettings.tremolo || 0) / 100;
            
            nodes.flangerMixNode.gain.value = (currentSettings.flanger || 0) / 100;
            nodes.flangerDepth.gain.value = (currentSettings.flanger || 0) > 0 ? 0.002 : 0;
            nodes.flangerFeedback.gain.value = (currentSettings.flanger || 0) > 0 ? 0.5 : 0;

            const preampVal = currentSettings.vstPreampGain !== undefined ? currentSettings.vstPreampGain : 1.0;
            nodes.vstPreamp.gain.value = preampVal;

            const activeFilters = currentSettings.vstFilters || [];
            for (let i = 0; i < 32; i++) {
                const fNode = nodes.vstFilters[i];
                if (i < activeFilters.length) {
                    const fDef = activeFilters[i];
                    fNode.type = fDef.type || 'peaking';
                    fNode.frequency.value = fDef.frequency || 1000;
                    fNode.gain.value = fDef.gain || 0;
                    fNode.Q.value = fDef.Q || 1.0;
                } else {
                    fNode.type = 'peaking';
                    fNode.frequency.value = 1000;
                    fNode.gain.value = 0;
                    fNode.Q.value = 1.0;
                }
            }

            const dllWarmth = currentSettings.vstDllWarmth || 0;
            const dllDrive = currentSettings.vstDllDrive || 0;
            const dllBass = currentSettings.vstDllBass || 0;
            const dllTreble = currentSettings.vstDllTreble || 0;

            nodes.tubeBassSweetener.gain.value = (dllBass / 10000) * 6;
            nodes.tubeAirSweetener.gain.value = (dllTreble / 10000) * 4;

            if (dllWarmth > 0 || dllDrive > 0) {
                nodes.tubeWarmthNode.curve = makeTubeSaturationCurve(dllDrive / 100, dllWarmth / 100);
            } else {
                nodes.tubeWarmthNode.curve = null;
            }
        });
    }
});

window.postMessage({ type: 'MIC_ENHANCER_INIT' }, '*');

if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia = async function(constraints) {
        if (constraints && constraints.audio && typeof constraints.audio === 'object') {
            constraints.audio.echoCancellation = false;
            constraints.audio.noiseSuppression = false;
            constraints.audio.autoGainControl = false;
            constraints.audio.channelCount = 2;
        }

        const stream = await originalGetUserMedia(constraints);
        if (!constraints || !constraints.audio || stream.getAudioTracks().length === 0) return stream;

        // Security gate: If extension is not licensed, bypass DSP and return clean microphone stream
        if (!currentSettings.isLicensed) {
            console.log('[Louders Official] DSP engine bypassed: Active license required.');
            return stream;
        }

        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const sourceNode = audioContext.createMediaStreamSource(stream);
        
        const distNode = audioContext.createWaveShaper();
        distNode.oversample = '4x';
        
        const bassNode = audioContext.createBiquadFilter();
        bassNode.type = 'lowshelf';
        bassNode.frequency.value = 200;
        
        const clearnessNode = audioContext.createBiquadFilter();
        clearnessNode.type = 'highshelf';
        clearnessNode.frequency.value = 3000;

        const vstPreamp = audioContext.createGain();
        vstPreamp.gain.value = currentSettings.vstPreampGain !== undefined ? currentSettings.vstPreampGain : 1.0;

        const vstFilters = [];
        const numVstFilters = 32;
        for (let i = 0; i < numVstFilters; i++) {
            const filter = audioContext.createBiquadFilter();
            filter.type = 'peaking';
            filter.frequency.value = 1000;
            filter.gain.value = 0;
            filter.Q.value = 1.0;
            vstFilters.push(filter);
        }

        const tubeBassSweetener = audioContext.createBiquadFilter();
        tubeBassSweetener.type = 'lowshelf';
        tubeBassSweetener.frequency.value = 80;
        tubeBassSweetener.gain.value = (currentSettings.vstDllBass || 0) / 100 * 6;

        const tubeAirSweetener = audioContext.createBiquadFilter();
        tubeAirSweetener.type = 'highshelf';
        tubeAirSweetener.frequency.value = 12000;
        tubeAirSweetener.gain.value = (currentSettings.vstDllTreble || 0) / 100 * 4;

        const tubeWarmthNode = audioContext.createWaveShaper();
        tubeWarmthNode.oversample = '4x';
        if ((currentSettings.vstDllWarmth || 0) > 0 || (currentSettings.vstDllDrive || 0) > 0) {
            tubeWarmthNode.curve = makeTubeSaturationCurve((currentSettings.vstDllDrive || 0) / 100, (currentSettings.vstDllWarmth || 0) / 100);
        } else {
            tubeWarmthNode.curve = null;
        }
        
        const gainNode = audioContext.createGain();
        
        const compNode = audioContext.createDynamicsCompressor();
        compNode.knee.value = 0;
        compNode.attack.value = 0.005;
        compNode.release.value = 0.050;

        const tremoloGain = audioContext.createGain();
        const tremoloLFO = audioContext.createOscillator();
        const tremoloDepth = audioContext.createGain();
        tremoloLFO.type = 'sine';
        tremoloLFO.frequency.value = 6; 
        tremoloLFO.connect(tremoloDepth);
        tremoloDepth.connect(tremoloGain.gain);
        tremoloLFO.start();

        const flangerDry = audioContext.createGain();
        const flangerWet = audioContext.createGain();
        const flangerDelay = audioContext.createDelay();
        const flangerLFO = audioContext.createOscillator();
        const flangerDepth = audioContext.createGain();
        const flangerFeedback = audioContext.createGain();
        const flangerMixNode = audioContext.createGain();

        flangerDelay.delayTime.value = 0.005;
        flangerLFO.type = 'sine';
        flangerLFO.frequency.value = 0.5;
        flangerLFO.connect(flangerDepth);
        flangerDepth.connect(flangerDelay.delayTime);
        flangerLFO.start();

        flangerDelay.connect(flangerFeedback);
        flangerFeedback.connect(flangerDelay);
        flangerDelay.connect(flangerMixNode);
        
        const preFlangerGain = audioContext.createGain();

        const pannerNode = audioContext.createStereoPanner();
        pannerNode.pan.value = currentSettings.pan;
        
        const convolverNode = audioContext.createConvolver();
        convolverNode.buffer = createReverbImpulse(audioContext, 2.0, 3.0);
        const dryMixNode = audioContext.createGain();
        const reverbMixNode = audioContext.createGain();

        sourceNode.connect(distNode);
        distNode.connect(bassNode);
        bassNode.connect(clearnessNode);

        clearnessNode.connect(vstPreamp);
        let lastFilterNode = vstPreamp;
        for (let i = 0; i < numVstFilters; i++) {
            lastFilterNode.connect(vstFilters[i]);
            lastFilterNode = vstFilters[i];
        }
        lastFilterNode.connect(tubeBassSweetener);
        tubeBassSweetener.connect(tubeAirSweetener);
        tubeAirSweetener.connect(tubeWarmthNode);

        tubeWarmthNode.connect(tremoloGain);
        tremoloGain.connect(preFlangerGain);
        
        preFlangerGain.connect(flangerDry);
        preFlangerGain.connect(flangerDelay);
        
        flangerDry.connect(gainNode);
        flangerMixNode.connect(gainNode);
        
        gainNode.connect(compNode);
        compNode.connect(pannerNode);
        
        pannerNode.connect(dryMixNode);
        pannerNode.connect(convolverNode);
        convolverNode.connect(reverbMixNode);
        
        const destinationNode = audioContext.createMediaStreamDestination();
        destinationNode.channelCount = 2;
        destinationNode.channelCountMode = 'explicit';
        
        dryMixNode.connect(destinationNode);
        reverbMixNode.connect(destinationNode);

        const nodes = { 
            ctx: audioContext, 
            gainNode, 
            pannerNode, 
            bassNode, 
            clearnessNode, 
            compNode, 
            distNode, 
            dryMixNode, 
            reverbMixNode, 
            tremoloDepth, 
            flangerMixNode, 
            flangerDepth, 
            flangerFeedback,
            vstPreamp,
            vstFilters,
            tubeBassSweetener,
            tubeAirSweetener,
            tubeWarmthNode
        };
        activeAudioNodes.add(nodes);

        const activeFilters = currentSettings.vstFilters || [];
        for (let i = 0; i < numVstFilters; i++) {
            const fNode = vstFilters[i];
            if (i < activeFilters.length) {
                const fDef = activeFilters[i];
                fNode.type = fDef.type || 'peaking';
                fNode.frequency.value = fDef.frequency || 1000;
                fNode.gain.value = fDef.gain || 0;
                fNode.Q.value = fDef.Q || 1.0;
            }
        }

        gainNode.gain.value = currentSettings.gain;
        bassNode.gain.value = Math.min(Math.max(currentSettings.bass, -40), 40);
        const mappedClearness = currentSettings.clearness > 0 ? (currentSettings.clearness / 10000) * 25 : Math.max(currentSettings.clearness, -40);
        clearnessNode.gain.value = mappedClearness;
        reverbMixNode.gain.value = currentSettings.reverb ? 0.8 : 0;
        dryMixNode.gain.value = currentSettings.reverb ? 0.5 : 1;
        compNode.threshold.value = -50 * (currentSettings.compressor / 100);
        compNode.ratio.value = 1 + (19 * (currentSettings.compressor / 100));
        distNode.curve = makeDistortionCurve(currentSettings.distortion * 10);
        
        tremoloDepth.gain.value = (currentSettings.tremolo || 0) / 100;
        flangerMixNode.gain.value = (currentSettings.flanger || 0) / 100;
        flangerDepth.gain.value = (currentSettings.flanger || 0) > 0 ? 0.002 : 0;
        flangerFeedback.gain.value = (currentSettings.flanger || 0) > 0 ? 0.5 : 0;

        stream.getAudioTracks()[0].onended = () => {
            activeAudioNodes.delete(nodes);
            audioContext.close();
        };

        const modifiedStream = destinationNode.stream;
        stream.getVideoTracks().forEach(track => modifiedStream.addTrack(track));

        const originalStop = modifiedStream.getTracks.bind(modifiedStream);
        modifiedStream.getTracks = function() {
            const tracks = originalStop();
            return tracks.map(t => {
                const oStop = t.stop.bind(t);
                t.stop = () => { oStop(); stream.getTracks().forEach(ot => ot.stop()); };
                return t;
            });
        };

        return modifiedStream;
    };
}
