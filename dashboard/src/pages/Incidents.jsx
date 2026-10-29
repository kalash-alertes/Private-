import React from "react";
import { useMemo, useState } from "react";
import {
  Search,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Clock3,
  CheckCircle2,
  CircleAlert,
  X,
  UserRound,
  CalendarDays,
  Monitor,
  ArrowUpRight,
} from "lucide-react";

const demoIncidents = [
  {
    id: "INC-2026-001",
    title: "Activité réseau suspecte",
    source: "192.168.1.24",
    destination: "10.0.0.15",
    device: "FortiGate-01",
    severity: "Critique",
    status: "Nouveau",
    analyst: "Non attribué",
    date: "2026-10-28 08:30",
    description:
      "Activité réseau nécessitant une investigation. Les détails réels devront être récupérés depuis FortiAnalyzer.",
  },
  {
    id: "INC-2026-002",
    title: "Tentatives de connexion répétées",
    source: "203.0.113.45",
    destination: "192.168.1.10",
    device: "FortiGate-01",
    severity: "Élevée",
    status: "En cours",
    analyst: "Analyste SOC",
    date: "2026-10-28 07:45",
    description:
      "Plusieurs tentatives de connexion ont été simulées pour tester l'interface.",
  },
  {
    id: "INC-2026-003",
    title: "Trafic sortant inhabituel",
    source: "192.168.1.50",
    destination: "198.51.100.20",
    device: "FortiGate-02",
    severity: "Moyenne",
    status: "En attente",
    analyst: "Non attribué",
    date: "2026-10-27 16:20",
    description:
      "Exemple de dossier de démonstration, sans événement réel associé.",
  },
  {
    id: "INC-2026-004",
    title: "Analyse de trafic terminée",
    source: "192.168.1.12",
    destination: "10.0.0.25",
    device: "FortiGate-02",
    severity: "Faible",
    status: "Résolu",
    analyst: "Analyste SOC",
    date: "2026-10-27 11:10",
    description:
      "Dossier de démonstration utilisé pour tester les filtres et les statuts.",
  },
];

const severityStyles = {
  Critique: { color: "#f87171", background: "rgba(248,113,113,.12)" },
  Élevée: { color: "#fb923c", background: "rgba(251,146,60,.12)" },
  Moyenne: { color: "#facc15", background: "rgba(250,204,21,.12)" },
  Faible: { color: "#4ade80", background: "rgba(74,222,128,.12)" },
};

const statusStyles = {
  Nouveau: { color: "#60a5fa", background: "rgba(96,165,250,.12)" },
  "En cours": { color: "#c084fc", background: "rgba(192,132,252,.12)" },
  "En attente": { color: "#facc15", background: "rgba(250,204,21,.12)" },
  Résolu: { color: "#4ade80", background: "rgba(74,222,128,.12)" },
};

const panelStyle = {
  background: "#111c2e",
  border: "1px solid #26364d",
  borderRadius: 12,
};

const inputStyle = {
  background: "#0b1423",
  border: "1px solid #2b3b51",
  color: "#e5edf8",
  borderRadius: 8,
  padding: "10px 12px",
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
};

