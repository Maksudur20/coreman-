// =========================================================
// COREMAN STOREFRONT — SEAMLESS IN-PLACE CART & CHECKOUT ENGINE
// =========================================================

document.addEventListener('DOMContentLoaded', () => {
  initHeroSlider();
  initAjaxAddToCart();
  initCartSteppers();
  initCheckoutPaymentCards();
  initCategoryFilters();
  initCheckoutDistrictSync();
  initStoreFlashAutoDismiss();
  initSmoothScroll();
});

// Toast Manager
let toastTimeout = null;

function showCartToast(title, price) {
  let toastWrap = document.querySelector('.cart-toast-wrap');
  if (!toastWrap) {
    toastWrap = document.createElement('div');
    toastWrap.className = 'cart-toast-wrap';
    document.body.appendChild(toastWrap);
  }

  toastWrap.innerHTML = '';
  if (toastTimeout) clearTimeout(toastTimeout);

  const toast = document.createElement('div');
  toast.className = 'cart-toast';
  toast.innerHTML = `
    <div class="toast-icon">✓</div>
    <div class="toast-details">
      <div class="toast-title">${title || 'Item Added'}</div>
      <div class="toast-subtitle">${price ? '৳' + Math.round(price) + ' · ' : ''}Added to your bag</div>
    </div>
    <a href="/cart" class="toast-action-btn">View Cart</a>
  `;

  toastWrap.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  toastTimeout = setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }, 3500);
}

// In-Place AJAX Add to Cart
function initAjaxAddToCart() {
  document.addEventListener('submit', async (e) => {
    const form = e.target;
    if (!form || !form.action || !form.action.includes('/cart/add')) return;

    e.preventDefault();

    const submitBtn = form.querySelector('button[type="submit"]') || form.querySelector('button');
    if (!submitBtn || submitBtn.disabled) return;

    const originalText = submitBtn.textContent;
    submitBtn.textContent = '✓ ADDED';
    submitBtn.classList.add('added');

    try {
      const formData = new FormData(form);
      const res = await fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json'
        }
      });

      if (!res.ok) throw new Error('Failed to add item');

      const data = await res.json();

      if (data.cart_count !== undefined) {
        document.querySelectorAll('.cart-pill').forEach(pill => {
          pill.textContent = data.cart_count;
          pill.classList.remove('pop');
          void pill.offsetWidth;
          pill.classList.add('pop');
        });
      }

      showCartToast(data.product_name, data.product_price);

      // Trigger Meta / Facebook Pixel AddToCart event
      if (typeof fbq === 'function') {
        fbq('track', 'AddToCart', {
          content_ids: [formData.get('product_id')],
          content_type: 'product',
          value: data.product_price || undefined,
          currency: 'BDT'
        });
      }

      // Trigger Google Tag Manager / sGTM Add to Cart
      if (window.dataLayer) {
        window.dataLayer.push({
          event: 'add_to_cart',
          ecommerce: {
            currency: 'BDT',
            value: data.product_price || undefined,
            items: [{
              item_id: formData.get('product_id'),
              item_name: data.product_name || undefined,
              price: data.product_price || undefined,
              quantity: 1
            }]
          }
        });
      }
    } catch (err) {
      console.error('Error adding to cart:', err);
    } finally {
      setTimeout(() => {
        submitBtn.textContent = originalText;
        submitBtn.classList.remove('added');
      }, 1500);
    }
  });
}

