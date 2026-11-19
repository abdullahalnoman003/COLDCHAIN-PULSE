import React, { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, Archive, BarChart3, Bell, Box, Check, ChevronRight,
  Download, LayoutDashboard, LogOut, Menu, Plus, Search, Settings, ShieldCheck,
  Thermometer, Truck, UserRound, Users, X,
} from "lucide-react";
import { api, clearSession, downloadReport, getToken, login } from "./api";

const roleLabels = {
  admin: "Administrator",
  dispatcher: "Dispatcher",
  driver: "Driver",
  clinic_receiver: "Clinic Receiver",
  auditor: "Auditor",
};

function Login({ onLogin }) {
  const [email, setEmail] = useState("admin@medswift.io");
  const [password, setPassword] = useState("Passw0rd!demo");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await login(email, password);
      localStorage.setItem("ccp_token", result.access_token);
      const user = await api("/auth/me");
      localStorage.setItem("ccp_user", JSON.stringify(user));
      onLogin(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-brand">
        <div className="brand-mark"><Activity size={28} /></div>
        <div><strong>ColdChain</strong><span> PULSE</span></div>
        <p>Real-time cold-chain visibility and compliance</p>
      </section>
      <section className="login-card">
        <div className="login-card-head">
          <span className="eyebrow">SECURE ACCESS</span>
          <h1>Welcome back</h1>
          <p>Sign in to continue to your operations workspace.</p>
        </div>
        <form onSubmit={submit}>
          <label>Email address
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <div className="form-error">{error}</div>}
          <button className="primary-button" disabled={busy}>{busy ? "Signing in..." : "Sign in"} <ChevronRight size={17} /></button>
        </form>
        <div className="demo-note"><ShieldCheck size={16} /> Demo credentials are pre-filled</div>
      </section>
    </main>
  );
}

function StatusBadge({ value }) {
  const label = String(value || "ok").replaceAll("_", " ");
  return <span className={`status status-${label.replaceAll(" ", "-")}`}><i />{label}</span>;
}

