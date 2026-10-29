import React from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Eye,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { api } from "../services/api";

const colors = {
  background: "#0f1725",
  panel: "#172235",
  border: "#29374b",
  text: "#edf3fc",
  muted: "#91a0b6",
  blue: "#6d9cff",
  red: "#ff667a",
  orange: "#ffb454",
  yellow: "#f4d35e",
  green: "#35c6ad",
};

function normalizeAlert(alert, index) {
  return {
    id: alert.id ?? alert.alert_id ?? alert.uuid ?? `AL-${index + 1}`,
    title:
      alert.title ??
      alert.name ??
      alert.message ??
      alert.description ??
      "Alerte sans titre",
    severity: normalizeSeverity(
      alert.severity ?? alert.level ?? alert.priority
    ),
    source:
      alert.source ??
      alert.device_name ??
      alert.hostname ??
      alert.device ??
      "Source inconnue",
    ip:
      alert.src_ip ??
      alert.source_ip ??
      alert.sourceIp ??
      alert.ip ??
      "—",
    status: normalizeStatus(alert.status ?? alert.state),
    date:
      alert.created_at ??
      alert.timestamp ??
      alert.date ??
      alert.time ??
      null,
    raw: alert,
  };
}

function normalizeSeverity(value) {
  const severity = String(value ?? "").toLowerCase();

  if (
    severity.includes("critical") ||
    severity.includes("critique") ||
    severity === "emergency" ||
    severity === "alert"
  ) return "Critique";

  if (
    severity.includes("high") ||
    severity.includes("élevée") ||
    severity.includes("elevee") ||
    severity === "error"
  ) return "Élevée";

  if (
    severity.includes("medium") ||
    severity.includes("moyenne") ||
    severity === "warning"
  ) return "Moyenne";

  if (
    severity.includes("low") ||
    severity.includes("faible") ||
    severity === "info" ||
    severity === "informational"
  ) return "Faible";

  return value ? String(value) : "Inconnue";
}

function normalizeStatus(value) {
  const status = String(value ?? "").toLowerCase();

  if (
    status.includes("resolve") ||
    status.includes("closed") ||
    status.includes("traitée") ||
    status.includes("traitee")
  ) return "Traitée";

  if (
    status.includes("investig") ||
    status.includes("progress") ||
    status.includes("en cours")
  ) return "En cours";

  return "À traiter";
}

function formatDate(value) {
  if (!value) return "Date inconnue";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);

  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

const severityColors = {
  Critique: colors.red,
  Élevée: colors.orange,
  Moyenne: colors.yellow,
  Faible: colors.green,
  Inconnue: colors.muted,
};

const cardStyle = {
  background: colors.panel,
  border: `1px solid ${colors.border}`,
  borderRadius: 12,
  padding: 18,
};

const buttonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 8,
  border: `1px solid ${colors.border}`,
  borderRadius: 8,
  padding: "9px 12px",
  background: "#202e43",
  color: colors.text,
  cursor: "pointer",
  fontSize: 13,
};

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("Toutes");
  const [statusFilter, setStatusFilter] = useState("Tous");
  const [selectedAlert, setSelectedAlert] = useState(null);

  async function loadAlerts() {
    setLoading(true);
    setError("");

    try {
      const response = await api.getAlerts();

      const data = Array.isArray(response)
        ? response
        : response?.results ??
          response?.items ??
          response?.alerts ??
          response?.data?.results ??
          response?.data?.items ??
          response?.data?.alerts ??
          response?.data ??
          [];

      if (!Array.isArray(data)) {
        throw new Error("Le format des données reçues est inattendu.");
      }

      setAlerts(data.map(normalizeAlert));
    } catch (err) {
      setAlerts([]);
      setError(
        "Impossible de charger les alertes. Vérifie que le backend est démarré et que l’API des alertes est accessible."
      );
      console.error("Erreur de chargement des alertes :", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAlerts();
  }, []);

  const visibleAlerts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return alerts.filter((alert) => {
      const matchesSearch = [
        alert.id,
        alert.title,
        alert.source,
        alert.ip,
        alert.severity,
        alert.status,
      ]
        .join(" ")
        .toLowerCase()
        .includes(query);

      const matchesSeverity =
        severityFilter === "Toutes" ||
        alert.severity === severityFilter;

      const matchesStatus =
        statusFilter === "Tous" || alert.status === statusFilter;

      return matchesSearch && matchesSeverity && matchesStatus;
    });
  }, [alerts, search, severityFilter, statusFilter]);

  const criticalCount = alerts.filter(
    (alert) => alert.severity === "Critique"
  ).length;

  const highCount = alerts.filter(
    (alert) => alert.severity === "Élevée"
  ).length;

  const pendingCount = alerts.filter(
    (alert) => alert.status === "À traiter"
  ).length;

  const resolvedCount = alerts.filter(
    (alert) => alert.status === "Traitée"
  ).length;

  const statCards = [
    {
      label: "Total des alertes",
      value: alerts.length,
      icon: Activity,
      color: colors.blue,
    },
    {
      label: "Alertes critiques",
      value: criticalCount,
      icon: ShieldAlert,
      color: colors.red,
    },
    {
      label: "À traiter",
      value: pendingCount,
      icon: Clock3,
      color: colors.orange,
    },
    {
      label: "Traitées",
      value: resolvedCount,
      icon: CheckCircle2,
      color: colors.green,
    },
  ];

  return (
    <div style={{ color: colors.text, display: "grid", gap: 22 }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 14,
        }}
      >
        <div>
          <div
            style={{
              color: colors.blue,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 1.5,
              marginBottom: 8,
            }}
          >
            SURVEILLANCE & DÉTECTION
          </div>
          <h1 style={{ fontSize: 27, margin: 0 }}>Alertes de sécurité</h1>
          <p style={{ color: colors.muted, marginBottom: 0, fontSize: 14 }}>
            Consulte et analyse les événements détectés dans ton environnement.
          </p>
        </div>

        <button
          type="button"
          onClick={loadAlerts}
          disabled={loading}
          style={{ ...buttonStyle, opacity: loading ? 0.6 : 1 }}
        >
          <RefreshCw size={15} />
          {loading ? "Chargement…" : "Actualiser"}
        </button>
      </header>

      {error && (
        <div
          role="alert"
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 10,
            padding: 14,
            borderRadius: 10,
            border: "1px solid #713b48",
            background: "#301f2b",
            color: "#ffb5bf",
            fontSize: 13,
          }}
        >
          <XCircle size={18} style={{ flexShrink: 0 }} />
          <div>
            <strong>Connexion aux alertes impossible</strong>
            <p style={{ margin: "5px 0 0" }}>{error}</p>
          </div>
        </div>
      )}

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
          gap: 14,
        }}
      >
        {statCards.map((card) => {
          const Icon = card.icon;

          return (
            <article key={card.label} style={cardStyle}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <span style={{ color: colors.muted, fontSize: 13 }}>
                  {card.label}
                </span>
                <Icon size={19} color={card.color} />
              </div>
              <div style={{ fontSize: 30, fontWeight: 700, marginTop: 15 }}>
                {loading ? "—" : card.value}
              </div>
              <div
                style={{
                  color: colors.muted,
                  fontSize: 11,
                  marginTop: 5,
                }}
              >
                {loading ? "Chargement des données" : "Données de l’API"}
              </div>
            </article>
          );
        })}
      </section>

      <section style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
        <div
          style={{
            padding: 18,
            borderBottom: `1px solid ${colors.border}`,
          }}
        >
          <h2 style={{ fontSize: 16, margin: 0 }}>Liste des alertes</h2>
          <p style={{ color: colors.muted, fontSize: 12, marginBottom: 0 }}>
            Recherche, filtres et consultation du détail des événements.
          </p>
        </div>

        <div
          style={{
            display: "flex",
            gap: 10,
            flexWrap: "wrap",
            padding: 16,
          }}
        >
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              flex: "1 1 220px",
              minWidth: 0,
              padding: "0 11px",
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              background: "#111c2c",
            }}
          >
            <Search size={16} color={colors.muted} />
            <input
              aria-label="Rechercher une alerte"
              placeholder="Rechercher une alerte, une IP, une source…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              style={{
                width: "100%",
                minWidth: 0,
                padding: "11px 0",
                border: 0,
                outline: 0,
                background: "transparent",
                color: colors.text,
                fontSize: 13,
              }}
            />
          </label>

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              padding: "0 10px",
              color: colors.muted,
            }}
          >
            <Filter size={14} />
            <select
              aria-label="Filtrer par sévérité"
              value={severityFilter}
              onChange={(event) => setSeverityFilter(event.target.value)}
              style={{
                border: 0,
                outline: 0,
                background: colors.panel,
                color: colors.text,
                padding: "10px 0",
              }}
            >
              <option value="Toutes">Toutes les sévérités</option>
              <option value="Critique">Critique</option>
              <option value="Élevée">Élevée</option>
              <option value="Moyenne">Moyenne</option>
              <option value="Faible">Faible</option>
              <option value="Inconnue">Inconnue</option>
            </select>
          </label>

          <select
            aria-label="Filtrer par statut"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            style={{
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              padding: "10px 12px",
              background: colors.panel,
              color: colors.text,
            }}
          >
            <option value="Tous">Tous les statuts</option>
            <option value="À traiter">À traiter</option>
            <option value="En cours">En cours</option>
            <option value="Traitée">Traitée</option>
          </select>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              minWidth: 760,
              borderCollapse: "collapse",
              textAlign: "left",
              fontSize: 12,
            }}
          >
            <thead style={{ background: "#121d2d", color: colors.muted }}>
              <tr>
                {[
                  "ALERTE",
                  "SOURCE",
                  "IP SOURCE",
                  "SÉVÉRITÉ",
                  "STATUT",
                  "DATE",
                  "",
                ].map((heading, index) => (
                  <th
                    key={`${heading}-${index}`}
                    style={{
                      padding: "13px 15px",
                      fontSize: 10,
                      letterSpacing: 0.6,
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {!loading && visibleAlerts.map((alert) => (
                <tr
                  key={alert.id}
                  style={{ borderTop: `1px solid ${colors.border}` }}
                >
                  <td style={{ padding: "15px", maxWidth: 280 }}>
                    <div style={{ fontWeight: 600 }}>{alert.title}</div>
                    <div style={{ color: colors.muted, marginTop: 5 }}>
                      ID : {String(alert.id)}
                    </div>
                  </td>
                  <td style={{ padding: "15px", whiteSpace: "nowrap" }}>
                    {alert.source}
                  </td>
                  <td style={{ padding: "15px", fontFamily: "monospace" }}>
                    {alert.ip}
                  </td>
                  <td style={{ padding: "15px" }}>
                    <span
                      style={{
                        color: severityColors[alert.severity] ?? colors.muted,
                        background: `${severityColors[alert.severity] ?? colors.muted}18`,
                        border: `1px solid ${severityColors[alert.severity] ?? colors.muted}55`,
                        padding: "5px 8px",
                        borderRadius: 6,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {alert.severity}
                    </span>
                  </td>
                  <td style={{ padding: "15px", whiteSpace: "nowrap" }}>
                    {alert.status}
                  </td>
                  <td style={{ padding: "15px", whiteSpace: "nowrap" }}>
                    {formatDate(alert.date)}
                  </td>
                  <td style={{ padding: "15px" }}>
                    <button
                      type="button"
                      aria-label={`Voir les détails de ${alert.title}`}
                      title="Voir les détails"
                      onClick={() => setSelectedAlert(alert)}
                      style={buttonStyle}
                    >
                      <Eye size={15} />
                    </button>
                  </td>
                </tr>
              ))}

              {!loading && visibleAlerts.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    style={{
                      padding: "42px 20px",
                      textAlign: "center",
                      color: colors.muted,
                    }}
                  >
                    {error ? (
                      <>
                        <AlertTriangle
                          size={24}
                          style={{ marginBottom: 10 }}
                        />
                        <div>Les alertes ne sont pas disponibles.</div>
                        <div style={{ marginTop: 5 }}>
                          Vérifie la connexion à l’API puis réessaie.
                        </div>
                      </>
                    ) : (
                      <>
                        <ShieldAlert
                          size={25}
                          style={{ marginBottom: 10 }}
                        />
                        <div>Aucune alerte ne correspond à ta recherche.</div>
                        <div style={{ marginTop: 5 }}>
                          Si le backend renvoie une liste vide, aucune alerte
                          n’est actuellement disponible.
                        </div>
                      </>
                    )}
                  </td>
                </tr>
              )}

              {loading && (
                <tr>
                  <td
                    colSpan={7}
                    style={{
                      padding: 35,
                      textAlign: "center",
                      color: colors.muted,
                    }}
                  >
                    Chargement des alertes…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div
          style={{
            borderTop: `1px solid ${colors.border}`,
            padding: "13px 16px",
            color: colors.muted,
            fontSize: 12,
          }}
        >
          {visibleAlerts.length} alerte(s) affichée(s) sur {alerts.length}
        </div>
      </section>

      {selectedAlert && (
        <div
          role="presentation"
          onClick={() => setSelectedAlert(null)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "#050a12b8",
            display: "flex",
            justifyContent: "flex-end",
          }}
        >
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Détails de l’alerte"
            onClick={(event) => event.stopPropagation()}
            style={{
              width: "min(480px, 100%)",
              height: "100%",
              overflowY: "auto",
              background: colors.background,
              borderLeft: `1px solid ${colors.border}`,
              padding: 24,
              boxSizing: "border-box",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 12,
              }}
            >
              <h2 style={{ fontSize: 19, margin: 0 }}>Détail de l’alerte</h2>
              <button
                type="button"
                onClick={() => setSelectedAlert(null)}
                style={buttonStyle}
              >
                <XCircle size={16} />
                Fermer
              </button>
            </div>

            <h3 style={{ marginTop: 28, fontSize: 17 }}>
              {selectedAlert.title}
            </h3>

            <p style={{ color: colors.muted, fontSize: 12 }}>
              Identifiant : {String(selectedAlert.id)}
            </p>

            {[
              ["Sévérité", selectedAlert.severity],
              ["Statut", selectedAlert.status],
              ["Source", selectedAlert.source],
              ["Adresse IP", selectedAlert.ip],
              ["Date", formatDate(selectedAlert.date)],
            ].map(([label, value]) => (
              <div
                key={label}
                style={{
                  padding: "14px 0",
                  borderBottom: `1px solid ${colors.border}`,
                }}
              >
                <div style={{ color: colors.muted, fontSize: 12 }}>
                  {label}
                </div>
                <div style={{ marginTop: 6, fontSize: 14 }}>{value}</div>
              </div>
            ))}

            <h4 style={{ marginTop: 24 }}>Données reçues de l’API</h4>
            <pre
              style={{
                whiteSpace: "pre-wrap",
                overflowWrap: "anywhere",
                background: "#111c2c",
                border: `1px solid ${colors.border}`,
                borderRadius: 8,
                padding: 12,
                fontSize: 11,
                color: "#cbd7e8",
              }}
            >
              {JSON.stringify(selectedAlert.raw, null, 2)}
            </pre>
          </aside>
        </div>
      )}
    </div>
  );
}
