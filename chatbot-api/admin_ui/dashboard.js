(function () {
  const globalStatusEl = document.getElementById('globalStatus');
  const agentsTableContainer = document.getElementById('agentsTableContainer');
  const agentsRelationshipsEl = document.getElementById('agentsRelationships');
  const agentKeyInput = document.getElementById('agentKeyInput');
  const agentNameInput = document.getElementById('agentNameInput');
  const agentModelIdInput = document.getElementById('agentModelIdInput');
  const agentDescriptionInput = document.getElementById('agentDescriptionInput');
  const agentInstructionsInput = document.getElementById('agentInstructionsInput');
  const saveAgentBtn = document.getElementById('saveAgentBtn');
  const agentStatus = document.getElementById('agentStatus');
  const rejectionTextarea = document.getElementById('rejectionMessage');
  const rejectionStatus = document.getElementById('rejectionStatus');
  const saveRejectionBtn = document.getElementById('saveRejectionBtn');
  const trainingExamplesCard = document.getElementById('trainingExamplesCard');
  const blacklistExamplesList = document.getElementById('blacklistExamplesList');
  const whitelistExamplesList = document.getElementById('whitelistExamplesList');
  const blacklistExamplesSearch = document.getElementById('blacklistExamplesSearch');
  const whitelistExamplesSearch = document.getElementById('whitelistExamplesSearch');
  const addBlacklistExampleBtn = document.getElementById('addBlacklistExampleBtn');
  const addWhitelistExampleBtn = document.getElementById('addWhitelistExampleBtn');
  const saveTrainingExamplesBtn = document.getElementById('saveTrainingExamplesBtn');
  const trainingExamplesStatus = document.getElementById('trainingExamplesStatus');

  function setGlobalStatus(text, type) {
    globalStatusEl.textContent = text || '';
    globalStatusEl.className = 'status' + (type ? ' ' + type : '');
  }

  function getAdminHeaders() {
    return { 'Content-Type': 'application/json' };
  }

  function handleFetchError(sectionStatusEl, resp) {
    if (!resp) {
      sectionStatusEl.textContent = 'Request failed (network error)';
      sectionStatusEl.className = 'status error';
      return;
    }
    resp
      .text()
      .then((text) => {
        sectionStatusEl.textContent = 'Error ' + resp.status + ': ' + (text || resp.statusText);
        sectionStatusEl.className = 'status error';
      })
      .catch(() => {
        sectionStatusEl.textContent = 'Error ' + resp.status;
        sectionStatusEl.className = 'status error';
      });
  }

  // --- Rejection message section ---
  async function loadRejectionMessage() {
    rejectionStatus.textContent = 'Loading...';
    rejectionStatus.className = 'status';
    rejectionTextarea.classList.add('skeleton-input');
    rejectionTextarea.disabled = true;
    try {
      const resp = await fetch('./messages/standard_rejection_message', {
        headers: getAdminHeaders(),
      });
      if (!resp.ok) {
        rejectionTextarea.value = '';
        handleFetchError(rejectionStatus, resp);
        return;
      }
      const data = await resp.json();
      rejectionTextarea.value = data.content || '';
      rejectionStatus.textContent = 'Loaded.';
      rejectionStatus.className = 'status';
    } catch (err) {
      rejectionTextarea.value = '';
      rejectionStatus.textContent = 'Failed to load message.';
      rejectionStatus.className = 'status error';
    } finally {
      rejectionTextarea.classList.remove('skeleton-input');
      rejectionTextarea.disabled = false;
    }
  }

  async function saveRejectionMessage() {
    rejectionStatus.textContent = 'Saving...';
    rejectionStatus.className = 'status';
    saveRejectionBtn.disabled = true;
    try {
      const payload = {
        content: rejectionTextarea.value,
      };
      const resp = await fetch('./messages/standard_rejection_message', {
        method: 'PUT',
        headers: getAdminHeaders(),
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        handleFetchError(rejectionStatus, resp);
        return;
      }
      rejectionStatus.textContent = 'Saved.';
      rejectionStatus.className = 'status success';
    } catch (err) {
      rejectionStatus.textContent = 'Failed to save message.';
      rejectionStatus.className = 'status error';
    } finally {
      saveRejectionBtn.disabled = false;
    }
  }

  saveRejectionBtn.addEventListener('click', function () {
    saveRejectionMessage();
  });

  // --- Training examples (whitelist/blacklist) section ---

  function createTrainingRow(kind, value) {
    const row = document.createElement('div');
    row.className = 'training-row';
    row.style.display = 'block';
    row.style.marginBottom = '6px';

    const top = document.createElement('div');
    top.style.display = 'flex';
    top.style.alignItems = 'center';
    top.style.gap = '6px';

    const input = document.createElement('input');
    input.type = 'text';
    input.value = value || '';
    input.className = 'training-input';
    input.dataset.kind = kind;
    input.readOnly = true;
    input.style.flex = '1';
    input.style.minWidth = '0';

    const actions = document.createElement('div');
    actions.style.display = 'flex';
    actions.style.gap = '4px';

    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'icon-button';
    editBtn.setAttribute('data-action', 'edit');
    editBtn.setAttribute('aria-label', 'Edit query');
    editBtn.innerHTML =
      '<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M4 13.5V16h2.5L15 7.5 12.5 5 4 13.5z"/><path stroke-linecap="round" stroke-linejoin="round" d="M11.5 4.5 13 3l2 2-1.5 1.5"/></svg>';

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'icon-button';
    deleteBtn.setAttribute('data-action', 'delete');
    deleteBtn.setAttribute('aria-label', 'Delete query');
    deleteBtn.innerHTML =
      '<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M6 6h8M8 6v8m4-8v8M5 4h10l-1 12H6L5 4zM8 4h4l-.5-1h-3L8 4z"/></svg>';

    actions.appendChild(editBtn);
    actions.appendChild(deleteBtn);

    top.appendChild(input);
    top.appendChild(actions);
    row.appendChild(top);

    return row;
  }

  function renderTrainingList(container, kind, items) {
    if (!container) return;
    container.innerHTML = '';
    if (!Array.isArray(items) || items.length === 0) {
      // Start with a single empty row so it's obvious you can add entries.
      container.appendChild(createTrainingRow(kind, ''));
      return;
    }
    items.forEach((q) => {
      container.appendChild(createTrainingRow(kind, q));
    });
  }

  function collectTrainingValues(container) {
    if (!container) return [];
    const inputs = Array.from(container.querySelectorAll('input.training-input'));
    return inputs
      .map((input) => (input.value || '').trim())
      .filter(Boolean);
  }

  function attachTrainingListHandlers(container) {
    if (!container) return;
    container.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const button = target.closest('button[data-action]');
      if (!button) return;

      const action = button.getAttribute('data-action');
      const row = button.closest('.training-row');
      if (!row) return;
      const input = row.querySelector('input.training-input');
      if (!input) return;

      if (action === 'edit') {
        const readonly = input.readOnly;
        input.readOnly = !readonly;
        if (!input.readOnly) {
          // Enter edit mode.
          row.classList.add('editing');
          input.focus();
          try {
            const len = input.value.length;
            input.setSelectionRange(len, len);
          } catch (e) {
            // ignore
          }
        } else {
          row.classList.remove('editing');
        }
      } else if (action === 'delete') {
        row.remove();
      }
    });
  }

  attachTrainingListHandlers(blacklistExamplesList);
  attachTrainingListHandlers(whitelistExamplesList);

  function applyTrainingFilter(container, searchInput) {
    if (!container || !searchInput) return;
    const term = (searchInput.value || '').toLowerCase();
    const rows = Array.from(container.querySelectorAll('.training-row'));
    rows.forEach((row) => {
      const input = row.querySelector('input.training-input');
      if (!input) return;
      const value = (input.value || '').toLowerCase();
      if (!term || value.includes(term)) {
        row.style.display = 'block';
      } else {
        row.style.display = 'none';
      }
    });
  }

  async function loadTrainingExamples() {
    if (!trainingExamplesCard) return;
    trainingExamplesStatus.textContent = 'Loading examples...';
    trainingExamplesStatus.className = 'status';

    try {
      const resp = await fetch('./training-examples', {
        headers: getAdminHeaders(),
      });
      if (!resp.ok) {
        handleFetchError(trainingExamplesStatus, resp);
        return;
      }
      const data = await resp.json();
      const blacklist = Array.isArray(data.blacklist_queries) ? data.blacklist_queries : [];
      const whitelist = Array.isArray(data.whitelist_queries) ? data.whitelist_queries : [];
      renderTrainingList(blacklistExamplesList, 'blacklist', blacklist);
      renderTrainingList(whitelistExamplesList, 'whitelist', whitelist);
      applyTrainingFilter(blacklistExamplesList, blacklistExamplesSearch);
      applyTrainingFilter(whitelistExamplesList, whitelistExamplesSearch);
      trainingExamplesStatus.textContent = 'Loaded.';
      trainingExamplesStatus.className = 'status';
    } catch (err) {
      trainingExamplesStatus.textContent = 'Failed to load training examples.';
      trainingExamplesStatus.className = 'status error';
    } finally {
      // no-op; we don't disable individual fields for loading state
    }
  }

  async function saveTrainingExamples() {
    if (!trainingExamplesCard) return;
    trainingExamplesStatus.textContent = 'Saving...';
    trainingExamplesStatus.className = 'status';
    saveTrainingExamplesBtn.disabled = true;

    try {
      const blacklistLines = collectTrainingValues(blacklistExamplesList);
      const whitelistLines = collectTrainingValues(whitelistExamplesList);

      const payload = {
        blacklist_queries: Array.from(new Set(blacklistLines)),
        whitelist_queries: Array.from(new Set(whitelistLines)),
      };

      const resp = await fetch('./training-examples', {
        method: 'PUT',
        headers: getAdminHeaders(),
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        handleFetchError(trainingExamplesStatus, resp);
        return;
      }

      const saved = await resp.json();
      const blacklistSaved = Array.isArray(saved.blacklist_queries) ? saved.blacklist_queries : [];
      const whitelistSaved = Array.isArray(saved.whitelist_queries) ? saved.whitelist_queries : [];
      renderTrainingList(blacklistExamplesList, 'blacklist', blacklistSaved);
      renderTrainingList(whitelistExamplesList, 'whitelist', whitelistSaved);
      applyTrainingFilter(blacklistExamplesList, blacklistExamplesSearch);
      applyTrainingFilter(whitelistExamplesList, whitelistExamplesSearch);

      trainingExamplesStatus.textContent = 'Saved.';
      trainingExamplesStatus.className = 'status success';
    } catch (err) {
      trainingExamplesStatus.textContent = 'Failed to save training examples.';
      trainingExamplesStatus.className = 'status error';
    } finally {
      saveTrainingExamplesBtn.disabled = false;
    }
  }

  if (saveTrainingExamplesBtn) {
    saveTrainingExamplesBtn.addEventListener('click', function () {
      saveTrainingExamples();
    });
  }

  function addTrainingRow(kind) {
    if (!trainingExamplesCard) return;
    const container =
      kind === 'blacklist' ? blacklistExamplesList : kind === 'whitelist' ? whitelistExamplesList : null;
    if (!container) return;
    const row = createTrainingRow(kind, '');
    container.appendChild(row);
    const input = row.querySelector('input.training-input');
    if (input) {
      input.readOnly = false;
      input.focus();
    }
    if (kind === 'blacklist') {
      applyTrainingFilter(blacklistExamplesList, blacklistExamplesSearch);
    } else if (kind === 'whitelist') {
      applyTrainingFilter(whitelistExamplesList, whitelistExamplesSearch);
    }
  }

  if (addBlacklistExampleBtn) {
    addBlacklistExampleBtn.addEventListener('click', function () {
      addTrainingRow('blacklist');
    });
  }

  if (addWhitelistExampleBtn) {
    addWhitelistExampleBtn.addEventListener('click', function () {
      addTrainingRow('whitelist');
    });
  }

  if (blacklistExamplesSearch) {
    blacklistExamplesSearch.addEventListener('input', function () {
      applyTrainingFilter(blacklistExamplesList, blacklistExamplesSearch);
    });
  }

  if (whitelistExamplesSearch) {
    whitelistExamplesSearch.addEventListener('input', function () {
      applyTrainingFilter(whitelistExamplesList, whitelistExamplesSearch);
    });
  }

  // --- Agents section ---
  let selectedAgentOriginalKey = null;

  function instructionsToTextarea(instructions) {
    if (!Array.isArray(instructions) || instructions.length === 0) {
      return '';
    }
    return instructions
      .sort((a, b) => (a.position || 0) - (b.position || 0))
      .map((i) => i.content || '')
      .join('\n');
  }

  function setAgentFormLoading(isLoading) {
    const targets = [
      agentKeyInput,
      agentNameInput,
      agentModelIdInput,
      agentDescriptionInput,
      agentInstructionsInput,
    ];
    targets.forEach((el) => {
      if (!el) return;
      if (isLoading) {
        el.classList.add('skeleton-input');
        el.disabled = true;
      } else {
        el.classList.remove('skeleton-input');
        // Agent key and display name are treated as read-only identifiers in the UI.
        if (el === agentKeyInput || el === agentNameInput) {
          el.disabled = true;
          el.classList.add('readonly-input');
        } else {
          el.disabled = false;
        }
      }
    });
  }

  function populateAgentForm(agent) {
    selectedAgentOriginalKey = agent.agent_key;
    agentKeyInput.value = agent.agent_key || '';
    agentNameInput.value = agent.name || '';
    agentModelIdInput.value = agent.model_id || '';
    agentDescriptionInput.value = agent.description_template || '';
    agentInstructionsInput.value = instructionsToTextarea(agent.instructions);

    // Show training examples only when viewing validator agents, where they are conceptually relevant.
    if (!trainingExamplesCard) return;
    const key = agent.agent_key || '';
    if (key === 'validation_blacklist' || key === 'validation_primary') {
      trainingExamplesCard.style.display = '';
    } else {
      trainingExamplesCard.style.display = 'none';
    }
  }

  function updateAgentsRelationships(agents) {
    if (!agentsRelationshipsEl) return;
    const runtime = agents.find((a) => a.agent_key === 'runtime_rag');
    const blacklist = agents.find((a) => a.agent_key === 'validation_blacklist');
    const primary = agents.find((a) => a.agent_key === 'validation_primary');

    if (!runtime) {
      agentsRelationshipsEl.textContent = '';
      return;
    }

    function modelLabel(agent) {
      return agent && agent.model_id ? agent.model_id : 'unknown';
    }

    let html =
      'Runtime agent <code>' + runtime.agent_key + '</code> (model ' + modelLabel(runtime) + ')';

    const hookParts = [];
    if (blacklist) {
      hookParts.push(
        '<code>' + blacklist.agent_key + '</code> (model ' + modelLabel(blacklist) + ')',
      );
    }
    if (primary) {
      hookParts.push(
        '<code>' + primary.agent_key + '</code> (model ' + modelLabel(primary) + ')',
      );
    }

    if (hookParts.length > 0) {
      html += ' runs with pre-hooks: ' + hookParts.join(', ');
    } else {
      html += ' has no configured pre-hook validator agents.';
    }

    agentsRelationshipsEl.innerHTML = html;
  }

  function renderAgentsSkeletonTable() {
    const rows = Array.from({ length: 3 })
      .map(
        () => `
        <tr>
          <td><div class="skeleton-line" style="width:70%;"></div></td>
          <td><div class="skeleton-line" style="width:80%;"></div></td>
          <td><div class="skeleton-line" style="width:40%;"></div></td>
          <td><div class="skeleton-line" style="width:25%;"></div></td>
        </tr>
      `,
      )
      .join('');

    return `
      <table>
        <thead>
          <tr><th>Agent key</th><th>Name</th><th>Model</th><th># Instructions</th></tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    `;
  }

  async function loadAgents(preserveStatus) {
    if (!preserveStatus) {
      agentStatus.textContent = 'Loading agents...';
      agentStatus.className = 'status';
      agentsTableContainer.innerHTML = renderAgentsSkeletonTable();
      setAgentFormLoading(true);
    }
    try {
      const resp = await fetch('./agents', {
        headers: getAdminHeaders(),
      });
      if (!resp.ok) {
        agentsTableContainer.innerHTML = '<div class="status error">Failed to load agents.</div>';
        handleFetchError(agentStatus, resp);
        return;
      }
      const agents = await resp.json();
      if (!Array.isArray(agents) || agents.length === 0) {
        agentsTableContainer.innerHTML =
          '<div class="inline-muted">No agents defined yet. Add runtime_rag and validation agents using the form below.</div>';
        if (agentsRelationshipsEl) {
          agentsRelationshipsEl.textContent = '';
        }
        if (!preserveStatus) {
          agentStatus.textContent = '';
          agentStatus.className = 'status';
          setAgentFormLoading(false);
        }
        return;
      }
      updateAgentsRelationships(agents);
      const rowsHtml = agents
        .map((a) => {
          const count = Array.isArray(a.instructions) ? a.instructions.length : 0;
          return (
            '<tr data-agent-key="' +
            a.agent_key +
            '">' +
            '<td>' +
            a.agent_key +
            '</td>' +
            '<td>' +
            (a.name || '') +
            '</td>' +
            '<td>' +
            (a.model_id || '') +
            '</td>' +
            '<td>' +
            count +
            '</td>' +
            '</tr>'
          );
        })
        .join('');
      const tableHtml =
        '<table>' +
        '<thead><tr><th>Agent key</th><th>Name</th><th>Model</th><th># Instructions</th></tr></thead>' +
        '<tbody>' +
        rowsHtml +
        '</tbody>' +
        '</table>';
      agentsTableContainer.innerHTML = tableHtml;
      const rows = agentsTableContainer.querySelectorAll('tbody tr');
      rows.forEach((row, idx) => {
        row.addEventListener('click', () => {
          rows.forEach((r) => r.classList.remove('selected'));
          row.classList.add('selected');
          const a = agents[idx];
          populateAgentForm(a);
        });
      });
      // Ensure one agent is always selected.
      let indexToSelect = 0;
      if (selectedAgentOriginalKey) {
        const foundIndex = agents.findIndex((a) => a.agent_key === selectedAgentOriginalKey);
        if (foundIndex >= 0) {
          indexToSelect = foundIndex;
        }
      }
      const rowToSelect = rows[indexToSelect];
      if (rowToSelect) {
        rows.forEach((r) => r.classList.remove('selected'));
        rowToSelect.classList.add('selected');
        populateAgentForm(agents[indexToSelect]);
      }
      if (!preserveStatus) {
        agentStatus.textContent = '';
        agentStatus.className = 'status';
        setAgentFormLoading(false);
      }
    } catch (err) {
      agentsTableContainer.innerHTML = '<div class="status error">Failed to load agents.</div>';
      if (!preserveStatus) {
        agentStatus.textContent = 'Failed to load agents.';
        agentStatus.className = 'status error';
        setAgentFormLoading(false);
      }
    }
  }

  async function saveAgent() {
    if (!selectedAgentOriginalKey) {
      agentStatus.textContent = 'Select an agent from the table to edit.';
      agentStatus.className = 'status error';
      return;
    }
    const key = agentKeyInput.value.trim();
    const name = agentNameInput.value.trim();
    const modelId = agentModelIdInput.value.trim();

    if (!key) {
      agentStatus.textContent = 'Agent key is required.';
      agentStatus.className = 'status error';
      return;
    }
    if (!modelId) {
      agentStatus.textContent = 'Model ID is required.';
      agentStatus.className = 'status error';
      return;
    }

    const lines = agentInstructionsInput.value
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    const instructions = lines.map((content, idx) => ({
      id: null,
      position: idx + 1,
      content: content,
    }));

    const payload = {
      id: null,
      agent_key: key,
      name: name || key,
      description_template: agentDescriptionInput.value || null,
      model_id: modelId,
      is_active: true,
      instructions: instructions,
    };

    agentStatus.textContent = 'Saving...';
    agentStatus.className = 'status';
    saveAgentBtn.disabled = true;

    try {
      const url = './agents/' + encodeURIComponent(selectedAgentOriginalKey);
      const method = 'PUT';
      const resp = await fetch(url, {
        method: method,
        headers: getAdminHeaders(),
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        handleFetchError(agentStatus, resp);
        return;
      }
      const saved = await resp.json();
      populateAgentForm(saved);
      agentStatus.textContent = 'Saved.';
      agentStatus.className = 'status success';
      await loadAgents(true);
    } catch (err) {
      agentStatus.textContent = 'Failed to save agent.';
      agentStatus.className = 'status error';
    } finally {
      saveAgentBtn.disabled = false;
    }
  }

  saveAgentBtn.addEventListener('click', function () {
    saveAgent();
  });

  // --- Initial load ---
  (function bootstrap() {
    setGlobalStatus('Loading configuration from /admin API...', '');
    Promise.all([loadRejectionMessage(), loadAgents(false), loadTrainingExamples()])
      .then(function () {
        setGlobalStatus('Configuration loaded.', 'success');
      })
      .catch(function () {
        setGlobalStatus('Failed to load configuration. Check DB.', 'error');
      });
  })();
})();


