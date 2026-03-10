/**
 * Annuaire Neoedge — Frontend JS
 * Inclut : thème (system/light/dark), logo, sauvegardes complètes.
 */

const App = (() => {

  // ── État ──────────────────────────────────────────────────────────────────
  let state = {
    user:      null,
    contacts:  [],
    rocs:      [],
    cSort:     { field: "societe",    dir: "asc" },
    rSort:     { field: "nom_client", dir: "asc" },
    cSearch:   "",
    selectedC: new Set(),
    selectedR: new Set(),
  };

  // ── Réseau ────────────────────────────────────────────────────────────────
  async function api(method, url, body = null) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body !== null) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (res.status === 401) { location.href = "/login"; return null; }
    return res;
  }

  function toast(msg, type = "ok") {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className   = `toast ${type}`;
    clearTimeout(t._timer);
    t._timer = setTimeout(() => { t.className = "toast hidden"; }, 3200);
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  async function init() {
    const res = await api("GET", "/api/auth/me");
    if (!res || !res.ok) return;
    state.user = await res.json();

    // Nom + rôle dans topbar
    const initials = (state.user.full_name || state.user.username).slice(0, 2).toUpperCase();
    document.getElementById("userAvatar").textContent = initials;
    document.getElementById("userName").textContent   = state.user.full_name || state.user.username;
    document.getElementById("userRole").textContent   = state.user.role;

    // Onglets admin
    if (state.user.role === "admin") {
      document.querySelectorAll(".admin-only").forEach(el => el.style.display = "");
    }
    // Cacher écriture pour viewers
    if (state.user.role === "viewer") {
      document.querySelectorAll(".write-only").forEach(el => el.style.display = "none");
    }

    // Thème sauvegardé
    applyTheme(state.user.theme || "system");

    // Logo
    loadLogo();

    await loadContacts();
    await loadRocs();
    bindEvents();
  }

  // ══════════════════════════════════════════════════════════════════════════
  // THÈME
  // ══════════════════════════════════════════════════════════════════════════

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);

    // Topbar : mettre en surbrillance le bon bouton
    document.querySelectorAll(".theme-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.theme === theme);
    });

    // Admin panel : cocher le bon radio
    const radio = document.querySelector(`input[name="themeChoice"][value="${theme}"]`);
    if (radio) radio.checked = true;
  }

  async function setTheme(theme) {
    applyTheme(theme);
    await api("POST", "/api/admin/theme", { theme });
    if (state.user) state.user.theme = theme;
  }

  // ══════════════════════════════════════════════════════════════════════════
  // LOGO
  // ══════════════════════════════════════════════════════════════════════════

  async function loadLogo() {
    const res = await fetch("/api/admin/logo");
    if (!res.ok) return;
    const data = await res.json();
    _applyLogo(data.logo);
  }

  function _applyLogo(dataUrl) {
    const img    = document.getElementById("logoImg");
    const dot    = document.getElementById("logoDot");
    const text   = document.getElementById("logoText");
    const prevWrap   = document.getElementById("logoPreviewWrap");
    const prevImg    = document.getElementById("logoPreviewAdmin");
    const placeholder= document.getElementById("logoPlaceholder");
    const btnDel     = document.getElementById("btnDeleteLogo");

    if (dataUrl) {
      img.src = dataUrl;
      img.style.display = "";
      dot.style.display = "none";
      if (prevWrap)    { prevWrap.style.display = ""; prevImg.src = dataUrl; }
      if (placeholder) placeholder.style.display = "none";
      if (btnDel)      btnDel.style.display = "";
    } else {
      img.style.display = "none";
      dot.style.display = "";
      if (prevWrap)    prevWrap.style.display = "none";
      if (placeholder) placeholder.style.display = "";
      if (btnDel)      btnDel.style.display = "none";
    }
  }

  async function uploadLogo(file) {
    const fd  = new FormData();
    fd.append("logo", file);
    const res = await fetch("/api/admin/logo", { method: "POST", body: fd });
    const json = await res.json();
    if (!res.ok) { toast(json.error, "err"); return; }
    _applyLogo(json.logo);
    toast("Logo mis à jour ✓");
  }

  async function deleteLogo() {
    if (!confirm("Supprimer le logo ?")) return;
    const res = await api("DELETE", "/api/admin/logo");
    if (!res || !res.ok) return;
    _applyLogo(null);
    toast("Logo supprimé ✓");
  }

  // ══════════════════════════════════════════════════════════════════════════
  // SAUVEGARDES
  // ══════════════════════════════════════════════════════════════════════════

  async function createBackup() {
    const res  = await api("POST", "/api/admin/backups", { kind: "manual" });
    if (!res || !res.ok) { toast("Erreur sauvegarde", "err"); return; }
    const json = await res.json();
    toast(`Sauvegarde créée : ${json.nb_contacts} contacts / ${json.nb_rocs} ROC ✓`);
    loadBackups();
    loadAdminStats();
  }

  async function loadBackups() {
    const res = await api("GET", "/api/admin/backups");
    if (!res || !res.ok) return;
    const list = await res.json();
    const el   = document.getElementById("backupsList");
    if (!el) return;

    if (!list.length) {
      el.innerHTML = `<p style="color:var(--muted);font-size:13px;padding:10px 0">Aucune sauvegarde.</p>`;
      return;
    }

    el.innerHTML = `
      <table class="backup-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Contacts</th>
            <th>ROC</th>
            <th>Créé par</th>
            <th style="text-align:right">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${list.map(b => `
            <tr>
              <td>${esc(b.created_at)}</td>
              <td><span class="kind-badge kind-${b.kind}">${b.kind === "manual" ? "Manuelle" : "Auto"}</span></td>
              <td>${b.nb_contacts}</td>
              <td>${b.nb_rocs}</td>
              <td>${esc(b.created_by)}</td>
              <td style="text-align:right;white-space:nowrap">
                <button class="btn btn-green btn-sm" onclick="App.downloadBackup(${b.id})">↓ Télécharger</button>
                <button class="btn btn-amber btn-sm" onclick="App.restoreBackup(${b.id},'${esc(b.created_at)}')">↩ Restaurer</button>
                <button class="btn btn-danger btn-sm" onclick="App.deleteBackup(${b.id})">🗑</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>`;
  }

  function downloadBackup(id) {
    window.open(`/api/admin/backups/${id}/download`, "_blank");
  }

  async function restoreBackup(id, date) {
    if (!confirm(`Restaurer la sauvegarde du ${date} ?\n\nATTENTION : toutes les données actuelles seront remplacées.\nUne sauvegarde de sécurité sera créée automatiquement.`)) return;
    const res  = await api("POST", `/api/admin/backups/${id}/restore`);
    if (!res || !res.ok) { toast("Erreur restauration", "err"); return; }
    const json = await res.json();
    toast(`Restauration OK : ${json.nb_contacts} contacts / ${json.nb_rocs} ROC ✓`);
    await loadContacts();
    await loadRocs();
    loadBackups();
    loadAdminStats();
  }

  async function deleteBackup(id) {
    if (!confirm("Supprimer cette sauvegarde ?")) return;
    const res = await api("DELETE", `/api/admin/backups/${id}`);
    if (!res || !res.ok) { toast("Erreur suppression", "err"); return; }
    toast("Sauvegarde supprimée ✓");
    loadBackups();
  }

  // ══════════════════════════════════════════════════════════════════════════
  // CONTACTS
  // ══════════════════════════════════════════════════════════════════════════

  async function loadContacts() {
    const params = new URLSearchParams({ q: state.cSearch, sort: state.cSort.field, dir: state.cSort.dir });
    const res    = await api("GET", `/api/contacts/?${params}`);
    if (!res || !res.ok) return;
    const data = await res.json();
    state.contacts = data.results;
    renderContacts();
    document.getElementById("contactTotal").textContent = data.total;
    document.getElementById("contactShown").textContent = data.results.length;
  }

  function renderContacts() {
    const tbody = document.getElementById("contactsTbody");
    tbody.innerHTML = "";
    state.contacts.forEach((c, i) => {
      const tr = document.createElement("tr");
      if (state.selectedC.has(c.id)) tr.classList.add("selected");
      tr.innerHTML = `
        <td class="col-check"><input type="checkbox" data-id="${c.id}" ${state.selectedC.has(c.id) ? "checked" : ""}></td>
        <td><b>${esc(c.societe)}</b></td>
        <td>${esc(c.nom)}</td>
        <td>${esc(c.prenom)}</td>
        <td><span style="background:rgba(79,142,247,.1);color:var(--accent);border-radius:4px;padding:2px 7px;font-size:11.5px">${esc(c.fonction)}</span></td>
        <td class="mono">${esc(c.email)}</td>
        <td class="mono">${esc(c.telephone)}</td>
        <td class="note">${esc(c.notes).substring(0, 55)}${c.notes.length > 55 ? "…" : ""}</td>
        <td class="by">${esc(c.updated_by)}</td>`;
      tr.querySelector("input[type=checkbox]").addEventListener("change", e => {
        e.stopPropagation();
        toggleSel(state.selectedC, c.id, e.target.checked);
        tr.classList.toggle("selected", e.target.checked);
        updateSelStatus();
      });
      tr.addEventListener("click", e => { if (e.target.type !== "checkbox") openSideContact(c); });
      tbody.appendChild(tr);
    });
  }

  // ══════════════════════════════════════════════════════════════════════════
  // ROC
  // ══════════════════════════════════════════════════════════════════════════

  async function loadRocs() {
    const params = new URLSearchParams({ sort: state.rSort.field, dir: state.rSort.dir });
    const res    = await api("GET", `/api/rocs/?${params}`);
    if (!res || !res.ok) return;
    const data = await res.json();
    state.rocs = data.results;
    renderRocs();
    document.getElementById("rocTotal").textContent = data.total;
    document.getElementById("rocShown").textContent = data.results.length;
  }

  function renderRocs() {
    const tbody = document.getElementById("rocsTbody");
    tbody.innerHTML = "";
    state.rocs.forEach(r => {
      const tr = document.createElement("tr");
      if (state.selectedR.has(r.id)) tr.classList.add("selected");
      tr.innerHTML = `
        <td class="col-check"><input type="checkbox" data-id="${r.id}" ${state.selectedR.has(r.id) ? "checked" : ""}></td>
        <td><b>${esc(r.nom_client)}</b></td>
        <td class="mono">${esc(r.roc)}</td>
        <td class="mono">${esc(r.trinity)}</td>
        <td>${esc(r.infogerance)}</td>
        <td>${esc(r.astreinte)}</td>
        <td>${esc(r.type_contrat)}</td>
        <td class="mono">${esc(r.date_anniversaire_contrat)}</td>
        <td class="by">${esc(r.updated_by)}</td>`;
      tr.querySelector("input[type=checkbox]").addEventListener("change", e => {
        e.stopPropagation();
        toggleSel(state.selectedR, r.id, e.target.checked);
        tr.classList.toggle("selected", e.target.checked);
      });
      tr.addEventListener("click", e => { if (e.target.type !== "checkbox") openSideRoc(r); });
      tbody.appendChild(tr);
    });
  }

  // ══════════════════════════════════════════════════════════════════════════
  // SIDE PANEL
  // ══════════════════════════════════════════════════════════════════════════

  function openSideContact(c) {
    const initials = ((c.prenom||"").slice(0,1) + (c.nom||"").slice(0,1)).toUpperCase() || "?";
    const ro       = state.user.role === "viewer" ? "readonly" : "";
    const canWrite = state.user.role !== "viewer";

    document.getElementById("sidePanelTitle").textContent = "";

    // En-tête enrichi
    document.getElementById("sidePanelHeader").innerHTML = `
      <div class="sp-hero">
        <div class="sp-avatar">${initials}</div>
        <div class="sp-hero-info">
          <div class="sp-name">${esc(c.prenom)} ${esc(c.nom)}</div>
          <div class="sp-sub">${esc(c.fonction) || '<span style="color:var(--muted);font-style:italic">Fonction non renseignée</span>'}</div>
          <div class="sp-company">🏢 ${esc(c.societe)}</div>
        </div>
        <button class="close-btn sp-close" id="btnCloseSide">✕</button>
      </div>`;
    document.getElementById("btnCloseSide").onclick = closeSide;

    document.getElementById("sidePanelBody").innerHTML = `
      <div class="sp-section-title">Identité</div>
      <div class="sp-row">
        ${sf("Nom",    "nom",    c.nom,    ro)}
        ${sf("Prénom", "prenom", c.prenom, ro)}
      </div>
      ${sf("Société",  "societe",  c.societe,  ro)}
      ${sf("Fonction", "fonction", c.fonction, ro)}

      <div class="sp-section-title" style="margin-top:16px">Coordonnées</div>
      ${sf("Email", "email", c.email, ro)}
      <div class="sp-row">
        ${sf("Téléphone",   "telephone",  c.telephone,  ro)}
        ${sf("Téléphone 2", "telephone2", c.telephone2, ro)}
      </div>

      <div class="sp-section-title" style="margin-top:16px">Notes</div>
      ${sf("", "notes", c.notes, ro, true)}

      <div class="sp-meta">
        Modifié par <b>${esc(c.updated_by)||"—"}</b> · ${esc(c.updated_at)||"—"}
      </div>`;

    const act = document.getElementById("sidePanelActions");
    act.innerHTML = canWrite
      ? `<button class="btn btn-primary sp-save-btn" id="btnSaveSide">💾 Sauvegarder</button>
         <button class="btn btn-danger" id="btnDelSide" title="Supprimer">🗑</button>` : "";
    if (canWrite) {
      document.getElementById("btnSaveSide").onclick = () => saveContact(c.id);
      document.getElementById("btnDelSide").onclick  = () => deleteContact(c.id);
    }
    document.getElementById("sidePanel").classList.remove("hidden");
    _fillSideValues();
  }

  function openSideRoc(r) {
    const ro       = state.user.role === "viewer" ? "readonly" : "";
    const canWrite = state.user.role !== "viewer";

    document.getElementById("sidePanelTitle").textContent = "";

    document.getElementById("sidePanelHeader").innerHTML = `
      <div class="sp-hero sp-hero-roc">
        <div class="sp-avatar sp-avatar-roc">📋</div>
        <div class="sp-hero-info">
          <div class="sp-name">${esc(r.nom_client)}</div>
          <div class="sp-sub">ROC : <b>${esc(r.roc)||"—"}</b></div>
          <div class="sp-company">Trinity : ${esc(r.trinity)||"—"}</div>
        </div>
        <button class="close-btn sp-close" id="btnCloseSide">✕</button>
      </div>`;
    document.getElementById("btnCloseSide").onclick = closeSide;

    document.getElementById("sidePanelBody").innerHTML = `
      <div class="sp-section-title">Identification</div>
      ${sf("Nom Client", "nom_client", r.nom_client, ro)}
      <div class="sp-row">
        ${sf("ROC",     "roc",     r.roc,     ro)}
        ${sf("Trinity", "trinity", r.trinity, ro)}
      </div>

      <div class="sp-section-title" style="margin-top:16px">Contrat</div>
      ${sf("Type de contrat",           "type_contrat",             r.type_contrat,             ro)}
      ${sf("Date anniversaire contrat", "date_anniversaire_contrat",r.date_anniversaire_contrat,ro)}

      <div class="sp-section-title" style="margin-top:16px">Support</div>
      ${sf("Infogérance", "infogerance", r.infogerance, ro)}
      ${sf("Astreinte",   "astreinte",   r.astreinte,   ro)}

      <div class="sp-meta">
        Modifié par <b>${esc(r.updated_by)||"—"}</b> · ${esc(r.updated_at)||"—"}
      </div>`;

    const act = document.getElementById("sidePanelActions");
    act.innerHTML = canWrite
      ? `<button class="btn btn-primary sp-save-btn" id="btnSaveSide">💾 Sauvegarder</button>
         <button class="btn btn-danger" id="btnDelSide" title="Supprimer">🗑</button>` : "";
    if (canWrite) {
      document.getElementById("btnSaveSide").onclick = () => saveRoc(r.id);
      document.getElementById("btnDelSide").onclick  = () => deleteRoc(r.id);
    }
    document.getElementById("sidePanel").classList.remove("hidden");
    _fillSideValues();
  }

  function closeSide() {
    document.getElementById("sidePanel").classList.add("hidden");
  }

  async function saveContact(id) {
    const data = readSideFields();
    const res  = await api("PUT", `/api/contacts/${id}`, data);
    if (!res) return;
    const json = await res.json();
    if (!res.ok) { toast(json.errors?.join(" ") || json.error, "err"); return; }
    toast("Contact sauvegardé ✓");
    await loadContacts(); openSideContact(json);
  }

  async function deleteContact(id) {
    if (!confirm("Supprimer ce contact ?")) return;
    await api("DELETE", `/api/contacts/${id}`);
    toast("Contact supprimé ✓"); closeSide(); await loadContacts();
  }

  async function saveRoc(id) {
    const data = readSideFields();
    const res  = await api("PUT", `/api/rocs/${id}`, data);
    if (!res) return;
    const json = await res.json();
    if (!res.ok) { toast(json.errors?.join(" ") || json.error, "err"); return; }
    toast("ROC sauvegardé ✓");
    await loadRocs(); openSideRoc(json);
  }

  async function deleteRoc(id) {
    if (!confirm("Supprimer ce ROC ?")) return;
    await api("DELETE", `/api/rocs/${id}`);
    toast("ROC supprimé ✓"); closeSide(); await loadRocs();
  }

  // ══════════════════════════════════════════════════════════════════════════
  // CRÉATION (modales)
  // ══════════════════════════════════════════════════════════════════════════

  function openNewContactModal() {
    openModal("Nouveau contact", `
      <div class="form-grid">
        ${fi("Société ★", "societe", "", "ex: Acme Corp")}
        ${fi("Fonction",  "fonction","", "ex: Directeur IT")}
      </div>
      <div class="form-grid">
        ${fi("Nom ★",    "nom",    "", "ex: Dupont")}
        ${fi("Prénom ★", "prenom", "", "ex: Jean")}
      </div>
      ${fi("Email", "email", "", "jean@acme.fr")}
      <div class="form-grid">
        ${fi("Téléphone",   "telephone",  "", "06 12 34 56 78")}
        ${fi("Téléphone 2", "telephone2", "", "01 23 45 67 89")}
      </div>
      <div class="form-row">
        <label class="form-label">Notes</label>
        <textarea class="form-input" name="notes" rows="3"></textarea>
      </div>
      <div id="formErrors"></div>`,
      [{ label:"Annuler", cls:"btn-ghost",   action: closeModal },
       { label:"Créer",   cls:"btn-primary", action: async () => {
          const d = readModalFields();
          const e = validateContact(d);
          if (e.length) { showModalErrors(e); return; }
          const res  = await api("POST", "/api/contacts/", d);
          const json = await res.json();
          if (!res.ok) { showModalErrors(json.errors || [json.error]); return; }
          toast("Contact créé ✓"); closeModal(); await loadContacts();
       }}]);
  }

  function openNewRocModal() {
    openModal("Nouveau ROC", `
      <div class="form-grid">
        ${fi("Nom Client ★", "nom_client", "", "")}
        ${fi("ROC ★",        "roc",        "", "")}
      </div>
      <div class="form-grid">
        ${fi("Trinity",      "trinity",     "", "")}
        ${fi("Type Contrat", "type_contrat","", "")}
      </div>
      ${fi("Infogérance",               "infogerance",               "", "")}
      ${fi("Astreinte",                 "astreinte",                 "", "")}
      ${fi("Date Anniversaire Contrat", "date_anniversaire_contrat", "", "jj/mm/aaaa")}
      <div id="formErrors"></div>`,
      [{ label:"Annuler", cls:"btn-ghost",   action: closeModal },
       { label:"Créer",   cls:"btn-primary", action: async () => {
          const d = readModalFields();
          const e = validateRoc(d);
          if (e.length) { showModalErrors(e); return; }
          const res  = await api("POST", "/api/rocs/", d);
          const json = await res.json();
          if (!res.ok) { showModalErrors(json.errors || [json.error]); return; }
          toast("ROC créé ✓"); closeModal(); await loadRocs();
       }}]);
  }

  // ══════════════════════════════════════════════════════════════════════════
  // BULK DELETE
  // ══════════════════════════════════════════════════════════════════════════

  async function bulkDeleteContacts() {
    if (!state.selectedC.size) { toast("Aucune sélection", "err"); return; }
    if (!confirm(`Supprimer ${state.selectedC.size} contact(s) ?`)) return;
    const res  = await api("DELETE", "/api/contacts/bulk", [...state.selectedC]);
    const json = await res.json();
    toast(`${json.deleted} contact(s) supprimé(s) ✓`);
    state.selectedC.clear(); closeSide(); await loadContacts();
  }

  async function bulkDeleteRocs() {
    if (!state.selectedR.size) { toast("Aucune sélection", "err"); return; }
    if (!confirm(`Supprimer ${state.selectedR.size} ROC(s) ?`)) return;
    const res  = await api("DELETE", "/api/rocs/bulk", [...state.selectedR]);
    const json = await res.json();
    toast(`${json.deleted} ROC(s) supprimé(s) ✓`);
    state.selectedR.clear(); await loadRocs();
  }

  // ══════════════════════════════════════════════════════════════════════════
  // ADMIN
  // ══════════════════════════════════════════════════════════════════════════

  async function loadAdminStats() {
    const res = await api("GET", "/api/admin/stats");
    if (!res || !res.ok) return;
    const d = await res.json();
    document.getElementById("adminStats").innerHTML = `
      <div class="stat-row"><span>Contacts</span>         <b>${d.contacts}</b></div>
      <div class="stat-row"><span>ROC</span>              <b>${d.rocs}</b></div>
      <div class="stat-row"><span>Utilisateurs</span>     <b>${d.users}</b></div>
      <div class="stat-row"><span>Sauvegardes</span>      <b>${d.nb_backups}</b></div>
      <div class="stat-row"><span>Dernière sauvegarde</span><b style="color:var(--green)">${d.last_backup}</b></div>`;
    loadUsers();
    loadBackups();
  }

  async function loadUsers() {
    const res = await api("GET", "/api/admin/users");
    if (!res || !res.ok) return;
    const users = await res.json();
    document.getElementById("usersList").innerHTML = users.map(u => `
      <div class="user-item">
        <div class="user-avatar">${(u.full_name||u.username).slice(0,2).toUpperCase()}</div>
        <div>
          <div style="font-size:13px">${esc(u.full_name || u.username)}</div>
          <div style="font-size:11px;color:var(--muted)">${esc(u.username)}</div>
        </div>
        <span class="role-badge role-${u.role}">${u.role}</span>
        <div class="user-actions">
          <button class="btn btn-ghost btn-sm" onclick="App.openEditUser(${u.id})">✏️</button>
          <button class="btn btn-danger btn-sm" onclick="App.deleteUser(${u.id},'${esc(u.username)}')">🗑</button>
        </div>
      </div>`).join("");
  }

  function openNewUserModal() {
    openModal("Nouvel utilisateur", `
      <div class="form-grid">
        ${fi("Identifiant", "username",  "", "prenom.nom")}
        ${fi("Nom complet", "full_name", "", "Jean Dupont")}
      </div>
      ${fi("Email",         "email",    "", "jean@neoedge.fr")}
      ${fi("Mot de passe",  "password", "", "min. 8 caractères")}
      <div class="form-row">
        <label class="form-label">Rôle</label>
        <select class="form-input" name="role">
          <option value="viewer">Viewer — lecture seule</option>
          <option value="editor">Editor — lecture + écriture</option>
          <option value="admin">Admin — accès complet</option>
        </select>
      </div>`,
      [{ label:"Annuler", cls:"btn-ghost",   action: closeModal },
       { label:"Créer",   cls:"btn-primary", action: async () => {
          const d = readModalFields();
          if (!d.username || !d.password || !d.email) { showModalErrors(["Tous les champs sont requis."]); return; }
          const res = await api("POST", "/api/admin/users", d);
          const j   = await res.json();
          if (!res.ok) { showModalErrors([j.error]); return; }
          toast("Utilisateur créé ✓"); closeModal(); loadUsers();
       }}]);
  }

  async function openEditUser(id) {
    const res = await api("GET", "/api/admin/users");
    if (!res || !res.ok) return;
    const u = (await res.json()).find(x => x.id === id);
    if (!u) return;
    openModal(`Modifier — ${u.username}`, `
      ${fi("Nom complet", "full_name", u.full_name, "")}
      ${fi("Email",       "email",     u.email,     "")}
      ${fi("Nouveau mot de passe (vide = inchangé)", "password", "", "")}
      <div class="form-row">
        <label class="form-label">Rôle</label>
        <select class="form-input" name="role">
          <option value="viewer" ${u.role==="viewer"?"selected":""}>Viewer</option>
          <option value="editor" ${u.role==="editor"?"selected":""}>Editor</option>
          <option value="admin"  ${u.role==="admin" ?"selected":""}>Admin</option>
        </select>
      </div>
      <div class="form-row">
        <label class="form-label">Compte actif</label>
        <select class="form-input" name="active">
          <option value="1" ${u.active?"selected":""}>Oui</option>
          <option value="0" ${!u.active?"selected":""}>Non (désactivé)</option>
        </select>
      </div>`,
      [{ label:"Annuler",     cls:"btn-ghost",   action: closeModal },
       { label:"Enregistrer", cls:"btn-primary", action: async () => {
          const d = readModalFields();
          if (!d.password) delete d.password;
          d.active = d.active === "1";
          const r = await api("PUT", `/api/admin/users/${id}`, d);
          const j = await r.json();
          if (!r.ok) { showModalErrors([j.error]); return; }
          toast("Utilisateur mis à jour ✓"); closeModal(); loadUsers();
       }}]);
  }

  async function deleteUser(id, username) {
    if (!confirm(`Supprimer "${username}" ?`)) return;
    await api("DELETE", `/api/admin/users/${id}`);
    toast("Utilisateur supprimé ✓"); loadUsers();
  }

  // ══════════════════════════════════════════════════════════════════════════
  // LOGS
  // ══════════════════════════════════════════════════════════════════════════

  let _logFilter = "";

  async function loadLogs(action = _logFilter) {
    _logFilter = action;
    const params = new URLSearchParams({ per_page: 200 });
    if (action) params.set("level", action);
    const res = await api("GET", `/api/admin/logs?${params}`);
    if (!res || !res.ok) return;
    const data = await res.json();
    document.getElementById("logWrap").innerHTML = data.results.map(l => `
      <div class="log-line log-${l.action}">
        <span style="color:var(--muted)">${l.timestamp}</span>
        <span class="log-level"> ${l.action} </span>
        <b>${esc(l.username)}</b>
        ${l.table_name ? `[${esc(l.table_name)}]` : ""}
        ${esc(l.detail)}
        <span style="color:var(--border);font-size:10px"> ${l.ip_address}</span>
      </div>`).join("");
  }

  async function purgeLogs() {
    if (!confirm("Purger tous les logs ?")) return;
    await api("POST", "/api/admin/logs/purge");
    toast("Logs purgés ✓"); loadLogs();
  }

  // ══════════════════════════════════════════════════════════════════════════
  // DOUBLONS
  // ══════════════════════════════════════════════════════════════════════════

  async function openDupScanner(table) {
    const res = await api("GET", `/api/duplicates/${table}?mode=similar`);
    if (!res || !res.ok) return;
    const data = await res.json();
    if (data.total_groups === 0) { toast("Aucun doublon détecté ✓"); return; }

    let html = `<p style="color:var(--muted);font-size:12.5px;margin-bottom:14px">
      ${data.total_groups} groupe(s) de doublons détecté(s).</p>`;
    data.groups.forEach((g, gi) => {
      html += `<div class="dup-group">
        <div class="dup-group-header">🔍 ${esc(g.reason)} — <b>${esc(g.key)}</b></div>`;
      g.records.forEach(r => {
        const label = table === "contacts"
          ? `${r.societe} / ${r.nom} ${r.prenom} — ${r.email}`
          : `${r.nom_client} / ${r.roc}`;
        html += `<div class="dup-record">
          <span>${esc(label)}</span>
          <button class="dup-keep-btn" data-gi="${gi}" data-id="${r.id}" onclick="App._pickKeep(this,${gi})">Conserver</button>
        </div>`;
      });
      html += `</div>`;
    });
    window._dupGroups = data.groups;
    window._dupTable  = table;

    openModal(`Doublons — ${table}`, html, [
      { label:"Annuler",  cls:"btn-ghost",   action: closeModal },
      { label:"Fusionner",cls:"btn-primary", action: mergeDuplicates },
    ]);
  }

  function _pickKeep(btn, gi) {
    document.querySelectorAll(`.dup-keep-btn[data-gi="${gi}"]`).forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");
  }

  async function mergeDuplicates() {
    const groups = window._dupGroups || [];
    const table  = window._dupTable;
    let merged   = 0;
    for (const g of groups) {
      const gi  = groups.indexOf(g);
      const btn = document.querySelector(`.dup-keep-btn[data-gi="${gi}"].selected`);
      if (!btn) continue;
      const keepId = parseInt(btn.dataset.id);
      const delIds = g.records.map(r => r.id).filter(id => id !== keepId);
      const res    = await api("POST", `/api/duplicates/${table}/merge`, { keep_id: keepId, delete_ids: delIds });
      if (res && res.ok) merged += (await res.json()).deleted;
    }
    toast(`${merged} doublon(s) fusionné(s) ✓`);
    closeModal();
    if (table === "contacts") await loadContacts(); else await loadRocs();
  }

  // ══════════════════════════════════════════════════════════════════════════
  // EXPORT
  // ══════════════════════════════════════════════════════════════════════════

  function exportData(table, format) {
    window.open(`/api/export/${table}/${format}`, "_blank");
  }

  // ══════════════════════════════════════════════════════════════════════════
  // MODAL GÉNÉRIQUE
  // ══════════════════════════════════════════════════════════════════════════

  function openModal(title, bodyHtml, buttons) {
    document.getElementById("modalTitle").textContent = title;
    document.getElementById("modalBody").innerHTML    = bodyHtml;
    const footer = document.getElementById("modalFooter");
    footer.innerHTML = "";
    (buttons || []).forEach(b => {
      const btn = document.createElement("button");
      btn.className   = `btn ${b.cls}`;
      btn.textContent = b.label;
      btn.onclick     = b.action;
      footer.appendChild(btn);
    });
    document.getElementById("modalOverlay").classList.add("open");
  }

  function closeModal() {
    document.getElementById("modalOverlay").classList.remove("open");
  }

  // ══════════════════════════════════════════════════════════════════════════
  // HELPERS UI
  // ══════════════════════════════════════════════════════════════════════════

  function sf(label, name, value, readonly, textarea = false) {
    // On utilise data-value pour passer la valeur sans risque d'injection HTML
    const ro  = readonly ? "readonly" : "";
    const val = (value || "").replace(/\\/g,"\\\\").replace(/"/g,"&quot;");
    if (textarea) return `<div class="field-group" data-field="${name}">
      <div class="field-label">${label}</div>
      <textarea class="field-input" name="${name}" ${ro}></textarea></div>`;
    return `<div class="field-group" data-field="${name}">
      <div class="field-label">${label}</div>
      <input class="field-input" type="text" name="${name}" data-val="${val}" ${ro}></div>`;
  }

  function _fillSideValues() {
    // Injecte les valeurs via .value (évite tout problème d'encodage HTML)
    document.querySelectorAll("#sidePanelBody input.field-input[data-val]").forEach(el => {
      el.value = el.dataset.val.replace(/&quot;/g, '"');
    });
  }

  function fi(label, name, value = "", placeholder = "") {
    return `<div class="form-row">
      <label class="form-label">${label}</label>
      <input class="form-input" name="${name}" value="${esc(value)}" placeholder="${esc(placeholder)}">
    </div>`;
  }

  function readModalFields() {
    const out = {};
    document.querySelectorAll("#modalBody [name]").forEach(el => { out[el.name] = el.value; });
    return out;
  }

  function readSideFields() {
    const out = {};
    document.querySelectorAll("#sidePanelBody [name]").forEach(el => { out[el.name] = el.value; });
    return out;
  }

  function validateContact(d) {
    const e = [];
    if (!d.societe?.trim()) e.push("La société est obligatoire.");
    if (!d.nom?.trim())     e.push("Le nom est obligatoire.");
    if (!d.prenom?.trim())  e.push("Le prénom est obligatoire.");
    return e;
  }

  function validateRoc(d) {
    const e = [];
    if (!d.nom_client?.trim()) e.push("Le nom client est obligatoire.");
    if (!d.roc?.trim())        e.push("Le ROC est obligatoire.");
    return e;
  }

  function showModalErrors(errors) {
    const el = document.getElementById("formErrors");
    if (el) el.innerHTML = errors.map(e => `<p class="error-msg">⚠ ${esc(e)}</p>`).join("");
  }

  function toggleSel(set, id, checked) {
    if (checked) set.add(id); else set.delete(id);
  }

  function updateSelStatus() {
    const el = document.getElementById("contactSelStatus");
    if (el) el.textContent = state.selectedC.size ? `${state.selectedC.size} sélectionné(s)` : "";
  }

  function esc(str) {
    return String(str || "")
      .replace(/&/g,"&amp;").replace(/</g,"&lt;")
      .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  // ══════════════════════════════════════════════════════════════════════════
  // BIND EVENTS
  // ══════════════════════════════════════════════════════════════════════════

  function bindSort(tableId, loadFn, sortState) {
    document.getElementById(tableId)?.querySelectorAll("th.sortable").forEach(th => {
      th.addEventListener("click", async () => {
        const field = th.dataset.sort;
        if (sortState.field === field) sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
        else { sortState.field = field; sortState.dir = "asc"; }
        document.getElementById(tableId).querySelectorAll("th.sortable")
          .forEach(h => h.classList.remove("sorted-asc","sorted-desc"));
        th.classList.add(sortState.dir === "asc" ? "sorted-asc" : "sorted-desc");
        await loadFn();
      });
    });
  }

  function bindEvents() {
    // Recherche
    document.getElementById("globalSearch").addEventListener("input", async e => {
      state.cSearch = e.target.value.trim(); await loadContacts();
    });
    document.getElementById("globalSearch").addEventListener("keydown", async e => {
      if (e.key === "Escape") { state.cSearch = ""; e.target.value = ""; await loadContacts(); }
    });

    // Tabs
    document.querySelectorAll(".tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        const name = tab.dataset.tab;
        document.querySelectorAll(".tab-content").forEach(s => s.classList.remove("active"));
        document.getElementById(`tab-${name}`).classList.add("active");
        closeSide();
        if (name === "admin") loadAdminStats();
        if (name === "logs")  loadLogs();
      });
    });

    // Thème — boutons topbar
    document.querySelectorAll(".theme-btn").forEach(btn => {
      btn.addEventListener("click", () => setTheme(btn.dataset.theme));
    });

    // Thème — radios panneau admin
    document.querySelectorAll("input[name='themeChoice']").forEach(radio => {
      radio.addEventListener("change", () => setTheme(radio.value));
    });

    // Logo
    document.getElementById("logoFileInput")?.addEventListener("change", e => {
      const file = e.target.files[0];
      if (file) uploadLogo(file);
      e.target.value = "";
    });

    // Drag & drop logo
    const uploadArea = document.getElementById("logoUploadArea");
    if (uploadArea) {
      uploadArea.addEventListener("dragover", e => { e.preventDefault(); uploadArea.style.borderColor = "var(--accent)"; });
      uploadArea.addEventListener("dragleave", () => { uploadArea.style.borderColor = ""; });
      uploadArea.addEventListener("drop", e => {
        e.preventDefault(); uploadArea.style.borderColor = "";
        const file = e.dataTransfer.files[0];
        if (file) uploadLogo(file);
      });
    }

    // Filtres logs
    document.querySelectorAll(".log-filter-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".log-filter-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        loadLogs(btn.dataset.action);
      });
    });

    // Boutons contacts
    document.getElementById("btnNewContact")?.addEventListener("click", openNewContactModal);
    document.getElementById("btnDelContacts")?.addEventListener("click", bulkDeleteContacts);
    document.getElementById("btnDupContacts")?.addEventListener("click", () => openDupScanner("contacts"));

    // Boutons ROC
    document.getElementById("btnNewRoc")?.addEventListener("click", openNewRocModal);
    document.getElementById("btnDelRocs")?.addEventListener("click", bulkDeleteRocs);
    document.getElementById("btnDupRocs")?.addEventListener("click", () => openDupScanner("rocs"));

    // Bouton utilisateur
    document.getElementById("btnNewUser")?.addEventListener("click", openNewUserModal);

    // Déconnexion
    document.getElementById("btnLogout").addEventListener("click", async () => {
      await api("POST", "/logout"); location.href = "/login";
    });

    // Fermer modal/side
    document.getElementById("btnCloseModal").addEventListener("click", closeModal);
    document.getElementById("btnCloseSide").addEventListener("click", closeSide);
    document.getElementById("modalOverlay").addEventListener("click", e => {
      if (e.target === document.getElementById("modalOverlay")) closeModal();
    });
    document.addEventListener("keydown", e => {
      if (e.key === "Escape") { closeModal(); closeSide(); }
    });

    // Checkboxes globales
    document.getElementById("checkAllContacts").addEventListener("change", e => {
      const checked = e.target.checked;
      state.contacts.forEach(c => { if (checked) state.selectedC.add(c.id); else state.selectedC.delete(c.id); });
      renderContacts(); updateSelStatus();
    });
    document.getElementById("checkAllRocs").addEventListener("change", e => {
      const checked = e.target.checked;
      state.rocs.forEach(r => { if (checked) state.selectedR.add(r.id); else state.selectedR.delete(r.id); });
      renderRocs();
    });

    // Tri
    bindSort("contactsTable", loadContacts, state.cSort);
    bindSort("rocsTable",     loadRocs,     state.rSort);
  }

  // ── API publique ─────────────────────────────────────────────────────────
  return {
    init,
    export:         exportData,
    createBackup,
    downloadBackup,
    restoreBackup,
    deleteBackup,
    deleteLogo,
    loadAdminStats,
    loadLogs,
    purgeLogs,
    openEditUser,
    deleteUser,
    _pickKeep,
  };
})();

document.addEventListener("DOMContentLoaded", App.init);
