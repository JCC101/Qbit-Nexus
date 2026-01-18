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

# --- 嵌入式 HTML 模板 (清爽明亮版 - Morning Mist) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qbit-Nexus | Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        bg: '#f8fafc',       // 极浅蓝灰背景
                        surface: '#ffffff',  // 纯白卡片
                        border: '#e2e8f0',   // 柔和边框
                        primary: '#0ea5e9',  // 天际蓝
                        primary_hover: '#0284c7',
                        text: '#334155',     // 深灰文本
                        muted: '#94a3b8',    // 浅灰文本
                        danger: '#ef4444'
                    },
                    fontFamily: {
                        sans: ['Inter', 'sans-serif']
                    },
                    boxShadow: {
                        'soft': '0 4px 20px -2px rgba(0, 0, 0, 0.05)',
                        'glow': '0 0 15px rgba(14, 165, 233, 0.3)'
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #f8fafc; color: #334155; font-family: 'Inter', sans-serif; }
        
        /* 玻璃拟态/卡片风格 */
        .fresh-card { 
            background-color: #ffffff; 
            border: 1px solid #e2e8f0; 
            border-radius: 1rem; 
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .fresh-input { 
            background-color: #f1f5f9; 
            border: 1px solid #e2e8f0; 
            color: #334155; 
            transition: all 0.2s;
            border-radius: 0.5rem;
        }
        .fresh-input:focus { 
            background-color: #ffffff;
            border-color: #0ea5e9; 
            outline: none; 
            box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1); 
        }
        
        .fresh-btn {
            background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%);
            color: white;
            border-radius: 0.5rem;
            transition: all 0.2s;
            box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.2);
        }
        .fresh-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 10px -1px rgba(59, 130, 246, 0.3);
        }
        .fresh-btn:active { transform: translateY(0); }

        .status-dot { height: 8px; width: 8px; border-radius: 50%; display: inline-block; }
        .status-online { background-color: #10b981; box-shadow: 0 0 8px rgba(16, 185, 129, 0.4); }
        .status-offline { background-color: #ef4444; }
        .status-pending { background-color: #cbd5e1; }

        /* 滚动条美化 */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
    </style>
</head>
<body class="h-screen flex overflow-hidden selection:bg-primary selection:text-white">

<aside class="w-72 bg-surface border-r border-border flex flex-col z-20 shadow-sm">
    <div class="h-20 flex items-center px-6 border-b border-border">
        <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-primary to-blue-600 flex items-center justify-center text-white shadow-glow">
                <i class="fas fa-bolt text-sm"></i>
            </div>
            <div>
                <h1 class="font-bold text-lg text-slate-800 tracking-tight">Qbit-Nexus</h1>
                <p class="text-[10px] text-muted font-medium uppercase tracking-wider">Control Center</p>
            </div>
        </div>
    </div>
    
    <div class="flex-1 overflow-y-auto p-4 space-y-3" id="serverList">
        </div>

    <div class="p-4 border-t border-border bg-slate-50">
        <button onclick="toggleModal('addNodeModal')" class="w-full py-2.5 rounded-lg border border-dashed border-slate-300 text-slate-500 text-sm font-medium hover:border-primary hover:text-primary hover:bg-white transition-all">
            <i class="fas fa-plus-circle mr-2"></i> 添加下载器
        </button>
    </div>
</aside>

<main class="flex-1 flex flex-col min-w-0 bg-bg relative">
    <header class="h-20 flex justify-between items-center px-8 sticky top-0 z-10">
        <div>
            <h2 class="font-bold text-xl text-slate-800">任务分发</h2>
            <p class="text-xs text-muted mt-0.5">配置您的分发任务参数</p>
        </div>
        <button onclick="openSettings()" class="group flex items-center gap-2 bg-white px-4 py-2 rounded-lg border border-border text-sm text-slate-600 hover:border-primary hover:text-primary transition-all shadow-sm">
            <i class="fas fa-sliders-h transition-transform group-hover:rotate-180"></i> 全局限速与默认值
        </button>
    </header>

    <div class="flex-1 overflow-y-auto p-8 pt-0">
        <div class="max-w-5xl mx-auto space-y-6">
            
            <div class="fresh-card p-6 bg-white">
                <h3 class="text-xs font-bold text-muted uppercase mb-4 flex items-center gap-2">
                    <span class="w-1.5 h-1.5 rounded-full bg-primary"></span> 资源选择
                </h3>
                <div class="grid grid-cols-1 md:grid-cols-12 gap-6">
                    <div class="md:col-span-5">
                        <div class="relative group h-full">
                            <input type="file" id="torrentFile" accept=".torrent" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" onchange="updateFileName(this)">
                            <div id="fileDropZone" class="h-32 border-2 border-dashed border-slate-200 rounded-xl flex flex-col items-center justify-center gap-2 group-hover:border-primary group-hover:bg-blue-50 transition-all">
                                <div class="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-muted group-hover:bg-blue-100 group-hover:text-primary transition-colors">
                                    <i class="fas fa-cloud-upload-alt"></i>
                                </div>
                                <span id="fileNameDisplay" class="text-xs font-medium text-slate-500">点击上传 .torrent 文件</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="md:col-span-1 flex items-center justify-center">
                        <span class="text-xs text-slate-300 font-bold">OR</span>
                    </div>

                    <div class="md:col-span-6">
                        <textarea id="magnetLink" placeholder="粘贴 Magnet 磁力链接..." class="w-full h-32 fresh-input p-4 text-xs font-mono resize-none"></textarea>
                    </div>
                </div>
            </div>

            <div class="fresh-card p-6">
                <h3 class="text-xs font-bold text-muted uppercase mb-4 flex items-center gap-2">
                    <span class="w-1.5 h-1.5 rounded-full bg-primary"></span> 任务参数
                </h3>
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-x-10 gap-y-6">
                    <div class="space-y-5">
                        <div>
                            <label class="block text-xs font-semibold text-slate-500 mb-1.5">保存路径</label>
                            <input type="text" id="savePath" class="w-full fresh-input px-3 py-2.5 text-sm" placeholder="/downloads/">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-semibold text-slate-500 mb-1.5">分类 (Category)</label>
                                <input type="text" id="category" class="w-full fresh-input px-3 py-2.5 text-sm">
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-slate-500 mb-1.5">标签 (Tags)</label>
                                <input type="text" id="tags" class="w-full fresh-input px-3 py-2.5 text-sm">
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-500 mb-1.5">内容布局 (Content Layout)</label>
                            <div class="relative">
                                <select id="contentLayout" class="w-full fresh-input px-3 py-2.5 text-sm appearance-none cursor-pointer">
                                    <option value="Original">原始 (创建子目录)</option>
                                    <option value="NoSubFolder">不创建子目录</option>
                                </select>
                                <div class="absolute right-3 top-3 text-slate-400 pointer-events-none">
                                    <i class="fas fa-chevron-down text-xs"></i>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="space-y-5">
                        <div class="bg-slate-50 rounded-xl p-4 border border-slate-100">
                            <div class="flex justify-between items-center mb-3">
                                <label class="text-xs font-bold text-slate-500 uppercase">速度限制</label>
                                <span class="text-[10px] text-blue-500 bg-blue-50 px-2 py-0.5 rounded cursor-pointer hover:underline" onclick="openSettings()">修改预设值</span>
                            </div>
                            
                            <div class="space-y-3">
                                <label class="flex items-center justify-between cursor-pointer group p-2 hover:bg-white rounded-lg transition-colors border border-transparent hover:border-slate-100 hover:shadow-sm">
                                    <div class="flex items-center gap-3">
                                        <div class="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs">
                                            <i class="fas fa-upload"></i>
                                        </div>
                                        <div>
                                            <span class="text-sm font-medium text-slate-700 block">启用上传限速</span>
                                            <span id="limitUlDisplay" class="text-[10px] text-slate-400">未配置预设值</span>
                                        </div>
                                    </div>
                                    <input type="checkbox" id="useLimitUl" class="accent-primary w-5 h-5 rounded border-slate-300">
                                </label>

                                <label class="flex items-center justify-between cursor-pointer group p-2 hover:bg-white rounded-lg transition-colors border border-transparent hover:border-slate-100 hover:shadow-sm">
                                    <div class="flex items-center gap-3">
                                        <div class="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs">
                                            <i class="fas fa-download"></i>
                                        </div>
                                        <div>
                                            <span class="text-sm font-medium text-slate-700 block">启用下载限速</span>
                                            <span id="limitDlDisplay" class="text-[10px] text-slate-400">未配置预设值</span>
                                        </div>
                                    </div>
                                    <input type="checkbox" id="useLimitDl" class="accent-primary w-5 h-5 rounded border-slate-300">
                                </label>
                            </div>
                        </div>

                        <div class="pt-2">
                             <label class="flex items-center gap-2 cursor-pointer select-none">
                                <input type="checkbox" id="paused" class="accent-primary w-4 h-4 rounded">
                                <span class="text-sm text-slate-600">添加任务后暂停 (Paused)</span>
                            </label>
                        </div>
                    </div>
                </div>

                <div class="mt-8 border-t border-slate-100 pt-6">
                    <button onclick="distributeTorrent()" class="fresh-btn w-full py-3.5 font-bold text-sm tracking-wide flex justify-center items-center gap-2">
                        <i class="fas fa-paper-plane"></i> 立即分发任务
                    </button>
                </div>
            </div>

            <div class="bg-white border border-slate-200 rounded-lg p-2 flex flex-col h-40 shadow-sm">
                <div class="px-2 pb-2 flex justify-between items-center border-b border-slate-50">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Operation Log</span>
                    <button onclick="document.getElementById('consoleLog').innerHTML=''" class="text-[10px] text-slate-400 hover:text-primary">Clear</button>
                </div>
                <div id="consoleLog" class="flex-1 overflow-y-auto p-2 font-mono text-[11px] space-y-1.5 text-slate-600">
                    <div class="text-primary"><i class="fas fa-check-circle mr-1"></i>System initialized.</div>
                </div>
            </div>
        </div>
    </div>
</main>

<div id="addNodeModal" class="fixed inset-0 bg-slate-900/20 z-50 hidden flex items-center justify-center backdrop-blur-sm transition-opacity">
    <div class="bg-white rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-5 transform transition-all scale-100">
        <div class="flex justify-between items-center">
            <h3 class="font-bold text-lg text-slate-800">添加下载器</h3>
            <button onclick="toggleModal('addNodeModal')" class="text-slate-400 hover:text-slate-600"><i class="fas fa-times"></i></button>
        </div>
        
        <div class="space-y-4">
            <div>
                <label class="block text-xs font-semibold text-slate-500 mb-1">名称 (显示用)</label>
                <input type="text" id="newNodeName" placeholder="例如: Hetzner 独服" class="w-full fresh-input px-3 py-2 text-sm">
            </div>
            <div>
                <label class="block text-xs font-semibold text-slate-500 mb-1">地址 (Host)</label>
                <input type="text" id="newHost" placeholder="http://IP:Port" class="w-full fresh-input px-3 py-2 text-sm">
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="block text-xs font-semibold text-slate-500 mb-1">用户名</label>
                    <input type="text" id="newUser" class="w-full fresh-input px-3 py-2 text-sm">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-500 mb-1">密码</label>
                    <input type="password" id="newPass" class="w-full fresh-input px-3 py-2 text-sm">
                </div>
            </div>
        </div>
        <div class="flex justify-end gap-3 pt-2">
            <button onclick="toggleModal('addNodeModal')" class="px-4 py-2 text-sm font-medium text-slate-500 hover:bg-slate-50 rounded-lg">取消</button>
            <button onclick="addServer()" class="px-5 py-2 text-sm font-medium bg-primary text-white rounded-lg hover:bg-blue-600 shadow-sm shadow-blue-200">保存</button>
        </div>
    </div>
</div>

<div id="settingsModal" class="fixed inset-0 bg-slate-900/20 z-50 hidden flex items-center justify-center backdrop-blur-sm">
    <div class="bg-white rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
        <div class="bg-slate-50 p-4 border-b border-slate-100 flex justify-between items-center">
            <h3 class="font-bold text-slate-800">全局配置 & 限速预设</h3>
            <button onclick="toggleModal('settingsModal')" class="text-slate-400 hover:text-slate-600"><i class="fas fa-times"></i></button>
        </div>
        <div class="p-6 space-y-6">
            <div class="bg-blue-50/50 rounded-xl p-4 border border-blue-100 space-y-3">
                <div class="flex items-center gap-2 text-primary">
                    <i class="fas fa-tachometer-alt"></i>
                    <span class="text-xs font-bold uppercase">限速预设值 (Preset Values)</span>
                </div>
                <p class="text-[10px] text-slate-500">在主界面勾选限速时，将应用以下数值。</p>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 mb-1">上传限速 (KiB/s)</label>
                        <input type="number" id="def_presetUl" class="w-full fresh-input px-3 py-2 text-sm bg-white" placeholder="例如: 10240">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 mb-1">下载限速 (KiB/s)</label>
                        <input type="number" id="def_presetDl" class="w-full fresh-input px-3 py-2 text-sm bg-white" placeholder="留空则不限制">
                    </div>
                </div>
            </div>

            <div class="space-y-4">
                <span class="text-xs font-bold text-slate-400 uppercase tracking-wider block">Default Form Values</span>
                <div>
                    <label class="block text-xs font-semibold text-slate-500 mb-1">默认保存路径</label>
                    <input type="text" id="def_savePath" class="w-full fresh-input px-3 py-2 text-sm">
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 mb-1">默认分类</label>
                        <input type="text" id="def_category" class="w-full fresh-input px-3 py-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 mb-1">默认标签</label>
                        <input type="text" id="def_tags" class="w-full fresh-input px-3 py-2 text-sm">
                    </div>
                </div>
            </div>
        </div>
        <div class="p-4 bg-slate-50 border-t border-slate-100 flex justify-end">
            <button onclick="saveSettings()" class="px-6 py-2.5 rounded-lg text-sm font-medium bg-primary text-white hover:bg-blue-600 shadow-md shadow-blue-200">保存配置</button>
        </div>
    </div>
</div>

<script>
    // --- Frontend Logic ---
    let globalConfig = {};

    function toggleModal(id) {
        document.getElementById(id).classList.toggle('hidden');
    }

    function log(msg, type='info') {
        const box = document.getElementById('consoleLog');
        const time = new Date().toLocaleTimeString('en-US', {hour12: false});
        let color = 'text-slate-600';
        let icon = '<i class="fas fa-info-circle text-xs mr-1 opacity-50"></i>';
        
        if(type === 'success') { color = 'text-emerald-600'; icon = '<i class="fas fa-check text-xs mr-1"></i>'; }
        if(type === 'error') { color = 'text-red-500'; icon = '<i class="fas fa-times text-xs mr-1"></i>'; }
        
        box.innerHTML += `<div class="${color} flex items-center"><span class="opacity-40 text-[10px] mr-2 font-normal">${time}</span>${icon}<span>${msg}</span></div>`;
        box.scrollTop = box.scrollHeight;
    }

    function updateFileName(input) {
        const display = document.getElementById('fileNameDisplay');
        const zone = document.getElementById('fileDropZone');
        if (input.files && input.files[0]) {
            display.innerText = input.files[0].name;
            display.className = "text-xs font-bold text-primary";
            zone.classList.add('border-primary', 'bg-blue-50');
        } else {
            display.innerText = '点击上传 .torrent 文件';
            display.className = "text-xs font-medium text-slate-500";
            zone.classList.remove('border-primary', 'bg-blue-50');
        }
    }

    // --- API Interactions ---

    async function loadData() {
        const res = await fetch('/api/config');
        const data = await res.json();
        globalConfig = data;
        const servers = data.servers || [];
        const defaults = data.defaults || {};

        // 1. Render Server List
        const container = document.getElementById('serverList');
        container.innerHTML = '';
        if(servers.length === 0) {
            container.innerHTML = '<div class="text-center py-8 text-xs text-muted">暂无节点<br>请点击下方按钮添加</div>';
        }
        
        servers.forEach((s, idx) => {
            const displayName = s.name || s.host; 
            const displaySub = s.name ? s.host : '';

            const div = document.createElement('div');
            div.className = 'bg-white border border-slate-100 p-3 rounded-lg hover:border-primary/50 hover:shadow-md transition-all group cursor-default mb-2';
            div.innerHTML = `
                <div class="flex justify-between items-start mb-1">
                    <div class="flex-1 min-w-0 pr-2">
                        <div class="font-bold text-sm text-slate-700 truncate">${displayName}</div>
                        <div class="text-[10px] text-slate-400 truncate font-mono">${displaySub}</div>
                    </div>
                    <div id="status-${idx}" class="status-dot status-pending mt-1.5" title="Pending"></div>
                </div>
                <div class="flex gap-3 mt-2 pt-2 border-t border-slate-50 opacity-60 group-hover:opacity-100 transition-opacity">
                    <button onclick="removeServer(${idx})" class="text-[10px] font-medium text-slate-400 hover:text-red-500 flex items-center gap-1"><i class="fas fa-trash"></i> 删除</button>
                    <button onclick="testServer(${idx})" class="text-[10px] font-medium text-slate-400 hover:text-primary flex items-center gap-1"><i class="fas fa-sync-alt"></i> 测试</button>
                </div>
            `;
            container.appendChild(div);
            setTimeout(() => testServer(idx, true), idx * 200 + 300);
        });

        // 2. Fill Defaults
        if(!document.getElementById('savePath').value) {
            document.getElementById('savePath').value = defaults.savePath || '';
            document.getElementById('category').value = defaults.category || '';
            document.getElementById('tags').value = defaults.tags || '';
        }

        // 3. Update Preset Displays
        const ulLimit = defaults.presetUl ? `${defaults.presetUl} KiB/s` : '未配置';
        const dlLimit = defaults.presetDl ? `${defaults.presetDl} KiB/s` : '未配置';
        document.getElementById('limitUlDisplay').innerText = ulLimit;
        document.getElementById('limitDlDisplay').innerText = dlLimit;
    }

    async function addServer() {
        const name = document.getElementById('newNodeName').value.trim();
        const host = document.getElementById('newHost').value.trim();
        const username = document.getElementById('newUser').value.trim();
        const password = document.getElementById('newPass').value.trim();

        if(!host || !username) return alert("地址和用户名必填");

        await fetch('/api/servers', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name, host, username, password })
        });
        
        document.getElementById('newNodeName').value = '';
        document.getElementById('newHost').value = '';
        document.getElementById('newUser').value = '';
        document.getElementById('newPass').value = '';
        
        toggleModal('addNodeModal');
        loadData();
        log(`节点已保存: ${name || host}`, 'success');
    }

    async function removeServer(idx) {
        if(!confirm("确认移除该下载器配置?")) return;
        await fetch(`/api/servers/${idx}`, { method: 'DELETE' });
        loadData();
    }

    async function testServer(idx, silent=false) {
        if(!silent) log(`正在连接节点 #${idx+1}...`);
        const indicator = document.getElementById(`status-${idx}`);
        
        try {
            const res = await fetch(`/api/servers/${idx}/test`, { method: 'POST' });
            const data = await res.json();
            if(data.success) {
                indicator.classList.remove('status-pending', 'status-offline');
                indicator.classList.add('status-online');
                if(!silent) log(`节点 #${idx+1} 连接成功 (v${data.version})`, 'success');
            } else {
                indicator.classList.remove('status-pending', 'status-online');
                indicator.classList.add('status-offline');
                if(!silent) log(`节点 #${idx+1} 连接失败: ${data.error}`, 'error');
            }
        } catch(e) {
            indicator.classList.add('status-offline');
        }
    }

    // --- Settings Logic ---
    async function openSettings() {
        const d = globalConfig.defaults || {};
        document.getElementById('def_presetUl').value = d.presetUl || '';
        document.getElementById('def_presetDl').value = d.presetDl || '';
        document.getElementById('def_savePath').value = d.savePath || '';
        document.getElementById('def_category').value = d.category || '';
        document.getElementById('def_tags').value = d.tags || '';
        
        toggleModal('settingsModal');
    }

    async function saveSettings() {
        const defaults = {
            presetUl: document.getElementById('def_presetUl').value,
            presetDl: document.getElementById('def_presetDl').value,
            savePath: document.getElementById('def_savePath').value,
            category: document.getElementById('def_category').value,
            tags: document.getElementById('def_tags').value,
        };

        await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(defaults)
        });
        
        toggleModal('settingsModal');
        log('全局预设已更新', 'success');
        loadData();
    }

    // --- Distribute Logic ---
    async function distributeTorrent() {
        const fileInput = document.getElementById('torrentFile');
        const magnet = document.getElementById('magnetLink').value.trim();
        
        if (!fileInput.files[0] && !magnet) return alert("请上传种子文件或输入磁力链接");

        const formData = new FormData();
        if (fileInput.files[0]) formData.append('file', fileInput.files[0]);
        if (magnet) formData.append('magnet', magnet);

        formData.append('save_path', document.getElementById('savePath').value.trim());
        formData.append('category', document.getElementById('category').value.trim());
        formData.append('tags', document.getElementById('tags').value.trim());
        
        formData.append('use_limit_ul', document.getElementById('useLimitUl').checked);
        formData.append('use_limit_dl', document.getElementById('useLimitDl').checked);

        formData.append('content_layout', document.getElementById('contentLayout').value);
        formData.append('paused', document.getElementById('paused').checked);

        log(">>> 开始分发任务...", 'info');

        try {
            const res = await fetch('/api/distribute', { method: 'POST', body: formData });
            const result = await res.json();
            
            result.results.forEach(r => {
                const sName = r.name || r.server; 
                if(r.success) log(`[成功] -> ${sName}`, 'success');
                else log(`[失败] -> ${sName}: ${r.error}`, 'error');
            });
            
            if(result.results.every(r => r.success)) log(">>> 所有任务分发完成", 'success');

        } catch (e) {
            log("系统错误: " + e.message, 'error');
        }
    }

    // Init
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
        # 修复：使用 REQUESTS_ARGS 字典传递 timeout，兼容新版 qbittorrent-api
        REQUESTS_ARGS={'timeout': 15}
    )

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

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

