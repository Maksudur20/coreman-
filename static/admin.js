// =========================================================
// COREMAN ADMIN SUITE - INTERACTIVE ENGINE & LIVE SYNC
// =========================================================

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initSearchAndFilters();
  initModals();
  initDistrictAdmin();
  initFlashAutoDismiss();
  initLiveOrdersSync();
});

// =========================================================
// 1. Tab Switcher
// =========================================================
function initTabs() {
  const tabPanes = document.querySelectorAll('.tab-pane');

  function getActiveTab() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('tab') || window.location.hash.replace('#', '') || 'dashboard';
  }

  function switchTab(tabId) {
    if (!tabId) tabId = 'dashboard';
    const navLinks = document.querySelectorAll('.admin-nav a, .nav-link[data-tab], [data-tab]');
    let matched = false;

    navLinks.forEach(link => {
      const linkTab = link.getAttribute('data-tab');
      if (linkTab === tabId) {
        link.classList.add('active');
        matched = true;
      } else if (linkTab) {
        link.classList.remove('active');
      }
    });

    tabPanes.forEach(pane => {
      if (pane.id === `tab-${tabId}`) {
        pane.style.display = 'block';
      } else {
        pane.style.display = 'none';
      }
    });

    if (!matched && tabPanes.length > 0) {
      tabPanes[0].style.display = 'block';
      const firstTab = tabPanes[0].id.replace('tab-', '');
      navLinks.forEach(link => {
        if (link.getAttribute('data-tab') === firstTab) {
          link.classList.add('active');
        }
      });
    }
  }

  // Delegated click handler for any tab link
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[data-tab], [data-tab], a[href*="tab="]');
    if (!link) return;

    let targetTab = link.getAttribute('data-tab');
    if (!targetTab && link.getAttribute('href')) {
      const match = link.getAttribute('href').match(/tab=([a-zA-Z0-9_-]+)/);
      if (match) targetTab = match[1];
    }

    if (targetTab) {
      e.preventDefault();
      switchTab(targetTab);
      window.history.pushState({ tab: targetTab }, '', `?tab=${targetTab}`);
    }
  });

  // Handle browser back and forward history buttons
  window.addEventListener('popstate', () => {
    switchTab(getActiveTab());
  });

  // Expose switchTab globally if needed
  window.switchAdminTab = switchTab;

  // Initialize active tab from URL or default to dashboard
  switchTab(getActiveTab());
}

// =========================================================
// 2. Live Search & Filtering
// =========================================================
function initSearchAndFilters() {
  const orderSearch = document.getElementById('orderSearch');
  const orderStatusFilter = document.getElementById('orderStatusFilter');
  const orderPaymentFilter = document.getElementById('orderPaymentFilter');

  function filterOrders() {
    const query = (orderSearch?.value || '').toLowerCase().trim();
    const status = (orderStatusFilter?.value || 'all').toLowerCase();
    const payment = (orderPaymentFilter?.value || 'all').toLowerCase();
    const orderRows = document.querySelectorAll('#ordersTableBody .order-row');

    orderRows.forEach(row => {
      const text = row.textContent.toLowerCase();
      const rowStatus = (row.getAttribute('data-status') || '').toLowerCase();
      const rowPayment = (row.getAttribute('data-payment') || '').toLowerCase();

      const matchesQuery = !query || text.includes(query);
      const matchesStatus = status === 'all' || rowStatus === status;
      const matchesPayment = payment === 'all' || rowPayment === payment;

      row.style.display = (matchesQuery && matchesStatus && matchesPayment) ? '' : 'none';
    });
  }

  if (orderSearch) orderSearch.addEventListener('input', filterOrders);
  if (orderStatusFilter) orderStatusFilter.addEventListener('change', filterOrders);
  if (orderPaymentFilter) orderPaymentFilter.addEventListener('change', filterOrders);
  window.filterOrdersLive = filterOrders;

  // Product Table Search & Filter
  const prodSearch = document.getElementById('prodSearch');
  const prodCategoryFilter = document.getElementById('prodCategoryFilter');

  function filterProducts() {
    const query = (prodSearch?.value || '').toLowerCase().trim();
    const cat = (prodCategoryFilter?.value || 'all').toLowerCase();
    const prodRows = document.querySelectorAll('.product-row');

    prodRows.forEach(row => {
      const text = row.textContent.toLowerCase();
      const rowCat = (row.getAttribute('data-category') || '').toLowerCase();

      const matchesQuery = !query || text.includes(query);
      const matchesCat = cat === 'all' || rowCat === cat;

      row.style.display = (matchesQuery && matchesCat) ? '' : 'none';
    });
  }

  if (prodSearch) prodSearch.addEventListener('input', filterProducts);
  if (prodCategoryFilter) prodCategoryFilter.addEventListener('change', filterProducts);
}

