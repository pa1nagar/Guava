/**
 * inventory.js — Inventory list with consumption recording modal.
 *
 * Handles:
 *  - GET  /api/farmers/me/inventory             → inventory list
 *  - POST /api/farmers/me/inventory             → add inventory item
 *  - PUT  /api/farmers/me/inventory/{id}        → update item
 *  - POST /api/farmers/me/inventory/{id}/consume → record consumption
 *
 * Inventory items are displayed as a farmer-entered catalogue — never as
 * endorsed products. Crop approval is NOT inferred from product name.
 * (Requirements 8.1, 8.3, 8.4)
 *
 * Requirements: 8.1, 8.2, 8.3, 8.4
 */

import { routeGuard, signOut } from "./auth.js";
import { apiFetch, showError } from "./api.js";

// ── State ─────────────────────────────────────────────────────────────────────
let _inventory = [];
let _consumeTargetId = null;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const invList        = document.getElementById("inventory-list");
const invListEmpty   = document.getElementById("inventory-list-empty");
const invLoading     = document.getElementById("inventory-loading");

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

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDate(isoStr) {
  if (!isoStr) return null;
  const d = new Date(isoStr);
  return `${String(d.getDate()).padStart(2,"0")}/${String(d.getMonth()+1).padStart(2,"0")}/${d.getFullYear()}`;
}

function isExpired(expiryStr) {
  if (!expiryStr) return false;
  return new Date(expiryStr) < new Date();
}

