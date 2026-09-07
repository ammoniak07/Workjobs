"use strict";

let state = {
  config: null,
  jobs: [],       // offres actuellement affichées
  selectedId: null,
  editingSiteIndex: null,
};

function $(id) { return document.getElementById(id); }

// ---------------------------------------------------------------------
// Onglets
// ---------------------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    $("tab-" + btn.dataset.tab).classList.add("active");
  });
});

function showResultsTab() {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
  document.querySelector('.tab-btn[data-tab="results"]').classList.add("active");
  $("tab-results").classList.add("active");
}

// ---------------------------------------------------------------------
// Chargement / sauvegarde de la config
// ---------------------------------------------------------------------
function fillFormFromConfig(config) {
  const r = config.recherche || {};
  $("f-mots-cles").value = r.mots_cles || "";
  $("f-lieu").value = r.lieu || "";
  $("f-type-contrat").value = r.type_contrat || "";
  $("f-max-resultats").value = r.max_resultats_par_source || 20;

  const s = config.sources || {};
  $("f-leforem").checked = !!(s.leforem && s.leforem.active);
  $("f-indeed").checked = !!(s.indeed && s.indeed.active);
  $("f-indeed-domaine").value = (s.indeed && s.indeed.domaine) || "fr.indeed.com";
  $("f-linkedin").checked = !!(s.linkedin && s.linkedin.active);

  const c = config.candidat || {};
  $("f-nom").value = c.nom || "";
  $("f-email").value = c.email || "";
  $("f-telephone").value = c.telephone || "";
  $("f-cv-path").value = c.cv_path || "";
  $("f-motivation").value = c.motivation || "";

  renderCustomSites();
}

function collectConfigFromForm() {
  state.config.recherche = {
    mots_cles: $("f-mots-cles").value.trim(),
    lieu: $("f-lieu").value.trim(),
    type_contrat: $("f-type-contrat").value.trim(),
    max_resultats_par_source: parseInt($("f-max-resultats").value, 10) || 20,
  };
  state.config.sources = {
    leforem: { active: $("f-leforem").checked },
    indeed: {
      active: $("f-indeed").checked,
      domaine: $("f-indeed-domaine").value.trim() || "fr.indeed.com",
    },
    linkedin: { active: $("f-linkedin").checked },
  };
  state.config.candidat = {
    nom: $("f-nom").value.trim(),
    email: $("f-email").value.trim(),
    telephone: $("f-telephone").value.trim(),
    cv_path: $("f-cv-path").value.trim(),
    motivation: $("f-motivation").value.trim(),
  };
  // state.config.sites_personnalises est déjà à jour (muté directement)
  return state.config;
}

async function loadConfig() {
  state.config = await window.pywebview.api.get_config();
  if (!state.config.sites_personnalises) state.config.sites_personnalises = [];
  fillFormFromConfig(state.config);
}

$("btn-save-config").addEventListener("click", async () => {
  const config = collectConfigFromForm();
  await window.pywebview.api.save_config(config);
  $("status-text").textContent = "Configuration enregistrée.";
});

$("btn-browse-cv").addEventListener("click", async () => {
  const path = await window.pywebview.api.browse_cv();
  if (path) $("f-cv-path").value = path;
});

