/**
 * ai-chat.js — Smart Farmer AI assistant chat UI.
 *
 * Exports:
 *   initAiChat(containerEl) — renders the chat interface inside containerEl
 *                              and wires up all interactivity.
 *
 * Requirements satisfied:
 *   14.6 — limitations block is prepended BEFORE the answer body.
 *   14.7 — degraded fallback shown when Gemini / network is unavailable.
 *   14.8 — HIGH-risk refusal displayed with a distinct amber badge.
 *   3.6  — GEMINI_API_KEY is NEVER placed in any frontend JS file.
 *   3.8  — 429 responses are surfaced to the farmer with retry guidance.
 */

import { apiFetch } from "./api.js";
import { t } from "./dom.js";

// ── Constants ─────────────────────────────────────────────────────────────────

/** Shown when the API returns non-200 or the network fails. (Req 14.7) */
const fallbackMsg = () => t("ai.unavailable");

/** Character limit matching the backend AIAskRequest.question max_length. */
const MAX_QUESTION_LEN = 2000;

// ── Template helpers ──────────────────────────────────────────────────────────

/**
 * Splits the AI response text into a limitations block and the answer body.
 *
 * The backend always prepends a limitations/warning paragraph that starts
 * with "⚠ Limitations:" before the main answer (Requirement 14.6).
 * We surface these two sections separately so the limitations can be
 * rendered visually above the answer.
 *
 * @param {string} text - Full response text from the API.
 * @returns {{ limitations: string, body: string }}
 */
function splitLimitationsAndBody(text) {
  if (!text) return { limitations: "", body: "" };

  // Match the limitations paragraph — starts with the ⚠ warning marker.
  // The block ends at the first blank line (double newline) after the marker.
  const LIMIT_RE = /^(⚠[^\n]*(?:\n(?!\n)[^\n]*)*)/m;
  const match = LIMIT_RE.exec(text);

  if (match) {
    const limitations = match[1].trim();
    const body = text.slice(match.index + match[0].length).trimStart();
    return { limitations, body };
  }

  // No limitations block found — treat everything as body.
  return { limitations: "", body: text };
}

/**
 * Converts plain-text line breaks and simple markdown (bold, bullet lists)
 * to safe HTML for display inside a message bubble. Uses text nodes where
 * possible to avoid XSS.
 *
 * @param {string} text
 * @returns {DocumentFragment}
 */
function textToFragment(text) {
  const frag = document.createDocumentFragment();
  const lines = text.split("\n");

  for (const line of lines) {
    if (!line.trim()) {
      frag.appendChild(document.createElement("br"));
      continue;
    }

    const p = document.createElement("p");
    p.style.margin = "0.25rem 0";

    // Detect bullet lines (- item or * item)
    if (/^[\-\*]\s/.test(line)) {
      p.style.paddingLeft = "1rem";
      p.textContent = "• " + line.slice(2);
    } else {
      // Render **bold** spans safely
      const parts = line.split(/(\*\*[^*]+\*\*)/g);
      for (const part of parts) {
        if (part.startsWith("**") && part.endsWith("**")) {
          const b = document.createElement("b");
          b.textContent = part.slice(2, -2);
          p.appendChild(b);
        } else {
          p.appendChild(document.createTextNode(part));
        }
      }
    }

    frag.appendChild(p);
  }

  return frag;
}

// ── UI builders ───────────────────────────────────────────────────────────────

/**
 * Creates the full chat UI DOM and appends it to containerEl.
 * Returns { messagesEl, inputEl, sendBtn, charCountEl } for wiring.
 *
 * @param {HTMLElement} containerEl
 */
