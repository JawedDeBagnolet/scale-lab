# Scale Lab · données pour le back-end

Cahier des charges pour remplacer `shared-data.js` (window.SCALE_DATA) et les données simulées des modules par l’API. Une ligne par entité : champs, source, fréquence de mise à jour, modules qui la lisent.

Sources :
- **App** : base Scale Lab (créé et modifié dans l’app).
- **iPhone** : agent installé sur chaque appareil du parc (télémétrie + exécution des ordres).
- **Plateforme** : données lues sur Instagram, Threads, X par les iPhones ou les scrapers.
- **OC** : API OnlyChat (MCP). **GMS** : API GetMySocial v3. **TG** : Bot API Telegram.

## 1. Entités de base (App)

| Entité | Champs | Lue par |
| --- | --- | --- |
| Persona | id, prsId (OnlyChat), first, last, color, market, city, age, platforms[], niches[], bios[], prompt, funnel, telegram (bot, username de la modèle, chat id, langue des briefs, groupe de production + topic) | tous |
| Compte | id, handle, persona, plat (ig/th/x), workflow (Onboarding/Warmup/Actif), status (ok/session/error/suspendu), device, proxy, env (environnements), sessions, follows, identifiants chiffrés (mot de passe, 2FA, token) | Comptes, Posting, Scénarios, Stats, Liens, Dashboard |
| Marché | code, actif, langue, fuseau | Paramètres, filtres partout |
| Niche | id, label (23 communes) | Personas, Veille, Targets |
| Collection | id, name, type (assembled/variable), persona, plat, ptype, captions[], médias[] | Posting |
| Média | id, persona, type (image/vidéo/audio), url, durée, tags, dossier, utilisé (anti-repeat) | Posting, Story Builder, Liens (landings) |
| Template post / story | id, persona, plat, calques, variables, collection | Posting |
| Campagne | id, name, icon, persona, plat, status, scenarios[], vagues, planning | Posting, Dashboard |
| Publication | id, compte, campagne, média, caption, planifiée à, statut (planifiée/publiée/échec/suspendue), id du post plateforme | Posting, Logs, Dashboard |
| Scénario | id, name, origin (spontané/login/création), couple, slots[], steps[] (actions + presets + délais), boucle | Scénarios |
| Run | id, scénario, comptes[], étape courante, statut, comptes bloqués, journal | Scénarios, Dashboard |
| Plage horaire | id, name, days[], ranges[] | Scénarios |
| Preset de comportement | id, plat, type de session, probabilités, pauses, durées | Comportements, Scénarios |
| Target | handle, plat, marché, niche, statut (ok/privé/renommé/banni), source | Targets, Veille |
| Veille | sources, inspirations, favoris, snipes, file de validation, albums, briefs | Veille, Dashboard |
| Règle d’alerte | module, type d’événement, seuil (X erreurs sur Y actions), Telegram | Logs |
| Objectif | métrique, fréquence (1 / 7 / 30 j), valeurs par persona | Statistiques, Dashboard |
| Disposition du Dashboard | widgets (type, x, y, w, h, cfg) par utilisateur | Dashboard (aujourd’hui en localStorage) |

## 2. Parc et réseau (iPhone)

| Entité | Champs | Fréquence | Encore simulé |
| --- | --- | --- | --- |
| iPhone | id, name, model, ios, rack, market, status (online/offline), jailbreak, règles (max comptes), proxy relié | temps réel (heartbeat 30 s) | — |
| Télémétrie iPhone | batterie %, en charge, qualité réseau, data consommée, run en cours + compte, dernier run, hors ligne depuis | 30 s | **oui, entièrement** |
| Proxy | id, pool (marché × plateforme), type 4G/5G, iPhone, IP, pays, latence, statut, blacklists, disponibilité 7 j | test toutes les 5 min | latence et historique |
| Allocation | mode (fill/spread), seuil de bascule | App | — |

## 3. Statistiques des comptes (Plateforme)

Série quotidienne par compte, conservée au moins 180 jours (aujourd’hui générée côté front) :
abonnés, gagnés, perdus, portée (vues uniques), impressions, engagements (likes, commentaires, partages, enregistrements), visites de profil, clics en bio, vues de stories, posts publiés, stories publiées, disponibilité.
Calculés côté back : gain net, taux d’engagement (engagements ÷ portée), impressions moyennes par post, taux de conversion (nouveaux subs ÷ portée), anomalies.

