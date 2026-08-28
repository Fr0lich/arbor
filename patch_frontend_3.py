import re

with open("backend/mobile_server.py", "r") as f:
    content = f.read()

# Add JS functions for filtering
search_js_fetchList = """
    async function fetchList() {
      try {
        let url = `/api/objects?limit=150&q=${encodeURIComponent(searchQuery)}`;
        if (activeStatusFilter !== 'all') {
          url += `&status=${encodeURIComponent(activeStatusFilter)}`;
        }
"""

replace_js_fetchList = """
    function toggleNoImageFilter() {
      noImageFilterActive = !noImageFilterActive;
      const pill = document.getElementById('pill-no-image');
      if (noImageFilterActive) {
        pill.className = 'px-3 py-1 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center gap-1.5 transition-colors bg-ink text-white border-ink';
      } else {
        pill.className = 'px-3 py-1 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center gap-1.5 transition-colors bg-surface text-ink-muted border-bordercol hover:bg-tonal1';
      }
      fetchList();
    }

    function openFilterModal() {
      // Populate Location Filters
      const locContainer = document.getElementById('filterModalLocations');
      locContainer.innerHTML = '';
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.location) {
        activeSchema.ui_sections.location.forEach(field => {
          if (field.type === 'checkbox') return; // Skip bool locations for simplicity, or implement if needed

          let inputHtml = '';
          if (field.type === 'choice' && field.choices) {
            inputHtml = `
              <select id="filter_loc_${field.name}" class="w-full bg-surface border border-bordercol rounded-[2px] px-2.5 py-1.5 text-xs font-sans text-ink outline-none focus:border-fern cursor-pointer">
                <option value="">Any ${field.name}</option>
                ${field.choices.map(c => `<option value="${c}" ${activeAdvancedFilters.locations[field.name] === c ? 'selected' : ''}>${c}</option>`).join('')}
              </select>
            `;
          } else {
            inputHtml = `
              <input type="text" id="filter_loc_${field.name}" placeholder="Any ${field.name}..." value="${activeAdvancedFilters.locations[field.name] || ''}" class="w-full bg-surface border border-bordercol rounded-[2px] px-2.5 py-1.5 text-xs font-sans text-ink placeholder:text-ink-faint outline-none focus:border-fern" />
            `;
          }

          locContainer.innerHTML += `
            <div>
              <label class="block text-[11px] font-bold text-ink-muted mb-1">${field.name}</label>
              ${inputHtml}
            </div>
          `;
        });
      }

      // Populate Specific Problems
      const probContainer = document.getElementById('filterModalProblems');
      probContainer.innerHTML = '';

      // Static specific problems
      let staticProblems = [
        { name: "Any_Problem", label: "Any problem (except images)" },
        { name: "Images_Missing", label: "Missing Images" }
      ];

      let dynamicProblems = [];
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.problems) {
        dynamicProblems = activeSchema.ui_sections.problems.map(p => {
          return { name: p.name, label: p.name.replace('_Problem', '').replace(/_/g, ' ') };
        });
      }

      const allProblems = staticProblems.concat(dynamicProblems);

      allProblems.forEach(p => {
        const isChecked = activeAdvancedFilters.problems.includes(p.name);
        probContainer.innerHTML += `
          <label class="flex items-center gap-2 p-1.5 rounded-[2px] hover:bg-tonal1 cursor-pointer">
            <input type="checkbox" id="filter_prob_${p.name}" value="${p.name}" ${isChecked ? 'checked' : ''} class="w-4 h-4 text-fern rounded-[2px] border-bordercol cursor-pointer" />
            <span class="text-xs font-sans text-ink">${p.label}</span>
          </label>
        `;
      });

      openModal('filterModal');
    }

    function closeFilterModal() {
      closeModal('filterModal');
    }

    function applyAdvancedFilters() {
      // Gather Locations
      activeAdvancedFilters.locations = {};
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.location) {
        activeSchema.ui_sections.location.forEach(field => {
          if (field.type === 'checkbox') return;
          const el = document.getElementById(`filter_loc_${field.name}`);
          if (el && el.value.trim()) {
            activeAdvancedFilters.locations[field.name] = el.value.trim();
          }
        });
      }

      // Gather Problems
      activeAdvancedFilters.problems = [];
      const probCheckboxes = document.querySelectorAll('#filterModalProblems input[type="checkbox"]');
      probCheckboxes.forEach(cb => {
        if (cb.checked) {
          activeAdvancedFilters.problems.push(cb.value);
        }
      });

      closeFilterModal();
      fetchList();
    }

    function clearAdvancedFilters() {
      activeAdvancedFilters = { locations: {}, problems: [] };
      closeFilterModal();
      fetchList();
    }

    async function fetchList() {
      try {
        let url = `/api/objects?limit=150&q=${encodeURIComponent(searchQuery)}`;
        if (activeStatusFilter !== 'all') {
          url += `&status=${encodeURIComponent(activeStatusFilter)}`;
        }

        // Append No Image filter
        if (noImageFilterActive) {
          // If we also had specific problems, we append it, but handled below
        }

        // Append Location Filters
        for (const [key, val] of Object.entries(activeAdvancedFilters.locations)) {
          url += `&loc_${encodeURIComponent(key)}=${encodeURIComponent(val)}`;
        }

        // Append Specific Problems (merge with No Image pill logic)
        let combinedProblems = [...activeAdvancedFilters.problems];
        if (noImageFilterActive && !combinedProblems.includes('Images_Missing')) {
          combinedProblems.push('Images_Missing');
        }

        if (combinedProblems.length > 0) {
          url += `&specific_problems=${encodeURIComponent(combinedProblems.join(','))}`;
        }
"""

content = content.replace(search_js_fetchList, replace_js_fetchList)

with open("backend/mobile_server.py", "w") as f:
    f.write(content)
