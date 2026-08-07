/**
 * Facts Desk / Antar chat UI — renders API cards by `type` only.
 * Never invents citation labels or advisory copy.
 */

const API_BASE = (() => {
  const params = new URLSearchParams(window.location.search);
  return (params.get("api") || "").replace(/\/$/, "") || "";
})();

const ASK_URL = `${API_BASE}/ask`;

const EXAMPLES = [
  "What is the expense ratio of HDFC Mid Cap Fund?",
  "What is the exit load on HDFC Small Cap Fund?",
  "What is the minimum SIP for HDFC Nifty 50 Index Fund?",
];

const FEEDBACK_REASONS = [
  "wrong number",
  "outdated",
  "not what I asked",
  "no source",
  "other",
];

const SESSION_KEY = "antar_session_id";
const FEEDBACK_KEY = "antar_feedback";

/** Inline SVGs — never ligature icon fonts (names must not render as text). */
const ICONS = {
  bot: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>`,
  send: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`,
  edit: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>`,
  doc: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`,
  external: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>`,
  info: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  searchOff: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="8" x2="14" y2="14"/></svg>`,
  arrow: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>`,
  warning: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  cloudOff: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22.61 16.95A5 5 0 0 0 18 10h-1.26A8 8 0 0 0 4 14.25"/><path d="m1 1 22 22"/><path d="M8 16h.01"/><path d="M16 16h2"/></svg>`,
  refresh: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>`,
  thumbUp: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>`,
  thumbDown: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>`,
  copy: `<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
};

function icon(name, className = "") {
  const svg = ICONS[name];
  if (!svg) return "";
  return `<span class="icon ${className}" aria-hidden="true">${svg}</span>`;
}

/** @type {string} */
let sessionId = loadSessionId();
/** @type {string | null} */
let lastUserQuery = null;
/** @type {boolean} */
let busy = false;

const el = {
  welcome: document.getElementById("welcome"),
  thread: document.getElementById("thread"),
  examples: document.getElementById("example-chips"),
  form: document.getElementById("ask-form"),
  input: document.getElementById("ask-input"),
  send: document.getElementById("btn-send"),
  newChat: document.getElementById("btn-new-chat"),
  main: document.getElementById("main"),
};

