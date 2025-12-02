(function () {
  const globalStatusEl = document.getElementById('responsesGlobalStatus');
  const tableContainer = document.getElementById('responsesTableContainer');
  const searchInput = document.getElementById('responsesSearchInput');
  const statusFilter = document.getElementById('responsesStatusFilter');
  const rangeSelect = document.getElementById('responsesRange');
  const customRangeRow = document.getElementById('responsesCustomRangeRow');
  const startDateInput = document.getElementById('responsesStartDate');
  const endDateInput = document.getElementById('responsesEndDate');
  const exportCsvBtn = document.getElementById('exportCsvBtn');

  function setGlobalStatus(text, type) {
    globalStatusEl.textContent = text || '';
    globalStatusEl.className = 'status' + (type ? ' ' + type : '');
  }

  function formatDateISO(d) {
    const year = d.getUTCFullYear();
    const month = String(d.getUTCMonth() + 1).padStart(2, '0');
    const day = String(d.getUTCDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  // Return a YYYY-MM-DD string for an ET calendar day offset from "today".
  // offsetDays = 0 => today in ET, -1 => yesterday in ET, etc.
  function getEtDateISO(offsetDays) {
    const now = new Date();
    // Extract the current date in America/New_York.
    const formatter = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/New_York',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
    const parts = formatter.formatToParts(now);
    let year = 0;
    let month = 0;
    let day = 0;
    for (const p of parts) {
      if (p.type === 'year') year = Number(p.value);
      else if (p.type === 'month') month = Number(p.value);
      else if (p.type === 'day') day = Number(p.value);
    }
    // Use a UTC date as a simple calendar container, then apply the offset.
    const base = new Date(Date.UTC(year, month - 1, day));
    base.setUTCDate(base.getUTCDate() + offsetDays);
    return formatDateISO(base);
  }

  function initDefaultDates() {
    if (rangeSelect) {
      rangeSelect.value = '7d';
    }
    applyRange('7d');
  }

  function applyRange(range) {
    let startISO = '';
    let endISO = '';

    if (range === 'today') {
      startISO = getEtDateISO(0);
      endISO = getEtDateISO(0);
    } else if (range === 'yesterday') {
      startISO = getEtDateISO(-1);
      endISO = getEtDateISO(-1);
    } else if (range === '7d') {
      endISO = getEtDateISO(0);
      startISO = getEtDateISO(-6);
    } else if (range === '30d') {
      endISO = getEtDateISO(0);
      startISO = getEtDateISO(-29);
    } else if (range === 'all') {
      startISO = '';
      endISO = '';
    } else if (range === 'custom') {
      if (customRangeRow) {
        customRangeRow.style.display = 'flex';
      }
      // Do not override any manually chosen dates for custom range.
      if (!startDateInput.value && !endDateInput.value) {
        const iso = getEtDateISO(0);
        startDateInput.value = iso;
        endDateInput.value = iso;
      }
      return;
    }

    if (customRangeRow) {
      customRangeRow.style.display = 'none';
    }

    startDateInput.value = startISO;
    endDateInput.value = endISO;
  }

  function getAdminHeaders() {
    return { 'Content-Type': 'application/json' };
  }

  function handleFetchError(resp, fallbackText) {
    if (!resp) {
      setGlobalStatus(fallbackText || 'Request failed (network error)', 'error');
      return;
    }
    resp
      .text()
      .then((text) => {
        setGlobalStatus(
          `Error ${resp.status}: ${text || resp.statusText || fallbackText || ''}`,
          'error',
        );
      })
      .catch(() => {
        setGlobalStatus(`Error ${resp.status}`, 'error');
      });
  }

  function escapeHTML(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function truncate(str, max) {
    if (!str) return '';
    const s = String(str);
    return s.length > max ? s.slice(0, max - 1) + '…' : s;
  }

  function parseDateAsUTC(dateString) {
    if (!dateString) return null;
    const hasTZ = /[zZ]$|[+-]\d\d:\d\d$/.test(dateString);
    const iso = hasTZ ? dateString : dateString + 'Z';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function formatInEST(date, options) {
    if (!date) return '';
    const formatter = new Intl.DateTimeFormat(undefined, {
      timeZone: 'America/New_York',
      ...options,
    });
    return formatter.format(date);
  }

  function renderAnswerMarkdown(raw) {
    if (!raw) {
      return '<span class="inline-muted">(No answer recorded.)</span>';
    }
    let html = String(raw);

    // First, fix spaces before closing brackets/parentheses in markdown links
    // Handle [text ](url) pattern - space before ]
    html = html.replace(/\[([^\]]+)\s+\]\(/g, '[$1](');
    // Handle [text](url ) pattern - space before closing )
    html = html.replace(/\]\(([^)]+)\s+\)/g, ']($1)');
    // Handle ("text" ) pattern - space before ) in parenthetical citations
    html = html.replace(/\(\s*"([^"]+)"\s+\)/g, '("$1")');
    // Handle (text ) pattern - space before ) in parenthetical text
    html = html.replace(/\(([^)"]+)\s+\)/g, '($1)');

    html = html
      // Convert ### headings (h3)
      .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-4 mb-2 text-white">$1</h3>')
      // Convert ## headings (h2)
      .replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold mt-5 mb-2 text-white">$1</h2>')
      // Convert # headings (h1)
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-6 mb-3 text-white">$1</h1>')
      // Convert [source] links to clipboard icon with punctuation
      .replace(
        /\[source\]\(([^)]+)\)([.,!?;:])/gi,
        '<a href="$1" target="_blank" rel="noopener noreferrer" class="inline text-blue-300 hover:text-blue-200 transition-colors mx-0.5" title="View source" style="display: inline; vertical-align: middle;"><span style="display: inline-flex; align-items: center; background: rgba(0, 0, 0, 0.3); border-radius: 4px; padding: 2px 4px;"><svg style="width: 14px; height: 14px; display: block;" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg></span></a>$2',
      )
      // Convert remaining [source] links (without trailing punctuation)
      .replace(
        /\[source\]\(([^)]+)\)/gi,
        '<a href="$1" target="_blank" rel="noopener noreferrer" class="inline text-blue-300 hover:text-blue-200 transition-colors mx-0.5" title="View source" style="display: inline; vertical-align: middle;"><span style="display: inline-flex; align-items: center; background: rgba(0, 0, 0, 0.3); border-radius: 4px; padding: 2px 4px;"><svg style="width: 14px; height: 14px; display: block;" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg></span></a>',
      )
      // Convert numbered citation links [1], [2], etc. with punctuation
      .replace(
        /\[(\d+|\*)\]\(([^)]+)\)([.,!?;:])/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer" class="inline text-blue-300 hover:text-blue-200 transition-colors mx-0.5" title="View source" style="display: inline; vertical-align: middle;"><span style="display: inline-flex; align-items: center; background: rgba(0, 0, 0, 0.3); border-radius: 4px; padding: 2px 4px;"><svg style="width: 14px; height: 14px; display: block;" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg></span></a>$3',
      )
      // Convert numbered citation links [1], [2], etc. without trailing punctuation
      .replace(
        /\[(\d+|\*)\]\(([^)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer" class="inline text-blue-300 hover:text-blue-200 transition-colors mx-0.5" title="View source" style="display: inline; vertical-align: middle;"><span style="display: inline-flex; align-items: center; background: rgba(0, 0, 0, 0.3); border-radius: 4px; padding: 2px 4px;"><svg style="width: 14px; height: 14px; display: block;" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg></span></a>',
      )
      // Convert markdown links [text](url) to HTML links with spacing after punctuation
      .replace(
        /\[([^\]]+)\]\(([^)]+)\)([.,!?;:])/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-blue-300 hover:text-blue-200 underline">$1</a>$3 ',
      )
      // Convert remaining markdown links (without trailing punctuation)
      .replace(
        /\[([^\]]+)\]\(([^)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-blue-300 hover:text-blue-200 underline">$1</a> ',
      )
      // Convert bold text **text** to HTML bold
      .replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold">$1</strong>')
      // Convert bullet points (- item) to styled list items
      .replace(/^- (.+)$/gm, '<span class="block ml-4 before:content-[\'•\'] before:mr-2 before:text-blue-400">$1</span>')
      // Add space after punctuation if followed by newline and capital letter (new sentence)
      .replace(/([.,!?;:])\n([A-Z])/g, '$1 $2')
      // Convert remaining single line breaks to <br> with spacing
      .replace(/\n/g, '<br class="mb-3">')
      // Style the cursor to make it blink
      .replace(/\|$/, '<span class="inline-block animate-pulse ml-0.5 font-bold">|</span>');

    return html;
  }

  function renderResponsesSkeletonTable() {
    const rows = Array.from({ length: 3 })
      .map(
        () => `
        <tr class="log-row">
          <td style="width:130px;">
            <div class="skeleton-pill"></div>
          </td>
          <td style="width:120px;">
            <div class="skeleton-line" style="width:80%;"></div>
            <div class="skeleton-line" style="width:60%;"></div>
          </td>
          <td>
            <div class="skeleton-line" style="width:90%;"></div>
            <div class="skeleton-line" style="width:70%;"></div>
          </td>
          <td>
            <div class="skeleton-line" style="width:95%;"></div>
            <div class="skeleton-line" style="width:65%;"></div>
          </td>
        </tr>
      `,
      )
      .join('');

    return `
      <table>
        <thead>
          <tr>
            <th style="width:130px;">Actions</th>
            <th style="width:120px;">When / Status</th>
            <th>Question</th>
            <th>Answer</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    `;
  }

  function renderDetailSkeleton() {
    return `
      <div>
        <div class="skeleton-line" style="width:40%;"></div>
        <div class="skeleton-line" style="width:60%;"></div>
        <div class="skeleton-line" style="width:30%;margin-top:8px;"></div>
        <div class="skeleton-line" style="width:90%;margin-top:12px;"></div>
        <div class="skeleton-line" style="width:95%;"></div>
        <div class="skeleton-line" style="width:88%;"></div>
      </div>
    `;
  }

  async function fetchLogs() {
    const params = new URLSearchParams();
    if (startDateInput.value) params.set('start_date', startDateInput.value);
    if (endDateInput.value) params.set('end_date', endDateInput.value);
    if (searchInput.value.trim()) params.set('q', searchInput.value.trim());
    // Backend expects `status_filter` query param (see admin_api.list_query_logs).
    if (statusFilter && statusFilter.value) params.set('status_filter', statusFilter.value);

    const url = './query-logs?' + params.toString();
    setGlobalStatus('Loading logs...', '');
    tableContainer.innerHTML = renderResponsesSkeletonTable();

    try {
      const resp = await fetch(url, { headers: getAdminHeaders() });
      if (!resp.ok) {
        tableContainer.innerHTML = '';
        handleFetchError(resp, 'Failed to load logs.');
        return;
      }
      const data = await resp.json();
      renderTable(Array.isArray(data) ? data : []);
      setGlobalStatus('', '');
    } catch (err) {
      tableContainer.innerHTML =
        '<div class="status error">Failed to load logs (network error).</div>';
      setGlobalStatus('Failed to load logs.', 'error');
    }
  }

  function renderTable(logs) {
    if (!logs.length) {
      tableContainer.innerHTML =
        '<div class="inline-muted">No logs for this range yet. Try a different date range or clear search.</div>';
      return;
    }

    const rows = logs
      .map((log) => {
        const created = log.created_at ? parseDateAsUTC(log.created_at) : null;
        const createdStr = created
          ? formatInEST(created, {
              month: 'short',
              day: 'numeric',
              hour: 'numeric',
              minute: '2-digit',
            }) + ' ET'
          : '';
        const statusLabel = escapeHTML(log.status || '');

        const question = escapeHTML(truncate(log.user_message || '', 160));
        const answer = escapeHTML(truncate(log.final_answer || '', 200));

        const isBlacklisted = !!log.is_blacklist_example;
        const isWhitelisted = !!log.is_whitelist_example;
        const isBlocked = (log.status || '').toLowerCase() === 'blocked';

        let actionHtml = '';
        if (isWhitelisted) {
          // Whitelist wins regardless of status.
          actionHtml = `<button class="secondary blacklisted-btn js-whitelist-toggle" data-log-id="${log.id}" data-default-label="Whitelisted">
            Whitelisted
          </button>`;
        } else if (isBlacklisted) {
          // Blacklist wins if no whitelist example exists.
          actionHtml = `<button class="secondary blacklisted-btn js-blacklist-toggle" data-log-id="${log.id}" data-default-label="Blacklisted">
            Blacklisted
          </button>`;
        } else if (isBlocked) {
          // Default for blocked (no whitelist/blacklist yet): allow whitelisting.
          actionHtml = `<button class="secondary js-whitelist-btn" data-log-id="${log.id}">
            Add to Whitelist
          </button>`;
        } else {
          // Default for answered/unblocked: allow blacklisting.
          actionHtml = `<button class="secondary js-blacklist-btn" data-log-id="${log.id}">
            Add to Blacklist
          </button>`;
        }

        return `
          <tr class="log-row" data-log-id="${log.id}">
            <td style="width:130px;white-space:nowrap;">
              ${actionHtml}
            </td>
            <td style="width:120px;">
              <div class="inline-muted">${createdStr}</div>
              <div class="pill" style="margin-top:4px;">${statusLabel}</div>
            </td>
            <td title="${escapeHTML(log.user_message || '')}">
              ${question}
            </td>
            <td title="${escapeHTML(log.final_answer || '')}">
              ${answer}
            </td>
          </tr>
          <tr class="log-detail-row" data-log-id="${log.id}" style="display:none;">
            <td colspan="4">
              <div class="inline-muted" style="margin-bottom:4px;">
                Click to collapse. Showing full metadata for this interaction.
              </div>
              <div class="log-detail-content">Loading details...</div>
            </td>
          </tr>
        `;
      })
      .join('');

    const tableHtml = `
      <table>
        <thead>
          <tr>
            <th style="width:130px;">Actions</th>
            <th style="width:120px;">When / Status</th>
            <th>Question</th>
            <th>Answer</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    `;

    tableContainer.innerHTML = tableHtml;

    const tbody = tableContainer.querySelector('tbody');
    if (!tbody) return;

    tbody.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      // Blacklist button
      const blacklistBtn = target.closest('.js-blacklist-btn');
      if (blacklistBtn) {
        const id = blacklistBtn.getAttribute('data-log-id');
        if (id) {
          event.stopPropagation();
          addToBlacklist(id, blacklistBtn);
        }
        return;
      }

      // Whitelist button (only shown for blocked queries)
      const whitelistBtn = target.closest('.js-whitelist-btn');
      if (whitelistBtn) {
        const id = whitelistBtn.getAttribute('data-log-id');
        if (id) {
          event.stopPropagation();
          addToWhitelist(id, whitelistBtn);
        }
        return;
      }

      // Blacklist toggle (already blacklisted -> allow removal)
      const blacklistToggle = target.closest('.js-blacklist-toggle');
      if (blacklistToggle) {
        const id = blacklistToggle.getAttribute('data-log-id');
        if (id) {
          event.stopPropagation();
          removeFromBlacklist(id, blacklistToggle);
        }
        return;
      }

      // Whitelist toggle (already whitelisted -> allow removal)
      const whitelistToggle = target.closest('.js-whitelist-toggle');
      if (whitelistToggle) {
        const id = whitelistToggle.getAttribute('data-log-id');
        if (id) {
          event.stopPropagation();
          removeFromWhitelist(id, whitelistToggle);
        }
        return;
      }

      const row = target.closest('tr.log-row');
      if (!row) return;
      const logId = row.getAttribute('data-log-id');
      if (!logId) return;
      toggleDetailRow(logId, row);
    });
  }

  async function toggleDetailRow(logId, rowEl) {
    const detailRow = tableContainer.querySelector(
      'tr.log-detail-row[data-log-id="' + logId + '"]',
    );
    if (!detailRow) return;

    const isHidden = detailRow.style.display === 'none';

    // Collapse all other detail rows
    tableContainer.querySelectorAll('tr.log-detail-row').forEach((tr) => {
      tr.style.display = 'none';
    });
    tableContainer.querySelectorAll('tr.log-row').forEach((tr) => {
      tr.classList.remove('selected');
    });

    if (!isHidden) {
      // Already visible -> we just collapsed everything so nothing to do.
      return;
    }

    detailRow.style.display = '';
    rowEl.classList.add('selected');

    const contentEl = detailRow.querySelector('.log-detail-content');
    if (!contentEl) return;

    contentEl.innerHTML = renderDetailSkeleton();
    try {
      const resp = await fetch('./query-logs/' + encodeURIComponent(logId), {
        headers: getAdminHeaders(),
      });
      if (!resp.ok) {
        handleFetchError(resp, 'Failed to load log details.');
        contentEl.textContent = 'Failed to load details.';
        return;
      }
      const detail = await resp.json();
      renderDetail(detail, contentEl);
    } catch (err) {
      contentEl.textContent = 'Failed to load details (network error).';
    }
  }

  function renderDetail(detail, container) {
    const blockedBy = detail.blocked_by || '—';
    const errorMessage = detail.error_message || '';
    const blacklistExample =
      typeof detail.is_blacklist_example === 'boolean'
        ? detail.is_blacklist_example
          ? 'yes'
          : 'no'
        : '—';
    const whitelistExample =
      typeof detail.is_whitelist_example === 'boolean'
        ? detail.is_whitelist_example
          ? 'yes'
          : 'no'
        : '—';
    const created = detail.created_at ? parseDateAsUTC(detail.created_at) : null;
    const createdFull = created
      ? formatInEST(created, {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
        }) + ' ET'
      : '';

    const headerHtml = `
      <div style="margin-bottom:8px;">
        <div class="inline-muted">Log ID: ${detail.id}</div>
        <div class="inline-muted">Created at: ${escapeHTML(createdFull)}</div>
        <div class="inline-muted">Status: ${escapeHTML(detail.status || '')}</div>
        <div class="inline-muted">Blocked by: ${escapeHTML(blockedBy)}</div>
        <div class="inline-muted">Blacklist example: ${escapeHTML(blacklistExample)}</div>
        <div class="inline-muted">Whitelist example: ${escapeHTML(whitelistExample)}</div>
        ${
          errorMessage
            ? `<div class="inline-muted">Error: ${escapeHTML(errorMessage)}</div>`
            : ''
        }
      </div>
    `;

    let partsHtml = '';
    if (Array.isArray(detail.parts) && detail.parts.length) {
      partsHtml =
        '<h3>Stages</h3>' +
        '<table>' +
        '<thead><tr><th>Stage</th><th>Model</th><th>Agent</th><th>Blocked?</th><th>Details</th></tr></thead>' +
        '<tbody>' +
        detail.parts
          .map((p) => {
            const when = p.created_at
              ? formatInEST(parseDateAsUTC(p.created_at), {
                  hour: 'numeric',
                  minute: '2-digit',
                  second: '2-digit',
                }) + ' ET'
              : '';
            const blocked = typeof p.blocked === 'boolean' ? (p.blocked ? 'yes' : 'no') : '—';
            const result = p.result || {};
            const reasoning = result.reasoning || result.reason || '';
            const isLegit =
              typeof result.is_legitimate_colby_query === 'boolean'
                ? `is_legitimate_colby_query=${result.is_legitimate_colby_query}`
                : '';
            const extra = isLegit || reasoning
              ? escapeHTML(
                  [isLegit, reasoning]
                    .filter(Boolean)
                    .join(' – '),
                )
              : '';
            return `
              <tr>
                <td>${escapeHTML(p.stage || '')}<br /><span class="inline-muted">${escapeHTML(
                  when,
                )}</span></td>
                <td>${escapeHTML(p.model_id || '')}</td>
                <td>${escapeHTML(p.agent_name || '')}</td>
                <td>${escapeHTML(blocked)}</td>
                <td>${extra}</td>
              </tr>
            `;
          })
          .join('') +
        '</tbody></table>';
    } else {
      partsHtml =
        '<div class="inline-muted">No per-stage metadata recorded for this query.</div>';
    }

    const fullQuestion = escapeHTML(detail.user_message || '');
    const answerHtml = renderAnswerMarkdown(detail.final_answer || '');

    const qaHtml = `
      <h3>Question</h3>
      <pre style="white-space:pre-wrap;font-size:0.8rem;">${fullQuestion}</pre>
      <h3>Answer</h3>
      <div style="font-size:0.8rem;line-height:1.5;">${answerHtml}</div>
    `;

    container.innerHTML = headerHtml + qaHtml + partsHtml;
  }

  async function addToBlacklist(logId, buttonEl) {
    if (!buttonEl) return;
    buttonEl.disabled = true;
    const originalText = buttonEl.textContent || 'Add to blacklist';
    buttonEl.textContent = 'Adding...';

    try {
      const resp = await fetch('./query-logs/' + encodeURIComponent(logId) + '/blacklist', {
        method: 'POST',
        headers: getAdminHeaders(),
      });
      if (!resp.ok) {
        handleFetchError(resp, 'Failed to add query to blacklist.');
        buttonEl.disabled = false;
        buttonEl.textContent = originalText;
        return;
      }
      const data = await resp.json();
      setGlobalStatus(data.message || 'Query added to blacklist.', 'success');
      buttonEl.textContent = 'Blacklisted';
      buttonEl.classList.add('blacklisted-btn');
      buttonEl.disabled = true;
      buttonEl.setAttribute('aria-disabled', 'true');
    } catch (err) {
      setGlobalStatus('Failed to add query to blacklist.', 'error');
      buttonEl.disabled = false;
      buttonEl.textContent = originalText;
    }
  }

  async function addToWhitelist(logId, buttonEl) {
    if (!buttonEl) return;
    buttonEl.disabled = true;
    const originalText = buttonEl.textContent || 'Add to Whitelist';
    buttonEl.textContent = 'Adding...';

    try {
      const resp = await fetch('./query-logs/' + encodeURIComponent(logId) + '/whitelist', {
        method: 'POST',
        headers: getAdminHeaders(),
      });
      if (!resp.ok) {
        handleFetchError(resp, 'Failed to add query to whitelist.');
        buttonEl.disabled = false;
        buttonEl.textContent = originalText;
        return;
      }
      const data = await resp.json();
      setGlobalStatus(data.message || 'Query added to whitelist.', 'success');
      buttonEl.textContent = 'Whitelisted';
      buttonEl.classList.add('blacklisted-btn');
      buttonEl.disabled = true;
      buttonEl.setAttribute('aria-disabled', 'true');
    } catch (err) {
      setGlobalStatus('Failed to add query to whitelist.', 'error');
      buttonEl.disabled = false;
      buttonEl.textContent = originalText;
    }
  }

  async function removeFromBlacklist(logId, buttonEl) {
    if (!buttonEl) return;
    buttonEl.disabled = true;
    const originalText = buttonEl.textContent || 'Blacklisted';
    buttonEl.textContent = 'Removing...';

    try {
      const resp = await fetch('./query-logs/' + encodeURIComponent(logId) + '/blacklist', {
        method: 'DELETE',
        headers: getAdminHeaders(),
      });
      if (!resp.ok) {
        handleFetchError(resp, 'Failed to remove query from blacklist.');
        buttonEl.disabled = false;
        buttonEl.textContent = originalText;
        return;
      }
      const data = await resp.json();
      setGlobalStatus(data.message || 'Query removed from blacklist.', 'success');
      // Reload logs so buttons and flags refresh consistently.
      fetchLogs();
    } catch (err) {
      setGlobalStatus('Failed to remove query from blacklist.', 'error');
      buttonEl.disabled = false;
      buttonEl.textContent = originalText;
    }
  }

  async function removeFromWhitelist(logId, buttonEl) {
    if (!buttonEl) return;
    buttonEl.disabled = true;
    const originalText = buttonEl.textContent || 'Whitelisted';
    buttonEl.textContent = 'Removing...';

    try {
      const resp = await fetch('./query-logs/' + encodeURIComponent(logId) + '/whitelist', {
        method: 'DELETE',
        headers: getAdminHeaders(),
      });
      if (!resp.ok) {
        handleFetchError(resp, 'Failed to remove query from whitelist.');
        buttonEl.disabled = false;
        buttonEl.textContent = originalText;
        return;
      }
      const data = await resp.json();
      setGlobalStatus(data.message || 'Query removed from whitelist.', 'success');
      // Reload logs so buttons and flags refresh consistently.
      fetchLogs();
    } catch (err) {
      setGlobalStatus('Failed to remove query from whitelist.', 'error');
      buttonEl.disabled = false;
      buttonEl.textContent = originalText;
    }
  }

  async function exportCsv() {
    const params = new URLSearchParams();
    if (startDateInput.value) params.set('start_date', startDateInput.value);
    if (endDateInput.value) params.set('end_date', endDateInput.value);
    if (searchInput.value.trim()) params.set('q', searchInput.value.trim());
    if (statusFilter && statusFilter.value) params.set('status_filter', statusFilter.value);

    const url = './query-logs/export/csv?' + params.toString();

    if (exportCsvBtn) {
      exportCsvBtn.disabled = true;
      exportCsvBtn.textContent = 'Exporting...';
    }
    setGlobalStatus('Generating CSV export...', '');

    try {
      const resp = await fetch(url, { headers: getAdminHeaders() });
      if (!resp.ok) {
        handleFetchError(resp, 'Failed to export CSV.');
        if (exportCsvBtn) {
          exportCsvBtn.disabled = false;
          exportCsvBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Export as CSV
          `;
        }
        return;
      }

      // Get filename from Content-Disposition header or use default
      const contentDisposition = resp.headers.get('Content-Disposition');
      let filename = 'chatbot_logs.csv';
      if (contentDisposition) {
        const match = contentDisposition.match(/filename=([^;]+)/);
        if (match) {
          filename = match[1].trim().replace(/"/g, '');
        }
      }

      const blob = await resp.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);

      setGlobalStatus('CSV exported successfully.', 'success');
    } catch (err) {
      setGlobalStatus('Failed to export CSV (network error).', 'error');
    } finally {
      if (exportCsvBtn) {
        exportCsvBtn.disabled = false;
        exportCsvBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Export as CSV
        `;
      }
    }
  }

  let searchDebounceTimer = null;

  function attachEventHandlers() {
    if (startDateInput) {
      startDateInput.addEventListener('change', () => {
        if (rangeSelect && rangeSelect.value !== 'custom') {
          rangeSelect.value = 'custom';
        }
        applyRange('custom');
        fetchLogs();
      });
    }
    if (endDateInput) {
      endDateInput.addEventListener('change', () => {
        if (rangeSelect && rangeSelect.value !== 'custom') {
          rangeSelect.value = 'custom';
        }
        applyRange('custom');
        fetchLogs();
      });
    }

    if (rangeSelect) {
      rangeSelect.addEventListener('change', () => {
        applyRange(rangeSelect.value);
        fetchLogs();
      });
    }

    searchInput.addEventListener('input', () => {
      if (searchDebounceTimer) {
        clearTimeout(searchDebounceTimer);
      }
      searchDebounceTimer = setTimeout(() => {
        fetchLogs();
      }, 300);
    });

    if (statusFilter) {
      statusFilter.addEventListener('change', () => {
        fetchLogs();
      });
    }

    if (exportCsvBtn) {
      exportCsvBtn.addEventListener('click', () => {
        exportCsv();
      });
    }

    // Hover behavior for blacklist/whitelist toggle buttons (change label on hover).
    tableContainer.addEventListener('mouseover', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      const toggle =
        target.closest('.js-blacklist-toggle') || target.closest('.js-whitelist-toggle');
      if (!toggle) return;

      const defaultLabel = toggle.getAttribute('data-default-label') || toggle.textContent || '';
      toggle.setAttribute('data-default-label', defaultLabel);

      if (toggle.classList.contains('js-blacklist-toggle')) {
        toggle.textContent = 'Remove from Blacklist';
      } else if (toggle.classList.contains('js-whitelist-toggle')) {
        toggle.textContent = 'Remove from Whitelist';
      }
    });

    tableContainer.addEventListener('mouseout', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      const toggle =
        target.closest('.js-blacklist-toggle') || target.closest('.js-whitelist-toggle');
      if (!toggle) return;

      const defaultLabel = toggle.getAttribute('data-default-label');
      if (defaultLabel) {
        toggle.textContent = defaultLabel;
      }
    });
  }

  (function bootstrap() {
    initDefaultDates();
    attachEventHandlers();
    fetchLogs();
  })();
})();