function buildUI(containerEl) {
  containerEl.innerHTML = "";
  containerEl.setAttribute("role", "region");
  containerEl.setAttribute("aria-label", t("ai.region"));

  // ── Scrollable message thread ────────────────────────────────────────────
  const messagesEl = document.createElement("div");
  messagesEl.id = "ai-chat-messages";
  messagesEl.setAttribute("aria-live", "polite");
  messagesEl.setAttribute("aria-relevant", "additions");
  messagesEl.style.cssText = [
    "flex: 1 1 auto",
    "overflow-y: auto",
    "padding: 1rem",
    "display: flex",
    "flex-direction: column",
    "gap: 1rem",
    "min-height: 10rem",
    "max-height: min(50vh, 28rem)",
  ].join(";");

  // Welcome message
  const welcome = document.createElement("div");
  welcome.style.cssText =
    "background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:0.875rem 1rem;font-size:1rem;color:#14532D;line-height:1.6;";
  const welcomeTitle = document.createElement("strong");
  welcomeTitle.textContent = t("ai.welcome.title");
  welcome.appendChild(welcomeTitle);
  welcome.appendChild(document.createTextNode(" — " + t("ai.welcome.body")));
  messagesEl.appendChild(welcome);

  // ── Composer row ─────────────────────────────────────────────────────────
  const composerWrap = document.createElement("div");
  composerWrap.style.cssText = [
    "display: flex",
    "flex-direction: column",
    "gap: 0.5rem",
    "padding: 0.75rem 1rem",
    "border-top: 1px solid #E5E7EB",
    "background: #fff",
    "flex-shrink: 0",
  ].join(";");

  const inputRow = document.createElement("div");
  inputRow.style.cssText = "display:flex;gap:0.5rem;align-items:flex-end;";

  const inputEl = document.createElement("textarea");
  inputEl.id = "ai-chat-input";
  inputEl.placeholder = t("ai.inputPlaceholder");
  inputEl.setAttribute("aria-label", t("ai.inputLabel"));
  inputEl.setAttribute("rows", "2");
  inputEl.setAttribute("maxlength", String(MAX_QUESTION_LEN));
  inputEl.style.cssText = [
    "flex: 1 1 auto",
    "min-width: 0",
    "resize: vertical",
    "min-height: 2.75rem",
    "max-height: 7rem",
    "border: 1.5px solid #6B7280",
    "border-radius: 10px",
    "padding: 0.5rem 0.75rem",
    "font-size: 1rem",
    "font-family: inherit",
    "outline: none",
    "transition: border-color 0.15s",
  ].join(";");
  inputEl.addEventListener("focus", () => { inputEl.style.borderColor = "#4A7C59"; });
  inputEl.addEventListener("blur",  () => { inputEl.style.borderColor = "#D1D5DB"; });

  const sendBtn = document.createElement("button");
  sendBtn.type = "button";
  sendBtn.setAttribute("aria-label", t("ai.send"));
  sendBtn.style.cssText = [
    "flex-shrink: 0",
    "height: 2.75rem",
    "width: 2.75rem",
    "border-radius: 10px",
    "background: #1E3A2B",
    "color: #fff",
    "border: none",
    "cursor: pointer",
    "display: flex",
    "align-items: center",
    "justify-content: center",
    "font-size: 1rem",
    "transition: background 0.15s",
  ].join(";");
  sendBtn.innerHTML = '<i class="fa-solid fa-paper-plane" aria-hidden="true"></i>';
  sendBtn.addEventListener("mouseenter", () => { sendBtn.style.background = "#4A7C59"; });
  sendBtn.addEventListener("mouseleave", () => { sendBtn.style.background = "#1E3A2B"; });

  const charCountEl = document.createElement("span");
  charCountEl.style.cssText = "font-size:0.875rem;color:#4B5563;text-align:right;align-self:flex-end;";
  charCountEl.textContent = `0 / ${MAX_QUESTION_LEN}`;

  inputRow.appendChild(inputEl);
  inputRow.appendChild(sendBtn);
  composerWrap.appendChild(inputRow);
  composerWrap.appendChild(charCountEl);

  // Outer layout wrapper
  const wrapper = document.createElement("div");
  wrapper.style.cssText = [
    "display: flex",
    "flex-direction: column",
    "border: 1px solid #E5E7EB",
    "border-radius: 16px",
    "overflow: hidden",
    "background: #fff",
    "box-shadow: 0 1px 6px rgba(0,0,0,0.06)",
  ].join(";");
  wrapper.appendChild(messagesEl);
  wrapper.appendChild(composerWrap);

  containerEl.appendChild(wrapper);

  return { messagesEl, inputEl, sendBtn, charCountEl };
}

// ── Message bubble builders ───────────────────────────────────────────────────

/**
 * Appends a farmer (user) message bubble to the thread.
 *
 * @param {HTMLElement} messagesEl
 * @param {string} text
 */