function loadSessionId() {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing && /^[A-Za-z0-9_-]{8,128}$/.test(existing)) return existing;
  } catch (_) {
    /* ignore */
  }
  const id =
    crypto.randomUUID?.() ||
    `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
  try {
    localStorage.setItem(SESSION_KEY, id);
  } catch (_) {
    /* ignore */
  }
  return id;
}

function persistSession(id) {
  sessionId = id;
  try {
    localStorage.setItem(SESSION_KEY, id);
  } catch (_) {
    /* ignore */
  }
}

function loadFeedbackMap() {
  try {
    return JSON.parse(localStorage.getItem(FEEDBACK_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function saveFeedback(auditId, payload) {
  if (!auditId) return;
  const map = loadFeedbackMap();
  map[auditId] = { ...payload, saved_at: new Date().toISOString() };
  try {
    localStorage.setItem(FEEDBACK_KEY, JSON.stringify(map));
  } catch (_) {
    /* ignore */
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Emphasize numeric tokens in API text for display only. */
function formatAnswerText(text) {
  const safe = escapeHtml(text || "");
  return safe.replace(
    /(\d+(?:\.\d+)?%?|\d{1,3}(?:,\d{3})+(?:\.\d+)?)/g,
    '<span class="num-em">$1</span>'
  );
}

function showThread() {
  el.welcome.classList.add("hidden");
  el.thread.classList.remove("hidden");
  el.thread.classList.add("flex");
}

function resetChat() {
  el.thread.innerHTML = "";
  el.thread.classList.add("hidden");
  el.thread.classList.remove("flex");
  el.welcome.classList.remove("hidden");
  lastUserQuery = null;
  busy = false;
  setBusy(false);
  el.input.focus();
}

function setBusy(on) {
  busy = on;
  el.send.disabled = on;
  el.input.disabled = on;
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  });
}

function appendUserBubble(text) {
  showThread();
  const wrap = document.createElement("div");
  wrap.className = "flex flex-col gap-unit items-end w-full mb-2";
  wrap.innerHTML = `
    <div class="bg-surface-variant text-on-surface px-4 py-3 rounded-2xl rounded-tr-sm max-w-[85%] self-end">
      <p class="text-body-lg whitespace-pre-wrap">${escapeHtml(text)}</p>
    </div>`;
  el.thread.appendChild(wrap);
  scrollToBottom();
}

function assistantShell() {
  const root = document.createElement("div");
  root.className = "flex flex-col gap-2 w-full max-w-[95%] mb-2";
  root.innerHTML = `
    <div class="flex items-center gap-2 mb-1 px-1">
      <div class="w-6 h-6 rounded-full bg-primary flex items-center justify-center shrink-0">
        <span class="material-symbols-outlined text-on-primary text-[14px]">smart_toy</span>
      </div>
      <span class="text-label-caps text-on-surface-variant tracking-wider uppercase">Antar</span>
    </div>
    <div data-slot="body"></div>`;
  el.thread.appendChild(root);
  return root.querySelector("[data-slot=body]");
}

function loadingCard(stage) {
  const label =
    stage === "accepted"
      ? "Connecting…"
      : stage === "cache_hit"
        ? "Loading cached answer…"
        : "Antar is finding the facts…";
  const node = document.createElement("div");
  node.dataset.loading = "1";
  node.className =
    "bg-surface-container-lowest text-on-surface border border-surface-container-highest rounded-2xl rounded-tl-sm p-4 flex items-center gap-3 w-fit shadow-[0_2px_8px_rgba(0,0,0,0.02)]";
  node.innerHTML = `
    <div class="flex space-x-1" aria-hidden="true">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
    <span class="text-body-sm text-on-surface-variant animate-pulse" data-stage-label>${escapeHtml(label)}</span>`;
  return node;
}

function updateLoadingLabel(node, stage) {
  const labelEl = node.querySelector("[data-stage-label]");
  if (!labelEl) return;
  if (stage === "accepted") labelEl.textContent = "Connecting…";
  else if (stage === "generating") labelEl.textContent = "Antar is finding the facts…";
  else if (stage === "cache_hit") labelEl.textContent = "Loading cached answer…";
  else if (stage === "generated") labelEl.textContent = "Preparing answer…";
}

function renderCard(card, meta) {
  const type = card && card.type;
  switch (type) {
    case "answer":
      return renderAnswerCard(card, meta);
    case "refusal":
      return renderRefusalCard(card, meta);
    case "coverage":
      return renderCoverageCard(card, meta);
    case "performance_redirect":
      return renderPerformanceCard(card, meta);
    case "clarify":
      return renderClarifyCard(card, meta);
    case "api_error":
      return renderApiErrorCard(card, meta);
    default:
      return renderUnknownCard(card);
  }
}

function feedbackFooter(meta, copyText) {
  const auditId = meta?.audit_id || "";
  const saved = auditId ? loadFeedbackMap()[auditId] : null;
  const wrap = document.createElement("div");
  wrap.className = "border-t border-surface-container-highest px-card-padding py-3";
  wrap.innerHTML = `
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-1" data-thumbs>
        <button type="button" class="thumb-btn w-8 h-8 rounded-full flex items-center justify-center text-on-surface-variant/70 hover:bg-surface-container transition-colors" data-vote="up" aria-label="Helpful" aria-pressed="false">
          <span class="material-symbols-outlined text-[18px]">thumb_up</span>
        </button>
        <button type="button" class="thumb-btn w-8 h-8 rounded-full flex items-center justify-center text-on-surface-variant/70 hover:bg-surface-container transition-colors" data-vote="down" aria-label="Not helpful" aria-pressed="false">
          <span class="material-symbols-outlined text-[18px]">thumb_down</span>
        </button>
        <div class="w-px h-4 bg-surface-container-highest mx-1"></div>
        <button type="button" class="w-8 h-8 rounded-full flex items-center justify-center text-on-surface-variant/70 hover:bg-surface-container transition-colors" data-copy aria-label="Copy answer">
          <span class="material-symbols-outlined text-[18px]">content_copy</span>
        </button>
      </div>
    </div>
    <div data-reasons class="hidden mt-3 flex flex-wrap gap-2"></div>
    <p data-feedback-note class="hidden mt-2 text-body-sm text-on-surface-variant"></p>`;

  const reasonsEl = wrap.querySelector("[data-reasons]");
  const noteEl = wrap.querySelector("[data-feedback-note]");
  const copyBtn = wrap.querySelector("[data-copy]");

  FEEDBACK_REASONS.forEach((reason) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className =
      "reason-chip px-3 py-1.5 rounded-full border border-outline-variant text-body-sm text-on-surface-variant hover:bg-surface-container-low transition-colors";
    chip.textContent = reason;
    chip.dataset.reason = reason;
    chip.setAttribute("aria-pressed", "false");
    chip.addEventListener("click", () => {
      const vote =
        wrap.querySelector('.thumb-btn[aria-pressed="true"]')?.dataset.vote ||
        "down";
      reasonsEl.querySelectorAll(".reason-chip").forEach((c) => {
        c.setAttribute("aria-pressed", c === chip ? "true" : "false");
      });
      saveFeedback(auditId, {
        vote,
        reason,
        session_id: sessionId,
        audit_id: auditId,
      });
      noteEl.textContent = "Thanks — feedback saved.";
      noteEl.classList.remove("hidden");
    });
    reasonsEl.appendChild(chip);
  });

  wrap.querySelectorAll("[data-vote]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const vote = btn.dataset.vote;
      wrap.querySelectorAll("[data-vote]").forEach((b) => {
        b.setAttribute("aria-pressed", b === btn ? "true" : "false");
      });
      if (vote === "down") {
        reasonsEl.classList.remove("hidden");
        reasonsEl.classList.add("flex");
      } else {
        reasonsEl.classList.add("hidden");
        reasonsEl.classList.remove("flex");
        saveFeedback(auditId, {
          vote: "up",
          reason: null,
          session_id: sessionId,
          audit_id: auditId,
        });
        noteEl.textContent = "Thanks — feedback saved.";
        noteEl.classList.remove("hidden");
      }
    });
  });

  copyBtn?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(copyText || "");
      noteEl.textContent = "Copied.";
      noteEl.classList.remove("hidden");
    } catch {
      noteEl.textContent = "Could not copy.";
      noteEl.classList.remove("hidden");
    }
  });

  if (saved?.vote) {
    const btn = wrap.querySelector(`[data-vote="${saved.vote}"]`);
    if (btn) btn.setAttribute("aria-pressed", "true");
    if (saved.vote === "down") {
      reasonsEl.classList.remove("hidden");
      reasonsEl.classList.add("flex");
      if (saved.reason) {
        const chip = [...reasonsEl.querySelectorAll(".reason-chip")].find(
          (c) => c.dataset.reason === saved.reason
        );
        if (chip) chip.setAttribute("aria-pressed", "true");
      }
    }
  }

  return wrap;
}

function buildCopyText(parts) {
  return parts.filter(Boolean).join("\n\n");
}

function renderAnswerCard(card, meta) {
  const text = typeof card.text === "string" ? card.text : "";
  const citationUrl =
    typeof card.citation_url === "string" ? card.citation_url : null;
  const sourceLabel =
    typeof card.source_label === "string" ? card.source_label : null;
  const freshness =
    typeof card.freshness_date === "string" ? card.freshness_date : null;

  let sourceBlock = "";
  if (citationUrl) {
    const label = sourceLabel || "Source";
    sourceBlock = `
      <div class="flex flex-wrap items-center gap-2 mb-4">
        <a class="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-surface-container-low hover:bg-surface-container transition-colors rounded-lg border border-surface-container-highest text-on-surface-variant text-body-sm no-underline group"
           href="${escapeHtml(citationUrl)}" target="_blank" rel="noopener noreferrer">
          <span class="material-symbols-outlined text-[16px] text-primary">description</span>
          <span>${escapeHtml(label)}</span>
          <span class="material-symbols-outlined text-[14px] opacity-50 ml-0.5">open_in_new</span>
        </a>
      </div>`;
  }

  const root = document.createElement("div");
  root.className =
    "bg-surface-container-lowest text-on-surface border border-surface-container-highest rounded-2xl rounded-tl-sm overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.02)]";

  const body = document.createElement("div");
  body.className = "p-card-padding";
  body.innerHTML = `
    <p class="text-body-lg leading-relaxed whitespace-pre-wrap${sourceBlock ? " mb-4" : ""}">${formatAnswerText(text)}</p>
    ${sourceBlock}`;
  root.appendChild(body);

  if (freshness) {
    const fresh = document.createElement("div");
    fresh.className =
      "px-card-padding pb-2 text-body-sm text-on-surface-variant/70";
    fresh.textContent = `Last updated from sources: ${freshness}`;
    root.appendChild(fresh);
  }

  root.appendChild(
    feedbackFooter(
      meta,
      buildCopyText([
        text,
        citationUrl
          ? `Source: ${sourceLabel || citationUrl}\n${citationUrl}`
          : null,
        freshness ? `Last updated from sources: ${freshness}` : null,
      ])
    )
  );
  return root;
}

function renderRefusalCard(card, meta) {
  const text = typeof card.text === "string" ? card.text : "";
  const edu =
    typeof card.educational_url === "string" && card.educational_url
      ? card.educational_url
      : null;

  const root = document.createElement("div");
  root.className =
    "bg-surface-container-lowest rounded-2xl rounded-tl-sm border border-outline-variant/50 overflow-hidden shadow-sm";
  root.innerHTML = `
    <div class="px-card-padding py-3">
      <p class="text-body-lg text-on-surface whitespace-pre-wrap">${escapeHtml(text)}</p>
    </div>`;

  if (edu) {
    const bar = document.createElement("div");
    bar.className =
      "px-card-padding py-3 border-t border-outline-variant/30 bg-surface-container-lowest/50";
    bar.innerHTML = `
      <a class="flex items-center gap-2 text-primary text-body-sm font-medium hover:opacity-80 transition-opacity no-underline"
         href="${escapeHtml(edu)}" target="_blank" rel="noopener noreferrer">
        <span class="material-symbols-outlined text-[16px]">info</span>
        <span>Learn more</span>
        <span class="material-symbols-outlined text-[14px] opacity-50">open_in_new</span>
      </a>`;
    root.appendChild(bar);
  }

  root.appendChild(feedbackFooter(meta, buildCopyText([text, edu])));
  return root;
}

function renderCoverageCard(card, meta) {
  const text = typeof card.text === "string" ? card.text : "";
  const citationUrl =
    typeof card.citation_url === "string" ? card.citation_url : null;
  const sourceLabel =
    typeof card.source_label === "string" ? card.source_label : null;
  const freshness =
    typeof card.freshness_date === "string" ? card.freshness_date : null;

  const outer = document.createElement("div");
  outer.className =
    "bg-surface-container-lowest rounded-2xl rounded-tl-sm border border-outline-variant/50 overflow-hidden shadow-sm";

  const bodyWrap = document.createElement("div");
  bodyWrap.className = "p-card-padding";
  bodyWrap.innerHTML = `
    <div class="flex gap-3 items-start">
      <span class="material-symbols-outlined text-outline mt-0.5 shrink-0">search_off</span>
      <div class="flex flex-col gap-3 min-w-0 flex-1">
        <p class="text-body-lg text-on-surface whitespace-pre-wrap">${escapeHtml(text)}</p>
        <div data-extra class="flex flex-col gap-2"></div>
      </div>
    </div>`;

  const extra = bodyWrap.querySelector("[data-extra]");
  if (citationUrl && extra) {
    const label = sourceLabel || "Source";
    const a = document.createElement("a");
    a.href = citationUrl;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.className =
      "inline-flex items-center gap-1.5 text-primary text-body-sm font-medium no-underline";
    a.innerHTML = `<span class="material-symbols-outlined text-[16px]">description</span><span>${escapeHtml(label)}</span>`;
    extra.appendChild(a);
  }
  if (freshness && extra) {
    const p = document.createElement("p");
    p.className = "text-body-sm text-on-surface-variant/70";
    p.textContent = `Last updated from sources: ${freshness}`;
    extra.appendChild(p);
  }

  outer.appendChild(bodyWrap);
  outer.appendChild(
    feedbackFooter(
      meta,
      buildCopyText([
        text,
        citationUrl ? `${sourceLabel || "Source"}: ${citationUrl}` : null,
        freshness ? `Last updated from sources: ${freshness}` : null,
      ])
    )
  );
  return outer;
}

function renderPerformanceCard(card, meta) {
  const text = typeof card.text === "string" ? card.text : "";
  const schemeUrl =
    typeof card.scheme_url === "string" && card.scheme_url
      ? card.scheme_url
      : null;

  const root = document.createElement("div");
  root.className =
    "bg-surface-container-lowest rounded-2xl rounded-tl-sm border border-outline-variant/50 overflow-hidden shadow-sm";
  root.innerHTML = `
    <div class="px-card-padding py-3">
      <p class="text-body-lg text-on-surface whitespace-pre-wrap">${escapeHtml(text)}</p>
    </div>`;

  if (schemeUrl) {
    const bar = document.createElement("div");
    bar.className =
      "px-card-padding py-3 border-t border-outline-variant/30 bg-surface-container-lowest/50";
    bar.innerHTML = `
      <a class="inline-flex items-center justify-between w-full bg-primary text-on-primary px-4 py-2.5 rounded-lg text-body-sm font-medium transition-colors hover:bg-primary-container no-underline"
         href="${escapeHtml(schemeUrl)}" target="_blank" rel="noopener noreferrer">
        <span>View scheme page on Groww</span>
        <span class="material-symbols-outlined text-[18px]">open_in_new</span>
      </a>`;
    root.appendChild(bar);
  }

  root.appendChild(feedbackFooter(meta, buildCopyText([text, schemeUrl])));
  return root;
}

function renderClarifyCard(card, meta) {
  const text = typeof card.text === "string" ? card.text : "";
  const options = Array.isArray(card.options) ? card.options : [];
  const chips = options.slice(0, 3);

  const root = document.createElement("div");
  root.className =
    "bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden shadow-sm";
  root.innerHTML = `
    <div class="p-card-padding">
      <p class="text-body-lg text-on-surface mb-4 whitespace-pre-wrap">${escapeHtml(text)}</p>
      <div class="flex flex-col gap-2" data-chips></div>
    </div>`;

  const host = root.querySelector("[data-chips]");
  chips.forEach((opt) => {
    if (!opt || typeof opt !== "object") return;
    const label = typeof opt.label === "string" ? opt.label : null;
    if (!label) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "w-full text-left bg-surface hover:bg-surface-container-low transition-colors px-4 py-3 rounded-lg border border-outline-variant flex items-center justify-between group";
    btn.innerHTML = `
      <span class="text-body-sm font-medium text-on-surface pr-2">${escapeHtml(label)}</span>
      <span class="material-symbols-outlined text-on-surface-variant opacity-60 group-hover:opacity-100 transition-opacity">arrow_forward</span>`;
    btn.addEventListener("click", () => {
      const base = lastUserQuery || "Tell me about this scheme";
      ask(`${base} (${label})`);
    });
    host?.appendChild(btn);
  });

  root.appendChild(feedbackFooter(meta, text));
  return root;
}

function renderApiErrorCard(card, meta) {
  const text = typeof card.text === "string" ? card.text : "Something went wrong.";
  const status =
    typeof card.status_code === "number" ? card.status_code : null;

  const root = document.createElement("div");
  root.className =
    "bg-surface-container-lowest border border-error/20 rounded-xl overflow-hidden shadow-sm relative";
  root.innerHTML = `
    <div class="absolute inset-0 bg-gradient-to-br from-error-container/20 to-transparent pointer-events-none"></div>
    <div class="relative z-10 p-card-padding flex flex-col gap-4">
      <div class="flex items-center gap-2 mb-1">
        <div class="w-6 h-6 rounded-full bg-error-container/50 flex items-center justify-center">
          <span class="material-symbols-outlined text-[14px] text-on-error-container">warning</span>
        </div>
        <span class="text-label-caps text-on-error-container uppercase tracking-widest">System</span>
        ${status != null ? `<span class="text-body-sm text-on-surface-variant">HTTP ${escapeHtml(String(status))}</span>` : ""}
      </div>
      <div class="flex items-start gap-3">
        <span class="material-symbols-outlined text-error mt-0.5">cloud_off</span>
        <p class="text-body-lg text-on-surface whitespace-pre-wrap">${escapeHtml(text)}</p>
      </div>
      <div class="flex justify-end pt-2">
        <button type="button" data-retry class="bg-transparent border border-outline-variant text-on-surface px-6 py-2 rounded-lg text-body-sm flex items-center gap-2 active:bg-surface-container transition-colors">
          <span class="material-symbols-outlined text-[18px]">refresh</span>
          Retry
        </button>
      </div>
    </div>`;

  root.querySelector("[data-retry]")?.addEventListener("click", () => {
    if (lastUserQuery) ask(lastUserQuery);
  });

  root.appendChild(feedbackFooter(meta, text));
  return root;
}

function renderUnknownCard(card) {
  const div = document.createElement("div");
  div.className =
    "bg-surface-container-lowest border border-outline-variant rounded-xl p-card-padding";
  div.innerHTML = `<p class="text-body-sm text-on-surface-variant">Unsupported card type.</p>`;
  return div;
}

async function parseSse(response, handlers) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() || "";
    for (const line of parts) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        const raw = line.slice(5).trim();
        if (!raw) continue;
        let data;
        try {
          data = JSON.parse(raw);
        } catch {
          continue;
        }
        handlers[eventName]?.(data);
        eventName = "message";
      } else if (line.trim() === "") {
        eventName = "message";
      }
    }
  }
}

async function ask(query) {
  const q = (query || "").trim();
  if (!q || busy) return;

  lastUserQuery = q;
  el.input.value = "";
  appendUserBubble(q);
  setBusy(true);

  const slot = assistantShell();
  const loading = loadingCard("accepted");
  slot.appendChild(loading);
  scrollToBottom();

  /** @type {object | null} */
  let card = null;
  /** @type {object} */
  let doneMeta = {};

  try {
    const res = await fetch(ASK_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "X-Session-Id": sessionId,
      },
      body: JSON.stringify({ query: q, session_id: sessionId, stream: true }),
    });

    const hdrSession = res.headers.get("X-Session-Id");
    if (hdrSession) persistSession(hdrSession);

    if (!res.ok) {
      let detail = `Request failed (${res.status})`;
      try {
        const errBody = await res.json();
        if (errBody?.detail?.text) detail = errBody.detail.text;
        else if (typeof errBody?.detail === "string") detail = errBody.detail;
      } catch (_) {
        /* ignore */
      }
      loading.remove();
      slot.appendChild(
        renderCard(
          { type: "api_error", text: detail, status_code: res.status },
          {}
        )
      );
      return;
    }

    await parseSse(res, {
      status: (data) => {
        if (data?.session_id) persistSession(data.session_id);
        if (data?.stage) updateLoadingLabel(loading, data.stage);
        scrollToBottom();
      },
      card: (data) => {
        card = data;
      },
      done: (data) => {
        doneMeta = data || {};
        if (data?.session_id) persistSession(data.session_id);
      },
    });

    loading.remove();
    if (card && typeof card.type === "string") {
      slot.appendChild(renderCard(card, doneMeta));
    } else {
      slot.appendChild(
        renderCard(
          {
            type: "api_error",
            text: "No response card received from the API.",
          },
          doneMeta
        )
      );
    }
  } catch (err) {
    loading.remove();
    slot.appendChild(
      renderCard(
        {
          type: "api_error",
          text:
            err?.message ||
            "Could not reach the API. Start the API (`python -m src.api.cli`) and open the UI via `python ui/serve.py`.",
        },
        {}
      )
    );
  } finally {
    setBusy(false);
    scrollToBottom();
  }
}

function initExamples() {
  EXAMPLES.forEach((text) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "w-full text-left bg-surface-container-lowest border border-outline-variant rounded-xl p-card-padding flex items-center justify-between group transition-colors active:bg-surface-container-low";
    btn.innerHTML = `
      <span class="text-body-lg text-on-surface pr-4">${escapeHtml(text)}</span>
      <span class="material-symbols-outlined text-on-surface-variant group-active:text-primary transition-colors">arrow_forward</span>`;
    btn.addEventListener("click", () => ask(text));
    el.examples.appendChild(btn);
  });
}

el.form.addEventListener("submit", (e) => {
  e.preventDefault();
  ask(el.input.value);
});

el.newChat.addEventListener("click", resetChat);

initExamples();
el.input.focus();
