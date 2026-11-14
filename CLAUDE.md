# DraftDB — dépôt back (contexte pour Claude Code)

> Les documents de référence sont dans `docs/` : cahier des charges, étude de faisabilité,
> dossier de conception (chapitres 1 à 3, V1.1). **Le dossier de conception fait foi.**
> Si une demande contredit ces documents, signale-le au lieu de trancher.

## Le projet

DraftDB (SAÉ 5.A.01, BUT3 Informatique, IUT de Montreuil, client : Thomas LOUVET) est une application
web de conception collaborative de schémas de bases de données : plusieurs personnes éditent le même
schéma, le versionnent, le font approuver, puis en tirent des scripts SQL pour MySQL et PostgreSQL.
Le front est l'éditeur open source ChartDB adapté (dépôt séparé). **Ce dépôt contient uniquement le
serveur (back-end).**

## Périmètre de ce dépôt

- Ne travailler que sur le back : API, accès à la base, logique métier, tests du back.
- Ne pas toucher au front (dépôt ChartDB), ni à l'intégration continue, ni au déploiement :
  ce sont les rôles d'autres membres de l'équipe.
- Ne faire que ce que demande le ticket Jira en cours, ni plus ni moins.

## Stack (issue du dossier de conception)

| Élément | Choix |
|---|---|
| API | Python, FastAPI (documentation Swagger sur `/docs`, montrée en soutenance) |
| Base de l'application | PostgreSQL 16, lancée par `docker-compose.yml` |
| Temps réel (sprints suivants) | pycrdt-websocket |
| Mots de passe (sprints suivants) | Argon2 |

## Base de données

- Le schéma est défini par **`db/01_schema.sql`** (traduction du MLD, § 3.2 du dossier).
  C'est la source de vérité : l'API utilise les tables existantes, elle ne les crée pas.
- Lancer la base : `docker compose up -d` (variables dans `.env`, modèle dans `.env.example`).
- 19 tables en 5 domaines : comptes et projets (`utilisateur`, `session`, `projet`, `participation`,
  `evenement_journal`), structure du schéma (`element_schema`, `table_schema`, `colonne`,
  `index_schema`, `colonne_index`, `relation`), historique (`operation`, `version`, `decision`),
  livraison (`script_sql`, `import_dump`), collaboration (`discussion`, `message`, `prise_de_main`).
- Identifiants des tables, colonnes, index et relations : id ChartDB `VARCHAR(25)` fournis par le
  navigateur. Autres identifiants : UUID.

## Principes de conception à respecter (dossier, § 1.6)

- **P1** Le serveur reçoit et renvoie les objets au format JSON de ChartDB (`Diagram`, `DBTable`,
  `DBField`, `DBIndex`, `DBRelationship`).
- **P2** Le serveur fait foi : les droits sont vérifiés côté serveur pour chaque action.
- **P3** Les identifiants ChartDB ne sont jamais régénérés.
- **P4** Rien ne s'efface : suppressions logiques (`date_suppression`), historique conservé.
- **P5** Les projets sont « generic » ; le dialecte n'est choisi qu'à l'export ou à la migration.
- **P6** Aucune donnée envoyée à un service extérieur. Les dumps importés ne sont jamais conservés.

## Interdits

- Ne jamais exécuter le SQL d'un dump, ni se connecter aux bases du client.
- Ne jamais stocker le contenu d'un dump (RG-24) : seules ses caractéristiques et le rapport.
- Ne jamais commiter `.env` ni les fichiers de l'IDE (`.idea/`).

## Conventions Git

- Branches : `main` (versions taguées), `develop` (intégration), `feature/DRAFTDB-<n>-<sujet>`.
- Les PR partent vers `develop` et sont relues par un autre membre de l'équipe back.
- Chaque message de commit commence par la clé Jira, ex. `DRAFTDB-40 ajoute la route d'import`.
- Refactor important : préfixe `[REFACTOR]` dans le message de commit (consigne de l'IUT).

## Ticket en cours : DRAFTDB-40 (dev back de DRAFTDB-12 « Importer le dump d'une base existante », CU 1.5)

Première étape : le **squelette de l'API** (application FastAPI, configuration lue depuis `.env`,
connexion à PostgreSQL, route de santé, premier test). Ensuite seulement : la route d'import.

### Ce que fait le CU 1.5 (cahier des charges § 3.2.5)

L'analyse du dump se fait **dans le navigateur** (import SQL de ChartDB). Le serveur ne reçoit jamais
le fichier : il reçoit le diagramme obtenu, les caractéristiques du fichier et le rapport d'import.

Côté serveur :
1. Seul le **responsable** du projet peut importer.
2. Si le schéma du projet n'est pas vide, l'import le remplace seulement après confirmation ;
   l'état précédent reste dans l'historique (suppression logique).
3. Enregistrer, dans une seule transaction : les éléments du schéma, une `version` (instantané du
   diagramme), une ligne `import_dump` (rapport compris) et un événement `IMPORT` dans
   `evenement_journal`.
4. Aucune instruction n'est ignorée en silence : le rapport liste tout ce qui n'a pas été repris.
5. Taille maximale du fichier : à fixer (paramètre de configuration).

### À valider avec l'équipe avant de coder la route d'import

- Le contrat de la route (URL, corps JSON, codes de retour).
- Le mode d'accès à la base depuis Python (SQL direct ou ORM sur les tables existantes).
- L'authentification n'est pas traitée au sprint 1 : prévoir où se brancheront le login et le
  contrôle des droits, sans les implémenter.
