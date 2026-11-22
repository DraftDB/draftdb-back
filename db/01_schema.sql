-- =============================================================================
-- DraftDB : base de l'application (PostgreSQL 16)
-- Traduction du MLD du dossier de conception V1.1, § 3.2 :
--   figures 15 à 19 (tables), table 9 (clés étrangères),
--   table 10 (contraintes d'intégrité), table 11 (dictionnaire des données).
-- Ticket : DRAFTDB-52 Mise en place de la BDD
--
-- Conventions :
--   * Identifiants des tables, colonnes, index et relations du schéma :
--     id ChartDB, VARCHAR(25), fournis par le navigateur.
--   * Autres identifiants : UUID générés par la base (gen_random_uuid()).
--   * Dates : TIMESTAMPTZ.
--   * P4 « Rien ne s'efface » : aucune clé étrangère en ON DELETE CASCADE,
--     sauf Colonne_index (un index du schéma supprimé emporte ses lignes).
--   * Les contraintes « vérifiées par le serveur » (table 10, 2e partie)
--     ne sont pas ici : elles sont contrôlées par l'API.
--   * Lignes marquées [AJOUT] : non précisées dans le dossier (défauts,
--     index de performance, tailles absentes du dictionnaire).
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Domaine 1 : comptes, projets et journal (figure 15)
-- -----------------------------------------------------------------------------

CREATE TABLE utilisateur (
    id_utilisateur       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    login                VARCHAR(50)   NOT NULL,
    empreinte_mdp        VARCHAR(255)  NOT NULL,              -- empreinte Argon2, sel inclus
    date_creation        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    nb_echecs_connexion  SMALLINT      NOT NULL DEFAULT 0,
    bloque_jusqu_au      TIMESTAMPTZ,                         -- nul si le compte n'est pas bloqué
    CONSTRAINT uq_utilisateur_login UNIQUE (login),           -- RG-01
    CONSTRAINT ck_utilisateur_echecs CHECK (nb_echecs_connexion >= 0)
);

CREATE TABLE session (
    id_session              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    empreinte_jeton         VARCHAR(255)  NOT NULL,           -- le jeton lui-même n'est pas stocké
    date_ouverture          TIMESTAMPTZ   NOT NULL DEFAULT now(),
    date_derniere_activite  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    date_expiration         TIMESTAMPTZ   NOT NULL,
    date_fermeture          TIMESTAMPTZ,
    id_utilisateur          UUID          NOT NULL REFERENCES utilisateur (id_utilisateur),
    CONSTRAINT uq_session_jeton UNIQUE (empreinte_jeton)      -- [AJOUT] recherche de session par jeton
);

CREATE TABLE projet (
    id_projet        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    nom              VARCHAR(100)  NOT NULL,                  -- sert aussi de nom au diagramme ChartDB
    description      VARCHAR(500),
    date_creation    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    type_base        VARCHAR(10)   NOT NULL DEFAULT 'generic',
    annexes          JSONB         NOT NULL DEFAULT '{}'::jsonb,  -- zones, notes, types perso, dépendances de vues (format ChartDB)
    numero_sequence  BIGINT        NOT NULL DEFAULT 0,        -- numéro de la dernière opération appliquée
    id_responsable   UUID          NOT NULL REFERENCES utilisateur (id_utilisateur),
    CONSTRAINT ck_projet_type_base
        CHECK (type_base IN ('generic', 'mysql', 'postgresql'))  -- RG-11
);

CREATE TABLE participation (
    id_utilisateur   UUID         NOT NULL REFERENCES utilisateur (id_utilisateur),
    id_projet        UUID         NOT NULL REFERENCES projet (id_projet),
    est_concepteur   BOOLEAN      NOT NULL DEFAULT false,
    est_relecteur    BOOLEAN      NOT NULL DEFAULT false,
    date_invitation  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (id_utilisateur, id_projet),
    CONSTRAINT ck_participation_role
        CHECK (est_concepteur OR est_relecteur)                -- RG-06
);

CREATE TABLE evenement_journal (
    id_evenement    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    nature          VARCHAR(40)  NOT NULL,                    -- CONNEXION_REUSSIE, IMPORT, MIGRATION... (liste ouverte)
    horodatage      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    details         JSONB,
    id_utilisateur  UUID         REFERENCES utilisateur (id_utilisateur),  -- nullable (ex. connexion échouée)
    id_projet       UUID         REFERENCES projet (id_projet)             -- nullable
);

-- -----------------------------------------------------------------------------
-- Domaine 2 : structure du schéma (figure 16)
-- Spécialisation traduite par une clé primaire partagée :
-- table_schema et colonne ont pour clé l'id de element_schema.
-- -----------------------------------------------------------------------------

CREATE TABLE element_schema (
    id_element        VARCHAR(25)  PRIMARY KEY,               -- id ChartDB
    nature            VARCHAR(7)   NOT NULL,
    date_creation     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    date_suppression  TIMESTAMPTZ,                            -- suppression logique (P4)
    id_projet         UUID         NOT NULL REFERENCES projet (id_projet),
    CONSTRAINT ck_element_nature CHECK (nature IN ('TABLE', 'COLONNE'))
);

CREATE TABLE table_schema (
    id_element   VARCHAR(25)   PRIMARY KEY REFERENCES element_schema (id_element),
    nom          VARCHAR(63)   NOT NULL,                      -- limite commune MySQL / PostgreSQL
    schema_sql   VARCHAR(63),                                 -- « schema » de ChartDB, facultatif
    position_x   NUMERIC(8,2)  NOT NULL DEFAULT 0,
    position_y   NUMERIC(8,2)  NOT NULL DEFAULT 0,
    largeur      NUMERIC(8,2),
    couleur      CHAR(7),                                     -- ex. #8eb7ff
    commentaire  TEXT,                                        -- [AJOUT] type non précisé
    est_vue      BOOLEAN       NOT NULL DEFAULT false
);

CREATE TABLE colonne (
    id_element       VARCHAR(25)   PRIMARY KEY REFERENCES element_schema (id_element),
    nom              VARCHAR(63)   NOT NULL,
    rang             SMALLINT      NOT NULL,
    type_donnee      VARCHAR(30)   NOT NULL,                  -- type générique ChartDB : int, varchar, uuid...
    taille           VARCHAR(10),                             -- characterMaximumLength
    precision_num    SMALLINT,                                -- precision
    echelle          SMALLINT,                                -- scale
    nullable         BOOLEAN       NOT NULL DEFAULT true,
    est_unique       BOOLEAN       NOT NULL DEFAULT false,
    cle_primaire     BOOLEAN       NOT NULL DEFAULT false,
    auto_increment   BOOLEAN       NOT NULL DEFAULT false,
    valeur_defaut    VARCHAR(255),
    interclassement  VARCHAR(63),                             -- collation
    commentaire      TEXT,                                    -- [AJOUT] type non précisé
    id_table         VARCHAR(25)   NOT NULL REFERENCES table_schema (id_element),
    CONSTRAINT ck_colonne_rang CHECK (rang >= 1),                         -- RG-12
    CONSTRAINT ck_colonne_pk_non_nullable
        CHECK (NOT (cle_primaire AND nullable))                           -- RG-12
);

CREATE TABLE index_schema (
    id_index          VARCHAR(25)  PRIMARY KEY,               -- id ChartDB
    nom               VARCHAR(63)  NOT NULL,
    est_unique        BOOLEAN      NOT NULL DEFAULT false,
    type_index        VARCHAR(10),                            -- btree, hash, gin... facultatif
    est_cle_primaire  BOOLEAN      NOT NULL DEFAULT false,
    id_table          VARCHAR(25)  NOT NULL REFERENCES table_schema (id_element)
);

CREATE TABLE colonne_index (
    id_index    VARCHAR(25)  NOT NULL REFERENCES index_schema (id_index) ON DELETE CASCADE,
    id_colonne  VARCHAR(25)  NOT NULL REFERENCES colonne (id_element),
    rang        SMALLINT     NOT NULL,                        -- ordre dans fieldIds
    PRIMARY KEY (id_index, id_colonne),
    CONSTRAINT uq_colonne_index_rang UNIQUE (id_index, rang)  -- RG-14
);

CREATE TABLE relation (
    id_relation         VARCHAR(25)  PRIMARY KEY,             -- id ChartDB
    nom                 VARCHAR(63)  NOT NULL,                -- [AJOUT] taille non précisée
    cardinalite_source  VARCHAR(4)   NOT NULL,
    cardinalite_cible   VARCHAR(4)   NOT NULL,
    id_colonne_source   VARCHAR(25)  NOT NULL REFERENCES colonne (id_element),
    id_colonne_cible    VARCHAR(25)  NOT NULL REFERENCES colonne (id_element),
    CONSTRAINT ck_relation_cardinalites
        CHECK (cardinalite_source IN ('one', 'many')
           AND cardinalite_cible  IN ('one', 'many')),         -- RG-13
    CONSTRAINT ck_relation_source_cible
        CHECK (id_colonne_source <> id_colonne_cible)          -- RG-13
);

-- -----------------------------------------------------------------------------
-- Domaine 3 : historique, versions et approbation (figure 17)
-- -----------------------------------------------------------------------------

CREATE TABLE operation (
    id_operation     UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    numero_sequence  BIGINT        NOT NULL,                  -- attribué par le serveur, croissant par projet
    cible            VARCHAR(20)   NOT NULL,
    action           VARCHAR(15)   NOT NULL,
    id_entite        VARCHAR(25),                             -- pas de clé étrangère : l'objet a pu être supprimé (RG-29)
    donnees_avant    JSONB,
    donnees_apres    JSONB,
    horodatage       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    id_projet        UUID          NOT NULL REFERENCES projet (id_projet),
    id_auteur        UUID          NOT NULL REFERENCES utilisateur (id_utilisateur),
    CONSTRAINT uq_operation_sequence UNIQUE (id_projet, numero_sequence),  -- RG-16
    CONSTRAINT ck_operation_cible CHECK (cible IN
        ('projet', 'table', 'colonne', 'index', 'relation', 'zone', 'note', 'type', 'dependance')),
    CONSTRAINT ck_operation_action CHECK (action IN
        ('ajout', 'modification', 'suppression', 'import', 'reprise_version'))
);

CREATE TABLE version (
    id_version       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    nature           VARCHAR(11)   NOT NULL,
    numero           INTEGER,                                 -- 1, 2, 3... pour les versions nommées ; nul sinon
    nom              VARCHAR(100),                            -- [AJOUT] taille non précisée
    description      VARCHAR(500),                            -- [AJOUT] taille non précisée
    statut           VARCHAR(10),
    numero_sequence  BIGINT        NOT NULL,                  -- dernière opération incluse
    instantane       JSONB         NOT NULL,                  -- diagramme complet au format ChartDB
    date_creation    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    date_soumission  TIMESTAMPTZ,
    id_projet        UUID          NOT NULL REFERENCES projet (id_projet),
    id_auteur        UUID          REFERENCES utilisateur (id_utilisateur),  -- nullable
    id_soumetteur    UUID          REFERENCES utilisateur (id_utilisateur),  -- nullable
    CONSTRAINT uq_version_numero UNIQUE (id_projet, numero),  -- RG-17
    CONSTRAINT uq_version_nom    UNIQUE (id_projet, nom),     -- RG-17
    CONSTRAINT ck_version_nature CHECK (nature IN ('AUTOMATIQUE', 'NOMMEE')),
    CONSTRAINT ck_version_statut CHECK (statut IN ('BROUILLON', 'EN_ATTENTE', 'APPROUVEE', 'REFUSEE')),
    CONSTRAINT ck_version_numero CHECK (numero >= 1),
    CONSTRAINT ck_version_selon_nature CHECK (                -- RG-18
        (nature = 'NOMMEE'
            AND numero IS NOT NULL AND nom IS NOT NULL AND description IS NOT NULL
            AND statut IS NOT NULL AND id_auteur IS NOT NULL)
        OR
        (nature = 'AUTOMATIQUE' AND numero IS NULL AND statut IS NULL)
    )
);

CREATE TABLE decision (
    id_decision    UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    verdict        VARCHAR(9)     NOT NULL,
    motif          VARCHAR(1000),
    date_decision  TIMESTAMPTZ    NOT NULL DEFAULT now(),
    id_version     UUID           NOT NULL REFERENCES version (id_version),
    id_relecteur   UUID           NOT NULL REFERENCES utilisateur (id_utilisateur),
    CONSTRAINT uq_decision_version UNIQUE (id_version),                    -- RG-20
    CONSTRAINT ck_decision_verdict CHECK (verdict IN ('APPROUVEE', 'REFUSEE')),
    CONSTRAINT ck_decision_motif_refus
        CHECK (verdict <> 'REFUSEE' OR (motif IS NOT NULL AND btrim(motif) <> ''))  -- RG-20
);

-- -----------------------------------------------------------------------------
-- Domaine 4 : livraison et reprise de l'existant (figure 18)
-- -----------------------------------------------------------------------------

CREATE TABLE script_sql (
    id_script           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    nature              VARCHAR(9)    NOT NULL,
    dialecte            VARCHAR(10)   NOT NULL,
    nom_fichier         VARCHAR(255)  NOT NULL,
    contenu             TEXT          NOT NULL,               -- script tel que téléchargé
    pertes_signalees    JSONB,                                -- opérations destructrices affichées avant téléchargement
    date_generation     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    id_version_depart   UUID          REFERENCES version (id_version),      -- nullable
    id_version_arrivee  UUID          NOT NULL REFERENCES version (id_version),
    id_auteur           UUID          NOT NULL REFERENCES utilisateur (id_utilisateur),
    CONSTRAINT ck_script_nature   CHECK (nature IN ('CREATION', 'MIGRATION')),
    CONSTRAINT ck_script_dialecte CHECK (dialecte IN ('mysql', 'postgresql')),
    CONSTRAINT ck_script_depart_si_migration
        CHECK ((id_version_depart IS NOT NULL) = (nature = 'MIGRATION')),  -- RG-21
    CONSTRAINT ck_script_depart_arrivee
        CHECK (id_version_depart IS NULL OR id_version_depart <> id_version_arrivee)  -- RG-21
);

-- Le contenu du dump n'est jamais stocké (RG-24) : seules ses caractéristiques et le rapport.
CREATE TABLE import_dump (
    id_import            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    nom_fichier          VARCHAR(255)  NOT NULL,
    dialecte             VARCHAR(10)   NOT NULL,
    taille_octets        BIGINT        NOT NULL,
    date_import          TIMESTAMPTZ   NOT NULL DEFAULT now(),
    nb_elements_crees    INTEGER       NOT NULL,
    rapport              JSONB         NOT NULL,              -- éléments créés et instructions non reprises
    id_projet            UUID          NOT NULL REFERENCES projet (id_projet),
    id_auteur            UUID          NOT NULL REFERENCES utilisateur (id_utilisateur),
    id_version_produite  UUID          REFERENCES version (id_version),  -- vide : l'import ne crée pas de version (CU 1.5, RG-17)
    CONSTRAINT uq_import_version   UNIQUE (id_version_produite),
    CONSTRAINT ck_import_dialecte  CHECK (dialecte IN ('mysql', 'postgresql')),
    CONSTRAINT ck_import_taille    CHECK (taille_octets >= 0),
    CONSTRAINT ck_import_nb        CHECK (nb_elements_crees >= 0)
);

-- -----------------------------------------------------------------------------
-- Domaine 5 : collaboration en séance (figure 19)
-- -----------------------------------------------------------------------------

CREATE TABLE discussion (
    id_discussion   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    statut          VARCHAR(7)   NOT NULL DEFAULT 'OUVERTE',
    date_ouverture  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    id_element      VARCHAR(25)  NOT NULL REFERENCES element_schema (id_element),  -- RG-25
    CONSTRAINT ck_discussion_statut CHECK (statut IN ('OUVERTE', 'REGLEE'))
);

CREATE TABLE message (
    id_message     UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    nature         VARCHAR(11)   NOT NULL,
    contenu        TEXT,
    date_envoi     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    id_discussion  UUID          NOT NULL REFERENCES discussion (id_discussion),
    id_auteur      UUID          NOT NULL REFERENCES utilisateur (id_utilisateur),
    CONSTRAINT ck_message_nature CHECK (nature IN ('MESSAGE', 'CLOTURE', 'REOUVERTURE')),
    CONSTRAINT ck_message_contenu
        CHECK (nature <> 'MESSAGE' OR (contenu IS NOT NULL AND btrim(contenu) <> ''))  -- RG-26
);

CREATE TABLE prise_de_main (
    id_prise      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    statut        VARCHAR(10)   NOT NULL DEFAULT 'DEMANDEE',
    date_demande  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    date_reponse  TIMESTAMPTZ,
    date_debut    TIMESTAMPTZ,
    date_fin      TIMESTAMPTZ,
    motif_fin     VARCHAR(12),
    id_projet     UUID          NOT NULL REFERENCES projet (id_projet),
    id_demandeur  UUID          NOT NULL REFERENCES utilisateur (id_utilisateur),
    id_arbitre    UUID          REFERENCES utilisateur (id_utilisateur),   -- nullable
    CONSTRAINT ck_prise_statut CHECK (statut IN
        ('DEMANDEE', 'REFUSEE', 'EN_COURS', 'TERMINEE', 'ANNULEE')),
    CONSTRAINT ck_prise_motif_fin CHECK (motif_fin IN
        ('RENDUE', 'RETIREE', 'DECONNEXION', 'RETRAIT'))
);

-- Une seule prise de main en cours par projet (RG-28)
CREATE UNIQUE INDEX uq_prise_en_cours_par_projet
    ON prise_de_main (id_projet)
    WHERE statut = 'EN_COURS';

-- -----------------------------------------------------------------------------
-- [AJOUT] Index sur les clés étrangères les plus utilisées
-- (PostgreSQL ne les crée pas automatiquement)
-- -----------------------------------------------------------------------------

CREATE INDEX ix_session_utilisateur      ON session (id_utilisateur);
CREATE INDEX ix_participation_projet     ON participation (id_projet);
CREATE INDEX ix_journal_projet           ON evenement_journal (id_projet);
CREATE INDEX ix_element_projet           ON element_schema (id_projet);
CREATE INDEX ix_colonne_table            ON colonne (id_table);
CREATE INDEX ix_index_table              ON index_schema (id_table);
CREATE INDEX ix_relation_source          ON relation (id_colonne_source);
CREATE INDEX ix_relation_cible           ON relation (id_colonne_cible);
CREATE INDEX ix_version_projet           ON version (id_projet);
CREATE INDEX ix_import_projet            ON import_dump (id_projet);
CREATE INDEX ix_script_version_arrivee   ON script_sql (id_version_arrivee);
CREATE INDEX ix_discussion_element       ON discussion (id_element);
CREATE INDEX ix_message_discussion       ON message (id_discussion);

COMMIT;