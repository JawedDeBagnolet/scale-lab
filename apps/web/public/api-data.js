// api-data.js — Charge les donnees reelles du backend Scale Lab.
// SCALE_DATA existe immediatement (synchrone), les modules chargent
// leurs donnees specifiques via D.loadModule('nom').
(function () {
  'use strict';

  // ─── Config ──────────────────────────────────────────────────────────
  var API_BASE = 'https://api.scalelab.win/api';
  var TOKEN = (function () {
    try { return localStorage.getItem('sl_api_token'); } catch (e) { return null; }
  })() || '75640332d36f253e8debecbcc6dba4d0eebfd9fafaeac96812b67593d77886b7';

  // ─── HTTP Helpers ────────────────────────────────────────────────────

  // GET synchrone — retourne le JSON parse ou [] en cas d'erreur
  function apiFetchSync(path) {
    try {
      var x = new XMLHttpRequest();
      x.open('GET', API_BASE + path, false);
      x.setRequestHeader('Authorization', 'Bearer ' + TOKEN);
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

  // POST synchrone — retourne l'objet cree ou null
  function apiPostSync(path, data) {
    try {
      var x = new XMLHttpRequest();
      x.open('POST', API_BASE + path, false);
      x.setRequestHeader('Authorization', 'Bearer ' + TOKEN);
      x.setRequestHeader('Content-Type', 'application/json');
      x.send(JSON.stringify(data));
      if (x.status >= 200 && x.status < 300) {
        return JSON.parse(x.responseText);
      }
      console.warn('[Scale Lab] POST ' + path + ' → ' + x.status, x.responseText);
    } catch (e) {
      console.warn('[Scale Lab] Erreur POST ' + path + ' :', e);
    }
    return null;
  }

  // PATCH synchrone — retourne l'objet mis a jour ou null
  function apiPatchSync(path, data) {
    try {
      var x = new XMLHttpRequest();
      x.open('PATCH', API_BASE + path, false);
      x.setRequestHeader('Authorization', 'Bearer ' + TOKEN);
      x.setRequestHeader('Content-Type', 'application/json');
      x.send(JSON.stringify(data));
      if (x.status >= 200 && x.status < 300) {
        return JSON.parse(x.responseText);
      }
      console.warn('[Scale Lab] PATCH ' + path + ' → ' + x.status, x.responseText);
    } catch (e) {
      console.warn('[Scale Lab] Erreur PATCH ' + path + ' :', e);
    }
    return null;
  }

  // DELETE synchrone — retourne true/false
  function apiDeleteSync(path) {
    try {
      var x = new XMLHttpRequest();
      x.open('DELETE', API_BASE + path, false);
      x.setRequestHeader('Authorization', 'Bearer ' + TOKEN);
      x.send();
      return x.status >= 200 && x.status < 300;
    } catch (e) {
      console.warn('[Scale Lab] Erreur DELETE ' + path + ' :', e);
    }
    return false;
  }

  // PUT synchrone — retourne l'objet ou null
  function apiPutSync(path, data) {
    try {
      var x = new XMLHttpRequest();
      x.open('PUT', API_BASE + path, false);
      x.setRequestHeader('Authorization', 'Bearer ' + TOKEN);
      x.setRequestHeader('Content-Type', 'application/json');
      x.send(JSON.stringify(data));
      if (x.status >= 200 && x.status < 300) {
        return JSON.parse(x.responseText);
      }
      console.warn('[Scale Lab] PUT ' + path + ' -> ' + x.status, x.responseText);
    } catch (e) {
      console.warn('[Scale Lab] Erreur PUT ' + path + ' :', e);
    }
    return null;
  }

  // Async fetch (pour les appels non-bloquants)
  function apiAsync(method, path, data) {
    var opts = {
      method: method,
      headers: { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json' }
    };
    if (data) opts.body = JSON.stringify(data);
    return fetch(API_BASE + path, opts)
      .then(function (r) { return r.json(); })
      .catch(function (e) { console.warn('[Scale Lab] Async ' + method + ' ' + path + ' :', e); return null; });
  }

  // Helper : s'assurer qu'on a un array
  function safe(v) { return Array.isArray(v) ? v : []; }

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
      device: c.device_id || null,
      proxy: c.proxy_id || null,
      env: c.env || null,
      sessions: c.sessions || 0,
      follows: c.follows || 0,
      created: c.created_at
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
      telemetry: d.telemetry || {},
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
      plat: s.plateforme || null,
      slots: s.slots || [],
      steps: s.steps || [],
      loop: s.loop || false,
      active: s.active !== false,
      desc: s.description || ''
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
      captions: typeof c.captions === 'number' ? c.captions : (Array.isArray(c.captions) ? c.captions.length : 0),
      mediaIds: c.media_ids || [],
      created: c.created_at,
      updated: c.updated_at
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
      scenarios: c.scenarios || [],
      waves: c.waves || [],
      planning: c.planning || {},
      created: c.created_at,
      updated: c.updated_at
    };
  }

  function xProxy(p) {
    return {
      id: p.id,
      pool: p.pool || '',
      type: p.type || '',
      iphone: p.iphone_id || null,
      ip: p.ip || '',
      country: p.country || '',
      latency: p.latency_ms || 0,
      status: p.status || 'online',
      blacklists: p.blacklists || [],
      uptime: p.availability_7d != null ? p.availability_7d : 1,
      created: p.created_at
    };
  }

  function xTarget(t) {
    return {
      id: t.id,
      u: t.handle,
      name: t.handle,
      plat: t.plateforme,
      market: t.market || 'FR',
      niche: t.niche_id || null,
      status: t.status || 'ok',
      src: t.source || 'manual',
      added: t.created_at,
      checked: t.updated_at
    };
  }

  function xRun(r) {
    return {
      id: r.id,
      sc: r.scenario_id,
      accs: r.comptes || [],
      cur: r.current_step || 0,
      status: r.status || 'pending',
      blocked: r.blocked_accounts || [],
      journal: r.journal || [],
      startAt: r.started_at || null,
      endAt: r.finished_at || null,
      created: r.created_at
    };
  }

  function xEvent(e) {
    return {
      id: e.id,
      t: new Date(e.timestamp).getTime(),
      mod: e.module,
      type: e.event_type,
      lvl: e.level || 'info',
      target: e.target || '',
      cause: e.cause || '',
      code: e.code || '',
      msg: e.message,
      meta: e.meta || null,
      key: e.module + ':' + e.event_type + ':' + (e.target || '')
    };
  }

  function xIncident(inc) {
    return {
      key: inc.id,
      id: inc.id,
      mod: inc.module,
      type: inc.event_type,
      lvl: 'error',
      title: inc.event_type,
      target: inc.target || '',
      count: inc.event_count || 0,
      first: inc.first_seen ? new Date(inc.first_seen).getTime() : 0,
      last: inc.last_seen ? new Date(inc.last_seen).getTime() : 0,
      status: inc.status || 'open',
      solutions: inc.solutions || [],
      causes: [],
      events: inc.related_events || [],
      meta: inc.meta || null
    };
  }

  function xAlertRule(r) {
    return {
      id: r.id,
      mod: r.module,
      type: r.event_type,
      on: r.tg_enabled !== false,
      th: r.threshold_errors || 3,
      thActions: r.threshold_actions || 10,
      created: r.created_at
    };
  }

  function xMedia(m) {
    return {
      id: m.id,
      persona: m.persona_id || null,
      type: m.media_type || 'image',
      url: m.url || '',
      dur: m.duration || 0,
      tags: m.tags || [],
      folder: m.folder || '',
      used: m.used || false,
      added: m.created_at
    };
  }

  function xTemplate(t) {
    return {
      id: t.id,
      name: t.name,
      persona: t.persona_id || null,
      plat: t.plateforme || 'ig',
      type: t.template_type || 'post',
      layers: t.layers || [],
      variables: t.variables || {},
      collection: t.collection_id || null,
      created: t.created_at,
      updated: t.updated_at
    };
  }

  function xPublication(p) {
    return {
      id: p.id,
      acc: p.compte_id,
      camp: p.campagne_id || null,
      media: p.media_id || null,
      caption: p.caption || '',
      date: p.scheduled_at || null,
      status: p.status || 'planned',
      postId: p.platform_post_id || null,
      created: p.created_at,
      updated: p.updated_at
    };
  }

  function xTrackedLink(l) {
    return {
      id: l.id,
      dom: l.domain_id || null,
      slug: l.slug || '',
      type: l.link_type || 'direct',
      dest: l.destination || '',
      plat: l.plateforme || '',
      persona: l.persona_id || null,
      acc: l.compte_id || null,
      active: l.active !== false,
      group: l.group_name || null,
      created: l.created_at,
      updated: l.updated_at
    };
  }

  function xDomain(d) {
    return {
      id: d.id,
      host: d.host,
      max: d.max_active_links || 500,
      alertAt: d.alert_threshold || 450,
      created: d.created_at,
      updated: d.updated_at
    };
  }

  function xClickEvent(c) {
    return {
      id: c.id,
      link: c.link_id,
      at: c.clicked_at,
      country: c.country || '',
      city: c.city || '',
      device: c.device || '',
      browser: c.browser || '',
      referrer: c.referrer || ''
    };
  }

  function xFan(f) {
    return {
      id: f.id,
      cr: f.creator_id,
      pseudo: f.pseudo,
      plat: f.platform_origin || '',
      acc: f.compte_id || null,
      joined: f.joined_at,
      spent: f.total_spent || 0,
      lastActive: f.last_activity || null,
      note: f.notes || '',
      created: f.created_at
    };
  }

  function xTransaction(t) {
    var d = t.timestamp ? new Date(t.timestamp) : new Date();
    return {
      id: t.id,
      fan: t.fan_id,
      cr: t.creator_id,
      type: t.transaction_type || 'tip',
      amount: t.amount || 0,
      script: t.script_id || null,
      acc: t.compte_id || null,
      d: d.toISOString().slice(0, 10),
      h: d.getHours(),
      at: t.timestamp,
      created: t.created_at
    };
  }

  function xScript(s) {
    return {
      id: s.id,
      group: s.script_group_id || null,
      folder: s.folder || '',
      active: s.active !== false,
      priority: s.priority || false,
      steps: s.steps || [],
      stats: s.stats || {},
      created: s.created_at,
      updated: s.updated_at
    };
  }

  function xVeilleSource(s) {
    return {
      id: s.id,
      u: s.handle,
      name: s.handle,
      plat: s.plateforme,
      niche: s.niche_id || null,
      active: s.active !== false,
      lastChecked: s.last_checked || null,
      created: s.created_at,
      updated: s.updated_at
    };
  }

  function xInspiration(i) {
    return {
      id: i.id,
      source: i.source_id,
      url: i.url || '',
      mediaType: i.media_type || 'image',
      caption: i.caption || '',
      engagement: i.engagement || 0,
      status: i.status || 'new',
      savedAt: i.saved_at || null,
      created: i.created_at
    };
  }

  function xFavorite(f) {
    return {
      id: f.id,
      inspiration: f.inspiration_id,
      album: f.album_id || null,
      notes: f.notes || '',
      created: f.created_at
    };
  }

  function xSnipe(s) {
    return {
      id: s.id,
      inspiration: s.inspiration_id,
      persona: s.target_persona_id || null,
      priority: s.priority || 'medium',
      status: s.status || 'pending',
      due: s.due_date || null,
      created: s.created_at,
      updated: s.updated_at
    };
  }

  function xAlbum(a) {
    return {
      id: a.id,
      name: a.name,
      desc: a.description || '',
      persona: a.persona_id || null,
      created: a.created_at,
      updated: a.updated_at
    };
  }

  function xDailyStat(s) {
    return {
      id: s.id,
      acc: s.compte_id,
      date: s.date,
      followers: s.followers || 0,
      gained: s.gained || 0,
      lost: s.lost || 0,
      reach: s.reach || 0,
      impressions: s.impressions || 0,
      engagements: s.engagements || 0,
      profileVisits: s.profile_visits || 0,
      bioClicks: s.bio_clicks || 0,
      storyViews: s.story_views || 0,
      postsPublished: s.posts_published || 0,
      storiesPublished: s.stories_published || 0,
      availability: s.availability != null ? s.availability : 1,
      netGain: s.net_gain,
      engRate: s.engagement_rate,
      avgImpr: s.avg_impressions_per_post,
      convRate: s.conversion_rate
    };
  }

  function xWorkspace(w) {
    return {
      name: w.name || 'Scale Lab',
      currency: w.currency || 'EUR',
      timezone: w.timezone || 'Europe/Paris',
      oc: w.oc || { connected: false },
      gms: w.gms || { connected: false },
      tg: w.tg || { connected: false },
      envProviders: w.env_providers || {},
      notifications: w.notifications || {},
      updated: w.updated_at
    };
  }

  // ─── behaviorParams (config statique, identique a shared-data.js) ──
  var behaviorParams = {
    labels: {
      like: ['Like', 'Probabilite de liker un post vu'],
      comments: ['Lire les commentaires', "Probabilite d'ouvrir les commentaires d'un post"],
      follow: ['Follow', 'Probabilite de suivre un profil visite'],
      cursor: ['Lecture au curseur', 'Probabilite que le curseur suive le texte ligne par ligne'],
      target: ['Visiter une target', "Quand un post vient d'une target non suivie, probabilite d'ouvrir son profil"],
      lambda: ['Visiter un compte lambda', 'Probabilite de visiter un profil hors cibles'],
      scrollback: ['Scroll-back', "Probabilite de remonter d'un post pour le relire"],
      openPost: ['Ouvrir un post', "Probabilite d'ouvrir un post en vue detaillee"],
      likeComment: ['Liker un commentaire', "Dans un post ouvert, probabilite de liker un commentaire"],
      commentAuthor: ['Profil auteur commentaire', "Apres avoir like un commentaire, probabilite de visiter le profil de l'auteur"],
      story: ['Regarder les stories', "Probabilite d'ouvrir les stories en haut du feed"],
      save: ['Enregistrer un post', "Probabilite d'enregistrer un post vu"]
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

  // ─── Donnees : core (chargees au demarrage) ───────────────────────
  var personas    = [];
  var accounts    = [];
  var devices     = [];
  var behaviors   = [];
  var slots       = [];
  var scenarios   = [];
  var campaigns   = [];
  var collections = [];
  var proxies     = [];
  var licenses    = [];
  var ocAccounts  = [];
  var alloc       = { on: true, mode: 'fill', at: 80 };
  var drawMode    = { x: 'weighted', ig: 'uniform', th: 'uniform' };

  // ─── Donnees : module-specific (chargees via loadModule) ──────────
  var targets       = [];
  var runs          = [];
  var logEvents     = [];
  var logIncidents  = [];
  var alertRules    = [];
  var medias        = [];
  var templates     = [];
  var publications  = [];
  var trackedLinks  = [];
  var domains       = [];
  var fans          = [];
  var transactions  = [];
  var crmScripts    = [];
  var veilleSources = [];
  var inspirations  = [];
  var vFavorites    = [];
  var snipes        = [];
  var veilleAlbums  = [];
  var dailyStats    = [];

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
      else if (R.plats.indexOf(plat) < 0) why = (PLN[plat] || plat) + ' non autorise';
      else if (R.personas.length && R.personas.indexOf(persona) < 0) why = 'persona non autorisee';
      else if (n >= R.max) why = 'plein · ' + n + '/' + R.max;
      if (why) skipped.push({ name: d.name, reason: why });
      else el.push({ d: d, n: n, ratio: n / R.max });
    });
    if (!alloc.on) return { device: null, off: true, why: 'Attribution automatique desactivee', skipped: skipped };
    if (!el.length) return { device: null, why: 'Aucun iPhone ' + market + ' ne peut recevoir ce compte', skipped: skipped };
    var ch, why;
    if (alloc.mode === 'fill') {
      var under = el.filter(function (e) { return e.ratio * 100 < alloc.at; });
      if (under.length) {
        ch = under.sort(function (a, b) { return b.ratio - a.ratio || a.d.id.localeCompare(b.d.id); })[0];
        why = ch.n ? 'remplissage en cours, sous le seuil de ' + alloc.at + ' %' : 'iPhone vide, le prochain a remplir';
      } else {
        ch = el.slice().sort(function (a, b) { return a.ratio - b.ratio; })[0];
        why = 'tous les iPhone possibles ont passe ' + alloc.at + ' %, le moins rempli';
      }
    } else {
      ch = el.sort(function (a, b) { return a.ratio - b.ratio; })[0];
      why = 'le moins rempli des iPhone possibles';
    }
    return { device: ch.d, n: ch.n, max: ch.d.rules.max, why: why, skipped: skipped };
  }

  // ─── Etat des integrations (backend reel) ──────────────────────────
  var _apiState = { oc: 'none', gms: 'none' };
  var _apiSync = {};  // timestamps de derniere synchro

  // Mise a jour de l'etat depuis les donnees workspace
  function apiUpdateFromWorkspace(ws) {
    if (!ws) return;
    if (ws.oc) {
      _apiState.oc = ws.oc.connected ? 'ok' : (ws.oc.key_tail ? 'auth' : 'none');
      if (ws.oc.last_sync) _apiSync.oc = new Date(ws.oc.last_sync).getTime();
    }
    if (ws.gms) {
      _apiState.gms = ws.gms.connected ? 'ok' : (ws.gms.key_tail ? 'auth' : 'none');
      if (ws.gms.last_sync) _apiSync.gms = new Date(ws.gms.last_sync).getTime();
    }
  }

  var api = {
    NAMES: { oc: 'OnlyChat', gms: 'GetMySocial' },
    STATES: [['ok', 'Connecte'], ['sync', 'Synchro en cours'], ['down', 'Injoignable'], ['auth', 'Cle refusee'], ['rate', 'Limite de requetes'], ['none', 'Non configure']],
    get: function (svc) { return _apiState[svc] || 'none'; },
    set: function (svc, v) {
      _apiState[svc] = v;
      window.dispatchEvent(new Event('scale-api'));
    },
    lastSync: function (svc) { return _apiSync[svc] || 0; },
    stale: function (svc) { var s = api.get(svc); return s === 'down' || s === 'auth' || s === 'rate'; },
    since: function (svc) {
      var ts = api.lastSync(svc);
      if (!ts) return 'jamais';
      var m = Math.round((Date.now() - ts) / 6e4);
      return m < 1 ? 'a l\'instant' : m < 60 ? m + ' min' : Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + String(m % 60).padStart(2, '0') : '');
    },
    retry: function (svc) {
      api.set(svc, 'sync');
      apiAsync('POST', '/integrations/' + svc + '/test', {}).then(function (r) {
        if (r && r.ok) { api.set(svc, 'ok'); _apiSync[svc] = Date.now(); }
        else api.set(svc, 'down');
      });
    },
    // Test a key (async, returns promise)
    testKey: function (svc, key) {
      return apiAsync('POST', '/integrations/' + svc + '/test', { api_key: key || null });
    },
    // Save a key (async, returns promise)
    saveKey: function (svc, key) {
      return apiAsync('PUT', '/integrations/' + svc + '/key', { api_key: key });
    },
    // Remove a key (async)
    removeKey: function (svc) {
      return apiAsync('DELETE', '/integrations/' + svc + '/key', null);
    },
    // Get live status (async)
    getStatus: function (svc) {
      return apiAsync('GET', '/integrations/' + svc + '/status');
    },
    // GMS data proxies
    gmsLinks: function (limit, cursor) {
      var q = '?limit=' + (limit || 25);
      if (cursor) q += '&cursor=' + encodeURIComponent(cursor);
      return apiAsync('GET', '/integrations/gms/links' + q);
    },
    gmsAnalytics: function (timeframe) {
      return apiAsync('GET', '/integrations/gms/analytics/overview?timeframe=' + (timeframe || 'today'));
    },
    // OC data proxies
    ocCreators: function () {
      return apiAsync('GET', '/integrations/oc/creators');
    },
    subscribe: function (fn) {
      window.addEventListener('scale-api', fn);
      return function () { window.removeEventListener('scale-api', fn); };
    },
    banners: function (svcs, compact) {
      return svcs.map(function (svc) {
        var s = api.get(svc), N = api.NAMES[svc], ts = api.lastSync(svc), ago = api.since(svc);
        var t = ts ? new Date(ts) : new Date();
        var hh = String(t.getHours()).padStart(2, '0') + ':' + String(t.getMinutes()).padStart(2, '0');
        if (s === 'ok' || s === 'none') return null;
        var B = {
          sync: ['ph ph-arrows-clockwise', 'Synchronisation ' + N + ' en cours', 'Les donnees se mettent a jour. Elles restent consultables pendant la synchro.', ['#8db4fd', 'rgba(141,180,253,.3)', 'rgba(141,180,253,.06)'], false, false],
          down: ['ph ph-cloud-slash', N + ' ne repond pas', "Donnees de la derniere synchro reussie, a " + hh + " (il y a " + ago + "). Les modifications vers " + N + " sont en attente.", ['#f5c77e', 'rgba(245,199,126,.32)', 'rgba(245,199,126,.06)'], true, true],
          auth: ['ph ph-key', 'Cle API ' + N + ' refusee', "La cle a expire ou a ete revoquee. Donnees figees a " + hh + " (il y a " + ago + ") tant qu'une nouvelle cle n'est pas enregistree.", ['#fda4af', 'rgba(244,114,140,.35)', 'rgba(244,114,140,.07)'], false, true],
          rate: ['ph ph-hourglass-medium', 'Limite de requetes ' + N + ' atteinte', "Nouvel essai automatique dans 4 min. Donnees de " + hh + " (il y a " + ago + ").", ['#f5c77e', 'rgba(245,199,126,.32)', 'rgba(245,199,126,.06)'], true, false]
        }[s];
        if (!B) return null;
        return {
          svc: svc, state: s, icon: B[0], title: B[1], text: compact ? '' : B[2], hasText: !compact,
          canRetry: B[4], retry: function () { api.retry(svc); }, retryLabel: 'Reessayer',
          settings: B[5], settingsHref: 'Module%20Parametres%20v1.dc.html',
          settingsLabel: s === 'auth' ? 'Mettre a jour la cle' : 'Parametres', spin: s === 'sync',
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
      ['gologin', 'GoLogin', 'Navigateur web anti-detection', 'ph ph-globe'],
      ['geelark', 'GeeLark', 'Telephone Android dans le cloud', 'ph ph-device-mobile-camera']
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

  // ─── Export synchrone : SCALE_DATA existe des le chargement ────────
  var D = {
    // Core arrays (chargees au demarrage)
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
    proxies: proxies,
    licenses: licenses,
    ocAccounts: ocAccounts,
    api: api,
    envs: envs,

    // Module-specific arrays (chargees via loadModule)
    targets: targets,
    runs: runs,
    logEvents: logEvents,
    logIncidents: logIncidents,
    alertRules: alertRules,
    medias: medias,
    templates: templates,
    publications: publications,
    trackedLinks: trackedLinks,
    domains: domains,
    fans: fans,
    transactions: transactions,
    crmScripts: crmScripts,
    veilleSources: veilleSources,
    inspirations: inspirations,
    vFavorites: vFavorites,
    snipes: snipes,
    veilleAlbums: veilleAlbums,
    dailyStats: dailyStats,

    // Overview/stats objects (populated via loadModule)
    logStats: null,
    statsOverview: null,
    crmOverview: null,
    postingOverview: null,
    dashboardStats: null,
    workspace: null,

    // Flags
    empty: EMPTY,
    _live: !EMPTY,
    _loaded: false,
    _error: null,

    // ── Core lookups ──
    persona: function (id) { return personas.find(function (p) { return p.id === id || p.prsId === id; }) || null; },
    account: function (handle) { return accounts.find(function (x) { return x.handle === handle; }) || null; },
    accountById: function (id) { return accounts.find(function (a) { return a.id === id; }) || null; },
    accountsOf: function (pid) { return accounts.filter(function (a) { return a.persona === pid; }); },
    accountPlat: function (handle) { var a = D.account(handle); return a ? a.plat : null; },
    device: function (id) { return devices.find(function (d) { return d.id === id; }) || null; },
    proxy: function (id) { return proxies.find(function (p) { return p.id === id; }) || null; },
    target: function (id) { return targets.find(function (t) { return t.id === id; }) || null; },
    fan: function (id) { return fans.find(function (f) { return f.id === id; }) || null; },
    scenario: function (id) { return scenarios.find(function (s) { return s.id === id; }) || null; },
    collection: function (id) { return collections.find(function (c) { return c.id === id; }) || null; },
    campaign: function (id) { return campaigns.find(function (c) { return c.id === id; }) || null; },
    pickDevice: pickDevice,

    // ── API helpers (write) ──
    apiPost: apiPostSync,
    apiPatch: apiPatchSync,
    apiPut: apiPutSync,
    apiDelete: apiDeleteSync,
    apiFetch: apiFetchSync,
    apiAsync: apiAsync,

    // ── Transforms (exposes pour les modules) ──
    x: {
      persona: xPersona, compte: xCompte, device: xDevice, preset: xPreset,
      scenario: xScenario, slot: xSlot, collection: xCollection, campaign: xCampaign,
      proxy: xProxy, target: xTarget, run: xRun, event: xEvent,
      incident: xIncident, alertRule: xAlertRule, media: xMedia,
      template: xTemplate, publication: xPublication,
      trackedLink: xTrackedLink, domain: xDomain, clickEvent: xClickEvent,
      fan: xFan, transaction: xTransaction, script: xScript,
      veilleSource: xVeilleSource, inspiration: xInspiration,
      favorite: xFavorite, snipe: xSnipe, album: xAlbum,
      dailyStat: xDailyStat, workspace: xWorkspace
    },

    // ── Module loader (lazy) ──
    loadModule: loadModule,
    refreshModule: function (name) { _moduleLoaded[name] = false; loadModule(name); },
    isModuleLoaded: function (name) { return !!_moduleLoaded[name]; },

    // ── Onboarding (simulation) ──
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

  // ─── Chargement ────────────────────────────────────────────────────
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

  // ── Chargement core (synchrone au demarrage) ──
  function loadData() {
    if (EMPTY) {
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
      var rawPersonas    = apiFetchSync('/personas');
      var rawComptes     = apiFetchSync('/comptes');
      var rawIphones     = apiFetchSync('/iphones');
      var rawPresets     = apiFetchSync('/presets');
      var rawScenarios   = apiFetchSync('/scenarios');
      var rawPlages      = apiFetchSync('/scenarios/plages');
      var rawCollections = apiFetchSync('/posting/collections');
      var rawCampagnes   = apiFetchSync('/posting/campagnes');
      var rawProxies     = apiFetchSync('/proxies');

      // Map proxy par ID pour lookup rapide dans xDevice
      var proxiesMap = {};
      safe(rawProxies).forEach(function (p) { proxiesMap[p.id] = p; });

      // Transformer et peupler les core arrays
      populate(personas,    safe(rawPersonas).map(xPersona));
      populate(accounts,    safe(rawComptes).map(xCompte));
      populate(devices,     safe(rawIphones).map(function (d) { return xDevice(d, proxiesMap); }));
      populate(behaviors,   safe(rawPresets).map(xPreset));
      populate(scenarios,   safe(rawScenarios).map(xScenario));
      populate(slots,       safe(rawPlages).map(xSlot));
      populate(collections, safe(rawCollections).map(xCollection));
      populate(campaigns,   safe(rawCampagnes).map(xCampaign));
      populate(proxies,     safe(rawProxies).map(xProxy));

      // Calculer les regles d'attribution iPhone ↔ comptes
      computeDeviceRules();

      D.empty = personas.length === 0;
      D._loaded = true;
      D._error = null;

      console.log('[Scale Lab] Core charge :', personas.length, 'personas,', accounts.length, 'comptes,', devices.length, 'iPhones,', proxies.length, 'proxies');

    } catch (err) {
      console.error('[Scale Lab] Erreur de chargement API :', err);
      D._error = err;
      D.empty = true;
      D._loaded = true;
    }
  }

  // ── Chargement module-specific (lazy, synchrone a la premiere demande) ──
  var _moduleLoaded = {};

  function loadModule(name) {
    if (EMPTY || _moduleLoaded[name]) return;
    _moduleLoaded[name] = true;

    try {
      switch (name) {

        case 'targets':
          populate(targets, safe(apiFetchSync('/targets')).map(xTarget));
          console.log('[Scale Lab] Module targets :', targets.length, 'targets');
          break;

        case 'scenarios':
          populate(runs, safe(apiFetchSync('/scenarios/runs/list')).map(xRun));
          console.log('[Scale Lab] Module scenarios :', runs.length, 'runs');
          break;

        case 'logs':
          populate(logEvents,    safe(apiFetchSync('/logs/events')).map(xEvent));
          populate(logIncidents, safe(apiFetchSync('/logs/incidents')).map(xIncident));
          populate(alertRules,   safe(apiFetchSync('/logs/rules')).map(xAlertRule));
          D.logStats = apiFetchSync('/logs/stats');
          if (!D.logStats || Array.isArray(D.logStats)) D.logStats = { total_events: 0, errors_24h: 0, open_incidents: 0, modules: {} };
          console.log('[Scale Lab] Module logs :', logEvents.length, 'events,', logIncidents.length, 'incidents');
          break;

        case 'stats':
          populate(dailyStats, safe(apiFetchSync('/stats')).map(xDailyStat));
          D.statsOverview = apiFetchSync('/stats/overview');
          if (!D.statsOverview || Array.isArray(D.statsOverview)) D.statsOverview = { total_followers: 0, avg_engagement_rate: 0, total_reach_30d: 0, best_day: null };
          console.log('[Scale Lab] Module stats :', dailyStats.length, 'daily stats');
          break;

        case 'veille':
          populate(veilleSources, safe(apiFetchSync('/veille/sources')).map(xVeilleSource));
          populate(inspirations,  safe(apiFetchSync('/veille/inspirations')).map(xInspiration));
          populate(vFavorites,    safe(apiFetchSync('/veille/favorites')).map(xFavorite));
          populate(snipes,        safe(apiFetchSync('/veille/snipes')).map(xSnipe));
          populate(veilleAlbums,  safe(apiFetchSync('/veille/albums')).map(xAlbum));
          console.log('[Scale Lab] Module veille :', veilleSources.length, 'sources,', inspirations.length, 'inspirations');
          break;

        case 'crm':
          populate(fans,         safe(apiFetchSync('/crm/fans')).map(xFan));
          populate(transactions, safe(apiFetchSync('/crm/transactions')).map(xTransaction));
          populate(crmScripts,   safe(apiFetchSync('/crm/scripts')).map(xScript));
          D.crmOverview = apiFetchSync('/crm/overview');
          if (!D.crmOverview || Array.isArray(D.crmOverview)) D.crmOverview = { total_fans: 0, total_revenue: 0, avg_ltv: 0, top_script: null };
          console.log('[Scale Lab] Module CRM :', fans.length, 'fans,', transactions.length, 'transactions,', crmScripts.length, 'scripts');
          break;

        case 'liens':
          populate(trackedLinks, safe(apiFetchSync('/liens')).map(xTrackedLink));
          populate(domains,      safe(apiFetchSync('/liens/domains')).map(xDomain));
          console.log('[Scale Lab] Module liens :', trackedLinks.length, 'liens,', domains.length, 'domaines');
          break;

        case 'posting':
          populate(medias,       safe(apiFetchSync('/posting/medias')).map(xMedia));
          populate(templates,    safe(apiFetchSync('/posting/templates')).map(xTemplate));
          populate(publications, safe(apiFetchSync('/posting/publications')).map(xPublication));
          D.postingOverview = apiFetchSync('/posting/overview');
          if (!D.postingOverview || Array.isArray(D.postingOverview)) D.postingOverview = { total_collections: 0, total_medias: 0, total_templates: 0, total_campagnes: 0, active_campagnes: 0, total_publications: 0, published: 0, planned: 0, failed: 0 };
          console.log('[Scale Lab] Module posting :', medias.length, 'medias,', templates.length, 'templates,', publications.length, 'publications');
          break;

        case 'dashboard':
          D.dashboardStats = apiFetchSync('/dashboard/stats');
          if (!D.dashboardStats || Array.isArray(D.dashboardStats)) D.dashboardStats = { total_personas: 0, total_comptes: 0, total_targets: 0, total_presets: 0, total_events: 0, errors_24h: 0, open_incidents: 0, comptes_ok: 0, comptes_error: 0 };
          console.log('[Scale Lab] Module dashboard : stats chargees');
          break;

        case 'settings':
          var raw = apiFetchSync('/settings');
          if (raw && !Array.isArray(raw)) {
            D.workspace = xWorkspace(raw);
            apiUpdateFromWorkspace(raw);
          } else {
            D.workspace = xWorkspace({});
          }
          console.log('[Scale Lab] Module settings : workspace charge, oc=' + api.get('oc') + ', gms=' + api.get('gms'));
          break;

        case 'proxies':
          // Proxies are already loaded in core, but module may want to refresh
          console.log('[Scale Lab] Module proxies :', proxies.length, 'proxies (deja charge)');
          break;

        case 'iphones':
          // Devices already loaded in core, nothing extra to fetch
          console.log('[Scale Lab] Module iphones :', devices.length, 'devices (deja charge)');
          break;

        default:
          console.warn('[Scale Lab] Module inconnu :', name);
      }
    } catch (err) {
      console.error('[Scale Lab] Erreur chargement module ' + name + ' :', err);
    }
  }

  // Charger immediatement (synchrone) — les core data sont pretes avant support.js
  loadData();
})();
