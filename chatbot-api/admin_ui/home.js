// Home dashboard script: loads last-7-days metrics and renders summary cards.

function formatPercent(numerator, denominator) {
  if (!denominator || denominator <= 0) return '0';
  const pct = (numerator / denominator) * 100;
  const txt = pct.toFixed(1);
  return txt.endsWith('.0') ? txt.slice(0, -2) : txt;
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

function renderWeeklySkeleton(container) {
  if (!container) return;
  container.innerHTML = `
    <div style="margin-bottom:10px;">
      <div class="skeleton-line" style="width:32%;height:14px;margin-bottom:8px;"></div>
      <div class="skeleton-line" style="width:22%;height:10px;"></div>
    </div>
    <div class="row" style="margin-top:4px;">
      <div class="col">
        <div class="skeleton-pill" style="height:54px;"></div>
      </div>
      <div class="col">
        <div class="skeleton-pill" style="height:54px;"></div>
      </div>
      <div class="col">
        <div class="skeleton-pill" style="height:54px;"></div>
      </div>
    </div>
  `;
}

function renderWeeklyError(container, message) {
  if (!container) return;
  container.innerHTML = `
    <div class="status error">${escapeHTML(message || 'Failed to load weekly metrics.')}</div>
  `;
}

function renderWeeklyMetrics(container, data, rangeLabel, rangeValue) {
  if (!container) return;

  const total = data?.total_queries ?? 0;
  const answered = data?.answered ?? 0;
  const blocked = data?.blocked ?? 0;

  const answeredRate = formatPercent(answered, total);
  const blockedRate = formatPercent(blocked, total);

  const blockedByQuery = data?.blocked_by_query_validator ?? 0;
  const blockedByBlacklist = data?.blocked_by_blacklist_validator ?? 0;
  const blockedByBoth = data?.blocked_by_both ?? 0;
  const passedGuardrails = data?.passed_guardrails ?? 0;
  const noAnswerAfterPass = data?.no_answer_after_pass ?? 0;

  const labelSuffix = rangeLabel ? rangeLabel.toLowerCase() : 'last 7 days';
  const currentRange = rangeValue || '7d';

  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;margin-bottom:10px;">
      <div style="margin-left:8px;">
        <h2 style="margin:0 0 0 0;font-size:1.5rem;">Quick Analytics</h2>
        <div class="inline-muted" style="margin-top:8px;">Chatbot queries and safety performance (ET).</div>
      </div>
      <div style="min-width:180px;text-align:right;">
        <select id="homeMetricsRange" class="range-select" style="min-width:160px;">
          <option value="7d"${currentRange === '7d' ? ' selected' : ''}>Last 7 days</option>
          <option value="today"${currentRange === 'today' ? ' selected' : ''}>Today</option>
          <option value="yesterday"${currentRange === 'yesterday' ? ' selected' : ''}>Yesterday</option>
          <option value="30d"${currentRange === '30d' ? ' selected' : ''}>Last 30 days</option>
          <option value="all"${currentRange === 'all' ? ' selected' : ''}>All time</option>
        </select>
      </div>
    </div>

    <div class="row" style="margin-top:14px;">
      <div class="col">
        <div style="background:rgba(15,23,42,0.9);border-radius:14px;padding:12px 14px;border:1px solid rgba(148,163,184,0.35);">
          <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:#9ca3af;font-weight:600;">
            Total queries
          </div>
          <div style="font-size:1.7rem;font-weight:600;color:#e5e7eb;margin-top:4px;">
            ${total}
          </div>
          <div class="inline-muted" style="margin-top:4px;">
            Across all agents (${escapeHTML(labelSuffix)})
          </div>
        </div>
      </div>
      <div class="col">
        <div style="background:linear-gradient(135deg, rgba(22,163,74,0.25), rgba(22,163,74,0.05));border-radius:14px;padding:12px 14px;border:1px solid rgba(74,222,128,0.4);">
          <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:#bbf7d0;font-weight:600;">
            Answered
          </div>
          <div style="font-size:1.7rem;font-weight:600;color:#bbf7d0;margin-top:4px;">
            ${answered}
          </div>
          <div style="font-size:0.8rem;color:#dcfce7;margin-top:4px;">
            ${answeredRate}% of all queries
          </div>
        </div>
      </div>
      <div class="col">
        <div style="background:linear-gradient(135deg, rgba(248,113,113,0.3), rgba(127,29,29,0.1));border-radius:14px;padding:12px 14px;border:1px solid rgba(248,113,113,0.55);">
          <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;color:#fecaca;font-weight:600;">
            Blocked
          </div>
          <div style="font-size:1.7rem;font-weight:600;color:#fee2e2;margin-top:4px;">
            ${blocked}
          </div>
          <div style="font-size:0.8rem;color:#fee2e2;margin-top:4px;">
            ${blockedRate}% flagged as unsafe or out of scope
          </div>
        </div>
      </div>
    </div>

    <div class="row" style="margin-top:14px;">
      <div class="col">
        <div style="border-radius:14px;padding:12px 14px;border:1px solid rgba(148,163,184,0.4);background:rgba(15,23,42,0.9);">
          <div style="font-size:0.85rem;font-weight:600;margin-bottom:6px;">Guardrail performance</div>
          <table style="margin-top:0;font-size:0.8rem;">
            <tbody>
              <tr>
                <td style="border:none;padding:2px 0;">Blocked by Colby Query Validator</td>
                <td style="border:none;padding:2px 0;text-align:right;font-weight:600;">${blockedByQuery}</td>
              </tr>
              <tr>
                <td style="border:none;padding:2px 0;">Blocked by Colby Blacklist Validator</td>
                <td style="border:none;padding:2px 0;text-align:right;font-weight:600;">${blockedByBlacklist}</td>
              </tr>
              <tr>
                <td style="border:none;padding:2px 0;">Blocked by both</td>
                <td style="border:none;padding:2px 0;text-align:right;font-weight:600;">${blockedByBoth}</td>
              </tr>
              <tr>
                <td style="border:none;padding:2px 0;">Passed guardrails</td>
                <td style="border:none;padding:2px 0;text-align:right;font-weight:600;color:#4ade80;">${passedGuardrails}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="col">
        <div style="border-radius:14px;padding:12px 14px;border:1px solid rgba(250,204,21,0.4);background:rgba(113,63,18,0.45);">
          <div style="font-size:0.85rem;font-weight:600;margin-bottom:6px;">No‑answer cases</div>
          <div style="font-size:0.8rem;color:#fef9c3;line-height:1.5;">
            ${noAnswerAfterPass} queries passed both guardrail agents but the main answer agent returned the standard rejection message.
          </div>
        </div>
      </div>
    </div>
  `;

  const rangeSelect = document.getElementById('homeMetricsRange');
  if (rangeSelect) {
    rangeSelect.addEventListener('change', () => {
      const value = rangeSelect.value || '7d';
      loadMetricsForRange(value);
    });
  }
}

function getEtDateISO(offsetDays) {
  const now = new Date();
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
  const base = new Date(Date.UTC(year, month - 1, day));
  base.setUTCDate(base.getUTCDate() + offsetDays);
  const y = base.getUTCFullYear();
  const m = String(base.getUTCMonth() + 1).padStart(2, '0');
  const d = String(base.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function computeRange(range) {
  let startISO = '';
  let endISO = '';
  let label = '';

  if (range === 'today') {
    startISO = getEtDateISO(0);
    endISO = getEtDateISO(0);
    label = 'today';
  } else if (range === 'yesterday') {
    startISO = getEtDateISO(-1);
    endISO = getEtDateISO(-1);
    label = 'yesterday';
  } else if (range === '30d') {
    endISO = getEtDateISO(0);
    startISO = getEtDateISO(-29);
    label = 'last 30 days';
  } else if (range === 'all') {
    // "All time": start far in the past and end today.
    startISO = '1970-01-01';
    endISO = getEtDateISO(0);
    label = 'all time';
  } else {
    // Default + explicit '7d': last 7 days.
    endISO = getEtDateISO(0);
    startISO = getEtDateISO(-6);
    label = 'last 7 days';
  }

  return { startISO, endISO, label };
}

async function loadMetricsForRange(range) {
  const container = document.getElementById('weeklySummary');
  if (!container) return;

  renderWeeklySkeleton(container);

  const { startISO, endISO, label } = computeRange(range || '7d');
  const params = new URLSearchParams();
  if (startISO) params.set('start_date', startISO);
  if (endISO) params.set('end_date', endISO);

  const url = './metrics/weekly' + (params.toString() ? `?${params.toString()}` : '');

  try {
    const resp = await fetch(url);
    if (!resp.ok) {
      renderWeeklyError(container, `Failed to load weekly metrics (HTTP ${resp.status}).`);
      return;
    }
    const data = await resp.json();
    renderWeeklyMetrics(container, data || {}, label, range);
  } catch (err) {
    renderWeeklyError(container, 'Failed to load weekly metrics (network error).');
  }
}

loadMetricsForRange('7d');