// =========================================================
// 3. Modals Engine & Order / Product Details Render
// =========================================================
function initModals() {
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay.id);
      }
    });
  });

  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const overlay = btn.closest('.modal-overlay');
      if (overlay) {
        closeModal(overlay.id);
      } else {
        closeAllModals();
      }
    });
  });

  // Delegated Edit Product Modal trigger
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-edit-prod');
    if (!btn) return;

    const id = btn.getAttribute('data-id');
    const name = btn.getAttribute('data-name');
    const category = btn.getAttribute('data-category');
    const price = btn.getAttribute('data-price');
    const stock = btn.getAttribute('data-stock');
    const desc = btn.getAttribute('data-desc');
    const image = btn.getAttribute('data-image');

    const modal = document.getElementById('editProductModal');
    const form = document.getElementById('editProductForm');
    if (modal && form) {
      form.action = `/admin/products/${id}/update`;
      const idEl = document.getElementById('editProdId');
      const nameEl = document.getElementById('editProdName');
      const catEl = document.getElementById('editProdCategory');
      const priceEl = document.getElementById('editProdPrice');
      const stockEl = document.getElementById('editProdStock');
      const descEl = document.getElementById('editProdDesc');
      const imgEl = document.getElementById('editProdImageUrl');

      if (idEl) idEl.value = id;
      if (nameEl) nameEl.value = name;
      if (catEl) catEl.value = category;
      if (priceEl) priceEl.value = price;
      if (stockEl) stockEl.value = stock;
      if (descEl) descEl.value = desc;
      if (imgEl) imgEl.value = image;

      openModal('editProductModal');
    }
  });

  // Delegated Order Details Modal trigger
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-view-order');
    if (!btn) return;

    const orderId = btn.getAttribute('data-id');
    const modal = document.getElementById('orderDetailsModal');
    const content = document.getElementById('orderDetailsContent');

    if (!modal || !content) return;

    content.innerHTML = '<div style="text-align:center; padding: 40px; color:#8e9bb0;">Loading order details...</div>';
    openModal('orderDetailsModal');

    try {
      const res = await fetch(`/admin/orders/${orderId}/json`);
      if (!res.ok) throw new Error('Order not found');
      const data = await res.json();
      renderOrderDetails(data, content);
    } catch (err) {
      content.innerHTML = `<div style="color:#f87171; padding:20px;">Failed to load order: ${err.message}</div>`;
    }
  });

  // Delegated Product Quick View Modal Trigger (From Orders Table or Order Details Modal)
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('.btn-quick-view-product');
    if (!trigger) return;

    e.preventDefault();
    e.stopPropagation();

    const pid = trigger.getAttribute('data-id');
    const name = trigger.getAttribute('data-name') || 'Product Details';
    const price = trigger.getAttribute('data-price') || '0';
    const image = trigger.getAttribute('data-image') || '/static/uploads/default-classic-black-tee.svg';
    const cat = trigger.getAttribute('data-category') || 'Apparel';
    const stock = trigger.getAttribute('data-stock') || 'Available';
    const desc = trigger.getAttribute('data-desc') || '';

    const modal = document.getElementById('productQuickViewModal');
    if (modal) {
      const imgEl = document.getElementById('pqImage');
      const nameEl = document.getElementById('pqName');
      const priceEl = document.getElementById('pqPrice');
      const catEl = document.getElementById('pqCategory');
      const stockEl = document.getElementById('pqStock');
      const descEl = document.getElementById('pqDesc');
      const linkEl = document.getElementById('pqStorefrontLink');

      if (imgEl) {
        imgEl.src = image;
        imgEl.alt = name;
      }
      if (nameEl) nameEl.textContent = name;
      if (priceEl) priceEl.textContent = `৳${price}`;
      if (catEl) catEl.textContent = cat.toUpperCase();
      if (stockEl) stockEl.textContent = `Stock: ${stock} units`;
      if (descEl) descEl.textContent = desc || 'Premium quality piece from COREMAN collection.';
      if (linkEl) {
        if (pid) {
          linkEl.href = `/product/${pid}`;
          linkEl.style.display = 'inline-block';
        } else {
          linkEl.style.display = 'none';
        }
      }

      openModal('productQuickViewModal');
    }
  });
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('active');
  }
  // If no other modal is active, restore scroll
  if (!document.querySelector('.modal-overlay.active')) {
    document.body.style.overflow = '';
  }
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.classList.remove('active');
  });
  document.body.style.overflow = '';
}

