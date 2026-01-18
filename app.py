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

# --- 嵌入式 HTML 模板 (现代专业版) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qbit-Nexus | Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        bg: '#121212',
                        surface: '#1e1e1e',
                        surface2: '#252526',
                        primary: '#3b82f6',
                        accent: '#06b6d4',
                        text: '#e4e4e7',
                        muted: '#a1a1aa',
                        border: '#3f3f46'
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #121212; color: #e4e4e7; font-family: 'Inter', system-ui, sans-serif; }
        /* 自定义滚动条 */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #1e1e1e; }
        ::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #52525b; }
        
        .input-dark { 
            background-color: #27272a; 
            border: 1px solid #3f3f46; 
            color: white; 
            transition: all 0.2s; 
        }
        .input-dark:focus { 
            border-color: #3b82f6; 
            outline: none; 
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2); 
        }
        .toggle-checkbox:checked {
            right: 0;
            border-color: #3b82f6;
        }
        .toggle-checkbox:checked + .toggle-label {
            background-color: #3b82f6;
        }
        
        /* 拟态卡片 */
        .glass-panel {
            background: #1e1e1e;
            border: 1px solid #333;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
        }
    </style>
</head>
<body class="h-screen flex flex-col overflow-hidden">

<header class="h-14 border-b border-border bg-surface flex items-center justify-between px-6 z-10 shrink-0">
    <div class="flex items-center gap-3">
        <i class="fas fa-network-wired text-primary text-xl"></i>
        <h1 class="font-bold text-lg tracking-wide">Qbit-Nexus <span class="text-xs font-normal text-muted bg-surface2 px-2 py-0.5 rounded ml-2">Pro</span></h1>
    </div>
    <div class="flex items-center gap-4">
        <button onclick="openSettings()" class="text-muted hover:text-primary transition-colors flex items-center gap-2 text-sm bg-surface2 px-3 py-1.5 rounded border border-border">
            <i class="fas fa-cog"></i> 全局默认设置
        </button>
        <div class="h-4 w-[1px] bg-border"></div>
        <a href="https://github.com/agonie0v0/qbit-nexus" target="_blank" class="text-muted hover:text-white transition-colors">
            <i class="fab fa-github text-xl"></i>
        </a>
    </div>
</header>

