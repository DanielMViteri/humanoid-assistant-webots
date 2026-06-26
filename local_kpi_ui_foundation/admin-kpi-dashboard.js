(function () {
  "use strict";

  const embeddedSnapshot = window.ADMIN_KPI_SNAPSHOT || null;
  const state = {
    snapshot: embeddedSnapshot,
    collectionFilter: "All",
    sortKey: "collection",
    sortDirection: "asc",
    logSearch: "",
    autoRefreshTimer: null,
    selectedRange: "snapshot",
    missingOpen: true
  };

  const q = (selector) => document.querySelector(selector);
  const qa = (selector) => Array.from(document.querySelectorAll(selector));

  const sectionTargets = {
    pipeline_status: "pipeline",
    end_to_end_latency: "latency",
    mongodb_write_latency: "latency",
    dashboard_refresh_latency: "latency",
    event_success_rate: "events",
    last_robot_action: "robot-actions",
    active_collections: "mongo-sync",
    failed_events: "events"
  };

  const formatNumber = (value) => {
    if (value === null || value === undefined || value === "—") return "—";
    const numeric = Number(value);
    if (Number.isNaN(numeric)) return String(value);
    return numeric.toLocaleString("en-US");
  };

  const formatMs = (value) => {
    if (value === null || value === undefined) return "—";
    return `${formatNumber(value)} ms`;
  };

  const statusClass = (status) => {
    if (["Available", "Connected", "Active"].includes(status)) return "status-available";
    if (["Partial", "Waiting"].includes(status)) return "status-partial";
    if (["Failed", "Failure"].includes(status)) return "status-failed";
    return "status-unavailable";
  };

  const setText = (selector, value) => {
    const node = q(selector);
    if (node) node.textContent = value;
  };

  const setActiveNavLink = (activeLink) => {
    qa(".nav-link").forEach((link) => {
      link.classList.toggle("active", link === activeLink);
    });
  };

  const scrollToSection = (id, activeLink) => {
    const target = document.getElementById(id);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    if (activeLink) setActiveNavLink(activeLink);
  };

  function updateClock() {
    const now = new Date();
    setText("[data-current-date]", now.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric"
    }));
    setText("[data-current-time]", now.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit"
    }));
  }

  function updateRenderStamp(message) {
    const stamp = q("[data-render-stamp]");
    if (stamp) {
      stamp.textContent = message || `Rendered ${new Date().toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit"
      })}`;
    }
  }

  function setWarning(visible) {
    const warning = q("[data-load-warning]");
    if (warning) warning.hidden = !visible;
  }

  function renderServices(data) {
    const target = q("[data-service-chips]");
    if (!target) return;

    target.innerHTML = (data.services || []).map((service) => {
      const connected = service.status === "Connected" ? " connected" : "";
      const mark = service.status === "Connected" ? "✓" : "○";
      return `
        <div class="service-chip${connected}" title="${service.detail || service.status}">
          <span class="service-dot">${mark}</span>
          <div>
            <strong>${service.name}</strong>
            <span>${service.status}</span>
          </div>
        </div>
      `;
    }).join("");
  }

  function renderTopKpis(data) {
    const icons = ["PS", "E2E", "DB", "DS", "SR", "RA", "AC", "FE"];
    const target = q("[data-kpi-cards]");
    if (!target) return;

    target.innerHTML = (data.top_kpis || []).map((kpi, index) => {
      const targetId = kpi.target || sectionTargets[kpi.id] || "overview";
      const valueClass = kpi.status === "Available"
        ? "available"
        : kpi.status === "Unavailable"
          ? "unavailable"
          : kpi.id === "failed_events"
            ? "failed"
            : "";

      return `
        <button class="kpi-card" type="button" data-kpi-target="${targetId}" aria-label="Open ${kpi.label}">
          <div class="kpi-card-top">
            <span class="icon-token">${icons[index] || "KP"}</span>
            <p class="kpi-card-title">${index + 1}. ${kpi.label}</p>
          </div>
          <p class="kpi-value ${valueClass}">${kpi.value}</p>
          <p class="kpi-detail">${kpi.detail}</p>
          <span class="status-chip ${statusClass(kpi.status)}">${kpi.status}</span>
        </button>
      `;
    }).join("");

    qa("[data-kpi-target]").forEach((button) => {
      button.addEventListener("click", () => scrollToSection(button.dataset.kpiTarget));
    });
  }

  function renderLatency(data) {
    const target = q("[data-latency-body]");
    if (!target) return;

    target.innerHTML = (data.latency?.segments || []).map((item) => `
      <tr>
        <td>${item.stage}</td>
        <td><span class="status-chip ${statusClass(item.status)}">${item.status}</span></td>
        <td>${item.samples === null ? "—" : formatNumber(item.samples)}</td>
        <td>${formatMs(item.median_ms)}</td>
        <td>${formatMs(item.average_ms)}</td>
        <td>${formatMs(item.p95_ms)}</td>
        <td>${formatNumber(item.negative)}</td>
        <td>${item.note}</td>
      </tr>
    `).join("");
  }

  function renderStatusBars(data) {
    const target = q("[data-status-bars]");
    if (!target) return;
    const event = data.event_success_rate || {};
    const total = event.total || 1;
    const rows = [
      { label: "Success", value: event.success || 0, color: "var(--nesto-green)" },
      { label: "Failure", value: event.failure || 0, color: "var(--nesto-red)" },
      { label: "Unknown / in progress", value: event.unknown || 0, color: "#9ba4a1" }
    ];

    target.innerHTML = rows.map((row) => {
      const width = Math.max(1, (row.value / total) * 100).toFixed(2);
      return `
        <div class="bar-row">
          <span>${row.label}</span>
          <div class="bar-track"><span class="bar-fill" style="--bar-width: ${width}%; --bar-color: ${row.color};"></span></div>
          <strong>${formatNumber(row.value)}</strong>
        </div>
      `;
    }).join("");
  }

  function renderEventRate(data) {
    const event = data.event_success_rate || {};
    setText("[data-event-total]", formatNumber(event.total));
    setText("[data-event-success]", formatNumber(event.success));
    setText("[data-event-failure]", formatNumber(event.failure));
    setText("[data-event-unknown]", formatNumber(event.unknown));
    renderStatusBars(data);
  }

  function renderSourceModules(data) {
    const target = q("[data-source-bars]");
    if (!target) return;
    const collections = data.mongo_sync?.collections || [];
    const maxDocs = Math.max(...collections.map((item) => item.documents || 0), 1);

    target.innerHTML = collections.map((item) => {
      const width = Math.max(1, ((item.documents || 0) / maxDocs) * 100).toFixed(2);
      return `
        <div class="bar-row">
          <span>${item.collection}</span>
          <div class="bar-track"><span class="bar-fill" style="--bar-width: ${width}%; --bar-color: var(--nesto-green);"></span></div>
          <strong>${formatNumber(item.documents)}</strong>
        </div>
      `;
    }).join("");
  }

  function renderRobotAction(data) {
    const action = data.last_robot_action || {};
    setText("[data-last-action]", `${action.action || "Unavailable"}${action.object ? ` / ${action.object}` : ""}`);
    setText("[data-action-note]", action.note || "Partial data in snapshot.");
    setText("[data-status-failed]", formatNumber(data.failed_events?.terminal_failures_detected ?? data.event_success_rate?.failure));
  }

  function getFilteredCollections(data) {
    const collections = [...(data.mongo_sync?.collections || [])];
    const filtered = state.collectionFilter === "All"
      ? collections
      : collections.filter((item) => item.status === state.collectionFilter);

    filtered.sort((left, right) => {
      const a = left[state.sortKey];
      const b = right[state.sortKey];
      const numeric = typeof a === "number" && typeof b === "number";
      const result = numeric
        ? a - b
        : String(a || "").localeCompare(String(b || ""));
      return state.sortDirection === "asc" ? result : -result;
    });

    return filtered;
  }

  function renderMongoSync(data) {
    const target = q("[data-sync-body]");
    if (!target) return;

    const rows = getFilteredCollections(data);
    setText("[data-collection-count]", `${rows.length} collections`);

    target.innerHTML = rows.map((item) => `
      <tr>
        <td>${item.collection}</td>
        <td>${formatNumber(item.documents)}</td>
        <td>${formatNumber(item.daniel_filter_matches)}</td>
        <td>${formatNumber(item.all_required_timestamp_fields_present)}</td>
        <td><span class="status-chip ${statusClass(item.status)}">${item.status}</span></td>
        <td>${item.last_update || "—"}</td>
        <td>${item.notes}</td>
      </tr>
    `).join("");

    const summary = data.mongo_sync?.summary || {};
    setText("[data-total-documents]", formatNumber(summary.total_documents));
    setText("[data-filter-matches]", formatNumber(summary.daniel_filter_matches));
    setText("[data-collections-with-data]", `${summary.collections_with_data} / ${summary.collections_inspected}`);
    setText("[data-main-blockers]", (summary.main_latency_blockers || []).join(", "));
  }

  function renderRecentEvents(data) {
    const target = q("[data-recent-events]");
    if (!target) return;
    const events = data.recent_events || [];
    const search = state.logSearch.trim().toLowerCase();
    const filtered = search
      ? events.filter((item) => JSON.stringify(item).toLowerCase().includes(search))
      : events;

    setText("[data-log-count]", filtered.length ? `${filtered.length} redacted rows` : "Waiting for route integration");

    if (filtered.length === 0) {
      target.innerHTML = `
        <tr>
          <td colspan="8">
            <div class="empty-state">Recent event rows will load from GET /api/admin/kpis once integrated.</div>
          </td>
        </tr>
      `;
      return;
    }

    target.innerHTML = filtered.map((event) => `
      <tr>
        <td>${event.time || "—"}</td>
        <td>${event.event_id || "Redacted"}</td>
        <td>${event.trigger || "—"}</td>
        <td>${event.scenario || "—"}</td>
        <td>${event.robot_action || "—"}</td>
        <td>${event.status || "Unknown"}</td>
        <td>${event.end_to_end_latency || "—"}</td>
        <td>${event.mongodb || "Logged"}</td>
      </tr>
    `).join("");
  }

  function renderMissingTelemetry(data) {
    const fields = data.missing_telemetry_fields || [];
    const fieldTarget = q("[data-missing-fields]");
    if (fieldTarget) {
      fieldTarget.innerHTML = fields.map((item) => `
        <div class="missing-field">
          <strong>${item.field}</strong>
          <span>${item.state}</span>
        </div>
      `).join("");
    }

    const blocked = Array.from(new Set(fields.flatMap((item) => item.blocked_kpis || [])));
    const blockedTarget = q("[data-blocked-kpis]");
    if (blockedTarget) {
      blockedTarget.innerHTML = blocked.map((item) => `<li>${item}</li>`).join("");
    }
  }

  function renderSystemInfo(data) {
    const target = q("[data-system-info]");
    if (!target) return;
    const services = Object.fromEntries((data.services || []).map((service) => [service.name, service]));
    const rows = [
      ["MongoDB", `${services.MongoDB?.status || "Waiting"} / ${services.MongoDB?.detail || "Not validated"}`],
      ["Kafka", `${services.Kafka?.status || "Waiting"} / ${services.Kafka?.detail || "Not validated"}`],
      ["Redis", `${services.Redis?.status || "Waiting"} / ${services.Redis?.detail || "Not validated"}`],
      ["ChromaDB", `${services.ChromaDB?.status || "Waiting"} / ${services.ChromaDB?.detail || "Not validated"}`],
      ["NLP Guardrails", data.nlp_guardrails?.note || "Documented task-focused instructions, not telemetry-validated."],
      ["Last Snapshot", data.generated_at || "Not recorded"],
      ["Writes performed", String(data.safety?.writes_performed === true)]
    ];

    target.innerHTML = rows.map(([label, value]) => `
      <div>
        <span>${label}</span>
        <strong>${value}</strong>
      </div>
    `).join("");
  }

  function renderSnapshot(data, sourceLabel) {
    if (!data) return;
    state.snapshot = data;
    setText("[data-db-name]", data.database || "humanoid_assistant");
    renderServices(data);
    renderTopKpis(data);
    renderLatency(data);
    renderEventRate(data);
    renderSourceModules(data);
    renderRobotAction(data);
    renderMongoSync(data);
    renderRecentEvents(data);
    renderMissingTelemetry(data);
    renderSystemInfo(data);
    updateRenderStamp(sourceLabel || "Rendered from embedded snapshot.");
  }

  async function loadSnapshot(allowWarning) {
    if (embeddedSnapshot) {
      renderSnapshot(embeddedSnapshot, "Rendered from embedded snapshot.");
    }

    if (window.location.protocol === "file:") {
      setWarning(false);
      return embeddedSnapshot;
    }

    try {
      const response = await fetch("./real_analysis_snapshot.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`Snapshot request returned ${response.status}`);
      const json = await response.json();
      setWarning(false);
      renderSnapshot(json, "Rendered from local server snapshot file.");
      return json;
    } catch (error) {
      if (allowWarning) setWarning(true);
      return embeddedSnapshot;
    }
  }

  function bindNavigation() {
    qa("[data-section-link]").forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        scrollToSection(link.dataset.sectionLink, link);
      });
    });
  }

  function bindControls() {
    const refresh = q("[data-refresh-button]");
    if (refresh) {
      refresh.addEventListener("click", async () => {
        await loadSnapshot(true);
        const note = q("[data-refresh-note]");
        if (note) note.textContent = "Snapshot refreshed from available local source.";
      });
    }

    const range = q("[data-range-select]");
    if (range) {
      range.addEventListener("change", () => {
        state.selectedRange = range.value;
        const note = q("[data-refresh-note]");
        if (note) note.textContent = `Range control set to ${range.options[range.selectedIndex].text}. Data remains snapshot-scoped until API integration.`;
      });
    }

    const auto = q("[data-auto-refresh]");
    if (auto) {
      auto.addEventListener("change", () => {
        if (state.autoRefreshTimer) {
          clearInterval(state.autoRefreshTimer);
          state.autoRefreshTimer = null;
        }
        if (auto.checked) {
          state.autoRefreshTimer = window.setInterval(() => {
            loadSnapshot(false);
          }, 30000);
          const note = q("[data-refresh-note]");
          if (note) note.textContent = "Auto refresh UI is on. It reloads local snapshot only.";
        } else {
          const note = q("[data-refresh-note]");
          if (note) note.textContent = "Auto refresh UI is off.";
        }
      });
    }

    const filter = q("[data-collection-filter]");
    if (filter) {
      filter.addEventListener("change", () => {
        state.collectionFilter = filter.value;
        renderMongoSync(state.snapshot);
      });
    }

    qa("[data-sort-key]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.sortKey;
        if (state.sortKey === key) {
          state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
        } else {
          state.sortKey = key;
          state.sortDirection = "asc";
        }
        renderMongoSync(state.snapshot);
      });
    });

    const search = q("[data-log-search]");
    if (search) {
      search.addEventListener("input", () => {
        state.logSearch = search.value;
        renderRecentEvents(state.snapshot);
      });
    }

    const expand = q("[data-expand-missing]");
    const details = q("[data-missing-details]");
    if (expand && details) {
      expand.addEventListener("click", () => {
        state.missingOpen = !state.missingOpen;
        details.hidden = !state.missingOpen;
        expand.setAttribute("aria-expanded", String(state.missingOpen));
        expand.textContent = state.missingOpen ? "Hide missing telemetry details" : "Show missing telemetry details";
      });
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    updateClock();
    window.setInterval(updateClock, 30000);
    bindNavigation();
    bindControls();
    await loadSnapshot(false);
  });
})();
