"""Objets du format JSON de ChartDB (principe P1), limités à ce que le serveur lit.

Les champs inconnus sont conservés (extra="allow") : le serveur renvoie les objets
tels qu'il les a reçus. Les noms (camelCase) suivent le modèle ChartDB (dossier de
conception, § 3.3.3) : à vérifier contre src/lib/domain de ChartDB v1.20.1.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

IdChartDB = Annotated[str, StringConstraints(min_length=1, max_length=25)]  # P3 : jamais régénérés
Nom = Annotated[str, StringConstraints(min_length=1, max_length=63)]
Coordonnee = Annotated[float, Field(ge=-999999.99, le=999999.99)]


class ChartDBModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class DBFieldType(ChartDBModel):
    id: str = Field(max_length=30)
    name: str | None = None


class DBField(ChartDBModel):
    id: IdChartDB
    name: Nom
    type: DBFieldType
    primary_key: bool = Field(False, alias="primaryKey")
    unique: bool = False
    nullable: bool = True
    increment: bool = False
    character_maximum_length: str | None = Field(None, alias="characterMaximumLength", max_length=10)
    precision: int | None = Field(None, ge=0, le=32767)
    scale: int | None = Field(None, ge=0, le=32767)
    default: str | None = Field(None, max_length=255)
    collation: str | None = Field(None, max_length=63)
    comments: str | None = None


class DBIndex(ChartDBModel):
    id: IdChartDB
    name: Nom
    unique: bool = False
    field_ids: list[IdChartDB] = Field(alias="fieldIds")
    type: str | None = Field(None, max_length=10)
    is_primary_key: bool = Field(False, alias="isPrimaryKey")


class DBTable(ChartDBModel):
    id: IdChartDB
    name: Nom
    schema_sql: Nom | None = Field(None, alias="schema")
    x: Coordonnee = 0
    y: Coordonnee = 0
    width: Coordonnee | None = None
    color: str | None = Field(None, max_length=7)
    comments: str | None = None
    is_view: bool = Field(False, alias="isView")
    fields: list[DBField] = []
    indexes: list[DBIndex] = []


class DBRelationship(ChartDBModel):
    id: IdChartDB
    name: Nom
    source_table_id: IdChartDB = Field(alias="sourceTableId")
    target_table_id: IdChartDB = Field(alias="targetTableId")
    source_field_id: IdChartDB = Field(alias="sourceFieldId")
    target_field_id: IdChartDB = Field(alias="targetFieldId")
    source_cardinality: Literal["one", "many"] = Field(alias="sourceCardinality")
    target_cardinality: Literal["one", "many"] = Field(alias="targetCardinality")


class Diagramme(ChartDBModel):
    id: str | None = None
    name: str | None = None
    tables: list[DBTable] = []
    relationships: list[DBRelationship] = []
    # Conservés tels quels dans Projet.annexes (dossier, table 11).
    areas: list[dict] = []
    notes: list[dict] = []
    custom_types: list[dict] = Field([], alias="customTypes")
    dependencies: list[dict] = []

    @model_validator(mode="after")
    def verifier_coherence(self):
        """Règles RG-12 à RG-14 et unicité des identifiants, contrôlées avant toute écriture."""
        ids_tables, ids_colonnes, ids_index, ids_relations = set(), set(), set(), set()
        for table in self.tables:
            _unique(ids_tables, table.id, "table")
            noms_colonnes = set()
            for champ in table.fields:
                _unique(ids_colonnes, champ.id, "colonne")
                if champ.name in noms_colonnes:
                    raise ValueError(f"Deux colonnes de la table {table.name!r} portent le nom {champ.name!r}.")
                noms_colonnes.add(champ.name)
                if champ.primary_key and champ.nullable:
                    raise ValueError(f"La colonne {table.name}.{champ.name} est clé primaire mais nullable (RG-12).")
        colonnes_de = {t.id: {c.id for c in t.fields} for t in self.tables}
        for table in self.tables:
            for index in table.indexes:
                _unique(ids_index, index.id, "index")
                if len(set(index.field_ids)) != len(index.field_ids):
                    raise ValueError(f"L'index {index.name!r} cite deux fois la même colonne (RG-14).")
                inconnues = set(index.field_ids) - colonnes_de[table.id]
                if inconnues:
                    raise ValueError(f"L'index {index.name!r} cite des colonnes absentes de sa table : {sorted(inconnues)}.")
        for rel in self.relationships:
            _unique(ids_relations, rel.id, "relation")
            if rel.source_field_id == rel.target_field_id:
                raise ValueError(f"La relation {rel.name!r} relie une colonne à elle-même (RG-13).")
            for id_colonne in (rel.source_field_id, rel.target_field_id):
                if id_colonne not in ids_colonnes:
                    raise ValueError(f"La relation {rel.name!r} cite une colonne absente du diagramme : {id_colonne!r}.")
        return self


def _unique(deja_vus: set, identifiant: str, nature: str) -> None:
    if identifiant in deja_vus:
        raise ValueError(f"Identifiant de {nature} en double : {identifiant!r}.")
    deja_vus.add(identifiant)