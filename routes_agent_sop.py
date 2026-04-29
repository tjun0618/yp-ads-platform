# -*- coding: utf-8 -*-
"""
routes_agent_sop.py
====================
广告优化 SOP Agent — 上传文件 → 执行SOP → 调用Skill → 输出清洁版广告

路由:
  GET  /agent_sop            — SOP 专用聊天页面
  POST /api/agent_sop/chat   — SOP 对话 API（流式SSE）
  POST /api/agent_sop/upload — 文件上传 API

功能:
  1. 上传广告数据文件（CSV/Excel/PDF）
  2. 自动执行固定 SOP 流程
  3. 调用 google-ads-diagnosis skill
  4. 输出 P0/P1/P2 诊断 + 清洁版广告文案
"""

import os
import json
import base64
import uuid
from datetime import datetime
from flask import Blueprint, Response, request, jsonify

bp = Blueprint("agent_sop", __name__)

# ─── Agent 后端地址 ───────────────────────────────────────────────────────────
AGENT_BACKEND_URL = os.environ.get("AGENT_BACKEND_URL", "http://localhost:3000")

# ─── 文件存储（内存）──────────────────────────────────────────────────────────
file_storage = {}


# ─── SOP Prompt ───────────────────────────────────────────────────────────────
SOP_SYSTEM_PROMPT = """你是 Google Ads 亚马逊联盟营销广告优化专家。

## 核心职责
按照以下固化 SOP 流程处理上传的广告数据：
1. 接收并解析上传的 CSV/Excel 广告数据
2. 调用 google-ads-diagnosis skill 进行系统性诊断
3. 输出 P0/P1/P2 分级问题清单
4. 分析利润模型和 CPA（每次点击成本）
5. 生成优化建议
6. 生成否定关键词清单
7. 输出清洁版广告文案

## 广告合规要求
- 美式英语 (American English)
- 美式拼写 (color, center, optimize 等)
- 美元 ($) 货币
- 美国常用单位 (oz, lbs, ft)
- 符合 Google Ads 政策
- 符合 Amazon Associates 合规要求

## 广告字符限制
- Headline: ≤30 字符
- Description: ≤90 字符

## 输出格式（最终必须包含）

### 📊 诊断结果
| 级别 | 问题 | 建议 |
|------|------|------|
| P0 | ... | ... |
| P1 | ... | ... |
| P2 | ... | ... |

### 💰 利润模型
- 佣金率: XX%
- 单价: $XX.XX
- 佣金/单: $X.XX
- 安全 CPA: $X.XX

### 🎯 优化建议
1. ...
2. ...

### 🚫 否定关键词
- xxx
- xxx

### ✨ 清洁版广告文案
**Headline 1:** xxx (XX字符)
**Headline 2:** xxx (XX字符)
**Headline 3:** xxx (XX字符)
**Description:** xxx (XX字符)

请开始处理上传的数据。"""


# ─── 页面路由 ─────────────────────────────────────────────────────────────────
@bp.route("/agent_sop")
def agent_sop_page():
    """SOP 专用聊天页面"""
    html = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>广告优化 SOP Agent — YP Affiliate</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f1419; color: #e7e9ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; height: 100vh; display: flex; }