// ---------------------------------------------------------------------
// Sites personnalisés
// ---------------------------------------------------------------------
function renderCustomSites() {
  const tbody = document.querySelector("#custom-sites-table tbody");
  tbody.innerHTML = "";
  (state.config.sites_personnalises || []).forEach((site, index) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(site.nom || "")}</td>
      <td>${site.active === false ? "non" : "oui"}</td>
      <td>${escapeHtml(site.url_recherche || "")}</td>
      <td class="actions-cell">
        <button data-action="edit" data-index="${index}">Modifier</button>
        <button data-action="delete" data-index="${index}">Supprimer</button>
      </td>`;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll("button[data-action='edit']").forEach((b) =>
    b.addEventListener("click", () => openSiteDialog(parseInt(b.dataset.index, 10)))
  );
  tbody.querySelectorAll("button[data-action='delete']").forEach((b) =>
    b.addEventListener("click", () => {
      state.config.sites_personnalises.splice(parseInt(b.dataset.index, 10), 1);
      renderCustomSites();
    })
  );
}

const SITE_FIELD_IDS = {
  nom: "sd-nom",
  url_recherche: "sd-url",
  base_url: "sd-base-url",
  selecteur_carte: "sd-carte",
  selecteur_titre: "sd-titre",
  selecteur_entreprise: "sd-entreprise",
  selecteur_lieu: "sd-lieu",
  selecteur_lien: "sd-lien",
};

function openSiteDialog(index) {
  state.editingSiteIndex = index;
  const site = index === null ? {} : state.config.sites_personnalises[index];
  for (const [key, elId] of Object.entries(SITE_FIELD_IDS)) {
    $(elId).value = (site && site[key]) || "";
  }
  $("sd-active").checked = site ? site.active !== false : true;
  $("site-dialog-title").textContent = index === null ? "Ajouter un site" : "Modifier le site";
  $("site-dialog").classList.remove("hidden");
}

$("btn-add-site").addEventListener("click", () => openSiteDialog(null));
$("sd-cancel").addEventListener("click", () => $("site-dialog").classList.add("hidden"));

$("sd-save").addEventListener("click", () => {
  const nom = $("sd-nom").value.trim();
  const url = $("sd-url").value.trim();
  const carte = $("sd-carte").value.trim();
  if (!nom || !url || !carte) {
    alert("Le nom, l'URL de recherche et le sélecteur CSS d'une offre sont obligatoires.");
    return;
  }
  const site = { active: $("sd-active").checked };
  for (const [key, elId] of Object.entries(SITE_FIELD_IDS)) {
    site[key] = $(elId).value.trim();
  }
  site.selecteur_lien = site.selecteur_lien || "a";

  if (!state.config.sites_personnalises) state.config.sites_personnalises = [];
  if (state.editingSiteIndex === null) {
    state.config.sites_personnalises.push(site);
  } else {
    state.config.sites_personnalises[state.editingSiteIndex] = site;
  }
  renderCustomSites();
  $("site-dialog").classList.add("hidden");
});

// ---------------------------------------------------------------------
// Recherche
// ---------------------------------------------------------------------
$("btn-search").addEventListener("click", async () => {
  const config = collectConfigFromForm();
  await window.pywebview.api.save_config(config);
  $("status-text").textContent = "Recherche en cours...";
  $("btn-search").disabled = true;
  appendLog("--- Nouvelle recherche ---");
  showResultsTab();
  await window.pywebview.api.start_search();
});

function onLog(text) {
  appendLog(text);
}
window.onLog = onLog;

function appendLog(text) {
  const log = $("log");
  log.textContent += text + "\n";
  log.scrollTop = log.scrollHeight;
}

function onSearchDone(jobs) {
  $("btn-search").disabled = false;
  $("status-text").textContent = jobs.length + " nouvelle(s) offre(s) trouvée(s).";
  state.jobs = jobs;
  renderResults();
  if (jobs.length === 0) {
    appendLog("Aucune nouvelle offre correspondant aux critères.");
  }
}
window.onSearchDone = onSearchDone;

function renderResults() {
  const tbody = document.querySelector("#results-table tbody");
  tbody.innerHTML = "";
  state.jobs.forEach((job) => {
    const tr = document.createElement("tr");
    tr.className = "job-row" + (job.id === state.selectedId ? " selected" : "");
    tr.dataset.id = job.id;
    tr.innerHTML = `
      <td>${escapeHtml(job.source)}</td>
      <td>${escapeHtml(job.title)}</td>
      <td>${escapeHtml(job.company || "")}</td>
      <td>${escapeHtml(job.location || "")}</td>
      <td class="actions-cell">
        <button data-action="draft">Brouillon</button>
        <button data-action="skip">Ignorer</button>
      </td>`;
    tr.addEventListener("click", (e) => {
      if (e.target.tagName === "BUTTON") return;
      selectJob(job.id);
    });
    tr.querySelector("button[data-action='draft']").addEventListener("click", () => prepareDraft(job.id));
    tr.querySelector("button[data-action='skip']").addEventListener("click", () => skipJob(job.id));
    tbody.appendChild(tr);
  });
}

function findJob(id) {
  return state.jobs.find((j) => j.id === id);
}

function selectJob(id) {
  state.selectedId = id;
  renderResults();
  const job = findJob(id);
  if (job && job.url) {
    $("preview-frame").src = job.url;
    $("btn-open-full").disabled = false;
  } else {
    $("preview-frame").src = "about:blank";
    $("btn-open-full").disabled = true;
  }
}

$("btn-open-full").addEventListener("click", () => {
  const job = findJob(state.selectedId);
  if (job) window.pywebview.api.open_full(job.url, job.title);
});

async function prepareDraft(id) {
  const job = findJob(id);
  const result = await window.pywebview.api.prepare_draft(id);
  if (result.ok) {
    appendLog(`Brouillon préparé pour « ${job.title} » -> ${result.path}`);
    removeJobFromList(id);
  } else {
    appendLog("Erreur : " + (result.error || "impossible de préparer le brouillon."));
  }
}

async function skipJob(id) {
  await window.pywebview.api.skip(id);
  const job = findJob(id);
  if (job) appendLog(`Offre ignorée : ${job.title}`);
  removeJobFromList(id);
}

function removeJobFromList(id) {
  state.jobs = state.jobs.filter((j) => j.id !== id);
  if (state.selectedId === id) {
    state.selectedId = null;
    $("preview-frame").src = "about:blank";
    $("btn-open-full").disabled = true;
  }
  renderResults();
}

$("btn-clear-results").addEventListener("click", () => {
  state.jobs = [];
  state.selectedId = null;
  $("preview-frame").src = "about:blank";
  $("btn-open-full").disabled = true;
  renderResults();
  appendLog("Résultats affichés vidés.");
});

$("btn-reset-history").addEventListener("click", async () => {
  if (!confirm(
    "Toutes les offres déjà acceptées ou ignorées pourront réapparaître lors de la " +
    "prochaine recherche. Continuer ?"
  )) return;
  await window.pywebview.api.reset_history();
  appendLog("Historique des offres déjà traitées réinitialisé.");
});

$("btn-open-drafts").addEventListener("click", () => {
  window.pywebview.api.open_drafts_folder();
});

// ---------------------------------------------------------------------
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

window.addEventListener("pywebviewready", loadConfig);
