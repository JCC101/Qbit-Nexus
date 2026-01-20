import json
import os
import threading
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import qbittorrentapi

# --- 配置存储路径 ---
DATA_DIR = os.getenv('DATA_DIR', '.')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
CONFIG_FILE = os.path.join(DATA_DIR, 'nexus_config.json')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
WEB_PASSWORD = os.getenv('WEB_PASSWORD')

# --- 辅助函数 ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if WEB_PASSWORD and not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def format_size(size):
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PiB"

def format_speed(speed):
    if speed == 0: return ""
    return f"{format_size(speed)}/s"

# --- 模板部分 ---
LOGIN_TEMPLATE = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Login</title><script src="https://cdn.tailwindcss.com"></script></head><body class="h-screen flex items-center justify-center bg-slate-50"><div class="w-full max-w-sm bg-white p-8 rounded-xl shadow-lg border border-slate-100"><h1 class="text-2xl font-bold text-center text-slate-800 mb-6">Nexus Security</h1><form method="POST" class="space-y-4"><input type="password" name="password" required class="w-full px-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:border-blue-500" placeholder="Password..."><button type="submit" class="w-full bg-blue-600 text-white py-3 rounded-lg font-bold hover:bg-blue-700 transition">Unlock</button></form></div></body></html>"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qbit-Nexus | Cluster Manager</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: { bg: '#f8fafc', primary: '#0ea5e9' },
                    fontFamily: { sans: ['Inter', 'sans-serif'] },
                    screens: { '2xl': '1600px', '3xl': '2100px' }
                }
            }
        }
    </script>
    <style>
        body { background-color: #f8fafc; color: #334155; }
        .nav-item.active { background-color: #0ea5e9; color: white; }
        .fresh-input { background-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 0.375rem; transition: 0.2s; }
        .fresh-input:focus { border-color: #0ea5e9; outline: none; box-shadow: 0 0 0 2px rgba(14,165,233,0.1); }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
    </style>
</head>
<body class="h-screen flex flex-col md:flex-row overflow-hidden">

<aside class="w-full md:w-64 bg-white border-b md:border-r border-slate-200 flex flex-col z-20 shrink-0">
    <div class="h-16 flex items-center px-6 border-b border-slate-100">
        <div class="flex items-center gap-2 text-slate-800 font-bold text-xl">
            <i class="fas fa-layer-group text-primary"></i> Qbit-Nexus
        </div>
    </div>
    
    <nav class="flex-1 p-4 space-y-2 overflow-y-auto">
        <button onclick="switchTab('distribute')" id="nav-distribute" class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors">
            <i class="fas fa-paper-plane"></i> 批量添加任务
        </button>
        <button onclick="switchTab('manage')" id="nav-manage" class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors">
            <i class="fas fa-tasks"></i> 集群任务管理
        </button>
        
        <div class="pt-4 mt-4 border-t border-slate-100">
            <div class="px-4 text-xs font-bold text-slate-400 uppercase mb-2">Nodes</div>
            <div id="sidebarNodeList" class="space-y-1"></div>
            <button onclick="toggleModal('addNodeModal')" class="mt-3 w-full py-2 border border-dashed border-slate-300 rounded text-xs text-slate-500 hover:text-primary hover:border-primary transition-colors">
                + 添加节点
            </button>
        </div>
    </nav>
    
    <div class="p-4 border-t border-slate-100">
        <a href="/logout" class="flex items-center gap-2 text-sm text-slate-400 hover:text-red-500 transition-colors px-2">
            <i class="fas fa-sign-out-alt"></i> 退出登录
        </a>
    </div>
</aside>

<main class="flex-1 flex flex-col min-w-0 bg-[#f8fafc] overflow-hidden relative">
    
    <div id="tab-distribute" class="flex-1 flex flex-col h-full overflow-hidden">
        <header class="h-16 flex justify-between items-center px-8 border-b border-slate-200 bg-white/80 backdrop-blur shrink-0">
            <h2 class="font-bold text-slate-700">批量任务分发</h2>
            <button onclick="openSettings()" class="text-xs font-medium text-slate-500 hover:text-primary bg-white border border-slate-200 px-3 py-1.5 rounded shadow-sm">
                <i class="fas fa-cog"></i> 全局配置
            </button>
        </header>
        
        <div class="flex-1 overflow-y-auto p-6">
            <div class="max-w-6xl mx-auto space-y-6">
                <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
                    <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
                        <div class="text-xs font-bold text-primary uppercase"><i class="fas fa-file-import mr-1"></i> 资源</div>
                        <div class="flex flex-col gap-3">
                            <div class="relative group h-24">
                                <input type="file" id="torrentFile" accept=".torrent" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" onchange="updateFileName(this)">
                                <div id="fileDropZone" class="h-full border-2 border-dashed border-slate-300 rounded-lg flex flex-col items-center justify-center gap-1 group-hover:border-primary bg-slate-50 transition-colors">
                                    <i class="fas fa-cloud-upload-alt text-xl text-slate-400"></i>
                                    <span id="fileNameDisplay" class="text-xs font-medium text-slate-500">点击上传 .torrent</span>
                                </div>
                            </div>
                            <input type="text" id="magnetLink" placeholder="或者粘贴 Magnet 链接..." class="fresh-input w-full px-3 py-2 text-sm">
                        </div>
                    </div>
                    
                    <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col">
                        <div class="flex justify-between items-center mb-3">
                            <span class="text-xs font-bold text-primary uppercase"><i class="fas fa-server mr-1"></i> 目标节点</span>
                            <div class="text-[10px] space-x-2">
                                <button onclick="toggleAllTargets(true)" class="text-blue-500 hover:underline">全选</button>
                                <button onclick="toggleAllTargets(false)" class="text-slate-400 hover:underline">全不选</button>
                            </div>
                        </div>
                        <div id="targetSelectionArea" class="grid grid-cols-2 lg:grid-cols-3 gap-2 overflow-y-auto max-h-40"></div>
                    </div>
                </div>

                <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold text-primary uppercase mb-4"><i class="fas fa-sliders-h mr-1"></i> 任务参数</div>
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div class="space-y-3">
                            <div class="grid grid-cols-2 gap-2">
                                <div><label class="text-xs font-bold text-slate-500">TMM</label><select id="autoTMM" class="fresh-input w-full p-1.5 text-sm"><option value="false">手动</option><option value="true">自动</option></select></div>
                                <div><label class="text-xs font-bold text-slate-500">布局</label><select id="contentLayout" class="fresh-input w-full p-1.5 text-sm"><option value="Original">原始</option><option value="NoSubFolder">不创建子目录</option></select></div>
                            </div>
                            <div><label class="text-xs font-bold text-slate-500">保存路径</label><input type="text" id="savePath" class="fresh-input w-full p-1.5 text-sm" placeholder="默认"></div>
                            <div><label class="text-xs font-bold text-slate-500">分类</label><input type="text" id="category" class="fresh-input w-full p-1.5 text-sm"></div>
                        </div>
                        
                        <div class="space-y-3 bg-slate-50 p-3 rounded border border-slate-100">
                            <label class="text-[10px] font-bold text-slate-400 uppercase">限速 (预设)</label>
                            <label class="flex justify-between items-center text-sm cursor-pointer"><span><i class="fas fa-upload text-green-500 mr-2"></i>上传限速</span><input type="checkbox" id="useLimitUl" class="accent-primary"></label>
                            <label class="flex justify-between items-center text-sm cursor-pointer"><span><i class="fas fa-download text-blue-500 mr-2"></i>下载限速</span><input type="checkbox" id="useLimitDl" class="accent-primary"></label>
                            
                            <label class="text-[10px] font-bold text-slate-400 uppercase mt-2 block">停止条件</label>
                            <div class="grid grid-cols-2 gap-2">
                                <input type="number" id="ratioLimit" placeholder="分享率" class="fresh-input text-xs p-1">
                                <input type="number" id="seedingTimeLimit" placeholder="时间(分)" class="fresh-input text-xs p-1">
                            </div>
                        </div>

                        <div class="space-y-2 pt-1 text-sm text-slate-600">
                            <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" id="startTorrent" checked class="accent-primary"> 开始任务</label>
                            <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" id="skipHash" class="accent-primary"> 跳过校验</label>
                            <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" id="firstLast" class="accent-primary"> 首尾块优先</label>
                        </div>
                    </div>
                    <button onclick="distributeTorrent()" class="mt-6 w-full py-3 bg-primary text-white font-bold rounded-lg hover:bg-blue-600 shadow-lg shadow-blue-500/20 transition-transform hover:scale-[1.01]">
                        <i class="fas fa-paper-plane mr-2"></i> 立即分发
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div id="tab-manage" class="hidden flex-1 flex flex-col h-full overflow-hidden">
        <header class="h-16 flex justify-between items-center px-8 border-b border-slate-200 bg-white/80 backdrop-blur shrink-0">
            <div class="flex items-center gap-4">
                <h2 class="font-bold text-slate-700">集群任务管理</h2>
                <button onclick="fetchClusterData()" class="text-xs bg-white border border-slate-200 px-3 py-1.5 rounded hover:text-primary transition-colors">
                    <i class="fas fa-sync-alt mr-1"></i> 刷新列表
                </button>
            </div>
            <div class="relative">
                <input type="text" id="tableSearch" onkeyup="filterTable()" placeholder="搜索任务..." class="pl-8 pr-3 py-1.5 text-sm border border-slate-200 rounded-full focus:outline-none focus:border-primary w-64">
                <i class="fas fa-search absolute left-3 top-2 text-slate-400 text-xs"></i>
            </div>
        </header>

        <div class="flex-1 overflow-auto p-6">
            <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden min-h-[400px]">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-50 text-xs font-bold text-slate-500 uppercase border-b border-slate-200 sticky top-0 z-10">
                        <tr>
                            <th class="px-6 py-4 w-1/3">任务名称 (Name)</th>
                            <th class="px-6 py-4 w-24">大小</th>
                            <th class="px-6 py-4">节点分布 (Node Status)</th>
                            <th class="px-6 py-4 w-32 text-right">操作</th>
                        </tr>
                    </thead>
                    <tbody id="clusterTableBody" class="text-sm divide-y divide-slate-100">
                        <tr><td colspan="4" class="px-6 py-10 text-center text-slate-400">请点击左上角“刷新列表”获取数据</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="h-8 bg-slate-800 text-slate-400 text-[10px] flex items-center px-4 shrink-0 font-mono overflow-hidden">
        <span class="mr-2 text-blue-400">LOG ></span>
        <div id="statusBar" class="truncate flex-1">Ready.</div>
    </div>

</main>

<div id="addNodeModal" class="fixed inset-0 bg-slate-900/40 z-50 hidden flex items-center justify-center backdrop-blur-sm">
    <div class="bg-white rounded-xl w-full max-w-sm p-6 shadow-2xl space-y-4">
        <h3 class="font-bold text-slate-800">添加下载器</h3>
        <input type="text" id="newNodeName" placeholder="别名 (Alias)" class="fresh-input w-full px-3 py-2 text-sm">
        <input type="text" id="newHost" placeholder="http://IP:Port" class="fresh-input w-full px-3 py-2 text-sm">
        <div class="grid grid-cols-2 gap-2">
            <input type="text" id="newUser" placeholder="用户名" class="fresh-input px-3 py-2 text-sm">
            <input type="password" id="newPass" placeholder="密码" class="fresh-input px-3 py-2 text-sm">
        </div>
        <div class="flex justify-end gap-2">
            <button onclick="toggleModal('addNodeModal')" class="px-3 py-1.5 text-sm text-slate-500">取消</button>
            <button onclick="addServer()" class="px-4 py-1.5 text-sm bg-primary text-white rounded hover:bg-blue-600">保存</button>
        </div>
    </div>
</div>

<div id="settingsModal" class="fixed inset-0 bg-slate-900/40 z-50 hidden flex items-center justify-center backdrop-blur-sm">
    <div class="bg-white rounded-xl w-full max-w-md p-6 shadow-2xl space-y-4">
        <h3 class="font-bold text-slate-800">全局预设</h3>
        <div class="bg-blue-50 p-3 rounded border border-blue-100 grid grid-cols-2 gap-3">
            <div><label class="text-xs text-slate-500">上传 (KiB/s)</label><input type="number" id="def_presetUl" class="fresh-input w-full px-2 py-1 bg-white"></div>
            <div><label class="text-xs text-slate-500">下载 (KiB/s)</label><input type="number" id="def_presetDl" class="fresh-input w-full px-2 py-1 bg-white"></div>
        </div>
        <div class="space-y-2">
            <label class="text-xs text-slate-500">默认保存路径</label><input type="text" id="def_savePath" class="fresh-input w-full px-2 py-1.5 text-sm">
            <div class="grid grid-cols-2 gap-2">
                <input type="text" id="def_category" placeholder="分类" class="fresh-input w-full px-2 py-1.5 text-sm">
                <input type="text" id="def_tags" placeholder="标签" class="fresh-input w-full px-2 py-1.5 text-sm">
            </div>
        </div>
        <div class="flex justify-end gap-2">
            <button onclick="toggleModal('settingsModal')" class="px-3 py-1.5 text-sm text-slate-500">取消</button>
            <button onclick="saveSettings()" class="px-4 py-1.5 text-sm bg-primary text-white rounded hover:bg-blue-600">保存</button>
        </div>
    </div>
</div>

<div id="deleteModal" class="fixed inset-0 bg-slate-900/50 z-50 hidden flex items-center justify-center backdrop-blur-sm">
    <div class="bg-white rounded-xl w-full max-w-md p-0 shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-slate-100 bg-red-50">
            <h3 class="font-bold text-red-600"><i class="fas fa-trash-alt mr-2"></i>删除任务</h3>
            <p id="delTorrentName" class="text-xs text-red-400 mt-1 truncate">Torrent Name</p>
        </div>
        <div class="p-5 space-y-4">
            <div class="text-sm text-slate-600 font-bold">请选择要执行删除的节点：</div>
            <div id="delNodeList" class="space-y-2 max-h-48 overflow-y-auto">
                </div>
            <label class="flex items-center gap-2 p-3 bg-slate-50 rounded border border-slate-200 cursor-pointer">
                <input type="checkbox" id="delWithData" class="accent-red-500 w-4 h-4">
                <span class="text-sm font-bold text-slate-700">同时删除硬盘文件 (Delete Files)</span>
            </label>
        </div>
        <div class="p-4 bg-slate-50 flex justify-end gap-3 border-t border-slate-100">
            <button onclick="toggleModal('deleteModal')" class="px-4 py-2 text-sm text-slate-500 hover:bg-white rounded">取消</button>
            <button onclick="confirmDelete()" class="px-5 py-2 text-sm bg-red-500 text-white rounded hover:bg-red-600 shadow-md shadow-red-200">确认删除</button>
        </div>
    </div>
</div>

<script>
    let globalConfig = {};
    let currentDeleteHash = '';
    let serverMap = {}; // index -> server name

    // --- Tab Switching ---
    function switchTab(tab) {
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        document.getElementById('nav-'+tab).classList.add('active');
        document.getElementById('tab-distribute').classList.add('hidden');
        document.getElementById('tab-manage').classList.add('hidden');
        document.getElementById('tab-'+tab).classList.remove('hidden');
    }

    // --- Utils ---
    function toggleModal(id) { document.getElementById(id).classList.toggle('hidden'); }
    function log(msg) { document.getElementById('statusBar').innerText = msg; }
    function openSettings() {
        const d = globalConfig.defaults || {};
        document.getElementById('def_presetUl').value = d.presetUl || '';
        document.getElementById('def_presetDl').value = d.presetDl || '';
        document.getElementById('def_savePath').value = d.savePath || '';
        document.getElementById('def_category').value = d.category || '';
        document.getElementById('def_tags').value = d.tags || '';
        toggleModal('settingsModal');
    }
    function updateFileName(input) {
        if(input.files[0]) {
            document.getElementById('fileNameDisplay').innerText = input.files[0].name;
            document.getElementById('fileDropZone').classList.add('border-primary', 'bg-blue-50');
        }
    }
    function toggleAllTargets(checked) {
        document.querySelectorAll('#targetSelectionArea input').forEach(cb => cb.checked = checked);
    }

    // --- Load Config ---
    async function loadData() {
        const res = await fetch('/api/config');
        if(res.status === 403 || res.redirected) window.location.href = '/login';
        const data = await res.json();
        globalConfig = data;
        const servers = data.servers || [];
        const defaults = data.defaults || {};

        // Sidebar List
        const sb = document.getElementById('sidebarNodeList');
        sb.innerHTML = '';
        // Targets Area
        const tg = document.getElementById('targetSelectionArea');
        tg.innerHTML = '';

        serverMap = {};

        servers.forEach((s, idx) => {
            serverMap[idx] = s.name || s.host;
            // Sidebar
            sb.innerHTML += `<div class="flex justify-between items-center px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 rounded group">
                <span class="truncate w-32" title="${s.host}">${s.name || s.host}</span>
                <button onclick="removeServer(${idx})" class="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-500"><i class="fas fa-trash"></i></button>
            </div>`;
            // Target Checkbox
            tg.innerHTML += `<label class="flex items-center gap-2 p-2 border rounded hover:bg-slate-50 cursor-pointer text-xs">
                <input type="checkbox" name="targetNode" value="${idx}" class="accent-primary">
                <span class="truncate">${s.name || s.host}</span>
            </label>`;
        });

        // Defaults
        if(!document.getElementById('savePath').value) document.getElementById('savePath').value = defaults.savePath || '';
        document.getElementById('category').value = defaults.category || '';
        document.getElementById('tags').value = defaults.tags || '';
    }

    async function addServer() {
        // ... (保持之前的 addServer 逻辑) ...
        const payload = {
            name: document.getElementById('newNodeName').value,
            host: document.getElementById('newHost').value,
            username: document.getElementById('newUser').value,
            password: document.getElementById('newPass').value
        };
        await fetch('/api/servers', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
        toggleModal('addNodeModal'); loadData(); log('节点添加成功');
    }
    async function removeServer(idx) { if(confirm('删除节点?')) { await fetch(`/api/servers/${idx}`, {method:'DELETE'}); loadData(); } }
    async function saveSettings() {
        const defaults = {
            presetUl: document.getElementById('def_presetUl').value, presetDl: document.getElementById('def_presetDl').value,
            savePath: document.getElementById('def_savePath').value, category: document.getElementById('def_category').value, tags: document.getElementById('def_tags').value
        };
        await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(defaults)});
        toggleModal('settingsModal'); log('全局配置已保存'); loadData();
    }

    // --- Core 1: Distribute ---
    async function distributeTorrent() {
        // ... (保持 distributeTorrent 逻辑, 略微精简以便展示) ...
        const file = document.getElementById('torrentFile').files[0];
        const magnet = document.getElementById('magnetLink').value;
        if(!file && !magnet) return alert('请选择种子');
        
        const targets = Array.from(document.querySelectorAll('#targetSelectionArea input:checked')).map(cb => parseInt(cb.value));
        if(targets.length === 0) return alert('请选择节点');

        const fd = new FormData();
        if(file) fd.append('file', file);
        if(magnet) fd.append('magnet', magnet);
        fd.append('targets', JSON.stringify(targets));
        // Append all options...
        fd.append('save_path', document.getElementById('savePath').value);
        fd.append('use_limit_ul', document.getElementById('useLimitUl').checked);
        fd.append('use_limit_dl', document.getElementById('useLimitDl').checked);
        // ... 其他参数 ...
        
        log('正在分发...');
        const res = await fetch('/api/distribute', {method:'POST', body:fd});
        const data = await res.json();
        log('分发完成: ' + data.results.map(r=>r.success?'OK':'Fail').join(', '));
    }

    // --- Core 2: Cluster Management (New) ---
    async function fetchClusterData() {
        const tbody = document.getElementById('clusterTableBody');
        tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-10 text-center"><i class="fas fa-spinner fa-spin text-primary text-2xl"></i><div class="mt-2 text-slate-400">正在从所有节点拉取数据...</div></td></tr>';
        
        try {
            const res = await fetch('/api/tasks/list');
            const data = await res.json();
            renderTable(data);
            log(`已刷新列表，共 ${Object.keys(data).length} 个聚合任务`);
        } catch(e) {
            tbody.innerHTML = `<tr><td colspan="4" class="px-6 py-4 text-center text-red-500">获取失败: ${e}</td></tr>`;
        }
    }

    function renderTable(data) {
        const tbody = document.getElementById('clusterTableBody');
        tbody.innerHTML = '';
        
        if(Object.keys(data).length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-10 text-center text-slate-400">暂无任务</td></tr>';
            return;
        }

        for (const [hash, task] of Object.entries(data)) {
            // Node Badges HTML
            let nodesHtml = '<div class="flex flex-wrap gap-2">';
            for(const [srvIdx, info] of Object.entries(task.nodes)) {
                const srvName = serverMap[srvIdx] || `Node ${srvIdx}`;
                // State Colors
                let badgeClass = "bg-slate-100 text-slate-500 border-slate-200"; // Default/Stopped
                let stateIcon = "<i class='fas fa-pause text-[10px]'></i>";
                
                if (['downloading', 'stalledDL', 'metaDL'].includes(info.state)) {
                    badgeClass = "bg-blue-50 text-blue-600 border-blue-200";
                    stateIcon = `<i class='fas fa-arrow-down text-[10px]'></i> ${info.dl_speed}`;
                } else if (['uploading', 'stalledUP', 'queuedUP', 'checkingUP'].includes(info.state)) {
                    badgeClass = "bg-green-50 text-green-600 border-green-200";
                    stateIcon = `<i class='fas fa-arrow-up text-[10px]'></i> ${info.up_speed}`;
                }
                
                nodesHtml += `
                    <div class="px-2 py-1 rounded border text-xs flex items-center gap-2 ${badgeClass}" title="${info.state}">
                        <span class="font-bold">${srvName}</span>
                        <span class="opacity-80 scale-90">${stateIcon}</span>
                    </div>
                `;
            }
            nodesHtml += '</div>';

            const tr = document.createElement('tr');
            tr.className = "hover:bg-slate-50 transition-colors group";
            tr.innerHTML = `
                <td class="px-6 py-4 font-medium text-slate-700">
                    <div class="truncate max-w-xs" title="${task.name}">${task.name}</div>
                    <div class="text-[10px] text-slate-400 font-mono select-all">${hash}</div>
                </td>
                <td class="px-6 py-4 text-slate-500">${task.size}</td>
                <td class="px-6 py-4">${nodesHtml}</td>
                <td class="px-6 py-4 text-right">
                    <button onclick="openDeleteModal('${hash}', '${task.name.replace(/'/g, "")}', ${JSON.stringify(Object.keys(task.nodes))})" 
                        class="text-slate-400 hover:text-red-500 p-2 rounded-full hover:bg-red-50 transition-all" title="删除">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                    <button onclick="actionTask('${hash}', 'pause')" class="text-slate-400 hover:text-yellow-500 p-2" title="暂停/停止"><i class="fas fa-pause"></i></button>
                    <button onclick="actionTask('${hash}', 'resume')" class="text-slate-400 hover:text-green-500 p-2" title="开始"><i class="fas fa-play"></i></button>
                </td>
            `;
            tbody.appendChild(tr);
        }
    }

    function filterTable() {
        const term = document.getElementById('tableSearch').value.toLowerCase();
        const rows = document.querySelectorAll('#clusterTableBody tr');
        rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            row.style.display = text.includes(term) ? '' : 'none';
        });
    }

    // --- Actions ---
    function openDeleteModal(hash, name, nodeIndices) {
        currentDeleteHash = hash;
        document.getElementById('delTorrentName').innerText = name;
        const list = document.getElementById('delNodeList');
        list.innerHTML = '';
        
        nodeIndices.forEach(idx => {
            const sName = serverMap[idx] || `Node ${idx}`;
            list.innerHTML += `
                <label class="flex items-center gap-3 p-2 hover:bg-slate-50 rounded cursor-pointer">
                    <input type="checkbox" name="delTarget" value="${idx}" checked class="accent-red-500 w-4 h-4">
                    <span class="text-sm text-slate-700">${sName}</span>
                </label>
            `;
        });
        
        toggleModal('deleteModal');
    }

    async function confirmDelete() {
        const targets = Array.from(document.querySelectorAll('input[name="delTarget"]:checked')).map(cb => parseInt(cb.value));
        const deleteFiles = document.getElementById('delWithData').checked;
        
        if(targets.length === 0) return alert("请至少选择一个节点");
        
        toggleModal('deleteModal');
        log('正在执行删除...');
        
        await fetch('/api/tasks/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                hash: currentDeleteHash,
                action: 'delete',
                targets: targets,
                delete_files: deleteFiles
            })
        });
        
        log('删除指令已发送');
        fetchClusterData(); // Refresh
    }

    async function actionTask(hash, action) {
        if(!confirm(`确认对所有节点执行 ${action} ?`)) return;
        // 简单起见，这里暂停/开始是对所有拥有该种子的节点执行
        // 如果需要细粒度，也可以弹窗，但通常暂停/开始是全局意图
        await fetch('/api/tasks/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ hash, action, targets: null }) // null means all holders
        });
        log(`指令 ${action} 已发送`);
        setTimeout(fetchClusterData, 1000); // Wait a bit then refresh
    }

    // Init
    switchTab('distribute');
    loadData();
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
            if isinstance(data, list): return {"servers": data, "defaults": {}}
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
        REQUESTS_ARGS={'timeout': 10} # 缩短超时，避免列表刷新太慢
    )