## 4. OnlyChat (OC)

| Entité | Champs | Fréquence |
| --- | --- | --- |
| Créatrice | = persona (prsId), profil, réglages | synchro 15 min |
| Compte OnlyChat | id, persona, platform (onlyfans/telegram), name, licence | 15 min |
| Licence | id, platform, key, expires, account (attribution faite dans OnlyChat, renouvellement auto) | 1 h |
| Transaction | id, date-heure, fan, créatrice, type (sub/ppv/tip), amount ($ entiers), script, compte | 5 min |
| Fan | id, pseudo, créatrice, compte, plateforme d’origine, rejoint le, dépensé, dernière activité, notes | 15 min |
| Script | id, scriptGroupId (versions), dossier, actif, prioritaire, steps (message, média, PPV, attente, réduction, post-média en s, skip followup), stats par compte (envois, ouvertures, unlock, revenus) | 15 min |
| Média OC | id, dossier, type, description, vault | 1 h |
| Crédit | solde, seuil d’alerte | 15 min |
| Quotas | imports de scripts et de médias restants | 1 h |

Calculés côté back : CA par jour / semaine / mois, LTV (CA des subs ÷ nouveaux subs de la période), unlock rate, ROI par plateforme et par persona, revenus par bot Telegram (persona + plateforme = un bot), estimation par campagne.

## 5. GetMySocial (GMS)

| Entité | Champs | Fréquence |
| --- | --- | --- |
| Lien GMS | id, title, slug, domaine, destination, actif, groupe, assignation (plateforme + @username) | 15 min |
| Landing | tous les champs du builder (profil, médias, thème, blocs, page, tracking Agency) via `POST/PATCH /v3/links` (multipart pour les médias) ; A/B en lecture seule | à l’enregistrement + 1 h |
| Domaine GMS | host, statut DNS | 1 h |
| Analytics | par lien et par jour : clics, uniques, CTA, bots, pays, villes, langues, appareils, navigateurs, referrers, clics par bouton | 15 min |
| Plan | type (Agency), options | 24 h |

## 6. Liens trackés Scale Lab (App)

Lien : id, domaine, slug, type (direct/landing), destination ou landing, plateforme source, persona, compte, actif, groupe, créé le. Clics enregistrés par le redirecteur Scale Lab (mêmes dimensions que GMS).
Domaine : host, limite de liens actifs, seuil d’alerte. Événements à émettre vers Logs : lien créé, lien sur compte indisponible, domaine bientôt plein, domaine plein.

## 7. Journal et alertes (App + TG)

Événement : id, horodatage, module, type, niveau, cible, cause, code, message. Les incidents regroupent les événements par module + type + cible (statut ouvert / acquitté / résolu, solutions appliquées, taux de réussite). Alertes et résumé quotidien envoyés par le bot d’alertes Telegram (token + destinataire dans Paramètres).

## 8. État des intégrations

Pour OC et GMS : statut (connecté / synchro en cours / injoignable / clé refusée / limite de requêtes), heure de la dernière synchro réussie, prochain essai. Lu par le CRM, Liens, Personas, le Dashboard et Paramètres. Aujourd’hui simulé depuis Paramètres › Intégrations (clé `scale.apiSim` en localStorage).

## 9. Règles transverses à appliquer côté back

- Un compte en checkpoint, suspendu ou session expirée ne reçoit aucun ordre : runs, publications, vagues et stories passent en « Suspendu » et reprennent au retour du compte.
- Un iPhone hors ligne met ses comptes en attente.
- Les clés API restent côté serveur ; le front n’affiche que les 4 derniers caractères.
- Prix entiers en dollars ; une réduction à 0 sur un step payant envoie le média gratuitement : bloquer à l’enregistrement.

## 10. Liens profonds (hash) à conserver

Comptes `#acc` `#persona` · Personas `#persona` · CRM `#creator[&tab]` `#fan` · Liens `#link` `#dom` `#persona` · Posting `#camp` `#q` · Statistiques `#acc` `#persona` · Parc `#dev` · Proxies `#proxy` · Logs `#acc` `#link` `#dom` `#q`.
