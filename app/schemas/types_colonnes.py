"""Types de colonnes admis (cahier des charges, CU 2.1 étape 3 ; RG-11 précisée).

Le concepteur choisit le type d'une colonne dans une liste fermée. Les listes reprennent les
identifiants de types de ChartDB v1.20.1, la version figée par l'équipe (dossier, § 1.6) :
``src/lib/data/data-types/{generic,mysql,postgres}-data-types.ts``. Ce sont ceux que l'éditeur
propose et que son analyseur de dump produit.

- Projet « generic » (P5) : types génériques de ChartDB, traduits dans le dialecte choisi à l'export.
- Projet « mysql » ou « postgresql » (après un import) : types génériques et types du dialecte.
- Dans tous les cas : les types personnalisés du projet (``customTypes`` de ChartDB, par exemple
  les énumérations PostgreSQL).

La comparaison ignore la casse et les espaces en bordure ; le type est enregistré tel que reçu (P1).
"""

TYPES_GENERIQUES = frozenset("""
    varchar int text boolean date timestamp decimal datetime json uuid bigint binary blob char double
    enum float numeric real set smallint time varbinary
""".split())

# Synonymes valides à la fois dans MySQL et dans PostgreSQL, admis dans un projet « generic ».
SYNONYMES_COMMUNS = frozenset({"integer", "bool"})

TYPES_MYSQL = frozenset("""
    int varchar text boolean timestamp date bigint decimal datetime json tinyint smallint mediumint
    float double bit char tinytext mediumtext longtext binary varbinary tinyblob blob mediumblob
    longblob enum set time year geometry point linestring polygon multipoint multilinestring
    multipolygon geometrycollection
""".split())

TYPES_POSTGRESQL = frozenset("""
    int varchar text boolean timestamp timestamptz date bigint serial json jsonb uuid numeric real
    double_precision smallserial bigserial money smallint char time timetz interval bytea enum point
    line lseg box path polygon circle cidr inet macaddr macaddr8 bit varbit tsvector tsquery xml
    int4range int8range numrange tsrange tstzrange daterange oid regproc regprocedure regoper
    regoperator regclass regtype regrole regnamespace regconfig regdictionary user-defined
""".split())

# Synonymes PostgreSQL que ChartDB reconnaît (getPostgresPreferredSynonym).
SYNONYMES_POSTGRESQL = frozenset({
    "character varying", "character", "bool", "integer", "int2", "int4", "int8", "float4", "float8",
    "double precision", "timestamp with time zone", "timestamp without time zone",
    "time with time zone", "time without time zone", "bit varying", "decimal",
})


def normaliser_type(type_id: str) -> str:
    return type_id.strip().lower()


def types_admis(type_base: str, types_personnalises: set[str] = frozenset()) -> frozenset[str]:
    """Types admis pour un projet du dialecte donné (« generic », « mysql » ou « postgresql »)."""
    admis = set(TYPES_GENERIQUES | SYNONYMES_COMMUNS)
    if type_base == "mysql":
        admis |= TYPES_MYSQL
    elif type_base == "postgresql":
        admis |= TYPES_POSTGRESQL | SYNONYMES_POSTGRESQL
    admis |= {normaliser_type(nom) for nom in types_personnalises}
    return frozenset(admis)


def noms_types_personnalises(custom_types: list[dict] | None) -> set[str]:
    """Noms des types personnalisés ChartDB (``customTypes``), tels que conservés dans Projet.annexes."""
    return {t["name"] for t in custom_types or [] if isinstance(t, dict) and isinstance(t.get("name"), str)}


def types_inconnus(champs, admis: frozenset[str]) -> list:
    """Colonnes dont le type n'est pas dans la liste admise, dans l'ordre de la table."""
    return [champ for champ in champs if normaliser_type(champ.type.id) not in admis]
