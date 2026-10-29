# Dashboard — prototype React inspiré de DFIR-IRIS

Interface de démonstration en React + Vite : navigation latérale, indicateurs SOC, graphique d'alertes, répartition des sévérités, tableau filtrable et création locale d'incidents.

## Prérequis
- Node.js 18 ou plus récent
- npm

## Installation et lancement

```bash
cd dashboard
npm install
npm run dev
```

Vite affiche une URL locale, généralement `http://localhost:5173`.

Pour vérifier la compilation de production :

```bash
npm run build
npm run preview
```

## Fichiers
- `src/main.jsx` : point d'entrée React.
- `src/App.jsx` : interface, données de démonstration, recherche, filtres et formulaire.
- `src/styles.css` : thème sombre responsive.
- `index.html` : page HTML initiale.
- `package.json` : dépendances et commandes.

## Fonctionnalités du prototype
- Navigation de la barre latérale.
- Recherche sur les incidents et filtrage par sévérité.
- Création d'un incident de démonstration via « Nouvel incident ».
- Graphique des alertes et répartition des sévérités.
- Toasts d'information et mise en page adaptée au mobile.

## Limites importantes
Ce projet reproduit une **interface inspirée** des workflows DFIR-IRIS, et non un clone exact de la plateforme. Les données sont simulées et restent dans l'état React : aucun serveur, authentification, base de données, audit trail ou API IRIS n'est connecté. Pour un usage réel, ajoutez un backend sécurisé et intégrez l'API officielle DFIR-IRIS. N'utilisez pas de données d'incident réelles dans cette maquette.

Documentation officielle : https://docs.dfir-iris.org/latest/
