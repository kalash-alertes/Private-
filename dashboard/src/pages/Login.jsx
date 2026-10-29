
import React, { useState } from "react";
import {
  Shield,
  UserRound,
  LockKeyhole,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";

function Login({ onLogin, error = "", loading = false }) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  function handleSubmit(event) {
    event.preventDefault();

    if (!identifier.trim() || !password) return;

    onLogin({
      identifier: identifier.trim(),
      password,
    });
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-brand">
          <div className="login-brand-icon">
            <Shield size={27} />
          </div>

          <div>
            <h1>FAnalyzer IR<span>·</span></h1>
            <p>INCIDENT RESPONSE</p>
          </div>
        </div>

        <div className="login-heading">
          <div className="login-heading-icon">
            <ShieldCheck size={22} />
          </div>

          <h2>Bienvenue</h2>
          <p>Connectez-vous pour accéder à votre espace de sécurité.</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            Nom d’utilisateur ou adresse e-mail
            <div className="login-input-wrap">
              <UserRound size={18} />
              <input
                type="text"
                value={identifier}
                onChange={(event) => setIdentifier(event.target.value)}
                placeholder="Votre identifiant"
                autoComplete="username"
                required
                autoFocus
              />
            </div>
          </label>

          <label>
            Mot de passe
            <div className="login-input-wrap">
              <LockKeyhole size={18} />
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Votre mot de passe"
                autoComplete="current-password"
                required
              />

              <button
                type="button"
                className="login-password-toggle"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={
                  showPassword
                    ? "Masquer le mot de passe"
                    : "Afficher le mot de passe"
                }
              >
                {showPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>
          </label>

          {error && (
            <div className="login-error" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="login-submit"
            disabled={loading}
          >
            {loading ? "Connexion en cours..." : "Se connecter"}
            {!loading && <ArrowRight size={18} />}
          </button>
        </form>

        <div className="login-footer">
          <LockKeyhole size={14} />
          <span>Accès réservé aux utilisateurs autorisés</span>
        </div>
      </section>

      <p className="login-copyright">
        FAnalyzer IR · Centre de réponse aux incidents
      </p>
    </main>
  );
}

export default Login;
