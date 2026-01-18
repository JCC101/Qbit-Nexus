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

# --- 嵌入式 HTML 模板 (v3.2 - 隐私保护 + 界面去重) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qbit-Nexus | Pro Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        bg: '#f8fafc', surface: '#ffffff', border: '#e2e8f0',
                        primary: '#0ea5e9', primary_hover: '#0284c7',
                        text: '#334155', muted: '#94a3b8'
                    },
                    fontFamily: { sans: ['Inter', 'sans-serif'] },
                    boxShadow: { 'soft': '0 4px 20px -2px rgba(0, 0, 0, 0.05)' }
                }
            }
        }
    </script>
    <style>
        body { background-color: #f8fafc; color: #334155; font-family: 'Inter', sans-serif; }
        .fresh-card { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02); }
        .fresh-input { background-color: #f1f5f9; border: 1px solid #e2e8f0; color: #334155; transition: all 0.2s; border-radius: 0.5rem; }
        .fresh-input:focus { background-color: #ffffff; border-color: #0ea5e9; outline: none; box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1); }
        .fresh-label { display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; margin-bottom: 0.25rem; }
        .section-title { font-size: 0.85rem; font-weight: 700; color: #0ea5e9; text-transform: uppercase; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
        .check-item { display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; color: #475569; cursor: pointer; user-select: none; }
        .check-item input { accent-color: #0ea5e9; width: 1rem; height: 1rem; border-radius: 4px; }
        .fresh-btn { background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%); color: white; border-radius: 0.5rem; transition: all 0.2s; box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.2); }
        .fresh-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 10px -1px rgba(59, 130, 246, 0.3); }
        .status-dot { height: 8px; width: 8px; border-radius: 50%; display: inline-block; }
        .status-online { background-color: #10b981; box-shadow: 0 0 8px rgba(16, 185, 129, 0.4); }
        .status-offline { background-color: #ef4444; }
        .status-pending { background-color: #cbd5e1; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
    </style>
</head>
<body class="h-screen flex overflow-hidden">

<aside class="w-72 bg-surface border-r border-border flex flex-col z-20 shadow-sm">
    <div class="h-16 flex items-center px-6 border-b border-border">
        <div class="flex items-center gap-2">
            <div class="w-7 h-7 rounded bg-primary flex items-center justify-center text-white"><i class="fas fa-bolt text-xs"></i></div>
            <h1 class="font-bold text-lg text-slate-800">Qbit-Nexus</h1>
        </div>
    </div>
    <div class="flex-1 overflow-y-auto p-4 space-y-2" id="serverList"></div>
    <div class="p-4 border-t border-border bg-slate-50">
        <button onclick="toggleModal('addNodeModal')" class="w-full py-2 rounded-lg border border-dashed border-slate-300 text-slate-500 text-sm hover:border-primary hover:text-primary transition-all">
            <i class="fas fa-plus mr-2"></i> 添加下载器
        </button>
    </div>
</aside>

<main class="flex-1 flex flex-col min-w-0 bg-bg">
    <header class="h-16 flex justify-between items-center px-8 border-b border-border bg-surface/50 backdrop-blur sticky top-0 z-10">
        <h2 class="font-bold text-slate-700">全网分发任务</h2>
        <button onclick="openSettings()" class="text-xs font-medium text-slate-500 hover:text-primary flex items-center gap-1 bg-white border border-slate-200 px-3 py-1.5 rounded shadow-sm">
            <i class="fas fa-cog"></i> 全局限速与默认值
        </button>
    </header>

    <div class="flex-1 overflow-y-auto p-6">
        <div class="max-w-6xl mx-auto space-y-6">
            
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="lg:col-span-2 fresh-card p-5 space-y-4">
                    <div class="section-title"><i class="fas fa-file-import"></i> 资源选择 (Payload)</div>
                    <div class="grid grid-cols-1 gap-4">
                        <div class="relative group">
                            <input type="file" id="torrentFile" accept=".torrent" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" onchange="updateFileName(this)">
                            <div id="fileDropZone" class="h-24 border-2 border-dashed border-slate-200 rounded-lg flex flex-col items-center justify-center gap-1 group-hover:border-primary group-hover:bg-blue-50 transition-all">
                                <span id="fileNameDisplay" class="text-sm font-medium text-slate-500">点击上传 .torrent 文件</span>
                            </div>
                        </div>
                        <div class="relative">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400"><i class="fas fa-magnet"></i></div>
                            <input type="text" id="magnetLink" placeholder="或者在此粘贴 Magnet 磁力链接..." class="pl-9 w-full fresh-input py-2 text-sm">
                        </div>
                    </div>
                </div>

                <div class="lg:col-span-1 fresh-card p-5 flex flex-col">
                    <div class="section-title"><i class="fas fa-server"></i> 目标节点 (Targets)</div>
                    <div id="targetSelectionArea" class="flex-1 overflow-y-auto space-y-2 max-h-40 pr-1">
                        <div class="text-xs text-slate-400 text-center py-4">正在加载...</div>
                    </div>
                </div>
            </div>

            <div class="fresh-card p-6">
                <div class="section-title"><i class="fas fa-sliders-h"></i> 任务选项 (Options)</div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-6">
                    
                    <div class="lg:col-span-5 space-y-4 border-r border-slate-100 lg:pr-6">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="fresh-label">管理模式 (TMM)</label>
                                <select id="autoTMM" class="w-full fresh-input px-3 py-2 text-sm">
                                    <option value="false">手动 (Manual)</option>
                                    <option value="true">自动 (Automatic)</option>
                                </select>
                            </div>
                            <div>
                                <label class="fresh-label">内容布局</label>
                                <select id="contentLayout" class="w-full fresh-input px-3 py-2 text-sm">
                                    <option value="Original">原始</option>
                                    <option value="Subfolder">创建子目录</option>
                                    <option value="NoSubFolder">不创建子目录</option>
                                </select>
                            </div>
                        </div>

                        <div><label class="fresh-label">保存路径 (Save Path)</label><input type="text" id="savePath" class="w-full fresh-input px-3 py-2 text-sm" placeholder="默认路径..."></div>
                        <div><label class="fresh-label">重命名 (可选)</label><input type="text" id="rename" class="w-full fresh-input px-3 py-2 text-sm" placeholder="保持原名则留空"></div>

                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="fresh-label">分类 (Category)</label><input type="text" id="category" class="w-full fresh-input px-3 py-2 text-sm"></div>
                            <div><label class="fresh-label">标签 (Tags)</label><input type="text" id="tags" class="w-full fresh-input px-3 py-2 text-sm"></div>
                        </div>
                    </div>

                    <div class="lg:col-span-4 space-y-4 border-r border-slate-100 lg:pr-6 lg:pl-2">
                        <div class="space-y-3 bg-slate-50 p-3 rounded-lg border border-slate-100">
                            <div class="flex justify-between items-center mb-1">
                                <label class="text-xs font-bold text-slate-400 uppercase">速度限制 (Use Presets)</label>
                            </div>
                            
                            <label class="flex items-center justify-between cursor-pointer group p-1.5 hover:bg-white rounded transition-colors">
                                <div class="flex items-center gap-2">
                                    <div class="w-6 h-6 rounded bg-green-100 text-green-600 flex items-center justify-center text-[10px]"><i class="fas fa-upload"></i></div>
                                    <div><span class="text-xs font-medium text-slate-700 block">启用上传限速</span><span id="limitUlDisplay" class="text-[10px] text-slate-400">未配置</span></div>
                                </div>
                                <input type="checkbox" id="useLimitUl" class="accent-primary w-4 h-4 rounded">
                            </label>

                            <label class="flex items-center justify-between cursor-pointer group p-1.5 hover:bg-white rounded transition-colors">
                                <div class="flex items-center gap-2">
                                    <div class="w-6 h-6 rounded bg-blue-100 text-blue-600 flex items-center justify-center text-[10px]"><i class="fas fa-download"></i></div>
                                    <div><span class="text-xs font-medium text-slate-700 block">启用下载限速</span><span id="limitDlDisplay" class="text-[10px] text-slate-400">未配置</span></div>
                                </div>
                                <input type="checkbox" id="useLimitDl" class="accent-primary w-4 h-4 rounded">
                            </label>
                        </div>

                        <div class="space-y-3 pt-1">
                            <label class="text-xs font-bold text-slate-400 uppercase">停止条件 (Stop Condition)</label>
                            <div class="grid grid-cols-2 gap-3">
                                <div><label class="fresh-label">最大分享率</label><input type="number" id="ratioLimit" class="w-full fresh-input px-2 py-1.5 text-sm" placeholder="无"></div>
                                <div><label class="fresh-label">做种时间(分钟)</label><input type="number" id="seedingTimeLimit" class="w-full fresh-input px-2 py-1.5 text-sm" placeholder="无"></div>
                            </div>
                        </div>
                    </div>

                    <div class="lg:col-span-3 space-y-3 lg:pl-2 pt-1">
                        <label class="text-xs font-bold text-slate-400 uppercase mb-2 block">高级选项</label>
                        <div class="flex flex-col gap-3">
                            <label class="check-item"><input type="checkbox" id="startTorrent" checked> <span>开始 Torrent</span></label>
                            <label class="check-item"><input type="checkbox" id="addToTop"> <span>添加到队列顶部</span></label>
                            <label class="check-item"><input type="checkbox" id="skipHash"> <span>跳过哈希校验</span></label>
                            <label class="check-item"><input type="checkbox" id="sequential"> <span>按顺序下载</span></label>
                            <label class="check-item"><input type="checkbox" id="firstLast"> <span>先下载首尾文件块</span></label>
                        </div>
                    </div>
                </div>

                <div class="mt-8 border-t border-slate-100 pt-6">
                    <button onclick="distributeTorrent()" class="fresh-btn w-full py-3 font-bold text-sm tracking-wide flex justify-center items-center gap-2">
                        <i class="fas fa-paper-plane"></i> 立即分发任务
                    </button>
                </div>
            </div>

            <div class="bg-white border border-slate-200 rounded-lg p-2 flex flex-col h-32 shadow-sm">
                <div class="px-2 pb-2 flex justify-between items-center border-b border-slate-50">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">System Log</span>
                    <button onclick="document.getElementById('consoleLog').innerHTML=''" class="text-[10px] text-slate-400 hover:text-primary">Clear</button>
                </div>
                <div id="consoleLog" class="flex-1 overflow-y-auto p-2 font-mono text-[11px] space-y-1 text-slate-600">
                    <div class="text-primary"><i class="fas fa-check-circle mr-1"></i>System initialized.</div>
                </div>
            </div>
        </div>
    </div>
</main>

<div id="addNodeModal" class="fixed inset-0 bg-slate-900/20 z-50 hidden flex items-center justify-center backdrop-blur-sm">
    <div class="bg-white rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-4">
        <h3 class="font-bold text-lg text-slate-800">添加下载器</h3>
        <input type="text" id="newNodeName" placeholder="名称 (Alias)" class="w-full fresh-input px-3 py-2 text-sm">
        <input type="text" id="newHost" placeholder="地址 (http://IP:Port)" class="w-full fresh-input px-3 py-2 text-sm">
        <div class="grid grid-cols-2 gap-3">
            <input type="text" id="newUser" placeholder="用户名" class="w-full fresh-input px-3 py-2 text-sm">
            <input type="password" id="newPass" placeholder="密码" class="w-full fresh-input px-3 py-2 text-sm">
        </div>
        <div class="flex justify-end gap-3">
            <button onclick="toggleModal('addNodeModal')" class="px-4 py-2 text-sm text-slate-500 hover:bg-slate-50 rounded">取消</button>
            <button onclick="addServer()" class="px-5 py-2 text-sm bg-primary text-white rounded hover:bg-blue-600">保存</button>
        </div>
    </div>
</div>

<div id="settingsModal" class="fixed inset-0 bg-slate-900/20 z-50 hidden flex items-center justify-center backdrop-blur-sm">
    <div class="bg-white rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-5">
        <h3 class="font-bold text-slate-800 border-b border-slate-100 pb-2">全局配置 & 预设 (Defaults)</h3>
        
        <div class="bg-blue-50/50 p-4 rounded border border-blue-100">
            <label class="text-xs font-bold text-primary uppercase mb-2 block">限速预设值 (Presets)</label>
            <div class="grid grid-cols-2 gap-4">
                <div><label class="fresh-label">上传限速 (KiB/s)</label><input type="number" id="def_presetUl" class="w-full fresh-input px-3 py-2 text-sm bg-white" placeholder="20480"></div>
                <div><label class="fresh-label">下载限速 (KiB/s)</label><input type="number" id="def_presetDl" class="w-full fresh-input px-3 py-2 text-sm bg-white"></div>
            </div>
        </div>
        
        <div class="space-y-3">
            <label class="text-xs font-bold text-slate-400 uppercase block">表单默认值</label>
            <div><label class="fresh-label">默认保存路径</label><input type="text" id="def_savePath" class="w-full fresh-input px-3 py-2 text-sm"></div>
            <div class="grid grid-cols-2 gap-4">
                <div><label class="fresh-label">默认分类</label><input type="text" id="def_category" class="w-full fresh-input px-3 py-2 text-sm"></div>
                <div><label class="fresh-label">默认标签</label><input type="text" id="def_tags" class="w-full fresh-input px-3 py-2 text-sm"></div>
            </div>
        </div>

        <div class="flex justify-end gap-3 pt-2">
            <button onclick="toggleModal('settingsModal')" class="px-4 py-2 text-sm text-slate-500">取消</button>
            <button onclick="saveSettings()" class="px-5 py-2 text-sm bg-primary text-white rounded hover:bg-blue-600">保存配置</button>
        </div>
    </div>
</div>

<script>
    let globalConfig = {};

    function toggleModal(id) { document.getElementById(id).classList.toggle('hidden'); }
    function openSettings() {
        const d = globalConfig.defaults || {};
        document.getElementById('def_presetUl').value = d.presetUl || '';
        document.getElementById('def_presetDl').value = d.presetDl || '';
        document.getElementById('def_savePath').value = d.savePath || '';
        document.getElementById('def_category').value = d.category || '';
        document.getElementById('def_tags').value = d.tags || '';
        toggleModal('settingsModal');
    }

    // --- 脱敏辅助函数 ---
    function maskUrl(urlStr) {
        try {
            // 简单处理 http://1.2.3.4:8080 -> http://1.***.***.4:8080
            return urlStr.replace(/(\d{1,3}\.)\d{1,3}\.\d{1,3}(\.\d{1,3})/, '$1***.***$2');
        } catch(e) { return '******'; }
    }

    function log(msg, type='info') {
        const box = document.getElementById('consoleLog');
        const time = new Date().toLocaleTimeString('en-US', {hour12: false});
        let color = 'text-slate-600'; let icon = '<i class="fas fa-info-circle text-xs mr-1 opacity-50"></i>';
        if(type === 'success') { color = 'text-emerald-600'; icon = '<i class="fas fa-check text-xs mr-1"></i>'; }
        if(type === 'error') { color = 'text-red-500'; icon = '<i class="fas fa-times text-xs mr-1"></i>'; }
        box.innerHTML += `<div class="${color} flex items-center"><span class="opacity-40 text-[10px] mr-2 font-normal">${time}</span>${icon}<span>${msg}</span></div>`;
        box.scrollTop = box.scrollHeight;
    }

    function updateFileName(input) {
        const display = document.getElementById('fileNameDisplay');
        const zone = document.getElementById('fileDropZone');
        if (input.files && input.files[0]) {
            display.innerText = input.files[0].name; display.className = "text-xs font-bold text-primary"; zone.classList.add('border-primary', 'bg-blue-50');
        } else {
            display.innerText = '点击上传 .torrent 文件'; display.className = "text-xs font-medium text-slate-500"; zone.classList.remove('border-primary', 'bg-blue-50');
        }
    }

    async function loadData() {
        const res = await fetch('/api/config');
        const data = await res.json();
        globalConfig = data;
        const servers = data.servers || [];
        const defaults = data.defaults || {};

        // 1. Sidebar Nodes
        const container = document.getElementById('serverList');
        container.innerHTML = '';
        const targetContainer = document.getElementById('targetSelectionArea');
        targetContainer.innerHTML = '';
        
        if(servers.length === 0) {
            container.innerHTML = '<div class="text-center py-6 text-xs text-muted">暂无节点</div>';
            targetContainer.innerHTML = '<div class="text-xs text-muted text-center py-4">请先添加节点</div>';
        }

        servers.forEach((s, idx) => {
            const displayName = s.name || s.host; 
            const safeHost = maskUrl(s.host); // 使用脱敏后的地址

            // Sidebar Item
            const div = document.createElement('div');
            div.className = 'bg-white border border-slate-100 p-2 rounded hover:border-primary/50 transition-all mb-2 flex justify-between items-center group';
            div.innerHTML = `
                <div class="overflow-hidden pr-2">
                    <div class="font-bold text-xs text-slate-700 truncate">${displayName}</div>
                    <div class="text-[10px] text-slate-400 truncate font-mono">${safeHost}</div>
                </div>
                <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onclick="removeServer(${idx})" class="text-slate-400 hover:text-red-500"><i class="fas fa-trash text-xs"></i></button>
                    <div id="status-${idx}" class="status-dot status-pending"></div>
                </div>
            `;
            container.appendChild(div);

            // Target Checkbox
            const label = document.createElement('label');
            label.className = "flex items-center gap-2 p-2 border border-slate-100 rounded hover:bg-blue-50 cursor-pointer bg-slate-50/50";
            label.innerHTML = `
                <input type="checkbox" name="targetNode" value="${idx}" checked>
                <span class="text-xs font-bold text-slate-600 truncate" title="${displayName}">${displayName}</span>
            `;
            targetContainer.appendChild(label);
            setTimeout(() => testServer(idx, true), idx * 200 + 300);
        });

        // 2. Fill Form Defaults
        if(!document.getElementById('savePath').value) document.getElementById('savePath').value = defaults.savePath || '';
        document.getElementById('category').value = defaults.category || '';
        document.getElementById('tags').value = defaults.tags || '';
        
        // 3. Update Preset Display
        document.getElementById('limitUlDisplay').innerText = defaults.presetUl ? `${defaults.presetUl} KiB/s` : '未配置';
        document.getElementById('limitDlDisplay').innerText = defaults.presetDl ? `${defaults.presetDl} KiB/s` : '未配置';
    }

    async function addServer() {
        const name = document.getElementById('newNodeName').value.trim();
        const host = document.getElementById('newHost').value.trim();
        const username = document.getElementById('newUser').value.trim();
        const password = document.getElementById('newPass').value.trim();
        if(!host || !username) return alert("地址和用户名必填");
        await fetch('/api/servers', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ name, host, username, password }) });
        document.getElementById('newNodeName').value = ''; document.getElementById('newHost').value = ''; document.getElementById('newUser').value = ''; document.getElementById('newPass').value = '';
        toggleModal('addNodeModal'); loadData(); log(`节点已保存: ${name || host}`, 'success');
    }

    async function removeServer(idx) { if(!confirm("确认移除?")) return; await fetch(`/api/servers/${idx}`, { method: 'DELETE' }); loadData(); }

    async function testServer(idx, silent=false) {
        const indicator = document.getElementById(`status-${idx}`);
        try {
            const res = await fetch(`/api/servers/${idx}/test`, { method: 'POST' });
            const data = await res.json();
            if(indicator) indicator.className = data.success ? "status-dot status-online" : "status-dot status-offline";
            if(!silent) log(data.success ? `Node #${idx+1} Online` : `Connect Fail: ${data.error}`, data.success?'success':'error');
        } catch(e) { if(indicator) indicator.className = "status-dot status-offline"; }
    }

    async function saveSettings() {
        const defaults = {
            presetUl: document.getElementById('def_presetUl').value, presetDl: document.getElementById('def_presetDl').value,
            savePath: document.getElementById('def_savePath').value, category: document.getElementById('def_category').value, tags: document.getElementById('def_tags').value,
        };
        await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(defaults) });
        toggleModal('settingsModal'); log('全局配置已更新', 'success'); loadData();
    }

    async function distributeTorrent() {
        const fileInput = document.getElementById('torrentFile');
        const magnet = document.getElementById('magnetLink').value.trim();
        if (!fileInput.files[0] && !magnet) return alert("请上传种子或输入磁力链");

        const selectedNodes = Array.from(document.querySelectorAll('input[name="targetNode"]:checked')).map(cb => parseInt(cb.value));
        if(selectedNodes.length === 0) return alert("请至少选择一个目标节点！");

        const formData = new FormData();
        if (fileInput.files[0]) formData.append('file', fileInput.files[0]);
        if (magnet) formData.append('magnet', magnet);

        formData.append('targets', JSON.stringify(selectedNodes));
        
        // Native Options Mapping
        formData.append('auto_tmm', document.getElementById('autoTMM').value); // 'true'/'false'
        formData.append('content_layout', document.getElementById('contentLayout').value);
        formData.append('save_path', document.getElementById('savePath').value.trim());
        formData.append('rename', document.getElementById('rename').value.trim());
        formData.append('category', document.getElementById('category').value.trim());
        formData.append('tags', document.getElementById('tags').value.trim());
        
        // Limits (From Checkbox -> Preset)
        formData.append('use_limit_ul', document.getElementById('useLimitUl').checked);
        formData.append('use_limit_dl', document.getElementById('useLimitDl').checked);
        
        // Stop Condition
        formData.append('ratio_limit', document.getElementById('ratioLimit').value);
        formData.append('seeding_time_limit', document.getElementById('seedingTimeLimit').value);

        // Booleans
        formData.append('start_torrent', document.getElementById('startTorrent').checked);
        formData.append('add_to_top', document.getElementById('addToTop').checked);
        formData.append('skip_hash', document.getElementById('skipHash').checked);
        formData.append('sequential', document.getElementById('sequential').checked);
        formData.append('first_last', document.getElementById('firstLast').checked);

        log(`>>> 开始分发至 ${selectedNodes.length} 个节点...`, 'info');

        try {
            const res = await fetch('/api/distribute', { method: 'POST', body: formData });
            const result = await res.json();
            
             // 显示调试信息
            if(result.debug_limits) {
               if(result.debug_limits.up) log(`[调试] 上传限速: ${result.debug_limits.up} Bytes/s`);
            }

            result.results.forEach(r => {
                const sName = r.name || r.server; 
                log(r.success ? `[成功] -> ${sName}` : `[失败] -> ${sName}: ${r.error}`, r.success?'success':'error');
            });
            if(result.results.every(r => r.success)) log(">>> 任务分发完成", 'success');
        } catch (e) { log("System Error: " + e.message, 'error'); }
    }

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
        REQUESTS_ARGS={'timeout': 15}
    )

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/config', methods=['GET'])
def get_config(): return jsonify(load_data_file())

