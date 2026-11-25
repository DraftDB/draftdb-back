-- =============================================================================
-- Données de test (développement uniquement). DRAFTDB-40.
-- Exécuté par Docker au premier démarrage du volume pgdata, après 01_schema.sql.
-- Pour le rejouer : docker compose down -v puis docker compose up -d
-- En test manuel (Swagger), envoyer l'en-tête X-User-Id avec l'un des UUID ci-dessous.
-- =============================================================================

INSERT INTO utilisateur (id_utilisateur, login, empreinte_mdp) VALUES
    ('00000000-0000-0000-0000-000000000001', 'responsable', 'seed-pas-un-vrai-hash'),
    ('00000000-0000-0000-0000-000000000002', 'relecteur',   'seed-pas-un-vrai-hash'),
    ('00000000-0000-0000-0000-000000000003', 'etranger',    'seed-pas-un-vrai-hash');

INSERT INTO projet (id_projet, nom, description, id_responsable) VALUES
    ('00000000-0000-0000-0000-0000000000a1', 'Projet de test', 'Projet créé par le seed', '00000000-0000-0000-0000-000000000001');

INSERT INTO participation (id_utilisateur, id_projet, est_concepteur, est_relecteur) VALUES
    ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', true,  false),
    ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000a1', false, true);