// Custom Plus / Minus Steppers in Shopping Bag (No browser up/down arrows)
function initCartSteppers() {
  const cartForm = document.getElementById('cartUpdateForm');
  if (!cartForm) return;

  // Handle Plus click
  document.querySelectorAll('.btn-stepper-plus').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      const input = document.getElementById(`qty-input-${id}`);
      const valDisplay = document.getElementById(`qty-val-${id}`);
      if (!input || !valDisplay) return;

      let current = parseInt(input.value) || 0;
      current += 1;
      input.value = current;
      valDisplay.textContent = current;

      triggerCartSync(cartForm);
    });
  });

  // Handle Minus click (Direct remove if 1, NO popup!)
  document.querySelectorAll('.btn-stepper-minus').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      const input = document.getElementById(`qty-input-${id}`);
      const valDisplay = document.getElementById(`qty-val-${id}`);
      const row = document.getElementById(`cart-item-row-${id}`);
      if (!input || !valDisplay) return;

      let current = parseInt(input.value) || 0;
      if (current > 1) {
        current -= 1;
        input.value = current;
        valDisplay.textContent = current;
        triggerCartSync(cartForm);
      } else {
        // Direct remove without popup message
        removeCartItemDirectly(id, row);
      }
    });
  });

  // Handle Delete button click (Direct remove without popup)
  document.querySelectorAll('.btn-item-delete').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      const row = document.getElementById(`cart-item-row-${id}`);
      removeCartItemDirectly(id, row);
    });
  });
}

// Direct remove function via dedicated endpoint
async function removeCartItemDirectly(id, row) {
  if (row) {
    row.style.opacity = '0.3';
    row.style.pointerEvents = 'none';
  }

  try {
    const res = await fetch(`/cart/remove/${id}`, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json'
      }
    });

    if (!res.ok) throw new Error('Remove failed');
    const data = await res.json();

    if (row && row.parentNode) {
      row.parentNode.removeChild(row);
    }

    // If cart is now empty, immediately reload cleanly so empty state renders
    if (!data.cart_count || data.cart_count === 0 || !data.items || data.items.length === 0) {
      window.location.reload();
      return;
    }

    // Update navbar cart pill
    document.querySelectorAll('.cart-pill').forEach(pill => {
      pill.textContent = data.cart_count;
      pill.classList.remove('pop');
      void pill.offsetWidth;
      pill.classList.add('pop');
    });

    // Update item count label
    const countLabel = document.getElementById('cartItemCountLabel');
    if (countLabel) countLabel.textContent = data.items.length;

    // Update grand total
    const grandTotalEl = document.getElementById('cartGrandTotal');
    if (grandTotalEl && data.total !== undefined) {
      grandTotalEl.textContent = `৳${Math.round(data.total)}`;
    }

    // Update shipping meter
    updateShippingMeter(data.total);

  } catch (err) {
    console.error('Error removing item:', err);
    if (row) {
      row.style.opacity = '1';
      row.style.pointerEvents = 'auto';
    }
  }
}

// Dynamic Free Shipping & Combo Progress Meter Update
function updateShippingMeter(total, cartCount) {
  const card = document.getElementById('shippingMeterCard');
  if (!card) return;

  const comboMin = parseInt(card.getAttribute('data-combo-min') || '2', 10);
  const feeDhaka = card.getAttribute('data-fee-dhaka') || '80';
  const feeOutside = card.getAttribute('data-fee-outside') || '130';

  let currentQty = cartCount;
  if (currentQty === undefined) {
    const qtyInputs = document.querySelectorAll('.qty-field');
    currentQty = 0;
    qtyInputs.forEach(i => { currentQty += parseInt(i.value || '0', 10); });
  }

  const isUnlocked = currentQty >= comboMin;
  const remainingQty = Math.max(0, comboMin - currentQty);
  const progressPct = isUnlocked ? 100 : Math.min(100, Math.round((currentQty / comboMin) * 100));

  const bar = document.querySelector('.shipping-meter-bar');
  if (bar) {
    bar.style.width = `${progressPct}%`;
    bar.style.background = isUnlocked ? '#16a34a' : 'linear-gradient(90deg, #171a18 0%, #a1632d 100%)';
  }

  const header = document.querySelector('.shipping-meter-header');
  if (header) {
    if (isUnlocked) {
      card.classList.add('unlocked');
      header.innerHTML = `
        <span class="meter-icon">🎉</span>
        <span class="meter-text"><strong>অভিনন্দন! কম্বো অফার আনলকড (Combo Offer Unlocked)</strong> — আপনি ${currentQty}টি প্রোডাক্ট অর্ডার করছেন, তাই সারা বাংলাদেশে <strong>FREE Delivery (৳০)</strong>!</span>
      `;
    } else {
      card.classList.remove('unlocked');
      header.innerHTML = `
        <span class="meter-icon">🎁</span>
        <span class="meter-text">
          আর মাত্র <strong>${remainingQty}টি প্রোডাক্ট</strong> ব্যাগে যোগ করলেই পাচ্ছেন <strong>কম্বো অফার: সারা দেশে ১০০% ফ্রি ডেলিভারি!</strong>
          <span style="display:block; font-size:11.5px; color:var(--core-muted); margin-top:3px;">(১টি প্রোডাক্ট নিলে ডেলিভারি চার্জ: ঢাকার ভেতরে ৳${feeDhaka} · ঢাকার বাইরে ৳${feeOutside})</span>
        </span>
      `;
    }
  }
}

