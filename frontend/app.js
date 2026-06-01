// PantryPal chat UI — vanilla JS, streams SSE from /api/chat.

const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const resetBtn = document.getElementById("reset");

// Stable per-browser id so memory persists across sessions (Marcus's continuity).
let userId = localStorage.getItem("pantrypal_user");
if (!userId) {
  userId = "u_" + Math.random().toString(36).slice(2, 10);
  localStorage.setItem("pantrypal_user", userId);
}

// Full conversation history sent to the backend each turn.
const history = [];

const SUGGESTIONS = [
  "Something spicy and fast for dinner",
  "What can I make with chicken, rice, and lime?",
  "How do I know when chicken is done?",
  "I just got an air fryer — what should I make?",
];

function showWelcome() {
  chat.innerHTML = `
    <div class="welcome">
      <h2>Hey, I'm PantryPal 🍳</h2>
      <p>Tell me what you're in the mood for, or what's in your kitchen.</p>
      <div class="chips">
        ${SUGGESTIONS.map((s) => `<button class="chip">${s}</button>`).join("")}
      </div>
    </div>`;
  chat.querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => {
      input.value = c.textContent;
      form.requestSubmit();
    })
  );
}
showWelcome();

// --- minimal, safe markdown rendering ---
function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function renderMarkdown(text) {
  let t = escapeHtml(text);
  t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  // bullet lists
  t = t.replace(/(?:^|\n)[-*] (.+)/g, (_, item) => `\n<li>${item}</li>`);
  t = t.replace(/(<li>[\s\S]*?<\/li>)/g, (m) => `<ul>${m.replace(/\n/g, "")}</ul>`);
  // paragraphs / line breaks
  t = t
    .split(/\n{2,}/)
    .map((para) => (para.includes("<ul>") ? para : `<p>${para.replace(/\n/g, "<br>")}</p>`))
    .join("");
  return t;
}

function addMessage(role) {
  if (chat.querySelector(".welcome")) chat.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  wrap.appendChild(bubble);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return { wrap, bubble };
}

function setStatus(text) {
  let el = chat.querySelector(".status.live");
  if (!el) {
    el = document.createElement("div");
    el.className = "status live";
    chat.appendChild(el);
  }
  el.textContent = text;
  chat.scrollTop = chat.scrollHeight;
}
function clearStatus() {
  chat.querySelector(".status.live")?.remove();
}

async function send(text) {
  history.push({ role: "user", content: text });
  addMessage("user").bubble.textContent = text;

  sendBtn.disabled = true;
  setStatus("PantryPal is thinking…");

  let bot = null;
  let answer = "";

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, messages: history }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop();
      for (const line of lines) {
        const m = line.trim();
        if (!m.startsWith("data:")) continue;
        const evt = JSON.parse(m.slice(5).trim());
        if (evt.type === "tool") {
          setStatus(evt.label);
        } else if (evt.type === "token") {
          if (!bot) { clearStatus(); bot = addMessage("bot"); }
          answer += evt.text;
          bot.bubble.innerHTML = renderMarkdown(answer);
          chat.scrollTop = chat.scrollHeight;
        } else if (evt.type === "disclaimer") {
          const d = document.createElement("div");
          d.className = "disclaimer";
          d.textContent = evt.text;
          (bot ? bot.wrap : chat).appendChild(d);
        } else if (evt.type === "error") {
          clearStatus();
          if (!bot) bot = addMessage("bot");
          bot.bubble.textContent = evt.message;
        }
      }
    }
  } catch (e) {
    clearStatus();
    addMessage("bot").bubble.textContent = "Connection hiccup — try that again?";
  } finally {
    clearStatus();
    sendBtn.disabled = false;
    if (answer) history.push({ role: "assistant", content: answer });
    input.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || sendBtn.disabled) return;
  input.value = "";
  input.style.height = "auto";
  send(text);
});

// textarea: auto-grow + Enter to send (Shift+Enter = newline)
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 140) + "px";
});
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

resetBtn.addEventListener("click", async () => {
  if (!confirm("Forget everything PantryPal remembers about you?")) return;
  await fetch(`/api/memory/${userId}`, { method: "DELETE" });
  history.length = 0;
  showWelcome();
});