window.openModal = openModal;
window.closeModal = closeModal;
window.closeAllModals = closeAllModals;

function renderOrderDetails(data, container) {
  const o = data.order;
  const items = data.items || [];

  // Items rows with clickable product view trigger, black/ink text, and product thumbnail image
  let itemsHtml = items.map(item => `
    <div style="display:flex; align-items:center; justify-content:space-between; padding:12px 0; border-bottom:1px solid var(--core-line, #e2e8f0);">
      <div style="display:flex; align-items:center; gap:14px;">
        <img src="${item.image || '/static/uploads/default-classic-black-tee.svg'}" 
             alt="${item.name}" 
             class="order-prod-thumb btn-quick-view-product"
             data-id="${item.product_id || ''}"
             data-name="${item.name}"
             data-price="${Math.round(item.price)}"
             data-image="${item.image || '/static/uploads/default-classic-black-tee.svg'}"
             data-category="${item.category || 'Apparel'}"
             data-stock="${item.stock !== undefined ? item.stock : 50}"
             data-desc="${item.description || ''}"
             title="Click to view ${item.name}"
             style="width:52px; height:52px; object-fit:cover; border-radius:6px; border:1px solid var(--core-line, #e2e8f0); background:#fff; flex-shrink:0; cursor:pointer;" 
             onerror="this.src='/static/uploads/default-classic-black-tee.svg'">
        <div>
          <div class="btn-quick-view-product"
               data-id="${item.product_id || ''}"
               data-name="${item.name}"
               data-price="${Math.round(item.price)}"
               data-image="${item.image || '/static/uploads/default-classic-black-tee.svg'}"
               data-category="${item.category || 'Apparel'}"
               data-stock="${item.stock !== undefined ? item.stock : 50}"
               data-desc="${item.description || ''}"
               title="Click to view ${item.name}"
               style="font-weight:700; font-size:0.95rem; color:#171a18; cursor:pointer; letter-spacing:-0.01em;">
            ${item.name} <span style="font-size:11px; color:var(--core-accent); margin-left:2px;">↗</span>
          </div>
          <div style="font-size:0.8rem; color:#5f6368; margin-top:3px;">Qty: ${item.qty} × ৳${Math.round(item.price)}</div>
        </div>
      </div>
      <div style="font-weight:800; font-size:1.05rem; color:#171a18;">৳${Math.round(item.qty * item.price)}</div>
    </div>
  `).join('');

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px; border-bottom:1px solid var(--core-line); padding-bottom:16px;">
      <div>
        <div style="font-size:11px; color:var(--core-muted); text-transform:uppercase; letter-spacing:0.08em; font-weight:700;">Order Reference</div>
        <div style="font-size:22px; font-weight:800; color:var(--core-ink);">#${o.id}</div>
        <div style="font-size:12px; color:var(--core-muted);">Placed on ${o.created_at || 'Recent'}</div>
      </div>
      <div style="text-align:right;">
        <span class="status-pill ${(o.status || '').toLowerCase()}">${o.status}</span>
        <div style="margin-top:6px; font-size:12px; color:var(--core-muted);">Payment: <strong style="color:var(--core-ink);">${o.payment_status}</strong></div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; background:#faf9f6; padding:16px; border-radius:4px; border:1px solid var(--core-line);">
      <div>
        <div style="font-size:11px; color:var(--core-muted); text-transform:uppercase; font-weight:700;">Customer Details</div>
        <div style="font-weight:700; color:var(--core-ink); margin-top:4px;">${o.name}</div>
        <div style="font-size:12px; color:var(--core-muted);"><a href="tel:${o.phone}" style="color:var(--core-accent); text-decoration:none;">📞 ${o.phone}</a></div>
        <div style="font-size:12px; color:var(--core-muted);"><a href="mailto:${o.email}" style="color:var(--core-accent); text-decoration:none;">✉️ ${o.email}</a></div>
      </div>
      <div>
        <div style="font-size:11px; color:var(--core-muted); text-transform:uppercase; font-weight:700;">Shipping Address</div>
        <div style="font-size:13px; color:var(--core-ink); margin-top:4px; line-height:1.4;">${o.address}</div>
        <div style="font-size:11px; color:#b45309; font-weight:600; margin-top:6px;">District: ${o.district || 'Dhaka'} | ETA: ${o.estimated_delivery || '3-4 days'}</div>
      </div>
    </div>

    <div style="margin-bottom:20px;">
      <div style="font-size:11px; color:var(--core-muted); text-transform:uppercase; font-weight:700; margin-bottom:10px;">Ordered Items (${items.length}) <span style="font-size:11px; font-weight:500; color:var(--core-muted);">(Click image to view)</span></div>
      <div style="background:#faf9f6; border:1px solid var(--core-line); border-radius:4px; padding:4px 16px;">
        ${itemsHtml || '<div style="padding:15px; color:var(--core-muted);">No item records found</div>'}
      </div>
    </div>

    <div style="display:flex; justify-content:space-between; align-items:center; padding:14px 16px; background:#faf9f6; border-radius:4px; border:1px solid var(--core-line);">
      <div style="font-size:13px; font-weight:600; color:var(--core-muted);">Grand Total</div>
      <div style="font-size:22px; font-weight:800; color:var(--core-ink);">৳${Math.round(o.total)}</div>
    </div>

    <div style="margin-top:24px; padding-top:16px; border-top:1px solid var(--core-line); display:flex; justify-content:space-between; align-items:center;">
      <a href="/admin/orders/${o.id}/invoice" target="_blank" class="btn-ghost" style="font-size:11px;">
        🖨️ Print Dispatch Invoice
      </a>
      <form method="post" action="/admin/orders/${o.id}/delete" onsubmit="return confirm('Delete Order #${o.id}?');" style="margin:0;">
        <button type="submit" class="btn-danger-sm">Delete Order</button>
      </form>
    </div>
  `;
}

// =========================================================
// 4. Flash Message Auto-Dismiss (5 Seconds)
// =========================================================
function initFlashAutoDismiss() {
  const flashMessages = document.querySelectorAll('.admin-flash-msg, .flash');
  flashMessages.forEach((msg) => {
    scheduleFlashDismiss(msg, 5000);
  });
}

function scheduleFlashDismiss(msg, delayMs = 5000) {
  if (!msg || msg.dataset.dismissScheduled) return;
  msg.dataset.dismissScheduled = 'true';

  if (!msg.querySelector('.flash-close-btn')) {
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.innerHTML = '&times;';
    closeBtn.className = 'flash-close-btn';
    closeBtn.title = 'Dismiss message';
    closeBtn.style.cssText = 'background:none; border:none; font-size:18px; line-height:1; cursor:pointer; color:inherit; opacity:0.6; padding:0 0 0 14px; margin-left:auto;';
    closeBtn.onclick = (e) => {
      e.stopPropagation();
      dismissFlashElement(msg);
    };
    msg.appendChild(closeBtn);
  }

  setTimeout(() => {
    dismissFlashElement(msg);
  }, delayMs);
}

function dismissFlashElement(msg) {
  if (!msg || msg.dataset.dismissing) return;
  msg.dataset.dismissing = 'true';
  msg.style.transition = 'opacity 0.4s ease, transform 0.4s ease, max-height 0.4s ease, margin 0.4s ease, padding 0.4s ease';
  msg.style.opacity = '0';
  msg.style.transform = 'translateY(-8px)';
  setTimeout(() => {
    msg.style.maxHeight = '0';
    msg.style.marginTop = '0';
    msg.style.marginBottom = '0';
    msg.style.paddingTop = '0';
    msg.style.paddingBottom = '0';
    msg.style.overflow = 'hidden';
    setTimeout(() => {
      const parent = msg.parentElement;
      msg.remove();
      if (parent && parent.children.length === 0 && (parent.classList.contains('admin-flash-list') || parent.classList.contains('flash-wrap'))) {
        parent.remove();
      }
    }, 400);
  }, 400);
}

function showAdminToast(message, type = 'success') {
  let list = document.querySelector('.admin-flash-list');
  if (!list) {
    list = document.createElement('div');
    list.className = 'admin-flash-list';
    const mainWrap = document.querySelector('.admin-main-wrap');
    if (mainWrap) {
      mainWrap.insertBefore(list, mainWrap.firstChild);
    } else {
      document.body.insertBefore(list, document.body.firstChild);
    }
  }
  const msg = document.createElement('div');
  msg.className = `admin-flash-msg is-${type}`;
  msg.innerHTML = `<span>${message}</span>`;
  list.appendChild(msg);
  scheduleFlashDismiss(msg, 5000);
}

window.showAdminToast = showAdminToast;

// =========================================================
// 5. Live Orders Auto-Update (No Reload Needed)
// =========================================================
let lastKnownLatestOrderId = 0;
let lastKnownOrdersCount = -1;
let lastOrdersFingerprint = '';
let isFirstLivePoll = true;

function initLiveOrdersSync() {
  const existingRows = document.querySelectorAll('#ordersTableBody .order-row');
  existingRows.forEach(row => {
    const id = parseInt(row.getAttribute('data-order-id'), 10);
    if (!isNaN(id) && id > lastKnownLatestOrderId) {
      lastKnownLatestOrderId = id;
    }
  });
  lastKnownOrdersCount = existingRows.length;

  setInterval(pollOrdersFeed, 4000);
}

function getOrdersFingerprint(orders) {
  if (!orders || !orders.length) return 'empty';
  return orders.map(o => `${o.id}:${o.status}:${o.payment_status}:${o.total}`).join('|');
}

async function pollOrdersFeed() {
  try {
    const res = await fetch('/admin/api/orders-feed');
    if (!res.ok) return;
    const data = await res.json();

    const newLatestId = data.latest_id || 0;
    const newTotalOrders = data.total_orders || 0;
    const currentFingerprint = getOrdersFingerprint(data.orders);

    if (isFirstLivePoll) {
      lastKnownLatestOrderId = newLatestId;
      lastKnownOrdersCount = newTotalOrders;
      lastOrdersFingerprint = currentFingerprint;
      isFirstLivePoll = false;
      return;
    }

    if (newLatestId > lastKnownLatestOrderId) {
      const newestOrder = data.orders && data.orders[0];
      if (newestOrder) {
        showAdminToast(`🔔 New Order #${newestOrder.id} received from ${newestOrder.name} (৳${Math.round(newestOrder.total)})`, 'success');
        playNewOrderChime();
      }
      updateAdminDashboardAndTables(data, true);
    } else if (newTotalOrders !== lastKnownOrdersCount || currentFingerprint !== lastOrdersFingerprint) {
      updateAdminDashboardAndTables(data, false);
    }

    lastKnownLatestOrderId = newLatestId;
    lastKnownOrdersCount = newTotalOrders;
    lastOrdersFingerprint = currentFingerprint;
  } catch (err) {
    // Network retry on next tick
  }
}