// Background sync for cart without page reload
async function triggerCartSync(cartForm) {
  try {
    const formData = new FormData(cartForm);
    const res = await fetch('/cart/update', {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json'
      }
    });

    if (!res.ok) return;
    const data = await res.json();

    // If cart is empty, reload cleanly
    if (!data.cart_count || data.cart_count === 0 || !data.items || data.items.length === 0) {
      window.location.reload();
      return;
    }

    // Update topbar cart pill
    if (data.cart_count !== undefined) {
      document.querySelectorAll('.cart-pill').forEach(pill => {
        pill.textContent = data.cart_count;
        pill.classList.remove('pop');
        void pill.offsetWidth;
        pill.classList.add('pop');
      });
    }

    // Update item count label
    const countLabel = document.getElementById('cartItemCountLabel');
    if (countLabel && data.items) countLabel.textContent = data.items.length;

    // Update individual item subtotals
    if (data.items && Array.isArray(data.items)) {
      data.items.forEach(item => {
        const subtotalEl = document.getElementById(`subtotal-${item.id}`);
        if (subtotalEl) {
          subtotalEl.textContent = `৳${Math.round(item.subtotal)}`;
        }
      });
    }

    // Update Grand Total
    const grandTotalEl = document.getElementById('cartGrandTotal');
    if (grandTotalEl && data.total !== undefined) {
      grandTotalEl.textContent = `৳${Math.round(data.total)}`;
    }

    // Update shipping meter with dynamic count
    const totalUnits = data.total_qty !== undefined ? data.total_qty : data.cart_count;
    updateShippingMeter(data.total, totalUnits);

  } catch (err) {
    console.error('Error syncing cart:', err);
  }
}

// Checkout Interactive Payment Radio Cards
function initCheckoutPaymentCards() {
  const paymentLabels = document.querySelectorAll('.payment-card-label');
  if (!paymentLabels.length) return;

  paymentLabels.forEach(label => {
    label.addEventListener('click', () => {
      paymentLabels.forEach(l => l.classList.remove('selected'));
      label.classList.add('selected');
      const radio = label.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
    });
  });
}

