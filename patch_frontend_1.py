import re

with open("backend/mobile_server.py", "r") as f:
    content = f.read()

# Add Filter button next to search box
search_box_html = """
        <!-- Search Input Box -->
        <div class="relative flex items-center gap-2">
          <div class="relative flex-1 flex items-center bg-tonal1 border border-bordercol rounded-[2px] transition-all search-active">
            <span class="text-ink-faint ml-2.5 shrink-0 text-xs">🔍</span>
            <input
              type="text"
              id="searchBox"
              oninput="debounceSearch()"
              placeholder="Search taxonomy, accession, collector, cabinet..."
              class="w-full bg-transparent px-2.5 py-2 font-sans text-xs text-ink placeholder:text-ink-faint outline-none"
            />
            <button
              type="button"
              id="searchClearBtn"
              onclick="clearSearch()"
              class="hidden p-1 mr-1.5 text-ink-faint hover:text-ink text-xs font-bold"
            >
              ✕
            </button>
          </div>

        </div>
"""

replace_box_html = """
        <!-- Search Input Box -->
        <div class="relative flex items-center gap-2">
          <div class="relative flex-1 flex items-center bg-tonal1 border border-bordercol rounded-[2px] transition-all search-active">
            <span class="text-ink-faint ml-2.5 shrink-0 text-xs">🔍</span>
            <input
              type="text"
              id="searchBox"
              oninput="debounceSearch()"
              placeholder="Search taxonomy, accession, collector, cabinet..."
              class="w-full bg-transparent px-2.5 py-2 font-sans text-xs text-ink placeholder:text-ink-faint outline-none"
            />
            <button
              type="button"
              id="searchClearBtn"
              onclick="clearSearch()"
              class="hidden p-1 mr-1.5 text-ink-faint hover:text-ink text-xs font-bold"
            >
              ✕
            </button>
          </div>

          <!-- Advanced Filter Modal Trigger -->
          <button
            type="button"
            onclick="openFilterModal()"
            class="p-2 bg-surface hover:bg-tonal1 border border-bordercol rounded-[2px] text-ink transition-colors touch-target-min flex items-center justify-center shrink-0"
            title="Advanced Filter"
          >
            <span class="text-ink text-sm font-mono">⚙</span>
          </button>
        </div>
"""

content = content.replace(search_box_html, replace_box_html)

# Add No Image pill
search_pills = """
          <button
            type="button"
            onclick="setStatusFilter('reviewed')"
            id="pill-reviewed"
            class="px-3 py-1 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center gap-1.5 transition-colors bg-fern-light text-fern-dark border-fern-border hover:bg-fern-light/80"
          >
            <span>✓</span>
            <span>Reviewed (0)</span>
          </button>
"""

replace_pills = """
          <button
            type="button"
            onclick="setStatusFilter('reviewed')"
            id="pill-reviewed"
            class="px-3 py-1 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center gap-1.5 transition-colors bg-fern-light text-fern-dark border-fern-border hover:bg-fern-light/80"
          >
            <span>✓</span>
            <span>Reviewed (0)</span>
          </button>

          <div class="w-px h-4 bg-tonal2 mx-0.5"></div>

          <button
            type="button"
            onclick="toggleNoImageFilter()"
            id="pill-no-image"
            class="px-3 py-1 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center gap-1.5 transition-colors bg-surface text-ink-muted border-bordercol hover:bg-tonal1"
          >
            <span>📷</span>
            <span>No Image</span>
          </button>
"""

content = content.replace(search_pills, replace_pills)

# Add variables to JS block
search_js_vars = """
    let activeStatusFilter = 'all';
    let activeSortBy = 'location';
    let searchQuery = '';
"""

replace_js_vars = """
    let activeStatusFilter = 'all';
    let noImageFilterActive = false;
    let activeAdvancedFilters = { locations: {}, problems: [] };
    let activeSortBy = 'location';
    let searchQuery = '';
"""

content = content.replace(search_js_vars, replace_js_vars)

with open("backend/mobile_server.py", "w") as f:
    f.write(content)