function playNewOrderChime() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.2, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch (e) {}
}

function updateAdminDashboardAndTables(data, isNewOrder = false) {
  const stats = data.stats || {};
  const orders = data.orders || [];

  const kpiBoxes = document.querySelectorAll('.kpi-box');
  if (kpiBoxes.length >= 4) {
    if (stats.total_revenue !== undefined) {
      const numEl = kpiBoxes[0].querySelector('.kpi-number');
      if (numEl) numEl.textContent = `৳${Math.round(stats.total_revenue)}`;
    }
    if (stats.total_orders !== undefined) {
      const numEl = kpiBoxes[1].querySelector('.kpi-number');
      if (numEl) numEl.textContent = `${stats.total_orders}`;
      const hint = kpiBoxes[1].querySelector('.kpi-hint');
      if (hint) {
        hint.textContent = `${stats.pending_orders || 0} Pending fulfillment`;
        hint.classList.toggle('highlight', (stats.pending_orders || 0) > 0);
      }
    }
    if (stats.aov !== undefined && kpiBoxes[3]) {
      const aovHint = kpiBoxes[3].querySelector('.kpi-hint');
      if (aovHint) aovHint.textContent = `Average Order: ৳${Math.round(stats.aov)}`;
    }
  }

  const ordersNav = document.querySelector('.admin-nav a[data-tab="orders"]');
  if (ordersNav) ordersNav.textContent = `Orders (${data.total_orders})`;
  const orderTotalSpan = document.querySelector('#tab-orders .admin-section-head span');
  if (orderTotalSpan) orderTotalSpan.textContent = `${data.total_orders} TOTAL ORDERS`;

  if (stats.status_breakdown) {
    const breakdownRows = document.querySelectorAll('.breakdown-row > div');
    const statusMap = {
      0: 'Pending',
      1: 'Processing',
      2: 'Packed',
      3: 'Shipped',
      4: 'Delivered',
      5: 'Cancelled'
    };
    breakdownRows.forEach((row, idx) => {
      const st = statusMap[idx];
      if (st && stats.status_breakdown[st] !== undefined) {
        const count = stats.status_breakdown[st];
        const pct = stats.total_orders > 0 ? (count / stats.total_orders * 100) : 0;
        const countSpan = row.querySelector('.bar-label-group span:last-child');
        if (countSpan) countSpan.textContent = `${count} (${Math.round(pct)}%)`;
        const barFill = row.querySelector('.bar-fill');
        if (barFill) barFill.style.width = `${pct}%`;
      }
    });
  }

  const ordersTbody = document.getElementById('ordersTableBody');
  if (ordersTbody) {
    if (orders.length === 0) {
      ordersTbody.innerHTML = `
        <tr id="noOrdersRow">
          <td colspan="9" style="text-align:center; padding:32px; color:var(--core-muted);">No orders recorded.</td>
        </tr>`;
    } else {
      ordersTbody.innerHTML = orders.map(o => renderOrderTableRow(o)).join('');
      if (typeof window.filterOrdersLive === 'function') {
        window.filterOrdersLive();
      }
      if (isNewOrder) {
        const firstRow = ordersTbody.querySelector('.order-row');
        if (firstRow) {
          firstRow.style.transition = 'background-color 1.5s ease';
          firstRow.style.backgroundColor = '#ecfdf5';
          setTimeout(() => {
            firstRow.style.backgroundColor = '';
          }, 3000);
        }
      }
    }
  }

  const recentTbody = document.getElementById('recentOrdersTableBody');
  if (recentTbody) {
    const recentOrders = orders.slice(0, 6);
    if (recentOrders.length === 0) {
      recentTbody.innerHTML = `
        <tr id="noRecentOrdersRow">
          <td colspan="7" style="text-align:center; padding:30px; color:var(--core-muted);">No orders recorded yet.</td>
        </tr>`;
    } else {
      recentTbody.innerHTML = recentOrders.map(o => renderRecentOrderRow(o)).join('');
    }
  }
}