// Interactive Category Filtering
function initCategoryFilters() {
  const buttons = document.querySelectorAll('.cat-filter-btn');
  const cards = document.querySelectorAll('.product-card-item');
  const countEl = document.getElementById('visibleProductCount');
  const catTextEl = document.getElementById('activeCategoryText');
  const noProductsAlert = document.getElementById('noProductsAlert');

  if (!buttons.length || !cards.length) return;

  buttons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const selected = btn.getAttribute('data-category');

      // Update button active state
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      let visibleCount = 0;
      cards.forEach(card => {
        const cardCat = card.getAttribute('data-category') || '';
        const match = selected === 'All' || cardCat.trim().toLowerCase() === selected.trim().toLowerCase();
        if (match) {
          card.style.display = '';
          visibleCount++;
        } else {
          card.style.display = 'none';
        }
      });

      if (countEl) countEl.textContent = visibleCount;
      if (catTextEl) catTextEl.textContent = selected;
      if (noProductsAlert) {
        noProductsAlert.style.display = visibleCount === 0 ? 'block' : 'none';
      }

      // Smooth scroll down to collection
      const shopSection = document.getElementById('shop');
      if (shopSection) {
        shopSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

// Checkout Delivery Option & Grand Total Sync
function initCheckoutDistrictSync() {
  const zoneRadioDhaka = document.getElementById('zoneRadioDhaka');
  const zoneRadioOutside = document.getElementById('zoneRadioOutside');
  const zoneCardDhaka = document.getElementById('zoneCardDhaka');
  const zoneCardOutside = document.getElementById('zoneCardOutside');
  const districtInput = document.getElementById('districtInput');

  if (!zoneRadioDhaka && !zoneRadioOutside) return;

  function updateCharges() {
    const subtotalEl = document.getElementById('checkoutSubtotal');
    if (!subtotalEl) return;
    const subtotal = parseFloat(subtotalEl.getAttribute('data-subtotal')) || 0;

    const settings = window.COREMAN_SETTINGS || {
      feeDhaka: 80,
      feeOutside: 130,
      isComboFree: false,
      totalQty: 1
    };

    const isDhaka = !zoneRadioOutside || !zoneRadioOutside.checked;

    // Card highlight state
    if (zoneCardDhaka && zoneCardOutside) {
      if (isDhaka) {
        zoneCardDhaka.classList.add('selected');
        zoneCardOutside.classList.remove('selected');
        if (zoneRadioDhaka) zoneRadioDhaka.checked = true;
      } else {
        zoneCardOutside.classList.add('selected');
        zoneCardDhaka.classList.remove('selected');
        if (zoneRadioOutside) zoneRadioOutside.checked = true;
      }
    }

    if (districtInput) {
      districtInput.value = isDhaka ? 'Dhaka' : 'Outside Dhaka';
    }

    const feeDhaka = settings.feeDhaka || 80;
    const feeOutside = settings.feeOutside || 130;
    const baseFee = isDhaka ? feeDhaka : feeOutside;

    let isFree = false;
    let freeTag = 'FREE';

    if (settings.isComboFree) {
      isFree = true;
      freeTag = 'FREE (Combo Offer)';
    }

    const fee = isFree ? 0 : baseFee;
    const grandTotal = subtotal + fee;

    // Update delivery fee label & display
    const feeLabel = document.getElementById('deliveryFeeLabel');
    const feeDisplay = document.getElementById('deliveryFeeDisplay');
    const grandTotalDisplay = document.getElementById('grandTotalDisplay');
    const etaText = document.getElementById('deliveryEtaText');
    const feeInput = document.getElementById('deliveryFeeInput');
    const finalTotalInput = document.getElementById('finalTotalInput');

    if (feeLabel) {
      feeLabel.textContent = `Delivery Charge (${isDhaka ? 'Inside Dhaka' : 'Outside Dhaka'})`;
    }

    if (feeDisplay) {
      if (isFree) {
        feeDisplay.innerHTML = `<span style="color: #15803d; font-weight: 700;">${freeTag}</span>`;
      } else {
        feeDisplay.innerHTML = `৳${Math.round(fee)}`;
      }
    }

    if (grandTotalDisplay) {
      grandTotalDisplay.textContent = `৳${Math.round(grandTotal)}`;
    }

    if (etaText) {
      etaText.innerHTML = isDhaka
        ? '<strong>Delivery ETA:</strong> 1-2 Days within Dhaka Metro'
        : '<strong>Delivery ETA:</strong> 2-4 Days delivery outside Dhaka';
    }

    if (feeInput) feeInput.value = fee;
    if (finalTotalInput) finalTotalInput.value = grandTotal;
  }

  // Radio button change listeners
  if (zoneRadioDhaka) {
    zoneRadioDhaka.addEventListener('change', updateCharges);
  }
  if (zoneRadioOutside) {
    zoneRadioOutside.addEventListener('change', updateCharges);
  }

  // Card click triggers
  if (zoneCardDhaka) {
    zoneCardDhaka.addEventListener('click', () => {
      if (zoneRadioDhaka) zoneRadioDhaka.checked = true;
      updateCharges();
    });
  }
  if (zoneCardOutside) {
    zoneCardOutside.addEventListener('click', () => {
      if (zoneRadioOutside) zoneRadioOutside.checked = true;
      updateCharges();
    });
  }

  // Run once on load to ensure initial sum is perfectly synchronized
  updateCharges();
}

// =========================================================
// DYNAMIC HERO SLIDER ENGINE (Smooth Horizontal Slider)
// =========================================================
function initHeroSlider() {
  const slider = document.getElementById('heroSlider');
  if (!slider) return;

  const track = document.getElementById('heroTrack');
  const slides = Array.from(slider.querySelectorAll('.hero-slide'));
  if (!slides || slides.length === 0) return;

  const prevBtn = document.getElementById('heroPrevBtn');
  const nextBtn = document.getElementById('heroNextBtn');
  const dots = Array.from(slider.querySelectorAll('.hero-dot'));

  let currentIndex = 0;
  let autoplayTimer = null;
  const autoplaySpeed = parseInt(slider.getAttribute('data-autoplay') || '3500', 10) || 3500;

  function updateSlider(index, animate = true) {
    if (index < 0) index = slides.length - 1;
    if (index >= slides.length) index = 0;
    currentIndex = index;

    if (track) {
      if (!animate) {
        track.style.transition = 'none';
      } else {
        track.style.transition = 'transform 0.7s cubic-bezier(0.25, 1, 0.5, 1)';
      }
      track.style.transform = `translateX(-${currentIndex * 100}%)`;
    }

    dots.forEach((dot, idx) => {
      dot.classList.toggle('active', idx === currentIndex);
    });

    slides.forEach((slide, idx) => {
      slide.classList.toggle('active', idx === currentIndex);
    });
  }

  function nextSlide() {
    updateSlider(currentIndex + 1);
  }

  function prevSlide() {
    updateSlider(currentIndex - 1);
  }

  function startAutoplay() {
    if (slides.length <= 1) return;
    stopAutoplay();
    autoplayTimer = setInterval(nextSlide, autoplaySpeed);
  }

  function stopAutoplay() {
    if (autoplayTimer) {
      clearInterval(autoplayTimer);
      autoplayTimer = null;
    }
  }

  function restartAutoplay() {
    stopAutoplay();
    startAutoplay();
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', (e) => {
      e.preventDefault();
      nextSlide();
      restartAutoplay();
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', (e) => {
      e.preventDefault();
      prevSlide();
      restartAutoplay();
    });
  }

  dots.forEach((dot) => {
    dot.addEventListener('click', (e) => {
      e.preventDefault();
      const targetIndex = parseInt(dot.getAttribute('data-index') || '0', 10);
      updateSlider(targetIndex);
      restartAutoplay();
    });
  });

  // Touch Swipe Support for mobile
  let touchStartX = 0;
  let touchEndX = 0;

  slider.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
    stopAutoplay();
  }, { passive: true });

  slider.addEventListener('touchend', (e) => {
    touchEndX = e.changedTouches[0].screenX;
    const diff = touchStartX - touchEndX;
    if (Math.abs(diff) > 40) {
      if (diff > 0) {
        nextSlide();
      } else {
        prevSlide();
      }
    }
    restartAutoplay();
  }, { passive: true });

  // Keyboard navigation
  document.addEventListener('keydown', (e) => {
    if (!slider || !document.body.contains(slider)) return;
    if (e.key === 'ArrowLeft') {
      prevSlide();
      restartAutoplay();
    } else if (e.key === 'ArrowRight') {
      nextSlide();
      restartAutoplay();
    }
  });

  // Initial state and start auto-play
  updateSlider(0, false);
  startAutoplay();
}

