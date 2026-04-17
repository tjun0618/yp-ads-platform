# -*- coding: utf-8 -*-
"""
routes_agent_chat.py
=====================
Agent 对话入口 — 与广告 Agent 自由对话
路由:
  GET  /agent_chat        — 聊天页面
  POST /api/agent_chat    — 流式对话 API（SSE）
"""

import os
import json
import time
import requests
from flask import Blueprint, Response, request, stream_with_context

bp = Blueprint("agent_chat", __name__)

# ─── API Key（仅从环境变量读取）─────────────────────────────────
KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
if not KIMI_API_KEY:
    print("[WARN] 未设置环境变量 KIMI_API_KEY")
KIMI_BASE_URL = "https://api.moonshot.cn/v1"

# ─── System Prompt ─────────────────────────────────────────────────────────────
AGENT_SYSTEM_PROMPT = """你是一个专业的 Google Ads 广告 Agent，专门服务于亚马逊联盟营销客。

## 你的专业领域
- Google Ads 广告创意（标题≤30字符，描述≤90字符，严格字符限制）
- 亚马逊联盟营销策略（佣金优化、ASIN 选品、ROI 分析）
- 美国市场投放（美式英语，美国消费者语言习惯）
- 关键词研究与否定词策略
- 广告质量评分优化

## 你可以做什么
1. **修改广告文案**：用户提供 ASIN 或商品信息，帮助优化标题和描述
2. **调教生成策略**：用户想改变广告风格（价格导向、痛点导向、社会证明等），帮助调整
3. **分析竞品**：分析竞争对手广告策略，给出差异化建议
4. **解答疑问**：回答 Google Ads、亚马逊联盟营销相关问题
5. **内容审核**：检查广告文案是否符合 Google 政策和字符限制

## 广告铁律（必须遵守）
- 标题：≤30字符（含空格）
- 描述：≤90字符（含空格）
- 语言：美式英语，禁止中文
- 禁止词：Guaranteed, Best, #1（除非有依据）
- 货币：$ 美元，度量单位：oz/lbs/ft

## 回复风格
- 中文回复（除非生成广告文案）
- 简洁直接，不废话
- 涉及广告文案时，自动标注字符数
- 给出具体可执行的建议，不给模糊意见

现在开始对话。用户有任何广告相关的问题、调教需求、内容修改，都可以直接说。"""


# ─── 聊天页面 ──────────────────────────────────────────────────────────────────
@bp.route("/agent_chat")
def agent_chat_page():
    html = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent 对话 — YP Affiliate</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #13151a; color: #e1e4e8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; height: 100vh; display: flex; flex-direction: column; }