function App() {
  const [initialUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("ccp_user")); } catch { return null; }
  });
  const [user, setUser] = useState(initialUser && getToken() ? initialUser : null);
  const [page, setPage] = useState("dashboard");
  const [mobileNav, setMobileNav] = useState(false);

  if (!user) return <Login onLogin={setUser} />;

  const nav = [
    { id: "dashboard", label: "Overview", icon: LayoutDashboard, roles: null },
    { id: "shipments", label: "Shipments", icon: Box, roles: null },
    { id: "alerts", label: "Alerts", icon: Bell, roles: null },
  ];
  if (["admin", "dispatcher", "auditor"].includes(user.role)) {
    nav.push({ id: "reports", label: "Reports", icon: Archive, roles: ["admin", "dispatcher", "auditor"] });
  }
  if (["admin", "dispatcher"].includes(user.role)) {
    nav.push({ id: "fleet", label: "Fleet & Users", icon: Users, roles: ["admin", "dispatcher"] });
  }
  if (["admin", "auditor"].includes(user.role)) {
    nav.push({ id: "audit", label: "Audit log", icon: ShieldCheck, roles: ["admin", "auditor"] });
  }
  if (["driver", "clinic_receiver"].includes(user.role)) {
    nav.push({ id: "handoff", label: "Handoff", icon: Truck, roles: ["driver", "clinic_receiver"] });
  }

  function logout() {
    clearSession();
    setUser(null);
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-mark small"><Activity size={21} /></div>
          <div><strong>ColdChain</strong><span> PULSE</span></div>
          <button className="icon-button close-nav" onClick={() => setMobileNav(false)}><X size={18} /></button>
        </div>
        <nav>
          <span className="nav-label">WORKSPACE</span>
          {nav.map((item) => (
            <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => { setPage(item.id); setMobileNav(false); }}>
              <item.icon size={19} /><span>{item.label}</span>
              {item.id === "alerts" && <span className="nav-count" id="alert-nav-count" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-avatar">{user.name.slice(0, 1).toUpperCase()}</div>
          <div className="user-meta"><strong>{user.name}</strong><span>{roleLabels[user.role]}</span></div>
          <button className="icon-button" title="Sign out" onClick={logout}><LogOut size={17} /></button>
        </div>
      </aside>
      {mobileNav && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
      <div className="main-shell">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setMobileNav(true)}><Menu size={20} /></button>
          <div className="system-status"><i /> Systems operational</div>
          <div className="topbar-actions">
            <button className="icon-button" onClick={() => setPage("alerts")} title="Alerts"><Bell size={18} /></button>
            <div className="top-avatar">{user.name.slice(0, 1).toUpperCase()}</div>
          </div>
        </header>
        <main className="content">
          {page === "dashboard" && <Dashboard user={user} openShipment={(id) => setPage(`shipments:${id}`)} />}
          {page.startsWith("shipments") && <Shipments role={user.role} selectedId={page.includes(":") ? Number(page.split(":")[1]) : null} />}
          {page === "alerts" && <Alerts role={user.role} />}
          {page === "reports" && <Reports />}
          {page === "fleet" && <Fleet role={user.role} />}
          {page === "audit" && <AuditLogs />}
          {page === "handoff" && <Handoff role={user.role} />}
        </main>
      </div>
    </div>
  );
}

function PageHead({ eyebrow, title, description, actions }) {
  return (
    <div className="page-head">
      <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{description && <p>{description}</p>}</div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

function Dashboard({ user, openShipment }) {
  const [summary, setSummary] = useState(null);
  const [shipments, setShipments] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api("/dashboard/summary"),
      api("/shipments?page=1&page_size=6"),
      api("/alerts?unacknowledged=true&limit=5"),
    ]).then(([s, p, a]) => { setSummary(s); setShipments(p.items); setAlerts(a); })
      .catch((e) => setError(e.message));
  }, []);

  const cards = summary ? [
    { label: "Active shipments", value: Object.values(summary.shipments_by_status).reduce((a, b) => a + b, 0) - (summary.shipments_by_status.delivered || 0), icon: Truck, tone: "blue" },
    { label: "In transit", value: summary.shipments_by_status.in_transit || 0, icon: Activity, tone: "cyan" },
    { label: "Open alerts", value: (summary.open_alerts.warning || 0) + (summary.open_alerts.critical || 0), icon: AlertTriangle, tone: "amber" },
    { label: "Compromised", value: summary.compromised_shipments || 0, icon: ShieldCheck, tone: "red" },
  ] : [];

  return (
    <>
      <PageHead eyebrow="OPERATIONS" title={`Good ${new Date().getHours() < 12 ? "morning" : "afternoon"}, ${user.name.split(" ")[0]}`}
        description="Live cold-chain monitoring and shipment activity." />
      {error && <div className="form-error">{error}</div>}
      <div className="metric-grid">
        {cards.map((card) => (
          <div className="metric-card" key={card.label}>
            <div className={`metric-icon ${card.tone}`}><card.icon size={20} /></div>
            <div><span>{card.label}</span><strong>{card.value}</strong></div>
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="panel recent-panel">
          <div className="panel-head"><div><span className="eyebrow">LIVE FLEET</span><h2>Recent shipments</h2></div><button className="text-button">View all <ChevronRight size={15} /></button></div>
          <div className="table-wrap">
            <table><thead><tr><th>Shipment</th><th>Route</th><th>Status</th><th>Temperature</th></tr></thead>
              <tbody>{shipments.map((s) => (
                <tr key={s.id} onClick={() => openShipment(s.id)}>
                  <td><strong>{s.code}</strong><span>{s.product || "Medical supplies"}</span></td>
                  <td>{s.origin} <b>→</b> {s.destination}</td>
                  <td><StatusBadge value={s.status} /></td>
                  <td>{s.last_temp != null ? <strong className={s.last_temp < s.min_temp || s.last_temp > s.max_temp ? "danger-text" : ""}>{s.last_temp.toFixed(1)}°C</strong> : <span className="muted">No data</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
        <section className="panel alert-panel">
          <div className="panel-head"><div><span className="eyebrow">ATTENTION</span><h2>Active alerts</h2></div></div>
          {alerts.length ? alerts.map((alert) => (
            <button className="alert-row" key={alert.id} onClick={() => openShipment(alert.shipment_id)}>
              <div className={`alert-symbol ${alert.level}`}><AlertTriangle size={17} /></div>
              <div><strong>{alert.level === "critical" ? "Critical breach" : "Temperature warning"}</strong><span>Shipment #{alert.shipment_id} · {alert.temperature != null ? `${alert.temperature}°C` : "Monitoring"}</span></div>
              <ChevronRight size={16} />
            </button>
          )) : <div className="empty-state"><Check size={22} /><p>No open alerts</p></div>}
        </section>
      </div>
    </>
  );
}

function Shipments({ role, selectedId }) {
  const [shipments, setShipments] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const params = new URLSearchParams({ page: "1", page_size: "100" });
      if (filter) params.set("status", filter);
      const data = await api(`/shipments?${params}`);
      setShipments(data.items);
      setTotal(data.total);
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { load(); }, [filter]);
  useEffect(() => {
    if (selectedId) api(`/shipments/${selectedId}`).then(setSelected).catch(() => {});
  }, [selectedId]);

  const visible = shipments.filter((s) => `${s.code} ${s.origin} ${s.destination} ${s.product}`.toLowerCase().includes(search.toLower()));

  return (
    <>
      <PageHead eyebrow="OPERATIONS" title="Shipments" description={`${total} shipment${total === 1 ? "" : "s"} in your workspace`}
        actions={["admin", "dispatcher"].includes(role) && <button className="primary-button" onClick={() => setCreateOpen(true)}><Plus size={17} /> New shipment</button>} />
      {error && <div className="form-error">{error}</div>}
      <section className="panel">
        <div className="toolbar">
          <div className="search-box"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search shipments..." /></div>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}><option value="">All statuses</option><option value="created">Created</option><option value="in_transit">In transit</option><option value="delivered">Delivered</option><option value="cancelled">Cancelled</option></select>
        </div>
        <div className="table-wrap">
          <table><thead><tr><th>Shipment</th><th>Route</th><th>Status</th><th>Alert state</th><th>Temperature</th><th /></tr></thead>
            <tbody>{visible.map((s) => (
              <tr key={s.id} onClick={() => setSelected(s)}>
                <td><strong>{s.code}</strong><span>{s.product || "Medical supplies"}</span></td>
                <td><strong>{s.origin}</strong><span>to {s.destination}</span></td>
                <td><StatusBadge value={s.status} /></td>
                <td><StatusBadge value={s.alert_state} /></td>
                <td>{s.last_temp != null ? <strong>{s.last_temp.toFixed(1)}°C</strong> : <span className="muted">—</span>}</td>
                <td><ChevronRight size={16} /></td>
              </tr>
            ))}</tbody>
          </table>
          {!visible.length && <div className="empty-state"><Box size={24} /><p>No shipments found</p></div>}
        </div>
      </section>
      {selected && <ShipmentDrawer shipment={selected} role={role} onClose={() => setSelected(null)} />}
      {createOpen && <CreateShipment onClose={() => setCreateOpen(false)} onCreated={() => { setCreateOpen(false); load(); }} />}
    </>
  );
}

function ShipmentDrawer({ shipment, role, onClose }) {
  const [detail, setDetail] = useState(shipment);
  const [telemetry, setTelemetry] = useState([]);
  const [handoffs, setHandoffs] = useState([]);
  useEffect(() => {
    Promise.all([
      api(`/shipments/${shipment.id}`),
      api(`/shipments/${shipment.id}/telemetry?limit=100`),
      api(`/shipments/${shipment.id}/handoffs`),
    ]).then(([d, t, h]) => { setDetail(d); setTelemetry(t); setHandoffs(h); }).catch(() => {});
  }, [shipment.id]);

  const values = telemetry.map((r) => r.temperature);
  const max = values.length ? Math.max(...values, detail.max_temp) : detail.max_temp;
  const min = values.length ? Math.min(...values, detail.min_temp) : detail.min_temp;
  const range = max - min || 1;
  const points = values.map((v, i) => `${values.length === 1 ? 50 : i * 100 / (values.length - 1)},${92 - ((v - min) / range) * 80}`).join(" ");

  return (
    <div className="drawer-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer">
        <div className="drawer-head"><div><span className="eyebrow">SHIPMENT DETAIL</span><h2>{detail.code}</h2></div><button className="icon-button" onClick={onClose}><X size={19} /></button></div>
        <div className="drawer-status"><StatusBadge value={detail.status} /><StatusBadge value={detail.alert_state} /></div>
        <div className="detail-route"><div><span>ORIGIN</span><strong>{detail.origin}</strong></div><div className="route-line"><Truck size={17} /></div><div><span>DESTINATION</span><strong>{detail.destination}</strong></div></div>
        <div className="detail-grid">
          <div><span>Product</span><strong>{detail.product || "—"}</strong></div>
          <div><span>Temperature range</span><strong>{detail.min_temp}–{detail.max_temp} °C</strong></div>
          <div><span>Last reading</span><strong>{detail.last_temp != null ? `${detail.last_temp} °C` : "No data"}</strong></div>
          <div><span>ETA</span><strong>{detail.eta ? new Date(detail.eta).toLocaleString() : "Not set"}</strong></div>
        </div>
        <section className="detail-section">
          <div className="section-title"><h3>Temperature history</h3><span>{telemetry.length} readings</span></div>
          {values.length ? <div className="chart">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none"><polygon points={`0,100 ${points} 100,100`} /><polyline points={points} /></svg>
            <div className="chart-labels"><span>{detail.min_temp}°C</span><span>{detail.max_temp}°C</span></div>
          </div> : <div className="empty-state small"><Thermometer size={20} /><p>No telemetry yet</p></div>}
        </section>
        <section className="detail-section">
          <div className="section-title"><h3>Chain of custody</h3><span>{handoffs.length} events</span></div>
          <div className="timeline">{handoffs.map((h) => <div key={h.id}><i /><div><strong>{h.type}</strong><span>{new Date(h.recorded_at).toLocaleString()}</span><span>{h.condition.replaceAll("_", " ")} · PIN {h.pin_verified ? "verified" : "not used"}</span></div></div>)}
            {!handoffs.length && <p className="muted">No handoffs recorded</p>}</div>
        </section>
        {["admin", "dispatcher", "auditor"].includes(role) && <button className="secondary-button full" onClick={() => downloadReport(`/reports/shipments/${detail.id}.pdf`, `${detail.code}_audit.pdf`)}><Download size={16} /> Download compliance report</button>}
      </aside>
    </div>
  );
}

function CreateShipment({ onClose, onCreated }) {
  const [users, setUsers] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [form, setForm] = useState({ origin: "", destination: "", product: "", vehicle_id: "", driver_id: "", receiver_id: "", min_temp: 2, max_temp: 8 });
  const [created, setCreated] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api("/users"), api("/vehicles")]).then(([u, v]) => { setUsers(u); setVehicles(v); }).catch((e) => setError(e.message));
  }, []);
  function change(e) { setForm({ ...form, [e.target.name]: e.target.value }); }
  async function submit(e) {
    e.preventDefault(); setError("");
    const body = { ...form,
      vehicle_id: form.vehicle_id ? Number(form.vehicle_id) : null,
      driver_id: form.driver_id ? Number(form.driver_id) : null,
      receiver_id: form.receiver_id ? Number(form.receiver_id) : null,
    };
    try { setCreated(await api("/shipments", { method: "POST", body: JSON.stringify(body) })); onCreated(); }
    catch (e) { setError(e.message); }
  }
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section className="modal">
        <div className="modal-head"><div><span className="eyebrow">DISPATCH</span><h2>{created ? "Shipment created" : "Create shipment"}</h2></div><button className="icon-button" onClick={onClose}><X size={19} /></button></div>
        {created ? <div className="created-result">
          <div className="success-icon"><Check size={24} /></div><h3>{created.code}</h3>
          <p>Save these credentials now. PINs cannot be retrieved later.</p>
          <div className="credential-grid"><div><span>QR payload</span><code>{created.qr_token}</code></div><div><span>Pickup PIN</span><strong>{created.pickup_pin}</strong></div><div><span>Delivery PIN</span><strong>{created.delivery_pin}</strong></div></div>
          <button className="primary-button full" onClick={onClose}>Done</button>
        </div> : <form onSubmit={submit} className="modal-form">
          <div className="form-grid"><label>Origin<input name="origin" value={form.origin} onChange={change} required /></label><label>Destination<input name="destination" value={form.destination} onChange={change} required /></label></div>
          <label>Product / contents<input name="product" value={form.product} onChange={change} /></label>
          <div className="form-grid"><label>Min temperature (°C)<input type="number" step="0.1" name="min_temp" value={form.min_temp} onChange={change} required /></label><label>Max temperature (°C)<input type="number" step="0.1" name="max_temp" value={form.max_temp} onChange={change} required /></label></div>
          <label>Vehicle<select name="vehicle_id" value={form.vehicle_id} onChange={change}><option value="">Unassigned</option>{vehicles.map((v) => <option key={v.id} value={v.id}>{v.plate} — {v.label}</option>)}</select></label>
          <div className="form-grid"><label>Assigned driver<select name="driver_id" value={form.driver_id} onChange={change}><option value="">Unassigned</option>{users.filter((u) => u.role === "driver").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label><label>Receiving clinic<select name="receiver_id" value={form.receiver_id} onChange={change}><option value="">Unassigned</option>{users.filter((u) => u.role === "clinic_receiver").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label></div>
          {error && <div className="form-error">{error}</div>}
          <button className="primary-button full" disabled={!form.origin || !form.destination}>Create shipment</button>
        </form>}
      </section>
    </div>
  );
}

function Alerts({ role }) {
  const [alerts, setAlerts] = useState([]);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  async function load() { try { setAlerts(await api(`/alerts?unacknowledged=${filter === "open"}&limit=100`)); } catch (e) { setError(e.message); } }
  useEffect(() => { load(); }, [filter]);
  async function acknowledge(id) { try { await api(`/alerts/${id}/acknowledge`, { method: "POST" }); load(); } catch (e) { setError(e.message); } }
  const visible = alerts.filter((a) => filter === "all" || filter === "open" || a.level === filter);
  return <>
    <PageHead eyebrow="MONITORING" title="Alert center" description="Temperature warnings and critical cold-chain breaches" />
    {error && <div className="form-error">{error}</div>}
    <div className="filter-tabs">{[["all", "All"], ["open", "Open"], ["warning", "Warnings"], ["critical", "Critical"]].map(([id, label]) => <button key={id} className={filter === id ? "active" : ""} onClick={() => setFilter(id)}>{label}</button>)}</div>
    <section className="alert-list">{visible.map((a) => <article className={`alert-card ${a.level}`} key={a.id}>
      <div className="alert-card-icon"><AlertTriangle size={21} /></div><div className="alert-card-copy"><div><strong>{a.level}</strong>{a.acknowledged_at && <span className="acknowledged"><Check size={12} /> Acknowledged</span>}</div><h3>{a.message}</h3><p>Shipment #{a.shipment_id} · {new Date(a.created_at).toLocaleString()}</p></div>
      {!a.acknowledged_at && ["admin", "dispatcher", "driver"].includes(role) && <button className="secondary-button" onClick={() => acknowledge(a.id)}>Acknowledge</button>}
    </article>)}
      {!visible.length && <div className="panel empty-state"><ShieldCheck size={25} /><p>No alerts match this view</p></div>}
    </section>
  </>;
}

function Reports() {
  const [shipments, setShipments] = useState([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    api("/shipments?page=1&page_size=200")
      .then((data) => setShipments(data.items))
      .catch((e) => setError(e.message));
  }, []);
  const visible = shipments.filter((s) => `${s.code} ${s.origin} ${s.destination}`.toLower())
    .filter((s) => `${s.code} ${s.origin} ${s.destination}`.toLower().includes(search.toLowerCase()));
  return <>
    <PageHead eyebrow="COMPLIANCE" title="Reports & integrity" description="Download audit reports and verify tamper-evident shipment logs" />
    {error && <div className="form-error">{error}</div>}
    <section className="panel">
      <div className="toolbar"><div className="search-box"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find a shipment..." /></div></div>
      <div className="table-wrap"><table><thead><tr><th>Shipment</th><th>Route</th><th>Status</th><th>Actions</th></tr></thead><tbody>
        {visible.map((s) => <tr key={s.id}><td><strong>{s.code}</strong><span>{s.product || "Medical supplies"}</span></td><td>{s.origin} → {s.destination}</td><td><StatusBadge value={s.status} /></td><td><div className="row-actions"><button title="Verify chain" onClick={() => api(`/reports/shipments/${s.id}/verify`).then((r) => alert(r.tamper_free ? "Chain integrity verified" : "Tampering detected")).catch((e) => alert(e.message))}><ShieldCheck size={16} /></button><button title="Download CSV" onClick={() => downloadReport(`/reports/shipments/${s.id}.csv`, `${s.code}_audit.csv`)}><Download size={16} /></button><button title="Download PDF" onClick={() => downloadReport(`/reports/shipments/${s.id}.pdf`, `${s.code}_audit.pdf`)}><Download size={16} /></button></div></td></tr>)}
      </tbody></table></div>
    </section>
  </>;
}

function Fleet({ role }) {
  const [tab, setTab] = useState("users");
  const [users, setUsers] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);
  async function load() {
    try {
      const [u, v] = await Promise.all([api("/users"), api("/vehicles")]);
      setUsers(u); setVehicles(v);
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { load(); }, []);
  async function submit(e) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    try {
      if (tab === "users") await api("/users", { method: "POST", body: JSON.stringify({ email: data.get("email"), name: data.get("name"), password: data.get("password"), role: data.get("role") }) });
      else await api("/vehicles", { method: "POST", body: JSON.stringify({ plate: data.get("plate"), label: data.get("label") }) });
      setModal(null); load();
    } catch (e) { setError(e.message); }
  }
  return <>
    <PageHead eyebrow="ADMINISTRATION" title="Fleet & users" description="Manage staff accounts and refrigerated vehicles"
      actions={(role === "admin" || (role === "dispatcher" && tab === "vehicles")) && <button className="primary-button" onClick={() => setModal(tab)}><Plus size={17} /> {tab === "users" ? "Add user" : "Add vehicle"}</button>} />
    {error && <div className="form-error">{error}</div>}
    <div className="filter-tabs"><button className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>Users</button><button className={tab === "vehicles" ? "active" : ""} onClick={() => setTab("vehicles")}>Vehicles</button></div>
    <section className="panel"><div className="table-wrap"><table>
      {tab === "users" ? <><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th></tr></thead><tbody>{users.map((u) => <tr key={u.id}><td><strong>{u.name}</strong></td><td>{u.email}</td><td><StatusBadge value={u.role} /></td><td><StatusBadge value={u.is_active ? "active" : "inactive"} /></td></tr>)}</tbody></>
      : <><thead><tr><th>Plate</th><th>Label</th><th>Status</th></tr></thead><tbody>{vehicles.map((v) => <tr key={v.id}><td><strong>{v.plate}</strong></td><td>{v.label || "—"}</td><td><StatusBadge value={v.is_active ? "active" : "inactive"} /></td></tr>)}</tbody></>}
    </table></div></section>
    {modal && <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setModal(null)}><section className="modal compact"><div className="modal-head"><h2>{tab === "users" ? "Add user" : "Add vehicle"}</h2><button className="icon-button" onClick={() => setModal(null)}><X size={18} /></button></div>
      <form onSubmit={submit} className="modal-form">{tab === "users" ? <>
        <label>Name<input name="name" required /></label><label>Email<input type="email" name="email" required /></label><label>Password<input type="password" name="password" minLength="8" required /></label><label>Role<select name="role" required><option value="dispatcher">Dispatcher</option><option value="driver">Driver</option><option value="clinic_receiver">Clinic receiver</option><option value="auditor">Auditor</option><option value="admin">Administrator</option></select></label>
      </> : <><label>Plate<input name="plate" required /></label><label>Label<input name="label" /></label></>}
      <button className="primary-button full">Save</button></form>
    </section></div>}
  </>;
}

function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [event, setEvent] = useState("");
  const [error, setError] = useState("");
  async function load() {
    try { setLogs(await api(`/audit-logs${event ? `?event=${encodeURIComponent(event)}` : "?limit=300"}`)); } catch (e) { setError(e.message); }
  }
  useEffect(() => { load(); }, [event]);
  return <>
    <PageHead eyebrow="SECURITY" title="Audit trail" description="Append-only operational and authentication events" />
    {error && <div className="form-error">{error}</div>}
    <section className="panel"><div className="toolbar"><div className="search-box"><Search size={17} /><input value={event} onChange={(e) => setEvent(e.target.value)} placeholder="Filter by event..." /></div></div><div className="table-wrap"><table><thead><tr><th>Time</th><th>Event</th><th>User / email</th><th>IP address</th><th>Detail</th></tr></thead><tbody>{logs.map((l) => <tr key={l.id}><td>{new Date(l.created_at).toLocaleString()}</td><td><StatusBadge value={l.event} /></td><td>{l.email || l.user_id || "—"}</td><td>{l.ip || "—"}</td><td>{l.detail || "—"}</td></tr>)}</tbody></table></div></section>
  </>;
}