// Flash Message Auto-Dismiss (5 Seconds)
function initStoreFlashAutoDismiss() {
  const flashMessages = document.querySelectorAll('.flash, .flash-wrap > div');
  flashMessages.forEach((msg) => {
    if (msg.dataset.dismissScheduled) return;
    msg.dataset.dismissScheduled = 'true';

    // Add close button if not present
    if (!msg.querySelector('.flash-close-btn')) {
      const closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.innerHTML = '&times;';
      closeBtn.className = 'flash-close-btn';
      closeBtn.title = 'Dismiss';
      closeBtn.style.cssText = 'background:none; border:none; font-size:18px; line-height:1; cursor:pointer; color:inherit; opacity:0.6; padding:0 0 0 12px; margin-left:auto;';
      closeBtn.onclick = (e) => {
        e.stopPropagation();
        dismissStoreFlash(msg);
      };
      msg.appendChild(closeBtn);
    }

    setTimeout(() => {
      dismissStoreFlash(msg);
    }, 5000);
  });
}

function dismissStoreFlash(el) {
  if (!el || el.dataset.dismissing) return;
  el.dataset.dismissing = 'true';
  el.style.transition = 'opacity 0.4s ease, transform 0.4s ease, max-height 0.4s ease, margin 0.4s ease, padding 0.4s ease';
  el.style.opacity = '0';
  el.style.transform = 'translateY(-8px)';
  setTimeout(() => {
    el.style.maxHeight = '0';
    el.style.marginTop = '0';
    el.style.marginBottom = '0';
    el.style.paddingTop = '0';
    el.style.paddingBottom = '0';
    el.style.overflow = 'hidden';
    setTimeout(() => {
      const parent = el.parentElement;
      el.remove();
      if (parent && parent.children.length === 0 && parent.classList.contains('flash-wrap')) {
        parent.remove();
      }
    }, 400);
  }, 400);
}