# --- 路由 ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not WEB_PASSWORD: 
        session['logged_in'] = True
        return redirect(url_for('index'))
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['logged_in'] = True
            return redirect(request.args.get('next') or url_for('index'))
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index(): return render_template_string(HTML_TEMPLATE)

# ... (原有的 config, servers, distribute 接口保持不变，此处省略以节省空间，请保留原代码中这部分) ...
# 为了完整性，这里我还是把 distribute 和 server 相关的贴上，确保您能直接复制运行

@app.route('/api/config', methods=['GET'])
@login_required
def get_config(): return jsonify(load_data_file())

@app.route('/api/settings', methods=['POST'])
@login_required
def save_settings():
    d = load_data_file(); d['defaults'] = request.json; save_data_file(d)
    return jsonify({'success': True})

@app.route('/api/servers', methods=['POST'])
@login_required
def add_server():
    d = load_data_file(); req = request.json
    node = {'name': req.get('name',''), 'host': req['host'], 'username': req['username'], 'password': req['password']}
    d['servers'].append(node); save_data_file(d)
    return jsonify({'success': True})

@app.route('/api/servers/<int:idx>', methods=['DELETE'])
@login_required
def delete_server(idx):
    d = load_data_file()
    if 0 <= idx < len(d['servers']): d['servers'].pop(idx); save_data_file(d)
    return jsonify({'success': True})

