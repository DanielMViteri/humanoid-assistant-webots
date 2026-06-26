import type { CSSProperties } from "react";
import type { AdminKpiDashboardData, AdminKpiDashboardProps } from "./admin_kpi_types";

function statusClass(status: string) {
  if (["Available", "Connected", "Active"].includes(status)) return "status-available";
  if (["Partial", "Waiting"].includes(status)) return "status-partial";
  if (["Failed", "Failure"].includes(status)) return "status-failed";
  return "status-unavailable";
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("en-US");
}

function formatMs(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${formatNumber(value)} ms`;
}

function KpiCard({ kpi, index }: { kpi: AdminKpiDashboardData["top_kpis"][number]; index: number }) {
  const labels = ["PS", "E2E", "DB", "DS", "SR", "RA", "AC", "FE"];
  const valueClass = kpi.status === "Available"
    ? "available"
    : kpi.status === "Unavailable"
      ? "unavailable"
      : kpi.id === "failed_events"
        ? "failed"
        : "";

  return (
    <button className="kpi-card" type="button" data-kpi-target={kpi.target || "overview"}>
      <div className="kpi-card-top">
        <span className="icon-token">{labels[index] || "KP"}</span>
        <p className="kpi-card-title">{index + 1}. {kpi.label}</p>
      </div>
      <p className={`kpi-value ${valueClass}`}>{kpi.value}</p>
      <p className="kpi-detail">{kpi.detail}</p>
      <span className={`status-chip ${statusClass(kpi.status)}`}>{kpi.status}</span>
    </button>
  );
}

function SourceBars({ data }: { data: AdminKpiDashboardData }) {
  const collections = data.mongo_sync.collections;
  const maxDocs = Math.max(...collections.map((item) => item.documents), 1);

  return (
    <div className="source-bars">
      {collections.map((item) => {
        const width = Math.max(1, (item.documents / maxDocs) * 100).toFixed(2);
        return (
          <div className="bar-row" key={item.collection}>
            <span>{item.collection}</span>
            <div className="bar-track">
              <span className="bar-fill" style={{ "--bar-width": `${width}%`, "--bar-color": "var(--nesto-green)" } as CSSProperties} />
            </div>
            <strong>{formatNumber(item.documents)}</strong>
          </div>
        );
      })}
    </div>
  );
}

export function AdminKpiDashboard({
  data,
  loading = false,
  error = null,
  onRefresh,
  selectedRange = "snapshot",
  onRangeChange
}: AdminKpiDashboardProps) {
  // TODO: replace snapshot prop with GET /api/admin/kpis once Daniel's FastAPI branch is available.
  // TODO: enable polling once the final frontend fetch strategy is confirmed.

  if (loading) {
    return <main className="operations-main"><div className="panel">Loading Admin KPI Dashboard...</div></main>;
  }

  if (error) {
    return <main className="operations-main"><div className="panel missing-field">{error}</div></main>;
  }

  const services = data.services || [];
  const blockedKpis = Array.from(new Set(data.missing_telemetry_fields.flatMap((field) => field.blocked_kpis)));

  return (
    <div className="operations-shell">
      <aside className="operations-sidebar">
        <div className="brand-lockup">
          <div className="brand-wordmark">NESTO<span>♡</span></div>
          <p>Care Operations</p>
        </div>
        <div className="sidebar-mascot" aria-label="NESTO robot mascot">
          <div className="mascot-head"><div className="mascot-screen"><span /><span /></div></div>
          <div className="mascot-arm mascot-arm-left" />
          <div className="mascot-arm mascot-arm-right" />
          <div className="mascot-body"><span /></div>
          <div className="mascot-base" />
        </div>
        <div className="sidebar-copy">
          <strong>Caring with Intelligence.</strong>
          <span>Supporting Lives.</span>
        </div>
        <nav className="side-nav" aria-label="Admin dashboard sections">
          {["Overview", "Robot Fleet", "Patients", "Guardian / Caregivers", "Alerts", "Telemetry & Logs"].map((item) => (
            <a className="nav-link" href="#overview" key={item}><span className="nav-icon">{item.slice(0, 2).toUpperCase()}</span><span>{item}</span></a>
          ))}
          <a className="nav-link active" href="#overview">
            <span className="nav-icon">KP</span>
            <span>KPI Dashboard</span>
            <span className="new-badge">NEW</span>
          </a>
          {["Reports", "System Health", "Settings"].map((item) => (
            <a className="nav-link" href="#system-info" key={item}><span className="nav-icon">{item.slice(0, 2).toUpperCase()}</span><span>{item}</span></a>
          ))}
        </nav>
        <div className="admin-profile">
          <div className="profile-photo">AI</div>
          <div>
            <strong>Dr. Ananya Iyer</strong>
            <span>System Administrator</span>
          </div>
        </div>
      </aside>

      <main className="operations-main">
        <header className="operations-header" id="overview">
          <div className="header-title">
            <span className="section-kicker">Admin KPI Dashboard</span>
            <h1>NESTO Care Operations</h1>
            <p>Real-time admin KPI dashboard for NESTO robotic care ecosystem</p>
          </div>
          <div className="header-actions">
            <div className="status-chip-grid">
              {services.map((service) => (
                <div className={`service-chip ${service.status === "Connected" ? "connected" : ""}`} key={service.name}>
                  <span className="service-dot">{service.status === "Connected" ? "✓" : "○"}</span>
                  <div>
                    <strong>{service.name}</strong>
                    <span>{service.status}</span>
                  </div>
                </div>
              ))}
            </div>
            <button className="icon-button" type="button" onClick={onRefresh} aria-label="Refresh KPI snapshot">↻</button>
          </div>
        </header>

        <section className="control-panel" aria-label="Dashboard controls">
          <label className="control-item">
            <span>Time range</span>
            <select value={selectedRange} onChange={(event) => onRangeChange?.(event.target.value)}>
              <option value="10m">Last 10 minutes</option>
              <option value="24h">Last 24 hours</option>
              <option value="snapshot">Snapshot</option>
            </select>
          </label>
          <label className="toggle-row">
            <input type="checkbox" readOnly />
            <span>Auto refresh UI</span>
          </label>
          <div className="refresh-note">Snapshot view loaded from read-only analysis.</div>
        </section>

        <section className="top-kpi-grid" aria-label="Required top KPI cards">
          {data.top_kpis.map((kpi, index) => <KpiCard kpi={kpi} index={index} key={kpi.id} />)}
        </section>

        <section className="dashboard-grid">
          <article className="panel panel-wide" id="pipeline">
            <div className="panel-heading"><span className="panel-index">1</span><div><h2>Pipeline Health Overview</h2><p>Command pipeline measured from real timestamp coverage.</p></div></div>
            <div className="pipeline-map">
              {["UI Trigger", "Backend API", "Bridge / Kafka", "Robot Action", "MongoDB Update", "Dashboard Update"].map((stage, index) => (
                <div className={`pipeline-node ${index > 3 ? "unavailable" : index === 3 ? "available" : "partial"}`} key={stage}>
                  <span>{stage.slice(0, 2).toUpperCase()}</span>
                  <strong>{stage}</strong>
                  <em>{index > 3 ? "Missing timestamps" : index === 3 ? "Started only" : "Partial"}</em>
                </div>
              ))}
            </div>
            <div className="notice notice-warning">Pipeline is partially measurable. Completion and dashboard timestamps are not parseable in the snapshot.</div>
          </article>

          <article className="panel panel-wide" id="latency">
            <div className="panel-heading"><span className="panel-index">2</span><div><h2>Latency KPIs</h2><p>Milliseconds only where timestamp pairs exist and parse cleanly.</p></div></div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Stage</th><th>Status</th><th>Samples</th><th>Median</th><th>Average</th><th>P95</th><th>Negative</th><th>Reason</th></tr>
                </thead>
                <tbody>
                  {data.latency.segments.map((segment) => (
                    <tr key={segment.stage}>
                      <td>{segment.stage}</td>
                      <td><span className={`status-chip ${statusClass(segment.status)}`}>{segment.status}</span></td>
                      <td>{formatNumber(segment.samples)}</td>
                      <td>{formatMs(segment.median_ms)}</td>
                      <td>{formatMs(segment.average_ms)}</td>
                      <td>{formatMs(segment.p95_ms)}</td>
                      <td>{formatNumber(segment.negative)}</td>
                      <td>{segment.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="panel" id="events">
            <div className="panel-heading"><span className="panel-index">3</span><div><h2>Event Throughput and Success Rate</h2><p>Terminal status coverage from the read-only sample.</p></div></div>
            <div className="throughput-row">
              <div><strong>{formatNumber(data.event_success_rate.total)}</strong><span>Total Events / sampled statuses</span></div>
              <div><strong>{formatNumber(data.event_success_rate.success)}</strong><span>Success</span></div>
              <div><strong>{formatNumber(data.event_success_rate.failure)}</strong><span>Failure</span></div>
              <div><strong>{formatNumber(data.event_success_rate.unknown)}</strong><span>Unknown / in progress</span></div>
            </div>
            <div className="notice notice-info compact">Time-series throughput will load from GET /api/admin/kpis once integrated.</div>
          </article>

          <article className="panel" id="source-modules">
            <div className="panel-heading"><span className="panel-index">4</span><div><h2>Events by Source Module</h2><p>Collection volumes from humanoid_assistant.</p></div></div>
            <SourceBars data={data} />
          </article>

          <article className="panel" id="robot-actions">
            <div className="panel-heading"><span className="panel-index">5</span><div><h2>Robot Action Status</h2><p>Latest available command details remain partial.</p></div></div>
            <div className="robot-status-card">
              <div className="robot-mini"><span /></div>
              <div>
                <span>Last Robot Action</span>
                <strong>{data.last_robot_action.action || "Unavailable"}{data.last_robot_action.object ? ` / ${data.last_robot_action.object}` : ""}</strong>
                <p>{data.last_robot_action.note}</p>
              </div>
            </div>
          </article>

          <article className="panel panel-wide" id="mongo-sync">
            <div className="panel-heading"><span className="panel-index">6</span><div><h2>MongoDB Sync Monitor</h2><p>Collection coverage and Daniel filter matches.</p></div></div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Collection</th><th>Documents</th><th>Daniel Filter Matches</th><th>All Required Timestamp Fields Present</th><th>Status</th><th>Last Update</th><th>Notes</th></tr>
                </thead>
                <tbody>
                  {data.mongo_sync.collections.map((item) => (
                    <tr key={item.collection}>
                      <td>{item.collection}</td>
                      <td>{formatNumber(item.documents)}</td>
                      <td>{formatNumber(item.daniel_filter_matches)}</td>
                      <td>{formatNumber(item.all_required_timestamp_fields_present)}</td>
                      <td><span className={`status-chip ${statusClass(item.status)}`}>{item.status}</span></td>
                      <td>{item.last_update || "—"}</td>
                      <td>{item.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="panel panel-wide" id="event-logs">
            <div className="panel-heading"><span className="panel-index">7</span><div><h2>Recent Event Logs</h2><p>Redacted rows only; private payload text is not shown.</p></div></div>
            <div className="empty-state">Recent event rows will load from GET /api/admin/kpis once integrated.</div>
          </article>

          <article className="panel" id="missing-telemetry">
            <div className="panel-heading"><span className="panel-index">8</span><div><h2>Missing Telemetry Fields</h2><p>Current blockers for complete KPI calculation.</p></div></div>
            <div className="missing-details">
              <div>
                {data.missing_telemetry_fields.map((field) => (
                  <div className="missing-field" key={field.field}>
                    <strong>{field.field}</strong>
                    <span>{field.state}</span>
                  </div>
                ))}
              </div>
              <h3>Blocked KPI calculations</h3>
              <ul>{blockedKpis.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          </article>

          <article className="panel" id="system-info">
            <div className="panel-heading"><span className="panel-index">9</span><div><h2>System Quick Info</h2><p>Snapshot scope and integration readiness.</p></div></div>
            <div className="quick-info-list">
              <div><span>MongoDB</span><strong>Connected / Readable</strong></div>
              <div><span>Kafka</span><strong>Waiting / Not validated</strong></div>
              <div><span>Redis</span><strong>Waiting / Not validated</strong></div>
              <div><span>ChromaDB</span><strong>Waiting / Not validated</strong></div>
              <div><span>NLP Guardrails</span><strong>{data.nlp_guardrails.note}</strong></div>
              <div><span>Last Snapshot</span><strong>{data.generated_at}</strong></div>
              <div><span>Writes performed</span><strong>{String(data.safety.writes_performed)}</strong></div>
            </div>
          </article>
        </section>

        <footer className="dashboard-footer">
          <span>All data shown is from read-only MongoDB analysis snapshots.</span>
          <strong>No writes performed.</strong>
        </footer>
      </main>
    </div>
  );
}
