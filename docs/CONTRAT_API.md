# Contrat de l'API DraftDB

Contrat entre le **front** (éditeur ChartDB adapté) et le **back** (ce dépôt) : pour chaque route, ce que le front
envoie, ce que le serveur renvoie, et dans quels cas il refuse. **Les exemples sont de vraies réponses du serveur**
(état au 22/11/2026, sprint 1).

Source : dossier de conception V1.2, chapitre 5.1, complété par ce qui a été réalisé. Les écarts avec le dossier sont
listés au [§ 5](#5-écarts-et-choix-par-rapport-au-dossier). Toute modification de ce contrat se discute avec le
développeur du front **avant** d'être codée.

Voir aussi : [`API.md`](API.md) (vue d'ensemble) et [`ARCHITECTURE.md`](ARCHITECTURE.md) (comment c'est construit).

| Route | Cas d'utilisation | Droits |
|---|---|---|
| [`GET /api/health`](#31-get-apihealth) | — | public |
| [`POST /api/projets`](#32-post-apiprojets-cu-11) | CU 1.1 | utilisateur identifié |
| [`GET /api/projets/{id_projet}`](#33-get-apiprojetsid_projet-cu-16) | CU 1.6 | participant |
| [`POST /api/projets/{id_projet}/import`](#34-post-apiprojetsid_projetimport-cu-15) | CU 1.5 | responsable |
| [`POST /api/projets/{id_projet}/tables`](#35-post-apiprojetsid_projettables-cu-21) | CU 2.1 | concepteur |
| [`DELETE /api/projets/{id_projet}/tables/{id_table}`](#36-delete-apiprojetsid_projettablesid_table-cu-23) | CU 2.3 | concepteur |

---

## 1. Conventions

| Sujet | Règle |
|---|---|
| Préfixe | `/api` pour toutes les routes, Swagger compris (`/api/docs`, `/api/redoc`, `/api/openapi.json`) |
| Format | JSON, UTF-8. Les objets du schéma suivent le **format ChartDB** (noms en camelCase : `primaryKey`, `fieldIds`…) |
| Identification | En-tête **`X-User-Id`** : l'UUID d'un utilisateur existant. **Provisoire** : il ne protège rien et disparaîtra avec le login. Absent, invalide ou inconnu : **401** |
| Identifiants du schéma | Identifiants ChartDB (table, colonne, index, relation) : chaîne de **25 caractères au plus**, fournie par le navigateur, **jamais régénérée** par le serveur. Un identifiant déjà utilisé est refusé, sauf pour **restaurer** une table supprimée du même projet (RG-09 précisée, voir l'ajout d'une table) |
| Noms et types | Voir « Règles de nommage » et « Types de colonnes » au § 2 (RG-10 et RG-11 précisées) |
| Autres identifiants | UUID (projet, import, utilisateur) |
| Dates | Dans le diagramme renvoyé, `createdAt` et `updatedAt` sont des **millisecondes depuis 1970** (comme ChartDB) |
| Droits | Vérifiés côté serveur à chaque requête. Un utilisateur qui ne participe pas au projet reçoit **403** |
| Ordre des contrôles | **401, puis 403, puis 404 / 422 / 409.** Une route qui écrit n'écrit **rien** en cas d'erreur |
| Transactions | Une requête qui écrit est « tout ou rien » |

### Format des erreurs

```json
{ "detail": "…" }
```

`detail` est :
- un **texte** pour 401, 403, 404, 413 et les erreurs métier en 422 ;
- une **liste** pour une erreur de validation du corps ou des paramètres (422), au format Pydantic :
  `[{"type", "loc", "msg", "input"}]`, où `loc` indique le champ fautif (par exemple `["body", "fields", 0, "type"]`) ;
- un **objet** pour une demande de confirmation (409).

### Confirmation (409)

Quand une action destructrice demande une confirmation, la route répond **409** sans rien modifier, avec
`{"detail": {"code": "CONFIRMATION_REQUISE", …}}`. Le front demande confirmation à l'utilisateur, puis **renvoie la même
requête** avec le paramètre de confirmation (`confirme_remplacement` pour l'import, `confirme_suppression` pour la
suppression d'une table). Le serveur impose cette confirmation : elle ne dépend pas du comportement du front.

### Codes de retour

| Code | Signification |
|---|---|
| 200 | Succès (lecture, suppression) |
| 201 | Création faite |
| 401 | Utilisateur non identifié |
| 403 | L'utilisateur n'a pas le droit |
| 404 | Projet ou table introuvable |
| 409 | Confirmation requise : rien n'est modifié |
| 413 | Fichier déclaré trop volumineux (import) |
| 422 | Requête invalide ou règle de gestion violée : rien n'est créé |
| 500 | Erreur technique : tout est annulé, l'état précédent est intact |
| 503 | Base injoignable, **uniquement** sur `/api/health` |

---

## 2. Objets échangés (format ChartDB)

Les champs inconnus de ChartDB (par exemple `createdAt`) sont **acceptés et conservés** à la réception.

### Règles de nommage (RG-10 précisée)

Elles s'appliquent à l'ajout d'une table **et** à l'import (cahier des charges, § 3.3.1.4).

| Niveau | Cas |
|---|---|
| **Refus (422)** | nom vide ou fait d'espaces ; espace au début ou à la fin ; caractère de contrôle (tabulation, NUL…) ; guillemet droit `"` ou accent grave `` ` `` ; plus de **63 octets** en UTF-8 (limite de PostgreSQL : un `é` compte 2 octets) |
| **Refus (422)** | deux tables d'un même schéma SQL, ou deux colonnes d'une même table, portant le même nom **sans tenir compte de la casse** (`Client` et `client`) |
| **Avertissement** `NOM_RESERVE` | nom de table ou de colonne qui est un mot réservé de MySQL 8.4 ou de PostgreSQL 16 (`select`, `user`, `order`…) : il devra être protégé par des guillemets dans les scripts |
| **Avertissement** `NOM_A_PROTEGER` | nom de table ou de colonne hors `[A-Za-z0-9_]` ou commençant par un chiffre (`Nom client`, `café`, `1ere`) |

Les mots réservés ne sont pas refusés : des noms comme `user` ou `order` sont courants dans les dumps réels (EX-14).
Les listes sont dans `app/schemas/mots_reserves.py`, avec leur source.

### Types de colonnes (RG-11 précisée)

`type.id` est comparé **sans tenir compte de la casse** aux types de ChartDB v1.20.1 :

| Dialecte du projet | Types admis |
|---|---|
| `generic` | types génériques de ChartDB (`int`, `varchar`, `text`, `boolean`, `date`, `timestamp`, `decimal`, `uuid`, `json`…) et les synonymes communs `integer`, `bool` |
| `mysql` | les précédents et les types MySQL de ChartDB (`tinyint`, `mediumtext`, `year`…) |
| `postgresql` | les types génériques et les types PostgreSQL de ChartDB (`jsonb`, `serial`, `timestamptz`…) avec leurs synonymes (`character varying`, `int4`…) |
| tous | les types personnalisés du projet (`customTypes` de ChartDB, conservés dans `projet.annexes`) |

À l'ajout d'une table, un type non admis donne un **422**. À l'import, il donne un avertissement `TYPE_INCONNU` sans
bloquer l'import. La liste complète est dans `app/schemas/types_colonnes.py`.

### `DBTable`

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| `id` | texte | oui | 1 à 25 caractères |
| `name` | texte | oui | 63 caractères et 63 octets au plus, règles de nommage ci-dessus |
| `schema` | texte | non | schéma SQL, 63 caractères au plus |
| `x`, `y` | nombre | non (0) | entre -999999,99 et 999999,99 |
| `width` | nombre | non | idem |
| `color` | texte | non | 7 caractères au plus (`#8eb7ff`) |
| `comments` | texte | non | |
| `isView` | booléen | non (`false`) | vue plutôt que table |
| `fields` | liste de `DBField` | non (`[]`) | l'ordre devient le **rang** des colonnes (à partir de 1) |
| `indexes` | liste de `DBIndex` | non (`[]`) | |

### `DBField` (colonne)

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| `id` | texte | oui | 1 à 25 caractères |
| `name` | texte | oui | règles de nommage ci-dessus ; unique dans la table, sans tenir compte de la casse (RG-10) |
| `type` | objet `{id, name?}` | **oui** | `type.id` : 30 caractères au plus, dans la liste admise pour le dialecte du projet (RG-11, ci-dessus) |
| `primaryKey` | booléen | non (`false`) | |
| `nullable` | booléen | non (**`true`**) | une clé primaire doit être non nullable (RG-12) |
| `unique`, `increment` | booléen | non (`false`) | |
| `characterMaximumLength` | **texte** | non | 10 caractères au plus (`"100"`) |
| `precision`, `scale` | entier | non | 0 à 32767 |
| `default` | texte | non | 255 caractères au plus |
| `collation` | texte | non | 63 caractères au plus |
| `comments` | texte | non | |

### `DBIndex`

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| `id` | texte | oui | 1 à 25 caractères |
| `name` | texte | oui | règles de nommage (refus seulement, sans avertissement) |
| `fieldIds` | liste de textes | oui | identifiants de colonnes **de la même table**, sans doublon (RG-14) ; l'ordre est conservé |
| `unique`, `isPrimaryKey` | booléen | non (`false`) | |
| `type` | texte | non | 10 caractères au plus (`btree`, `hash`…) |

### `DBRelationship` (clé étrangère)

| Champ | Type | Règle |
|---|---|---|
| `id`, `name` | texte | 25 caractères au plus pour `id` ; `name` suit les règles de nommage (refus seulement) |
| `sourceTableId`, `targetTableId`, `sourceFieldId`, `targetFieldId` | texte | les colonnes source et cible sont **distinctes** et présentes dans le diagramme (RG-13) |
| `sourceCardinality`, `targetCardinality` | `"one"` ou `"many"` | |

### `Diagram` (diagramme complet)

| Champ | Type | Règle |
|---|---|---|
| `id`, `name` | texte | à l'import : `name` est ignoré (le nom du projet est conservé) |
| `tables` | liste de `DBTable` | **au moins une** pour un import |
| `relationships` | liste de `DBRelationship` | |
| `areas`, `notes`, `customTypes`, `dependencies` | listes d'objets | conservés tels quels dans `projet.annexes` |

---

## 3. Routes

### 3.1 `GET /api/health`

Vérifie que l'API et la base répondent. Aucune identification.

**Réponse 200**

```json
{ "status": "ok", "database": "ok" }
```

**Réponse 503** (base injoignable) : `{ "status": "error", "database": "indisponible" }`

---

### 3.2 `POST /api/projets` (CU 1.1)

Crée un **projet vide**. L'utilisateur identifié en devient le **responsable** et reçoit le rôle de **concepteur**. Le
dialecte n'est pas demandé : il est fixé plus tard (import ou export).

**Droits** : utilisateur identifié.

**Entrée**

| Paramètre | Où | Obligatoire | Règle |
|---|---|---|---|
| `X-User-Id` | en-tête | oui | UUID d'un utilisateur existant |
| `nom` | corps | oui | 1 à 100 caractères ; les espaces autour sont retirés ; non vide |
| `description` | corps | non | 500 caractères au plus ; les espaces autour sont retirés ; **vide ou absente : enregistrée comme `null`** |

**Réponse 201**

```json
{
  "id_projet": "2de2ad68-662f-472e-ba89-e993b9961073",
  "nom": "Boutique en ligne",
  "description": "Schéma de la boutique",
  "type_base": "generic",
  "numero_sequence": 0
}
```

`type_base` vaut `generic` à la création ; `numero_sequence` vaut `0` (aucune opération pour l'instant).

**Écrit en base** (une seule transaction) : une ligne `projet`, la `participation` du créateur (concepteur), un événement
`CREATION_PROJET` dans le journal d'activité. Aucun élément de schéma.

**Erreurs**

| Code | Cas |
|---|---|
| 401 | Utilisateur non identifié (`"Utilisateur non identifié (en-tête X-User-Id manquant)."`) |
| 422 | `nom` absent, vide ou de plus de 100 caractères ; `description` de plus de 500 caractères ; valeur refusée par la base (caractère NUL) |

Deux projets peuvent porter le même nom : aucune règle n'impose un nom unique.

---

### 3.3 `GET /api/projets/{id_projet}` (CU 1.6)

Ouvre un projet : ses informations et le **dernier état de son schéma**, au format ChartDB. Lecture seule : rien n'est
écrit et le projet n'est pas verrouillé.

**Droits** : participant du projet (le responsable participe d'office).

**Entrée** : `id_projet` (chemin, UUID), `X-User-Id` (en-tête).

**Réponse 200** (projet vide)

```json
{
  "id_projet": "2de2ad68-662f-472e-ba89-e993b9961073",
  "nom": "Boutique en ligne",
  "description": "Schéma de la boutique",
  "type_base": "generic",
  "numero_sequence": 0,
  "diagramme": {
    "id": "2de2ad68-662f-472e-ba89-e993b9961073",
    "name": "Boutique en ligne",
    "databaseType": "generic",
    "tables": [],
    "relationships": [],
    "areas": [],
    "notes": [],
    "customTypes": [],
    "dependencies": [],
    "createdAt": 1795365349868,
    "updatedAt": 1795365349868
  }
}
```

Une table du diagramme (extrait d'un projet importé) :

```json
{
  "id": "imp_cmd",
  "name": "commande",
  "x": 0.0, "y": 0.0, "isView": false,
  "fields": [
    { "id": "imp_cmd_id", "name": "id", "type": { "id": "integer", "name": "integer" },
      "primaryKey": true, "unique": false, "nullable": false, "increment": false, "createdAt": 1795365350171 },
    { "id": "imp_cmd_client", "name": "client_id", "type": { "id": "integer", "name": "integer" },
      "primaryKey": false, "unique": false, "nullable": false, "increment": false, "createdAt": 1795365350171 }
  ],
  "indexes": [],
  "createdAt": 1795365350171
}
```

- `type_base` : `generic`, `mysql` ou `postgresql` (le dialecte du dernier dump importé).
- Les colonnes sont dans l'**ordre de leur rang**. Les éléments **supprimés logiquement ne sont pas renvoyés**.
- Les clés à valeur nulle sont omises (pas de `"schema": null`).
- Approximations : `updatedAt` reprend la date de création du projet, et `type.name` reprend `type.id`.

**Erreurs**

| Code | Cas |
|---|---|
| 401 | Utilisateur non identifié |
| 403 | L'utilisateur ne participe pas au projet (`"Vous ne participez pas à ce projet."`) |
| 404 | Projet introuvable (`"Projet introuvable."`). Le 404 précède le 403 : un non-participant peut savoir qu'un projet existe |

---

### 3.4 `POST /api/projets/{id_projet}/import` (CU 1.5)

Enregistre le diagramme obtenu à partir du dump d'une base existante. **Le serveur ne reçoit jamais le dump** : il
reçoit le diagramme (produit par ChartDB dans le navigateur), les caractéristiques du fichier et le rapport d'import.

**Droits** : **responsable** du projet.

**Entrée**

| Paramètre | Où | Obligatoire | Règle |
|---|---|---|---|
| `id_projet` | chemin | oui | UUID |
| `X-User-Id` | en-tête | oui | |
| `confirme_remplacement` | corps | non (`false`) | `true` pour remplacer un schéma non vide |
| `fichier.nom` | corps | oui | 1 à 255 caractères |
| `fichier.dialecte` | corps | oui | `mysql` ou `postgresql` |
| `fichier.taille_octets` | corps | oui | entier ≥ 0, comparé au maximum configuré (50 Mo par défaut) |
| `diagramme` | corps | oui | objet `Diagram` ; **au moins une table** |
| `rapport.non_repris` | corps | non | liste de `{ligne?, type, raison}` : `type` 50 caractères au plus, `raison` 500 ; **aucun autre champ** (le texte d'une instruction est refusé, RG-24) |

```json
{
  "confirme_remplacement": false,
  "fichier": { "nom": "boutique.sql", "dialecte": "postgresql", "taille_octets": 2048 },
  "diagramme": {
    "id": "diag1", "name": "Boutique", "databaseType": "postgresql",
    "tables": [
      { "id": "imp_client", "name": "client",
        "fields": [ { "id": "imp_c_id", "name": "id", "type": { "id": "integer" }, "primaryKey": true, "nullable": false } ] }
    ],
    "relationships": []
  },
  "rapport": { "non_repris": [ { "ligne": 42, "type": "INSERT", "raison": "instruction de données" } ] }
}
```

**Réponse 201**

```json
{
  "id_import": "b6005d51-2739-4363-a7ff-4a1825fb165f",
  "numero_sequence": 1,
  "nb_elements_crees": 6,
  "avertissements": [
    { "code": "NOM_RESERVE", "id_element": "tbl_user_001",
      "message": "Le nom de table 'user' est un mot réservé de PostgreSQL : il devra être protégé par des guillemets dans les scripts SQL." }
  ]
}
```

`nb_elements_crees` compte les tables, colonnes, index et relations ; il est **calculé par le serveur**.
`avertissements` (toujours présent, liste vide si tout va bien) signale les noms réservés ou à protéger (RG-10) et les
types inconnus du dialecte du dump (`TYPE_INCONNU`, RG-11). Ils ne bloquent pas l'import et sont aussi enregistrés dans
le rapport (`import_dump.rapport.avertissements`). L'avertissement « table sans clé primaire » reste propre à l'ajout.

**Comportement**

- Si le schéma du projet **n'est pas vide** et que `confirme_remplacement` n'est pas `true` : **409**, rien n'est modifié.
- Avec confirmation, l'ancien état est **supprimé logiquement** (rien n'est effacé) et remplacé.
- Le dialecte du projet devient celui du fichier.
- **L'import ne crée pas de version** : le responsable en crée une, nommée, ensuite (CU 3.1).
- Écrit dans une seule transaction : éléments du schéma, annexes et dialecte du projet, opération `import`, trace
  `import_dump` (avec le rapport) et événement `IMPORT` du journal.

**Erreurs** (dans cet ordre : 401, 422, puis 404, 403, 413, 409)

| Code | Cas |
|---|---|
| 401 | Utilisateur non identifié |
| 422 | Diagramme ou corps invalide (voir ci-dessous) ; identifiant ChartDB déjà utilisé (l'import exige des identifiants neufs) ; valeur refusée par la base |
| 404 | Projet introuvable |
| 403 | Non participant, ou participant non responsable |
| 413 | Taille déclarée supérieure au maximum (`"Fichier trop volumineux (maximum 52428800 octets)."`) |
| 409 | Schéma non vide, remplacement non confirmé |

**409**

```json
{ "detail": { "code": "CONFIRMATION_REQUISE", "nb_tables_existantes": 2 } }
```

**422 : un diagramme est refusé quand** il ne contient aucune table, deux tables du même schéma SQL portent le même nom
à la casse près (RG-10), deux colonnes d'une table portent le même nom à la casse près, un nom enfreint les règles de
nommage, une table et une colonne partagent un identifiant, une clé primaire est nullable (RG-12), une relation relie une
colonne à elle-même ou cite une colonne absente (RG-13), un index cite deux fois la même colonne ou une colonne d'une
autre table (RG-14), un identifiant est en double ou de plus de 25 caractères.

```json
{ "detail": [ { "type": "value_error", "loc": ["body", "diagramme"],
                "msg": "Value error, Le diagramme ne contient aucune table : rien à importer.", "input": { "…": "…" } } ] }
```

---

### 3.5 `POST /api/projets/{id_projet}/tables` (CU 2.1)

Ajoute une table au schéma du projet. La table est reçue **au format ChartDB** (`DBTable`) ; le serveur la valide, l'enregistre
avec ses colonnes et ses index, attribue le numéro de séquence suivant du projet et inscrit l'opération d'ajout.

**Droits** : **concepteur** du projet.

**Entrée** : `id_projet` (chemin), `X-User-Id` (en-tête), et le corps : un objet `DBTable` (voir § 2).

```json
{
  "id": "tbl_client_001", "name": "client", "x": 10, "y": 20,
  "fields": [
    { "id": "col_client_id", "name": "id", "type": { "id": "integer", "name": "integer" },
      "primaryKey": true, "nullable": false, "unique": true, "increment": true },
    { "id": "col_client_nom", "name": "nom", "type": { "id": "varchar", "name": "varchar" },
      "nullable": false, "characterMaximumLength": "100" }
  ],
  "indexes": [ { "id": "idx_client_pk", "name": "client_pkey", "unique": true,
                 "fieldIds": ["col_client_id"], "isPrimaryKey": true } ]
}
```

**Réponse 201**

```json
{
  "table": { "id": "tbl_client_001", "name": "client", "x": 10.0, "y": 20.0, "isView": false,
             "fields": [ "…" ], "indexes": [ "…" ] },
  "numero_sequence": 1,
  "avertissement": null,
  "avertissements": [],
  "restauree": false
}
```

- `table` : la table **telle qu'enregistrée** (valeurs par défaut comprises, clés nulles omises).
- `numero_sequence` : le numéro de l'opération d'ajout.
- `avertissement` : **toujours présent**, `null` quand tout va bien. Une table **sans colonne clé primaire** est acceptée
  (201), avec :

```json
{ "code": "TABLE_SANS_CLE_PRIMAIRE", "message": "La table 'journal' n'a aucune colonne clé primaire (RG-12)." }
```

Une table sans aucune colonne est acceptée aussi, avec le même avertissement. L'avertissement n'est jamais bloquant.

- `avertissements` : **toujours présent**, liste vide quand tout va bien. Il reprend `TABLE_SANS_CLE_PRIMAIRE` puis les
  avertissements de nommage (`NOM_RESERVE`, `NOM_A_PROTEGER`), chacun avec l'`id_element` concerné. `avertissement` est
  conservé tel quel pour le front existant.
- `restauree` : `true` si la table reprend l'identifiant d'une **table supprimée du même projet** (voir ci-dessous).

**Restauration d'une table supprimée (RG-09 précisée)**

Pour qu'« annuler » une suppression fonctionne, une table dont l'`id` est celui d'une table **supprimée du même projet**
est restaurée au lieu d'être refusée :

- la table et les colonnes reprises redeviennent actives et prennent les valeurs reçues ; les colonnes nouvelles sont
  ajoutées ; les anciennes colonnes absentes du corps restent supprimées ;
- les index reçus remplacent ceux de l'ancienne table ; les anciens index absents du corps sont retirés (leur état passé
  reste dans l'opération de suppression de la table) ;
- les relations ne sont pas dans le corps : celles dont les deux colonnes sont de nouveau actives réapparaissent ;
- l'opération inscrite est un `ajout` ; le nom doit être libre (RG-10).

Tout autre identifiant déjà présent en base reste refusé (P3) : élément actif, élément d'un autre projet, colonne ou index
d'une autre table.

**Erreurs** (dans cet ordre : 401, 404, 403, 422)

| Code | Cas |
|---|---|
| 401 | Utilisateur non identifié |
| 404 | Projet introuvable |
| 403 | N'est pas concepteur du projet (`"Seul un concepteur du projet peut modifier le schéma."`) |
| 422 | Corps invalide : type de colonne absent, nom contraire aux règles de nommage, clé primaire nullable (RG-12), deux colonnes de même nom à la casse près, index sur une colonne absente ou en double (RG-14), identifiant en double dans la table |
| 422 | **Nom de table déjà pris** dans le projet, schéma SQL compris, sans tenir compte de la casse (RG-10) : `"Une table du projet porte déjà le nom 'client' (sans tenir compte de la casse, RG-10)."` |
| 422 | **Type de colonne non admis** pour le dialecte du projet (RG-11) : `"Type de colonne non reconnu pour un projet « generic » (f : 'tinyint') (RG-11)."` |
| 422 | **Identifiant ChartDB déjà utilisé** hors restauration (P3) : `"Identifiant ChartDB déjà utilisé : ['tbl_client_001'] (P3). Seule une table supprimée de ce projet peut être restaurée, avec ses propres colonnes et index (RG-09)."` |
| 422 | Valeur refusée par la base (caractère NUL) |

Le 403 passe **avant** la validation du corps : un non-concepteur reçoit 403 même si sa table est invalide.

---

### 3.6 `DELETE /api/projets/{id_projet}/tables/{id_table}` (CU 2.3)

Supprime **logiquement** une table et ses colonnes (rien n'est effacé). La suppression se fait en **deux appels** sur la
même route.

**Droits** : **concepteur** du projet.

**Entrée**

| Paramètre | Où | Obligatoire | Règle |
|---|---|---|---|
| `id_projet` | chemin | oui | UUID |
| `id_table` | chemin | oui | identifiant ChartDB de la table, 1 à 25 caractères |
| `confirme_suppression` | requête | non (`false`) | `true` pour confirmer (accepte `true`, `1`, `True`…) |
| `X-User-Id` | en-tête | oui | |

**1er appel, sans confirmation : 409**, rien n'est modifié. `detail` liste les liens de la table :

```json
{
  "detail": {
    "code": "CONFIRMATION_REQUISE",
    "cles_etrangeres": [
      { "id": "r_fk", "name": "fk_commande_client",
        "sourceTableId": "t_cmd", "targetTableId": "t_client",
        "sourceFieldId": "c_cmd_client", "targetFieldId": "c_id" }
    ],
    "index": [ { "id": "idx_client_pk", "name": "client_pkey" } ]
  }
}
```

- `cles_etrangeres` : les relations qui touchent la table, **dans les deux sens** (la table est la source ou la cible),
  avec les noms de ChartDB. Une relation dont l'autre extrémité est déjà supprimée n'est pas listée.
- `index` : les index de la table.
- Les deux listes peuvent être vides : la confirmation est **exigée à chaque suppression**.

Le front affiche ces liens, demande la confirmation, puis renvoie la requête avec `?confirme_suppression=true`.

**2e appel, avec confirmation : 200**

```json
{ "id_table": "tbl_client_001", "numero_sequence": 3 }
```

**Comportement**

- La table et ses colonnes reçoivent une date de suppression ; les colonnes déjà supprimées gardent leur date d'origine.
- Une opération `suppression` est inscrite avec le numéro de séquence suivant et l'**état avant** de la table
  (au format ChartDB), pour pouvoir la restituer dans l'historique.
- Les relations et index liés **ne sont pas modifiés** : ils disparaissent du schéma renvoyé par
  `GET /api/projets/{id_projet}` avec leur table. Le **nom** de la table redevient libre (RG-10) ; son **identifiant**
  ne peut resservir que pour **restaurer** cette table, par `POST …/tables` (voir l'ajout d'une table).

**Erreurs** (dans cet ordre : 401, 404 projet, 403, 422, 404 table, 409)

| Code | Cas |
|---|---|
| 401 | Utilisateur non identifié |
| 404 | Projet introuvable |
| 403 | N'est pas concepteur du projet |
| 422 | `id_table` de plus de 25 caractères, ou `confirme_suppression` qui n'est pas un booléen |
| 404 | Table introuvable dans ce projet : inconnue, **déjà supprimée**, d'un autre projet, ou identifiant d'une colonne (`"Table introuvable dans ce projet."`) |
| 409 | Confirmation requise (liens listés ci-dessus) |

Le 403 passe avant le 404 de la table : un non-concepteur ne peut pas sonder les identifiants.

---

## 4. Ordre des contrôles, route par route

| Route | Ordre |
|---|---|
| `POST /api/projets` | 401 → 422 |
| `GET /api/projets/{id}` | 401 → 404 → 403 |
| `POST …/import` | 401 → 422 (corps) → 404 → 403 → 413 → 409 → écriture (422 si la base refuse) |
| `POST …/tables` | 401 → 404 → 403 → 422 (corps) → 422 (nom, types, identifiants) → écriture (ajout ou restauration) |
| `DELETE …/tables/{id_table}` | 401 → 404 → 403 → 422 (paramètres) → 404 (table) → 409 → écriture |

---

## 5. Écarts et choix par rapport au dossier

Le dossier V1.2 fait foi. Ces points précisent ou complètent ce qu'il dit.

| Sujet | Choix réalisé |
|---|---|
| Ordre des contrôles de l'ajout et de la suppression | 401 → 404 (projet) → 403 → 422, obtenu avec une dépendance FastAPI : la validation du corps passe **après** les droits |
| Projet inexistant | 404 sur toutes les routes de projet (le dossier ne prévoit pas ce cas pour l'ajout et la suppression) |
| Table inconnue à la suppression | 404 (le dossier ne prévoit pas ce cas), après les droits |
| Format des liens du 409 de suppression | Le § 5.1.7 laisse `[...]` : `cles_etrangeres` reprend les champs de `DBRelationship`, `index` donne `{id, name}` |
| Confirmation sans lien | Exigée à chaque suppression, comme le diagramme du dossier (fig. 34). Le § 4.5.11 demande de le confirmer avec l'équipe |
| Nom et description d'un projet | Espaces retirés ; description vide enregistrée à `null` (le dossier dit « vide si non donnée ») |
| Nature d'événement `CREATION_PROJET` | Absente de la liste du chapitre 3 : à y ajouter |
| RG-10 | Au sein d'un même schéma SQL (dossier, § 4.2.7), **sans tenir compte de la casse** ; règles de nommage (refus et avertissements) d'après le cahier des charges, § 3.3.1.4 : à faire valider par le client |
| RG-11 | Types de colonnes limités aux listes de ChartDB v1.20.1 selon le dialecte du projet (CU 2.1 étape 3) : 422 à l'ajout, avertissement à l'import |
| RG-09 et P3 | Un identifiant supprimé peut resservir pour **restaurer** sa table dans le même projet (annuler une suppression) ; les autres cas restent refusés |
| Version à l'import | Aucune (dossier, § 4.2.5) : `import_dump.id_version_produite` reste vide |
| Prise de main (RG-29) | Non contrôlée (CU 2.6) |
| Relations et index à la suppression d'une table | Non traités, ils disparaissent du schéma avec leur table (dossier, § 4.5.11) |

---

## 6. Ce que le front doit savoir

- **L'en-tête `X-User-Id` va dans les en-têtes HTTP**, pas dans le corps.
- **Afficher les avertissements** : `avertissements` (liste) est présent dans chaque réponse d'ajout de table et d'import, même vide ; `avertissement` (un seul, clé primaire) reste présent pour compatibilité.
- **Annuler une suppression** : renvoyer la table supprimée telle quelle par `POST …/tables` ; la réponse a `restauree: true`.
- **Proposer les types** de la liste admise pour le dialecte du projet (l'éditeur ChartDB le fait déjà) : un autre type donne un 422.
- **Gérer le 409** des deux routes de confirmation : afficher, demander, renvoyer avec le paramètre de confirmation.
- **Un 422 de validation** a un `detail` en **liste** (champ par champ) ; un 422 métier a un `detail` en **texte**.
- **Le front génère les identifiants ChartDB** : un identifiant déjà utilisé donne un 422, sauf pour restaurer une table supprimée du même projet.
- **L'ordre des colonnes** dans `fields` devient leur rang ; il est conservé à l'ouverture du projet.
- **Pas de temps réel** pour l'instant : un ajout ou une suppression n'est pas poussé aux autres participants.
- **Un dump n'est jamais envoyé** : seul le diagramme, le nom, le dialecte et la taille du fichier, et le rapport.