/* ── 顶栏 ── */
.topbar { background: #1a1d27; border-bottom: 1px solid #23262f; padding: 0 28px; display: flex; align-items: center; gap: 20px; height: 56px; position: sticky; top: 0; z-index: 200; }
.topbar-title { font-size: 1.05rem; font-weight: 700; color: #fff; white-space: nowrap; }
.topbar-nav { display: flex; align-items: center; gap: 4px; }
.topbar-nav a { color: #adb5bd; text-decoration: none; font-size: .87rem; padding: 6px 12px; border-radius: 6px; transition: background .15s; }
.topbar-nav a:hover, .topbar-nav a.active { background: #23262f; color: #fff; }

/* ── 主体布局 ── */
.chat-wrap { flex: 1; display: flex; flex-direction: column; max-width: 900px; width: 100%; margin: 0 auto; padding: 0 20px; overflow: hidden; }

/* ── 消息列表 ── */
.messages { flex: 1; overflow-y: auto; padding: 24px 0 12px; display: flex; flex-direction: column; gap: 18px; }
.messages::-webkit-scrollbar { width: 5px; }
.messages::-webkit-scrollbar-track { background: transparent; }
.messages::-webkit-scrollbar-thumb { background: #3a3d4a; border-radius: 3px; }

/* ── 消息气泡 ── */
.msg { display: flex; gap: 12px; animation: fadeUp .25s ease; }
@keyframes fadeUp { from { opacity:0; transform: translateY(8px); } to { opacity:1; transform: translateY(0); } }
.msg.user { flex-direction: row-reverse; }
.avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }
.msg.user .avatar { background: #3b5bdb; }
.msg.assistant .avatar { background: #2d333d; }
.bubble { max-width: 78%; padding: 12px 16px; border-radius: 14px; line-height: 1.65; font-size: .93rem; white-space: pre-wrap; word-break: break-word; }
.msg.user .bubble { background: #3b5bdb; color: #fff; border-bottom-right-radius: 4px; }
.msg.assistant .bubble { background: #1e2130; color: #e1e4e8; border-bottom-left-radius: 4px; border: 1px solid #2d333d; }
.msg.assistant .bubble code { background: #0d1117; padding: 1px 5px; border-radius: 4px; font-family: monospace; font-size: .86em; color: #79c0ff; }
.msg.assistant .bubble pre { background: #0d1117; padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
.msg.assistant .bubble pre code { background: none; padding: 0; color: #e6edf3; }
.bubble strong { color: #fff; }
.bubble em { color: #adb5bd; }

/* ── 打字指示器 ── */
.typing { display: flex; gap: 5px; padding: 14px 16px; }
.typing span { width: 7px; height: 7px; background: #adb5bd; border-radius: 50%; animation: blink 1.2s infinite; }
.typing span:nth-child(2) { animation-delay: .2s; }
.typing span:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%,80%,100% { opacity:.2; } 40% { opacity:1; } }

/* ── 欢迎提示 ── */
.welcome { text-align: center; padding: 40px 20px; }
.welcome h2 { font-size: 1.4rem; color: #fff; margin-bottom: 10px; }
.welcome p { color: #6c757d; font-size: .9rem; line-height: 1.6; margin-bottom: 24px; }
.suggestions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
.suggestion-btn { background: #1e2130; border: 1px solid #2d333d; color: #adb5bd; padding: 8px 16px; border-radius: 20px; cursor: pointer; font-size: .85rem; transition: all .15s; }
.suggestion-btn:hover { background: #23273a; border-color: #3b5bdb; color: #fff; }

/* ── 输入区域 ── */
.input-wrap { padding: 16px 0 24px; }
.input-row { display: flex; gap: 10px; align-items: flex-end; background: #1e2130; border: 1px solid #2d333d; border-radius: 14px; padding: 10px 14px; transition: border-color .15s; }
.input-row:focus-within { border-color: #3b5bdb; }
#user-input { flex: 1; background: none; border: none; outline: none; color: #e1e4e8; font-size: .95rem; resize: none; line-height: 1.5; max-height: 160px; min-height: 24px; overflow-y: auto; font-family: inherit; }
#user-input::placeholder { color: #555d6b; }
.send-btn { background: #3b5bdb; border: none; color: #fff; width: 36px; height: 36px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: background .15s; }
.send-btn:hover:not(:disabled) { background: #4c6ef5; }
.send-btn:disabled { background: #2d333d; cursor: not-allowed; }
.send-btn svg { width: 16px; height: 16px; }

/* ── 清空按钮 ── */
.clear-btn { background: none; border: 1px solid #2d333d; color: #6c757d; font-size: .8rem; padding: 5px 12px; border-radius: 6px; cursor: pointer; transition: all .15s; white-space: nowrap; }
.clear-btn:hover { border-color: #e03131; color: #e03131; }

/* ── 工具栏 ── */
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.model-badge { font-size: .78rem; color: #555d6b; }
.model-badge span { color: #4c6ef5; }
</style>
</head>
<body>

<!-- 顶栏 -->
<div class="topbar">
  <span class="topbar-title">YP Affiliate 管理台</span>
  <nav class="topbar-nav">
    <a href="/yp_sync">🌐 全量同步</a>
    <a href="/yp_collect">⬇ YP采集</a>
    <a href="/amazon_scrape">🔄 Amazon采集</a>
    <a href="/merchants">🏬 商户管理</a>
    <a href="/">📦 商品列表</a>
    <a href="/plans">📋 广告方案</a>
    <a href="/qs_dashboard">⭐ 质量评分</a>
    <a href="/competitor_ads">🔍 竞品参考</a>
    <a href="/optimize" style="color:#ffa726">📈 投放优化</a>
    <a href="/agent_chat" class="active" style="color:#4c6ef5">🤖 Agent对话</a>
  </nav>
</div>

<!-- 聊天区域 -->
<div class="chat-wrap">
  <div class="toolbar">
    <div class="model-badge">模型：<span>kimi-k2.5</span> · 128K上下文</div>
    <button class="clear-btn" onclick="clearChat()">🗑 清空对话</button>
  </div>

  <div class="messages" id="messages">
    <!-- 欢迎界面 -->
    <div class="welcome" id="welcome">
      <h2>🤖 广告 Agent</h2>
      <p>你的专属 Google Ads 顾问。<br>调教广告风格、修改文案、分析策略——直接说就行。</p>
      <div class="suggestions">
        <button class="suggestion-btn" onclick="sendSuggestion(this)">我想让广告更偏价格驱动</button>
        <button class="suggestion-btn" onclick="sendSuggestion(this)">帮我检查这条标题的字符数</button>
        <button class="suggestion-btn" onclick="sendSuggestion(this)">什么类型的商品适合用恐惧诉求？</button>
        <button class="suggestion-btn" onclick="sendSuggestion(this)">给我3条痛点型描述的公式</button>
        <button class="suggestion-btn" onclick="sendSuggestion(this)">如何选择否定关键词？</button>
        <button class="suggestion-btn" onclick="sendSuggestion(this)">帮我优化这条描述：</button>
      </div>
    </div>
  </div>

  <!-- 输入区 -->
  <div class="input-wrap">
    <div class="input-row">
      <textarea id="user-input" rows="1" placeholder="问我任何广告相关的问题，或者把要修改的文案粘贴进来…" onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
      <button class="send-btn" id="send-btn" onclick="sendMessage()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </div>
  </div>
</div>

<script>
// ── 状态 ──────────────────────────────────────────────────────────────────────
var _chatHistory = [];
var isStreaming = false;

// ── 工具函数 ─────────────────────────────────────────────────────────────────
function htmlEsc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

function scrollToBottom() {
  var msgs = document.getElementById('messages');
  msgs.scrollTop = msgs.scrollHeight;
}

function hideWelcome() {
  var w = document.getElementById('welcome');
  if (w) w.remove();
}

// ── 渲染 Markdown 简版 ──────────────────────────────────────────────────────
function renderMarkdown(text) {
  text = text.replace(/```([A-Za-z0-9_]*)\n?([\s\S]*?)```/g, function(_, lang, code) {
    return '<pre><code>' + htmlEsc(code.trim()) + '</code></pre>';
  });
  text = text.replace(/`([^`]+)`/g, function(_, c) { return '<code>' + htmlEsc(c) + '</code>'; });
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
  text = text.replace(/^### (.+)$/gm, '<strong style="font-size:1rem;display:block;margin:10px 0 4px">$1</strong>');
  text = text.replace(/^## (.+)$/gm, '<strong style="font-size:1.05rem;display:block;margin:12px 0 4px">$1</strong>');
  text = text.replace(/^# (.+)$/gm, '<strong style="font-size:1.1rem;display:block;margin:14px 0 6px">$1</strong>');
  text = text.replace(/\n/g, '<br>');
  return text;
}

// ── 追加消息气泡 ──────────────────────────────────────────────────────────────
function appendBubble(role, content, streaming) {
  var msgs = document.getElementById('messages');
  var div = document.createElement('div');
  div.className = 'msg ' + role;
  var avatar = role === 'user' ? '👤' : '🤖';
  div.innerHTML = '<div class="avatar">' + avatar + '</div>'
    + '<div class="bubble"></div>';
  msgs.appendChild(div);
  var bubble = div.querySelector('.bubble');
  if (streaming) {
    bubble.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
  } else {
    bubble.innerHTML = renderMarkdown(content);
  }
  scrollToBottom();
  return bubble;
}

// ── 发送消息（XMLHttpRequest，兼容所有浏览器）───────────────────────────────
function sendMessage() {
  if (isStreaming) return;
  var input = document.getElementById('user-input');
  var text = input.value.trim();
  if (!text) return;

  hideWelcome();
  isStreaming = true;
  document.getElementById('send-btn').disabled = true;
  input.value = '';
  input.style.height = 'auto';

  appendBubble('user', text, false);
  _chatHistory.push({role: 'user', content: text});

  var bubble = appendBubble('assistant', '', true);
  var fullText = '';
  var xhr = new XMLHttpRequest();

  xhr.open('POST', '/api/agent_chat', true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.timeout = 180000;

  var lastIdx = 0;
  xhr.onprogress = function() {
    var newData = xhr.responseText.substring(lastIdx);
    lastIdx = xhr.responseText.length;
    var lines = newData.split('\n');
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.indexOf('data: ') === 0) {
        var data = line.substring(6).trim();
        if (data === '[DONE]') break;
        try {
          var obj = JSON.parse(data);
          if (obj.text) {
            fullText += obj.text;
            bubble.innerHTML = renderMarkdown(fullText);
            scrollToBottom();
          }
          if (obj.error) {
            bubble.innerHTML = '<span style="color:#e03131">Error: ' + htmlEsc(obj.error) + '</span>';
          }
        } catch(e) {}
      }
    }
  };

  xhr.onload = function() {
    if (xhr.status >= 200 && xhr.status < 300) {
      // 处理 onload 时剩余的 chunk
      if (fullText) {
        _chatHistory.push({role: 'assistant', content: fullText});
        if (_chatHistory.length > 40) _chatHistory.splice(0, 2);
      }
    } else {
      if (!fullText || fullText.indexOf('Error') === -1) {
        bubble.innerHTML = '<span style="color:#e03131">HTTP ' + xhr.status + ': ' + htmlEsc(xhr.responseText.substring(0, 200)) + '</span>';
      }
    }
    isStreaming = false;
    document.getElementById('send-btn').disabled = false;
    scrollToBottom();
  };

  xhr.onerror = function() {
    bubble.innerHTML = '<span style="color:#e03131">Network error</span>';
    isStreaming = false;
    document.getElementById('send-btn').disabled = false;
  };

  xhr.ontimeout = function() {
    bubble.innerHTML = '<span style="color:#e03131">Request timed out</span>';
    isStreaming = false;
    document.getElementById('send-btn').disabled = false;
  };

  // 先触发一次 onprogress 来清掉 typing 指示器
  bubble.innerHTML = '';
  xhr.send(JSON.stringify({messages: _chatHistory}));
}

// ── 快捷建议 ─────────────────────────────────────────────────────────────────
function sendSuggestion(btn) {
  document.getElementById('user-input').value = btn.textContent;
  sendMessage();
}

// ── 回车发送 ─────────────────────────────────────────────────────────────────
function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

// ── 清空对话 ─────────────────────────────────────────────────────────────────
function clearChat() {
  _chatHistory.length = 0;
  var msgs = document.getElementById('messages');
  msgs.innerHTML = '<div class="welcome" id="welcome">'
    + '<h2>🤖 广告 Agent</h2>'
    + '<p>对话已清空，重新开始吧。</p>'
    + '</div>';
}
</script>
</body>
</html>"""
    return Response(html, mimetype="text/html; charset=utf-8")


# ─── 流式对话 API ─────────────────────────────────────────────────────────────
@bp.route("/api/agent_chat", methods=["POST"])
def api_agent_chat():
    """SSE 流式对话"""
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])

    if not messages:
        return Response(
            'data: {"error": "messages required"}\n\n',
            mimetype="text/event-stream",
        )

    # 构建请求体（多轮对话）
    api_messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    for m in messages[-20:]:  # 最多保留最近 20 条
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            api_messages.append({"role": role, "content": content})

    def generate():
        try:
            resp = requests.post(
                f"{KIMI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {KIMI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "kimi-k2.5",
                    "messages": api_messages,
                    "temperature": 1,
                    "max_tokens": 4096,
                    "stream": True,
                },
                stream=True,
                timeout=180,
            )

            if resp.status_code != 200:
                err = resp.text[:300]
                yield f"data: {json.dumps({'error': f'API 错误 {resp.status_code}: {err}'}, ensure_ascii=False)}\n\n"
                return

            for line in resp.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if not decoded.startswith("data: "):
                    continue
                raw = decoded[6:].strip()
                if raw == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                try:
                    obj = json.loads(raw)
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield f"data: {json.dumps({'text': content}, ensure_ascii=False)}\n\n"
                except Exception:
                    continue

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