function Badge({ value, styles }) {
  const style = styles[value] || {
    color: "#cbd5e1",
    background: "rgba(203,213,225,.1)",
  };

  return (
    <span
      style={{
        color: style.color,
        background: style.background,
        borderRadius: 6,
        padding: "5px 8px",
        fontSize: 12,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {value}
    </span>
  );
}

export default function Incidents() {
  const [incidents, setIncidents] = useState([]);
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("Toutes");
  const [statusFilter, setStatusFilter] = useState("Tous");
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [comments, setComments] = useState({});
  const [newComment, setNewComment] = useState("");
  const [notice, setNotice] = useState("");

  const filteredIncidents = useMemo(() => {
    const term = search.trim().toLowerCase();

    return incidents.filter((incident) => {
      const matchesSearch =
        !term ||
        [
          incident.id,
          incident.title,
          incident.source,
          incident.destination,
          incident.device,
          incident.analyst,
        ].some((value) => value.toLowerCase().includes(term));

      const matchesSeverity =
        severityFilter === "Toutes" ||
        incident.severity === severityFilter;

      const matchesStatus =
        statusFilter === "Tous" || incident.status === statusFilter;

      return matchesSearch && matchesSeverity && matchesStatus;
    });
  }, [incidents, search, severityFilter, statusFilter]);

  const updateIncident = (id, changes) => {
    setIncidents((current) =>
      current.map((incident) =>
        incident.id === id ? { ...incident, ...changes } : incident
      )
    );

    setSelectedIncident((current) =>
      current && current.id === id ? { ...current, ...changes } : current
    );
  };

  const addComment = () => {
    if (!newComment.trim() || !selectedIncident) return;

    const id = selectedIncident.id;
    setComments((current) => ({
      ...current,
      [id]: [
        ...(current[id] || []),
        {
          text: newComment.trim(),
          date: new Date().toLocaleString(),
        },
      ],
    }));

    setNewComment("");
    setNotice("Commentaire ajouté à cette session de démonstration.");
  };

  const selectStyle = { ...inputStyle, cursor: "pointer" };

  const statCards = [
    {
      label: "Total affiché",
      value: incidents.length,
      icon: ShieldAlert,
      color: "#60a5fa",
    },
    {
      label: "Nouveaux",
      value: incidents.filter((i) => i.status === "Nouveau").length,
      icon: CircleAlert,
      color: "#f87171",
    },
    {
      label: "En cours",
      value: incidents.filter((i) => i.status === "En cours").length,
      icon: Clock3,
      color: "#c084fc",
    },
    {
      label: "Résolus",
      value: incidents.filter((i) => i.status === "Résolu").length,
      icon: CheckCircle2,
      color: "#4ade80",
    },
  ];

  return (
    <div style={{ color: "#e5edf8", display: "grid", gap: 22 }}>
      

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ fontSize: 13, color: "#8fa5c1", marginBottom: 7 }}>
            FAnalyzer IR / Investigation
          </div>
          <h1 style={{ fontSize: 27, margin: 0, fontWeight: 700 }}>
            Gestion des incidents
          </h1>
          <p style={{ color: "#8fa5c1", marginBottom: 0, fontSize: 14 }}>
            Investigation, qualification et suivi des incidents de sécurité.
          </p>
        </div>

        <button
          onClick={() => {
            setSearch("");
            setSeverityFilter("Toutes");
            setStatusFilter("Tous");
            setNotice("Filtres réinitialisés.");
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "10px 13px",
            background: "#1a2a40",
            border: "1px solid #30445e",
            color: "#e5edf8",
            borderRadius: 8,
            cursor: "pointer",
          }}
        >
          <RefreshCw size={16} /> Réinitialiser les filtres
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 14,
        }}
      >
        {statCards.map((stat) => {
          const Icon = stat.icon;

          return (
            <div key={stat.label} style={{ ...panelStyle, padding: 18 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span style={{ fontSize: 13, color: "#8fa5c1" }}>
                  {stat.label}
                </span>
                <Icon size={19} color={stat.color} />
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, marginTop: 12 }}>
                {stat.value}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ ...panelStyle, padding: 16 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 12,
          }}
        >
          <div style={{ position: "relative" }}>
            <Search
              size={17}
              color="#8fa5c1"
              style={{
                position: "absolute",
                left: 12,
                top: 12,
              }}
            />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Rechercher un incident, une IP..."
              aria-label="Rechercher un incident"
              style={{ ...inputStyle, paddingLeft: 38 }}
            />
          </div>

          <select
            value={severityFilter}
            onChange={(event) => setSeverityFilter(event.target.value)}
            style={selectStyle}
            aria-label="Filtrer par sévérité"
          >
            <option value="Toutes">Toutes les sévérités</option>
            <option>Critique</option>
            <option>Élevée</option>
            <option>Moyenne</option>
            <option>Faible</option>
          </select>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            style={selectStyle}
            aria-label="Filtrer par statut"
          >
            <option value="Tous">Tous les statuts</option>
            <option>Nouveau</option>
            <option>En cours</option>
            <option>En attente</option>
            <option>Résolu</option>
          </select>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
            flexWrap: "wrap",
            color: "#8fa5c1",
            fontSize: 12,
            marginTop: 13,
          }}
        >
          <span>
            <Filter size={13} style={{ verticalAlign: "middle" }} />{" "}
            {filteredIncidents.length} résultat(s)
          </span>
          <span>Les changements ne sont pas encore enregistrés sur un serveur.</span>
        </div>
      </div>

      {notice && (
        <div
          role="status"
          style={{
            background: "rgba(96,165,250,.1)",
            border: "1px solid rgba(96,165,250,.25)",
            borderRadius: 8,
            padding: 12,
            fontSize: 13,
            color: "#bfdbfe",
          }}
        >
          {notice}
          <button
            onClick={() => setNotice("")}
            aria-label="Fermer le message"
            style={{
              float: "right",
              background: "transparent",
              border: 0,
              color: "inherit",
              cursor: "pointer",
            }}
          >
            <X size={15} />
          </button>
        </div>
      )}

      <div style={{ ...panelStyle, overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            textAlign: "left",
            minWidth: 850,
          }}
        >
          <thead>
            <tr style={{ background: "#17243a", color: "#91a7c2" }}>
              {[
                "INCIDENT",
                "SOURCE → DESTINATION",
                "SÉVÉRITÉ",
                "STATUT",
                "DATE",
                "",
              ].map((heading) => (
                <th
                  key={heading}
                  style={{
                    padding: "14px 15px",
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: ".04em",
                  }}
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredIncidents.map((incident) => (
              <tr
                key={incident.id}
                onClick={() => {
                  setSelectedIncident(incident);
                  setNewComment("");
                }}
                style={{
                  borderTop: "1px solid #26364d",
                  cursor: "pointer",
                }}
                onMouseEnter={(event) => {
                  event.currentTarget.style.background = "#17243a";
                }}
                onMouseLeave={(event) => {
                  event.currentTarget.style.background = "transparent";
                }}
              >
                <td style={{ padding: 15 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {incident.title}
                  </div>
                  <div
                    style={{
                      color: "#7890ad",
                      fontSize: 11,
                      marginTop: 5,
                    }}
                  >
                    {incident.id} · {incident.device}
                  </div>
                </td>
                <td style={{ padding: 15, fontSize: 12 }}>
                  <div>{incident.source}</div>
                  <div style={{ color: "#7890ad", marginTop: 5 }}>
                    → {incident.destination}
                  </div>
                </td>
                <td style={{ padding: 15 }}>
                  <Badge value={incident.severity} styles={severityStyles} />
                </td>
                <td style={{ padding: 15 }}>
                  <Badge value={incident.status} styles={statusStyles} />
                </td>
                <td
                  style={{
                    padding: 15,
                    fontSize: 12,
                    color: "#a5b4c8",
                    whiteSpace: "nowrap",
                  }}
                >
                  {incident.date}
                </td>
                <td style={{ padding: 15 }}>
                  <ChevronRight size={17} color="#7890ad" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredIncidents.length === 0 && (
          <div
            style={{
              textAlign: "center",
              padding: 40,
              color: "#8fa5c1",
            }}
          >
            Aucun résultat. Essaie de modifier les filtres.
          </div>
        )}
      </div>

      {selectedIncident && (
        <div
          onClick={() => setSelectedIncident(null)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "rgba(2,8,18,.75)",
            display: "flex",
            justifyContent: "flex-end",
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Fiche détaillée de l'incident"
            onClick={(event) => event.stopPropagation()}
            style={{
              width: "min(560px, 100%)",
              height: "100%",
              overflowY: "auto",
              background: "#0f1a2b",
              borderLeft: "1px solid #30445e",
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
              <span style={{ color: "#8fa5c1", fontSize: 12 }}>
                {selectedIncident.id}
              </span>
              <button
                onClick={() => setSelectedIncident(null)}
                aria-label="Fermer la fiche"
                style={{
                  background: "#1a2a40",
                  border: "1px solid #30445e",
                  color: "#e5edf8",
                  borderRadius: 8,
                  padding: 8,
                  cursor: "pointer",
                }}
              >
                <X size={18} />
              </button>
            </div>

            <h2 style={{ fontSize: 23, margin: "18px 0 12px" }}>
              {selectedIncident.title}
            </h2>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Badge value={selectedIncident.severity} styles={severityStyles} />
              <Badge value={selectedIncident.status} styles={statusStyles} />
            </div>

            <p
              style={{
                color: "#a5b4c8",
                lineHeight: 1.7,
                fontSize: 14,
                marginTop: 18,
              }}
            >
              {selectedIncident.description}
            </p>

            <h3 style={{ fontSize: 15, marginTop: 28 }}>Informations techniques</h3>
            {[
              ["Équipement", selectedIncident.device, Monitor],
              ["Adresse source", selectedIncident.source, ArrowUpRight],
              ["Adresse destination", selectedIncident.destination, ArrowUpRight],
              ["Date de détection", selectedIncident.date, CalendarDays],
            ].map(([label, value, Icon]) => (
              <div
                key={label}
                style={{
                  display: "flex",
                  gap: 12,
                  padding: "13px 0",
                  borderBottom: "1px solid #26364d",
                  alignItems: "center",
                }}
              >
                <Icon size={17} color="#8fa5c1" />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 11, color: "#8fa5c1" }}>{label}</div>
                  <div style={{ fontSize: 13, marginTop: 4 }}>{value}</div>
                </div>
              </div>
            ))}

            <h3 style={{ fontSize: 15, marginTop: 26 }}>Suivi de l'incident</h3>

            <label style={{ display: "block", fontSize: 12, marginBottom: 7 }}>
              Statut
            </label>
            <select
              value={selectedIncident.status}
              onChange={(event) =>
                updateIncident(selectedIncident.id, {
                  status: event.target.value,
                })
              }
              style={{ ...selectStyle, marginBottom: 16 }}
            >
              <option>Nouveau</option>
              <option>En cours</option>
              <option>En attente</option>
              <option>Résolu</option>
            </select>

            <label style={{ display: "block", fontSize: 12, marginBottom: 7 }}>
              Sévérité de traitement
            </label>
            <select
              value={selectedIncident.severity}
              onChange={(event) =>
                updateIncident(selectedIncident.id, {
                  severity: event.target.value,
                })
              }
              style={{ ...selectStyle, marginBottom: 16 }}
            >
              <option>Critique</option>
              <option>Élevée</option>
              <option>Moyenne</option>
              <option>Faible</option>
            </select>

            <label style={{ display: "block", fontSize: 12, marginBottom: 7 }}>
              Analyste assigné
            </label>
            <select
              value={selectedIncident.analyst}
              onChange={(event) =>
                updateIncident(selectedIncident.id, {
                  analyst: event.target.value,
                })
              }
              style={{ ...selectStyle, marginBottom: 22 }}
            >
              <option>Non attribué</option>
              <option>Analyste SOC</option>
              <option>Analyste niveau 2</option>
              <option>Administrateur sécurité</option>
            </select>

            <h3 style={{ fontSize: 15 }}>Commentaires</h3>
            {(comments[selectedIncident.id] || []).map((comment, index) => (
              <div
                key={index}
                style={{
                  background: "#17243a",
                  padding: 12,
                  borderRadius: 8,
                  marginBottom: 8,
                }}
              >
                <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                  {comment.text}
                </div>
                <div
                  style={{
                    color: "#8fa5c1",
                    fontSize: 11,
                    marginTop: 7,
                  }}
                >
                  {comment.date}
                </div>
              </div>
            ))}

            <textarea
              value={newComment}
              onChange={(event) => setNewComment(event.target.value)}
              placeholder="Ajouter un commentaire d'investigation..."
              rows={3}
              style={{
                ...inputStyle,
                resize: "vertical",
                fontFamily: "inherit",
                marginTop: 8,
              }}
            />

            <button
              onClick={addComment}
              disabled={!newComment.trim()}
              style={{
                marginTop: 10,
                padding: "11px 14px",
                background: "#2563eb",
                border: 0,
                borderRadius: 8,
                color: "white",
                fontWeight: 600,
                cursor: "pointer",
                opacity: newComment.trim() ? 1 : 0.5,
              }}
            >
              Ajouter le commentaire
            </button>

            <p
              style={{
                color: "#7890ad",
                fontSize: 11,
                lineHeight: 1.6,
                marginTop: 16,
              }}
            >
              Les modifications et commentaires sont conservés uniquement en
              mémoire pendant cette session. Ils ne sont pas encore enregistrés
              dans une base de données.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
