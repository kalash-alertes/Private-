// Page « Logs bruts » : ajoute en tête de liste les messages arrivés depuis le dernier passage, toutes les
// REFRESH_INTERVAL_MILLISECONDS, et met à jour le bilan par niveau. Le HTML vient du serveur (fragment Jinja2,
// texte des logs échappé) : ce script ne fabrique aucun contenu à partir des logs.
// Les lignes dépliées restent dépliées : seules de nouvelles lignes sont insérées au-dessus.
(function () {
  "use strict";

  const REFRESH_INTERVAL_MILLISECONDS = 3000;
  // Au-delà, les lignes les plus anciennes sont retirées de la page (le navigateur resterait fluide).
  const MAXIMUM_ENTRIES_DISPLAYED = 500;
  const NEW_ENTRY_HIGHLIGHT_MILLISECONDS = 2500;

  const entriesContainer = document.getElementById("raw-feed-entries");
  const statisticsContainer = document.getElementById("raw-feed-statistics");
  const pauseButton = document.getElementById("raw-feed-pause-button");
  const liveState = document.getElementById("raw-feed-live-state");
  const emptyMessage = document.getElementById("raw-feed-empty");
  if (!entriesContainer) {
    return;
  }

  let lastNumber = Number(entriesContainer.dataset.lastNumber || 0);
  let isPaused = false;
  let isRequestInProgress = false;

  function buildUpdateUrl() {
    const updateUrl = new URL(entriesContainer.dataset.updateUrl, window.location.origin);
    updateUrl.searchParams.set("apres", String(lastNumber));
    return updateUrl;
  }

  function showLiveState(label, cssModifier) {
    liveState.lastChild.textContent = label;
    liveState.className = "raw-feed-live-state " + (cssModifier || "");
  }

  async function fetchNewMessages() {
    if (isPaused || isRequestInProgress || document.hidden) {
      return;
    }
    isRequestInProgress = true;
    try {
      const response = await fetch(buildUpdateUrl(), { headers: { Accept: "text/html" } });
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      const fragment = new DOMParser().parseFromString(await response.text(), "text/html");
      const updateRoot = fragment.querySelector("[data-last-number]");
      lastNumber = Number(updateRoot.dataset.lastNumber || lastNumber);
      const newEntries = Array.from(fragment.querySelector('template[data-role="entries"]').content.children);
      // Si l'analyste lit (liste défilée ou ligne dépliée), les nouvelles lignes ne doivent pas déplacer ce qu'il lit :
      // on compense la hauteur ajoutée en tête.
      const isReading = entriesContainer.scrollTop > 0 || entriesContainer.querySelector("details[open]") !== null;
      const heightBeforeInsertion = entriesContainer.scrollHeight;
      // Le serveur renvoie le plus récent d'abord : insérer dans l'ordre inverse garde ce tri en tête de liste.
      for (const newEntry of newEntries.reverse()) {
        newEntry.classList.add("raw-log-new");
        entriesContainer.prepend(newEntry);
        window.setTimeout(() => newEntry.classList.remove("raw-log-new"), NEW_ENTRY_HIGHLIGHT_MILLISECONDS);
      }
      if (isReading) {
        entriesContainer.scrollTop += entriesContainer.scrollHeight - heightBeforeInsertion;
      }
      // Retire les plus anciennes lignes, sauf celles que l'analyste a dépliées.
      const closedEntries = Array.from(entriesContainer.querySelectorAll("details:not([open])"));
      let excessCount = entriesContainer.children.length - MAXIMUM_ENTRIES_DISPLAYED;
      while (excessCount > 0 && closedEntries.length > 0) {
        closedEntries.pop().remove();
        excessCount -= 1;
      }
      emptyMessage.hidden = entriesContainer.children.length > 0;
      statisticsContainer.replaceChildren(
        ...fragment.querySelector('template[data-role="statistics"]').content.childNodes
      );
      showLiveState("En direct", "");
    } catch (fetchError) {
      showLiveState("Connexion perdue, nouvel essai...", "raw-feed-live-error");
    } finally {
      isRequestInProgress = false;
    }
  }

  pauseButton.addEventListener("click", () => {
    isPaused = !isPaused;
    pauseButton.textContent = isPaused ? "Reprendre" : "Pause";
    showLiveState(isPaused ? "En pause" : "En direct", isPaused ? "raw-feed-live-paused" : "");
    if (!isPaused) {
      fetchNewMessages();
    }
  });

  window.setInterval(fetchNewMessages, REFRESH_INTERVAL_MILLISECONDS);
})();
