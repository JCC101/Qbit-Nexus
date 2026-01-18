import json
import os
import threading
from flask import Flask, request, jsonify, render_template_string
import qbittorrentapi

# --- 配置存储路径 ---
DATA_DIR = os.getenv('DATA_DIR', '.')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
CONFIG_FILE = os.path.join(DATA_DIR, 'nexus_config.json')

app = Flask(__name__)

# --- 嵌入式 HTML 模板 (极简暗黑风) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qbit-Nexus | Central Control</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #0b0c10; color: #c5c6c7; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .nexus-card { background-color: #1f2833; border-radius: 0.5rem; padding: 1.5rem; border: 1px solid #45a29e; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); }
        .nexus-input { background-color: #0b0c10; border: 1px solid #45a29e; color: #66fcf1; border-radius: 0.25rem; padding: 0.5rem; width: 100%; transition: 0.3s; }
        .nexus-input:focus { outline: none; box-shadow: 0 0 10px #45a29e; }
        .nexus-btn { padding: 0.5rem 1rem; border-radius: 0.25rem; font-weight: 600; cursor: pointer; transition: all 0.3s; text-transform: uppercase; letter-spacing: 1px; }
        .btn-action { background-color: #45a29e; color: #0b0c10; }
        .btn-action:hover { background-color: #66fcf1; box-shadow: 0 0 15px #66fcf1; }
        .btn-danger { background-color: #b91c1c; color: white; }
        .btn-danger:hover { background-color: #ef4444; }
        .log-terminal { background-color: #000; font-family: 'Consolas', monospace; height: 250px; overflow-y: auto; padding: 15px; border-radius: 4px; border: 1px solid #333; color: #66fcf1; font-size: 0.8rem; }
        .header-glow { text-shadow: 0 0 10px #45a29e; }
    </style>
</head>
<body class="p-4 md:p-8">

<div class="max-w-7xl mx-auto mb-8 flex justify-between items-center">
    <h1 class="text-3xl font-bold text-[#66fcf1] header-glow"><i class="fas fa-network-wired mr-3"></i>Qbit-Nexus</h1>
    <span class="text-xs text-gray-500">Version 1.0.0</span>
</div>

<div class="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
    
    <!-- 左侧：节点列表 -->
    <div class="lg:col-span-4 space-y-6">
        <div class="nexus-card">
            <h2 class="text-xl font-bold mb-4 text-[#66fcf1]"><i class="fas fa-server mr-2"></i>Nodes</h2>
            <div id="serverList" class="space-y-3 mb-6"></div>
            
            <div class="border-t border-slate-700 pt-4">
                <h3 class="text-xs font-semibold mb-3 text-gray-400 uppercase tracking-widest">Add Node</h3>
                <div class="space-y-3">
                    <input type="text" id="newHost" placeholder="Host (http://IP:Port)" class="nexus-input">
                    <div class="grid grid-cols-2 gap-3">
                        <input type="text" id="newUser" placeholder="Username" class="nexus-input">
                        <input type="password" id="newPass" placeholder="Password" class="nexus-input">
                    </div>
                    <button onclick="addServer()" class="nexus-btn btn-action w-full"><i class="fas fa-plus mr-2"></i>Link Node</button>
                </div>
            </div>
        </div>
    </div>

    <!-- 右侧：分发控制台 -->
    <div class="lg:col-span-8 space-y-6">
        <div class="nexus-card">
            <h2 class="text-xl font-bold mb-4 text-[#66fcf1]"><i class="fas fa-satellite-dish mr-2"></i>Broadcast Task</h2>
            
            <form id="uploadForm" class="space-y-5">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-xs font-bold text-gray-400 mb-2 uppercase">Torrent File</label>
                        <input type="file" id="torrentFile" accept=".torrent" class="nexus-input text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-gray-400 mb-2 uppercase">Magnet Link</label>
                        <input type="text" id="magnetLink" placeholder="magnet:?xt=urn:btih:..." class="nexus-input">
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 bg-[#0b0c10] p-4 rounded border border-[#333]">
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">Save Path</label>
                        <input type="text" id="savePath" placeholder="/downloads/" class="nexus-input h-8 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">Category</label>
                        <input type="text" id="category" placeholder="Movies" class="nexus-input h-8 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">Tags</label>
                        <input type="text" id="tags" placeholder="nexus, 4k" class="nexus-input h-8 text-sm">
                    </div>
                    <div class="flex items-end pb-1 gap-4">
                        <label class="inline-flex items-center cursor-pointer">
                            <input type="checkbox" id="paused" class="accent-[#45a29e] w-4 h-4">
                            <span class="ml-2 text-sm text-gray-400">Pause</span>
                        </label>
                        <label class="inline-flex items-center cursor-pointer">
                            <input type="checkbox" id="rootFolder" checked class="accent-[#45a29e] w-4 h-4">
                            <span class="ml-2 text-sm text-gray-400">Root Dir</span>
                        </label>
                        <label class="inline-flex items-center cursor-pointer">
                            <input type="checkbox" id="autoTMM" class="accent-[#45a29e] w-4 h-4">
                            <span class="ml-2 text-sm text-gray-400">AutoTMM</span>
                        </label>
                    </div>
                </div>

                <button type="button" onclick="distributeTorrent()" class="nexus-btn btn-action w-full py-3 text-lg shadow-lg">
                    <i class="fas fa-paper-plane mr-2"></i> Initiate Broadcast
                </button>
            </form>
        </div>

        <div class="nexus-card">
            <div class="flex justify-between items-center mb-2">
                <h2 class="text-sm font-bold text-gray-400 uppercase">System Log</h2>
                <button onclick="document.getElementById('consoleLog').innerHTML=''" class="text-xs text-gray-600 hover:text-white">Clear</button>
            </div>
            <div id="consoleLog" class="log-terminal">System Ready... Waiting for command.</div>
        </div>
    </div>
</div>

<script>
    // --- Frontend Logic ---
    async function loadServers() {
        const res = await fetch('/api/servers');
        const servers = await res.json();
        const container = document.getElementById('serverList');
        container.innerHTML = '';

        if(servers.length === 0) {
            container.innerHTML = '<div class="text-gray-600 text-center text-xs py-4 border border-dashed border-gray-700 rounded">NO NODES LINKED</div>';
            return;
        }

        servers.forEach((s, idx) => {
            const div = document.createElement('div');
            div.className = 'flex justify-between items-center bg-[#0b0c10] p-3 rounded border border-gray-800 hover:border-[#45a29e] transition-colors';
            div.innerHTML = `
                <div class="overflow-hidden">
                    <div class="font-bold text-sm text-[#66fcf1] truncate">${s.host}</div>
                    <div class="text-xs text-gray-500">${s.username}</div>
                </div>
                <div class="flex gap-2">
                     <button onclick="testServer(${idx})" class="text-gray-400 hover:text-[#66fcf1] transition-colors" title="Ping"><i class="fas fa-signal"></i></button>
                    <button onclick="removeServer(${idx})" class="text-gray-600 hover:text-red-500 transition-colors" title="Unlink"><i class="fas fa-times"></i></button>
                </div>
            `;
            container.appendChild(div);
        });
    }

    async function addServer() {
        const host = document.getElementById('newHost').value.trim();
        const username = document.getElementById('newUser').value.trim();
        const password = document.getElementById('newPass').value.trim();
        if(!host || !username) return alert("Host and Username required");

        const res = await fetch('/api/servers', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ host, username, password })
        });
        
        if(res.ok) {
            document.getElementById('newHost').value = '';
            document.getElementById('newUser').value = '';
            document.getElementById('newPass').value = '';
            loadServers();
            log(`NODE LINKED: ${host}`, 'success');
        } else {
            log("FAILED TO LINK NODE", 'error');
        }
    }

    async function removeServer(idx) {
        if(!confirm("Unlink this node?")) return;
        await fetch(`/api/servers/${idx}`, { method: 'DELETE' });
        loadServers();
    }
    
    async function testServer(idx) {
        log(`Pinging Node #${idx+1}...`);
        const res = await fetch(`/api/servers/${idx}/test`, { method: 'POST' });
        const data = await res.json();
        if(data.success) {
            log(`[ACK] Node #${idx+1} Online (v${data.version})`, 'success');
        } else {
            log(`[ERR] Node #${idx+1} Unreachable: ${data.error}`, 'error');
        }
    }

    async function distributeTorrent() {
        const fileInput = document.getElementById('torrentFile');
        const magnet = document.getElementById('magnetLink').value.trim();
        
        if (!fileInput.files[0] && !magnet) return alert("Payload required (Torrent File or Magnet)");

        const formData = new FormData();
        if (fileInput.files[0]) formData.append('file', fileInput.files[0]);
        if (magnet) formData.append('magnet', magnet);

        formData.append('save_path', document.getElementById('savePath').value.trim());
        formData.append('category', document.getElementById('category').value.trim());
        formData.append('tags', document.getElementById('tags').value.trim());
        formData.append('paused', document.getElementById('paused').checked);
        formData.append('root_folder', document.getElementById('rootFolder').checked);
        formData.append('auto_tmm', document.getElementById('autoTMM').checked);

        log(">>> INITIATING BROADCAST SEQUENCE...", 'info');

        try {
            const res = await fetch('/api/distribute', { method: 'POST', body: formData });
            const result = await res.json();
            
            result.results.forEach(r => {
                if(r.success) log(`[SENT] -> ${r.server}`, 'success');
                else log(`[FAIL] -> ${r.server}: ${r.error}`, 'error');
            });
            
            if(result.results.every(r => r.success)) log(">>> BROADCAST COMPLETE. ALL NODES ACKNOWLEDGED.", 'success');

        } catch (e) {
            log("SYSTEM FAILURE: " + e.message, 'error');
        }
    }

    function log(msg, type='info') {
        const box = document.getElementById('consoleLog');
        const time = new Date().toLocaleTimeString('en-US', {hour12: false});
        let color = '#c5c6c7';
        if(type === 'success') color = '#66fcf1';
        if(type === 'error') color = '#fc5185';
        
        box.innerHTML += `<div style="color:${color}; margin-bottom: 2px;"><span style="opacity:0.5">[${time}]</span> ${msg}</div>`;
        box.scrollTop = box.scrollHeight;
    }

    loadServers();
</script>
</body>
</html>
"""

# --- 后端逻辑 ---

def load_config():
    if not os.path.exists(CONFIG_FILE): return []
    try:
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    except: return []

def save_config(servers):
    with open(CONFIG_FILE, 'w') as f: json.dump(servers, f, indent=4)

def get_client(server_conf):
    return qbittorrentapi.Client(
        host=server_conf['host'],
        username=server_conf['username'],
        password=server_conf['password'],
        VERIFY_WEBUI_CERTIFICATE=False,
        REQUESTS_TIMEOUT=15
    )

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/servers', methods=['GET', 'POST'])
def handle_servers():
    if request.method == 'GET':
        return jsonify(load_config())
    if request.method == 'POST':
        data = request.json
        servers = load_config()
        # 去重：如果Host相同则更新密码
        for s in servers:
            if s['host'] == data['host']:
                s['username'] = data['username']
                s['password'] = data['password']
                save_config(servers)
                return jsonify({'success': True, 'msg': 'Updated'})
        
        servers.append({'host': data['host'], 'username': data['username'], 'password': data['password']})
        save_config(servers)
        return jsonify({'success': True})

@app.route('/api/servers/<int:idx>', methods=['DELETE'])
def delete_server(idx):
    servers = load_config()
    if 0 <= idx < len(servers):
        servers.pop(idx)
        save_config(servers)
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid index'}), 400

@app.route('/api/servers/<int:idx>/test', methods=['POST'])
def test_server(idx):
    servers = load_config()
    if not (0 <= idx < len(servers)): return jsonify({'success': False, 'error': 'Invalid index'})
    
    try:
        qb = get_client(servers[idx])
        qb.auth_log_in()
        return jsonify({'success': True, 'version': qb.app.version})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/distribute', methods=['POST'])
def distribute():
    servers = load_config()
    if not servers: return jsonify({'results': [], 'error': 'No nodes linked'})

    magnet = request.form.get('magnet')
    torrent_file = request.files.get('file')
    
    # 构建参数字典
    options = {
        'save_path': request.form.get('save_path') or None,
        'category': request.form.get('category') or None,
        'tags': request.form.get('tags') or None,
        'is_paused': request.form.get('paused') == 'true',
        'is_root_folder': request.form.get('root_folder') == 'true',
        'use_auto_torrent_management': request.form.get('auto_tmm') == 'true',
    }

    file_data = torrent_file.read() if torrent_file else None
    results = []

    def task(srv):
        res = {'server': srv['host'], 'success': False}
        try:
            qb = get_client(srv)
            qb.auth_log_in()
            if file_data: qb.torrents_add(torrent_files=file_data, **options)
            elif magnet: qb.torrents_add(urls=magnet, **options)
            else: raise Exception("No payload")
            res['success'] = True
        except Exception as e:
            res['error'] = str(e)
        results.append(res)

    threads = [threading.Thread(target=task, args=(s,)) for s in servers]
    for t in threads: t.start()
    for t in threads: t.join()

    return jsonify({'results': results})

if __name__ == '__main__':
    # 容器内部始终监听 5000，映射交给 Docker
    app.run(host='0.0.0.0', port=5000)