function renderOrderTableRow(order) {
  const itemsHtml = (order.items && order.items.length) ? `
    <div class="order-items-preview" style="display:flex; flex-direction:column; gap:4px; max-width:160px;">
      ${order.items.map(it => `
        <div style="display:flex; align-items:center; gap:6px;">
          <img src="${it.image || '/static/uploads/default-classic-black-tee.svg'}" 
               alt="${it.name}" 
               class="order-prod-thumb btn-quick-view-product"
               data-id="${it.product_id || ''}"
               data-name="${it.name}"
               data-price="${Math.round(it.price)}"
               data-image="${it.image || '/static/uploads/default-classic-black-tee.svg'}"
               data-category="${it.category || 'Apparel'}"
               data-stock="${it.stock !== undefined ? it.stock : 50}"
               data-desc="${it.description || ''}"
               title="Click to view ${it.name}"
               style="width:34px; height:34px; object-fit:cover; border-radius:4px; border:1px solid var(--core-line); flex-shrink:0; background:#fff; cursor:pointer;"
               onerror="this.src='/static/uploads/default-classic-black-tee.svg'">
          <div style="line-height:1.2; overflow:hidden;">
            <div class="btn-quick-view-product"
                 data-id="${it.product_id || ''}"
                 data-name="${it.name}"
                 data-price="${Math.round(it.price)}"
                 data-image="${it.image || '/static/uploads/default-classic-black-tee.svg'}"
                 data-category="${it.category || 'Apparel'}"
                 data-stock="${it.stock !== undefined ? it.stock : 50}"
                 data-desc="${it.description || ''}"
                 style="font-weight:700; font-size:11.5px; color:var(--core-ink); cursor:pointer; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;"
                 title="Click to view ${it.name}">
              ${it.name}
            </div>
            <div style="font-size:10.5px; color:var(--core-muted);">Qty: ${it.qty} × ৳${Math.round(it.price)}</div>
          </div>
        </div>
      `).join('')}
    </div>
  ` : '<span style="font-size:11px; color:var(--core-muted);">No items recorded</span>';

  return `
    <tr class="order-row" data-order-id="${order.id}" data-status="${(order.status || '').toLowerCase()}" data-payment="${(order.payment_status || '').toLowerCase()}">
      <td><strong>#${order.id}</strong></td>
      <td style="color:var(--core-muted); font-size:11px; white-space:nowrap;">${order.created_date || 'Recent'}</td>
      <td>
        <div style="font-weight:700; font-size:12px; line-height:1.2;">${order.name}</div>
        <div style="font-size:11px; color:var(--core-muted); margin-top:2px;"><a href="tel:${order.phone}" style="color:var(--core-accent); text-decoration:none;">${order.phone}</a></div>
      </td>
      <td>${itemsHtml}</td>
      <td>
        <div style="max-width:150px; font-size:11.5px; line-height:1.3; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;" title="${order.address}">${order.address}</div>
        <div style="font-size:10.5px; color:#b45309; font-weight:600; margin-top:2px;">ETA: ${order.estimated_delivery || '3-4 days'}</div>
      </td>
      <td>
        <strong style="font-size:13.5px; color:var(--core-ink); white-space:nowrap;">৳${Math.round(order.total)}</strong>
      </td>
      <td>
        <div style="font-size:10.5px; color:var(--core-muted); white-space:nowrap;">${order.payment_method || 'Cash on Delivery'}</div>
        <span class="status-pill ${order.payment_status === 'Paid' ? 'delivered' : 'pending'}" style="font-size:10px; padding:2px 7px; margin-top:2px;">
          ${order.payment_status}
        </span>
      </td>
      <td>
        <form method="post" action="/admin/orders/${order.id}/update" style="display:flex; flex-direction:column; gap:3px; max-width:125px; margin:0;">
          <select name="status" class="admin-select" style="padding:2px 5px; font-size:10.5px; height:24px; width:100%;">
            <option value="Pending" ${order.status === 'Pending' ? 'selected' : ''}>Pending</option>
            <option value="Processing" ${order.status === 'Processing' ? 'selected' : ''}>Processing</option>
            <option value="Packed" ${order.status === 'Packed' ? 'selected' : ''}>Packed</option>
            <option value="Shipped" ${order.status === 'Shipped' ? 'selected' : ''}>Shipped</option>
            <option value="Delivered" ${order.status === 'Delivered' ? 'selected' : ''}>Delivered</option>
            <option value="Cancelled" ${order.status === 'Cancelled' ? 'selected' : ''}>Cancelled</option>
          </select>
          <div style="display:flex; gap:3px;">
            <select name="payment_status" class="admin-select" style="padding:2px 5px; font-size:10.5px; height:24px; flex:1;">
              <option value="Pending" ${order.payment_status === 'Pending' ? 'selected' : ''}>Pending</option>
              <option value="Paid" ${order.payment_status === 'Paid' ? 'selected' : ''}>Paid</option>
              <option value="Cancelled" ${order.payment_status === 'Cancelled' ? 'selected' : ''}>Cancelled</option>
            </select>
            <button type="submit" class="btn-dark" style="padding:2px 7px; font-size:10px; height:24px;">Save</button>
          </div>
        </form>
      </td>
      <td style="text-align:right;">
        <div style="display:inline-flex; gap:4px; align-items:center;">
          <button class="btn-ghost btn-view-order" data-id="${order.id}" style="padding:4px 7px; font-size:10px;">Details</button>
          <a href="/admin/orders/${order.id}/invoice" target="_blank" class="btn-ghost" style="padding:4px 7px; font-size:10px;">Invoice</a>
          <form method="post" action="/admin/orders/${order.id}/delete" onsubmit="return confirm('Delete Order #${order.id}?');" style="margin:0; display:inline;">
            <button type="submit" class="btn-ghost" style="padding:4px 6px; font-size:10px; color:#dc2626; border-color:#fca5a5;" title="Delete Order">Delete</button>
          </form>
        </div>
      </td>
    </tr>
  `;
}