<main class="flex-1 flex overflow-hidden">
    
    <aside class="w-80 border-r border-border bg-surface flex flex-col shrink-0">
        <div class="p-4 border-b border-border flex justify-between items-center">
            <span class="font-semibold text-sm text-muted uppercase tracking-wider">节点列表</span>
            <button onclick="toggleAddNodePanel()" class="text-primary hover:text-accent text-sm"><i class="fas fa-plus"></i> 添加</button>
        </div>
        
        <div id="addNodePanel" class="hidden p-4 bg-surface2 border-b border-border space-y-3">
            <input type="text" id="newHost" placeholder="地址 (http://IP:Port)" class="w-full input-dark rounded px-3 py-2 text-sm">
            <div class="flex gap-2">
                <input type="text" id="newUser" placeholder="用户名" class="w-1/2 input-dark rounded px-3 py-2 text-sm">
                <input type="password" id="newPass" placeholder="密码" class="w-1/2 input-dark rounded px-3 py-2 text-sm">
            </div>
            <button onclick="addServer()" class="w-full bg-primary hover:bg-blue-600 text-white font-medium py-1.5 rounded text-sm transition-colors">确认添加</button>
        </div>

        <div id="serverList" class="flex-1 overflow-y-auto p-2 space-y-2">
            </div>
    </aside>

    <section class="flex-1 flex flex-col bg-bg overflow-y-auto">
        <div class="max-w-5xl w-full mx-auto p-6 space-y-6">
            
            <div class="glass-panel rounded-lg p-5">
                <h2 class="text-lg font-medium mb-4 flex items-center gap-2 text-primary">
                    <i class="fas fa-file-import"></i> 任务来源
                </h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="space-y-2">
                        <label class="text-xs font-semibold text-muted uppercase">上传 Torrent 文件</label>
                        <div class="relative group">
                            <input type="file" id="torrentFile" accept=".torrent" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" onchange="updateFileName(this)">
                            <div class="input-dark rounded border border-dashed border-gray-600 p-8 text-center group-hover:border-primary transition-colors flex flex-col items-center justify-center gap-2">
                                <i class="fas fa-cloud-upload-alt text-2xl text-muted"></i>
                                <span id="fileNameDisplay" class="text-sm text-gray-400">拖拽文件或点击选择</span>
                            </div>
                        </div>
                    </div>
                    <div class="space-y-2">
                        <label class="text-xs font-semibold text-muted uppercase">或 粘贴 Magnet 链接</label>
                        <textarea id="magnetLink" placeholder="magnet:?xt=urn:btih:..." class="w-full h-[116px] input-dark rounded p-3 text-sm resize-none font-mono"></textarea>
                    </div>
                </div>
            </div>

            <div class="glass-panel rounded-lg p-5">
                <h2 class="text-lg font-medium mb-4 flex items-center gap-2 text-primary">
                    <i class="fas fa-sliders-h"></i> 任务选项
                </h2>
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-5">
                    
                    <div class="space-y-4">
                        <div>
                            <label class="block text-xs text-muted mb-1">保存路径 (Save Path)</label>
                            <input type="text" id="savePath" class="w-full input-dark rounded px-3 py-1.5 text-sm">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs text-muted mb-1">分类 (Category)</label>
                                <input type="text" id="category" class="w-full input-dark rounded px-3 py-1.5 text-sm">
                            </div>
                            <div>
                                <label class="block text-xs text-muted mb-1">标签 (Tags)</label>
                                <input type="text" id="tags" placeholder="tag1, tag2" class="w-full input-dark rounded px-3 py-1.5 text-sm">
                            </div>
                        </div>
                        
                        <div class="pt-2">
                            <label class="block text-xs text-muted mb-1">重命名 (可选)</label>
                            <input type="text" id="rename" placeholder="不修改则留空" class="w-full input-dark rounded px-3 py-1.5 text-sm">
                        </div>
                    </div>

                    <div class="space-y-4">
                         <div class="grid grid-cols-2 gap-4 bg-surface2 p-3 rounded border border-border">
                            <div>
                                <label class="block text-xs text-muted mb-1">下载限速 (KiB/s)</label>
                                <input type="number" id="limitDl" placeholder="无限制" class="w-full input-dark rounded px-3 py-1.5 text-sm">
                            </div>
                            <div>
                                <label class="block text-xs text-muted mb-1">上传限速 (KiB/s)</label>
                                <input type="number" id="limitUl" placeholder="无限制" class="w-full input-dark rounded px-3 py-1.5 text-sm">
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-2 text-sm pt-1">
                            <label class="flex items-center gap-2 cursor-pointer hover:text-white text-gray-400">
                                <input type="checkbox" id="paused" class="accent-primary w-4 h-4 rounded">
                                <span>添加后暂停</span>
                            </label>
                             <label class="flex items-center gap-2 cursor-pointer hover:text-white text-gray-400">
                                <input type="checkbox" id="skipHash" class="accent-primary w-4 h-4 rounded">
                                <span>跳过哈希校验</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer hover:text-white text-gray-400">
                                <input type="checkbox" id="rootFolder" class="accent-primary w-4 h-4 rounded">
                                <span>创建子目录</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer hover:text-white text-gray-400">
                                <input type="checkbox" id="autoTMM" class="accent-primary w-4 h-4 rounded">
                                <span>自动管理 (AutoTMM)</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer hover:text-white text-gray-400">
                                <input type="checkbox" id="sequential" class="accent-primary w-4 h-4 rounded">
                                <span>按顺序下载</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer hover:text-white text-gray-400">
                                <input type="checkbox" id="firstLast" class="accent-primary w-4 h-4 rounded">
                                <span>先下载首尾块</span>
                            </label>
                        </div>
                    </div>
                </div>
            </div>

            <div class="flex gap-4 items-start">
                 <button onclick="distributeTorrent()" class="flex-1 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold py-4 rounded shadow-lg transform active:scale-95 transition-all text-lg tracking-wide">
                    <i class="fas fa-paper-plane mr-2"></i> 开始分发任务
                </button>
            </div>
            
            <div class="glass-panel rounded-lg flex flex-col h-48">
                <div class="p-2 border-b border-border bg-surface2 flex justify-between items-center px-4">
                    <span class="text-xs font-mono text-muted">SYSTEM_LOG</span>
                    <button onclick="document.getElementById('consoleLog').innerHTML=''" class="text-xs hover:text-white text-muted">Clear</button>
                </div>
                <div id="consoleLog" class="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-1 text-gray-400 bg-black">
                    <div class="text-green-500">System Ready...</div>
                </div>
            </div>
        </div>
    </section>
