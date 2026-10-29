import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Archive,
  Bell,
  BriefcaseBusiness,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Clock3,
  Command,
  Download,
  Ellipsis,
  FileSearch,
  Filter,
  LayoutDashboard,
  LockKeyhole,
  Menu,
  Plus,
  Search,
  Settings,
  Shield,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  User,
  X,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "./services/api";
import Alerts from "./pages/Alerts";
import Incidents from "./pages/Incidents";
import Playbooks from "./pages/Playbooks";
import UsersPage from "./pages/Users";
import Logs from "./pages/Logs";

/**
 * Accepte les formats courants renvoyés par une API :
 * - [...]
 * - { data: [...] }
 * - { incidents: [...] }
 * - { alerts: [...] }
 */
function extractArray(response, possibleKeys = []) {
  if (Array.isArray(response)) return response;

  if (response && Array.isArray(response.data)) {
    return response.data;
  }

  for (const key of possibleKeys) {
    if (response && Array.isArray(response[key])) {
      return response[key];
    }
  }

  return [];
}

function extractObject(response) {
  if (!response || typeof response !== "object") return {};

  if (
    response.data &&
    typeof response.data === "object" &&
    !Array.isArray(response.data)
  ) {
    return response.data;
  }

  return response;
}

/**
 * Uniformise les champs d'un incident pour l'affichage.
 * Les noms en snake_case sont également acceptés.
 */
function normalizeIncident(item, index = 0) {
  return {
    ...item,
    id: item.id ?? item.incident_id ?? item.uuid ?? `incident-${index}`,
    title: item.title ?? item.name ?? item.summary ?? "Incident sans titre",
    source: item.source ?? item.origin ?? item.device ?? "Non renseignée",
    severity: normalizeSeverity(item.severity ?? item.priority),
    status: normalizeStatus(item.status ?? item.state),
    assignee:
      item.assignee ??
      item.assigned_to ??
      item.owner ??
      "Non assigné",
    time:
      item.time ??
      item.last_activity ??
      item.updated_at ??
      item.created_at ??
      "—",
  };
}

function normalizeSeverity(value) {
  if (!value) return "Moyenne";

  const severity = String(value).toLowerCase();

  if (
    severity.includes("critical") ||
    severity.includes("critique") ||
    severity === "p1"
  ) {
    return "Critique";
  }

  if (
    severity.includes("high") ||
    severity.includes("élevée") ||
    severity.includes("elevee") ||
    severity === "p2"
  ) {
    return "Élevée";
  }

  if (
    severity.includes("low") ||
    severity.includes("faible") ||
    severity === "p4"
  ) {
    return "Faible";
  }

  if (
    severity.includes("medium") ||
    severity.includes("moyenne") ||
    severity === "p3"
  ) {
    return "Moyenne";
  }

  return String(value);
}

function normalizeStatus(value) {
  if (!value) return "À qualifier";

  const status = String(value).toLowerCase();

  if (
    status.includes("closed") ||
    status.includes("resolved") ||
    status.includes("résolu") ||
    status.includes("resolu") ||
    status.includes("clos")
  ) {
    return "Résolu";
  }

  if (
    status.includes("progress") ||
    status.includes("investigat") ||
    status.includes("en cours") ||
    status.includes("open")
  ) {
    return "En cours";
  }

  if (
    status.includes("qualif") ||
    status.includes("new") ||
    status.includes("nouveau")
  ) {
    return "À qualifier";
  }

  return String(value);
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "—";

  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("fr-FR").format(number)
    : value;
}

