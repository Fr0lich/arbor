import re

with open("backend/mobile_server.py", "r") as f:
    content = f.read()

# Add Filter Modal HTML
search_modal_end = """
    <!-- ========================================== -->
    <!-- MODAL: ADD DISCREPANCY                     -->
    <!-- ========================================== -->
"""

replace_modal_end = """
    <!-- ========================================== -->
    <!-- MODAL: ADVANCED FILTER                     -->
    <!-- ========================================== -->
    <div id="filterModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded-[2px] w-full max-w-md shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-2">
            <span class="text-sm">⚙</span>
            <h2 class="font-serif font-bold text-sm text-ink">
              Advanced Filter
            </h2>
          </div>
          <button
            type="button"
            onclick="closeFilterModal()"
            class="p-1 text-ink-faint hover:text-ink rounded-[2px] text-sm font-bold"
          >
            ✕
          </button>
        </header>

        <div class="p-4 overflow-y-auto space-y-6 flex-1">
          <!-- Locations -->
          <div>
            <h3 class="font-sans text-xs font-bold text-ink mb-3 uppercase tracking-wider">Location Filters</h3>
            <div id="filterModalLocations" class="space-y-3">
              <!-- Dynamically populated -->
            </div>
          </div>

          <hr class="border-t border-tonal2" />

          <!-- Specific Problems -->
          <div>
            <h3 class="font-sans text-xs font-bold text-ink mb-3 uppercase tracking-wider">Specific Problems</h3>
            <div id="filterModalProblems" class="space-y-2">
              <!-- Dynamically populated -->
            </div>
          </div>
        </div>

        <footer class="p-3.5 bg-tonal1 border-t border-tonal2 flex gap-3 justify-end shrink-0">
          <button
            type="button"
            onclick="clearAdvancedFilters()"
            class="px-4 py-2 font-sans font-medium text-xs text-ink-muted hover:text-ink transition-colors rounded-[2px]"
          >
            Clear All
          </button>
          <button
            type="button"
            onclick="applyAdvancedFilters()"
            class="px-5 py-2 bg-fern hover:bg-fern-dark text-white font-sans font-bold text-xs transition-colors rounded-[2px]"
          >
            Apply Filters
          </button>
        </footer>
      </div>
    </div>


    <!-- ========================================== -->
    <!-- MODAL: ADD DISCREPANCY                     -->
    <!-- ========================================== -->
"""

content = content.replace(search_modal_end, replace_modal_end)

with open("backend/mobile_server.py", "w") as f:
    f.write(content)