</main>

<div id="settingsModal" class="fixed inset-0 bg-black/80 z-50 hidden flex items-center justify-center backdrop-blur-sm">
    <div class="bg-surface border border-border rounded-lg w-full max-w-2xl shadow-2xl transform transition-all scale-100 p-0 overflow-hidden">
        <div class="bg-surface2 p-4 border-b border-border flex justify-between items-center">
            <h3 class="font-bold text-white"><i class="fas fa-cog text-primary mr-2"></i> 全局默认配置</h3>
            <button onclick="closeSettings()" class="text-muted hover:text-white"><i class="fas fa-times"></i></button>
        </div>
        <div class="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
            <p class="text-xs text-muted bg-blue-900/20 border border-blue-900/50 p-3 rounded">
                <i class="fas fa-info-circle mr-1"></i> 这里设置的值将作为每次打开页面时的默认值。
            </p>

            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-xs text-muted mb-1">默认保存路径</label>
                    <input type="text" id="def_savePath" class="w-full input-dark rounded px-3 py-2 text-sm">
                </div>
                <div>
                    <label class="block text-xs text-muted mb-1">默认分类</label>
                    <input type="text" id="def_category" class="w-full input-dark rounded px-3 py-2 text-sm">
                </div>
                <div>
                    <label class="block text-xs text-muted mb-1">默认标签</label>
                    <input type="text" id="def_tags" class="w-full input-dark rounded px-3 py-2 text-sm">
                </div>
                <div>
                    <label class="block text-xs text-muted mb-1">默认上传限速 (KiB/s)</label>
                    <input type="number" id="def_limitUl" class="w-full input-dark rounded px-3 py-2 text-sm">
                </div>
            </div>

            <div class="space-y-3 pt-2">
                <span class="text-xs font-bold text-muted uppercase block border-b border-border pb-1">默认开关状态</span>
                <div class="grid grid-cols-3 gap-3">
                    <label class="flex items-center gap-2 cursor-pointer text-sm text-gray-300">
                        <input type="checkbox" id="def_rootFolder" class="accent-primary"> 创建子目录
                    </label>
                    <label class="flex items-center gap-2 cursor-pointer text-sm text-gray-300">
                        <input type="checkbox" id="def_autoTMM" class="accent-primary"> AutoTMM
                    </label>
                    <label class="flex items-center gap-2 cursor-pointer text-sm text-gray-300">
                        <input type="checkbox" id="def_paused" class="accent-primary"> 暂停添加
                    </label>
                     <label class="flex items-center gap-2 cursor-pointer text-sm text-gray-300">
                        <input type="checkbox" id="def_skipHash" class="accent-primary"> 跳过哈希校验
                    </label>
                </div>
            </div>
        </div>
        <div class="p-4 bg-surface2 border-t border-border flex justify-end gap-3">
            <button onclick="closeSettings()" class="px-4 py-2 rounded text-sm text-gray-400 hover:text-white">取消</button>
            <button onclick="saveSettings()" class="px-6 py-2 rounded text-sm bg-primary hover:bg-blue-600 text-white font-medium">保存配置</button>
        </div>
    </div>
