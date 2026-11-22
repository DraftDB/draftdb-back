# DraftDB : back-end (contexte pour Claude Code)

## Règles de travail avec Claude (à respecter en priorité)

1. **Répondre toujours en français** : explications, messages de commit, descriptions de PR, commentaires
   et docstrings du code.
2. **Ne jamais lancer `git commit` ni `git push` sans ma permission explicite, donnée à ce moment-là.**
   Une permission pour un commit ne vaut pas pour les suivants. Même si un hook ou un outil le réclame,
   ne pas commiter ni pousser : me proposer à la place le message de commit et les commandes à lancer.
3. **Toujours passer par une PR.** Jamais de push direct sur `develop` ni sur `main`, jamais de
   force-push. Ne pas créer, ne pas merger une PR sans mon accord. Les PR visent `develop`.
4. **Ne faire que ce que demande le ticket Jira en cours, ni plus ni moins.** Si autre chose mérite d'être
   corrigé, me le signaler au lieu de le faire.
5. **Le dossier de conception fait foi.** Si une demande le contredit, me le signaler au lieu de trancher.
   Quand le dossier est silencieux, proposer un choix et l'indiquer dans la PR (section « Points à valider »).
6. **Avant de coder, lire la section du dossier qui décrit le cas d'utilisation** (chapitre 4) et le contrat
   de la route (§ 5.1).