// High-Performance Smooth Anchor Navigation
function initSmoothScroll() {
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href^="#"], a[href^="/#"]');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href || href === '#' || href === '/#') return;

    const hash = href.includes('#') ? '#' + href.split('#')[1] : null;
    if (!hash) return;

    const isHomePage = (window.location.pathname === '/' || window.location.pathname === '');
    const targetEl = document.querySelector(hash);

    // If clicking an in-page anchor while already on the home page, scroll smoothly with header offset
    if (isHomePage && targetEl) {
      e.preventDefault();
      const header = document.querySelector('.topbar') || document.querySelector('header');
      const headerHeight = header ? header.offsetHeight : 80;
      const targetPos = targetEl.getBoundingClientRect().top + window.pageYOffset - headerHeight;
      window.scrollTo({
        top: Math.max(0, targetPos),
        behavior: 'smooth'
      });
      history.pushState(null, '', hash);
    }
  });

  // If page loaded with a hash (e.g. navigating from /cart to /#shop)
  if (window.location.hash) {
    const hash = window.location.hash;
    const target = document.querySelector(hash);
    if (target) {
      requestAnimationFrame(() => {
        const header = document.querySelector('.topbar') || document.querySelector('header');
        const headerHeight = header ? header.offsetHeight : 80;
        const targetPos = target.getBoundingClientRect().top + window.pageYOffset - headerHeight;
        window.scrollTo({
          top: Math.max(0, targetPos),
          behavior: 'auto'
        });
      });
    }
  }
}

