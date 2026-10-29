import { useMemo, useState } from "react";
import {
  Activity,
  Clock3,
  FileText,
  Filter,
  Gauge,
  Search,
  Server,
  ShieldCheck,
  X,
} from "lucide-react";
import { parseFortiAnalyzerLog } from "../utils/fortiLogParser";
import { sampleFortiLogs } from "../data/sampleFortiLogs";

const colors = {
  panel: "#111d2e",
  border: "#263349",
  text: "#e7edf7",
  muted: "#8391a7",
  blue: "#83adff",
  green: "#54d4b3",
  orange: "#ffb76b",
};

const logs = sampleFortiLogs.map(parseFortiAnalyzerLog);

function formatDate(value) {
  if (!value) return "Date inconnue";
  const parsed = new Date(value.replace(" ", "T"));
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(parsed);
}

function Metric({ label, value, suffix = "%", icon: Icon = Gauge, color = colors.blue }) {
  return (
    <article className="log-metric-card">
      <div className="log-metric-heading">
        <span>{label}</span>
        <Icon size={16} color={color} />
      </div>
      <strong>{value ?? "—"}<small>{value === null ? "" : suffix}</small></strong>
    </article>
  );
}

export default function Logs() {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("Tous les types");
  const [selected, setSelected] = useState(null);

  const visibleLogs = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return logs.filter((log) => {
      const matchesType = typeFilter === "Tous les types" || log.category === typeFilter;
      const searchable = [log.id, log.category, log.device, log.level, log.message, log.raw]
        .join(" ")
        .toLowerCase();
      return matchesType && searchable.includes(normalizedQuery);
    });
  }, [query, typeFilter]);

  return (
    <div className="logs-page">
      <section className="logs-intro">
        <div>
          <div className="logs-eyebrow"><Activity size={14} /> COLLECTE ET ANALYSE</div>
          <h2>Journaux FortiAnalyzer</h2>
          <p>Lecture structurée des logs système et des événements d’administration.</p>
        </div>
        <span className="logs-demo-badge"><span /> Exemples de démonstration</span>
      </section>

      <section className="logs-summary-grid" aria-label="Résumé des journaux">
        <article className="logs-summary-card">
          <span>Logs affichés</span><strong>{visibleLogs.length}</strong>
          <small>sur {logs.length} exemples chargés</small>
        </article>
        <article className="logs-summary-card">
          <span>Types reconnus</span><strong>2</strong>
          <small>Performance et administration</small>
        </article>
        <article className="logs-summary-card">
          <span>Équipement source</span><strong>FortiAnalyzer</strong>
          <small>FAZVMSTM26009641</small>
        </article>
      </section>

      <section className="panel logs-list-panel">
        <div className="panel-header logs-list-header">
          <div><h2>Liste des journaux</h2><p>Recherchez un message, un équipement ou un identifiant.</p></div>
          <span className="logs-count">{visibleLogs.length} log(s)</span>
        </div>
        <div className="logs-toolbar">
          <label className="logs-search"><Search size={15} />
            <input aria-label="Rechercher dans les journaux" placeholder="Rechercher dans les logs…" value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <label className="logs-filter"><Filter size={14} />
            <select aria-label="Filtrer les journaux par type" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
              <option>Tous les types</option>
              <option>Performance système</option>
              <option>Connexion administrateur</option>
            </select>
          </label>
        </div>

        <div className="table-scroll">
          <table className="logs-table">
            <thead><tr><th>TYPE</th><th>RÉSUMÉ</th><th>NIVEAU</th><th>ÉQUIPEMENT</th><th>DATE</th><th /></tr></thead>
            <tbody>
              {visibleLogs.map((log) => (
                <tr key={log.id}>
                  <td><span className="logs-type"><span className={log.kind === "performance" ? "logs-type-icon performance" : "logs-type-icon admin"}>{log.kind === "performance" ? <Gauge size={14} /> : <ShieldCheck size={14} />}</span>{log.category}</span></td>
                  <td className="logs-message-cell">{log.message}</td>
                  <td><span className="logs-level">{log.level}</span></td>
                  <td>{log.device}</td>
                  <td className="logs-date-cell"><Clock3 size={13} /> {formatDate(log.date)}</td>
                  <td><button className="logs-detail-button" type="button" onClick={() => setSelected(log)}>Détails</button></td>
                </tr>
              ))}
              {visibleLogs.length === 0 && <tr><td colSpan={6} className="logs-empty">Aucun journal ne correspond à votre recherche.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="logs-table-footer">Les exemples sont conservés localement dans l’interface ; aucun log réel n’est encore connecté.</div>
      </section>

      {selected && (
        <div className="log-detail-backdrop" role="presentation" onClick={() => setSelected(null)}>
          <aside className="log-detail-panel" role="dialog" aria-modal="true" aria-label="Détail du journal" onClick={(event) => event.stopPropagation()}>
            <div className="log-detail-heading">
              <div><span className="logs-eyebrow"><FileText size={14} /> DÉTAIL DU JOURNAL</span><h2>{selected.category}</h2></div>
              <button type="button" className="icon-button" aria-label="Fermer" onClick={() => setSelected(null)}><X size={18} /></button>
            </div>
            <p className="log-detail-message">{selected.message || "Aucun message."}</p>

            {selected.kind === "performance" && <>
              <h3 className="log-section-title">Mesures système</h3>
              <div className="log-metrics-grid">
                <Metric label="CPU" value={selected.metrics.cpu} icon={Gauge} color={colors.orange} />
                <Metric label="Mémoire" value={selected.metrics.memory} icon={Activity} color={colors.blue} />
                <Metric label="Disque" value={selected.metrics.disk} icon={Server} color={colors.green} />
                <Metric label="Taux de logs" value={selected.metrics.logsPerSecond} suffix=" /s" icon={Activity} />
                <Metric label="Insertion" value={selected.metrics.insertRate} suffix=" /s" icon={Activity} />
                <Metric label="Messages" value={selected.metrics.messageRate} suffix=" /s" icon={Activity} />
              </div>
              {selected.fields.lograte !== String(selected.metrics.logsPerSecond) && <div className="log-data-note"><strong>Valeurs à vérifier :</strong> le message indique {selected.metrics.logsPerSecond} logs/s, tandis que le champ séparé <code>lograte</code> vaut {selected.fields.lograte ?? "—"}. Les deux valeurs sont conservées telles quelles.</div>}
            </>}

            {selected.kind === "admin" && <>
              <h3 className="log-section-title">Informations de connexion</h3>
              <div className="log-facts-grid">
                <div><span>Utilisateur</span><strong>{selected.fields.user ?? "—"}</strong></div>
                <div><span>Profil</span><strong>{selected.fields.adminprof ?? "—"}</strong></div>
                <div><span>Source</span><strong>{selected.fields.userfrom ?? "—"}</strong></div>
                <div><span>ADOM</span><strong>{selected.fields.adom ?? "—"}</strong></div>
                <div><span>Opération</span><strong>{selected.operation}</strong></div>
                <div><span>Heure</span><strong>{formatDate(selected.date)}</strong></div>
              </div>
            </>}

            <h3 className="log-section-title">Champs extraits</h3>
            <div className="log-fields-grid">{Object.entries(selected.fields).map(([key, value]) => <div key={key}><span>{key}</span><strong>{key === "msg" ? selected.message : value}</strong></div>)}</div>
            <h3 className="log-section-title">Log brut d’origine</h3>
            <pre className="log-raw-block">{selected.raw}</pre>
          </aside>
        </div>
      )}
    </div>
  );
}
