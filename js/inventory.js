/**
 * inventory.js — Inventory list with consumption recording modal.
 *
 * Handles:
 *  - GET  /api/farmers/me/inventory             → inventory list
 *  - POST /api/farmers/me/inventory             → add inventory item
 *  - POST /api/farmers/me/inventory/{id}/consume → record consumption
 *
 * Field names follow backend/routers/inventory.py (expiry_date, purchase_price,
 * quantity_consumed). Inventory items are displayed as a farmer-entered
 * catalogue — never as endorsed products. Crop approval is NOT inferred from
 * product name. (Requirements 8.1, 8.3, 8.4)
 *
 * Requirements: 8.1, 8.2, 8.3, 8.4
 */

import { routeGuard, signOut } from "./auth.js";
import { apiFetch } from "./api.js";
import {
  applyI18n, errorMessage, escapeHtml, initPage, renderLoadError, setBusy, t,
} from "./dom.js";
import { formatDate, formatNumber } from "./translator.js";

// An item "expires soon" when its expiry date is within this many days.
// This is a display convenience for the headline count, not an agronomic value.
const EXPIRING_SOON_DAYS = 30;

// ── State ─────────────────────────────────────────────────────────────────────
let _inventory = [];
let _consumeTargetId = null;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const invList        = document.getElementById("inventory-list");
const invListEmpty   = document.getElementById("inventory-list-empty");
const invLoading     = document.getElementById("inventory-loading");
const headlineAttn   = document.getElementById("headline-attention");

const invFormWrap    = document.getElementById("inv-form-wrap");
const invFormToggle  = document.getElementById("btn-show-inv-form");
const invFormCancel  = document.getElementById("btn-cancel-inv-form");
const invForm        = document.getElementById("inv-form");
const invFormError   = document.getElementById("inv-form-error");
const invSaveBtn     = document.getElementById("btn-save-inv");

const consumeModal   = document.getElementById("consume-modal");
const consumeForm    = document.getElementById("consume-form");
const consumeError   = document.getElementById("consume-form-error");
const consumeItemName = document.getElementById("consume-item-name");
const consumeClose   = document.getElementById("btn-close-consume");
const consumeCancel  = document.getElementById("btn-cancel-consume");
const consumeSaveBtn = document.getElementById("btn-save-consume");

// ── Utilities ─────────────────────────────────────────────────────────────────
function setHidden(el, hidden) {
  if (el) el.classList.toggle("hidden", hidden);
}

function showError_(el, message) {
  el.textContent = message;
  el.classList.remove("hidden");
}

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return null;
  return Math.ceil((d.getTime() - Date.now()) / 86400000);
}

function itemState(item) {
  const days = daysUntil(item.expiry_date);
  return {
    expired: days !== null && days < 0,
    expiringSoon: days !== null && days >= 0 && days <= EXPIRING_SOON_DAYS,
    outOfStock: item.quantity_on_hand != null && Number(item.quantity_on_hand) <= 0,
  };
}

// ── Render inventory ──────────────────────────────────────────────────────────
function renderHeadline() {
  const n = _inventory.filter((i) => {
    const s = itemState(i);
    return s.expired || s.expiringSoon || s.outOfStock;
  }).length;
  if (headlineAttn) headlineAttn.textContent = formatNumber(n);
}

function badge(cls, key) {
  return `<span class="text-sm ${cls} px-2 py-0.5 rounded-full font-semibold">${escapeHtml(t(key))}</span>`;
}

function renderInventory() {
  setHidden(invLoading, true);
  invList.innerHTML = "";
  renderHeadline();

  if (!_inventory || _inventory.length === 0) {
    setHidden(invListEmpty, false);
    return;
  }
  setHidden(invListEmpty, true);

  _inventory.forEach((item) => {
    const st = itemState(item);

    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-xl p-4 shadow-sm";
    card.innerHTML = `
      <div class="flex flex-col gap-3">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2 mb-1">
            <h3 class="font-bold text-emerald-900 text-base break-words">${escapeHtml(item.product_name)}</h3>
            ${st.expired ? badge("bg-red-100 text-red-800", "inventory.expired") : ""}
            ${st.expiringSoon ? badge("bg-amber-100 text-amber-800", "inventory.expiringSoon") : ""}
            ${st.outOfStock && !st.expired ? badge("bg-amber-100 text-amber-800", "inventory.outOfStock") : ""}
          </div>

          <div class="flex flex-wrap gap-x-4 gap-y-0.5 text-sm text-gray-600 mt-1">
            ${item.active_ingredient ? `<span>🧪 ${escapeHtml(item.active_ingredient)}</span>` : ""}
            ${item.formulation ? `<span>🧴 ${escapeHtml(item.formulation)}</span>` : ""}
            ${item.manufacturer ? `<span>🏭 ${escapeHtml(item.manufacturer)}</span>` : ""}
          </div>

          <div class="flex flex-wrap gap-x-4 gap-y-0.5 text-sm text-gray-600 mt-1.5">
            <span class="font-semibold text-emerald-800">
              📦 ${item.quantity_on_hand != null
                ? escapeHtml(formatNumber(item.quantity_on_hand) + " " + (item.unit || ""))
                : "—"}
            </span>
            ${item.purchase_price != null
              ? `<span>₹${escapeHtml(formatNumber(item.purchase_price, { minimumFractionDigits: 2, maximumFractionDigits: 2 }))}</span>`
              : ""}
            ${item.supplier_name ? `<span>🏪 ${escapeHtml(item.supplier_name)}</span>` : ""}
            ${item.expiry_date ? `<span>📅 ${escapeHtml(t("inventory.expires"))}: ${escapeHtml(formatDate(item.expiry_date))}</span>` : ""}
          </div>

          <!-- Disclaimer: not an endorsement (requirement 8.4) -->
          <p class="text-sm text-gray-500 italic mt-2" data-i18n="inventory.farmerRecordOnly"></p>
        </div>
        <button type="button"
          class="btn-consume text-sm font-semibold text-brand-secondary border border-brand-secondary px-3 py-1.5 rounded-lg
                 hover:bg-brand-secondary hover:text-white transition btn-block-mobile"
          data-item-id="${escapeHtml(item.id)}"
          data-item-name="${escapeHtml(item.product_name)}"
          data-i18n="inventory.recordUse"
          ${st.outOfStock ? "disabled" : ""}></button>
      </div>
    `;
    invList.appendChild(card);
  });
  applyI18n(invList);

  invList.querySelectorAll(".btn-consume").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      openConsumeModal(btn.getAttribute("data-item-id"), btn.getAttribute("data-item-name"));
    });
  });
}