function StatusPill({ children }) {
  const status = String(children).toLowerCase();

  const cls =
    status.includes("cours") || status.includes("progress")
      ? "status-progress"
      : status.includes("qualif") || status.includes("new")
        ? "status-review"
        : "status-closed";

  return (
    <span className={`status-pill ${cls}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}

function SeverityPill({ children }) {
  const cls =
    children === "Critique"
      ? "severity-critical"
      : children === "Élevée"
        ? "severity-high"
        : children === "Moyenne"
          ? "severity-medium"
          : "severity-low";

  return (
    <span className={`severity-pill ${cls}`}>
      <span className="severity-dot" />
      {children}
    </span>
  );
}

const navGroups = [
  {
    label: "ESPACE DE TRAVAIL",
    items: [
      { name: "Dashboard", icon: LayoutDashboard },
      { name: "Incidents", icon: ShieldAlert },
      { name: "Alertes", icon: Bell },
      { name: "Journaux", icon: FileSearch },
    ],
  },
  {
  label: "INVESTIGATION",
  items: [
    { name: "Playbooks", icon: ClipboardList },
  ],
},
  {
    label: "ADMINISTRATION",
    items: [
      { name: "Utilisateurs", icon: Users },
    ],
  },
];

function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("Toutes");
  const [showNewIncident, setShowNewIncident] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [incidents, setIncidents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);
  const [trendData, setTrendData] = useState([]);

  const [loading, setLoading] = useState(true);
  const [creatingIncident, setCreatingIncident] = useState(false);
  const [incidentsError, setIncidentsError] = useState("");
  const [dashboardError, setDashboardError] = useState("");
  const [alertsError, setAlertsError] = useState("");
  const [notice, setNotice] = useState("");

  function showNotice(message) {
    setNotice(message);
  }

  /**
   * Charge les données réelles depuis le service API.
   * Une erreur sur une ressource ne bloque pas le chargement des autres.
   */
  async function loadData() {
    setLoading(true);
    setIncidentsError("");
    setDashboardError("");
    setAlertsError("");

    const results = await Promise.allSettled([
      api.getIncidents(),
      api.getDashboard(),
      api.getAlerts(),
    ]);

    const [incidentsResult, dashboardResult, alertsResult] = results;

    if (incidentsResult.status === "fulfilled") {
      const list = extractArray(incidentsResult.value, ["incidents", "results"]);
      setIncidents(list.map(normalizeIncident));
    } else {
      setIncidents([]);
      setIncidentsError(
        "Impossible de charger les incidents. Vérifie que le backend est démarré et que l'API est accessible."
      );
    }

    if (dashboardResult.status === "fulfilled") {
      const data = extractObject(dashboardResult.value);
      setDashboardData(data);

      const chart =
        data.trendData ??
        data.trends ??
        data.activity ??
        data.alertActivity ??
        data.alert_activity ??
        [];

      setTrendData(
        Array.isArray(chart)
          ? chart.map((item) => ({
              day: item.day ?? item.date ?? item.label ?? "—",
              alerts: Number(item.alerts ?? item.detected ?? item.total_alerts ?? 0),
              resolved: Number(
                item.resolved ??
                  item.treated ??
                  item.processed ??
                  item.alerts_resolved ??
                  0
              ),
            }))
          : []
      );
    } else {
      setDashboardData(null);
      setTrendData([]);
      setDashboardError(
        "Les statistiques du dashboard ne sont pas disponibles pour le moment."
      );
    }

    if (alertsResult.status === "fulfilled") {
      setAlerts(
        extractArray(alertsResult.value, ["alerts", "results"])
      );
    } else {
      setAlerts([]);
      setAlertsError("Impossible de charger les alertes.");
    }

    setLoading(false);
  }

  useEffect(() => {
    loadData();
  }, []);

  const visibleIncidents = useMemo(() => {
    const searchText = search.trim().toLowerCase();

    return incidents.filter((item) => {
      const matchesSearch = [
        item.id,
        item.title,
        item.source,
        item.assignee,
        item.status,
        item.severity,
      ]
        .join(" ")
        .toLowerCase()
        .includes(searchText);

      const matchesFilter =
        filter === "Toutes" || item.severity === filter;

      return matchesSearch && matchesFilter;
    });
  }, [incidents, search, filter]);

  const activeIncidents = incidents.filter(
    (item) => item.status !== "Résolu"
  );

  const severityCounts = {
    Critique: activeIncidents.filter((item) => item.severity === "Critique").length,
    "Élevée": activeIncidents.filter((item) => item.severity === "Élevée").length,
    Moyenne: activeIncidents.filter((item) => item.severity === "Moyenne").length,
    Faible: activeIncidents.filter((item) => item.severity === "Faible").length,
  };

  const severityTotal = Object.values(severityCounts).reduce(
    (total, value) => total + value,
    0
  );

  const severityPercent = (count) =>
    severityTotal > 0
      ? `${((count / severityTotal) * 100).toLocaleString("fr-FR", {
          maximumFractionDigits: 1,
        })}%`
      : "0 %";

  const openIncidents =
    dashboardData?.openIncidents ??
    dashboardData?.open_incidents ??
    dashboardData?.incidents_open ??
    activeIncidents.length;

  const alertsToProcess =
    dashboardData?.alertsToProcess ??
    dashboardData?.alerts_to_process ??
    dashboardData?.pendingAlerts ??
    dashboardData?.pending_alerts ??
    alerts.length;

  const resolvedThisMonth =
    dashboardData?.resolvedThisMonth ??
    dashboardData?.resolved_this_month ??
    dashboardData?.resolvedIncidents ??
    dashboardData?.resolved_incidents ??
    incidents.filter((item) => item.status === "Résolu").length;

  const averageResponse =
    dashboardData?.averageResponseMinutes ??
    dashboardData?.average_response_minutes ??
    dashboardData?.averageResponseTime ??
    dashboardData?.average_response_time;

  const criticalAlerts =
    dashboardData?.criticalAlerts ??
    dashboardData?.critical_alerts ??
    alerts.filter(
      (item) =>
        normalizeSeverity(item.severity ?? item.priority) === "Critique"
    ).length;

  async function addIncident(event) {
    event.preventDefault();

    if (creatingIncident) return;

    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const title = String(form.get("title") || "").trim();

    if (!title) {
      showNotice("Le titre de l'incident est obligatoire.");
      return;
    }

    const newIncident = {
      title,
      source: String(form.get("source") || "Saisie manuelle"),
      severity: String(form.get("severity") || "Moyenne"),
    };

    setCreatingIncident(true);
    setIncidentsError("");

    try {
      await api.createIncident(newIncident);

      setShowNewIncident(false);
      formElement.reset();

      showNotice("Incident transmis à l'API avec succès.");
      await loadData();
    } catch (error) {
      console.error("Erreur lors de la création de l'incident :", error);
      showNotice(
        "La création a échoué. Vérifie la connexion au backend et les données demandées par l'API."
      );
    } finally {
      setCreatingIncident(false);
    }
  }

  function handleExport() {
    if (incidents.length === 0) {
      showNotice("Aucun incident à exporter.");
      return;
    }

    const headers = [
      "ID",
      "Titre",
      "Source",
      "Sévérité",
      "Statut",
      "Responsable",
      "Dernière activité",
    ];

    const rows = incidents.map((incident) => [
      incident.id,
      incident.title,
      incident.source,
      incident.severity,
      incident.status,
      incident.assignee,
      incident.time,
    ]);

    const csv = [headers, ...rows]
      .map((row) =>
        row
          .map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`)
          .join(";")
      )
      .join("\n");

    const blob = new Blob(["\uFEFF" + csv], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "fanalyzer-incidents.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  const pageDescription =
    activePage === "Dashboard"
      ? "Vue d'ensemble de votre environnement de réponse aux incidents."
      : `Espace ${activePage.toLowerCase()}.`;

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark">
            <Shield size={22} strokeWidth={2.4} />
          </div>

          <div className="brand-copy">
            <strong>
              FAnalyzer IR<span>·</span>
            </strong>
            <small>INCIDENT RESPONSE</small>
          </div>

          <button
            className="icon-button sidebar-close"
            aria-label="Fermer le menu"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <nav className="side-nav">
          {navGroups.map((group) => (
            <section className="nav-group" key={group.label}>
              <p className="nav-label">{group.label}</p>

              {group.items.map(({ name, icon: Icon }) => (
                <button
                  key={name}
                  onClick={() => {
                    setActivePage(name);
                    setSidebarOpen(false);
                  }}
                  className={`nav-item ${
                    activePage === name ? "active" : ""
                  }`}
                >
                  <Icon size={17} strokeWidth={1.9} />
                  <span>{name}</span>

                  {name === "Incidents" && incidents.length > 0 && (
                    <span className="nav-count">{incidents.length}</span>
                  )}

                  {name === "Alertes" && alerts.length > 0 && (
                    <span className="nav-count count-alert">
                      {alerts.length}
                    </span>
                  )}
                </button>
              ))}
            </section>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="system-status">
            <span
              className="online-indicator"
              style={{ opacity: incidentsError || dashboardError ? 0.45 : 1 }}
            />
            <span>
              {loading
                ? "Connexion aux services…"
                : incidentsError || dashboardError
                  ? "Connexion à vérifier"
                  : "API connectée"}
            </span>
            <span className="status-check">
              {loading ? "…" : incidentsError || dashboardError ? "!" : "✓"}
            </span>
          </div>

          <button
            className="nav-item help-link"
            onClick={() =>
              showNotice(
                "Sélectionne une section dans le menu pour consulter les données disponibles."
              )
            }
          >
           
          </button>

        </div>
      </aside>

      {sidebarOpen && (
        <button
          className="mobile-scrim"
          aria-label="Fermer le menu"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              aria-label="Ouvrir le menu"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={20} />
            </button>

            <div className="breadcrumb">
              <span>Workspace</span>
              <ChevronRight size={14} />
              <strong>{activePage}</strong>
            </div>
          </div>

          <div className="topbar-actions">
            <div className="global-search">
              <Search size={16} />
              <input
                aria-label="Recherche globale"
                placeholder="Rechercher..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <kbd>⌘ K</kbd>
            </div>

            <button
              className="icon-button top-icon"
              aria-label="Aide"
              onClick={() =>
                showNotice(
                  "Utilise la recherche et les filtres pour retrouver les incidents."
                )
              }
            >
              <CircleHelp size={18} />
            </button>

            <button
              className="icon-button top-icon notification-button"
              aria-label="Notifications"
              onClick={() =>
                showNotice(
                  `${alerts.length} alerte(s) chargée(s) depuis l'API.`
                )
              }
            >
              <Bell size={18} />
              <i />
            </button>

            <button
  type="button"
  className="top-avatar"
  onClick={() => setActivePage("Utilisateurs")}
  title="Ouvrir la gestion des utilisateurs"
  aria-label="Ouvrir la gestion des utilisateurs"
  style={{
    cursor: "pointer",
    color: "inherit",
  }}
>
  <User size={18} />
</button>
          </div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="eyebrow-line" /> CENTRE DE SÉCURITÉ
              </div>
              <h1>{activePage}</h1>
              <p>{pageDescription}</p>
            </div>

            <div className="heading-actions">
              <button
                className="button button-secondary"
                onClick={() => {
                  setSearch("");
                  setFilter("Toutes");
                }}
              >
                <SlidersHorizontal size={16} />
                Réinitialiser
              </button>

{activePage !== "Utilisateurs" && activePage !== "Journaux" && (
  <button
    className="button button-primary"
    onClick={() => setShowNewIncident(true)}
  >
    <Plus size={17} />
    Nouvel incident
  </button>
)}
            </div>
          </div>

          
{activePage === "Utilisateurs" ? (
  <UsersPage />
) : activePage === "Playbooks" ? (
  <Playbooks />
) : activePage === "Incidents" ? (
  <Incidents />
) : activePage === "Alertes" ? (
  <Alerts />
) : activePage === "Journaux" ? (
  <Logs />
) : (
  <>

          <div className="context-strip">
            <div className="context-left">
              <span className="live-dot" />
              <strong>
                {loading ? "Connexion en cours" : "Surveillance"}
              </strong>
              <span className="context-separator">/</span>
              <span>
                {loading
                  ? "Chargement des données…"
                  : `Incidents chargés : ${incidents.length}`}
              </span>
            </div>

            <div className="context-right">
              <span>
                <LockKeyhole size={13} />
                Données de l'API
              </span>
              <button onClick={loadData} disabled={loading}>
                Actualiser <ChevronDown size={13} />
              </button>
            </div>
          </div>

          {(incidentsError || dashboardError || alertsError) && (
            <div
              role="alert"
              style={{
                padding: "12px 16px",
                marginBottom: "16px",
                borderRadius: "8px",
                border: "1px solid rgba(255, 170, 70, 0.35)",
                background: "rgba(255, 170, 70, 0.08)",
                color: "inherit",
              }}
            >
              <strong>Attention : certaines données sont indisponibles.</strong>
              <div style={{ marginTop: "6px", fontSize: "13px" }}>
                {[incidentsError, dashboardError, alertsError]
                  .filter(Boolean)
                  .join(" ")}
              </div>
              <button
                className="text-button"
                style={{ marginTop: "8px" }}
                onClick={loadData}
                disabled={loading}
              >
                Réessayer
              </button>
            </div>
          )}

          <section className="stats-grid" aria-label="Indicateurs clés">
            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-icon icon-blue">
                  <ShieldAlert size={19} />
                </span>
              </div>
              <p className="stat-label">Incidents ouverts</p>
              <div className="stat-value">
                {loading ? "…" : formatNumber(openIncidents)}
                <span className="stat-unit">incidents</span>
              </div>
              <div className="stat-footer">
                <span className="mini-bars">
                  <i />
                  <i />
                  <i />
                  <i />
                  <i />
                  <i />
                  <i />
                </span>
                <span>Données disponibles</span>
              </div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-icon icon-orange">
                  <AlertTriangle size={19} />
                </span>
              </div>
              <p className="stat-label">Alertes à traiter</p>
              <div className="stat-value">
                {loading ? "…" : formatNumber(alertsToProcess)}
                <span className="stat-unit">alertes</span>
              </div>
              <div className="stat-footer">
                <span className="footer-dot orange-dot" />
                <span>
                  {loading
                    ? "Chargement…"
                    : `${formatNumber(criticalAlerts)} alerte(s) critique(s)`}
                </span>
              </div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-icon icon-green">
                  <ShieldCheck size={19} />
                </span>
              </div>
              <p className="stat-label">Incidents résolus</p>
              <div className="stat-value">
                {loading ? "…" : formatNumber(resolvedThisMonth)}
                <span className="stat-unit">résolus</span>
              </div>
              <div className="stat-footer">
                <span className="footer-dot green-dot" />
                <span>Selon les données disponibles</span>
              </div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-icon icon-purple">
                  <Clock3 size={19} />
                </span>
              </div>
              <p className="stat-label">Temps moyen de réponse</p>
              <div className="stat-value">
                {loading
                  ? "…"
                  : averageResponse === null || averageResponse === undefined
                    ? "—"
                    : formatNumber(averageResponse)}
                <span className="stat-unit">
                  {averageResponse === null || averageResponse === undefined
                    ? ""
                    : typeof averageResponse === "string" &&
                        averageResponse.toLowerCase().includes("min")
                      ? ""
                      : "min"}
                </span>
              </div>
              <div className="stat-footer">
                <span className="footer-dot purple-dot" />
                <span>Statistique fournie par l'API</span>
              </div>
            </article>
          </section>

          <section className="middle-grid">
            <article className="panel chart-panel">
              <div className="panel-header">
                <div>
                  <h2>Activité des alertes</h2>
                  <p>Volume détecté et alertes traitées</p>
                </div>

                <button
                  className="select-button"
                  onClick={loadData}
                  disabled={loading}
                >
                  Actualiser <ChevronDown size={14} />
                </button>
              </div>

              <div className="chart-legend">
                <span>
                  <i className="legend-blue" /> Alertes détectées
                </span>
                <span>
                  <i className="legend-teal" /> Alertes traitées
                </span>
              </div>

              <div className="chart-wrap">
                {trendData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={trendData}
                      margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="alertFill"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#6597ff"
                            stopOpacity={0.2}
                          />
                          <stop
                            offset="100%"
                            stopColor="#6597ff"
                            stopOpacity={0}
                          />
                        </linearGradient>

                        <linearGradient
                          id="resolvedFill"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#35c6ad"
                            stopOpacity={0.15}
                          />
                          <stop
                            offset="100%"
                            stopColor="#35c6ad"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>

                      <CartesianGrid
                        stroke="#263245"
                        strokeDasharray="3 5"
                        vertical={false}
                      />

                      <XAxis
                        dataKey="day"
                        tick={{ fill: "#8290a5", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        dy={10}
                      />

                      <YAxis
                        tick={{ fill: "#8290a5", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />

                      <Tooltip
                        contentStyle={{
                          background: "#172235",
                          border: "1px solid #2c3b52",
                          borderRadius: 10,
                          color: "#edf3fc",
                          fontSize: 12,
                        }}
                      />

                      <Area
                        type="monotone"
                        dataKey="alerts"
                        name="Détectées"
                        stroke="#6d9cff"
                        strokeWidth={2.5}
                        fill="url(#alertFill)"
                      />

                      <Area
                        type="monotone"
                        dataKey="resolved"
                        name="Traitées"
                        stroke="#35c6ad"
                        strokeWidth={2.5}
                        fill="url(#resolvedFill)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div
                    className="empty-state"
                    style={{
                      height: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "20px",
                    }}
                  >
                    {loading
                      ? "Chargement du graphique…"
                      : "Aucune donnée d'activité fournie par l'API."}
                  </div>
                )}
              </div>
            </article>

            <article className="panel severity-panel">
              <div className="panel-header">
                <div>
                  <h2>Répartition par sévérité</h2>
                  <p>Incidents actifs chargés</p>
                </div>

                <button
                  className="icon-button"
                  aria-label="Actualiser la répartition"
                  onClick={loadData}
                  disabled={loading}
                >
                  <Ellipsis size={19} />
                </button>
              </div>

              <div className="severity-total">
                <strong>{loading ? "…" : formatNumber(severityTotal)}</strong>
                <span>incidents actifs</span>
              </div>

              <div className="severity-stack">
                {severityTotal > 0 ? (
                  <>
                    <span
                      className="stack-critical"
                      style={{
                        width: `${(severityCounts.Critique / severityTotal) * 100}%`,
                      }}
                    />
                    <span
                      className="stack-high"
                      style={{
                        width: `${(severityCounts["Élevée"] / severityTotal) * 100}%`,
                      }}
                    />
                    <span
                      className="stack-medium"
                      style={{
                        width: `${(severityCounts.Moyenne / severityTotal) * 100}%`,
                      }}
                    />
                    <span
                      className="stack-low"
                      style={{
                        width: `${(severityCounts.Faible / severityTotal) * 100}%`,
                      }}
                    />
                  </>
                ) : (
                  <span style={{ width: "100%", opacity: 0.2 }} />
                )}
              </div>

              <div className="severity-list">
                <div>
                  <span className="severity-name">
                    <i className="dot-critical" />
                    Critique
                  </span>
                  <strong>
                    {severityCounts.Critique}
                    <small>{severityPercent(severityCounts.Critique)}</small>
                  </strong>
                </div>

                <div>
                  <span className="severity-name">
                    <i className="dot-high" />
                    Élevée
                  </span>
                  <strong>
                    {severityCounts["Élevée"]}
                    <small>{severityPercent(severityCounts["Élevée"])}</small>
                  </strong>
                </div>

                <div>
                  <span className="severity-name">
                    <i className="dot-medium" />
                    Moyenne
                  </span>
                  <strong>
                    {severityCounts.Moyenne}
                    <small>{severityPercent(severityCounts.Moyenne)}</small>
                  </strong>
                </div>

                <div>
                  <span className="severity-name">
                    <i className="dot-low" />
                    Faible
                  </span>
                  <strong>
                    {severityCounts.Faible}
                    <small>{severityPercent(severityCounts.Faible)}</small>
                  </strong>
                </div>
              </div>

              <div className="severity-note">
                <ShieldCheck size={15} />
                <span>
                  {severityCounts.Critique > 0
                    ? `${severityCounts.Critique} incident(s) critique(s) nécessitent une attention immédiate.`
                    : "Aucun incident critique parmi les incidents chargés."}
                </span>
              </div>
            </article>
          </section>

          <section className="panel incidents-panel">
            <div className="panel-header incidents-header">
              <div>
                <div className="title-with-count">
                  <h2>Incidents récents</h2>
                  <span className="table-count">
                    {visibleIncidents.length}
                  </span>
                </div>
                <p>Incidents retournés par le service API</p>
              </div>

              <button
                className="text-button"
                onClick={() => setActivePage("Incidents")}
              >
                Voir tous les incidents <ChevronRight size={15} />
              </button>
            </div>

            <div className="table-toolbar">
              <div className="table-search">
                <Search size={15} />
                <input
                  placeholder="Rechercher un incident..."
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>

              <div className="table-tools">
                <label className="filter-control">
                  <Filter size={14} />
                  <select
                    value={filter}
                    onChange={(event) => setFilter(event.target.value)}
                    aria-label="Filtrer par sévérité"
                  >
                    <option value="Toutes">Toutes</option>
                    <option value="Critique">Critique</option>
                    <option value="Élevée">Élevée</option>
                    <option value="Moyenne">Moyenne</option>
                    <option value="Faible">Faible</option>
                  </select>
                  <ChevronDown size={13} />
                </label>

                <button
                  className="button button-secondary button-small"
                  onClick={handleExport}
                >
                  <Download size={14} />
                  Exporter
                </button>
              </div>
            </div>

            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>INCIDENT</th>
                    <th>SOURCE</th>
                    <th>SÉVÉRITÉ</th>
                    <th>STATUT</th>
                    <th>RESPONSABLE</th>
                    <th>DERNIÈRE ACTIVITÉ</th>
                    <th />
                  </tr>
                </thead>

                <tbody>
                  {visibleIncidents.map((incident) => (
                    <tr key={incident.id}>
                      <td>
                        <div className="incident-title">{incident.title}</div>
                        <div className="incident-id">{incident.id}</div>
                      </td>

                      <td>
                        <span className="source-label">
                          <span className="source-icon">
                            <Command size={13} />
                          </span>
                          {incident.source}
                        </span>
                      </td>

                      <td>
                        <SeverityPill>{incident.severity}</SeverityPill>
                      </td>

                      <td>
                        <StatusPill>{incident.status}</StatusPill>
                      </td>

                      <td>
                        <span className="assignee">
                          <span className="assignee-avatar">
                            {incident.assignee === "Non assigné"
                              ? "—"
                              : String(incident.assignee)
                                  .split(" ")
                                  .map((part) => part[0] ?? "")
                                  .join("")
                                  .slice(0, 2)}
                          </span>
                          {incident.assignee}
                        </span>
                      </td>

                      <td className="time-cell">{incident.time}</td>

                      <td>
                        <button
                          className="row-more"
                          aria-label={`Options ${incident.id}`}
                          onClick={() =>
                            showNotice(
                              `Incident ${incident.id} — ${incident.title}`
                            )
                          }
                        >
                          <Ellipsis size={18} />
                        </button>
                      </td>
                    </tr>
                  ))}

                  {loading && (
                    <tr>
                      <td colSpan="7" className="empty-state">
                        Chargement des incidents…
                      </td>
                    </tr>
                  )}

                  {!loading &&
                    !incidentsError &&
                    visibleIncidents.length === 0 && (
                      <tr>
                        <td colSpan="7" className="empty-state">
                          {incidents.length === 0
                            ? "Aucun incident n'a été retourné par l'API."
                            : "Aucun incident ne correspond à votre recherche."}
                        </td>
                      </tr>
                    )}

                  {!loading && incidentsError && incidents.length === 0 && (
                    <tr>
                      <td colSpan="7" className="empty-state">
                        Les incidents ne peuvent pas être affichés. Vérifie la
                        connexion au backend.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="table-footer">
              <span>
                Affichage de <strong>{visibleIncidents.length}</strong> sur{" "}
                <strong>{incidents.length}</strong> incidents
              </span>

              <div className="pagination">
                <button disabled aria-label="Page précédente">
                  <ChevronLeft size={15} />
                </button>
                <button className="page-current" disabled>
                  1
                </button>
                <button disabled aria-label="Page suivante">
                  <ChevronRight size={15} />
                </button>
              </div>
            </div>
          </section>

          <footer className="page-footer">
            <span>
              FAnalyzer IR <b>•</b> Centre de réponse aux incidents
            </span>
            <span>
              <span className="online-indicator" />
              {loading
                ? "Chargement des services"
                : incidentsError || dashboardError
                  ? "Vérification de la connexion nécessaire"
                  : "État des services chargé"}
            </span>
          </footer>
            </>
          )}
        </div>
      </main>

      {notice && (
        <div className="toast" role="status">
          <span className="toast-check">✓</span>
          {notice}
          <button
            onClick={() => setNotice("")}
            aria-label="Fermer le message"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {showNewIncident && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !creatingIncident) {
              setShowNewIncident(false);
            }
          }}
        >
          <form className="incident-modal" onSubmit={addIncident}>
            <div className="modal-heading">
              <div>
                <span className="modal-icon">
                  <Plus size={18} />
                </span>
                <h2>Créer un incident</h2>
                <p>
                  Les informations seront envoyées au service API.
                </p>
              </div>

              <button
                type="button"
                className="icon-button"
                onClick={() => setShowNewIncident(false)}
                aria-label="Fermer"
                disabled={creatingIncident}
              >
                <X size={18} />
              </button>
            </div>

            <label className="field-label">
              Titre de l'incident
              <input
                name="title"
                required
                placeholder="Ex. : Activité réseau inhabituelle"
                autoFocus
              />
            </label>

            <label className="field-label">
              Source
              <select name="source" defaultValue="Saisie manuelle">
                <option value="Saisie manuelle">Saisie manuelle</option>
                <option value="FortiAnalyzer">FortiAnalyzer</option>
                <option value="FortiGate">FortiGate</option>
              
                
              </select>
            </label>

            <label className="field-label">
              Sévérité
              <select name="severity" defaultValue="Moyenne">
                <option value="Moyenne">Moyenne</option>
                <option value="Faible">Faible</option>
                <option value="Élevée">Élevée</option>
                <option value="Critique">Critique</option>
              </select>
            </label>

            <div className="modal-actions">
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setShowNewIncident(false)}
                disabled={creatingIncident}
              >
                Annuler
              </button>

              <button
                type="submit"
                className="button button-primary"
                disabled={creatingIncident}
              >
                <Plus size={16} />
                {creatingIncident ? "Envoi en cours…" : "Créer l'incident"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export default App;