function renderRecentOrderRow(o) {
  const itemsHtml = (o.items && o.items.length) ? `
    <div style="display:flex; flex-direction:column; gap:4px; min-width:140px;">
      ${o.items.map(it => `
        <div style="display:flex; align-items:center; gap:6px;">
          <img src="${it.image || '/static/uploads/default-classic-black-tee.svg'}" 
               alt="${it.name}" 
               class="order-prod-thumb btn-quick-view-product"
               data-id="${it.product_id || ''}"
               data-name="${it.name}"
               data-price="${Math.round(it.price)}"
               data-image="${it.image || '/static/uploads/default-classic-black-tee.svg'}"
               data-category="${it.category || 'Apparel'}"
               data-stock="${it.stock !== undefined ? it.stock : 50}"
               data-desc="${it.description || ''}"
               title="Click to view ${it.name}"
               style="width:28px; height:28px; object-fit:cover; border-radius:3px; border:1px solid var(--core-line); flex-shrink:0; background:#fff; cursor:pointer;"
               onerror="this.src='/static/uploads/default-classic-black-tee.svg'">
          <span class="btn-quick-view-product"
                data-id="${it.product_id || ''}"
                data-name="${it.name}"
                data-price="${Math.round(it.price)}"
                data-image="${it.image || '/static/uploads/default-classic-black-tee.svg'}"
                data-category="${it.category || 'Apparel'}"
                data-stock="${it.stock !== undefined ? it.stock : 50}"
                data-desc="${it.description || ''}"
                style="font-size:11px; font-weight:700; color:var(--core-ink); cursor:pointer;">
            ${it.name} (${it.qty})
          </span>
        </div>
      `).join('')}
    </div>
  ` : '<span style="font-size:11px; color:var(--core-muted);">-</span>';

  return `
    <tr>
      <td><strong>#${o.id}</strong></td>
      <td>
        <div><strong>${o.name}</strong></div>
        <div style="font-size:11px; color:var(--core-muted);">${o.phone}</div>
      </td>
      <td>${itemsHtml}</td>
      <td><strong>৳${Math.round(o.total)}</strong></td>
      <td>
        <span class="status-pill ${o.payment_status === 'Paid' ? 'delivered' : 'pending'}">
          ${o.payment_status}
        </span>
      </td>
      <td>
        <span class="status-pill ${(o.status || '').toLowerCase()}">${o.status}</span>
      </td>
      <td>
        <button class="btn-ghost btn-view-order" data-id="${o.id}" style="padding:4px 10px; font-size:10px;">Details</button>
      </td>
    </tr>
  `;
}

