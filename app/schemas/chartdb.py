"""Objets du format JSON de ChartDB (principe P1), limités à ce que le serveur lit.

Les champs inconnus sont conservés (extra="allow") : le serveur renvoie les objets
tels qu'il les a reçus. Les noms (camelCase) suivent le modèle ChartDB (dossier de
conception, § 3.3.3) : à vérifier contre src/lib/domain de ChartDB v1.20.1.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.regles import cle_nom, verifier_nom

IdChartDB = Annotated[str, StringConstraints(min_length=1, max_length=25)]  # P3 : jamais régénérés
# RG-10 précisée : nom vide, bordé d'espaces, caractère de contrôle, guillemet ou plus de 63 octets -> 422.
Nom = Annotated[str, StringConstraints(min_length=1, max_length=63), AfterValidator(verifier_nom)]
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

    @model_validator(mode="after")
    def verifier_regles_internes(self):
        """Règles qui se voient dans la table seule, communes à l'ajout (CU 2.1) et à l'import (CU 1.5).

        RG-10 entre colonnes (sans tenir compte de la casse), RG-12, RG-14 et unicité des identifiants
        dans la table : la table et ses colonnes partagent la même clé primaire en base (element_schema).
        """
        ids_elements = {self.id}
        noms_colonnes = set()
        for champ in self.fields:
            if champ.id in ids_elements:
                raise ValueError(f"Identifiant en double dans la table : {champ.id!r}.")
            ids_elements.add(champ.id)
            if cle_nom(champ.name) in noms_colonnes:  # RG-10
                raise ValueError(f"Deux colonnes de la table {self.name!r} portent le nom {champ.name!r} "
                                 "(sans tenir compte de la casse, RG-10).")
            noms_colonnes.add(cle_nom(champ.name))
            if champ.primary_key and champ.nullable:  # RG-12
                raise ValueError(f"La colonne {self.name}.{champ.name} est clé primaire mais nullable (RG-12).")

        ids_colonnes = {champ.id for champ in self.fields}
        ids_index = set()
        for index in self.indexes:
            if index.id in ids_index:
                raise ValueError(f"Identifiant d'index en double : {index.id!r}.")
            ids_index.add(index.id)
            if len(set(index.field_ids)) != len(index.field_ids):  # RG-14
                raise ValueError(f"L'index {index.name!r} cite deux fois la même colonne (RG-14).")
            inconnues = set(index.field_ids) - ids_colonnes
            if inconnues:  # RG-14
                raise ValueError(f"L'index {index.name!r} cite des colonnes absentes de sa table : {sorted(inconnues)}.")
        return self


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
        """Règles entre tables (RG-10, RG-13, unicité des identifiants), contrôlées avant toute écriture.

        Les règles internes à chaque table (RG-10 entre colonnes, RG-12, RG-14) sont vérifiées par DBTable.
        """
        if not self.tables:
            raise ValueError("Le diagramme ne contient aucune table : rien à importer.")
        ids_elements, ids_index, ids_relations = set(), set(), set()  # tables et colonnes : même clé en base
        noms_tables = set()
        for table in self.tables:
            _unique(ids_elements, table.id, "table")
            nom_complet = (cle_nom(table.schema_sql), cle_nom(table.name))
            if nom_complet in noms_tables:  # RG-10
                raise ValueError(f"Deux tables portent le même nom : {table.name!r} "
                                 "(sans tenir compte de la casse, RG-10).")
            noms_tables.add(nom_complet)
            for champ in table.fields:
                _unique(ids_elements, champ.id, "colonne")
            for index in table.indexes:
                _unique(ids_index, index.id, "index")
        ids_colonnes = {champ.id for table in self.tables for champ in table.fields}
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
