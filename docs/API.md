# API DraftDB : vue d'ensemble

Ce document répond à trois questions : **comment on utilise l'API**, **quelles routes existent** et **à quelles exigences
du client elles répondent**. Le détail de chaque route (entrées, sorties, erreurs, exemples) est dans
[`CONTRAT_API.md`](CONTRAT_API.md) ; la construction du code est dans [`ARCHITECTURE.md`](ARCHITECTURE.md).

État au 22/11/2026 (fin du sprint 1) : **5 cas d'utilisation sur 27** sont réalisés côté serveur.

---

## 1. Utiliser l'API

### Documentation interactive

Quand le serveur tourne (`python -m uvicorn app.main:app --reload`) :

| Adresse | Rôle |
|---|---|
| http://127.0.0.1:8000/api/docs | **Swagger** : lire le contrat et **essayer** chaque route (bouton *Try it out*) |
| http://127.0.0.1:8000/api/redoc | ReDoc : la même documentation, en lecture |
| http://127.0.0.1:8000/api/openapi.json | Le contrat OpenAPI brut (pour générer un client, par exemple) |

### Identification (provisoire)

Les routes qui ne sont pas publiques demandent l'en-tête **`X-User-Id`**, l'UUID d'un utilisateur existant :

```text
X-User-Id: 00000000-0000-0000-0000-000000000001
```

Il va dans les **en-têtes** de la requête, pas dans le corps JSON. Il ne protège rien et disparaîtra avec le login (CU 0.1
à 0.3). Les utilisateurs de test sont dans la base de développement (`db/02_seed.sql`) :

| Utilisateur | `X-User-Id` | Rôle dans le projet de test `00000000-0000-0000-0000-0000000000a1` |
|---|---|---|
| `responsable` | `00000000-0000-0000-0000-000000000001` | Responsable et concepteur |
| `relecteur` | `00000000-0000-0000-0000-000000000002` | Relecteur seulement |
| `etranger` | `00000000-0000-0000-0000-000000000003` | Ne participe pas |

### Exemples avec `curl` (bash)

```bash
U=00000000-0000-0000-0000-000000000001

# Créer un projet
curl -s -X POST http://127.0.0.1:8000/api/projets \
  -H "X-User-Id: $U" -H "Content-Type: application/json" \
  -d '{"nom": "Boutique en ligne", "description": "Schéma de la boutique"}'

# Ajouter une table (remplacer <id_projet> par l'identifiant renvoyé)
curl -s -X POST http://127.0.0.1:8000/api/projets/<id_projet>/tables \
  -H "X-User-Id: $U" -H "Content-Type: application/json" \
  -d '{"id": "tbl_exemple_01", "name": "exemple", "fields": [{"id": "col_exemple_id", "name": "id", "type": {"id": "integer"}, "primaryKey": true, "nullable": false}]}'

# Ouvrir le projet
curl -s http://127.0.0.1:8000/api/projets/<id_projet> -H "X-User-Id: $U"

# Supprimer la table : 1er appel sans confirmation (409), 2e appel avec confirmation (200)
curl -s -X DELETE http://127.0.0.1:8000/api/projets/<id_projet>/tables/tbl_exemple_01 -H "X-User-Id: $U"
curl -s -X DELETE "http://127.0.0.1:8000/api/projets/<id_projet>/tables/tbl_exemple_01?confirme_suppression=true" -H "X-User-Id: $U"
```

Sous PowerShell, préférer Swagger : l'écriture des guillemets JSON y est pénible.

> Les identifiants ChartDB (`tbl_exemple_01`, `col_exemple_id`) ne peuvent servir **qu'une seule fois** dans toute la base,
> même après une suppression de la table (principe P3). Pour rejouer l'exemple, changer les identifiants, ou repartir d'une
> base neuve (`docker compose down -v`).

---

## 2. Routes disponibles

| Méthode et route | Cas d'utilisation | Droits | Réponse de succès |
|---|---|---|---|
| `GET /api/health` | — | public | 200 `{status, database}` |
| `POST /api/projets` | CU 1.1 Créer un projet | utilisateur identifié | 201 le projet |
| `GET /api/projets/{id_projet}` | CU 1.6 Ouvrir un projet | participant | 200 le projet et son diagramme |
| `POST /api/projets/{id_projet}/import` | CU 1.5 Importer le dump d'une base existante | responsable | 201 `{id_import, numero_sequence, nb_elements_crees}` |
| `POST /api/projets/{id_projet}/tables` | CU 2.1 Ajouter une table | concepteur | 201 `{table, numero_sequence, avertissement}` |
| `DELETE /api/projets/{id_projet}/tables/{id_table}` | CU 2.3 Supprimer une table | concepteur | 200 `{id_table, numero_sequence}` (après un 409 de confirmation) |

### Droits d'accès

| Route | Visiteur | Utilisateur identifié | Participant | Concepteur | Responsable |
|---|---|---|---|---|---|
| `GET /api/health` | oui | oui | oui | oui | oui |
| `POST /api/projets` | 401 | oui | oui | oui | oui |
| `GET /api/projets/{id}` | 401 | 403 | oui | oui | oui |
| `POST /api/projets/{id}/import` | 401 | 403 | 403 | 403 | **oui** |
| `POST /api/projets/{id}/tables` | 401 | 403 | 403 | **oui** | oui si concepteur |
| `DELETE /api/projets/{id}/tables/{id_table}` | 401 | 403 | 403 | **oui** | oui si concepteur |

Le « visiteur » est une requête sans `X-User-Id` valide. Un utilisateur qui n'est pas dans le projet reçoit 403. Le
responsable reçoit le rôle de concepteur à la création du projet ; seul ce rôle autorise la modification du schéma.

