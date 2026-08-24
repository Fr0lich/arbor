/**
 * Arbor Mobile Web Companion SPA Engine
 * Provides touch-friendly museum specimen inspection, fast typeahead search,
 * review toggles, Screen Wake Lock, and real-time synchronization with Arbor desktop.
 */

(function () {
  'use strict';

  // State Management
  const state = {
    token: '',
    status: null,
    specimens: [],
    selectedId: null,
    currentDetail: null,
    searchQuery: '',
    statusFilter: 'all', // all, pending, flagged, reviewed
    isWakeLockActive: false,
    wakeLockObj: null,
    offlineQueue: JSON.parse(localStorage.getItem('arbor_pending_edits') || '[]'),
    imageSourcePref: 'online', // 'online' or 'local'
  };

  // 1. Session Token Extraction
  const urlParams = new URLSearchParams(window.location.search);
  const tokenFromUrl = urlParams.get('token');
  if (tokenFromUrl) {
    state.token = tokenFromUrl;
    localStorage.setItem('arbor_session_token', tokenFromUrl);
  } else {
    state.token = localStorage.getItem('arbor_session_token') || '';
  }

  // 2. API Service Client
  const api = {
    async request(endpoint, options = {}) {
      const headers = {
        'Content-Type': 'application/json',
        'X-Session-Token': state.token,
        ...(options.headers || {}),
      };
      const sep = endpoint.includes('?') ? '&' : '?';
      const url = `${endpoint}${state.token ? `${sep}token=${encodeURIComponent(state.token)}` : ''}`;

      try {
        const res = await fetch(url, { ...options, headers });
        if (res.status === 401) {
          showToast('Unauthorized: Session token invalid', 'error');
          throw new Error('401 Unauthorized');
        }
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return await res.json();
      } catch (err) {
        if (!navigator.onLine || err.message.includes('Failed to fetch')) {
          updateConnectionStatus(false);
        }
        throw err;
      }
    },

    async getStatus() {
      return this.request('/api/status');
    },

    async getObjects(q = '', status = 'all') {
      const p = new URLSearchParams();
      if (q) p.set('q', q);
      if (status !== 'all') p.set('status', status);
      return this.request(`/api/objects?${p.toString()}`);
    },

    async getObjectDetail(id) {
      return this.request(`/api/object/${encodeURIComponent(id)}`);
    },

    async updateObject(id, reviewed, observation = {}) {
      return this.request('/api/update', {
        method: 'POST',
        body: JSON.stringify({ id, reviewed, observation }),
      });
    },
  };

  // 3. Screen Wake Lock API
  async function toggleWakeLock() {
    if ('wakeLock' in navigator) {
      try {
        if (!state.isWakeLockActive) {
          state.wakeLockObj = await navigator.wakeLock.request('screen');
          state.isWakeLockActive = true;
          state.wakeLockObj.addEventListener('release', () => {
            state.isWakeLockActive = false;
            updateWakeLockButton();
          });
          showToast('Screen Wake Lock active: Display will stay awake', 'success');
        } else if (state.wakeLockObj) {
          await state.wakeLockObj.release();
          state.wakeLockObj = null;
          state.isWakeLockActive = false;
        }
      } catch (err) {
        console.warn('WakeLock error:', err);
      }
      updateWakeLockButton();
    } else {
      showToast('Screen WakeLock not supported on this browser', 'info');
    }
  }

  function updateWakeLockButton() {
    const btn = document.getElementById('btn-wakelock');
    if (!btn) return;
    if (state.isWakeLockActive) {
      btn.classList.add('text-[#3a7d44]', 'bg-[#eff7f1]');
      btn.classList.remove('text-[#535d56]');
    } else {
      btn.classList.remove('text-[#3a7d44]', 'bg-[#eff7f1]');
      btn.classList.add('text-[#535d56]');
    }
  }

  // 4. Toast Notifications
  function showToast(msg, type = 'success') {
    const toast = document.getElementById('sync-toast');
    const toastMsg = document.getElementById('sync-toast-msg');
    if (!toast || !toastMsg) return;

    toastMsg.textContent = msg;
    toast.classList.remove('opacity-0');
    toast.classList.add('opacity-100');

    setTimeout(() => {
      toast.classList.remove('opacity-100');
      toast.classList.add('opacity-0');
    }, 2800);
  }

  function updateConnectionStatus(isOnline) {
    const btn = document.getElementById('btn-connection-status');
    const txt = document.getElementById('conn-text');
    if (!btn || !txt) return;

    if (isOnline) {
      btn.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[#eff7f1] text-[#3a7d44] border border-[#a4cca9]';
      txt.textContent = 'Live';
    } else {
      btn.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[#fef2f2] text-[#dc2626] border border-[#fca5a5]';
      txt.textContent = 'Offline';
    }
  }

  // 5. Offline Queue Synchronization
  async function flushOfflineQueue() {
    if (!navigator.onLine || state.offlineQueue.length === 0) return;
    const queue = [...state.offlineQueue];
    state.offlineQueue = [];
    localStorage.setItem('arbor_pending_edits', '[]');

    for (const item of queue) {
      try {
        await api.updateObject(item.id, item.reviewed, item.observation);
      } catch (err) {
        state.offlineQueue.push(item);
      }
    }
    localStorage.setItem('arbor_pending_edits', JSON.stringify(state.offlineQueue));
    if (state.offlineQueue.length === 0) {
      showToast('All offline edits synchronized with desktop host', 'success');
    }
  }

  window.addEventListener('online', () => {
    updateConnectionStatus(true);
    flushOfflineQueue();
  });
  window.addEventListener('offline', () => updateConnectionStatus(false));

  // 6. View Rendering
  const appRoot = document.getElementById('app-root');

  function renderListView() {
    state.selectedId = null;
    state.currentDetail = null;

    let itemsHtml = '';
    if (state.specimens.length === 0) {
      itemsHtml = `
        <div class="arbor-card p-8 text-center mt-3">
          <i data-lucide="package-open" class="w-10 h-10 mx-auto text-[#848f87] mb-2"></i>
          <p class="font-serif text-base font-semibold text-[#191e1a]">No specimens match</p>
          <p class="font-sans text-xs text-[#535d56] mt-1">Try adjusting your search query or status filter.</p>
        </div>
      `;
    } else {
      itemsHtml = state.specimens.map(s => {
        const isReviewed = s.review_status === 'reviewed';
        const hasFlags = s.has_flags;

        const badgeClass = isReviewed
          ? 'bg-[#eff7f1] text-[#3a7d44] border-[#a4cca9]'
          : hasFlags
            ? 'bg-[#fffbeb] text-[#d97706] border-[#fcd34d]'
            : 'bg-[#eceeec] text-[#535d56] border-[#d4d8d5]';

        const badgeText = isReviewed ? 'Reviewed' : hasFlags ? 'Flagged' : 'Pending';

        const locTags = Object.entries(s.location || {})
          .map(([k, v]) => `${k.charAt(0).toUpperCase() + k.slice(1)} ${v}`)
          .join(' · ');

        return `
          <div data-oid="${s.id}" class="specimen-card arbor-card p-3.5 mb-2.5 cursor-pointer touch-press transition-all hover:border-[#3a7d44]/50">
            <div class="flex items-start justify-between gap-2">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="font-mono text-xs font-semibold px-2 py-0.5 rounded-sm bg-[#eceeec] text-[#191e1a] border border-[#d4d8d5]">${s.id}</span>
                  ${s.family ? `<span class="font-sans text-xs text-[#848f87] truncate">${s.family}</span>` : ''}
                </div>
                <h3 class="font-serif italic font-semibold text-base text-[#191e1a] truncate">${s.scientific_name}</h3>
                ${locTags ? `<p class="font-mono text-xs text-[#535d56] mt-1 flex items-center gap-1"><i data-lucide="map-pin" class="w-3 h-3 text-[#848f87]"></i>${locTags}</p>` : ''}
              </div>
              <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${badgeClass}">${badgeText}</span>
            </div>
          </div>
        `;
      }).join('');
    }

    appRoot.innerHTML = `
      <!-- Search & Filters Container -->
      <div class="sticky top-[57px] z-30 bg-[#f3f3f3] pt-1 pb-3">
        <!-- Live Search Input -->
        <div class="relative search-active arbor-card overflow-hidden border border-[#d4d8d5] transition-all">
          <i data-lucide="search" class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#848f87]"></i>
          <input id="input-search" type="text" placeholder="Search ID, Genus, Species, Drawer..." value="${state.searchQuery}"
            class="w-full pl-9 pr-8 py-2.5 bg-transparent font-sans text-sm outline-none text-[#191e1a] placeholder-[#848f87]">
          ${state.searchQuery ? `<button id="btn-clear-search" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#848f87] p-1"><i data-lucide="x" class="w-4 h-4"></i></button>` : ''}
        </div>

        <!-- Filter Tabs -->
        <div class="flex items-center gap-1.5 mt-2.5 overflow-x-auto no-scrollbar py-0.5">
          <button data-filter="all" class="filter-tab px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${state.statusFilter === 'all' ? 'bg-[#2c302e] text-white' : 'bg-[#e9ece5] text-[#535d56] hover:bg-[#dfe3e0]'}">All (${state.status ? state.status.total_objects : state.specimens.length})</button>
          <button data-filter="pending" class="filter-tab px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${state.statusFilter === 'pending' ? 'bg-[#2c302e] text-white' : 'bg-[#e9ece5] text-[#535d56] hover:bg-[#dfe3e0]'}">Unreviewed (${state.status ? state.status.pending_count : 0})</button>
          <button data-filter="reviewed" class="filter-tab px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${state.statusFilter === 'reviewed' ? 'bg-[#3a7d44] text-white' : 'bg-[#e9ece5] text-[#535d56] hover:bg-[#dfe3e0]'}">Reviewed (${state.status ? state.status.reviewed_count : 0})</button>
        </div>
      </div>

      <!-- Specimen List -->
      <div id="specimen-list-container">
        ${itemsHtml}
      </div>
    `;

    if (window.lucide) window.lucide.createIcons();

    // Event listeners
    const searchInput = document.getElementById('input-search');
    let debounceTimer;
    searchInput?.addEventListener('input', e => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.searchQuery = e.target.value;
        loadSpecimens();
      }, 200);
    });

    document.getElementById('btn-clear-search')?.addEventListener('click', () => {
      state.searchQuery = '';
      loadSpecimens();
    });

    document.querySelectorAll('.filter-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        state.statusFilter = btn.getAttribute('data-filter');
        loadSpecimens();
      });
    });

    document.querySelectorAll('.specimen-card').forEach(card => {
      card.addEventListener('click', () => {
        const oid = card.getAttribute('data-oid');
        openSpecimenDetail(oid);
      });
    });
  }

  async function openSpecimenDetail(oid) {
    state.selectedId = oid;
    appRoot.innerHTML = `
      <div class="flex flex-col items-center justify-center min-h-[50vh] text-center p-6">
        <div class="w-8 h-8 border-3 border-[#3a7d44] border-t-transparent rounded-full animate-spin mb-3"></div>
        <p class="font-serif text-sm font-semibold text-[#191e1a]">Loading Specimen ${oid}...</p>
      </div>
    `;

    try {
      const detail = await api.getObjectDetail(oid);
      state.currentDetail = detail;
      renderDetailView(detail);
    } catch (err) {
      showToast(`Failed to load specimen ${oid}`, 'error');
      renderListView();
    }
  }

  function renderDetailView(detail) {
    const isReviewed = detail.review_status === 'reviewed';
    const reg = detail.registration || {};
    const obs = detail.observation || {};
    const images = detail.images || {};

    const onlineUrl = (images.online_urls && images.online_urls[0]) || '';
    const localEndpoint = (images.local_endpoints && images.local_endpoints[0]) || '';
    const initialImgSrc = state.imageSourcePref === 'online' && onlineUrl ? onlineUrl : (localEndpoint || onlineUrl);

    appRoot.innerHTML = `
      <!-- Back Navigation Header -->
      <div class="flex items-center justify-between mb-3">
        <button id="btn-back" class="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#e9ece5] text-[#2c302e] font-sans text-xs font-semibold hover:bg-[#dfe3e0] active:scale-95 transition-all">
          <i data-lucide="arrow-left" class="w-4 h-4"></i> Back to Collection
        </button>
        <span class="font-mono text-xs font-bold px-2.5 py-1 rounded-sm bg-[#2c302e] text-white">ID: ${detail.id}</span>
      </div>

      <!-- Specimen Header Card -->
      <div class="arbor-card p-4 mb-3 border-l-4 ${isReviewed ? 'border-l-[#3a7d44]' : 'border-l-[#d95c14]'}">
        <span class="font-mono text-xs text-[#848f87] uppercase tracking-wider font-semibold">${reg.Family || 'Botanical Specimen'}</span>
        <h2 class="font-serif italic font-bold text-xl text-[#191e1a] mt-0.5 leading-tight">${detail.scientific_name}</h2>
        ${reg.Author ? `<p class="font-serif text-xs text-[#535d56] mt-0.5">${reg.Author}</p>` : ''}
      </div>

      <!-- Specimen Image Preview with Cascading Fallback -->
      <div class="arbor-card overflow-hidden mb-3 bg-[#191e1a] relative group">
        <div id="image-wrapper" class="w-full h-56 flex items-center justify-center bg-[#191e1a]">
          ${initialImgSrc ? `
            <img id="detail-photo-img" src="${initialImgSrc}" alt="${detail.scientific_name}"
              class="w-full h-full object-contain cursor-pointer transition-transform hover:scale-102"
              onerror="handleImageError(this, '${localEndpoint}')">
          ` : `
            <div class="text-center text-[#848f87] p-6">
              <i data-lucide="image-off" class="w-8 h-8 mx-auto mb-1"></i>
              <p class="font-mono text-xs">No photos attached</p>
            </div>
          `}
        </div>
        ${initialImgSrc ? `
          <button id="btn-fullscreen-photo" class="absolute bottom-2 right-2 px-2.5 py-1 rounded-md bg-black/60 text-white font-sans text-xs flex items-center gap-1 backdrop-blur-xs">
            <i data-lucide="maximize-2" class="w-3.5 h-3.5"></i> Inspect Photo
          </button>
        ` : ''}
      </div>

      <!-- Collapsible Sections -->
      <!-- Section 1: Taxonomy -->
      <div class="arbor-card p-3.5 mb-2.5">
        <div class="flex items-center justify-between font-serif font-bold text-sm text-[#191e1a] mb-2 pb-1 border-b border-[#eceeec]">
          <span class="flex items-center gap-1.5"><i data-lucide="dna" class="w-4 h-4 text-[#3a7d44]"></i> Taxonomy Data</span>
        </div>
        <div class="grid grid-cols-2 gap-2 text-xs font-sans">
          <div><span class="text-[#848f87]">Genus:</span> <p class="font-medium font-serif italic">${reg.Genus || '—'}</p></div>
          <div><span class="text-[#848f87]">Species:</span> <p class="font-medium font-serif italic">${reg.Species || '—'}</p></div>
          <div><span class="text-[#848f87]">Family:</span> <p class="font-medium">${reg.Family || '—'}</p></div>
          <div><span class="text-[#848f87]">Type Status:</span> <p class="font-medium">${reg.TypeStatus || 'Standard'}</p></div>
        </div>
      </div>

      <!-- Section 2: Observations & Problems -->
      <div class="arbor-card p-3.5 mb-2.5">
        <div class="flex items-center justify-between font-serif font-bold text-sm text-[#191e1a] mb-2 pb-1 border-b border-[#eceeec]">
          <span class="flex items-center gap-1.5"><i data-lucide="clipboard-list" class="w-4 h-4 text-[#d95c14]"></i> Observations & Notes</span>
        </div>
        <div class="space-y-2.5 text-xs font-sans">
          <div>
            <label class="block text-[#848f87] mb-1 font-medium">Curator Notes:</label>
            <textarea id="detail-notes" rows="2" class="w-full p-2 rounded-md bg-[#f8f9fa] border border-[#d4d8d5] text-xs font-sans outline-none focus:border-[#3a7d44]">${obs.Notes || ''}</textarea>
          </div>
          <div class="flex items-center justify-between pt-1">
            <span class="text-[#535d56] font-medium">Genus / Taxonomy Problem:</span>
            <input id="chk-genus-problem" type="checkbox" ${obs.Genus_Problem ? 'checked' : ''} class="w-4 h-4 accent-[#d95c14]">
          </div>
        </div>
      </div>

      <!-- Section 3: Physical Location -->
      <div class="arbor-card p-3.5 mb-4">
        <div class="flex items-center justify-between font-serif font-bold text-sm text-[#191e1a] mb-2 pb-1 border-b border-[#eceeec]">
          <span class="flex items-center gap-1.5"><i data-lucide="map-pin" class="w-4 h-4 text-[#3a7d44]"></i> Physical Storage</span>
        </div>
        <div class="grid grid-cols-3 gap-2 text-xs font-sans">
          <div><span class="text-[#848f87]">Cabinet:</span> <p class="font-mono font-semibold">${reg.Cabinet || obs.Cabinet || '—'}</p></div>
          <div><span class="text-[#848f87]">Drawer:</span> <p class="font-mono font-semibold">${reg.Drawer || obs.Drawer || '—'}</p></div>
          <div><span class="text-[#848f87]">Tray:</span> <p class="font-mono font-semibold">${reg.Tray || obs.Tray || '—'}</p></div>
        </div>
      </div>

      <!-- Sticky Action Bar -->
      <div class="fixed bottom-0 left-0 right-0 z-40 bg-[#fbfaf8] border-t border-[#d4d8d5] p-3 shadow-lg">
        <div class="max-w-md mx-auto flex items-center gap-2">
          <!-- Big Reviewed Toggle Button -->
          <button id="btn-toggle-reviewed" class="flex-1 touch-target-min rounded-lg font-sans font-bold text-sm flex items-center justify-center gap-2 transition-all touch-press ${
            isReviewed
              ? 'bg-[#eff7f1] text-[#3a7d44] border-2 border-[#3a7d44]'
              : 'bg-[#3a7d44] text-white shadow-md hover:bg-[#2c6034]'
          }">
            <i data-lucide="${isReviewed ? 'check-circle-2' : 'circle'}" class="w-5 h-5"></i>
            <span>${isReviewed ? 'Marked Reviewed' : 'Mark as Reviewed'}</span>
          </button>

          <!-- Save & Next Unreviewed -->
          <button id="btn-save-next" title="Save and jump to next unreviewed" class="touch-target-min px-4 rounded-lg bg-[#2c302e] text-white font-sans font-semibold text-xs flex items-center gap-1.5 touch-press">
            <span>Save & Next</span>
            <i data-lucide="chevron-right" class="w-4 h-4"></i>
          </button>
        </div>
      </div>
    `;

    if (window.lucide) window.lucide.createIcons();

    // Event listeners
    document.getElementById('btn-back')?.addEventListener('click', () => renderListView());

    // Fullscreen photo modal
    const imgEl = document.getElementById('detail-photo-img');
    if (imgEl && imgEl.src) {
      document.getElementById('btn-fullscreen-photo')?.addEventListener('click', () => openPhotoModal(imgEl.src));
      imgEl.addEventListener('click', () => openPhotoModal(imgEl.src));
    }

    // Reviewed toggle
    document.getElementById('btn-toggle-reviewed')?.addEventListener('click', async () => {
      const nextReviewed = !isReviewed;
      const notes = document.getElementById('detail-notes')?.value || '';
      const genusProblem = document.getElementById('chk-genus-problem')?.checked || false;

      // Optimistic UI update
      detail.review_status = nextReviewed ? 'reviewed' : 'pending';
      detail.observation.Reviewed = nextReviewed;
      renderDetailView(detail);
      showToast(nextReviewed ? 'Specimen Marked as Reviewed' : 'Review status reopened', 'success');

      try {
        await api.updateObject(detail.id, nextReviewed, {
          Notes: notes,
          Genus_Problem: genusProblem,
        });
        refreshHeaderStatus();
      } catch (err) {
        state.offlineQueue.push({ id: detail.id, reviewed: nextReviewed, observation: { Notes: notes, Genus_Problem: genusProblem } });
        localStorage.setItem('arbor_pending_edits', JSON.stringify(state.offlineQueue));
      }
    });

    // Save and Next
    document.getElementById('btn-save-next')?.addEventListener('click', async () => {
      const notes = document.getElementById('detail-notes')?.value || '';
      const genusProblem = document.getElementById('chk-genus-problem')?.checked || false;

      try {
        await api.updateObject(detail.id, true, {
          Notes: notes,
          Genus_Problem: genusProblem,
        });
        showToast('Saved · Advancing to next specimen', 'success');
        refreshHeaderStatus();
      } catch (err) {
        state.offlineQueue.push({ id: detail.id, reviewed: true, observation: { Notes: notes, Genus_Problem: genusProblem } });
        localStorage.setItem('arbor_pending_edits', JSON.stringify(state.offlineQueue));
      }

      // Advance in specimen array
      const currentIndex = state.specimens.findIndex(s => s.id === detail.id);
      if (currentIndex !== -1 && currentIndex < state.specimens.length - 1) {
        openSpecimenDetail(state.specimens[currentIndex + 1].id);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } else {
        renderListView();
      }
    });
  }

  // Cascading Image Fallback Helper
  window.handleImageError = function (imgEl, localFallback) {
    if (localFallback && imgEl.src !== localFallback && !imgEl.dataset.triedLocal) {
      imgEl.dataset.triedLocal = 'true';
      imgEl.src = localFallback;
    } else {
      imgEl.parentElement.innerHTML = `
        <div class="text-center text-[#848f87] p-6">
          <i data-lucide="image-off" class="w-8 h-8 mx-auto mb-1"></i>
          <p class="font-mono text-xs">Photo unavailable</p>
        </div>
      `;
      if (window.lucide) window.lucide.createIcons();
    }
  };

  // Photo Fullscreen Modal
  function openPhotoModal(src) {
    const modal = document.getElementById('photo-modal');
    const modalImg = document.getElementById('modal-photo-img');
    if (!modal || !modalImg) return;

    modalImg.src = src;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }

  document.getElementById('btn-close-photo-modal')?.addEventListener('click', () => {
    const modal = document.getElementById('photo-modal');
    modal?.classList.add('hidden');
    modal?.classList.remove('flex');
  });

  // 7. Data Fetching & App Startup
  async function refreshHeaderStatus() {
    try {
      const status = await api.getStatus();
      state.status = status;
      const dbLabel = document.getElementById('header-db-name');
      if (dbLabel) dbLabel.textContent = status.database_name || 'Arbor Collection';
      updateConnectionStatus(true);
    } catch (err) {
      console.warn('Status poll error:', err);
    }
  }

  async function loadSpecimens() {
    try {
      const res = await api.getObjects(state.searchQuery, state.statusFilter);
      state.specimens = res.objects || [];
      if (!state.selectedId) {
        renderListView();
      }
    } catch (err) {
      showToast('Failed to load specimen collection', 'error');
    }
  }

  // Init App
  async function init() {
    document.getElementById('btn-wakelock')?.addEventListener('click', toggleWakeLock);

    try {
      await refreshHeaderStatus();
      await loadSpecimens();
    } catch (err) {
      console.error('App init failed:', err);
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