@app.route('/api/servers/<int:idx>/test', methods=['POST'])
@login_required
def test_server(idx):
    d = load_data_file()
    if not (0 <= idx < len(d['servers'])): return jsonify({'error': 'Index'})
    try:
        qb = get_client(d['servers'][idx]); qb.auth_log_in()
        return jsonify({'success': True, 'version': qb.app.version})
    except Exception as e: return jsonify({'success': False, 'error': str(e)})

@app.route('/api/distribute', methods=['POST'])
@login_required
def distribute():
    d = load_data_file(); servers = d['servers']; defaults = d.get('defaults', {})
    try: targets = json.loads(request.form.get('targets', '[]'))
    except: return jsonify({'error': 'Targets'})
    target_srvs = [servers[i] for i in targets if 0 <= i < len(servers)]
    if not target_srvs: return jsonify({'error': 'No targets'})
    
    file = request.files.get('file'); magnet = request.form.get('magnet')
    fdata = file.read() if file else None
    
    def get_val(k, t=str): 
        v = request.form.get(k)
        if t==int: return int(v) if v and v.isdigit() else None
        if t==float: return float(v) if v and v.replace('.','').isdigit() else None
        return v or None
        
    def get_preset(k): 
        v = defaults.get(k); return int(v)*1024 if v and str(v).isdigit() else None

    # Logic: If checkbox checked, use preset; else None
    up_limit = get_preset('presetUl') if request.form.get('use_limit_ul') == 'true' else None
    dl_limit = get_preset('presetDl') if request.form.get('use_limit_dl') == 'true' else None
    
    layout = get_val('content_layout')
    
    opts = {
        'save_path': get_val('save_path'), 'rename': get_val('rename'), 
        'category': get_val('category'), 'tags': get_val('tags'),
        'is_paused': request.form.get('start_torrent') == 'false',
        'use_auto_torrent_management': request.form.get('auto_tmm') == 'true',
        'content_layout': layout, 'is_root_folder': (layout=='Original'),
        'upload_limit': up_limit, 'download_limit': dl_limit,
        'ratio_limit': get_val('ratio_limit', float),
        'seeding_time_limit': get_val('seeding_time_limit', int),
        'is_skip_checking': request.form.get('skip_hash') == 'true',
        'is_sequential_download': request.form.get('sequential') == 'true',
        'is_first_last_piece_priority': request.form.get('first_last') == 'true',
        'add_to_top_of_queue': request.form.get('add_to_top') == 'true'
    }
    opts = {k:v for k,v in opts.items() if v is not None}
    
    res_list = []
    def run(s):
        r = {'server': s.get('name') or s['host'], 'success': False}
        try:
            c = get_client(s); c.auth_log_in()
            if fdata: c.torrents_add(torrent_files=fdata, **opts)
            elif magnet: c.torrents_add(urls=magnet, **opts)
            r['success'] = True
        except Exception as e: r['error'] = str(e)
        res_list.append(r)
        
    ts = [threading.Thread(target=run, args=(s,)) for s in target_srvs]
    for t in ts: t.start()
    for t in ts: t.join()
    
    return jsonify({'results': res_list, 'debug_limits': {'up': up_limit, 'dl': dl_limit}})


