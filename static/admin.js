// =========================================================
// COREMAN ADMIN SUITE - INTERACTIVE ENGINE
// =========================================================

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initSearchAndFilters();
  initModals();
});

// Tab Switcher
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

// Live Search & Filtering
function initSearchAndFilters() {
  // Order Table Search & Filters
  const orderSearch = document.getElementById('orderSearch');
  const orderStatusFilter = document.getElementById('orderStatusFilter');
  const orderPaymentFilter = document.getElementById('orderPaymentFilter');
  const orderRows = document.querySelectorAll('.order-row');

  function filterOrders() {
    const query = (orderSearch?.value || '').toLowerCase().trim();
    const status = (orderStatusFilter?.value || 'all').toLowerCase();
    const payment = (orderPaymentFilter?.value || 'all').toLowerCase();

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

  // Product Table Search & Filter
  const prodSearch = document.getElementById('prodSearch');
  const prodCategoryFilter = document.getElementById('prodCategoryFilter');
  const prodRows = document.querySelectorAll('.product-row');

  function filterProducts() {
    const query = (prodSearch?.value || '').toLowerCase().trim();
    const cat = (prodCategoryFilter?.value || 'all').toLowerCase();

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

// Modals Engine
function initModals() {
  // Close any modal with .modal-close or clicking overlay
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeAllModals();
      }
    });
  });

  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', closeAllModals);
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
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.classList.remove('active');
  });
  document.body.style.overflow = '';
}

// Expose modal controllers globally
window.openModal = openModal;
window.closeAllModals = closeAllModals;

function renderOrderDetails(data, container) {
  const o = data.order;
  const items = data.items || [];

  let itemsHtml = items.map(item => `
    <div style="display:flex; align-items:center; justify-content:space-between; padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.06);">
      <div style="display:flex; align-items:center; gap:12px;">
        <div>
          <div style="font-weight:600; font-size:0.9rem; color:#fff;">${item.name}</div>
          <div style="font-size:0.75rem; color:#8e9bb0;">Qty: ${item.qty} × ৳${Math.round(item.price)}</div>
        </div>
      </div>
      <div style="font-weight:700; color:#fff;">৳${Math.round(item.qty * item.price)}</div>
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
        <span class="status-pill ${o.status.toLowerCase()}">${o.status}</span>
        <div style="margin-top:6px; font-size:12px; color:var(--core-muted);">Payment: <strong style="color:var(--core-ink);">${o.payment_status}</strong></div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; background:#faf9f6; padding:16px; border-radius:3px; border:1px solid var(--core-line);">
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
      <div style="font-size:11px; color:var(--core-muted); text-transform:uppercase; font-weight:700; margin-bottom:10px;">Ordered Items (${items.length})</div>
      <div style="background:#faf9f6; border:1px solid var(--core-line); border-radius:3px; padding:0 14px;">
        ${itemsHtml || '<div style="padding:15px; color:var(--core-muted);">No item records found</div>'}
      </div>
    </div>

    <div style="display:flex; justify-content:space-between; align-items:center; padding:14px 16px; background:#faf9f6; border-radius:3px; border:1px solid var(--core-line);">
      <div style="font-size:13px; font-weight:600; color:var(--core-muted);">Grand Total</div>
      <div style="font-size:22px; font-weight:800; color:var(--core-ink);">৳${Math.round(o.total)}</div>
    </div>

    <div style="margin-top:24px; padding-top:16px; border-top:1px solid var(--core-line); display:flex; justify-content:space-between; align-items:center;">
      <a href="/admin/orders/${o.id}/invoice" target="_blank" class="btn-ghost" style="font-size:11px;">
        🖨️ Print Dispatch Invoice
      </a>
      <!-- Direct delete with no popup alert dialog -->
      <form method="post" action="/admin/orders/${o.id}/delete">
        <button type="submit" class="btn-danger-sm">Delete Order</button>
      </form>
    </div>
  `;
}