</div>

<script>
    // --- State & Helpers ---
    let serverCount = 0;

    function log(msg, type='info') {
        const box = document.getElementById('consoleLog');
        const time = new Date().toLocaleTimeString('en-US', {hour12: false});
        let color = 'text-gray-400';
        if(type === 'success') color = 'text-green-400';
        if(type === 'error') color = 'text-red-400';
        
        box.innerHTML += `<div class="${color} font-mono border-l-2 border-transparent pl-2 hover:bg-white/5"><span class="opacity-50">[${time}]</span> ${msg}</div>`;
        box.scrollTop = box.scrollHeight;
    }

    function updateFileName(input) {
        const display = document.getElementById('fileNameDisplay');
        if (input.files && input.files[0]) {
            display.innerHTML = `<span class="text-white font-medium">${input.files[0].name}</span>`;
            display.parentElement.classList.add('border-primary', 'bg-blue-900/10');
        } else {
            display.innerHTML = '拖拽文件或点击选择';
            display.parentElement.classList.remove('border-primary', 'bg-blue-900/10');
        }
    }

    function toggleAddNodePanel() {
        const panel = document.getElementById('addNodePanel');
        panel.classList.toggle('hidden');
    }

    // --- API Calls ---

    async function loadServers() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();
            const servers = data.servers || [];
            const defaults = data.defaults || {};

            // Render Servers
            const container = document.getElementById('serverList');
            container.innerHTML = '';
            
            if(servers.length === 0) {
                container.innerHTML = '<div class="text-muted text-center text-xs py-8 opacity-50">暂无节点</div>';
            } else {
                servers.forEach((s, idx) => {
                    const div = document.createElement('div');
                    div.className = 'group flex justify-between items-center bg-surface2 p-3 rounded border border-transparent hover:border-primary transition-all cursor-default';
                    div.innerHTML = `
                        <div class="overflow-hidden">
                            <div class="font-bold text-xs text-gray-300 group-hover:text-white truncate"><i class="fas fa-server mr-2 text-muted"></i>${s.host}</div>
                            <div class="text-[10px] text-gray-600 pl-5">${s.username}</div>
                        </div>
                        <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onclick="testServer(${idx})" class="text-xs bg-black/50 hover:bg-primary hover:text-white text-muted p-1.5 rounded"><i class="fas fa-plug"></i></button>
                            <button onclick="removeServer(${idx})" class="text-xs bg-black/50 hover:bg-red-600 hover:text-white text-muted p-1.5 rounded"><i class="fas fa-trash"></i></button>
                        </div>
                    `;
                    container.appendChild(div);
                });
            }

            // Apply Defaults ONLY if form is empty (simple check)
            if(!document.getElementById('savePath').value) {
                document.getElementById('savePath').value = defaults.savePath || '';
                document.getElementById('category').value = defaults.category || '';
                document.getElementById('tags').value = defaults.tags || '';
                document.getElementById('limitUl').value = defaults.limitUl || '';
                document.getElementById('limitDl').value = defaults.limitDl || '';
                
                document.getElementById('rootFolder').checked = defaults.rootFolder !== false; // Default true
                document.getElementById('autoTMM').checked = defaults.autoTMM === true;
                document.getElementById('paused').checked = defaults.paused === true;
                document.getElementById('skipHash').checked = defaults.skipHash === true;
            }

        } catch(e) { console.error(e); }
    }

    async function addServer() {
        const host = document.getElementById('newHost').value.trim();
        const username = document.getElementById('newUser').value.trim();
        const password = document.getElementById('newPass').value.trim();
        if(!host || !username) return alert("Host and Username required");

        await fetch('/api/servers', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ host, username, password })
        });
        
        document.getElementById('newHost').value = '';
        document.getElementById('newUser').value = '';
        document.getElementById('newPass').value = '';
        toggleAddNodePanel();
        loadServers();
        log(`添加节点: ${host}`, 'success');
    }

    async function removeServer(idx) {
        if(!confirm("确认删除该节点?")) return;
        await fetch(`/api/servers/${idx}`, { method: 'DELETE' });
        loadServers();
    }
    
    async function testServer(idx) {
        log(`正在连接节点 #${idx+1}...`);
        const res = await fetch(`/api/servers/${idx}/test`, { method: 'POST' });
        const data = await res.json();
        if(data.success) log(`[OK] 节点 #${idx+1} 连接成功 (v${data.version})`, 'success');
        else log(`[Error] 节点 #${idx+1} 连接失败: ${data.error}`, 'error');
    }

    // --- Settings Modal Logic ---
    async function openSettings() {
        const res = await fetch('/api/config');
        const data = await res.json();
        const d = data.defaults || {};

        document.getElementById('def_savePath').value = d.savePath || '';
        document.getElementById('def_category').value = d.category || '';
        document.getElementById('def_tags').value = d.tags || '';
        document.getElementById('def_limitUl').value = d.limitUl || '';
        
        document.getElementById('def_rootFolder').checked = d.rootFolder !== false;
        document.getElementById('def_autoTMM').checked = d.autoTMM === true;
        document.getElementById('def_paused').checked = d.paused === true;
        document.getElementById('def_skipHash').checked = d.skipHash === true;

        document.getElementById('settingsModal').classList.remove('hidden');
    }

    function closeSettings() {
        document.getElementById('settingsModal').classList.add('hidden');
    }

    async function saveSettings() {
        const defaults = {
            savePath: document.getElementById('def_savePath').value,
            category: document.getElementById('def_category').value,
            tags: document.getElementById('def_tags').value,
            limitUl: document.getElementById('def_limitUl').value,
            rootFolder: document.getElementById('def_rootFolder').checked,
            autoTMM: document.getElementById('def_autoTMM').checked,
            paused: document.getElementById('def_paused').checked,
            skipHash: document.getElementById('def_skipHash').checked
        };

        await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(defaults)
        });
        
        closeSettings();
        log('全局默认配置已保存', 'success');
        // Reload to apply defaults to current fields if empty
        window.location.reload(); 
    }

    // --- Distribution Logic ---
    async function distributeTorrent() {
        const fileInput = document.getElementById('torrentFile');
        const magnet = document.getElementById('magnetLink').value.trim();
        
        if (!fileInput.files[0] && !magnet) return alert("请选择种子文件或输入磁力链接");

        const formData = new FormData();
        if (fileInput.files[0]) formData.append('file', fileInput.files[0]);
        if (magnet) formData.append('magnet', magnet);

        // Map basic fields
        formData.append('save_path', document.getElementById('savePath').value.trim());
        formData.append('category', document.getElementById('category').value.trim());
        formData.append('tags', document.getElementById('tags').value.trim());
        formData.append('rename', document.getElementById('rename').value.trim());
        
        // Map Limits (Convert KiB to Bytes later or pass raw) - We pass raw int here
        formData.append('up_limit', document.getElementById('limitUl').value);
        formData.append('dl_limit', document.getElementById('limitDl').value);

        // Map Booleans
        formData.append('paused', document.getElementById('paused').checked);
        formData.append('root_folder', document.getElementById('rootFolder').checked);
        formData.append('auto_tmm', document.getElementById('autoTMM').checked);
        formData.append('skip_hash', document.getElementById('skipHash').checked);
        formData.append('sequential', document.getElementById('sequential').checked);
        formData.append('first_last', document.getElementById('firstLast').checked);

        log(">>> 开始任务分发...", 'info');

        try {
            const res = await fetch('/api/distribute', { method: 'POST', body: formData });
            const result = await res.json();
            
            result.results.forEach(r => {
                if(r.success) log(`[发送成功] -> ${r.server}`, 'success');
                else log(`[发送失败] -> ${r.server}: ${r.error}`, 'error');
            });
            
            if(result.results.every(r => r.success)) log(">>> 所有节点分发完成。", 'success');

        } catch (e) {
            log("系统错误: " + e.message, 'error');
        }
    }

    // Init
    loadServers();