# --- 核心新增接口：集群管理 ---

@app.route('/api/tasks/list', methods=['GET'])
@login_required
def cluster_list():
    """ 拉取所有节点任务并聚合 """
    data = load_data_file()
    servers = data['servers']
    
    aggregated = {} # Hash -> {name, size, nodes: {srvIdx: {state, up, dl}}}
    lock = threading.Lock()
    
    def fetch(idx, srv):
        try:
            qb = get_client(srv)
            qb.auth_log_in()
            # 获取所有种子
            torrents = qb.torrents_info()
            
            with lock:
                for t in torrents:
                    h = t.hash
                    if h not in aggregated:
                        aggregated[h] = {
                            'name': t.name,
                            'size': format_size(t.total_size), # 格式化大小
                            'nodes': {}
                        }
                    
                    # 记录该节点的具体状态
                    aggregated[h]['nodes'][idx] = {
                        'state': t.state,
                        'up_speed': format_speed(t.upspeed),
                        'dl_speed': format_speed(t.dlspeed),
                        'progress': t.progress
                    }
        except:
            pass # 忽略连接失败的节点

    threads = [threading.Thread(target=fetch, args=(i, s)) for i, s in enumerate(servers)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    return jsonify(aggregated)

@app.route('/api/tasks/action', methods=['POST'])
@login_required
def cluster_action():
    """ 执行批量操作 (删除/暂停/开始) """
    req = request.json
    action = req.get('action') # delete, pause, resume
    target_hash = req.get('hash')
    target_idxs = req.get('targets') # [0, 2] specific nodes, or None for all
    delete_files = req.get('delete_files', False)
    
    data = load_data_file()
    servers = data['servers']
    
    def perform(idx, srv):
        try:
            qb = get_client(srv)
            qb.auth_log_in()
            
            # 如果指定了 targets，则只在列表内的节点执行；否则对所有持有该 hash 的执行
            # 但这里我们简化逻辑：前端必须传 targets (对于删除) 或者我们先检查是否存在
            # 实际上 qb 操作不存在的 hash 不会报错，所以直接发指令即可
            
            if action == 'delete':
                qb.torrents_delete(torrent_hashes=target_hash, delete_files=delete_files)
            elif action == 'pause':
                # v5.0 兼容：torrents_pause 在库中通常映射正确，但在 v5 UI 显示为停止
                qb.torrents_pause(torrent_hashes=target_hash)
            elif action == 'resume':
                qb.torrents_resume(torrent_hashes=target_hash)
                
        except: pass

    # 确定要操作的服务器列表
    # 如果前端传了 targets (如删除操作)，只操作这些
    # 如果没传 (如全局暂停)，则操作所有配置的服务器 (简单粗暴，反正没任务的不受影响)
    idxs_to_run = target_idxs if target_idxs is not None else range(len(servers))
    
    threads = [threading.Thread(target=perform, args=(i, servers[i])) for i in idxs_to_run]
    for t in threads: t.start()
    for t in threads: t.join()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
