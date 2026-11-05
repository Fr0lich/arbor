# This file archives the mobile scanner code (HTML and JS) that was previously in mobile_server.py.
# The feature is currently disabled and hidden from the user, but stored here for potential future use.

SCANNER_TRIGGER_HTML = """
          <!-- Barcode / QR Scanner Modal Trigger -->
          <button
            type="button"
            onclick="openScannerModal()"
            class="p-2 bg-surface hover:bg-tonal1 border border-bordercol rounded-[2px] text-ink transition-colors touch-target-min flex items-center justify-center shrink-0"
            title="Scan Physical Barcode / QR"
          >
            <span class="text-ember text-sm font-mono">📷</span>
          </button>
"""

SCANNER_MODAL_HTML = """
    <!-- ========================================== -->
    <!-- MODAL: QR / BARCODE SCANNER                -->
    <!-- ========================================== -->
    <div id="qrScannerModal" class="hidden fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex flex-col p-4 items-center justify-center">
      <div class="bg-surface border border-bordercol rounded-[2px] w-full max-w-sm overflow-hidden shadow-2xl">
        <header class="p-3 bg-tonal1 border-b border-tonal2 flex items-center justify-between">
          <h3 class="font-serif font-bold text-xs text-ink">📷 Scan Accession Barcode / QR</h3>
          <button type="button" onclick="closeScannerModal()" class="p-1 text-ink-muted text-sm font-bold">✕</button>
        </header>

        <div class="p-4 text-center space-y-3">
          <div class="relative w-full h-48 bg-black rounded-[2px] overflow-hidden flex items-center justify-center">
            <video id="scannerVideo" class="w-full h-full object-cover"></video>
            <div class="absolute inset-4 border-2 border-dashed border-ember/70 pointer-events-none rounded-[2px]"></div>
          </div>

          <p class="text-xs text-ink-muted font-sans">
            Align specimen barcode or type accession number below:
          </p>

          <div class="flex items-center gap-2">
            <input
              type="text"
              id="manualBarcodeInput"
              placeholder="e.g. 1024"
              class="flex-1 bg-surface border border-bordercol rounded-[2px] px-3 py-2 text-xs font-mono outline-none focus:border-fern"
            />
            <button
              type="button"
              onclick="handleManualBarcodeSearch()"
              class="px-3 py-2 bg-fern hover:bg-fern-dark text-white rounded-[2px] text-xs font-bold"
            >
              Find
            </button>
          </div>
        </div>
      </div>
    </div>
"""

SCANNER_JS = """
    // ==========================================
    // QR / BARCODE SCANNER MODAL
    // ==========================================
    let scannerStream = null;

    async function openScannerModal() {
      openModal('qrScannerModal');
      document.getElementById('manualBarcodeInput').value = '';
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
          scannerStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
          const video = document.getElementById('scannerVideo');
          video.srcObject = scannerStream;
          video.play();
        } catch(err) {
          // Camera denied or unavailable
        }
      }
    }

    function closeScannerModal() {
      if (scannerStream) {
        scannerStream.getTracks().forEach(track => track.stop());
        scannerStream = null;
      }
      closeModal('qrScannerModal');
    }

    function handleManualBarcodeSearch() {
      const code = document.getElementById('manualBarcodeInput').value.trim();
      if (!code) return;
      closeScannerModal();
      // Search or load directly
      const match = objectList.find(o => o.id === code || o.accession_number === code);
      if (match) {
        loadSpecimen(match.id);
      } else {
        document.getElementById('searchBox').value = code;
        debounceSearch();
      }
    }
"""