@app.route('/api/servers', methods=['POST'])
def add_server():
    req = request.json
    data = load_data_file()
    
    new_node = {
        'name': req.get('name', ''),
        'host': req['host'],
        'username': req['username'],
        'password': req['password']
    }
    
    found = False
    for s in data['servers']:
        if s['host'] == req['host']:
            s.update(new_node)
            found = True
            break
    if not found:
        data['servers'].append(new_node)
    
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

@app.route('/api/distribute', methods=['POST'])
def distribute():
    data = load_data_file()
    servers = data['servers']
    defaults = data.get('defaults', {})
    
    if not servers: return jsonify({'results': [], 'error': 'No nodes linked'})

    magnet = request.form.get('magnet')
    torrent_file = request.files.get('file')
    
    # 获取限速预设值 (KiB -> Bytes)
    def get_preset_bytes(key):
        val = defaults.get(key)
        if val and str(val).isdigit():
            return int(val) * 1024
        return None

    up_limit = None
    dl_limit = None
    
    if request.form.get('use_limit_ul') == 'true':
        up_limit = get_preset_bytes('presetUl')
    
    if request.form.get('use_limit_dl') == 'true':
        dl_limit = get_preset_bytes('presetDl')

    # 内容布局
    layout_val = request.form.get('content_layout', 'Original')
    is_root_folder = (layout_val == 'Original')

    options = {
        'save_path': request.form.get('save_path') or None,
        'category': request.form.get('category') or None,
        'tags': request.form.get('tags') or None,
        'is_paused': request.form.get('paused') == 'true',
        'content_layout': layout_val,
        'is_root_folder': is_root_folder,
        'up_limit': up_limit,
        'dl_limit': dl_limit,
    }
    
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
        except Exception as e:
            res['error'] = str(e)
        results.append(res)

    threads = [threading.Thread(target=task, args=(s,)) for s in servers]
    for t in threads: t.start()
    for t in threads: t.join()

    return jsonify({'results': results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