@app.route('/api/settings', methods=['POST'])
def save_settings():
    new_defaults = request.json
    data = load_data_file()
    data['defaults'] = new_defaults
    save_data_file(data)
    return jsonify({'success': True})

@app.route('/api/servers', methods=['POST'])
def add_server():
    req = request.json
    data = load_data_file()
    new_node = {'name': req.get('name', ''), 'host': req['host'], 'username': req['username'], 'password': req['password']}
    found = False
    for s in data['servers']:
        if s['host'] == req['host']:
            s.update(new_node); found = True; break
    if not found: data['servers'].append(new_node)
    save_data_file(data)
    return jsonify({'success': True})

@app.route('/api/servers/<int:idx>', methods=['DELETE'])
def delete_server(idx):
    data = load_data_file()
    if 0 <= idx < len(data['servers']):
        data['servers'].pop(idx); save_data_file(data)
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
    except Exception as e: return jsonify({'success': False, 'error': str(e)})

@app.route('/api/distribute', methods=['POST'])
def distribute():
    data = load_data_file()
    all_servers = data['servers']
    defaults = data.get('defaults', {})
    
    if not all_servers: return jsonify({'results': [], 'error': 'No nodes linked'})

    try:
        target_indices = json.loads(request.form.get('targets', '[]'))
        target_servers = [all_servers[i] for i in target_indices if 0 <= i < len(all_servers)]
    except: return jsonify({'results': [], 'error': 'Invalid targets'})

    if not target_servers: return jsonify({'results': [], 'error': 'No targets selected'})

    magnet = request.form.get('magnet')
    torrent_file = request.files.get('file')
    
    # --- 参数解析与转换 ---
    def get_float(key):
        val = request.form.get(key)
        return float(val) if val and val.replace('.','',1).isdigit() else None
        
    def get_int(key): 
        val = request.form.get(key)
        return int(val) if val and val.isdigit() else None
    
    # 核心修改：从预设读取限速
    def get_preset_bytes(key):
        val = defaults.get(key)
        if val and str(val).isdigit(): return int(val) * 1024
        return None

    up_limit = get_preset_bytes('presetUl') if request.form.get('use_limit_ul') == 'true' else None
    dl_limit = get_preset_bytes('presetDl') if request.form.get('use_limit_dl') == 'true' else None
    
    layout_val = request.form.get('content_layout', 'Original')

    options = {
        'save_path': request.form.get('save_path') or None,
        'rename': request.form.get('rename') or None,
        'category': request.form.get('category') or None,
        'tags': request.form.get('tags') or None,
        
        # 核心布尔值
        'is_paused': request.form.get('start_torrent') == 'false', # 反转逻辑：勾选开始=不暂停
        'use_auto_torrent_management': request.form.get('auto_tmm') == 'true',
        
        # 布局
        'content_layout': layout_val,
        'is_root_folder': (layout_val == 'Original'),
        
        # 限制 (来自预设)
        'upload_limit': up_limit,
        'download_limit': dl_limit,
        'ratio_limit': get_float('ratio_limit'),
        'seeding_time_limit': get_int('seeding_time_limit'), # 分钟
        
        # 高级选项
        'is_skip_checking': request.form.get('skip_hash') == 'true',
        'is_sequential_download': request.form.get('sequential') == 'true',
        'is_first_last_piece_priority': request.form.get('first_last') == 'true',
        'add_to_top_of_queue': request.form.get('add_to_top') == 'true'
    }
    
    # 清理 None 值
    options = {k: v for k, v in options.items() if v is not None}

    file_data = torrent_file.read() if torrent_file else None
    results = []

    def task(srv):
        res = {'server': srv['host'], 'name': srv.get('name', ''), 'success': False}
        try:
            qb = get_client(srv)
            qb.auth_log_in()
            if file_data: qb.torrents_add(torrent_files=file_data, **options)
            elif magnet: qb.torrents_add(urls=magnet, **options)
            else: raise Exception("No payload")
            res['success'] = True
        except Exception as e: res['error'] = str(e)
        results.append(res)

    threads = [threading.Thread(target=task, args=(s,)) for s in target_servers]
    for t in threads: t.start()
    for t in threads: t.join()

    return jsonify({
        'results': results,
        'debug_limits': {'up': up_limit, 'dl': dl_limit}
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
