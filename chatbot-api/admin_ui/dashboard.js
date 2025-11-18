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

  function populateAgentForm(agent) {
    selectedAgentOriginalKey = agent.agent_key;
    agentKeyInput.value = agent.agent_key || '';
    agentNameInput.value = agent.name || '';
    agentModelIdInput.value = agent.model_id || '';
    agentDescriptionInput.value = agent.description_template || '';
    agentInstructionsInput.value = instructionsToTextarea(agent.instructions);
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

  async function loadAgents() {
    agentStatus.textContent = 'Loading agents...';
    agentStatus.className = 'status';
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
        agentStatus.textContent = '';
        agentStatus.className = 'status';
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
      agentStatus.textContent = '';
      agentStatus.className = 'status';
    } catch (err) {
      agentsTableContainer.innerHTML = '<div class="status error">Failed to load agents.</div>';
      agentStatus.textContent = 'Failed to load agents.';
      agentStatus.className = 'status error';
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
      await loadAgents();
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
    Promise.all([loadRejectionMessage(), loadAgents()])
      .then(function () {
        setGlobalStatus('Configuration loaded.', 'success');
      })
      .catch(function () {
        setGlobalStatus('Failed to load configuration. Check DB.', 'error');
      });
  })();
})();