7. **Toute fonctionnalité est testée** et les tests passent (`python -m pytest`) avant de proposer une PR.
8. **Confirmer avant toute action difficile à annuler** (supprimer des données, `docker compose down -v`,
   réécrire l'historique Git).
9. **Ne jamais inventer** : si une information manque (ticket Jira vide, règle absente du dossier), le dire.

## Le projet

DraftDB est une application web de **conception collaborative de schémas de bases de données** (SAÉ 5.A.01,
BUT 3 Informatique, IUT de Montreuil, client : Thomas LOUVET). Plusieurs personnes éditent le même schéma
en atelier, le versionnent, le font approuver par un relecteur, puis en tirent les scripts SQL de création
et de migration pour **MySQL et PostgreSQL**. Elle ne se connecte jamais aux bases du client : elle produit
des fichiers `.sql`.

- Le **front** est l'éditeur open source **ChartDB** adapté (TypeScript, React 18, React Flow, Yjs), dans un
  **dépôt séparé**. **Ce dépôt ne contient que le serveur (back-end).**
- Profils : utilisateur, participant, **responsable** de projet (unique, transmissible), **concepteur** (modifie
  le schéma), **relecteur** (approuve ou refuse une version). Les rôles se cumulent, projet par projet.
- Processus : P0 accéder à l'application, P1 mettre en place un projet, P2 concevoir le schéma en atelier,
  P3 valider et livrer une évolution.

## Stack

| Élément | Choix |
|---|---|
| API | Python 3.13+, FastAPI (Swagger sur `/api/docs`, montré en soutenance) |
| Accès à la base | SQLAlchemy 2 + psycopg 3, **SQL direct** (`text()`), pas de modèles ORM |
| Validation | Pydantic 2 (DTO dans `app/schemas/`), `pydantic-settings` pour la configuration |
| Base de l'application | PostgreSQL 16, lancée par `docker-compose.yml` (port hôte **5433**) |
| Tests | pytest, `httpx`/`TestClient`, vraie base PostgreSQL |
| Sprints suivants | `pycrdt-websocket` (temps réel), Argon2 (mots de passe), Docker et Jenkins (livraison) |

## Structure du dépôt

```text
app/
  main.py            création de l'application, toutes les routes sous /api
  config.py          configuration lue dans .env (connexion base, taille max d'un import)
  database.py        get_db : une session par requête, AUCUN commit automatique
  security.py        get_current_user : identification (provisoire, en-tête X-User-Id)
  routers/           une route par sujet (health, imports, ouverture, projets, tables)
  services/          logique métier (acces, importer, lecture, projets, tables)
  schemas/           DTO Pydantic : objets ChartDB (chartdb.py), requêtes et réponses
db/
  01_schema.sql      schéma de la base, SOURCE DE VÉRITÉ (traduction du MLD)
  02_seed.sql        données de test, développement uniquement
tests/               tests unitaires (sans base) et d'intégration (avec base)
docs/                cahier des charges, étude de faisabilité, dossier de conception
```

Pour ajouter une fonctionnalité : un fichier dans `app/routers/` (+ `app/services/` et `app/schemas/`),
puis l'inclure dans `app/main.py`.

## Lancer le projet

```bash
cp .env.example .env                       # une seule fois
docker compose up -d                       # PostgreSQL 16 (schéma + seed au 1er démarrage du volume)
python -m venv .venv && source .venv/bin/activate     # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload              # http://127.0.0.1:8000/api/docs
```

- Le schéma et le seed ne se jouent qu'au **premier démarrage du volume**. Pour les rejouer :
  `docker compose down -v` puis `docker compose up -d` (**efface les données locales**). Pour garder les
  données après une modification du schéma, écrire un `ALTER TABLE` et le communiquer à l'équipe.
- Données de test (Swagger) : en-tête `X-User-Id` = `00000000-0000-0000-0000-000000000001` (responsable et
  concepteur), `…0002` (relecteur), `…0003` (étranger au projet) ; projet `00000000-0000-0000-0000-0000000000a1`.
- Ne jamais commiter `.env` ni `.idea/`.

## Tester

```bash
python -m pytest                           # tout
python -m pytest tests/test_x.py -v        # un fichier
```

- Tests marqués `integration` : ils ont besoin de la base démarrée et d'un `.env`, sinon ils sont **sautés**.
- Chaque test d'intégration tourne dans une **transaction annulée** à la fin : rien ne reste en base.
- Fixtures de `tests/conftest.py` : `client_db`, `db_session`, `monde` (3 utilisateurs et un projet),
  `en_tete(id)`, et `i("nom")` qui suffixe les identifiants ChartDB pour qu'ils soient uniques à chaque exécution.
- **Piège** : la route et les fixtures partagent la même session. Un `rollback()` dans la route annule aussi
  les données de la fixture : ne pas comparer des totaux avant/après, filtrer sur les identifiants du test.
- Le `StarletteDeprecationWarning` sur `httpx` est connu et sans conséquence.

## API : conventions

- Préfixe `/api`, JSON, documentation sur `/api/docs`. Les objets du schéma suivent le format **ChartDB** (P1).
- **Identification provisoire** : en-tête `X-User-Id` (401 sinon). Elle sera remplacée par le login (CU 0.1 à 0.3)
  sans changer les routes.
- **Ordre des contrôles** : 401, puis 403 (droits), puis 404/422/409. Les droits sont vérifiés avant de valider
  le corps (voir `projet_modifiable` dans `app/routers/tables.py`).
- **Erreurs** : `{"detail": ...}`. Liste pour une validation du corps, texte ou objet pour une erreur métier.
  Confirmation requise : **409** `{"detail": {"code": "CONFIRMATION_REQUISE", ...}}`, rien n'est modifié.
- Une valeur refusée par la base (caractère NUL) donne un **422** avec rollback, jamais un 500.
- Routes (selon l'avancement des PR) : `GET /api/health`, `POST /api/projets`, `GET /api/projets/{id}`,
  `POST /api/projets/{id}/import`, `POST /api/projets/{id}/tables`,
  `DELETE /api/projets/{id}/tables/{id_table}`.

## Base de données

- `db/01_schema.sql` est la source de vérité : **l'API utilise les tables, elle ne les crée pas.**
- 19 tables en 5 domaines : comptes et projets (`utilisateur`, `session`, `projet`, `participation`,
  `evenement_journal`), structure du schéma (`element_schema`, `table_schema`, `colonne`, `index_schema`,
  `colonne_index`, `relation`), historique (`operation`, `version`, `decision`), livraison (`script_sql`,
  `import_dump`), collaboration (`discussion`, `message`, `prise_de_main`).
- Identifiants des tables, colonnes, index et relations : **id ChartDB, `VARCHAR(25)`**, fournis par le
  navigateur et jamais régénérés. Les autres identifiants sont des UUID. Dates en `TIMESTAMPTZ`.
- Seul `element_schema` (tables et colonnes) porte `date_suppression` : la visibilité d'un index ou d'une
  relation dépend de sa table ou de sa colonne.
- Les règles de gestion (RG-xx) sont portées par des `CHECK`, des `UNIQUE` et un index partiel ; les autres
  sont contrôlées par l'API.

## Principes de conception (dossier, § 1.6)

- **P1** Le serveur reçoit et renvoie les objets au format JSON de ChartDB.
- **P2** Le serveur fait foi : droits, règles et numéros de séquence vérifiés ou calculés côté serveur.
- **P3** Les identifiants ChartDB sont conservés tels quels ; un identifiant déjà utilisé est refusé (422).
- **P4** Rien ne s'efface : suppressions **logiques**, historique et décisions conservés.
- **P5** Les projets sont « generic » ; le dialecte n'est choisi qu'à l'import, à l'export ou à la migration.
- **P6** Aucune donnée vers un service extérieur ; un dump importé n'est jamais conservé (RG-24).

## Conventions de code

- Trois niveaux : **route** (reçoit, délègue), **service** (logique métier), **SQL** via `text()` avec
  paramètres nommés. Jamais de SQL construit par concaténation de valeurs.
- **Transactions** : `get_db` ne commite jamais. Une route qui écrit regroupe ses écritures dans une seule
  transaction et appelle `db.commit()` **une fois**, à la fin. Le service n'appelle pas `commit()` (l'import,
  plus ancien, le fait lui-même).
- **Numéro de séquence (RG-16)** : charger le projet avec `charger_projet(db, id, verrouiller=True)`
  (`FOR UPDATE`), prendre `numero_sequence + 1`, l'écrire dans `operation` **et** dans `projet`.
- Domaine en français (`projet`, `table`, `colonne`, `participation`), commentaires et docstrings en français,
  avec la référence de la règle appliquée (RG-xx, P1 à P6, EX-xx).
- Pas de refactor hors ticket. Un refactor important se fait dans un commit à part préfixé `[REFACTOR]`.

## Conventions Git et PR

- Branches : `main` (versions taguées), `develop` (intégration), `feature/DRAFTDB-<n>-<sujet>`
  (`<n>` = ticket Jira de dev back, par exemple `feature/DRAFTDB-43-supprimer-table`).
- Chaque message de commit commence par la clé Jira : `DRAFTDB-43 ajoute la route de suppression d'une table`.
- Une PR par ticket, vers `develop`, relue par un **autre membre de l'équipe back**.
- Description de PR : contexte et dépendances, ce que ça fait, fichiers, **points à valider**, tests
  (nombre et résultat), comment tester dans Swagger.
- PR empilées : indiquer la dépendance en tête de description et viser la branche parente tant qu'elle n'est
  pas mergée ; la base repasse à `develop` ensuite.
- Aucun CI pour l'instant : lancer `python -m pytest` avant chaque PR.

## Périmètre et interdits

- Ne travailler que sur le back (API, accès base, logique métier, tests). Ne pas toucher au front, à
  l'intégration continue ni au déploiement : ce sont d'autres rôles.
- Ne jamais exécuter le SQL d'un dump, ni se connecter aux bases du client.
- Ne jamais stocker le contenu d'un dump (RG-24) : seulement ses caractéristiques et le rapport.
- Ne jamais mettre de secret dans le dépôt.

## Documents de référence (`docs/`)

Cahier des charges (le « quoi », EX-01 à EX-17), étude de faisabilité, **dossier d'architecture et de
conception** (le « comment » : modèles, cas d'utilisation, contrats de l'API). La version à jour est la **V1.2**
(chapitres 4 et 5 : détail des cas d'utilisation et spécifications techniques).

## Calendrier et suivi

Méthode Scrum, 4 sprints : S1 du 04/11 au 26/11/2026 (revue le 26/11), S2 jusqu'au 10/12, S3 jusqu'au 06/01
(comité de pilotage le 16/12, version V1), S4 du 07/01 au 15/01/2027 (recette). Le suivi des tickets est dans
Jira ; **l'état d'avancement se lit dans Jira et dans les PR ouvertes**, pas dans ce fichier.