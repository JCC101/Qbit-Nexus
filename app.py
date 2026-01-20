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
# 设置 Session 密钥
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
# 获取环境变量中的密码
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
    # 始终返回速度字符串，保持对齐
    if speed == 0: return "0 B/s"
    return f"{format_size(speed)}/s"

# --- 登录页面模板 ---
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qbit-Nexus | Login</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iOCIgZmlsbD0idXJsKCNnKSIvPjxkZWZzPjxsaW5lYXJHcmFkaWVudCBpZD0iZyIgeDE9IjAlIiB5MT0iMCUiIHgyPSIxMDAlIiB5Mj0iMTAwJSI+PHN0b3Agb2Zmc2V0PSIwJSIgc3RvcC1jb2xvcj0iIzBlYTVlOSIvPjxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0iIzNiODJmNiIvPjwvbGluZWFyR3JhZGllbnQ+PC9kZWZzPjxwYXRoIGQ9Ik0xNiA3TDI1IDEzLjVWNzQuNUwxNiAyOUw3IDI0LjVWMTMuNUwxNiA3WiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PGNpcmNsZSBjeD0iMTYiIGN5PSIxOCIgcj0iMyIgZmlsbD0id2hpdGUiLz48L3N2Zz4=">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Inter', sans-serif; }</style>
</head>
<body class="h-screen flex items-center justify-center bg-[#f8fafc]">
    <div class="w-full max-w-md bg-white p-8 rounded-2xl shadow-xl border border-slate-100 mx-4">
        <div class="text-center mb-8">
            <div class="w-14 h-14 bg-gradient-to-tr from-[#0ea5e9] to-[#3b82f6] rounded-xl flex items-center justify-center text-white text-2xl mx-auto mb-4 shadow-lg shadow-blue-500/30">
                <i class="fas fa-shield-alt"></i>
            </div>
            <h1 class="text-2xl font-bold text-slate-800">安全验证</h1>
            <p class="text-slate-400 text-sm mt-2">Qbit-Nexus Control Center</p>
        </div>
        <form method="POST" class="space-y-6">
            <div>
                <label class="block text-xs font-bold text-slate-400 uppercase mb-2 tracking-wider">Access Password</label>
                <input type="password" name="password" required autofocus
                    class="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3.5 text-slate-700 outline-none focus:border-[#0ea5e9] focus:ring-4 focus:ring-blue-500/10 transition-all placeholder-slate-300"
                    placeholder="请输入访问密码...">
            </div>
            {% if error %}
            <div class="text-red-500 text-xs font-medium text-center bg-red-50 py-2.5 rounded-lg border border-red-100 flex items-center justify-center gap-2">
                <i class="fas fa-exclamation-circle"></i> {{ error }}
            </div>
            {% endif %}
            <button type="submit" 
                class="w-full bg-gradient-to-r from-[#0ea5e9] to-[#3b82f6] text-white font-bold py-3.5 rounded-xl shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40 hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200">
                解锁控制台
            </button>
        </form>
    </div>