// ── Load inventory ────────────────────────────────────────────────────────────
async function loadInventory() {
  setHidden(invLoading, false);
  setHidden(invListEmpty, true);
  invList.innerHTML = "";

  try {
    const res = await apiFetch("/api/farmers/me/inventory");
    if (!res.ok) {
      setHidden(invLoading, true);
      renderLoadError(invList, loadInventory);
      return;
    }
    _inventory = await res.json();
    renderInventory();
  } catch {
    setHidden(invLoading, true);
    renderLoadError(invList, loadInventory, "common.error.network");
  }
}

// ── Add inventory item ────────────────────────────────────────────────────────
async function handleSaveInventory(e) {
  e.preventDefault();
  invFormError.classList.add("hidden");

  const val = (id) => document.getElementById(id).value.trim();
  const price = parseFloat(document.getElementById("inv-purchase-price").value);
  const body = {
    product_name:      val("inv-product-name"),
    active_ingredient: val("inv-active-ingredient") || null,
    formulation:       val("inv-formulation") || null,
    manufacturer:      val("inv-manufacturer") || null,
    batch_number:      val("inv-batch-number") || null,
    expiry_date:       document.getElementById("inv-batch-expiry").value || null,
    quantity_on_hand:  parseFloat(document.getElementById("inv-quantity").value) || 0,
    unit:              document.getElementById("inv-unit").value || "units",
    purchase_price:    Number.isNaN(price) ? null : price,
    supplier_name:     val("inv-supplier") || null,
  };

  if (!body.product_name) {
    showError_(invFormError, t("inventory.error.nameRequired"));
    return;
  }

  setBusy(invSaveBtn, true);
  try {
    const res = await apiFetch("/api/farmers/me/inventory", { method: "POST", body: JSON.stringify(body) });
    if (!res.ok) {
      showError_(invFormError, await errorMessage(res));
      return;
    }
    invForm.reset();
    invFormWrap.classList.add("hidden");
    await loadInventory();
  } catch {
    showError_(invFormError, t("common.error.network"));
  } finally {
    setBusy(invSaveBtn, false);
  }
}

// ── Consume modal ─────────────────────────────────────────────────────────────
function openConsumeModal(itemId, itemName) {
  _consumeTargetId = itemId;
  if (consumeItemName) consumeItemName.textContent = itemName;
  consumeError.classList.add("hidden");
  consumeForm.reset();
  consumeModal.classList.remove("hidden");
  document.getElementById("consume-quantity")?.focus();
}

function closeConsumeModal() {
  consumeModal.classList.add("hidden");
  _consumeTargetId = null;
}

async function handleSaveConsumption(e) {
  e.preventDefault();
  consumeError.classList.add("hidden");

  const body = {
    quantity_consumed: parseFloat(document.getElementById("consume-quantity").value),
    activity_id:       document.getElementById("consume-activity-id").value.trim() || null,
  };

  if (!body.quantity_consumed || body.quantity_consumed <= 0) {
    showError_(consumeError, t("inventory.error.quantityRequired"));
    return;
  }

  setBusy(consumeSaveBtn, true);
  try {
    const res = await apiFetch(`/api/farmers/me/inventory/${encodeURIComponent(_consumeTargetId)}/consume`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (res.status === 404) {
      showError_(consumeError, t("inventory.error.activityNotFound"));
      return;
    }
    if (!res.ok) {
      showError_(consumeError, await errorMessage(res));
      return;
    }
    closeConsumeModal();
    await loadInventory();
  } catch {
    showError_(consumeError, t("common.error.network"));
  } finally {
    setBusy(consumeSaveBtn, false);
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  initPage();
  await routeGuard("farm"); // inventory is part of the farm feature set

  document.getElementById("btn-signout")?.addEventListener("click", signOut);

  invFormToggle?.addEventListener("click", () => {
    invFormWrap.classList.toggle("hidden");
    invFormError.classList.add("hidden");
  });
  invFormCancel?.addEventListener("click", () => invFormWrap.classList.add("hidden"));
  invForm?.addEventListener("submit", handleSaveInventory);

  consumeClose?.addEventListener("click", closeConsumeModal);
  consumeCancel?.addEventListener("click", closeConsumeModal);
  consumeModal?.addEventListener("click", (e) => {
    if (e.target === consumeModal) closeConsumeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !consumeModal.classList.contains("hidden")) closeConsumeModal();
  });
  consumeForm?.addEventListener("submit", handleSaveConsumption);

  await loadInventory();
});