// =========================================================
// 6. District Delivery Charge Live Search & Bulk Applicator
// =========================================================
function initDistrictAdmin() {
  const searchInput = document.getElementById('adminDistrictSearch');
  const blocks = document.querySelectorAll('.division-block');

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase().trim();
      blocks.forEach(block => {
        let hasVisibleInBlock = false;
        const dists = block.querySelectorAll('.district-rate-item');
        dists.forEach(d => {
          const name = (d.getAttribute('data-name') || '').toLowerCase();
          const bn = d.getAttribute('data-bn') || '';
          const match = !q || name.includes(q) || bn.includes(q);
          d.style.display = match ? 'flex' : 'none';
          if (match) hasVisibleInBlock = true;
        });
        block.style.display = hasVisibleInBlock ? 'block' : 'none';
      });
    });
  }

  const btnApply = document.getElementById('btnApplyBulkDivision');
  const bulkSelect = document.getElementById('bulkDivisionSelect');
  const bulkRate = document.getElementById('bulkDivisionRate');

  if (btnApply && bulkSelect && bulkRate) {
    btnApply.addEventListener('click', () => {
      const selectedDiv = bulkSelect.value;
      const rateVal = parseFloat(bulkRate.value);
      if (isNaN(rateVal) || rateVal < 0) {
        bulkRate.focus();
        return;
      }
      const targetBlock = document.querySelector(`.division-block[data-division="${selectedDiv}"]`);
      if (targetBlock) {
        const inputs = targetBlock.querySelectorAll('.dist-input');
        inputs.forEach(inp => {
          inp.value = Math.round(rateVal);
          inp.style.background = '#ecfdf5';
          setTimeout(() => { inp.style.background = ''; }, 600);
        });
      }
    });
  }
}