</body>
</html>
"""

# --- 主界面模板 (v5.1 - 节点状态卡片化优化) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qbit-Nexus | 批量任务</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iOCIgZmlsbD0idXJsKCNnKSIvPjxkZWZzPjxsaW5lYXJHcmFkaWVudCBpZD0iZyIgeDE9IjAlIiB5MT0iMCUiIHgyPSIxMDAlIiB5Mj0iMTAwJSI+PHN0b3Agb2Zmc2V0PSIwJSIgc3RvcC1jb2xvcj0iIzBlYTVlOSIvPjxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0iIzNiODJmNiIvPjwvbGluZWFyR3JhZGllbnQ+PC9kZWZzPjxwYXRoIGQ9Ik0xNiA3TDI1IDEzLjVWNzQuNUwxNiAyOUw3IDI0LjVWMTMuNUwxNiA3WiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PGNpcmNsZSBjeD0iMTYiIGN5PSIxOCIgcj0iMyIgZmlsbD0id2hpdGUiLz48L3N2Zz4=">
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
                    screens: { 
                        '2xl': '1600px',
                        '3xl': '2100px'
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #f8fafc; color: #334155; font-family: 'Inter', sans-serif; }
        .fresh-card { 
            background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 0.75rem; 
            box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.02); display: flex; flex-direction: column;
        }
        .fresh-input { 
            background-color: #f1f5f9; border: 1px solid #e2e8f0; color: #334155; 
            transition: all 0.2s; border-radius: 0.375rem; width: 100%; font-size: 0.875rem;
        }
        .fresh-input:focus { background-color: #ffffff; border-color: #0ea5e9; outline: none; box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.1); }
        
        .txt-responsive { font-size: 0.8rem; } 
        @media (min-width: 1600px) { .txt-responsive { font-size: 0.875rem; } }
        @media (min-width: 2100px) { .txt-responsive { font-size: 1rem; } }

        .lbl-responsive { font-size: 0.7rem; font-weight: 600; color: #64748b; margin-bottom: 0.15rem; } 
        @media (min-width: 1600px) { .lbl-responsive { font-size: 0.75rem; margin-bottom: 0.25rem; } }
        @media (min-width: 2100px) { .lbl-responsive { font-size: 0.875rem; margin-bottom: 0.4rem; } }

        .section-title { font-size: 0.8rem; font-weight: 700; color: #0ea5e9; text-transform: uppercase; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem; } 
        @media (min-width: 2100px) { .section-title { font-size: 1rem; margin-bottom: 1.25rem; } }

        .check-item { display: flex; align-items: center; gap: 0.4rem; cursor: pointer; user-select: none; color: #475569; font-size: 0.8rem;}
        @media (min-width: 2100px) { .check-item { font-size: 0.95rem; gap: 0.6rem; } }
        
        .check-item input { accent-color: #0ea5e9; width: 0.9rem; height: 0.9rem; border-radius: 3px; } 
        @media (min-width: 2100px) { .check-item input { width: 1.1rem; height: 1.1rem; } }

        .fresh-btn { background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%); color: white; border-radius: 9999px; transition: all 0.2s; box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.2); }
        .fresh-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 10px -1px rgba(59, 130, 246, 0.3); }
        .action-btn { display: flex; align-items: center; justify-content: center; border-radius: 0.5rem; transition: all 0.2s; font-weight: 500; font-size: 0.75rem; }
        .action-btn:hover { transform: translateY(-1px); box-shadow: 0 2px 4px rgba(0,0,0,0.05); }

        .status-dot { height: 6px; width: 6px; border-radius: 50%; display: inline-block; }
        .status-online { background-color: #10b981; } .status-offline { background-color: #ef4444; } .status-pending { background-color: #cbd5e1; }
        
        ::-webkit-scrollbar { width: 4px; height: 4px; } 
        ::-webkit-scrollbar-track { background: transparent; } 
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }
    </style>
</head>
<body class="h-screen flex flex-col md:flex-row overflow-hidden bg-bg text-text">

<aside class="w-full md:w-56 3xl:w-80 bg-surface border-b md:border-r border-border flex flex-col z-20 shadow-sm shrink-0 transition-all">
    <div class="h-14 3xl:h-20 flex items-center justify-between px-4 border-b border-border">
        <div class="flex items-center gap-2">
            <div class="w-7 h-7 3xl:w-9 3xl:h-9 rounded bg-primary flex items-center justify-center text-white"><i class="fas fa-layer-group text-sm 3xl:text-lg"></i></div>
            <h1 class="font-bold text-base 3xl:text-xl text-slate-800">Qbit-Nexus</h1>
        </div>
        <button class="md:hidden text-slate-500" onclick="document.getElementById('mobileMenu').classList.toggle('hidden')"><i class="fas fa-bars"></i></button>
    </div>
    <div id="mobileMenu" class="hidden md:flex flex-1 flex-col overflow-hidden">
        <nav class="flex-1 p-3 space-y-1 overflow-y-auto">
            <button onclick="switchTab('distribute')" id="nav-distribute" class="w-full text-left px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-50 border border-transparent hover:border-slate-100 transition-all mb-1 font-medium bg-slate-50">🚀 批量添加</button>
            <button onclick="switchTab('manage')" id="nav-manage" class="w-full text-left px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-50 border border-transparent hover:border-slate-100 transition-all font-medium">📊 集群管理</button>
            <div class="mt-4 pt-4 border-t border-slate-100">
                <div class="px-2 text-xs font-bold text-slate-400 uppercase mb-2">节点列表</div>
                <div id="sidebarNodeList" class="space-y-1"></div>
                <button onclick="toggleModal('addNodeModal')" class="mt-3 w-full py-2 border border-dashed border-slate-300 rounded text-xs text-slate-500 hover:text-primary hover:border-primary transition-all">+ 添加节点</button>
            </div>
        </nav>
    </div>
</aside>

<main class="flex-1 flex flex-col min-w-0 bg-bg overflow-hidden relative">
    <header class="h-14 3xl:h-20 flex justify-between items-center px-6 border-b border-border bg-surface/60 backdrop-blur shrink-0">
        <h2 id="headerTitle" class="font-bold text-slate-700 text-sm 3xl:text-lg">批量任务添加 (Batch Add)</h2>
        <div class="flex items-center gap-2">
            <button onclick="openSettings()" class="text-xs 3xl:text-sm font-medium text-slate-500 hover:text-primary flex items-center gap-1.5 bg-white border border-slate-200 px-3 py-1.5 3xl:px-4 3xl:py-2 rounded-full shadow-sm transition-all">
                <i class="fas fa-cog"></i> 全局配置
            </button>
            <a href="/logout" class="text-xs 3xl:text-sm font-medium text-red-400 hover:text-red-600 hover:bg-red-50 flex items-center gap-1.5 bg-white border border-red-100 px-3 py-1.5 3xl:px-4 3xl:py-2 rounded-full shadow-sm transition-all" title="退出">
                <i class="fas fa-sign-out-alt"></i>
            </a>
        </div>
    </header>

    <div id="tab-distribute" class="flex-1 overflow-y-auto p-4 3xl:p-8">
        <div class="w-full max-w-[2400px] mx-auto space-y-4 3xl:space-y-6">
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-4 3xl:gap-6 h-auto xl:h-[240px] 3xl:h-[360px]">
                <div class="fresh-card p-4 3xl:p-6 space-y-2 3xl:space-y-4">
                    <div class="section-title text-xs"><i class="fas fa-file-import"></i> 资源选择</div>
                    <div class="flex flex-col justify-center h-full gap-3 3xl:gap-5">
                        <div class="relative group flex-1 max-h-24 3xl:max-h-40">
                            <input type="file" id="torrentFile" accept=".torrent" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" onchange="updateFileName(this)">
                            <div id="fileDropZone" class="h-full border border-dashed border-slate-300 rounded flex flex-col items-center justify-center gap-1 3xl:gap-3 group-hover:border-primary group-hover:bg-blue-50 transition-all bg-slate-50/50">
                                <i class="fas fa-cloud-upload-alt text-lg 3xl:text-3xl text-slate-400 group-hover:text-primary"></i>
                                <span id="fileNameDisplay" class="text-xs 3xl:text-base font-medium text-slate-500">点击上传 .torrent 文件</span>
                            </div>
                        </div>
                        <div class="relative">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400 text-xs 3xl:text-base"><i class="fas fa-magnet"></i></div>
                            <input type="text" id="magnetLink" placeholder="或者粘贴 Magnet 链接..." class="pl-8 3xl:pl-10 w-full fresh-input py-1.5 3xl:py-3 text-xs 3xl:text-sm">
                        </div>
                    </div>
                </div>
                <div class="fresh-card p-4 3xl:p-6 flex flex-col">
                    <div class="section-title text-xs flex justify-between">
                        <span><i class="fas fa-server"></i> 目标节点</span>
                        <div class="space-x-1.5 text-[10px] 3xl:text-xs">
                            <button onclick="toggleAllTargets(true)" class="text-primary hover:underline">全选</button>
                            <span class="text-slate-300">|</span>
                            <button onclick="toggleAllTargets(false)" class="text-slate-400 hover:text-slate-600 hover:underline">全不选</button>
                        </div>
                    </div>
                    <div id="targetSelectionArea" class="flex-1 overflow-y-auto pr-1 grid grid-cols-2 md:grid-cols-3 3xl:grid-cols-4 gap-2 3xl:gap-4 content-start">
                        <div class="text-xs text-slate-400 col-span-full text-center py-4">正在加载节点...</div>
                    </div>
                </div>
            </div>
            <div class="fresh-card p-5 3xl:p-8">
                <div class="section-title text-xs mb-3 3xl:mb-6"><i class="fas fa-sliders-h"></i> 任务参数</div>
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 3xl:gap-10">
                    <div class="lg:col-span-5 space-y-3 3xl:space-y-5 border-b lg:border-b-0 lg:border-r border-slate-100 pb-4 lg:pb-0 lg:pr-6 3xl:pr-10">
                        <div class="grid grid-cols-2 gap-3 3xl:gap-5">
                            <div><label class="lbl-responsive">管理模式 (TMM)</label><select id="autoTMM" class="fresh-input px-2 py-1.5 3xl:py-2.5 txt-responsive"><option value="false">手动 (Manual)</option><option value="true">自动 (Automatic)</option></select></div>
                            <div><label class="lbl-responsive">内容布局</label><select id="contentLayout" class="fresh-input px-2 py-1.5 3xl:py-2.5 txt-responsive"><option value="Original">原始</option><option value="Subfolder">创建子目录</option><option value="NoSubFolder">不创建子目录</option></select></div>
                        </div>
                        <div><label class="lbl-responsive">保存路径</label><input type="text" id="savePath" class="fresh-input px-2 py-1.5 3xl:py-2.5 txt-responsive" placeholder="默认路径..."></div>
                        <div><label class="lbl-responsive">重命名 (可选)</label><input type="text" id="rename" class="fresh-input px-2 py-1.5 3xl:py-2.5 txt-responsive" placeholder="保持原名则留空"></div>
                        <div class="grid grid-cols-2 gap-3 3xl:gap-5">
                            <div><label class="lbl-responsive">分类</label><input type="text" id="category" class="fresh-input px-2 py-1.5 3xl:py-2.5 txt-responsive"></div>
                            <div><label class="lbl-responsive">标签</label><input type="text" id="tags" class="fresh-input px-2 py-1.5 3xl:py-2.5 txt-responsive"></div>
                        </div>
                    </div>
                    <div class="lg:col-span-4 space-y-3 3xl:space-y-5 border-b lg:border-b-0 lg:border-r border-slate-100 pb-4 lg:pb-0 lg:px-6 3xl:px-10">
                        <div class="space-y-2 3xl:space-y-4 bg-slate-50 p-3 3xl:p-5 rounded border border-slate-100">
                            <label class="text-[10px] 3xl:text-xs font-bold text-slate-400 uppercase">速度限制 (预设)</label>
                            <label class="flex items-center justify-between cursor-pointer group p-1 hover:bg-white rounded transition-colors">
                                <div class="flex items-center gap-2"><div class="w-6 h-6 rounded bg-green-100 text-green-600 flex items-center justify-center text-xs"><i class="fas fa-upload"></i></div><span class="txt-responsive font-medium text-slate-700">上传限速</span></div>
                                <div class="flex items-center gap-2"><span id="limitUlDisplay" class="text-[10px] 3xl:text-xs text-slate-400">--</span><input type="checkbox" id="useLimitUl" class="accent-primary w-4 h-4 3xl:w-5 3xl:h-5 rounded"></div>
                            </label>
                            <label class="flex items-center justify-between cursor-pointer group p-1 hover:bg-white rounded transition-colors">
                                <div class="flex items-center gap-2"><div class="w-6 h-6 rounded bg-blue-100 text-blue-600 flex items-center justify-center text-xs"><i class="fas fa-download"></i></div><span class="txt-responsive font-medium text-slate-700">下载限速</span></div>
                                <div class="flex items-center gap-2"><span id="limitDlDisplay" class="text-[10px] 3xl:text-xs text-slate-400">--</span><input type="checkbox" id="useLimitDl" class="accent-primary w-4 h-4 3xl:w-5 3xl:h-5 rounded"></div>
                            </label>
                        </div>
                        <div class="space-y-2 3xl:space-y-4 pt-1">
                            <label class="text-[10px] 3xl:text-xs font-bold text-slate-400 uppercase">停止条件 (留空为无)</label>
                            <div class="grid grid-cols-2 gap-3 3xl:gap-5">
                                <div><label class="lbl-responsive">最大分享率</label><input type="number" id="ratioLimit" class="fresh-input px-2 py-1.5 3xl:py-2.5 txt-responsive" placeholder="∞"></div>
                                <div><label class="lbl-responsive">做种时间(分)</label><input type="number" id="seedingTimeLimit" class="fresh-input px-2 py-1.5 3xl:py-2.5 txt-responsive" placeholder="∞"></div>
                            </div>
                        </div>
                    </div>
                    <div class="lg:col-span-3 space-y-3 3xl:space-y-5 lg:pl-4 3xl:pl-8 pt-1">
                        <label class="text-[10px] 3xl:text-xs font-bold text-slate-400 uppercase mb-2 block">高级选项</label>
                        <div class="flex flex-col gap-2.5 3xl:gap-4">
                            <label class="check-item"><input type="checkbox" id="startTorrent" checked> <span>开始 Torrent</span></label>
                            <label class="check-item"><input type="checkbox" id="addToTop"> <span>添加到队列顶部</span></label>
                            <label class="check-item"><input type="checkbox" id="skipHash"> <span>跳过哈希校验</span></label>
                            <label class="check-item"><input type="checkbox" id="sequential"> <span>按顺序下载</span></label>
                            <label class="check-item"><input type="checkbox" id="firstLast"> <span>先下载首尾文件块</span></label>
                        </div>
                    </div>
                </div>
                <div class="mt-6 pt-4 3xl:mt-10 3xl:pt-6 border-t border-slate-100 flex justify-center">
                    <button onclick="distributeTorrent()" class="fresh-btn w-full md:w-auto md:px-12 py-3 3xl:py-3.5 font-bold text-sm 3xl:text-base tracking-wide flex justify-center items-center gap-2 shadow-lg shadow-blue-500/20 hover:scale-105 transform transition-transform">
                        <i class="fas fa-paper-plane"></i> 立即批量添加
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div id="tab-manage" class="hidden flex-1 flex flex-col h-full overflow-hidden">
        <header class="h-14 3xl:h-20 flex justify-between items-center px-6 border-b border-border bg-surface/60 backdrop-blur shrink-0 gap-4">
            <div class="relative flex-1 max-w-md">
                <input type="text" id="tableSearch" onkeyup="filterTable()" placeholder="搜索任务名称 / Hash..." class="pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded-full w-full focus:border-primary focus:ring-2 focus:ring-blue-100 transition-all outline-none">
                <i class="fas fa-search absolute left-3 top-2 text-slate-400 text-xs"></i>
            </div>
            <button onclick="fetchClusterData()" class="text-xs bg-white border border-slate-200 px-3 py-1.5 rounded hover:text-primary transition-colors whitespace-nowrap"><i class="fas fa-sync-alt mr-1"></i> 刷新列表</button>
        </header>
        <div class="flex-1 overflow-auto p-4 3xl:p-8">
            <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden min-h-[400px]">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-50 text-xs font-bold text-slate-500 uppercase border-b border-slate-200 sticky top-0 z-10">
                        <tr>
                            <th class="px-6 py-4 w-1/4">名称 (NAME)</th>
                            <th class="px-6 py-4 w-24">大小 (SIZE)</th>
                            <th class="px-6 py-4">节点分布 (NODES DISTRIBUTION)</th>
                            <th class="px-6 py-4 w-48 text-right">操作 (ACTION)</th>
                        </tr>
                    </thead>
                    <tbody id="clusterTableBody" class="text-sm divide-y divide-slate-100"></tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="h-8 bg-slate-800 text-slate-400 text-[10px] flex items-center px-4 shrink-0 font-mono"><span class="mr-2 text-blue-400">LOG ></span><div id="statusBar" class="truncate flex-1">Ready.</div></div>
</main>

<div id="addNodeModal" class="fixed inset-0 bg-slate-900/30 z-50 hidden flex items-center justify-center backdrop-blur-sm p-4"><div class="bg-white rounded-xl w-full max-w-sm shadow-2xl p-5 space-y-3"><h3 class="font-bold text-base text-slate-800">添加下载器</h3><input id="newNodeName" placeholder="名称 (Alias)" class="fresh-input px-3 py-2"><input id="newHost" placeholder="地址 (http://IP:Port)" class="fresh-input px-3 py-2"><div class="grid grid-cols-2 gap-2"><input id="newUser" placeholder="用户名" class="fresh-input px-3 py-2"><input type="password" id="newPass" placeholder="密码" class="fresh-input px-3 py-2"></div><div class="flex justify-end gap-2 pt-2"><button onclick="toggleModal('addNodeModal')" class="px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-50 rounded">取消</button><button onclick="addServer()" class="px-4 py-1.5 text-xs bg-primary text-white rounded hover:bg-blue-600">保存</button></div></div></div>
<div id="settingsModal" class="fixed inset-0 bg-slate-900/30 z-50 hidden flex items-center justify-center backdrop-blur-sm p-4"><div class="bg-white rounded-xl w-full max-w-md shadow-2xl p-5 space-y-4"><h3 class="font-bold text-base text-slate-800 border-b border-slate-100 pb-2">全局配置 & 预设</h3><div class="bg-blue-50/50 p-3 rounded border border-blue-100"><label class="text-[10px] font-bold text-primary uppercase mb-2 block">限速预设值 (Presets)</label><div class="grid grid-cols-2 gap-3"><div><label class="lbl-responsive">上传 (KiB/s)</label><input type="number" id="def_presetUl" class="fresh-input px-2 py-1.5 bg-white"></div><div><label class="lbl-responsive">下载 (KiB/s)</label><input type="number" id="def_presetDl" class="fresh-input px-2 py-1.5 bg-white"></div></div></div><div class="space-y-3"><label class="text-[10px] font-bold text-slate-400 uppercase block">表单默认值</label><div><label class="lbl-responsive">默认保存路径</label><input type="text" id="def_savePath" class="fresh-input px-2 py-1.5"></div><div class="grid grid-cols-2 gap-3"><div><label class="lbl-responsive">默认分类</label><input type="text" id="def_category" class="fresh-input px-2 py-1.5"></div><div><label class="lbl-responsive">默认标签</label><input type="text" id="def_tags" class="fresh-input px-2 py-1.5"></div></div></div><div class="flex justify-end gap-2 pt-2"><button onclick="toggleModal('settingsModal')" class="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-800">取消</button><button onclick="saveSettings()" class="px-4 py-1.5 text-xs bg-primary text-white rounded hover:bg-blue-600 shadow-sm">保存</button></div></div></div>

<div id="actionModal" class="fixed inset-0 bg-slate-900/40 z-50 hidden flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-white rounded-xl w-full max-w-md shadow-2xl overflow-hidden transform transition-all scale-100">
        <div class="p-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
            <h3 id="modalTitle" class="font-bold text-slate-700">操作确认</h3>
            <button onclick="toggleModal('actionModal')" class="text-slate-400 hover:text-slate-600"><i class="fas fa-times"></i></button>
        </div>
        <div class="p-5 space-y-4">
            <div class="text-sm text-slate-600">
                <p class="mb-2">目标任务：<span id="modalTaskName" class="font-bold text-slate-800 break-all"></span></p>
                <p class="text-xs text-slate-400">请选择要执行操作的节点：</p>
            </div>
            <div id="actionNodeList" class="space-y-2 max-h-48 overflow-y-auto border border-slate-100 rounded p-2 bg-slate-50/50"></div>
            <div id="deleteOptions" class="hidden">
                <label class="flex items-center gap-2 p-3 bg-red-50 rounded border border-red-100 cursor-pointer">
                    <input type="checkbox" id="delWithData" class="accent-red-500 w-4 h-4">
                    <span class="text-sm font-bold text-red-600">⚠️ 同时删除硬盘文件</span>
                </label>
            </div>
        </div>
        <div class="p-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-3">
            <button onclick="toggleModal('actionModal')" class="px-4 py-2 text-sm text-slate-500 hover:bg-white rounded transition-colors">取消</button>
            <button id="modalConfirmBtn" onclick="executeAction()" class="px-6 py-2 text-sm text-white font-bold rounded shadow-md transition-transform hover:scale-105">确认</button>
        </div>
    </div>
</div>

<script>
    let globalConfig = {};
    let clusterData = {}; 
    let currentAction = {};

    function toggleModal(id) { document.getElementById(id).classList.toggle('hidden'); }
    function switchTab(tab) {
        document.querySelectorAll('button[id^="nav-"]').forEach(b => {
            b.classList.remove('bg-slate-50', 'text-primary'); 
            b.classList.add('text-slate-600', 'hover:bg-slate-50');
        });
        document.getElementById('nav-'+tab).classList.add('bg-slate-50', 'text-primary');
        document.getElementById('nav-'+tab).classList.remove('text-slate-600');
        
        document.getElementById('tab-distribute').classList.add('hidden');
        document.getElementById('tab-manage').classList.add('hidden');
        document.getElementById('tab-'+tab).classList.remove('hidden');
        
        document.getElementById('headerTitle').innerText = (tab === 'distribute') ? '批量任务添加 (Batch Add)' : '集群任务管理 (Cluster Manager)';
    }
    function log(msg) { document.getElementById('statusBar').innerText = msg; }
    function maskUrl(url) { try { return url.replace(/(\d{1,3}\.)\d{1,3}\.\d{1,3}(\.\d{1,3})/, '$1***.***$2'); } catch(e) { return '***'; } }
    function toggleAllTargets(checked) { document.querySelectorAll('#targetSelectionArea input').forEach(cb => cb.checked = checked); }
    function updateFileName(input) { if(input.files[0]) document.getElementById('fileNameDisplay').innerText = input.files[0].name; }

    // --- 加载数据 ---
    async function loadData() {
        const res = await fetch('/api/config');
        if(res.status === 403 || res.redirected) window.location.href = '/login';
        const data = await res.json();
        globalConfig = data;
        
        const sb = document.getElementById('sidebarNodeList'); sb.innerHTML = '';
        const tg = document.getElementById('targetSelectionArea'); tg.innerHTML = '';
        
        data.servers.forEach((s, idx) => {
            const name = s.name || s.host;
            sb.innerHTML += `<div class="flex justify-between px-2 py-1 hover:bg-slate-50 rounded text-xs text-slate-600 group"><span class="truncate w-32" title="${s.host}">${name}</span><button onclick="removeServer(${idx})" class="hidden group-hover:block text-red-400"><i class="fas fa-times"></i></button></div>`;
            tg.innerHTML += `<label class="flex items-center gap-2 p-2 border rounded hover:bg-slate-50 cursor-pointer bg-white"><input type="checkbox" name="targetNode" value="${idx}" class="accent-primary w-3.5 h-3.5"><div class="overflow-hidden"><div class="text-xs font-bold text-slate-700 truncate">${name}</div><div class="text-[10px] text-slate-400 truncate">${maskUrl(s.host)}</div></div></label>`;
        });

        if(!document.getElementById('savePath').value) {
            const d = data.defaults || {};
            document.getElementById('savePath').value = d.savePath || '';
            document.getElementById('def_savePath').value = d.savePath || '';
            document.getElementById('def_presetUl').value = d.presetUl || '';
            document.getElementById('def_presetDl').value = d.presetDl || '';
            const ulTxt = d.presetUl ? `${d.presetUl} KiB/s` : '--';
            const dlTxt = d.presetDl ? `${d.presetDl} KiB/s` : '--';
            document.getElementById('limitUlDisplay').innerText = ulTxt;
            document.getElementById('limitDlDisplay').innerText = dlTxt;
        }
    }

    async function addServer() {
        const payload = {
            name: document.getElementById('newNodeName').value, host: document.getElementById('newHost').value,
            username: document.getElementById('newUser').value, password: document.getElementById('newPass').value
        };
        await fetch('/api/servers', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
        toggleModal('addNodeModal'); loadData();
    }
    async function removeServer(idx) { if(confirm('删除节点?')) { await fetch(`/api/servers/${idx}`, {method:'DELETE'}); loadData(); } }
    async function saveSettings() {
        const defaults = {
            presetUl: document.getElementById('def_presetUl').value, presetDl: document.getElementById('def_presetDl').value,
            savePath: document.getElementById('def_savePath').value
        };
        await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(defaults)});
        toggleModal('settingsModal'); loadData();
    }

    async function distributeTorrent() {
        const file = document.getElementById('torrentFile').files[0];
        const magnet = document.getElementById('magnetLink').value;
        const targets = Array.from(document.querySelectorAll('#targetSelectionArea input:checked')).map(cb => parseInt(cb.value));
        if((!file && !magnet) || targets.length === 0) return alert('请检查资源和节点选择');

        const fd = new FormData();
        if(file) fd.append('file', file); if(magnet) fd.append('magnet', magnet);
        fd.append('targets', JSON.stringify(targets));
        ['autoTMM','contentLayout','savePath','rename','category','tags','ratioLimit','seedingTimeLimit'].forEach(k => fd.append(k.replace(/[A-Z]/g, m=>'_'+m.toLowerCase()), document.getElementById(k).value));
        ['useLimitUl','useLimitDl','startTorrent','addToTop','skipHash','sequential','firstLast'].forEach(k => fd.append(k.replace(/[A-Z]/g, m=>'_'+m.toLowerCase()), document.getElementById(k).checked));

        log('发送中...');
        const res = await fetch('/api/distribute', {method:'POST', body:fd});
        const data = await res.json();
        log('完成: ' + data.results.map(r=>r.success?'OK':'Fail').join(', '));
    }

    async function fetchClusterData() {
        document.getElementById('clusterTableBody').innerHTML = '<tr><td colspan="4" class="px-6 py-8 text-center text-slate-400"><i class="fas fa-circle-notch fa-spin mr-2"></i>正在同步数据...</td></tr>';
        try {
            const res = await fetch('/api/tasks/list');
            clusterData = await res.json();
            renderTable(clusterData);
            log(`已同步 ${Object.keys(clusterData).length} 个任务`);
        } catch(e) { document.getElementById('clusterTableBody').innerHTML = '<tr><td colspan="4" class="text-center text-red-400 py-4">同步失败</td></tr>'; }
    }

    function renderTable(data) {
        const tbody = document.getElementById('clusterTableBody'); tbody.innerHTML = '';
        if(Object.keys(data).length === 0) { tbody.innerHTML = '<tr><td colspan="4" class="text-center py-8 text-slate-400">暂无任务</td></tr>'; return; }

        for (const [hash, task] of Object.entries(data)) {
            let nodesHtml = '<div class="flex flex-wrap gap-2">';
            for(const [srvIdx, info] of Object.entries(task.nodes)) {
                const srvName = globalConfig.servers[srvIdx]?.name || `Node ${srvIdx}`;
                
                // 状态卡片设计
                let borderColor = "border-slate-200";
                let bgColor = "bg-white";
                let icon = "<i class='fas fa-pause text-slate-400'></i>";
                
                if (['downloading', 'stalledDL'].some(s => info.state.includes(s))) {
                    borderColor = "border-blue-200"; bgColor = "bg-blue-50"; icon = "<i class='fas fa-arrow-down text-blue-500'></i>";
                } else if (['uploading', 'stalledUP', 'queuedUP', 'forcedUP'].some(s => info.state.includes(s))) {
                    borderColor = "border-green-200"; bgColor = "bg-green-50"; icon = "<i class='fas fa-arrow-up text-green-500'></i>";
                }

                // 进度条颜色
                const progColor = info.progress >= 1 ? 'bg-green-500' : 'bg-blue-500';
                const progWidth = Math.round(info.progress * 100) + '%';

                nodesHtml += `
                    <div class="border ${borderColor} ${bgColor} rounded px-2 py-1.5 min-w-[140px] max-w-[180px] shadow-sm">
                        <div class="flex justify-between items-center text-xs mb-1">
                            <span class="font-bold text-slate-700 truncate mr-2" title="${srvName}">${srvName}</span>
                            ${icon}
                        </div>
                        <div class="w-full bg-slate-200 h-1 rounded-full overflow-hidden mb-1.5">
                            <div class="${progColor} h-full" style="width: ${progWidth}"></div>
                        </div>
                        <div class="grid grid-cols-2 gap-x-1 text-[10px] text-slate-500 leading-tight">
                            <span>⬇ ${info.dl_speed}</span>
                            <span class="text-right">D: ${info.downloaded}</span>
                            <span>⬆ ${info.up_speed}</span>
                            <span class="text-right">U: ${info.uploaded}</span>
                        </div>
                    </div>
                `;
            }
            nodesHtml += '</div>';

            const tr = document.createElement('tr');
            tr.className = "hover:bg-slate-50 transition-colors border-b border-slate-50 group";
            tr.innerHTML = `
                <td class="px-6 py-3 align-top"><div class="font-medium text-slate-700 break-words w-full max-w-md 3xl:max-w-xl text-sm leading-tight">${task.name}</div><div class="text-[10px] text-slate-300 font-mono mt-1 select-all">${hash}</div></td>
                <td class="px-6 py-3 text-xs text-slate-500 whitespace-nowrap align-top pt-3">${task.size}</td>
                <td class="px-6 py-2 align-top">${nodesHtml}</td>
                <td class="px-6 py-3 text-right whitespace-nowrap align-top pt-3 space-x-1">
                    <button onclick="openActionModal('${hash}', 'delete')" class="action-btn px-2.5 py-1.5 text-red-500 bg-red-50 hover:bg-red-100 hover:shadow"><i class="fas fa-trash-alt mr-1.5"></i> 删除</button>
                    <button onclick="openActionModal('${hash}', 'pause')" class="action-btn px-2.5 py-1.5 text-amber-500 bg-amber-50 hover:bg-amber-100 hover:shadow"><i class="fas fa-pause mr-1.5"></i> 暂停</button>
                    <button onclick="openActionModal('${hash}', 'resume')" class="action-btn px-2.5 py-1.5 text-green-500 bg-green-50 hover:bg-green-100 hover:shadow"><i class="fas fa-play mr-1.5"></i> 开始</button>
                </td>
            `;
            tbody.appendChild(tr);
        }
    }

    function openActionModal(hash, type) {
        const task = clusterData[hash];
        if(!task) return alert("任务数据丢失，请刷新");
        currentAction = { hash, type };
        document.getElementById('modalTaskName').innerText = task.name;
        
        const config = {
            'delete': { title: '删除确认', btnClass: 'bg-red-500 hover:bg-red-600', btnText: '确认删除' },
            'pause':  { title: '暂停任务', btnClass: 'bg-amber-500 hover:bg-amber-600', btnText: '执行暂停' },
            'resume': { title: '开始任务', btnClass: 'bg-green-500 hover:bg-green-600', btnText: '执行开始' }
        };
        const cfg = config[type];
        document.getElementById('modalTitle').innerText = cfg.title;
        const btn = document.getElementById('modalConfirmBtn');
        btn.className = `px-6 py-2 text-sm text-white font-bold rounded shadow-md transition-transform hover:scale-105 ${cfg.btnClass}`;
        btn.innerText = cfg.btnText;

        const list = document.getElementById('actionNodeList'); list.innerHTML = '';
        for(const srvIdx of Object.keys(task.nodes)) {
            const sName = globalConfig.servers[srvIdx]?.name || `Node ${srvIdx}`;
            list.innerHTML += `<label class="flex items-center gap-3 p-2 hover:bg-white rounded cursor-pointer transition-colors"><input type="checkbox" name="actionTarget" value="${srvIdx}" checked class="accent-primary w-4 h-4"><span class="text-sm text-slate-600">${sName}</span></label>`;
        }
        document.getElementById('deleteOptions').style.display = (type === 'delete') ? 'block' : 'none';
        toggleModal('actionModal');
    }

    async function executeAction() {
        const targets = Array.from(document.querySelectorAll('input[name="actionTarget"]:checked')).map(cb => parseInt(cb.value));
        if(targets.length === 0) return alert("请至少选择一个节点");
        
        const payload = {
            hash: currentAction.hash,
            action: currentAction.type,
            targets: targets,
            delete_files: document.getElementById('delWithData').checked
        };
        toggleModal('actionModal'); log('正在执行操作...');
        await fetch('/api/tasks/action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
        log('指令已发送'); setTimeout(fetchClusterData, 500);
    }

    function filterTable() {
        const term = document.getElementById('tableSearch').value.toLowerCase();
        document.querySelectorAll('#clusterTableBody tr').forEach(row => { row.style.display = row.innerText.toLowerCase().includes(term) ? '' : 'none'; });
    }

    openSettings = function() { // override init
        const d = globalConfig.defaults || {};
        document.getElementById('def_presetUl').value = d.presetUl || '';
        document.getElementById('def_presetDl').value = d.presetDl || '';
        document.getElementById('def_savePath').value = d.savePath || '';
        toggleModal('settingsModal');
    }
    loadData();
    switchTab('distribute');
</script>
</body>
</html>
"""