function appendUserBubble(messagesEl, text) {
  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;justify-content:flex-end;";

  const bubble = document.createElement("div");
  bubble.style.cssText = [
    "max-width: 85%",
    "background: #1E3A2B",
    "color: #fff",
    "border-radius: 16px 16px 4px 16px",
    "padding: 0.625rem 0.875rem",
    "font-size: 1rem",
    "line-height: 1.6",
    "word-break: break-word",
  ].join(";");
  bubble.setAttribute("aria-label", t("ai.yourQuestion"));
  bubble.textContent = text;

  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/**
 * Appends a typing indicator (three bouncing dots) and returns the element
 * so it can be removed once the answer arrives.
 *
 * @param {HTMLElement} messagesEl
 * @returns {HTMLElement} The typing indicator element.
 */
function appendTypingIndicator(messagesEl) {
  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;align-items:center;gap:0.375rem;";
  wrap.setAttribute("aria-label", t("ai.thinking"));
  wrap.setAttribute("role", "status");
  wrap.setAttribute("aria-live", "off");

  const style = document.createElement("style");
  style.textContent = `
    @keyframes sf-bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }
    .sf-dot { width:7px;height:7px;border-radius:50%;background:#9CA3AF;animation:sf-bounce 1.4s infinite ease-in-out; }
    .sf-dot:nth-child(2){animation-delay:0.2s}
    .sf-dot:nth-child(3){animation-delay:0.4s}
  `;
  document.head.appendChild(style);

  [1, 2, 3].forEach(() => {
    const d = document.createElement("span");
    d.className = "sf-dot";
    wrap.appendChild(d);
  });

  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrap;
}

/**
 * Appends an AI response bubble.
 *
 * Requirement 14.6 — limitations block rendered BEFORE the body text.
 * Requirement 14.8 — HIGH-risk refusals show a distinct amber badge.
 *
 * @param {HTMLElement} messagesEl
 * @param {Object} opts
 * @param {string}  opts.responseText
 * @param {boolean} opts.isHighRisk
 * @param {boolean} opts.isFallback   — true for degraded / error messages
 */
function appendAiBubble(messagesEl, { responseText, isHighRisk, isFallback }) {
  const outerWrap = document.createElement("div");
  outerWrap.style.cssText = "display:flex;flex-direction:column;gap:0.375rem;max-width:95%;";

  // ── HIGH-risk refusal badge (Req 14.8) ──────────────────────────────────
  if (isHighRisk) {
    const badge = document.createElement("div");
    badge.setAttribute("role", "alert");
    badge.style.cssText = [
      "display: inline-flex",
      "align-items: center",
      "gap: 0.4rem",
      "background: #FEF3C7",
      "border: 1.5px solid #F59E0B",
      "color: #92400E",
      "font-size: 0.875rem",
      "font-weight: 700",
      "padding: 0.3rem 0.65rem",
      "border-radius: 8px",
      "width: fit-content",
    ].join(";");
    badge.textContent = "⚠ " + t("ai.refusalBadge");
    outerWrap.appendChild(badge);
  }

  // ── Fallback badge (Req 14.7) ────────────────────────────────────────────
  if (isFallback) {
    const badge = document.createElement("div");
    badge.setAttribute("role", "status");
    badge.style.cssText = [
      "display: inline-flex",
      "align-items: center",
      "gap: 0.4rem",
      "background: #F3F4F6",
      "border: 1px solid #D1D5DB",
      "color: #374151",
      "font-size: 0.875rem",
      "font-weight: 600",
      "padding: 0.3rem 0.65rem",
      "border-radius: 8px",
      "width: fit-content",
    ].join(";");
    badge.textContent = "✕ " + t("ai.unavailableBadge");
    outerWrap.appendChild(badge);
  }

  // ── Message bubble ───────────────────────────────────────────────────────
  const bubble = document.createElement("div");
  bubble.style.cssText = [
    "background: #F9FAFB",
    "border: 1px solid #E5E7EB",
    "border-radius: 4px 16px 16px 16px",
    "padding: 0.75rem 1rem",
    "font-size: 1rem",
    "line-height: 1.6",
    "color: #111827",
    "word-break: break-word",
    isHighRisk  ? "border-color:#F59E0B;background:#FFFBEB;" : "",
    isFallback  ? "border-color:#D1D5DB;color:#374151;"      : "",
  ].filter(Boolean).join(";");

  if (isFallback) {
    bubble.textContent = responseText;
  } else {
    // Split limitations from body (Req 14.6)
    const { limitations, body } = splitLimitationsAndBody(responseText);

    if (limitations) {
      const limBlock = document.createElement("div");
      limBlock.setAttribute("aria-label", t("ai.limitations.heading"));
      limBlock.style.cssText = [
        "background: #FFFBEB",
        "border: 1px solid #FDE68A",
        "border-radius: 8px",
        "padding: 0.5rem 0.75rem",
        "margin-bottom: 0.625rem",
        "font-size: 0.9375rem",
        "color: #78350F",
      ].join(";");
      limBlock.appendChild(textToFragment(limitations));
      bubble.appendChild(limBlock);
    }

    if (body) {
      const bodyWrap = document.createElement("div");
      bodyWrap.appendChild(textToFragment(body));
      bubble.appendChild(bodyWrap);
    }

    // If neither block has content, fall back to rendering the whole response
    if (!limitations && !body) {
      bubble.appendChild(textToFragment(responseText));
    }
  }

  outerWrap.appendChild(bubble);
  messagesEl.appendChild(outerWrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ── Core send logic ───────────────────────────────────────────────────────────

/**
 * Sends a question to POST /api/ai/ask and renders the response into the
 * message thread.
 *
 * @param {string}      question
 * @param {HTMLElement} messagesEl
 * @param {HTMLElement} inputEl
 * @param {HTMLElement} sendBtn
 */
async function sendQuestion(question, messagesEl, inputEl, sendBtn) {
  // Disable controls while request is in flight
  inputEl.disabled = true;
  sendBtn.disabled = true;
  sendBtn.style.opacity = "0.5";

  appendUserBubble(messagesEl, question);
  const indicator = appendTypingIndicator(messagesEl);

  let responseText = fallbackMsg();
  let isHighRisk   = false;
  let isFallback   = false;

  try {
    const res = await apiFetch("/api/ai/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    });

    // 429 is already handled (banner shown) by apiFetch; surface retry text.
    if (res.status === 429) {
      responseText = t("ai.rateLimited");
      isFallback   = true;
    } else if (!res.ok) {
      // Non-200, non-429 — degraded fallback (Req 14.7)
      responseText = fallbackMsg();
      isFallback   = true;
    } else {
      const data = await res.json();
      // The refusal text for chemical / dose questions is shown exactly as the server returned it.
      responseText = data.response ?? fallbackMsg();
      isHighRisk   = Boolean(data.is_high_risk_refusal);
      isFallback   = false;
    }
  } catch (_err) {
    // Network failure — degraded fallback (Req 14.7)
    responseText = fallbackMsg();
    isFallback   = true;
  }

  // Remove typing indicator, then render the reply
  indicator.remove();
  appendAiBubble(messagesEl, { responseText, isHighRisk, isFallback });

  // Keep the question in the box after a failure so the farmer can send it again
  if (isFallback) inputEl.value = question;

  // Re-enable controls
  inputEl.disabled = false;
  sendBtn.disabled = false;
  sendBtn.style.opacity = "1";
  inputEl.focus();
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Initialises the AI chat UI inside the provided container element.
 * Safe to call multiple times — the UI is rebuilt only once.
 *
 * @param {HTMLElement} containerEl - The DOM element to mount the chat inside.
 */
export function initAiChat(containerEl) {
  if (!containerEl) return;

  // Idempotent — skip if already initialised
  if (containerEl.dataset.aiChatReady === "1") return;
  containerEl.dataset.aiChatReady = "1";

  const { messagesEl, inputEl, sendBtn, charCountEl } = buildUI(containerEl);

  // ── Character counter ────────────────────────────────────────────────────
  inputEl.addEventListener("input", () => {
    const len = inputEl.value.length;
    charCountEl.textContent = `${len} / ${MAX_QUESTION_LEN}`;
    charCountEl.style.color = len > MAX_QUESTION_LEN * 0.9 ? "#EF4444" : "#9CA3AF";
  });

  // ── Send on button click ─────────────────────────────────────────────────
  const doSend = () => {
    const q = inputEl.value.trim();
    if (!q || inputEl.disabled) return;
    inputEl.value = "";
    charCountEl.textContent = `0 / ${MAX_QUESTION_LEN}`;
    charCountEl.style.color = "#9CA3AF";
    sendQuestion(q, messagesEl, inputEl, sendBtn);
  };

  sendBtn.addEventListener("click", doSend);

  // ── Send on Ctrl/Cmd + Enter ──────────────────────────────────────────────
  inputEl.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      doSend();
    }
  });
}
