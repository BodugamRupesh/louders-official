const http = require('http');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const PORT = 4890;
const APO_DIR = 'C:\\Program Files\\EqualizerAPO';
const APO_EDITOR = path.join(APO_DIR, 'Editor.exe');

const server = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

    const reqUrl = new URL(req.url, `http://${req.headers.host}`);
    
    if (reqUrl.pathname === '/open') {
        const fileName = reqUrl.searchParams.get('file');
        if (!fileName || !/^[a-zA-Z0-9 _.\-()]+$/.test(fileName)) {
            res.writeHead(400, {'Content-Type':'application/json'});
            res.end(JSON.stringify({error:'Invalid file'}));
            return;
        }

        const ext = path.extname(fileName).toLowerCase();
        
        if (ext === '.dll' || ext === '.vst3' || ext === '.vst') {
            if (fs.existsSync(APO_EDITOR)) {
                exec(`start "" /D "${APO_DIR}" "${APO_EDITOR}"`, (err) => {
                    if (err) {
                        console.log('[Error] ' + err.message);
                        res.writeHead(500, {'Content-Type':'application/json'});
                        res.end(JSON.stringify({error: err.message}));
                        return;
                    }
                    console.log(`[OK] Opened Equalizer APO Editor for: ${fileName}`);
                    res.writeHead(200, {'Content-Type':'application/json'});
                    res.end(JSON.stringify({success:true, opened:'Equalizer APO Editor', note:'Open the plugin panel from inside the Editor'}));
                });
            } else {
                res.writeHead(200, {'Content-Type':'application/json'});
                res.end(JSON.stringify({success:false, error:'apo_not_found'}));
            }
            return;
        }

        const filePath = path.join(__dirname, 'vst plugins', fileName);
        exec(`start "" "${filePath}"`, (err) => {
            if (err) {
                console.log(`[Error] ${filePath}: ${err.message}`);
                res.writeHead(500, {'Content-Type':'application/json'});
                res.end(JSON.stringify({error: err.message}));
                return;
            }
            console.log(`[OK] Opened: ${filePath}`);
            res.writeHead(200, {'Content-Type':'application/json'});
            res.end(JSON.stringify({success:true, opened:fileName}));
        });
    } else {
        res.writeHead(404); res.end('Not Found');
    }
});

server.listen(PORT, () => {
    console.log('==============================================');
    console.log(`  LOUDERS OFFICIAL BRIDGE - PORT ${PORT}`);
    console.log('==============================================');
    console.log('  Server chalu hai. Made with punjuu.');
    console.log('  Extension me "Open" click karke panel open karo.');
    console.log('  Ye window band mat karna.');
    console.log('==============================================');
});