---

## 3. Correspondance avec les exigences du client

Les 17 exigences (EX-01 à EX-17) sont vérifiées par le client à la recette. Priorités MoSCoW (Must, Should, Could) du
cahier des charges. Légende : ✅ réalisé, 🟡 partiel, ⬜ à faire.

| Exigence | Résumé | Prio. | Cas d'utilisation | État | Ce qui existe |
|---|---|---|---|---|---|
| EX-01 | Travail simultané sans perte, même après coupure | Must | CU 2.1 à 2.4 | 🟡 | Ajout et suppression de table côté serveur, numérotées sous verrou ; pas de temps réel |
| EX-03 | Script de migration exécutable sans retouche | Must | CU 3.6 | ⬜ | |
| EX-04 | Voir avant migration ce qui sera supprimé ou perdu | Must | CU 3.6 | ⬜ | |
| EX-06 | Modifications visibles chez les autres sans attente | Must | CU 2.1, 2.2 | ⬜ | Temps réel à venir |
| EX-08 | Seules les personnes invitées accèdent au projet | Must | CU 0.1 à 0.3, 1.1 à 1.4, 1.6 | 🟡 | Contrôle d'accès par projet (403) ; identification provisoire ; comptes, invitations et rôles à faire |
| EX-09 | Exporter le schéma pour le réutiliser | Must | CU 3.7 | ⬜ | |
| EX-14 | Démarrer un projet depuis le dump d'une base existante | Must | CU 1.5 | ✅ | `POST …/import` |
| EX-15 | Migration produite uniquement depuis une version approuvée | Must | CU 3.4 à 3.6 | ⬜ | |
| EX-02 | Voir qui travaille et sur quelle partie | Should | CU 2.1, 2.2 | ⬜ | |
| EX-05 | Être prévenu quand une modification pose problème | Should | CU 2.1 à 2.5 | 🟡 | Avertissement « table sans clé primaire » à l'ajout ; vérification complète à faire |
| EX-07 | Retrouver l'état du schéma à une date antérieure | Should | CU 1.6, 3.1 à 3.3 | 🟡 | Ouverture du dernier état ; versions à faire |
| EX-10 | Commenter une table ou une colonne | Should | CU 2.8, 2.9 | ⬜ | |
| EX-16 | Prendre la main | Should | CU 2.6, 2.7 | ⬜ | |
| EX-17 | La séance n'est pas bloquée si celui qui a la main part | Should | CU 2.6 | ⬜ | |
| EX-11 | Répondre à un commentaire et clôturer une discussion | Could | CU 2.9 à 2.11 | ⬜ | |
| EX-12 | Discussion conservée si l'élément est renommé ou supprimé | Could | CU 2.8 | ⬜ | |
| EX-13 | Retrouver les commentaires d'une version antérieure | Could | CU 3.2 | ⬜ | |

---

## 4. Cas d'utilisation : réalisés et à faire

27 cas d'utilisation, répartis en quatre processus.

| Processus | Cas d'utilisation | État |
|---|---|---|
| **P0** Accéder à l'application | 0.1 Créer un compte · 0.2 S'authentifier · 0.3 Modifier son mot de passe | ⬜ |
| **P1** Mettre en place un projet | **1.1 Créer un projet** ✅ · 1.2 Inviter un participant ⬜ · 1.3 Modifier les rôles ⬜ · 1.4 Retirer un participant ⬜ · **1.5 Importer le dump** ✅ · **1.6 Ouvrir un projet** ✅ | 3 sur 6 |
| **P2** Concevoir le schéma en atelier | **2.1 Ajouter une table** ✅ · 2.2 Modifier une table et ses colonnes ⬜ · **2.3 Supprimer une table** ✅ · 2.4 Relier deux tables ⬜ · 2.5 Vérifier la cohérence ⬜ · 2.6 Demander la main ⬜ · 2.7 Rendre la main ⬜ · 2.8 à 2.11 Discussions ⬜ | 2 sur 11 |
| **P3** Valider et livrer une évolution | 3.1 Créer une version nommée · 3.2 Consulter une version antérieure · 3.3 Comparer · 3.4 Soumettre · 3.5 Approuver ou refuser · 3.6 Générer le script de migration · 3.7 Exporter en SQL | ⬜ |

---

## 5. Temps réel

**Non réalisé.** Le dossier prévoit un canal WebSocket (`pycrdt-websocket`, côté navigateur `Yjs`) pour :

- la synchronisation des modifications entre participants (objectif : moins de 500 ms) ;
- la présence (qui est connecté, sur quel élément) ;
- la prise de main et sa libération automatique.

Aujourd'hui, un ajout ou une suppression de table est enregistré côté serveur mais n'est **pas poussé** aux autres
participants : le front recharge le projet avec `GET /api/projets/{id_projet}`. Le numéro de séquence
(`numero_sequence`) est déjà attribué à chaque modification, pour servir de repère quand le temps réel arrivera.

---

## 6. Ce qui reste à faire côté API

Dans l'ordre où le dossier les place : comptes et connexion (CU 0.1 à 0.3), invitations et rôles (CU 1.2 à 1.4),
modification d'une table et de ses colonnes (CU 2.2), clés étrangères et vérification de cohérence (CU 2.4 et 2.5), prise
de main et temps réel (CU 2.6 et 2.7), discussions (CU 2.8 à 2.11), versions, comparaison et approbation (CU 3.1 à 3.5),
génération des scripts de migration et export SQL (CU 3.6 et 3.7).