# --- 后端逻辑 ---
def load_data_file():
    if not os.path.exists(CONFIG_FILE): return {"servers": [], "defaults": {}}
    try:
        with open(CONFIG_FILE, 'r') as f: data = json.load(f); return data if isinstance(data, dict) else {"servers": data, "defaults": {}}
    except: return {"servers": [], "defaults": {}}

def save_data_file(data):
    with open(CONFIG_FILE, 'w') as f: json.dump(data, f, indent=4)

def get_client(server_conf):
    return qbittorrentapi.Client(host=server_conf['host'], username=server_conf['username'], password=server_conf['password'], VERIFY_WEBUI_CERTIFICATE=False, REQUESTS_ARGS={'timeout': 10})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not WEB_PASSWORD: session['logged_in'] = True; return redirect(url_for('index'))
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD: session['logged_in'] = True; return redirect(request.args.get('next') or url_for('index'))
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout(): session.pop('logged_in', None); return redirect(url_for('login'))

@app.route('/')
@login_required
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/config')
@login_required
def get_config(): return jsonify(load_data_file())

@app.route('/api/settings', methods=['POST'])
@login_required
def save_settings():
    d = load_data_file(); d['defaults'] = request.json; save_data_file(d); return jsonify({'success': True})

@app.route('/api/servers', methods=['POST'])
@login_required
def add_server():
    d = load_data_file(); req = request.json
    d.setdefault('servers', []).append({'name': req.get('name',''), 'host': req['host'], 'username': req['username'], 'password': req['password']})
    save_data_file(d); return jsonify({'success': True})

