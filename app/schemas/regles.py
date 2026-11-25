"""Règles de nommage (RG-10 précisée) et avertissements non bloquants (EX-05).

Cahier des charges, § 3.3.1.4 : « les noms respectent les règles de MySQL et de PostgreSQL
(caractères autorisés, longueur, mots réservés) ». Le serveur applique ces règles en deux niveaux :

- **refus (422)** pour ce qu'aucun script SQL ne pourrait reprendre proprement : nom vide ou bordé
  d'espaces, caractère de contrôle, guillemet droit ou accent grave (les deux SGBD s'en servent
  pour protéger les noms), plus de 63 octets (limite de PostgreSQL ; MySQL accepte 64) ;
- **avertissement** pour ce qui reste valide à condition d'être protégé par des guillemets à
  l'export : mot réservé de MySQL ou de PostgreSQL, caractères hors ``[A-Za-z0-9_]``, chiffre en
  premier. Refuser ces noms bloquerait l'import de dumps réels (EX-14).

Deux tables d'un même schéma SQL, ou deux colonnes d'une même table, ne peuvent pas porter le même
nom **sans tenir compte de la casse** : « Client » et « client » sont la même table pour PostgreSQL
(noms non protégés) et pour MySQL sous Windows et macOS.
"""

import re

from pydantic import BaseModel

from app.schemas.mots_reserves import MOTS_RESERVES_MYSQL, MOTS_RESERVES_POSTGRESQL

LONGUEUR_MAX_OCTETS = 63
_IDENTIFIANT_SIMPLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Avertissement(BaseModel):
    """Problème non bloquant, renvoyé avec la table ou l'import (EX-05)."""

    code: str
    message: str
    id_element: str | None = None  # identifiant ChartDB de la table ou de la colonne concernée


def verifier_nom(nom: str) -> str:
    """Validateur Pydantic des noms : lève ValueError (donc 422) si le nom est inutilisable en SQL."""
    if not nom.strip():
        raise ValueError("Le nom ne peut pas être vide (nom vide ou fait d'espaces).")
    if nom != nom.strip():
        raise ValueError(f"Le nom {nom!r} commence ou finit par un espace.")
    if any(ord(c) < 32 or ord(c) == 127 for c in nom):
        raise ValueError(f"Le nom {nom!r} contient un caractère de contrôle.")
    if '"' in nom or "`" in nom:
        raise ValueError(f"Le nom {nom!r} contient un guillemet (\" ou `), interdit dans un nom (RG-10).")
    if len(nom.encode("utf-8")) > LONGUEUR_MAX_OCTETS:
        raise ValueError(f"Le nom {nom!r} dépasse {LONGUEUR_MAX_OCTETS} octets (limite de PostgreSQL, RG-10).")
    return nom


def cle_nom(nom: str | None) -> str:
    """Clé de comparaison des noms pour RG-10 : sans tenir compte de la casse (même règle que lower() en SQL)."""
    return (nom or "").lower()


def _avertissement_nom(nom: str, nature: str, id_element: str) -> Avertissement | None:
    mot = nom.lower()
    sgbd = [s for s, mots in (("MySQL", MOTS_RESERVES_MYSQL), ("PostgreSQL", MOTS_RESERVES_POSTGRESQL)) if mot in mots]
    if sgbd:
        return Avertissement(
            code="NOM_RESERVE", id_element=id_element,
            message=f"Le nom de {nature} {nom!r} est un mot réservé de {' et de '.join(sgbd)} : "
                    "il devra être protégé par des guillemets dans les scripts SQL.",
        )
    if not _IDENTIFIANT_SIMPLE.match(nom):
        return Avertissement(
            code="NOM_A_PROTEGER", id_element=id_element,
            message=f"Le nom de {nature} {nom!r} contient des caractères hors [A-Za-z0-9_] ou commence par un "
                    "chiffre : il devra être protégé par des guillemets dans les scripts SQL.",
        )
    return None


def avertissement_cle_primaire(table) -> Avertissement | None:
    """EX-05, RG-12 : une table sans clé primaire est acceptée, avec un avertissement."""
    if any(champ.primary_key for champ in table.fields):
        return None
    return Avertissement(
        code="TABLE_SANS_CLE_PRIMAIRE", id_element=table.id,
        message=f"La table {table.name!r} n'a aucune colonne clé primaire (RG-12).",
    )


def avertissements_noms(table) -> list[Avertissement]:
    """Avertissements sur les noms d'une table (objet DBTable) et de ses colonnes : mots réservés, noms à protéger."""
    candidats = [_avertissement_nom(table.name, "table", table.id)]
    candidats += [_avertissement_nom(champ.name, "colonne", champ.id) for champ in table.fields]
    return [a for a in candidats if a is not None]


def avertissements_table(table) -> list[Avertissement]:
    """Avertissements à l'ajout d'une table (CU 2.1) : clé primaire (RG-12), puis noms (RG-10)."""
    cle_primaire = avertissement_cle_primaire(table)
    return ([cle_primaire] if cle_primaire else []) + avertissements_noms(table)