</script>
</body>
</html>
"""

# --- 后端逻辑 ---

def load_data_file():
    if not os.path.exists(CONFIG_FILE): return {"servers": [], "defaults": {}}
    try:
        with open(CONFIG_FILE, 'r') as f: 
            data = json.load(f)
            if isinstance(data, list): # 兼容旧版格式
                return {"servers": data, "defaults": {}}
            return data
    except: return {"servers": [], "defaults": {}}

def save_data_file(data):
    with open(CONFIG_FILE, 'w') as f: json.dump(data, f, indent=4)

def get_client(server_conf):
    return qbittorrentapi.Client(
        host=server_conf['host'],
        username=server_conf['username'],
        password=server_conf['password'],
        VERIFY_WEBUI_CERTIFICATE=False,
        REQUESTS_TIMEOUT=20
    )

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

# --- 统一配置接口 (Server List + Defaults) ---
@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_data_file())

@app.route('/api/settings', methods=['POST'])
def save_settings():
    new_defaults = request.json
    data = load_data_file()
    data['defaults'] = new_defaults
    save_data_file(data)
    return jsonify({'success': True})

# --- Server Management ---
@app.route('/api/servers', methods=['POST'])
def add_server():
    req = request.json
    data = load_data_file()
    
    # Update if exists, else add
    found = False
    for s in data['servers']:
        if s['host'] == req['host']:
            s['username'] = req['username']
            s['password'] = req['password']
            found = True
            break
    if not found:
        data['servers'].append(req)
    
    save_data_file(data)
    return jsonify({'success': True})

@app.route('/api/servers/<int:idx>', methods=['DELETE'])
def delete_server(idx):
    data = load_data_file()
    if 0 <= idx < len(data['servers']):
        data['servers'].pop(idx)
        save_data_file(data)
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid index'}), 400

@app.route('/api/servers/<int:idx>/test', methods=['POST'])
def test_server(idx):
    data = load_data_file()
    servers = data['servers']
    if not (0 <= idx < len(servers)): return jsonify({'success': False, 'error': 'Invalid index'})
    
    try:
        qb = get_client(servers[idx])
        qb.auth_log_in()
        return jsonify({'success': True, 'version': qb.app.version})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# --- 核心分发逻辑 (增强版) ---
@app.route('/api/distribute', methods=['POST'])
def distribute():
    data = load_data_file()
    servers = data['servers']
    if not servers: return jsonify({'results': [], 'error': 'No nodes linked'})

    magnet = request.form.get('magnet')
    torrent_file = request.files.get('file')
    
    # 处理限速单位: 输入为 KiB/s -> API 需要 Bytes/s
    def get_limit_bytes(key):
        val = request.form.get(key)
        if val and val.isdigit():
            return int(val) * 1024
        return None

    # 构建 qBittorrent API 参数
    # 参考: https://qbittorrent-api.readthedocs.io/en/latest/modules/torrents.html#qbittorrentapi.torrents.Torrents.add
    options = {
        'save_path': request.form.get('save_path') or None,
        'category': request.form.get('category') or None,
        'tags': request.form.get('tags') or None,
        'rename': request.form.get('rename') or None,
        
        # Boolean Flags
        'is_paused': request.form.get('paused') == 'true',
        'is_root_folder': request.form.get('root_folder') == 'true', # Create Subfolder
        'use_auto_torrent_management': request.form.get('auto_tmm') == 'true',
        'is_sequential_download': request.form.get('sequential') == 'true',
        'is_first_last_piece_priority': request.form.get('first_last') == 'true',
        'is_skip_checking': request.form.get('skip_hash') == 'true',
        
        # Limits
        'up_limit': get_limit_bytes('up_limit'),
        'dl_limit': get_limit_bytes('dl_limit'),
    }

    # 移除 None 值的参数，避免覆盖默认值
    options = {k: v for k, v in options.items() if v is not None}

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
    app.run(host='0.0.0.0', port=5000)