// ── Render inventory ──────────────────────────────────────────────────────────
function renderInventory() {
  setHidden(invLoading, true);
  invList.innerHTML = "";

  if (!_inventory || _inventory.length === 0) {
    setHidden(invListEmpty, false);
    return;
  }
  setHidden(invListEmpty, true);

  _inventory.forEach(item => {
    const expired = isExpired(item.batch_expiry);
    const lowStock = item.quantity_on_hand != null && item.quantity_on_hand <= 0;

    const card = document.createElement("div");
    card.className = "bg-white border border-gray-200 rounded-xl p-4 shadow-sm";
    card.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div class="flex-1 min-w-0">
          <div class="flex flex-wrap items-center gap-2 mb-1">
            <h3 class="font-bold text-emerald-900 text-sm">${escapeHtml(item.product_name)}</h3>
            ${expired
              ? '<span class="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-semibold">Expired</span>'
              : ""}
            ${lowStock && !expired
              ? '<span class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-semibold">Out of stock</span>'
              : ""}
          </div>

          <div class="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-500 mt-1">
            ${item.active_ingredient ? `<span>🧪 ${escapeHtml(item.active_ingredient)}</span>` : ""}
            ${item.formulation ? `<span>🧴 ${escapeHtml(item.formulation)}</span>` : ""}
            ${item.manufacturer ? `<span>🏭 ${escapeHtml(item.manufacturer)}</span>` : ""}
          </div>

          <div class="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-400 mt-1.5">
            <span class="font-semibold text-emerald-700">
              📦 ${item.quantity_on_hand != null
                ? Number(item.quantity_on_hand).toLocaleString("en-IN") + " " + escapeHtml(item.unit || "")
                : "—"}
            </span>
            ${item.purchase_price_inr != null
              ? `<span>₹${Number(item.purchase_price_inr).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>`
              : ""}
            ${item.supplier_name ? `<span>🏪 ${escapeHtml(item.supplier_name)}</span>` : ""}
            ${item.batch_expiry ? `<span>📅 Exp: ${formatDate(item.batch_expiry)}</span>` : ""}
          </div>

          <!-- Disclaimer: not an endorsement (requirement 8.4) -->
          <p class="text-xs text-gray-400 italic mt-2">
            Farmer-entered record only — not an endorsed product.
          </p>
        </div>
        <button
          class="btn-consume flex-shrink-0 text-xs font-semibold text-brand-secondary
                 border border-brand-secondary px-3 py-1.5 rounded-lg
                 hover:bg-brand-secondary hover:text-white transition"
          data-item-id="${item.id}"
          data-item-name="${escapeHtml(item.product_name)}"
          data-i18n-btn="inventory.consume"
          ${lowStock ? "disabled" : ""}>
          Record Use
        </button>
      </div>
    `;
    invList.appendChild(card);
  });

  // Bind consume buttons
  invList.querySelectorAll(".btn-consume").forEach(btn => {
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
      showError("Failed to load inventory.");
      setHidden(invLoading, true);
      return;
    }
    _inventory = await res.json();
    renderInventory();
  } catch {
    showError("Could not connect to server.");
    setHidden(invLoading, true);
  }
}

// ── Add inventory item ────────────────────────────────────────────────────────
async function handleSaveInventory(e) {
  e.preventDefault();
  invFormError.classList.add("hidden");
  invSaveBtn.disabled = true;
  invSaveBtn.textContent = "Saving…";

  const body = {
    product_name:       document.getElementById("inv-product-name").value.trim(),
    active_ingredient:  document.getElementById("inv-active-ingredient").value.trim() || null,
    formulation:        document.getElementById("inv-formulation").value.trim() || null,
    manufacturer:       document.getElementById("inv-manufacturer").value.trim() || null,
    batch_number:       document.getElementById("inv-batch-number").value.trim() || null,
    batch_expiry:       document.getElementById("inv-batch-expiry").value || null,
    quantity_on_hand:   parseFloat(document.getElementById("inv-quantity").value) || 0,
    unit:               document.getElementById("inv-unit").value || null,
    purchase_price_inr: parseFloat(document.getElementById("inv-purchase-price").value) || null,
    supplier_name:      document.getElementById("inv-supplier").value.trim() || null,
  };

  if (!body.product_name) {
    invFormError.textContent = "Product name is required.";
    invFormError.classList.remove("hidden");
    invSaveBtn.disabled = false;
    invSaveBtn.textContent = "Save Item";
    return;
  }

  try {
    const res = await apiFetch("/api/farmers/me/inventory", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (res.status === 422) {
      const data = await res.json();
      const detail = data.detail;
      invFormError.textContent = typeof detail === "string"
        ? detail : Array.isArray(detail)
        ? detail.map(d => d.msg).join(". ")
        : "Validation error.";
      invFormError.classList.remove("hidden");
      return;
    }
    if (!res.ok) {
      invFormError.textContent = "Failed to save item. Please try again.";
      invFormError.classList.remove("hidden");
      return;
    }

    invForm.reset();
    invFormWrap.classList.add("hidden");
    await loadInventory();
  } catch {
    invFormError.textContent = "Network error. Please try again.";
    invFormError.classList.remove("hidden");
  } finally {
    invSaveBtn.disabled = false;
    invSaveBtn.textContent = "Save Item";
  }
}

// ── Consume modal ─────────────────────────────────────────────────────────────
function openConsumeModal(itemId, itemName) {
  _consumeTargetId = itemId;
  if (consumeItemName) consumeItemName.textContent = itemName;
  consumeError.classList.add("hidden");
  consumeForm.reset();
  consumeModal.classList.remove("hidden");
}

function closeConsumeModal() {
  consumeModal.classList.add("hidden");
  _consumeTargetId = null;
}

async function handleSaveConsumption(e) {
  e.preventDefault();
  consumeError.classList.add("hidden");
  consumeSaveBtn.disabled = true;
  consumeSaveBtn.textContent = "Recording…";

  const body = {
    quantity_used: parseFloat(document.getElementById("consume-quantity").value),
    activity_id:   document.getElementById("consume-activity-id").value.trim() || null,
    notes:         document.getElementById("consume-notes").value.trim() || null,
  };

  if (!body.quantity_used || body.quantity_used <= 0) {
    consumeError.textContent = "Quantity used must be greater than 0.";
    consumeError.classList.remove("hidden");
    consumeSaveBtn.disabled = false;
    consumeSaveBtn.textContent = "Record Use";
    return;
  }

  try {
    const res = await apiFetch(`/api/farmers/me/inventory/${_consumeTargetId}/consume`, {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (res.status === 404) {
      consumeError.textContent = "Activity not found. Check the activity ID or leave it blank.";
      consumeError.classList.remove("hidden");
      return;
    }
    if (res.status === 422) {
      const data = await res.json();
      consumeError.textContent = typeof data.detail === "string"
        ? data.detail : "Validation error.";
      consumeError.classList.remove("hidden");
      return;
    }
    if (!res.ok) {
      consumeError.textContent = "Failed to record consumption. Please try again.";
      consumeError.classList.remove("hidden");
      return;
    }

    closeConsumeModal();
    await loadInventory();
  } catch {
    consumeError.textContent = "Network error. Please try again.";
    consumeError.classList.remove("hidden");
  } finally {
    consumeSaveBtn.disabled = false;
    consumeSaveBtn.textContent = "Record Use";
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await routeGuard("farm"); // inventory is part of the farm feature set

  document.getElementById("btn-signout")?.addEventListener("click", signOut);

  // Inventory form
  invFormToggle?.addEventListener("click", () => {
    invFormWrap.classList.toggle("hidden");
    invFormError.classList.add("hidden");
    invForm.reset();
  });
  invFormCancel?.addEventListener("click", () => invFormWrap.classList.add("hidden"));
  invForm?.addEventListener("submit", handleSaveInventory);

  // Consume modal
  consumeClose?.addEventListener("click", closeConsumeModal);
  consumeCancel?.addEventListener("click", closeConsumeModal);
  consumeModal?.addEventListener("click", (e) => {
    if (e.target === consumeModal) closeConsumeModal();
  });
  consumeForm?.addEventListener("submit", handleSaveConsumption);

  await loadInventory();
});