@app.route('/api/servers/<int:idx>', methods=['DELETE'])
@login_required
def delete_server(idx):
    d = load_data_file(); d['servers'].pop(idx); save_data_file(d); return jsonify({'success': True})

@app.route('/api/servers/<int:idx>/test', methods=['POST'])
@login_required
def test_server(idx):
    d = load_data_file()
    try: qb = get_client(d['servers'][idx]); qb.auth_log_in(); return jsonify({'success': True})
    except Exception as e: return jsonify({'success': False, 'error': str(e)})

@app.route('/api/distribute', methods=['POST'])
@login_required
def distribute():
    d = load_data_file(); servers = d['servers']; defaults = d.get('defaults', {})
    targets = json.loads(request.form.get('targets', '[]'))
    target_srvs = [servers[i] for i in targets if 0 <= i < len(servers)]
    if not target_srvs: return jsonify({'error': 'No targets'})
    
    file = request.files.get('file'); magnet = request.form.get('magnet')
    fdata = file.read() if file else None
    
    def get_val(k, t=str): 
        v = request.form.get(k)
        if t==int: return int(v) if v and v.isdigit() else None
        if t==float: return float(v) if v and v.replace('.','').isdigit() else None
        return v or None
        
    def get_preset(k): v = defaults.get(k); return int(v)*1024 if v and str(v).isdigit() else None
    up_limit = get_preset('presetUl') if request.form.get('use_limit_ul') == 'true' else None
    dl_limit = get_preset('presetDl') if request.form.get('use_limit_dl') == 'true' else None
    layout = get_val('content_layout')
    
    opts = {
        'save_path': get_val('save_path'), 'rename': get_val('rename'), 'category': get_val('category'), 'tags': get_val('tags'),
        'is_paused': request.form.get('start_torrent') == 'false', 'use_auto_torrent_management': request.form.get('auto_tmm') == 'true',
        'content_layout': layout, 'is_root_folder': (layout=='Original'),
        'upload_limit': up_limit, 'download_limit': dl_limit,
        'ratio_limit': get_val('ratio_limit', float), 'seeding_time_limit': get_val('seeding_time_limit', int),
        'is_skip_checking': request.form.get('skip_hash') == 'true', 'is_sequential_download': request.form.get('sequential') == 'true',
        'is_first_last_piece_priority': request.form.get('first_last') == 'true', 'add_to_top_of_queue': request.form.get('add_to_top') == 'true'
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
        
    ts = [threading.Thread(target=run, args=(s,)) for s in target_srvs]; [t.start() for t in ts]; [t.join() for t in ts]
    return jsonify({'results': res_list})

@app.route('/api/tasks/list', methods=['GET'])
@login_required
def cluster_list():
    data = load_data_file(); servers = data['servers']; aggregated = {}; lock = threading.Lock()
    def fetch(idx, srv):
        try:
            qb = get_client(srv); qb.auth_log_in(); torrents = qb.torrents_info()
            with lock:
                for t in torrents:
                    h = t.hash
                    if h not in aggregated: aggregated[h] = {'name': t.name, 'size': format_size(t.total_size), 'nodes': {}}
                    aggregated[h]['nodes'][idx] = {
                        'state': t.state, 
                        'up_speed': format_speed(t.upspeed), 'dl_speed': format_speed(t.dlspeed),
                        'uploaded': format_size(t.uploaded), 'downloaded': format_size(t.downloaded),
                        'progress': t.progress
                    }
        except: pass
    ts = [threading.Thread(target=fetch, args=(i, s)) for i, s in enumerate(servers)]; [t.start() for t in ts]; [t.join() for t in ts]
    return jsonify(aggregated)

@app.route('/api/tasks/action', methods=['POST'])
@login_required
def cluster_action():
    req = request.json; action = req.get('action'); target_hash = req.get('hash')
    target_idxs = req.get('targets', []); delete_files = req.get('delete_files', False)
    data = load_data_file(); servers = data['servers']
    
    def perform(idx):
        try:
            qb = get_client(servers[idx]); qb.auth_log_in()
            if action == 'delete': qb.torrents_delete(torrent_hashes=target_hash, delete_files=delete_files)
            elif action == 'pause': qb.torrents_pause(torrent_hashes=target_hash)
            elif action == 'resume': qb.torrents_resume(torrent_hashes=target_hash)
        except: pass

    ts = [threading.Thread(target=perform, args=(i,)) for i in target_idxs]; [t.start() for t in ts]; [t.join() for t in ts]
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
