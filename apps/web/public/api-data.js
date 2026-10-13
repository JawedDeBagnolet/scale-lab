// api-data.js — Remplace shared-data.js par les données réelles du backend.
// Charge un squelette synchrone (SCALE_DATA existe immédiatement),
// puis fetch les données en async et déclenche un re-render.
(function () {
  'use strict';

  // ─── Config ──────────────────────────────────────────────────────────
  var API_BASE = 'https://api.scalelab.win/api';
  var TOKEN = (function () {
    try { return localStorage.getItem('sl_api_token'); } catch (e) { return null; }
  })() || '75640332d36f253e8debecbcc6dba4d0eebfd9fafaeac96812b67593d77886b7';

  // XHR synchrone pour que SCALE_DATA soit peuplé AVANT le rendu des templates
  function apiFetchSync(path) {
    try {
      var x = new XMLHttpRequest();
      x.open('GET', API_BASE + path, false); // false = synchrone
      x.setRequestHeader('Authorization', 'Bearer ' + TOKEN);
      // Pas de Content-Type sur GET — évite le preflight CORS avec XHR synchrone
      x.send();
      if (x.status >= 200 && x.status < 300) {
        return JSON.parse(x.responseText);
      }
      console.warn('[Scale Lab] API ' + path + ' → ' + x.status);
    } catch (e) {
      console.warn('[Scale Lab] Erreur fetch ' + path + ' :', e);
    }
    return [];
  }

  // ─── Transformations : API snake_case → SCALE_DATA camelCase ───────
  function xPersona(p) {
    return {
      id: p.id,
      prsId: p.prs_id || p.id,
      first: p.first_name,
      last: p.last_name,
      name: p.first_name + ' ' + p.last_name,
      color: p.color || '#8b7cf6',
      market: p.market || 'FR',
      city: p.city || '',
      age: p.age || 0,
      platforms: p.platforms || [],
      niches: p.niches || [],
      tg: p.telegram || null
    };
  }

  function xCompte(c) {
    return {
      id: c.id,
      handle: c.handle,
      persona: c.persona_id,
      plat: c.plateforme,
      workflow: c.workflow || 'Actif',
      status: c.status || 'idle',
      device: c.device_id || null
    };
  }

  function xDevice(d, proxiesMap) {
    var px = proxiesMap[d.proxy_id] || null;
    return {
      id: d.id,
      name: d.name,
      model: d.model || 'iPhone',
      ios: d.ios_version || '',
      rack: d.rack || '',
      status: d.status || 'online',
      market: d.market || 'FR',
      proxy: d.proxy_id || null,
      pxStatus: px ? px.status : 'ok',
      jb: d.jailbreak !== false,
      rules: { max: d.max_comptes || 6, personas: [], plats: ['ig', 'th', 'x'] }
    };
  }

  function xPreset(b) {
    var cfg = b.config || {};
    return {
      id: b.id,
      plat: b.plateforme,
      icon: cfg.icon || 'sliders',
      name: b.name,
      type: b.session_type || 'feed',
      weight: cfg.weight || 1,
      p: cfg.p || {},
      pauses: (cfg.pauses || []).map(function (x, i) {
        return { id: b.id + 'p' + i, label: x.label || x[0], min: x.min || x[1], max: x.max || x[2], prob: x.prob || x[3] };
      }),
      durations: (cfg.durations || []).map(function (x, i) {
        return { id: b.id + 'd' + i, min: x.min || x[0], max: x.max || x[1], weight: x.weight || x[2] };
      })
    };
  }

  function xScenario(s) {
    return {
      id: s.id,
      name: s.name,
      icon: s.icon || 'lightning',
      origin: s.origin || 'spont',
      couple: !!s.couple,
      slots: s.slots || [],
      steps: s.steps || []
    };
  }

  function xSlot(s) {
    return {
      id: s.id,
      name: s.name,
      icon: s.icon || 'clock',
      days: s.days || [],
      ranges: s.ranges || []
    };
  }

  function xCollection(c) {
    return {
      id: c.id,
      name: c.name,
      type: c.collection_type || c.type || 'variable',
      persona: c.persona_id || c.persona,
      plat: c.plateforme || c.plat || 'ig',
      ptype: c.post_type || c.ptype || 'reel',
      platLabel: c.plat_label || '',
      captions: typeof c.captions === 'number' ? c.captions : (Array.isArray(c.captions) ? c.captions.length : 0)
    };
  }

  function xCampaign(c) {
    return {
      id: c.id,
      name: c.name,
      icon: c.icon || 'flag',
      persona: c.persona_id || c.persona,
      plat: c.plateforme || c.plat || 'ig',
      status: c.status || 'active',
      scenarios: c.scenarios || []
    };
  }

  // ─── behaviorParams (config statique, identique à shared-data.js) ──
  var behaviorParams = {
    labels: {
      like: ['Like', 'Probabilité de liker un post vu'],
      comments: ['Lire les commentaires', "Probabilité d'ouvrir les commentaires d'un post"],
      follow: ['Follow', 'Probabilité de suivre un profil visité'],
      cursor: ['Lecture au curseur', 'Probabilité que le curseur suive le texte ligne par ligne'],
      target: ['Visiter une target', "Quand un post vient d'une target non suivie, probabilité d'ouvrir son profil"],
      lambda: ['Visiter un compte lambda', 'Probabilité de visiter un profil hors cibles'],
      scrollback: ['Scroll-back', "Probabilité de remonter d'un post pour le relire"],
      openPost: ['Ouvrir un post', "Probabilité d'ouvrir un post en vue détaillée"],
      likeComment: ['Liker un commentaire', "Dans un post ouvert, probabilité de liker un commentaire"],
      commentAuthor: ['Profil auteur commentaire', "Après avoir liké un commentaire, probabilité de visiter le profil de l'auteur"],
      story: ['Regarder les stories', "Probabilité d'ouvrir les stories en haut du feed"],
      save: ['Enregistrer un post', "Probabilité d'enregistrer un post vu"]
    },
    lot1: ['like', 'comments', 'follow'],
    lot2: {
      x: ['cursor', 'target', 'lambda', 'scrollback', 'openPost', 'likeComment', 'commentAuthor'],
      ig: ['target', 'lambda', 'scrollback', 'openPost', 'likeComment', 'commentAuthor', 'story', 'save'],
      th: ['target', 'lambda', 'scrollback', 'openPost', 'likeComment', 'commentAuthor']
    },
    types: {
      x: [['feed', 'Feed Home'], ['hybrid', 'Hybrid'], ['profile', 'Profil']],
      ig: [['feed', 'Feed'], ['reels', 'Reels'], ['profile', 'Profil']],
      th: [['feed', 'Feed'], ['hybrid', 'Hybrid'], ['profile', 'Profil']]
    }
  };

  // ─── Données : démarrent vides, remplies par l'API ─────────────────
  var personas = [];
  var accounts = [];
  var devices = [];
  var behaviors = [];
  var slots = [];
  var scenarios = [];
  var campaigns = [];
  var collections = [];
  var licenses = [];
  var ocAccounts = [];
  var alloc = { on: true, mode: 'fill', at: 80 };
  var drawMode = { x: 'weighted', ig: 'uniform', th: 'uniform' };

  // ─── Fonctions de recherche ────────────────────────────────────────
  var PLN = { ig: 'Instagram', th: 'Threads', x: 'X' };

  function pickDevice(market, persona, plat, extra) {
    extra = extra || {};
    var skipped = [], el = [];
    devices.filter(function (d) { return d.market === market; }).forEach(function (d) {
      var n = accounts.filter(function (a) { return a.device === d.id; }).length + (extra[d.id] || 0);
      var R = d.rules; var why = null;
      if (d.status !== 'online') why = 'indisponible';
      else if (d.jb === false) why = 'jailbreak perdu';
      else if (!d.proxy) why = 'sans proxy';
      else if (d.pxStatus === 'down') why = 'proxy hors ligne';
      else if (R.plats.indexOf(plat) < 0) why = (PLN[plat] || plat) + ' non autorisé';
      else if (R.personas.length && R.personas.indexOf(persona) < 0) why = 'persona non autorisée';
      else if (n >= R.max) why = 'plein · ' + n + '/' + R.max;
      if (why) skipped.push({ name: d.name, reason: why });
      else el.push({ d: d, n: n, ratio: n / R.max });
    });
    if (!alloc.on) return { device: null, off: true, why: 'Attribution automatique désactivée', skipped: skipped };
    if (!el.length) return { device: null, why: 'Aucun iPhone ' + market + ' ne peut recevoir ce compte', skipped: skipped };
    var ch, why;
    if (alloc.mode === 'fill') {
      var under = el.filter(function (e) { return e.ratio * 100 < alloc.at; });
      if (under.length) {
        ch = under.sort(function (a, b) { return b.ratio - a.ratio || a.d.id.localeCompare(b.d.id); })[0];
        why = ch.n ? 'remplissage en cours, sous le seuil de ' + alloc.at + ' %' : 'iPhone vide, le prochain à remplir';
      } else {
        ch = el.slice().sort(function (a, b) { return a.ratio - b.ratio; })[0];
        why = 'tous les iPhone possibles ont passé ' + alloc.at + ' %, le moins rempli';
      }
    } else {
      ch = el.sort(function (a, b) { return a.ratio - b.ratio; })[0];
      why = 'le moins rempli des iPhone possibles';
    }
    return { device: ch.d, n: ch.n, max: ch.d.rules.max, why: why, skipped: skipped };
  }

  // ─── État des intégrations (localStorage, identique à shared-data) ─
  var API_KEY = 'scale.apiSim';
  function apiRead() {
    try { return JSON.parse(localStorage.getItem(API_KEY) || '{}'); } catch (e) { return {}; }
  }
  var api = {
    NAMES: { oc: 'OnlyChat', gms: 'GetMySocial' },
    STATES: [['ok', 'Connecté'], ['sync', 'Synchro en cours'], ['down', 'Injoignable'], ['auth', 'Clé refusée'], ['rate', 'Limite de requêtes']],
    get: function (svc) { return apiRead()[svc] || 'ok'; },
    set: function (svc, v) {
      var o = apiRead(); o[svc] = v;
      try { localStorage.setItem(API_KEY, JSON.stringify(o)); } catch (e) {}
      window.dispatchEvent(new Event('scale-api'));
    },
    lastSync: function (svc) { return Date.now() - (svc === 'oc' ? 2 * 36e5 + 14 * 6e4 : 47 * 6e4); },
    stale: function (svc) { var s = api.get(svc); return s === 'down' || s === 'auth' || s === 'rate'; },
    since: function (svc) {
      var m = Math.round((Date.now() - api.lastSync(svc)) / 6e4);
      return m < 60 ? m + ' min' : Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + String(m % 60).padStart(2, '0') : '');
    },
    retry: function (svc) { api.set(svc, 'sync'); setTimeout(function () { api.set(svc, 'ok'); }, 1600); },
    subscribe: function (fn) {
      window.addEventListener('scale-api', fn);
      window.addEventListener('storage', fn);
      return function () { window.removeEventListener('scale-api', fn); window.removeEventListener('storage', fn); };
    },
    banners: function (svcs, compact) {
      return svcs.map(function (svc) {
        var s = api.get(svc), N = api.NAMES[svc], ago = api.since(svc),
            t = new Date(api.lastSync(svc)),
            hh = String(t.getHours()).padStart(2, '0') + ':' + String(t.getMinutes()).padStart(2, '0');
        if (s === 'ok') return null;
        var B = {
          sync: ['ph ph-arrows-clockwise', 'Synchronisation ' + N + ' en cours', 'Les données se mettent à jour. Elles restent consultables pendant la synchro.', ['#8db4fd', 'rgba(141,180,253,.3)', 'rgba(141,180,253,.06)'], false, false],
          down: ['ph ph-cloud-slash', N + ' ne répond pas', "Données de la dernière synchro réussie, à " + hh + " (il y a " + ago + "). Les modifications vers " + N + " sont en attente.", ['#f5c77e', 'rgba(245,199,126,.32)', 'rgba(245,199,126,.06)'], true, true],
          auth: ['ph ph-key', 'Clé API ' + N + ' refusée', "La clé a expiré ou a été révoquée. Données figées à " + hh + " (il y a " + ago + ") tant qu'une nouvelle clé n'est pas enregistrée.", ['#fda4af', 'rgba(244,114,140,.35)', 'rgba(244,114,140,.07)'], false, true],
          rate: ['ph ph-hourglass-medium', 'Limite de requêtes ' + N + ' atteinte', "Nouvel essai automatique dans 4 min. Données de " + hh + " (il y a " + ago + ").", ['#f5c77e', 'rgba(245,199,126,.32)', 'rgba(245,199,126,.06)'], true, false]
        }[s];
        return {
          svc: svc, state: s, icon: B[0], title: B[1], text: compact ? '' : B[2], hasText: !compact,
          canRetry: B[4], retry: function () { api.retry(svc); }, retryLabel: 'Réessayer',
          settings: B[5], settingsHref: 'Module%20Parametres%20v1.dc.html',
          settingsLabel: s === 'auth' ? 'Mettre à jour la clé' : 'Paramètres', spin: s === 'sync',
          iconStyle: { fontSize: compact ? 15 : 18, flex: 'none', color: B[3][0] },
          titleStyle: { fontSize: compact ? 12 : 13, fontWeight: 600, color: B[3][0] },
          btnStyle: { display: 'flex', alignItems: 'center', gap: 6, height: 30, padding: '0 11px', borderRadius: 9, fontSize: 12, fontWeight: 600, color: B[3][0], border: '1px solid ' + B[3][1], cursor: 'pointer', whiteSpace: 'nowrap', textDecoration: 'none' },
          box: { display: 'flex', alignItems: compact ? 'center' : 'flex-start', gap: 12, padding: compact ? '8px 12px' : '12px 14px', borderRadius: 12, border: '1px solid ' + B[3][1], background: B[3][2] }
        };
      }).filter(Boolean);
    },
    dim: function (svcs) {
      var st = svcs.some(function (s) { return api.stale(s); });
      return st ? { opacity: .6, filter: 'saturate(.55)', transition: 'opacity .2s' } : { transition: 'opacity .2s' };
    }
  };

  // ─── Fournisseurs d'environnement (localStorage) ──────────────────
  var ENV_KEY = 'scale.envProviders';
  var envs = {
    PROVIDERS: [
      ['gologin', 'GoLogin', 'Navigateur web anti-détection', 'ph ph-globe'],
      ['geelark', 'GeeLark', 'Téléphone Android dans le cloud', 'ph ph-device-mobile-camera']
    ],
    all: function () {
      var d = null;
      try { d = JSON.parse(localStorage.getItem(ENV_KEY) || 'null'); } catch (e) {}
      if (!d) d = D.empty ? {} : { gologin: { last4: 'a91f' }, geelark: { last4: '33kd' } };
      return d;
    },
    get: function (k) { return envs.all()[k] || null; },
    set: function (k, v) {
      var d = envs.all();
      if (v) d[k] = v; else delete d[k];
      try { localStorage.setItem(ENV_KEY, JSON.stringify(d)); } catch (e) {}
      window.dispatchEvent(new Event('scale-api'));
    },
    connected: function () {
      var d = envs.all();
      return envs.PROVIDERS.filter(function (p) { return d[p[0]]; }).map(function (p) { return p[1]; });
    },
    ready: function () { return devices.length > 0 || envs.connected().length > 0; }
  };

  // ─── Mode "workspace vide" (simulation onboarding) ────────────────
  var EMPTY = false;
  try { EMPTY = localStorage.getItem('scale.emptySim') === '1'; } catch (e) {}

  // ─── Export synchrone : SCALE_DATA existe dès le chargement ────────
  var D = {
    personas: personas,
    accounts: accounts,
    devices: devices,
    behaviors: behaviors,
    behaviorParams: behaviorParams,
    drawMode: drawMode,
    alloc: alloc,
    slots: slots,
    scenarios: scenarios,
    campaigns: campaigns,
    collections: collections,
    licenses: licenses,
    ocAccounts: ocAccounts,
    api: api,
    envs: envs,
    empty: EMPTY,
    _live: !EMPTY,  // flag : données réelles (pas démo) → les seed functions retournent []
    _loaded: false,
    _error: null,

    // Lookups
    persona: function (id) { return personas.find(function (p) { return p.id === id || p.prsId === id; }) || null; },
    account: function (handle) { return accounts.find(function (x) { return x.handle === handle; }) || null; },
    accountsOf: function (pid) { return accounts.filter(function (a) { return a.persona === pid; }); },
    accountPlat: function (handle) { var a = D.account(handle); return a ? a.plat : null; },
    device: function (id) { return devices.find(function (d) { return d.id === id; }) || null; },
    pickDevice: pickDevice,

    // Onboarding (simulation)
    setEmpty: function (v) {
      try {
        localStorage.setItem('scale.emptySim', v ? '1' : '0');
        localStorage.removeItem('scale.envProviders');
        localStorage.removeItem('scale.emptyPersonas');
        localStorage.removeItem('scale.empty.accounts');
        localStorage.removeItem('scale.empty.devices');
      } catch (e) {}
      location.reload();
    },
    saveEmpty: function (kind, list) {
      if (!EMPTY) return;
      var EMPTY_KEYS = { personas: 'scale.emptyPersonas', accounts: 'scale.empty.accounts', devices: 'scale.empty.devices' };
      var EMPTY_ARR = { personas: personas, accounts: accounts, devices: devices };
      if (!EMPTY_KEYS[kind]) return;
      var arr = EMPTY_ARR[kind]; arr.length = 0;
      list.forEach(function (x) { arr.push(x); });
      try { localStorage.setItem(EMPTY_KEYS[kind], JSON.stringify(list)); } catch (e) {}
      window.dispatchEvent(new Event('scale-api'));
    }
  };

  window.SCALE_DATA = D;

  // ─── Chargement async des données réelles ──────────────────────────
  function populate(arr, items) {
    arr.length = 0;
    items.forEach(function (x) { arr.push(x); });
  }

  function computeDeviceRules() {
    devices.forEach(function (d) {
      var ps = [];
      accounts.forEach(function (a) {
        if (a.device === d.id && ps.indexOf(a.persona) < 0) ps.push(a.persona);
      });
      d.rules.personas = ps;
    });
  }

  function loadData() {
    if (EMPTY) {
      // En mode vide, ne pas charger l'API. Restaurer les données localStorage si présentes.
      var EMPTY_KEYS = { personas: 'scale.emptyPersonas', accounts: 'scale.empty.accounts', devices: 'scale.empty.devices' };
      var EMPTY_ARR = { personas: personas, accounts: accounts, devices: devices };
      Object.keys(EMPTY_KEYS).forEach(function (k) {
        try {
          (JSON.parse(localStorage.getItem(EMPTY_KEYS[k]) || '[]') || []).forEach(function (x) {
            EMPTY_ARR[k].push(x);
          });
        } catch (e) {}
      });
      D._loaded = true;
      return;
    }

    try {
      // Fetch synchrone — les données DOIVENT être présentes avant le rendu des templates
      var rawPersonas    = apiFetchSync('/personas');
      var rawComptes     = apiFetchSync('/comptes');
      var rawIphones     = apiFetchSync('/iphones');
      var rawPresets     = apiFetchSync('/presets');
      var rawScenarios   = apiFetchSync('/scenarios');
      var rawPlages      = apiFetchSync('/scenarios/plages');
      var rawCollections = apiFetchSync('/posting/collections');
      var rawCampagnes   = apiFetchSync('/posting/campagnes');
      var rawProxies     = apiFetchSync('/proxies');

      // Map proxy par ID pour lookup rapide
      var proxiesMap = {};
      (Array.isArray(rawProxies) ? rawProxies : []).forEach(function (p) { proxiesMap[p.id] = p; });

      // Transformer et peupler
      populate(personas,   (Array.isArray(rawPersonas)    ? rawPersonas    : []).map(xPersona));
      populate(accounts,   (Array.isArray(rawComptes)     ? rawComptes     : []).map(xCompte));
      populate(devices,    (Array.isArray(rawIphones)     ? rawIphones     : []).map(function (d) { return xDevice(d, proxiesMap); }));
      populate(behaviors,  (Array.isArray(rawPresets)     ? rawPresets     : []).map(xPreset));
      populate(scenarios,  (Array.isArray(rawScenarios)   ? rawScenarios   : []).map(xScenario));
      populate(slots,      (Array.isArray(rawPlages)      ? rawPlages      : []).map(xSlot));
      populate(collections,(Array.isArray(rawCollections) ? rawCollections : []).map(xCollection));
      populate(campaigns,  (Array.isArray(rawCampagnes)   ? rawCampagnes   : []).map(xCampaign));

      // Calculer les règles d'attribution iPhone ↔ comptes
      computeDeviceRules();

      // Déterminer si le workspace est vide
      D.empty = personas.length === 0;

      D._loaded = true;
      D._error = null;

      console.log('[Scale Lab] Données chargées :', personas.length, 'personas,', accounts.length, 'comptes,', devices.length, 'iPhones');

    } catch (err) {
      console.error('[Scale Lab] Erreur de chargement API :', err);
      D._error = err;
      D.empty = true;
      D._loaded = true;
    }
  }

  // Charger immédiatement (synchrone) — les données sont prêtes avant que support.js ne parse le DOM
  loadData();
})();