function Handoff({ role }) {
  const [shipments, setShipments] = useState([]);
  const [shipmentId, setShipmentId] = useState("");
  const [type, setType] = useState(role === "driver" ? "pickup" : "delivery");
  const [qr, setQr] = useState("");
  const [pin, setPin] = useState("");
  const [condition, setCondition] = useState("intact");
  const [notes, setNotes] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/shipments?page=1&page_size=200").then((d) => setShipments(d.items)).catch((e) => setError(e.message)); }, []);
  function locate() {
    if (!navigator.geolocation) return setError("Geolocation is not supported");
    navigator.geolocation.getCurrentPosition((p) => { setLatitude(p.coords.latitude.toFixed(6)); setLongitude(p.coords.longitude.toFixed(6)); }, () => setError("Could not access location"));
  }
  async function submit(e) {
    e.preventDefault(); setError(""); setResult(null);
    try {
      const body = { type, qr_token: qr, pin: pin || null, latitude: latitude ? Number(latitude) : null, longitude: longitude ? Number(longitude) : null, condition, notes: notes || null, client_uuid: crypto.randomUUID() };
      const handoff = await api(`/shipments/${shipmentId}/handoffs`, { method: "POST", body: JSON.stringify(body) });
      setResult(handoff);
    } catch (e) { setError(e.message); }
  }
  return <>
    <PageHead eyebrow="CHAIN OF CUSTODY" title="Record handoff" description="Capture pickup or delivery credentials and condition" />
    <section className="handoff-layout">
      <form className="panel handoff-form" onSubmit={submit}>
        <div className="handoff-type"><button type="button" className={type === "pickup" ? "active" : ""} disabled={role !== "driver"} onClick={() => setType("pickup")}><Truck size={18} /> Pickup</button><button type="button" className={type === "delivery" ? "active" : ""} disabled={role !== "clinic_receiver"} onClick={() => setType("delivery")}><Archive size={18} /> Delivery</button></div>
        <label>Shipment<select value={shipmentId} onChange={(e) => setShipmentId(e.target.value)} required><option value="">Select shipment</option>{shipments.map((s) => <option key={s.id} value={s.id}>{s.code} — {s.origin} → {s.destination}</option>)}</select></label>
        <label>QR payload<input value={qr} onChange={(e) => setQr(e.target.value)} placeholder="coldchain:ID:TOKEN" required /></label>
        <label>{type === "pickup" ? "Pickup" : "Delivery"} PIN<input value={pin} onChange={(e) => setPin(e.target.value)} inputMode="numeric" maxLength="12" required /></label>
        <label>Condition<select value={condition} onChange={(e) => setCondition(e.target.value)}><option value="intact">Intact</option><option value="damaged">Damaged</option><option value="temperature_concern">Temperature concern</option></select></label>
        <label>Notes<textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength="1000" /></label>
        <div className="location-row"><button type="button" className="secondary-button" onClick={locate}>Use current location</button><input value={latitude} onChange={(e) => setLatitude(e.target.value)} placeholder="Latitude" /><input value={longitude} onChange={(e) => setLongitude(e.target.value)} placeholder="Longitude" /></div>
        {error && <div className="form-error">{error}</div>}
        {result && <div className="success-note"><Check size={17} /> Handoff recorded and added to the append-only chain.</div>}
        <button className="primary-button full">Record handoff</button>
      </form>
      <aside className="handoff-help"><div className="brand-mark"><ShieldCheck size={24} /></div><h3>Verified custody</h3><p>Both credential validation and timestamped location are recorded in the shipment’s tamper-evident chain.</p><div className="help-step"><span>1</span><div><strong>Verify QR</strong><p>Scan or enter the parcel payload.</p></div></div><div className="help-step"><span>2</span><div><strong>Confirm PIN</strong><p>Use the PIN issued at dispatch.</p></div></div><div className="help-step"><span>3</span><div><strong>Record condition</strong><p>Capture location and any exception.</p></div></div></aside>
    </section>
  </>;
}

export default App;
