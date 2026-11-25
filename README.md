# DraftDB — API (back-end)

![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.162-009688?logo=fastapi&logoColor=white)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![SQLAlchemy 2](https://img.shields.io/badge/SQLAlchemy-2.1-D71F00?logo=sqlalchemy&logoColor=white)
![Pydantic 2](https://img.shields.io/badge/Pydantic-2-E92063?logo=pydantic&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![OpenAPI Swagger](https://img.shields.io/badge/API-OpenAPI%20%2F%20Swagger-85EA2D?logo=swagger&logoColor=black)
![SAÉ 5.A.01](https://img.shields.io/badge/SA%C3%89-5.A.01-8A2BE2)
[![Licence AGPL-3.0](https://img.shields.io/badge/licence-AGPL--3.0-blue)](LICENSE)

API de **DraftDB**, une application web de conception collaborative de schémas de bases de données :
plusieurs personnes dessinent le même schéma, le versionnent, le font approuver, puis en tirent les scripts SQL
de création et de migration pour **MySQL** et **PostgreSQL**.

Projet de SAÉ 5.A.01 (BUT 3 Informatique, IUT de Montreuil), pour le client Thomas LOUVET.

Ce dépôt contient le **back-end** : une API REST en Python (FastAPI) et le schéma de la base PostgreSQL.
L'éditeur de schémas est **ChartDB** (projet open source, voir [Licence](#licence)), adapté par l'équipe dans un
**dépôt séparé** : le front a besoin de cette API pour enregistrer quoi que ce soit.

| Document | Contenu |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Organisation du code, règles entre les couches, transactions, base de données, tests, décisions |
| [`docs/CONTRAT_API.md`](docs/CONTRAT_API.md) | Contrat détaillé de chaque route : entrées, sorties, erreurs, exemples réels |
| [`docs/API.md`](docs/API.md) | Vue d'ensemble : routes, droits, correspondance avec les exigences du client, ce qui reste à faire |
| [`CLAUDE.md`](CLAUDE.md) | Consignes de travail pour Claude Code (règles, conventions, commandes) |
| [`db/01_schema.sql`](db/01_schema.sql) | Schéma de la base : **source de vérité** |
| [`.env.example`](.env.example) | Variables de configuration |
| [`docs/`](docs/) | Cahier des charges, étude de faisabilité, dossier de conception (chapitres 1 à 3, V1.1), présentation de soutenance (PDF) |
| [`docs/MODIFICATIONS_DOSSIER_V1.3.md`](docs/MODIFICATIONS_DOSSIER_V1.3.md) | Modifications prévues pour la V1.3 du dossier de conception |
| [`.github/workflows/`](.github/workflows/) | Intégration continue (tests) et création des releases |

---

## Où en est le projet

Sprint 1 (du 04/11 au 26/11/2026) : les cas d'utilisation suivants sont réalisés côté serveur.

| Cas d'utilisation | Route | Droits |
|---|---|---|
| Santé de l'API | `GET /api/health` | public |
| CU 1.1 Créer un projet | `POST /api/projets` | utilisateur identifié |
| CU 1.6 Ouvrir un projet | `GET /api/projets/{id_projet}` | participant du projet |
| CU 1.5 Importer le dump d'une base existante | `POST /api/projets/{id_projet}/import` | responsable du projet |
| CU 2.1 Ajouter une table | `POST /api/projets/{id_projet}/tables` | concepteur du projet |
| CU 2.3 Supprimer une table | `DELETE /api/projets/{id_projet}/tables/{id_table}` | concepteur du projet |

L'identification est **provisoire** (en-tête `X-User-Id`) : les comptes et la connexion (CU 0.1 à 0.3) arrivent plus tard.
Le détail des routes est dans [`docs/CONTRAT_API.md`](docs/CONTRAT_API.md), la liste de ce qui reste à faire dans
[`docs/API.md`](docs/API.md).

---

## Versions utilisées

Ce sont celles avec lesquelles le projet est développé et testé. D'autres versions récentes fonctionneront
sans doute, mais elles n'ont pas été vérifiées.

| Outil | Version | Où elle intervient |
|---|---|---|
| Docker Desktop (Windows, macOS) ou Docker Engine (Linux) | version récente, avec `docker compose` (v2) | PostgreSQL (rien d'autre à installer pour la base) |
| WSL 2 (Windows seulement) | avec une distribution Ubuntu | Moteur de Docker Desktop |
| Python | **3.13** ou plus récent (testé en 3.13 et 3.14 ; la CI utilise 3.14) | API |
| PostgreSQL | **16** | Base de données (image `postgres:16`) |
| FastAPI / Uvicorn | 0.162.7 / 0.54.0 | API et serveur |
| SQLAlchemy / psycopg | 2.1.8 / 3.3.9 | Accès à la base (SQL direct) |
| Pydantic / pydantic-settings | 2.x / 2.16.3 | Validation et configuration |
| pytest / httpx | 9.2.0 / 0.28.1 | Tests |
| Git | récent | Clonage |

Les dépendances sont dans `requirements.txt` (exécution) et `requirements-dev.txt` (tests).

---

## Windows : installer les outils (une seule fois)

La base PostgreSQL tourne dans un conteneur **Linux**. Sous Windows, il faut donc **Docker Desktop**, qui s'appuie
sur **WSL 2**. Sans eux, la commande `docker compose` n'existe pas ou ne trouve pas de moteur. L'API demande
**Python 3.13 ou plus récent**.

1. **Vérifier la virtualisation** : Gestionnaire des tâches, onglet *Performances*, *UC* : « Virtualisation » doit
   indiquer « Activé ». Sinon, l'activer dans le BIOS (*Intel VT-x*, *SVM* ou *Virtualization Technology*).
2. **Installer WSL 2** : dans un PowerShell **en administrateur**, `wsl --install`, puis redémarrer. Au redémarrage,
   Ubuntu demande un nom d'utilisateur et un mot de passe Linux (sans rapport avec Windows). Vérifier avec `wsl -l -v` :
   la colonne `VERSION` doit afficher `2` (sinon `wsl --update`).
3. **Installer Docker Desktop** (https://www.docker.com/products/docker-desktop/) en laissant cochée l'option
   *Use WSL 2 instead of Hyper-V*, puis le **lancer** et attendre « Engine running ». Il doit rester ouvert tant qu'on
   utilise le projet.
4. **Installer Python 3.13 ou plus récent** (https://www.python.org/downloads/). Avec l'installateur classique, cocher
   **« Add python.exe to PATH »** sur le premier écran : sans cette case, la commande `python` n'est pas trouvée.
   Si `python` ouvre le **Microsoft Store** au lieu de répondre, désactiver les raccourcis de Windows : *Paramètres*,
   *Applications*, *Paramètres avancés des applications*, *Alias d'exécution d'application*, puis désactiver
   `python.exe` et `python3.exe`.
5. **Installer Git pour Windows** (https://git-scm.com/download/win).

Vérifier dans un **nouveau** PowerShell :

```powershell
python --version             # doit afficher 3.13 ou plus
git --version
docker --version
docker compose version
docker run --rm hello-world
```

La dernière commande doit afficher « Hello from Docker! ».

## Linux et macOS : installer les outils (une seule fois)

- **Docker** :
  - macOS : Docker Desktop (https://www.docker.com/products/docker-desktop/) ;
  - Linux : Docker Engine et le plugin `docker compose` (https://docs.docker.com/engine/install/). Pour lancer `docker`
    sans `sudo`, ajouter son utilisateur au groupe `docker` (`sudo usermod -aG docker $USER`), puis se déconnecter et
    se reconnecter.
- **Python 3.13 ou plus récent** : vérifier avec `python3 --version`.
  - Ubuntu : `sudo apt install python3 python3-venv python3-pip`. **Ubuntu 24.04 fournit Python 3.12, trop ancien** :
    installer `python3.13` et `python3.13-venv` (par exemple depuis le PPA *deadsnakes*), puis créer l'environnement avec
    `python3.13 -m venv .venv`.
  - macOS : l'installateur de https://www.python.org/downloads/ ou `brew install python@3.13`.
- **Git** : `sudo apt install git` (Ubuntu) ; sur macOS, il est proposé au premier appel de `git`.

Sous Linux et macOS, la commande s'appelle `python3` **tant que l'environnement virtuel n'est pas activé** ; une fois
activé, `python` suffit.

---

## Démarrage rapide

Docker Desktop doit être **lancé** (Windows, macOS) avant `docker compose`.

**Windows (PowerShell)** :

```powershell
git clone https://github.com/DraftDB/draftdb-back.git
cd draftdb-back

Copy-Item .env.example .env          # configuration (les valeurs par défaut conviennent au développement)
docker compose up -d                 # PostgreSQL 16 : crée la base, joue db/01_schema.sql puis db/02_seed.sql

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

python -m uvicorn app.main:app --reload
```

**Linux et macOS** :

```bash
git clone https://github.com/DraftDB/draftdb-back.git
cd draftdb-back

cp .env.example .env
docker compose up -d

python3 -m venv .venv                # ou python3.13 -m venv .venv (voir plus haut)
source .venv/bin/activate
python -m pip install -r requirements-dev.txt

python -m uvicorn app.main:app --reload
```

Au **tout premier** `docker compose up -d`, PostgreSQL met quelques secondes à créer la base et à jouer les scripts de
`db/`. Pendant ce temps, `/api/health` répond `503` avec `"database": "indisponible"` : attendre puis recharger. La base
est prête quand `docker compose logs db` affiche « database system is ready to accept connections » après la ligne
« PostgreSQL init process complete ».

À chaque nouveau terminal, **réactiver l'environnement virtuel** avant de lancer l'API ou les tests
(`.\.venv\Scripts\Activate.ps1` ou `source .venv/bin/activate`) : le début de la ligne de commande affiche alors `(.venv)`.

| Adresse | Rôle |
|---|---|
| http://127.0.0.1:8000/api/docs | Documentation interactive (Swagger), pour essayer les routes |
| http://127.0.0.1:8000/api/redoc | Documentation en lecture (ReDoc) |
| http://127.0.0.1:8000/api/health | État de l'API et de la base : `{"status": "ok", "database": "ok"}` |

Vérifier que la base tourne : `docker compose ps` (le service `db` doit être « running »).

> Toujours `python -m pip` plutôt que `pip`, et `python -m uvicorn` plutôt que `uvicorn` : voir le
> [dépannage](#dépannage).

### Essayer l'API dans Swagger

Les routes qui ne sont pas publiques demandent l'en-tête **`X-User-Id`** (identification provisoire). Il va dans les
**en-têtes** de la requête, pas dans le corps JSON. Avec les données de test (voir plus bas) :

1. Ouvrir http://127.0.0.1:8000/api/docs, dérouler `POST /api/projets/{id_projet}/tables`, puis **Try it out**.
2. Renseigner `id_projet` = `00000000-0000-0000-0000-0000000000a1` et `x-user-id` = `00000000-0000-0000-0000-000000000001`.
3. Coller un corps, par exemple :

```json
{
  "id": "tbl_client_001",
  "name": "client",
  "fields": [
    {"id": "col_client_id", "name": "id", "type": {"id": "integer"}, "primaryKey": true, "nullable": false}
  ]
}
```

4. **Execute** : réponse **201** avec la table, son numéro de séquence et ses avertissements éventuels (clé primaire
   absente, mot réservé, nom à protéger par des guillemets).

> Les identifiants ChartDB (`id` de la table, des colonnes, des index) sont uniques dans toute la base. Renvoyer une table
> **supprimée** du même projet, avec les mêmes `id`, la **restaure** (`"restauree": true`). Sinon, pour rejouer l'exemple,
> changer les `id` : un identifiant déjà utilisé donne un **422** « Identifiant ChartDB déjà utilisé ».
>
> Les noms et les types sont contrôlés : guillemet, espace en bordure ou deux tables `Client` et `client` donnent un
> **422** ; le type d'une colonne doit être un type ChartDB admis pour le dialecte du projet (`int`, `varchar`, `uuid`…
> pour un projet `generic`).

Chaque route, avec ses réponses d'erreur, est décrite dans [`docs/CONTRAT_API.md`](docs/CONTRAT_API.md).

### Avec le front (ChartDB adapté)

Le front est dans un **dépôt séparé** de l'organisation [DraftDB](https://github.com/DraftDB) ; son installation est
décrite dans son propre README. Ce serveur doit tourner en même temps, sur http://127.0.0.1:8000, avec ses routes sous
`/api`.

> **Limite actuelle** : l'API ne configure pas encore de **CORS**. Si le front est servi depuis une autre adresse (un
> autre port, par exemple un serveur de développement), le navigateur bloque ses appels à l'API (erreur « CORS » dans la
> console). Dans le déploiement prévu (dossier de conception, figure 1), un reverse proxy transmet `/api/` au serveur :
> si le front est servi par ce même proxy, il a la même adresse que l'API et le problème ne se pose pas.

---

## Configuration

Elle se lit dans le fichier `.env` (modèle : [`.env.example`](.env.example)) ou dans l'environnement. `.env` n'est
jamais versionné. Les variables `POSTGRES_*` servent **à la fois** au conteneur de la base et à l'API.

| Variable | Rôle | Défaut |
|---|---|---|
| `POSTGRES_USER` | Utilisateur de la base | — (obligatoire) |
| `POSTGRES_PASSWORD` | Mot de passe de la base | — (obligatoire) |
| `POSTGRES_DB` | Nom de la base | — (obligatoire) |
| `POSTGRES_HOST` | Où l'API joint la base | `localhost` |
| `POSTGRES_PORT` | Port de la base vu depuis la machine | `5433` (port publié par `docker-compose.yml`) |
| `IMPORT_TAILLE_MAX_OCTETS` | Taille maximale déclarée d'un dump importé | `52428800` (50 Mo, valeur provisoire) |

---

## Données de test

`docker compose up -d` joue `db/02_seed.sql` à la **création du volume**. Il contient, pour le **développement
uniquement** (ne jamais l'utiliser en production) :

| Utilisateur | `X-User-Id` | Rôle dans le projet de test |
|---|---|---|
| `responsable` | `00000000-0000-0000-0000-000000000001` | Responsable et concepteur |
| `relecteur` | `00000000-0000-0000-0000-000000000002` | Relecteur (ne peut pas modifier le schéma) |
| `etranger` | `00000000-0000-0000-0000-000000000003` | Ne participe pas au projet |

Projet de test : `00000000-0000-0000-0000-0000000000a1`.

Pour **rejouer** le schéma et les données de test : `docker compose down -v` puis `docker compose up -d`. Attention,
cela **efface la base locale**.

---

## Tests

```powershell
python -m pytest
```

- Les tests marqués `integration` ont besoin de la base démarrée (`docker compose up -d`) et d'un `.env`. Sinon, ils
  sont **sautés** (`skipped`), pas en échec.
- Chaque test d'intégration s'exécute dans une **transaction annulée** à la fin : aucune donnée ne reste en base.
- Les tests unitaires (validation des objets ChartDB, traduction en lignes de tables) tournent **sans base**.
- Un test précis : `python -m pytest tests/test_table_ajout.py -v`.
- L'avertissement `StarletteDeprecationWarning` (`httpx`) est connu et sans conséquence.

La stratégie de test est détaillée dans [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#tests).

---

## Intégration continue et releases

Deux workflows GitHub Actions sont dans [`.github/workflows/`](.github/workflows/) :

| Workflow | Quand | Ce qu'il fait |
|---|---|---|
| `ci.yml` | À chaque push et pull request sur `develop` et `main` | Démarre un PostgreSQL 16, joue `db/01_schema.sql` et `db/02_seed.sql`, puis lance toute la suite `pytest` (tests d'intégration compris) avec Python 3.14 |
| `release.yml` | À chaque tag `v*` poussé | Crée la release GitHub avec des notes générées à partir des PR, sauf si elle existe déjà |

Le résultat s'affiche dans l'onglet **Actions** du dépôt et en bas de chaque pull request. Dans le journal du job
`tests`, aucun test ne doit être « skipped » pour « Base PostgreSQL indisponible ».

Publier une version (après le merge de `develop` dans `main`) :

```powershell
git checkout main
git pull
git tag -a v0.2.0 -m "v0.2.0 : Sprint 2"
git push origin v0.2.0
```

Puis, dans l'onglet **Releases**, ouvrir la version et la modifier pour compléter les notes si besoin.

---

## Commandes utiles

| Besoin | Commande |
|---|---|
| Voir les logs de la base | `docker compose logs -f db` |
| Arrêter la base | `docker compose down` |
| Repartir d'une base vide (rejoue le schéma et le seed) | `docker compose down -v` puis `docker compose up -d` |
| Ouvrir un terminal SQL | `docker compose exec db psql -U draftdb -d draftdb` |
| Migrer une base existante sans la perdre | écrire un `ALTER TABLE` (voir les notes de la PR qui change le schéma) |

> Le dossier `db/` n'est rejoué **qu'à la création du volume**. Après une modification du schéma, `docker compose up`
> ne suffit pas.

---

## Organisation du dépôt

```text
app/
  main.py          création de l'application, toutes les routes sous /api
  config.py        configuration lue dans .env
  database.py      connexion PostgreSQL, une session par requête (aucun commit automatique)
  security.py      identification de l'utilisateur (provisoire : en-tête X-User-Id)
  routers/         une route par sujet : health, imports, ouverture, projets, tables
  services/        logique métier : acces, importer, lecture, projets, tables
  schemas/         objets Pydantic : format ChartDB, requêtes et réponses
db/
  01_schema.sql    schéma de la base (19 tables), source de vérité
  02_seed.sql      données de test, développement uniquement
tests/             tests unitaires (sans base) et d'intégration (avec base)
docs/              documentation du projet (Markdown) et documents de référence (PDF)
```

Les règles entre les couches sont dans [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Dépannage

**`python` n'est pas reconnu, ou ouvre le Microsoft Store** : Python n'est pas installé ou pas dans le `PATH`.
Réinstaller en cochant « Add python.exe to PATH », et désactiver les alias `python.exe` et `python3.exe` (voir
l'installation sous Windows). Sous Linux et macOS, utiliser `python3`.

**`pip install` échoue, ou l'API ne démarre pas avec une erreur de syntaxe ou d'import** : vérifier la version de
Python dans l'environnement activé avec `python --version` (3.13 au minimum). Si elle est trop ancienne, supprimer le
dossier `.venv`, puis le recréer avec la bonne version.

**`ModuleNotFoundError: No module named 'fastapi'`** (ou un autre module) : l'environnement virtuel n'est pas activé
dans ce terminal, ou les dépendances n'y sont pas installées. Activer `.venv`, puis relancer
`python -m pip install -r requirements-dev.txt`.

**`/api/health` répond `503`** : la base n'est pas joignable. Au premier démarrage, attendre quelques secondes
(voir le démarrage rapide) ; sinon vérifier `docker compose ps` et le fichier `.env`.

**`500 Internal Server Error`, avec une `ValidationError` sur `postgres_user` (ou `postgres_password`, `postgres_db`)
dans le terminal de l'API** : l'API démarre, mais la configuration n'est lue qu'au premier appel qui touche la base ;
le fichier `.env` est absent. Lancer `Copy-Item .env.example .env` (ou `cp .env.example .env`) **à la racine du dépôt**, et lancer
l'API depuis ce dossier.

**Le port 8000 est déjà utilisé** : lancer l'API sur un autre port,
`python -m uvicorn app.main:app --reload --port 8001`, et utiliser http://127.0.0.1:8001/api/docs.

**`401` « en-tête X-User-Id manquant »** : l'en-tête est absent, ou placé dans le corps JSON au lieu des **en-têtes**.
Dans un client REST, ouvrir la section *Headers* et y ajouter `X-User-Id`, avec `Content-Type: application/json`.

**`401` « Utilisateur inconnu »** : la base ne contient pas les données de test. Le seed ne se joue qu'à la création du
volume : `docker compose down -v` puis `docker compose up -d`.

**`405 Method Not Allowed` sur `/api/docs`** : `/api/docs` est la page Swagger et n'accepte que des `GET`. Les routes de
l'API sont sous `/api/projets/...`.

**Les tests d'intégration sont « skipped »** : la base n'est pas joignable. Vérifier `docker compose ps`, le fichier
`.env` (`POSTGRES_HOST`, `POSTGRES_PORT`) et que Docker Desktop est lancé.

**Après un `git pull`, les imports ou les tests échouent sur la base** : le schéma a peut-être changé. Voir « Repartir
d'une base vide » plus haut.

**« Une stratégie de contrôle d'application a bloqué ce fichier »** : Windows peut bloquer les exécutables de
`.venv\Scripts\` (`pip.exe`, `uvicorn.exe`…). Passer par Python : `python -m pip …`, `python -m uvicorn …`.

**PowerShell refuse d'activer l'environnement virtuel** :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**`docker` n'est pas reconnu, ou « Cannot connect to the Docker daemon »** : Docker Desktop n'est pas installé, pas
lancé, ou le terminal a été ouvert avant l'installation (en ouvrir un nouveau). « WSL 2 installation is incomplete » :
`wsl --update` dans un PowerShell administrateur, puis relancer Docker Desktop.

**Le port 5433 est déjà utilisé** : dans `docker-compose.yml`, remplacer `"5433:5432"` par un autre port (par exemple
`"5434:5432"`) et mettre le même dans `POSTGRES_PORT` du `.env`.

---

## Contribuer

- Branches : `main` (versions taguées), `develop` (intégration), `feature/DRAFTDB-<n>-<sujet>`.
- Messages de commit : ils commencent par la clé Jira, par exemple `DRAFTDB-43 ajoute la route de suppression d'une table`.
- Toute modification passe par une **pull request vers `develop`**, relue par un autre membre de l'équipe back
  (GitHub exige des approbations avant le merge).
- Avant une PR : `python -m pytest`, et mettre à jour la documentation (`docs/CONTRAT_API.md`, `docs/API.md`) si une
  route change.
- Sur la PR, le job `tests` de l'intégration continue doit être **vert** avant le merge.

Les conventions de code sont dans [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#conventions-de-code).

---

## Licence

Ce projet est publié sous la licence **GNU Affero General Public License version 3 (AGPL-3.0)**. Le texte complet est
dans [`LICENSE`](LICENSE).

**Pourquoi l'AGPL-3.0.** DraftDB est construit à partir de **ChartDB** (https://github.com/chartdb/chartdb), un éditeur
de diagrammes de bases de données open source publié sous AGPL-3.0, dont l'équipe a étudié la version 1.20.1 et qu'elle
a **adapté** : la partie visible (l'éditeur) est une version modifiée de ChartDB. L'AGPL-3.0 impose que toute version
modifiée, y compris celle qu'on met à disposition à travers un réseau (un site web), soit publiée avec son code
source sous la même licence. Ce dépôt (le serveur) ne reprend pas de code de ChartDB : il reprend son **format de
données** (tables, champs, index, relations). Il est publié sous la même licence pour que l'ensemble de DraftDB
(front et back) ait **une seule licence cohérente**, et parce que l'AGPL est faite pour les applications servies
sur un réseau.

Vous pouvez donc utiliser, étudier, modifier et redistribuer ce code, **y compris commercialement**, à condition de :

- **conserver la licence AGPL-3.0** et les mentions de droits d'auteur sur toute copie ou version modifiée ;
- **publier le code source de vos modifications** sous la même licence ;
- **proposer le code source à ses utilisateurs** si vous faites tourner une version modifiée en ligne (article 13).

**Ce que la licence ne couvre pas :**
- les dépendances listées dans `requirements.txt` et `requirements-dev.txt`, qui gardent chacune leur propre licence ;
- les documents du dossier `docs/` rédigés pour la SAÉ (cahier des charges, étude de faisabilité, dossier de conception) :
  ils sont fournis pour information.

Le projet est un travail pédagogique, fourni « en l'état », sans garantie d'aucune sorte.

Copyright (c) 2026 Fabio GUERREIRO MARQUES, Edin DUPUIS, Nicolas QUEMENER, Lino COUTURIER et Yohann LE COGUIC,
BUT Informatique, IUT de Montreuil.

---

## Crédits

- **ChartDB** (https://github.com/chartdb/chartdb, AGPL-3.0) : l'éditeur de schémas dont DraftDB est dérivé.
- Client : Thomas LOUVET.
- Équipe : Fabio GUERREIRO MARQUES, Edin DUPUIS, Nicolas QUEMENER, Lino COUTURIER, Yohann LE COGUIC (BUT 3
  Informatique, IUT de Montreuil, Université Paris 8).