/* ── 左侧边栏 ── */
.sidebar { width: 260px; background: #16181c; border-right: 1px solid #2f3336; display: flex; flex-direction: column; }
.sidebar-header { padding: 16px; border-bottom: 1px solid #2f3336; }
.sidebar-title { font-size: 1.1rem; font-weight: 700; color: #fff; }
.sidebar-subtitle { font-size: .75rem; color: #71767b; margin-top: 4px; }

.sidebar-status { padding: 12px 16px; border-bottom: 1px solid #2f3336; }
.status-indicator { display: flex; align-items: center; gap: 8px; font-size: .85rem; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.online { background: #00c853; box-shadow: 0 0 8px #00c853; }
.status-dot.offline { background: #ff5252; }

.sidebar-nav { padding: 12px; flex: 1; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 8px; color: #71767b; text-decoration: none; font-size: .9rem; transition: all .15s; margin-bottom: 4px; }
.nav-item:hover { background: #1d9bf0; color: #fff; }
.nav-item.active { background: #1d9bf0; color: #fff; }
.nav-item.back { margin-top: auto; border-top: 1px solid #2f3336; padding-top: 12px; margin-top: 12px; }

/* ── 主内容区 ── */
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

/* ── 顶部栏 ── */
.topbar { background: #16181c; border-bottom: 1px solid #2f3336; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; }
.topbar-title { font-size: 1rem; font-weight: 600; color: #fff; }
.topbar-badge { font-size: .7rem; background: #1d9bf0; color: #fff; padding: 3px 8px; border-radius: 10px; }

/* ── 聊天区 ── */
.chat-area { flex: 1; overflow-y: auto; padding: 20px 24px; }
.chat-area::-webkit-scrollbar { width: 6px; }
.chat-area::-webkit-scrollbar-track { background: transparent; }
.chat-area::-webkit-scrollbar-thumb { background: #2f3336; border-radius: 3px; }

/* ── 消息气泡 ── */
.msg { margin-bottom: 20px; animation: fadeUp .3s ease; }
@keyframes fadeUp { from { opacity:0; transform: translateY(10px); } to { opacity:1; transform: translateY(0); } }
.msg-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.msg-avatar { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; }
.msg.user .msg-avatar { background: #1d9bf0; }
.msg.assistant .msg-avatar { background: #2f3336; }
.msg-role { font-size: .8rem; font-weight: 600; color: #71767b; }
.msg-time { font-size: .7rem; color: #536471; margin-left: auto; }
.msg-content { background: #16181c; border: 1px solid #2f3336; border-radius: 16px; padding: 14px 18px; line-height: 1.6; font-size: .9rem; }
.msg.user .msg-content { background: #1d9bf0; border: none; border-bottom-right-radius: 4px; }

/* ── 工具调用卡片 ── */
.tool-card { background: #1a1f29; border-left: 3px solid #1d9bf0; border-radius: 8px; padding: 12px 14px; margin: 10px 0; }
.tool-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.tool-icon { font-size: 14px; }
.tool-name { font-size: .8rem; font-weight: 600; color: #1d9bf0; }
.tool-status { font-size: .7rem; padding: 2px 8px; border-radius: 10px; margin-left: auto; }
.tool-status.running { background: #ffa726; color: #000; }
.tool-status.completed { background: #00c853; color: #fff; }
.tool-status.error { background: #ff5252; color: #fff; }
.tool-input { background: #0f1419; padding: 10px; border-radius: 6px; font-size: .75rem; color: #71767b; font-family: monospace; overflow-x: auto; margin-bottom: 8px; }
.tool-result { font-size: .8rem; color: #adb5bd; max-height: 100px; overflow: hidden; }

/* ── 欢迎界面 ── */
.welcome { text-align: center; padding: 60px 20px; }
.welcome-icon { font-size: 4rem; margin-bottom: 20px; }
.welcome h2 { font-size: 1.5rem; color: #fff; margin-bottom: 12px; }
.welcome p { color: #71767b; font-size: .95rem; max-width: 500px; margin: 0 auto 30px; line-height: 1.6; }
.welcome-features { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; max-width: 600px; margin: 0 auto; }
.feature-card { background: #16181c; border: 1px solid #2f3336; border-radius: 12px; padding: 16px 20px; text-align: center; width: 180px; }
.feature-icon { font-size: 1.5rem; margin-bottom: 8px; }
.feature-name { font-size: .85rem; color: #e7e9ea; font-weight: 600; }
.feature-desc { font-size: .7rem; color: #71767b; margin-top: 4px; }

/* ── 快捷按钮 ── */
.quick-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 24px; }
.quick-btn { background: #1d9bf0; border: none; color: #fff; padding: 10px 18px; border-radius: 20px; font-size: .85rem; cursor: pointer; transition: all .15s; }
.quick-btn:hover { background: #1a8cd8; transform: scale(1.05); }

/* ── 输入区 ── */
.input-area { background: #16181c; border-top: 1px solid #2f3336; padding: 16px 24px; }
.file-preview { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.file-tag { display: flex; align-items: center; gap: 6px; background: #2f3336; padding: 6px 12px; border-radius: 20px; font-size: .8rem; }
.file-tag .remove { cursor: pointer; color: #ff5252; font-weight: bold; }
.input-row { display: flex; gap: 12px; align-items: flex-end; }
.input-field { flex: 1; background: #2f3336; border: none; border-radius: 12px; padding: 12px 16px; color: #e7e9ea; font-size: .9rem; resize: none; min-height: 48px; max-height: 120px; outline: none; }
.input-field::placeholder { color: #71767b; }
.input-field:focus { box-shadow: 0 0 0 2px #1d9bf0; }
.send-btn { background: #1d9bf0; border: none; color: #fff; width: 48px; height: 48px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all .15s; }
.send-btn:hover:not(:disabled) { background: #1a8cd8; }
.send-btn:disabled { background: #2f3336; cursor: not-allowed; }

/* ── 上传区 ── */
.upload-zone { border: 2px dashed #2f3336; border-radius: 12px; padding: 20px; text-align: center; margin-top: 12px; cursor: pointer; transition: all .2s; }
.upload-zone:hover, .upload-zone.dragover { border-color: #1d9bf0; background: rgba(29,155,240,.1); }
.upload-zone input { display: none; }
.upload-text { font-size: .85rem; color: #71767b; }
.upload-text span { color: #1d9bf0; }

/* ── 清洁输出 ── */
.output-panel { width: 380px; background: #16181c; border-left: 1px solid #2f3336; padding: 20px; overflow-y: auto; }
.output-panel h3 { font-size: .9rem; color: #fff; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.output-block { background: #1a1f29; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
.output-block h4 { font-size: .8rem; color: #1d9bf0; margin-bottom: 10px; }
.output-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #2f3336; font-size: .8rem; }
.output-item:last-child { border-bottom: none; }
.output-label { color: #71767b; }
.output-value { color: #e7e9ea; font-weight: 500; }

/* ── 广告卡片 ── */
.ad-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 16px; margin-top: 12px; }
.ad-card-title { font-size: .7rem; color: rgba(255,255,255,.7); margin-bottom: 8px; }
.ad-headline { font-size: .85rem; color: #fff; margin-bottom: 6px; }
.ad-headline span { font-size: .65rem; color: rgba(255,255,255,.5); margin-left: 8px; }
.ad-desc { font-size: .8rem; color: rgba(255,255,255,.9); line-height: 1.5; }

/* ── 打字指示器 ── */
.typing { display: flex; gap: 5px; padding: 14px 16px; }
.typing span { width: 7px; height: 7px; background: #71767b; border-radius: 50%; animation: blink 1.2s infinite; }
.typing span:nth-child(2) { animation-delay: .2s; }
.typing span:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%,80%,100% { opacity:.2; } 40% { opacity:1; } }
</style>
</head>
<body>

<!-- 左侧边栏 -->
<aside class="sidebar">
  <div class="sidebar-header">
    <div class="sidebar-title">🎯 广告优化 Agent</div>
    <div class="sidebar-subtitle">Amazon 联盟营销专用</div>
  </div>
  
  <div class="sidebar-status">
    <div class="status-indicator">
      <div class="status-dot" id="statusDot"></div>
      <span id="statusText">检测中...</span>
    </div>
  </div>
  
  <nav class="sidebar-nav">
    <a href="/agent_chat" class="nav-item">🤖 Agent 对话</a>
    <a href="/agent_sop" class="nav-item active">📊 优化 SOP</a>
    <a href="/optimize" class="nav-item">📈 投放优化</a>
    <a href="/plans" class="nav-item">📋 广告方案</a>
    
    <a href="/" class="nav-item back">← 返回首页</a>
  </nav>
</aside>

<!-- 主内容区 -->
<main class="main">
  <div class="topbar">
    <div>
      <span class="topbar-title">广告优化 SOP</span>
    </div>
    <span class="topbar-badge">SOP 模式</span>
  </div>
  
  <div style="display: flex; flex: 1; overflow: hidden;">
    <!-- 聊天区 -->
    <div class="chat-area" id="chatArea">
      <!-- 欢迎界面 -->
      <div class="welcome" id="welcome">
        <div class="welcome-icon">🎯</div>
        <h2>广告优化 SOP Agent</h2>
        <p>上传您的 Google Ads 广告数据文件，我将按照固化流程进行诊断、优化，并生成清洁版广告文案。</p>
        
        <div class="welcome-features">
          <div class="feature-card">
            <div class="feature-icon">📊</div>
            <div class="feature-name">数据诊断</div>
            <div class="feature-desc">P0/P1/P2 分级问题</div>
          </div>
          <div class="feature-card">
            <div class="feature-icon">💰</div>
            <div class="feature-name">利润分析</div>
            <div class="feature-desc">CPA/CPS/ROI</div>
          </div>
          <div class="feature-card">
            <div class="feature-icon">🎯</div>
            <div class="feature-name">优化建议</div>
            <div class="feature-desc">可执行策略</div>
          </div>
          <div class="feature-card">
            <div class="feature-icon">✨</div>
            <div class="feature-name">清洁广告</div>
            <div class="feature-desc">合规文案</div>
          </div>
        </div>
        
        <div class="quick-actions">
          <button class="quick-btn" onclick="quickAction('诊断')">📊 诊断广告数据</button>
          <button class="quick-btn" onclick="quickAction('优化')">✨ 优化广告文案</button>
          <button class="quick-btn" onclick="quickAction('生成')">📝 生成新广告</button>
        </div>
      </div>
    </div>
    
    <!-- 右侧输出面板 -->
    <div class="output-panel" id="outputPanel" style="display: none;">
      <h3>✨ 清洁版广告输出</h3>
      <div id="cleanOutput"></div>
    </div>
  </div>
  
  <!-- 输入区 -->
  <div class="input-area">
    <div class="file-preview" id="filePreview"></div>
    <div class="input-row">
      <textarea class="input-field" id="userInput" rows="1" placeholder="输入消息，或点击下方上传广告数据文件..." onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
      <button class="send-btn" id="sendBtn" onclick="sendMessage()">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </div>
    <div class="upload-zone" onclick="document.getElementById('fileInput').click()">
      <input type="file" id="fileInput" multiple accept=".csv,.xlsx,.xls,.pdf,.txt,.json" onchange="handleFiles(this.files)">
      <div class="upload-text">📎 点击或拖拽上传文件（支持 <span>CSV、Excel、PDF</span>）</div>
    </div>
  </div>
</main>

<script>
// ── 状态 ──────────────────────────────────────────────────────────────────────
var _messages = [];
var _files = [];
var _isStreaming = false;
var _currentModel = 'kimi-k2.5';

// ── 初始化 ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    checkAgentStatus();
});

function checkAgentStatus() {
    fetch('/api/agent_sop/health')
        .then(r => r.json())
        .then(d => {
            var dot = document.getElementById('statusDot');
            var text = document.getElementById('statusText');
            if (d.status === 'online') {
                dot.className = 'status-dot online';
                text.textContent = 'Agent 已连接';
            } else {
                dot.className = 'status-dot offline';
                text.textContent = 'Agent 未连接';
            }
        })
        .catch(() => {
            document.getElementById('statusDot').className = 'status-dot offline';
            document.getElementById('statusText').textContent = 'Agent 未连接';
        });
}

// ── 文件处理 ──────────────────────────────────────────────────────────────────
function handleFiles(files) {
    for (var i = 0; i < files.length; i++) {
        _files.push(files[i]);
    }
    renderFilePreview();
}

function renderFilePreview() {
    var container = document.getElementById('filePreview');
    container.innerHTML = _files.map(function(f, i) {
        return '<div class="file-tag"><span>📄</span><span>' + f.name + '</span><span class="remove" onclick="removeFile(' + i + ')">×</span></div>';
    }).join('');
}

function removeFile(index) {
    _files.splice(index, 1);
    renderFilePreview();
}

// ── 快捷操作 ──────────────────────────────────────────────────────────────────
function quickAction(type) {
    var templates = {
        '诊断': '请分析我上传的广告数据，按照SOP流程进行P0/P1/P2分级诊断。',
        '优化': '请基于上传的广告数据分析结果，进行广告优化并给出具体建议。',
        '生成': '请基于上传的产品信息，生成一套完整的Google Ads广告文案（标题+描述）。'
    };
    document.getElementById('userInput').value = templates[type] || '';
    document.getElementById('userInput').focus();
}

// ── 发送消息 ──────────────────────────────────────────────────────────────────
function sendMessage() {
    if (_isStreaming) return;
    var input = document.getElementById('userInput');
    var text = input.value.trim();
    if (!text && _files.length === 0) return;
    
    // 隐藏欢迎界面
    document.getElementById('welcome').style.display = 'none';
    
    // 添加用户消息
    addMessage('user', text, _files.slice());
    input.value = '';
    _files = [];
    renderFilePreview();
    
    // 开始流式请求
    streamResponse(text);
}

function streamResponse(messageText) {
    _isStreaming = true;
    var sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    
    // 构建文件信息
    var fileInfo = '';
    if (_messages.filter(function(m) { return m.role === 'user'; }).length === 1) {
        // 只在第一条消息时发送文件内容预览
        fileInfo = '\n\n[用户上传了 ' + _messages.filter(function(m) { return m.role === 'user'; }).reduce(function(acc, m) { return acc + (m.files ? m.files.length : 0); }, 0) + ' 个文件]';
    }
    
    fetch('/api/agent_sop/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: messageText + fileInfo,
            use_sop: true
        })
    })
    .then(function(response) {
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        
        // 添加 AI 消息占位
        var aiMsg = addMessage('assistant', '', []);
        
        function read() {
            reader.read().then(function(result) {
                if (result.done) {
                    _isStreaming = false;
                    sendBtn.disabled = false;
                    finishMessage(aiMsg);
                    return;
                }
                
                var chunk = decoder.decode(result.value);
                var lines = chunk.split('\n');
                
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];
                    if (line.startsWith('data: ')) {
                        try {
                            var data = JSON.parse(line.slice(6));
                            if (data.type === 'text') {
                                aiMsg.content += data.content;
                                renderMessage(aiMsg);
                            } else if (data.type === 'tool') {
                                aiMsg.tools = aiMsg.tools || [];
                                aiMsg.tools.push({
                                    name: data.name,
                                    input: data.input,
                                    status: 'running'
                                });
                                renderMessage(aiMsg);
                            } else if (data.type === 'tool_result') {
                                var tool = aiMsg.tools[aiMsg.tools.length - 1];
                                if (tool) {
                                    tool.status = data.isError ? 'error' : 'completed';
                                    tool.result = data.content;
                                    renderMessage(aiMsg);
                                }
                            } else if (data.type === 'done') {
                                extractCleanOutput(aiMsg.content);
                            }
                        } catch (e) {}
                    }
                }
                
                read();
            });
        }
        
        read();
    })
    .catch(function(err) {
        console.error('Error:', err);
        addMessage('assistant', '发生错误：' + err.message, []);
        _isStreaming = false;
        sendBtn.disabled = false;
    });
}

// ── 消息管理 ──────────────────────────────────────────────────────────────────
function addMessage(role, content, files) {
    var msg = {
        role: role,
        content: content,
        files: files,
        tools: [],
        time: new Date().toLocaleTimeString()
    };
    _messages.push(msg);
    renderMessage(msg);
    scrollToBottom();
    return msg;
}

function renderMessage(msg) {
    var chatArea = document.getElementById('chatArea');
    
    // 查找或创建消息元素
    var msgEl = chatArea.querySelector('[data-id="' + _messages.indexOf(msg) + '"]');
    if (!msgEl) {
        msgEl = document.createElement('div');
        msgEl.className = 'msg ' + msg.role;
        msgEl.setAttribute('data-id', _messages.indexOf(msg));
        msgEl.innerHTML = '<div class="msg-header"><div class="msg-avatar">' + (msg.role === 'user' ? '👤' : '🤖') + '</div><span class="msg-role">' + (msg.role === 'user' ? '你' : 'Agent') + '</span><span class="msg-time">' + msg.time + '</span></div><div class="msg-content"></div>';
        chatArea.appendChild(msgEl);
    }
    
    var contentEl = msgEl.querySelector('.msg-content');
    
    // 渲染文本
    var textHtml = escapeHtml(msg.content);
    if (msg.content === '' && msg.role === 'assistant' && !msg.tools.length) {
        textHtml = '<div class="typing"><span></span><span></span><span></span></div>';
    }
    
    // 渲染工具调用
    var toolsHtml = '';
    if (msg.tools && msg.tools.length) {
        for (var i = 0; i < msg.tools.length; i++) {
            var tool = msg.tools[i];
            toolsHtml += '<div class="tool-card"><div class="tool-header"><span class="tool-icon">🔧</span><span class="tool-name">' + tool.name + '</span><span class="tool-status ' + tool.status + '">' + tool.status + '</span></div>';
            if (tool.input) {
                toolsHtml += '<div class="tool-input">输入: ' + escapeHtml(JSON.stringify(tool.input, null, 2).slice(0, 200)) + '...</div>';
            }
            if (tool.result) {
                toolsHtml += '<div class="tool-result">' + escapeHtml(tool.result.slice(0, 150)) + '...</div>';
            }
            toolsHtml += '</div>';
        }
    }
    
    contentEl.innerHTML = textHtml + toolsHtml;
}

function finishMessage(msg) {
    // 标记消息完成
    msg.finished = true;
}

function scrollToBottom() {
    var chatArea = document.getElementById('chatArea');
    chatArea.scrollTop = chatArea.scrollHeight;
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
}

// ── 提取清洁输出 ──────────────────────────────────────────────────────────────
function extractCleanOutput(content) {
    var panel = document.getElementById('outputPanel');
    var container = document.getElementById('cleanOutput');
    
    // 简单解析：查找广告文案部分
    var adMatch = content.match(/\*\*Headline \d:\*\*\s*(.+)/gi);
    var descMatch = content.match(/\*\*Description:\*\*\s*(.+)/gi);
    
    if (adMatch && adMatch.length > 0) {
        panel.style.display = 'block';
        container.innerHTML = '<div class="ad-card"><div class="ad-card-title">Google Ads 文案</div>' +
            adMatch.map(function(h) { return '<div class="ad-headline">' + h.replace(/\*\*/g, '') + '</div>'; }).join('') +
            (descMatch ? '<div class="ad-desc">' + descMatch[0].replace(/\*\*/g, '') + '</div>' : '') +
            '</div>';
    }
}

// ── 工具函数 ──────────────────────────────────────────────────────────────────
function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// ── 清空对话 ──────────────────────────────────────────────────────────────────
function clearChat() {
    _messages = [];
    document.getElementById('chatArea').innerHTML = '';
    document.getElementById('welcome').style.display = 'block';
    document.getElementById('outputPanel').style.display = 'none';
}
</script>
</body>
</html>"""
    return html


# ─── API 路由 ─────────────────────────────────────────────────────────────────
@bp.route("/api/agent_sop/health", methods=["GET"])
def check_health():
    """检查 Agent 后端状态"""
    try:
        import requests as _requests
        resp = _requests.get(f"{AGENT_BACKEND_URL}/api/health", timeout=3)
        return jsonify({
            "status": "online" if resp.status_code == 200 else "offline",
            "data": resp.json() if resp.status_code == 200 else {}
        })
    except Exception as e:
        return jsonify({
            "status": "offline",
            "error": str(e)
        })


@bp.route("/api/agent_sop/chat", methods=["POST"])
def chat_sop():
    """
    SOP 对话 API（流式 SSE）
    
    请求: { message, use_sop }
    响应: SSE stream
    """
    data = request.get_json()
    message = data.get("message", "")
    use_sop = data.get("use_sop", True)
    
    def generate():
        try:
            import requests as _requests
            
            # 调用 Agent 后端
            resp = _requests.post(
                f"{AGENT_BACKEND_URL}/api/chat",
                json={
                    "message": message,
                    "systemPrompt": SOP_SYSTEM_PROMPT if use_sop else None,
                    "permissionMode": "bypassPermissions"
                },
                stream=True,
                timeout=300
            )
            
            for chunk in resp.iter_content(chunk_size=None):
                if chunk:
                    yield chunk
                    
        except Exception as e:
            yield f'data: {json.dumps({"type": "error", "message": str(e)})}\n\n'.encode()
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@bp.route("/api/agent_sop/upload", methods=["POST"])
def upload_file():
    """文件上传 API"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
    
    content = file.read()
    file_id = str(uuid.uuid4())
    
    file_storage[file_id] = {
        "file_id": file_id,
        "name": file.filename,
        "size": len(content),
        "uploaded_at": datetime.now().isoformat(),
        "content_base64": base64.b64encode(content).decode('utf-8'),
        "content_preview": content[:500].decode('utf-8', errors='ignore') if content else ""
    }
    
    return jsonify({
        "success": True,
        **file_storage[file_id]
    })
