// Données de workspace partagées entre tous les modules.
// Source unique côté front : à remplacer par les réponses de l'API côté back-end.
(function () {
  var personas = [
    { id: 'lea', prsId: 'prs_8f3a2c91d4e7', first: 'Léa', last: 'Martin', color: '#8b7cf6', market: 'FR', city: 'Paris', age: 24, platforms: ['ig', 'th', 'x'], niches: ['fitness', 'gnd'], tg: 'Léa · Team' },
    { id: 'maya', prsId: 'prs_2b7e90a4c1f3', first: 'Maya', last: 'Laurent', color: '#5b8def', market: 'FR', city: 'Lyon', age: 26, platforms: ['ig', 'th'], niches: ['gnd', 'lifestyle'], tg: 'Maya · Studio' },
    { id: 'sofia', prsId: 'prs_c41d8e2f7a90', first: 'Sofia', last: 'Reyes', color: '#2dd4a8', market: 'US', city: 'Austin', age: 28, platforms: ['ig', 'x', 'tt'], niches: ['lifestyle', 'fitness'], tg: 'Sofia · Crew' },
    { id: 'clara', prsId: 'prs_91e0f3b5d28c', first: 'Clara', last: 'Vidal', color: '#f472b6', market: 'ES', city: 'Madrid', age: 23, platforms: ['ig', 'tt', 'sc'], niches: ['cosplay', 'petite'], tg: 'Clara · Team' },
    { id: 'nina', prsId: 'prs_5a6c2e8b0f14', first: 'Nina', last: 'Morel', color: '#f5b04c', market: 'FR', city: 'Bordeaux', age: 27, platforms: ['ig', 'th'], niches: ['alt', 'asmr'], tg: 'Nina · Studio' },
    { id: 'alba', prsId: 'prs_e7d19c3a64b2', first: 'Alba', last: 'Ortega', color: '#38bdf8', market: 'ES', city: 'Barcelone', age: 25, platforms: ['ig', 'sc'], niches: ['latina', 'curvy'], tg: null }
  ].map(function (p) { p.name = p.first + ' ' + p.last; return p; });

  var handles = {
    lea: ['lea.fitfr', 'lea.moves', 'leafit.daily', 'lea.gymfr', 'lea_coach', 'lea_x', 'lea.threads'],
    maya: ['maya.threads', 'maya.ig', 'maya.slow', 'mayadaily', 'maya_x', 'maya.home', 'maya.cafe'],
    sofia: ['sofia.rlx', 'sofia.us.ig', 'sofia.calm', 'sofiawell', 'sofia_x', 'sofia.glow', 'sofia.breathe'],
    clara: ['clara.ntv', 'clara.glow', 'clarabeauty', 'clara_x', 'clara.skin'],
    nina: ['nina.fr', 'nina.flow', 'ninayoga', 'nina_x', 'nina.mat', 'nina.zen', 'nina.om'],
    alba: ['alba.trip', 'alba.go', 'albatravel', 'alba_x', 'alba.wander', 'alba.maps', 'alba.sun', 'alba.road']
  };
  var accounts = []; var i = 0; var seed = 11; var rnd = function () { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  Object.keys(handles).forEach(function (pid) {
    handles[pid].forEach(function (h) {
      var plat = h.indexOf('_x') >= 0 ? 'x' : h.indexOf('threads') >= 0 ? 'th' : (i % 3 === 1 ? 'th' : 'ig');
      var r = rnd(); var workflow = r < .58 ? 'Actif' : r < .74 ? 'Warmup' : r < .9 ? 'Onboarding' : 'Pause'; var r2 = rnd();
      var status = h === 'clara.ntv' ? 'error' : workflow === 'Pause' ? 'idle' : r2 < .15 ? 'session' : r2 < .24 ? 'error' : 'idle';
      accounts.push({ id: 'acc_' + h.replace(/[^a-z0-9]/g, ''), handle: h, persona: pid, plat: plat, workflow: workflow, status: status }); i++;
    });
  });


  // ---- Comportements (presets), plages horaires, scénarios
  var behaviorParams = {
    labels: { like: ['Like', 'Probabilité de liker un post vu'], comments: ['Lire les commentaires', 'Probabilité d’ouvrir les commentaires d’un post'], follow: ['Follow', 'Probabilité de suivre un profil visité'], cursor: ['Lecture au curseur', 'Probabilité que le curseur suive le texte ligne par ligne'], target: ['Visiter une target', 'Quand un post vient d’une target non suivie, probabilité d’ouvrir son profil'], lambda: ['Visiter un compte lambda', 'Probabilité de visiter un profil hors cibles'], scrollback: ['Scroll-back', 'Probabilité de remonter d’un post pour le relire'], openPost: ['Ouvrir un post', 'Probabilité d’ouvrir un post en vue détaillée'], likeComment: ['Liker un commentaire', 'Dans un post ouvert, probabilité de liker un commentaire'], commentAuthor: ['Profil auteur commentaire', 'Après avoir liké un commentaire, probabilité de visiter le profil de l’auteur'], story: ['Regarder les stories', 'Probabilité d’ouvrir les stories en haut du feed'], save: ['Enregistrer un post', 'Probabilité d’enregistrer un post vu'] },
    lot1: ['like', 'comments', 'follow'],
    lot2: { x: ['cursor', 'target', 'lambda', 'scrollback', 'openPost', 'likeComment', 'commentAuthor'], ig: ['target', 'lambda', 'scrollback', 'openPost', 'likeComment', 'commentAuthor', 'story', 'save'], th: ['target', 'lambda', 'scrollback', 'openPost', 'likeComment', 'commentAuthor'] },
    types: { x: [['feed', 'Feed Home'], ['hybrid', 'Hybrid'], ['profile', 'Profil']], ig: [['feed', 'Feed'], ['reels', 'Reels'], ['profile', 'Profil']], th: [['feed', 'Feed'], ['hybrid', 'Hybrid'], ['profile', 'Profil']] }
  };
  function B(id, plat, icon, name, type, weight, vals, pauses) { var keys = behaviorParams.lot1.concat(behaviorParams.lot2[plat]); var p = {}; keys.forEach(function (k, i) { p[k] = vals[i]; }); return { id: id, plat: plat, icon: icon, name: name, type: type, weight: weight, p: p, pauses: pauses.map(function (x, i) { return { id: id + 'p' + i, label: x[0], min: x[1], max: x[2], prob: x[3] }; }) }; }
  var behaviors = [
    B('xb1', 'x', 'book-open', 'Lecteur discret', 'feed', 3, [12, 20, 2, 45, 10, 4, 15, 18, 6, 10], [['Lecture longue', 20, 60, 15], ['Distraction', 120, 300, 5]]),
    B('xb2', 'x', 'fire', 'Engagé', 'hybrid', 2, [35, 30, 8, 25, 30, 6, 10, 25, 15, 20], [['Respiration', 5, 15, 30]]),
    B('xb3', 'x', 'magnifying-glass', 'Fouineur de profils', 'profile', 1, [20, 25, 10, 30, 0, 8, 12, 35, 10, 25], [['Lecture de bio', 8, 25, 40], ['Distraction', 90, 240, 4]]),
    B('xb4', 'x', 'lightning', 'Scroll rapide', 'feed', 1, [8, 6, 1, 10, 5, 2, 5, 6, 2, 3], []),
    B('ib1', 'ig', 'sun-horizon', 'Flâneuse', 'feed', 2, [18, 15, 3, 12, 5, 10, 14, 4, 6, 30, 3], [['Pause café', 60, 180, 6]]),
    B('ib2', 'ig', 'film-strip', 'Reels en boucle', 'reels', 2, [25, 8, 2, 6, 3, 4, 5, 3, 2, 10, 6], [['Revoir un reel', 5, 20, 20]]),
    B('ib3', 'ig', 'target', 'Visite ciblée', 'profile', 1, [30, 20, 12, 40, 4, 6, 30, 8, 12, 15, 5], []),
    B('tb1', 'th', 'chat-circle-dots', 'Conversation', 'hybrid', 1, [28, 35, 6, 20, 5, 8, 30, 14, 18], [['Réflexion', 15, 45, 20]]),
    B('tb2', 'th', 'broadcast', 'Observateur', 'feed', 2, [10, 18, 2, 6, 3, 12, 10, 4, 4], [])
  ];
  // durées de session du preset : [min, max (minutes), poids] · tirage pondéré à chaque session
  var DUR = { xb1: [[8, 12, 3], [15, 25, 1]], xb2: [[12, 20, 2], [25, 40, 1]], xb3: [[6, 10, 1]], xb4: [[3, 6, 2], [8, 12, 1]], ib1: [[10, 18, 2], [20, 30, 1]], ib2: [[5, 10, 3], [15, 25, 1]], ib3: [], tb1: [[10, 20, 1]], tb2: [[6, 12, 2], [15, 20, 1]] };
  behaviors.forEach(function (b) { b.durations = (DUR[b.id] || []).map(function (x, i) { return { id: b.id + 'd' + i, min: x[0], max: x[1], weight: x[2] }; }); });
  // campagnes actives du module Posting (même source à terme)
  var campaigns = [
    { id: 'c1', name: 'Léa · Reels du matin', icon: 'sun-horizon', persona: 'lea', plat: 'ig', status: 'active', scenarios: ['sc1'] },
    { id: 'c2', name: 'Maya · Threads slow life', icon: 'coffee', persona: 'maya', plat: 'th', status: 'active', scenarios: [] },
    { id: 'c3', name: 'Sofia · US launch', icon: 'rocket-launch', persona: 'sofia', plat: 'ig', status: 'paused', scenarios: ['sc1'] },
    { id: 'c4', name: 'Nina · Yoga du soir', icon: 'moon-stars', persona: 'nina', plat: 'ig', status: 'done', scenarios: [] }
  ];
  var drawMode = { x: 'weighted', ig: 'uniform', th: 'uniform' };
  var slots = [
    { id: 's1', name: 'Matin', icon: 'sun-horizon', days: [1, 2, 3, 4, 5], ranges: [['08:30', '11:30']] },
    { id: 's2', name: 'Soirée', icon: 'moon-stars', days: [1, 2, 3, 4, 5, 6, 7], ranges: [['18:00', '22:30']] },
    { id: 's3', name: 'Pause déj', icon: 'coffee', days: [1, 2, 3, 4, 5], ranges: [['12:00', '13:45']] },
    { id: 's4', name: 'Week-end', icon: 'calendar-dots', days: [6, 7], ranges: [['10:00', '13:00'], ['16:00', '21:00']] }
  ];
  // origin : spont (lancé à la main) | login | creation (proposé au login / à la création des comptes) · couple : démarre juste après l'origine
  // steps : [plateforme, [[action, valeurs, presets]], délai]
  var scenarios = [
    { id: 'sc1', name: 'Warmup iPhone J1–J7', icon: 'fire', origin: 'creation', couple: true, slots: ['s1', 's2'], steps: [
      ['ig_iph', [['igi_conf', { photo: 'Album persona' }]]],
      ['ig_iph', [['igi_feed', { dur: 8 }, ['ib1']]], { mode: 'rand', a: 1, b: 3, u2: 'h' }],
      ['ig_iph', [['igi_reels', { reels: 10 }, ['ib2']]], { mode: 'at', at: '19:00' }],
      ['ig_iph', [['igi_feed', { dur: 15 }, ['ib1']], ['igi_reels', { reels: 20 }, ['ib2']]], { mode: 'dur', n: 1, u: 'd' }],
      ['ig_iph', [['igi_prof', { nProfiles: 6 }, ['ib3']]], { mode: 'rand', a: 2, b: 4, u2: 'h' }],
      ['ig_iph', [['igi_camp', { campaign: 'Campagnes reliées au scénario' }]], { mode: 'at', at: '09:00', day: 1 }] ] },
    { id: 'sc2', name: 'Setup profil Threads', icon: 'user-circle-gear', origin: 'login', couple: true, slots: [], steps: [
      ['th_web', [['th_conf', { photoTh: 'Importer depuis IG' }]]],
      ['th_web', [['th_feed', { dur: 12 }]], { mode: 'dur', n: 30, u: 'm' }],
      ['th_web', [['th_post', {}]], { mode: 'rand', a: 2, b: 5, u2: 'h' }],
      ['th_iph', [['thi_camp', { campaign: 'Campagnes de la persona' }]], { mode: 'dur', n: 1, u: 'd' }] ] },
    { id: 'sc3', name: 'Warmup Twitter', icon: 'lightning', origin: 'login', couple: false, slots: ['s1', 's3', 's2'], steps: [
      ['x_web', [['x_warmup', { dur: 15 }, ['xb1']]]],
      ['x_web', [['x_hybrid', { dur: 20 }, ['xb2', 'xb4']]], { mode: 'rand', a: 3, b: 6, u2: 'h' }],
      ['x_web', [['x_profil', { nProfiles: 8 }, ['xb3']]], { mode: 'dur', n: 1, u: 'd' }] ] },
    { id: 'sc4', name: 'Relance stories', icon: 'film-strip', origin: 'spont', couple: false, slots: ['s2'], steps: [
      ['stories', [['st_cl', {}]]],
      ['stories', [['st_hl', {}]], { mode: 'dur', n: 2, u: 'h' }] ] },
    { id: 'sc5', name: 'Session du soir', icon: 'moon-stars', origin: 'spont', couple: false, slots: ['s2'], steps: [
      ['ig_iph', [['igi_feed', { dur: 12 }, ['ib1']], ['igi_reels', { reels: 15 }, ['ib2']]]],
      ['ig_iph', [['igi_prof', { nProfiles: 3 }]], { mode: 'rand', a: 20, b: 50, u2: 'm' }] ] }
  ];

  var collections = [
    { id: 'col1', name: 'Léa · Reels salle de sport', type: 'assembled', persona: 'lea', plat: 'ig', ptype: 'reel', platLabel: 'Instagram · Reel', captions: 0 },
    { id: 'col2', name: 'Léa · Accroches du matin', type: 'variable', persona: 'lea', plat: 'ig', ptype: 'reel', platLabel: 'Instagram · Reel', captions: 12 },
    { id: 'col3', name: 'Maya · Slow life', type: 'variable', persona: 'maya', plat: 'th', ptype: 'th_media', platLabel: 'Threads · Médias', captions: 10 },
    { id: 'col4', name: 'Sofia · Breathwork US', type: 'assembled', persona: 'sofia', plat: 'ig', ptype: 'reel', platLabel: 'Instagram · Reel', captions: 0 },
    { id: 'col5', name: 'Nina · Yoga du soir', type: 'variable', persona: 'nina', plat: 'ig', ptype: 'reel', platLabel: 'Instagram · Reel', captions: 8 },
    { id: 'col6', name: 'Maya · Questions X', type: 'variable', persona: 'maya', plat: 'x', ptype: 'tw', platLabel: 'X · Tweet', captions: 9 },
    { id: 'col7', name: 'Alba · Viajes', type: 'assembled', persona: 'alba', plat: 'th', ptype: 'th_media', platLabel: 'Threads · Médias', captions: 0 }
  ];

  // market + proxy : proxy mobile relié à l'iPhone (même liaison que le module Proxies)
  var devProxy = { 3: ['FR', 'proxy-fr-04'], 4: ['FR', 'proxy-fr-12'], 5: ['FR', 'proxy-fr-15'], 7: ['FR', 'proxy-fr-21'], 8: ['FR', 'proxy-fr-08'], 9: ['FR', 'proxy-fr-19'], 11: ['FR', 'proxy-fr-31'], 12: ['US', 'proxy-us-03'], 14: ['US', 'proxy-us-07'], 15: ['US', 'proxy-us-11'], 16: ['ES', 'proxy-es-07'], 18: ['ES', 'proxy-es-02'] };
  var pxStatus = { 'proxy-fr-12': 'down', 'proxy-us-03': 'slow' };
  var devices = [3, 4, 5, 7, 8, 9, 11, 12, 14, 15, 16, 18].map(function (n, i) { var id = 'iphone-' + (n < 10 ? '0' : '') + n; return { id: id, name: 'iPhone #' + (n < 10 ? '0' : '') + n, model: ['iPhone 12', 'iPhone 13', 'iPhone 13 mini', 'iPhone 14'][i % 4], ios: ['17.5', '17.6', '18.0'][i % 3], rack: 'Rack ' + String.fromCharCode(65 + Math.floor(i / 6)) + (i % 6 + 1), status: n === 7 || n === 11 ? 'offline' : 'online', market: devProxy[n][0], proxy: devProxy[n][1], pxStatus: pxStatus[devProxy[n][1]] || 'ok', jb: n !== 18 }; });

  // iPhone de chaque compte (même répartition initiale que le Parc d'iPhone) + règles d'attribution par iPhone
  ['FR', 'US', 'ES'].forEach(function (mk) {
    var ds = devices.filter(function (d) { return d.market === mk && d.pxStatus !== 'down'; });
    var as = accounts.filter(function (a) { var p = personas.find(function (x) { return x.id === a.persona; }); return p && p.market === mk; });
    as.forEach(function (a, i) { a.device = ds.length ? ds[Math.floor(i * ds.length / as.length)].id : null; });
  });
  devices.forEach(function (d) {
    var ps = []; accounts.forEach(function (a) { if (a.device === d.id && ps.indexOf(a.persona) < 0) ps.push(a.persona); });
    d.rules = { max: d.market === 'ES' ? 8 : 6, personas: ps, plats: ['ig', 'th', 'x'] };
  });
  var alloc = { on: true, mode: 'fill', at: 80 };
  var PLN = { ig: 'Instagram', th: 'Threads', x: 'X' };
  // Choisit l'iPhone d'un nouveau compte. extra = { deviceId: comptes déjà ajoutés hors de ce fichier }
  function pickDevice(market, persona, plat, extra) {
    extra = extra || {}; var skipped = [], el = [];
    devices.filter(function (d) { return d.market === market; }).forEach(function (d) {
      var n = accounts.filter(function (a) { return a.device === d.id; }).length + (extra[d.id] || 0); var R = d.rules; var why = null;
      if (d.status !== 'online') why = 'indisponible'; else if (d.jb === false) why = 'jailbreak perdu'; else if (!d.proxy) why = 'sans proxy'; else if (d.pxStatus === 'down') why = 'proxy hors ligne';
      else if (R.plats.indexOf(plat) < 0) why = (PLN[plat] || plat) + ' non autorisé'; else if (R.personas.length && R.personas.indexOf(persona) < 0) why = 'persona non autorisée'; else if (n >= R.max) why = 'plein · ' + n + '/' + R.max;
      if (why) skipped.push({ name: d.name, reason: why }); else el.push({ d: d, n: n, ratio: n / R.max });
    });
    if (!alloc.on) return { device: null, off: true, why: 'Attribution automatique désactivée', skipped: skipped };
    if (!el.length) return { device: null, why: 'Aucun iPhone ' + market + ' ne peut recevoir ce compte', skipped: skipped };
    var ch, why;
    if (alloc.mode === 'fill') {
      var under = el.filter(function (e) { return e.ratio * 100 < alloc.at; });
      if (under.length) { ch = under.sort(function (a, b) { return b.ratio - a.ratio || a.d.id.localeCompare(b.d.id); })[0]; why = ch.n ? 'remplissage en cours, sous le seuil de ' + alloc.at + ' %' : 'iPhone vide, le prochain à remplir'; }
      else { ch = el.slice().sort(function (a, b) { return a.ratio - b.ratio; })[0]; why = 'tous les iPhone possibles ont passé ' + alloc.at + ' %, le moins rempli'; }
    } else { ch = el.sort(function (a, b) { return a.ratio - b.ratio; })[0]; why = 'le moins rempli des iPhone possibles'; }
    return { device: ch.d, n: ch.n, max: ch.d.rules.max, why: why, skipped: skipped };
  }

  // ---- OnlyChat : comptes créatrice (1 OnlyFans + N Telegram par persona) et licences
  // Telegram limite les messages par compte : une persona peut avoir 3 à 5 comptes Telegram, chacun avec sa licence.
  var TGN = { lea: 3, maya: 2, sofia: 4, clara: 3, nina: 2, alba: 0 };
  var ocAccounts = [], licenses = []; var li = 0;
  function lic(platform, acc, days) { var d = new Date(); d.setDate(d.getDate() + days); var id = 'lic_' + (++li); licenses.push({ id: id, platform: platform, key: (platform === 'onlyfans' ? 'OF-' : 'TG-') + (4000 + li * 37) + '-' + String.fromCharCode(65 + li % 26) + String.fromCharCode(70 + li % 19), expires: d.toISOString().slice(0, 10), account: acc }); return id; }
  personas.forEach(function (p, pi) {
    var of = 'oc_of_' + p.id; ocAccounts.push({ id: of, persona: p.id, platform: 'onlyfans', name: p.first.toLowerCase().normalize('NFD').replace(/[^a-z]/g, '') + (p.market === 'US' ? '.xo' : '.of'), license: lic('onlyfans', of, 20 + pi * 9) });
    for (var k = 0; k < (TGN[p.id] || 0); k++) { var id = 'oc_tg_' + p.id + (k + 1); ocAccounts.push({ id: id, persona: p.id, platform: 'telegram', name: p.first + ' · TG ' + (k + 1), license: lic('telegram', id, k === 2 ? 4 : 12 + k * 15 + pi * 3) }); }
  });
  // comptes OnlyChat pas encore reliés à une persona
  ocAccounts.push({ id: 'oc_tg_new1', persona: null, platform: 'telegram', name: 'Compte Telegram 1', license: lic('telegram', 'oc_tg_new1', 30) });
  ocAccounts.push({ id: 'oc_tg_new2', persona: null, platform: 'telegram', name: 'Compte Telegram 2', license: null });
  ocAccounts.push({ id: 'oc_of_new1', persona: null, platform: 'onlyfans', name: 'jade.of', license: lic('onlyfans', 'oc_of_new1', 45) });
  ocAccounts.push({ id: 'oc_of_new2', persona: null, platform: 'onlyfans', name: 'lou.xo', license: lic('onlyfans', 'oc_of_new2', -3) });
  ocAccounts.push({ id: 'oc_of_new3', persona: null, platform: 'onlyfans', name: 'emma.vip', license: null });


  // État des intégrations (prototype) : simulé depuis Paramètres, lu par les modules.
  var API_KEY = 'scale.apiSim';
  function apiRead() { try { return JSON.parse(localStorage.getItem(API_KEY) || '{}'); } catch (e) { return {}; } }
  var api = {
    NAMES: { oc: 'OnlyChat', gms: 'GetMySocial' },
    STATES: [['ok', 'Connecté'], ['sync', 'Synchro en cours'], ['down', 'Injoignable'], ['auth', 'Clé refusée'], ['rate', 'Limite de requêtes']],
    get: function (svc) { return apiRead()[svc] || 'ok'; },
    set: function (svc, v) { var o = apiRead(); o[svc] = v; try { localStorage.setItem(API_KEY, JSON.stringify(o)); } catch (e) {} window.dispatchEvent(new Event('scale-api')); },
    lastSync: function (svc) { return Date.now() - (svc === 'oc' ? 2 * 36e5 + 14 * 6e4 : 47 * 6e4); },
    stale: function (svc) { var s = api.get(svc); return s === 'down' || s === 'auth' || s === 'rate'; },
    since: function (svc) { var m = Math.round((Date.now() - api.lastSync(svc)) / 6e4); return m < 60 ? m + ' min' : Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + String(m % 60).padStart(2, '0') : ''); },
    retry: function (svc) { api.set(svc, 'sync'); setTimeout(function () { api.set(svc, 'ok'); }, 1600); },
    subscribe: function (fn) { window.addEventListener('scale-api', fn); window.addEventListener('storage', fn); return function () { window.removeEventListener('scale-api', fn); window.removeEventListener('storage', fn); }; },
    banners: function (svcs, compact) {
      return svcs.map(function (svc) {
        var s = api.get(svc), N = api.NAMES[svc], ago = api.since(svc), t = new Date(api.lastSync(svc)), hh = String(t.getHours()).padStart(2, '0') + ':' + String(t.getMinutes()).padStart(2, '0');
        if (s === 'ok') return null;
        var B = {
          sync: ['ph ph-arrows-clockwise', 'Synchronisation ' + N + ' en cours', 'Les données se mettent à jour. Elles restent consultables pendant la synchro.', ['#8db4fd', 'rgba(141,180,253,.3)', 'rgba(141,180,253,.06)'], false, false],
          down: ['ph ph-cloud-slash', N + ' ne répond pas', 'Données de la dernière synchro réussie, à ' + hh + ' (il y a ' + ago + '). Les modifications vers ' + N + ' sont en attente.', ['#f5c77e', 'rgba(245,199,126,.32)', 'rgba(245,199,126,.06)'], true, true],
          auth: ['ph ph-key', 'Clé API ' + N + ' refusée', 'La clé a expiré ou a été révoquée. Données figées à ' + hh + ' (il y a ' + ago + ') tant qu’une nouvelle clé n’est pas enregistrée.', ['#fda4af', 'rgba(244,114,140,.35)', 'rgba(244,114,140,.07)'], false, true],
          rate: ['ph ph-hourglass-medium', 'Limite de requêtes ' + N + ' atteinte', 'Nouvel essai automatique dans 4 min. Données de ' + hh + ' (il y a ' + ago + ').', ['#f5c77e', 'rgba(245,199,126,.32)', 'rgba(245,199,126,.06)'], true, false]
        }[s];
        return { svc: svc, state: s, icon: B[0], title: B[1], text: compact ? '' : B[2], hasText: !compact, canRetry: B[4], retry: function () { api.retry(svc); }, retryLabel: 'Réessayer', settings: B[5], settingsHref: 'Module%20Parametres%20v1.dc.html', settingsLabel: s === 'auth' ? 'Mettre à jour la clé' : 'Paramètres', spin: s === 'sync',
          iconStyle: { fontSize: compact ? 15 : 18, flex: 'none', color: B[3][0] }, titleStyle: { fontSize: compact ? 12 : 13, fontWeight: 600, color: B[3][0] }, btnStyle: { display: 'flex', alignItems: 'center', gap: 6, height: 30, padding: '0 11px', borderRadius: 9, fontSize: 12, fontWeight: 600, color: B[3][0], border: '1px solid ' + B[3][1], cursor: 'pointer', whiteSpace: 'nowrap', textDecoration: 'none' },
          box: { display: 'flex', alignItems: compact ? 'center' : 'flex-start', gap: 12, padding: compact ? '8px 12px' : '12px 14px', borderRadius: 12, border: '1px solid ' + B[3][1], background: B[3][2] } };
      }).filter(Boolean);
    },
    dim: function (svcs) { var st = svcs.some(function (s) { return api.stale(s); }); return st ? { opacity: .6, filter: 'saturate(.55)', transition: 'opacity .2s' } : { transition: 'opacity .2s' }; }
  };
  var ENV_KEY = 'scale.envProviders';
  var envs = {
    PROVIDERS: [['gologin', 'GoLogin', 'Navigateur web anti-détection', 'ph ph-globe'], ['geelark', 'GeeLark', 'Téléphone Android dans le cloud', 'ph ph-device-mobile-camera']],
    all: function () { var d = null; try { d = JSON.parse(localStorage.getItem(ENV_KEY) || 'null'); } catch (e) {} if (!d) d = {}; return d; },
    get: function (k) { return envs.all()[k] || null; },
    set: function (k, v) { var d = envs.all(); if (v) d[k] = v; else delete d[k]; try { localStorage.setItem(ENV_KEY, JSON.stringify(d)); } catch (e) {} window.dispatchEvent(new Event('scale-api')); },
    connected: function () { var d = envs.all(); return envs.PROVIDERS.filter(function (p) { return d[p[0]]; }).map(function (p) { return p[1]; }); },
    ready: function () { return devices.length > 0 || envs.connected().length > 0; }
  };
  window.SCALE_DATA = {
    ocAccounts: ocAccounts,
    api: api,
    envs: envs,
    licenses: licenses,
    devices: devices,
    alloc: alloc,
    behaviorParams: behaviorParams,
    behaviors: behaviors,
    drawMode: drawMode,
    campaigns: campaigns,
    slots: slots,
    scenarios: scenarios,
    pickDevice: pickDevice,
    device: function (id) { return devices.find(function (d) { return d.id === id; }) || null; },
    personas: personas,
    accounts: accounts,
    collections: collections,
    persona: function (id) { return personas.find(function (p) { return p.id === id || p.prsId === id; }) || null; },
    accountsOf: function (pid) { return accounts.filter(function (a) { return a.persona === pid; }); },
    account: function (handle) { return accounts.find(function (x) { return x.handle === handle; }) || null; },
    accountPlat: function (handle) { var a = accounts.find(function (x) { return x.handle === handle; }); return a ? a.plat : null; }
  };
})();
