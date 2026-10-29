
import React, { useEffect, useState } from "react";
import {
  Plus,
  Search,
  Workflow,
  Trash2,
  Save,
  X,
  ShieldCheck,
} from "lucide-react";

const STORAGE_KEY = "fanalyzer-ir-playbooks";

const emptyStep = () => ({
  id: crypto.randomUUID(),
  name: "",
  type: "Analyse",
  instructions: "",
});

const emptyPlaybook = () => ({
  name: "",
  description: "",
  category: "Analyse et investigation",
  priority: "Moyenne",
  trigger: "Manuel",
  steps: [emptyStep()],
});

export default function Playbooks() {
  const [playbooks, setPlaybooks] = useState([]);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState(emptyPlaybook);
  const [message, setMessage] = useState("");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        setPlaybooks(JSON.parse(saved));
      }
    } catch {
      setMessage("Impossible de lire les brouillons locaux.");
    }
  }, []);

  function updateDraft(field, value) {
    setDraft((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateStep(id, field, value) {
    setDraft((current) => ({
      ...current,
      steps: current.steps.map((step) =>
        step.id === id ? { ...step, [field]: value } : step
      ),
    }));
  }

  function addStep() {
    setDraft((current) => ({
      ...current,
      steps: [...current.steps, emptyStep()],
    }));
  }

  function removeStep(id) {
    setDraft((current) => ({
      ...current,
      steps: current.steps.filter((step) => step.id !== id),
    }));
  }

  function savePlaybook(event) {
    event.preventDefault();

    if (!draft.name.trim()) {
      setMessage("Le nom du playbook est obligatoire.");
      return;
    }

    if (draft.steps.some((step) => !step.name.trim())) {
      setMessage("Donne un nom à chaque étape avant l'enregistrement.");
      return;
    }

    const savedPlaybook = {
      ...draft,
      id: crypto.randomUUID(),
      status: "Brouillon",
      createdAt: new Date().toISOString(),
    };

    const updated = [...playbooks, savedPlaybook];

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      setPlaybooks(updated);
      setDraft(emptyPlaybook());
      setCreating(false);
      setMessage("Brouillon enregistré sur cet appareil.");
    } catch {
      setMessage("Enregistrement impossible dans le stockage local.");
    }
  }

  const filtered = playbooks.filter((playbook) =>
    `${playbook.name} ${playbook.description} ${playbook.category}`
      .toLowerCase()
      .includes(search.trim().toLowerCase())
  );

  return (
    <section className="playbooks-page">
      <div className="playbooks-header">
        <div>
          <h2>Bibliothèque de playbooks</h2>
          <p>
            Crée et organise tes procédures de réponse aux incidents.
          </p>
        </div>

        <button
          className="button button-primary"
          onClick={() => {
            setDraft(emptyPlaybook());
            setCreating(true);
            setMessage("");
          }}
        >
          <Plus size={17} />
          Nouveau playbook
        </button>
      </div>

      <div className="playbooks-notice">
        <ShieldCheck size={19} />
        <div>
          <strong>Mode local</strong>
          <p>
            Les brouillons sont conservés dans ce navigateur.
            Aucune connexion à FortiAnalyzer ni exécution réelle
            n'est effectuée par cette page.
          </p>
        </div>
      </div>

      <div className="playbooks-search">
        <Search size={17} />
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Rechercher un playbook..."
          aria-label="Rechercher un playbook"
        />
      </div>

      {message && (
        <p role="status" className="playbooks-message">
          {message}
        </p>
      )}

      {creating && (
        <form className="playbook-form" onSubmit={savePlaybook}>
          <div className="playbook-form-header">
            <h3>Créer un playbook</h3>
            <button
              type="button"
              className="icon-button"
              onClick={() => setCreating(false)}
              aria-label="Fermer le formulaire"
            >
              <X size={18} />
            </button>
          </div>

          <label>
            Nom *
            <input
              value={draft.name}
              onChange={(event) => updateDraft("name", event.target.value)}
              placeholder="Ex. : Investigation d'une IP suspecte"
              required
            />
          </label>

          <label>
            Description
            <textarea
              value={draft.description}
              onChange={(event) =>
                updateDraft("description", event.target.value)
              }
              placeholder="Objectif de la procédure..."
              rows={3}
            />
          </label>

          <div className="playbook-form-grid">
            <label>
              Catégorie
              <select
                value={draft.category}
                onChange={(event) =>
                  updateDraft("category", event.target.value)
                }
              >
                <option>Analyse et investigation</option>
                <option>Phishing</option>
                <option>Réseau</option>
                <option>Malware</option>
                <option>Collecte de preuves</option>
              </select>
            </label>

            <label>
              Priorité
              <select
                value={draft.priority}
                onChange={(event) =>
                  updateDraft("priority", event.target.value)
                }
              >
                <option>Faible</option>
                <option>Moyenne</option>
                <option>Élevée</option>
                <option>Critique</option>
              </select>
            </label>
          </div>

          <label>
            Déclenchement
            <select
              value={draft.trigger}
              onChange={(event) =>
                updateDraft("trigger", event.target.value)
              }
            >
              <option value="Manuel">Manuel</option>
              <option value="Incident">Depuis un incident</option>
              <option value="Automatique">
                Automatique — intégration future
              </option>
            </select>
          </label>

          <div className="playbook-steps-heading">
            <h3>Étapes de la procédure</h3>
            <button type="button" className="button button-secondary" onClick={addStep}>
              <Plus size={15} />
              Ajouter une étape
            </button>
          </div>

          {draft.steps.map((step, index) => (
            <div className="playbook-step" key={step.id}>
              <div className="playbook-step-heading">
                <strong>Étape {index + 1}</strong>
                {draft.steps.length > 1 && (
                  <button
                    type="button"
                    className="icon-button"
                    onClick={() => removeStep(step.id)}
                    aria-label={`Supprimer l'étape ${index + 1}`}
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>

              <label>
                Nom de l'étape *
                <input
                  value={step.name}
                  onChange={(event) =>
                    updateStep(step.id, "name", event.target.value)
                  }
                  placeholder="Ex. : Analyser les journaux réseau"
                  required
                />
              </label>

              <label>
                Type
                <select
                  value={step.type}
                  onChange={(event) =>
                    updateStep(step.id, "type", event.target.value)
                  }
                >
                  <option>Analyse</option>
                  <option>Collecte d'informations</option>
                  <option>Validation humaine</option>
                  <option>Remédiation</option>
                  <option>Notification</option>
                </select>
              </label>

              <label>
                Instructions
                <textarea
                  value={step.instructions}
                  onChange={(event) =>
                    updateStep(step.id, "instructions", event.target.value)
                  }
                  placeholder="Décris ce qui doit être fait..."
                  rows={2}
                />
              </label>
            </div>
          ))}

          <div className="playbook-form-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setCreating(false)}
            >
              Annuler
            </button>
            <button type="submit" className="button button-primary">
              <Save size={16} />
              Enregistrer le brouillon
            </button>
          </div>
        </form>
      )}

      <div className="playbooks-grid">
        {filtered.map((playbook) => (
          <article className="playbook-card" key={playbook.id}>
            <div className="playbook-card-icon">
              <Workflow size={22} />
            </div>
            <span className="playbook-status">{playbook.status}</span>
            <h3>{playbook.name}</h3>
            <p>
              {playbook.description || "Aucune description renseignée."}
            </p>
            <div className="playbook-tags">
              <span>{playbook.category}</span>
              <span>{playbook.priority}</span>
            </div>
            <small>{playbook.steps.length} étape(s)</small>
          </article>
        ))}

        {filtered.length === 0 && !creating && (
          <div className="playbooks-empty">
            <Workflow size={30} />
            <h3>Aucun playbook enregistré</h3>
            <p>
              Crée ton premier brouillon pour commencer à définir
              une procédure de réponse aux incidents.
            </p>
            <button
              className="button button-primary"
              onClick={() => setCreating(true)}
            >
              <Plus size={16} />
              Créer mon premier playbook
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
