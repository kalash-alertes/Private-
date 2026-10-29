
import React, { useState } from "react";
import { Plus, Search, Users, X, ShieldCheck } from "lucide-react";

function UsersPage() {
  const [users, setUsers] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState("");

  const [form, setForm] = useState({
    name: "",
    username: "",
    email: "",
    activation: "En attente",
  });

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  function handleSubmit(event) {
    event.preventDefault();

    const newUser = {
      id: `${Date.now()}`,
      ...form,
    };

    // Prototype uniquement : le compte n'est pas encore
    // enregistré dans le backend.
    setUsers((previous) => [...previous, newUser]);

    setForm({
      name: "",
      username: "",
      email: "",
      activation: "En attente",
    });

    setShowForm(false);
    setNotice(
      "Utilisateur ajouté à cette maquette. Il ne pourra pas encore se connecter : le backend doit être configuré."
    );
  }

  const visibleUsers = users.filter((user) =>
    `${user.name} ${user.username} ${user.email}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  return (
    <section className="users-page">
      <div className="users-toolbar">
        <div className="users-search">
          <Search size={16} />
          <input
            type="search"
            placeholder="Rechercher un utilisateur..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>

        <button
          className="button button-primary"
          onClick={() => {
            setNotice("");
            setShowForm(true);
          }}
        >
          <Plus size={17} />
          Ajouter un administrateur
        </button>
      </div>

      <div className="users-info">
        <ShieldCheck size={18} />
        <div>
          <strong>Gestion des utilisateurs</strong>
          <p>
            Maquette en cours : les comptes affichés ici ne sont
            pas encore enregistrés sur le serveur.
          </p>
        </div>
      </div>

      <div className="users-table-wrap">
        <table className="users-table">
          <thead>
            <tr>
              <th>NOM</th>
              <th>NOM D’UTILISATEUR</th>
              <th>ADRESSE E-MAIL</th>
              <th>ACTIVATION DU COMPTE</th>
            </tr>
          </thead>

          <tbody>
            {visibleUsers.map((user) => (
              <tr key={user.id}>
                <td>{user.name}</td>
                <td>{user.username}</td>
                <td>{user.email}</td>
                <td>
                  <span
                    className={`user-status ${
                      user.activation === "Actif"
                        ? "user-status-active"
                        : "user-status-pending"
                    }`}
                  >
                    {user.activation}
                  </span>
                </td>
              </tr>
            ))}

            {visibleUsers.length === 0 && (
              <tr>
                <td colSpan="4" className="users-empty">
                  {search
                    ? "Aucun utilisateur trouvé."
                    : "Aucun utilisateur ajouté dans cette maquette."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {notice && (
        <div className="users-notice" role="status">
          <span>{notice}</span>
          <button
            type="button"
            onClick={() => setNotice("")}
            aria-label="Fermer le message"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {showForm && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setShowForm(false);
            }
          }}
        >
          <form className="user-modal" onSubmit={handleSubmit}>
            <div className="user-modal-heading">
              <div>
                <span className="modal-icon">
                  <Users size={18} />
                </span>
                <h2>Ajouter un administrateur</h2>
                <p>Renseigne les informations du nouvel utilisateur.</p>
              </div>

              <button
                type="button"
                className="icon-button"
                onClick={() => setShowForm(false)}
                aria-label="Fermer"
              >
                <X size={18} />
              </button>
            </div>

            <label className="field-label">
              Nom
              <input
                name="name"
                value={form.name}
                onChange={handleChange}
                placeholder="Nom complet"
                required
              />
            </label>

            <label className="field-label">
              Nom d’utilisateur
              <input
                name="username"
                value={form.username}
                onChange={handleChange}
                placeholder="Ex. : jdupont"
                autoComplete="off"
                required
              />
            </label>

            <label className="field-label">
              Adresse e-mail
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                placeholder="nom@entreprise.com"
                autoComplete="email"
                required
              />
            </label>

            <label className="field-label">
              Activation du compte
              <select
                name="activation"
                value={form.activation}
                onChange={handleChange}
              >
                <option value="En attente">En attente</option>
                <option value="Actif">Actif</option>
              </select>
            </label>

            <div className="user-modal-note">
              Le mot de passe et l’accès à l’application seront
              configurés lorsque l’authentification du backend sera prête.
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setShowForm(false)}
              >
                Annuler
              </button>

              <button
                type="submit"
                className="button button-primary"
              >
                <Plus size={16} />
                Ajouter
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}

export default UsersPage;
