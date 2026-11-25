# Dossier d'architecture et de conception : modifications pour la V1.3

Ce document liste, section par section, les changements à reporter dans le dossier (Overleaf) pour qu'il décrive le
code de la branche `feature/DRAFTDB-42-corrections-audit`. Le dossier fait foi : ces changements **précisent** RG-09,
RG-10, RG-11 et P3 ; ils ne les contredisent pas sur le fond, sauf la restauration d'une table, qui assouplit P3.
Les pages citées sont celles de la **V1.2** (pied de page « x / 90 »).

Une fois le dossier mis à jour, ce fichier peut être supprimé du dépôt.

---

## 0. Suivi du document (p. 2)

Ajouter une ligne :

| Date | Rédacteur(s) | Version | Statut | Commentaires |
|---|---|---|---|---|
| 26/11/2026 | F. GUERREIRO MARQUES | V1.3 | En cours | Corrections issues de l'audit du sprint 1 : restauration d'une table supprimée (RG-09, P3), règles de nommage (RG-10), types de colonnes par dialecte (RG-11), avertissements de l'ajout et de l'import ; mise à jour de l'état du sprint 1 (§ 4, § 5.3.2, § 5.6). |

Dans le tableau « Chapitre / État », chapitre 05 : ajouter « précisions RG-09, RG-10, RG-11 (§ 5.7) ».

**À vérifier à l'export** : le PDF V1.2 contient, sur ses 43 premières pages, deux couches de texte superposées (V1.1 et
V1.2 ; par exemple deux descriptions de `GenerateurSQL` p. 42 et des pieds de page « x / 43 » et « x / 90 »). Exporter la
V1.3 depuis Overleaf sans calque ni `latexdiff`, puis contrôler avec `pdftotext` qu'une seule version du texte subsiste.

---

## 1. § 1.6 Principes de conception, P3 (p. 8)

**Remplacer**

> P3 Des identifiants stables. ChartDB attribue à chaque table, champ, index et relation un identifiant unique qui ne
> change jamais. Un renommage reste un renommage (et non une suppression suivie d'un ajout), ce qui fiabilise les
> comparaisons, les migrations et le rattachement des discussions.

**par**

> P3 Des identifiants stables. ChartDB attribue à chaque table, champ, index et relation un identifiant unique qui ne
> change jamais. Un renommage reste un renommage (et non une suppression suivie d'un ajout), ce qui fiabilise les
> comparaisons, les migrations et le rattachement des discussions. Un identifiant ne désigne jamais deux éléments
> différents : il n'est réutilisable que pour **restaurer** l'élément supprimé qu'il désignait (annuler une suppression).

---

## 2. § 3 Règles de gestion (p. 21-22)

**RG-09 : ajouter à la fin**

> Une table supprimée du même projet peut être **restaurée** sous son identifiant : elle redevient active avec ses
> colonnes reprises, et le contenu reçu devient son état. Un identifiant ne peut pas servir à un autre élément, ni dans
> un autre projet.

**RG-10 : remplacer** « Deux tables actives d'un même projet ne portent pas le même nom ; deux colonnes actives d'une
même table non plus. » **par**

> Deux tables actives d'un même projet (dans un même schéma SQL) ne portent pas le même nom, **sans tenir compte de la
> casse** ; deux colonnes actives d'une même table non plus. Un nom n'est ni vide, ni bordé d'espaces ; il ne contient
> ni caractère de contrôle, ni guillemet droit, ni accent grave, et ne dépasse pas 63 octets. Un mot réservé de MySQL ou
> de PostgreSQL, ou un nom hors [A-Za-z0-9_], est accepté avec un avertissement.

Colonne « Source » : ajouter « CdC § 3.3.1.4 ».

**RG-11 : ajouter à la fin**

> Le type d'une colonne est choisi dans la liste des types génériques de ChartDB ; un projet MySQL ou PostgreSQL
> (après un import) admet en plus les types de son dialecte. Les types personnalisés du projet sont toujours admis.

Colonne « Source » : ajouter « CU 2.1 (étape 3) ».

**RG-15 : ajouter à la fin**

> À la restauration d'une table (RG-09), les index reçus remplacent ceux de l'ancienne table ; les relations dont les
> deux colonnes sont de nouveau actives réapparaissent.

---

## 3. § 4.2 CU 1.5 Importer le dump (p. 52-57)

- **Règles appliquées** (tableau, p. 56) : RG-10 → ajouter « sans tenir compte de la casse ; règles de nommage (RG-10
  précisée) ». Ajouter une ligne **RG-11** : « Un type de colonne inconnu du dialecte du dump n'empêche pas l'import : il
  est signalé par un avertissement `TYPE_INCONNU` ».
- **Résultat** : la réponse 201 comprend `avertissements` (noms réservés ou à protéger, types inconnus), aussi
  enregistrés dans `import_dump.rapport.avertissements`.
- **§ 4.2.10 Limites** (p. 57) : la phrase « l'avertissement est produit à l'ajout d'une table (CU 2.1) » reste vraie
  pour la clé primaire ; ajouter « Les avertissements de nommage et de type sont produits à l'import. »
- L'import exige toujours des identifiants neufs : la restauration (RG-09) ne concerne que l'ajout d'une table.

---

## 4. § 4.4 CU 2.1 Ajouter une table (p. 63-68)

- **§ 4.4.2 Fonctionnement** (p. 63) : remplacer « Il répond ensuite 201 avec la table, son numéro de séquence et
  l'avertissement » par « Il répond ensuite 201 avec la table, son numéro de séquence, l'avertissement de clé primaire,
  la liste des avertissements et l'indication de restauration ». Dans la liste des contrôles : « nom de table libre
  (RG-10, casse ignorée), **type de colonne admis pour le dialecte du projet (RG-11)**, identifiants libres **ou table à
  restaurer** (P3, RG-09) ».
- **Identifiant ChartDB** (p. 65) : remplacer « Un identifiant déjà utilisé est refusé en 422. » par « Un identifiant
  déjà utilisé est refusé en 422, sauf s'il est celui d'une table supprimée du même projet : la table est alors
  restaurée (RG-09). »
- **§ 4.4.5 Données reçues** (p. 66) : ligne `name, schema` → « Nom de la table, unique dans le projet sans tenir compte
  de la casse, conforme aux règles de nommage (RG-10) » ; ligne `fields : type` → « Type de la colonne, obligatoire, dans
  la liste admise pour le dialecte du projet (RG-11) ».
- **§ 4.4.7 Erreurs** (p. 66) : ajouter « Nom contraire aux règles de nommage (guillemet, espace en bordure, caractère de
  contrôle, plus de 63 octets) : 422 » et « Type de colonne non admis pour le dialecte du projet : 422 (RG-11) ».
- **Règles appliquées** (tableau, p. 67) : remplacer la ligne RG-09, P3 par « Les identifiants ChartDB sont conservés
  tels quels ; un identifiant déjà présent est refusé (422), sauf pour restaurer une table supprimée du même projet » ;
  compléter RG-10 (casse, nommage) ; ajouter RG-11 (types).
- **Choix de conception** (p. 67-68) : ajouter
  > **Restauration plutôt que refus.** ChartDB permet d'annuler une suppression : il renvoie alors la table avec ses
  > identifiants d'origine. Les refuser rendrait l'annulation impossible ; les accepter comme une restauration garde
  > l'historique intact (l'opération de suppression et la nouvelle opération d'ajout sont toutes deux conservées).
  >
  > **Avertir plutôt que refuser les mots réservés.** Les deux SGBD acceptent un mot réservé protégé par des guillemets,
  > et les dumps réels en contiennent (`user`, `order`) : les refuser bloquerait l'import (EX-14).
- **« Un contrôle par cas d'erreur »** (p. 68) : « les trois cas de 422 » devient « les quatre cas de 422 » (corps, nom
  pris, type non admis, identifiant).
- **§ 4.4.11 Limites** (p. 68) : supprimer « Fichiers prévus. routers/tables.py et services/tables.py sont des noms
  proposés. » (les fichiers existent).
- **Suivi des cas d'utilisation du sprint 1** (p. 45) : passer CU 2.1 et CU 2.3, colonne « Dev back », de « à faire » à
  « terminé ».

---

## 5. § 4.5 CU 2.3 Supprimer une table (p. 69-75)

- **Règles appliquées** (p. 72) : à la ligne RG-10 « son nom redevient libre dans le projet », ajouter la ligne **RG-09**
  : « Son identifiant ne peut resservir que pour la restaurer (CU 2.1) ».

---

## 6. § 5.1 Services API (p. 75-84)

- **§ 5.1.4 POST …/import** (p. 76-77), paramètres de sortie : ajouter
  `avertissements` | liste | « Avertissements non bloquants : `NOM_RESERVE`, `NOM_A_PROTEGER`, `TYPE_INCONNU`, chacun
  avec `code`, `message` et `id_element` ». Ligne 422 : « identifiant déjà utilisé (l'import exige des identifiants
  neufs) ; nom contraire aux règles de nommage ; deux tables ou colonnes de même nom à la casse près ».
- **§ 5.1.6 POST …/tables** (p. 78) : retirer « (prévue) » du titre. Paramètres de sortie : ajouter
  `avertissements` | liste | « tous les avertissements (clé primaire, nommage) » et `restauree` | booléen | « vrai si la
  table reprend l'identifiant d'une table supprimée du même projet (RG-09) ». Ligne 422 : « Type de colonne absent ou non
  admis pour le dialecte du projet (RG-11) ; nom invalide (règles de nommage) ; nom déjà pris dans le projet, casse
  ignorée (RG-10) ; identifiant ChartDB déjà utilisé hors restauration (P3) ; valeur refusée par la base ».
- **§ 5.1.7 DELETE …/tables/{id_table}** (p. 79-84) : retirer « (prévue) » du titre s'il y figure.

---

## 7. § 5.2 Services fonctionnels (p. 82-84)

Ajouter, pour `services/tables.py` :

| Service | Rôle |
|---|---|
| `_verifier_types` | Contrôle le type de chaque colonne selon le dialecte du projet (RG-11) |
| `_restauration` | Décide si la table est nouvelle ou à restaurer ; refuse tout autre identifiant déjà utilisé (P3, RG-09) |
| `_restaurer` | Réactive la table et les colonnes reprises, remplace les index (RG-09, RG-15) |

Et pour `services/importer.py` : `avertissements_import` (avertissements de nommage et de type de l'import).

---

## 8. § 5.3.2 Organisation du code (p. 85-86)

Remplacer la liste des routes par `health.py`, `imports.py`, `ouverture.py`, `projets.py`, `tables.py`, et ajouter dans
`app/schemas/` :

| Fichier | Rôle |
|---|---|
| `app/schemas/regles.py` | Règles de nommage (RG-10), objet `Avertissement` et avertissements de nommage et de clé primaire |
| `app/schemas/mots_reserves.py` | Mots réservés de MySQL 8.4 (264) et de PostgreSQL 16 (101), avec leur source |
| `app/schemas/types_colonnes.py` | Types de colonnes admis selon le dialecte (listes de ChartDB v1.20.1) |

---

## 9. § 5.6 Principes, tests et limites (p. 89)

- Tableau des principes, ligne **P3** : « Les identifiants ChartDB sont conservés ; un identifiant déjà présent est
  refusé (422), sauf pour restaurer une table supprimée du même projet ».
- **§ 5.6.2 Tests** : remplacer « 33 tests automatiques » par « **182 tests automatiques** (au 25/11/2026) » et ajouter à
  la liste : restauration d'une table, règles de nommage, mots réservés, types de colonnes par dialecte.
- **§ 5.6.3 Limites** : remplacer « L'avertissement RG-12 est produit à l'ajout d'une table (CU 2.1), pas à l'import »
  par « L'avertissement RG-12 est produit à l'ajout d'une table (CU 2.1), pas à l'import ; les avertissements de
  nommage et de type sont produits aux deux ».

---

## 10. § 5.7 Précisions sur les règles de gestion (p. 89-90)

Ajouter au tableau :

| N° | Règle ou section | Précision apportée par l'implémentation |
|---|---|---|
| 8 | RG-09, P3 | Un identifiant de table supprimée peut resservir pour restaurer cette table, dans le même projet seulement. Ses colonnes peuvent reprendre leurs identifiants ; tout autre identifiant déjà présent en base est refusé (422). L'import exige des identifiants neufs. |
| 9 | RG-15 | À la restauration, le corps reçu devient l'état de la table : les index reçus remplacent les anciens, retirés de `index_schema` (leur état passé reste dans l'opération de suppression) ; les anciennes colonnes absentes du corps restent supprimées ; les relations dont les deux colonnes sont actives réapparaissent. |
| 10 | RG-10 | Unicité sans tenir compte de la casse (comparaison par `lower()`). Refus : nom vide ou bordé d'espaces, caractère de contrôle, guillemet droit ou accent grave, plus de 63 octets. Avertissement `NOM_RESERVE` (mots réservés de MySQL 8.4 et de PostgreSQL 16) ou `NOM_A_PROTEGER` (hors [A-Za-z0-9_] ou chiffre en premier). |
| 11 | RG-11, CU 2.1 | Types admis : types génériques de ChartDB v1.20.1 et synonymes `integer`, `bool` ; en plus, types MySQL ou PostgreSQL de ChartDB selon le dialecte du projet ; types personnalisés du projet. 422 à l'ajout, avertissement `TYPE_INCONNU` à l'import. |

---

## 11. Points à faire valider par le client (à ajouter aux questions de la Sprint Review)

1. Les règles de nommage proposées (refus et avertissements) traduisent-elles bien le § 3.3.1.4 du cahier des charges ?
   En particulier : les mots réservés sont **acceptés avec un avertissement**, pas refusés.
2. Deux tables `Client` et `client` sont refusées dans un même projet : est-ce acceptable pour vos bases ?
3. Les types de colonnes sont limités aux types de ChartDB pour le dialecte du projet : manque-t-il des types que vos
   équipes utilisent ?
4. Annuler la suppression d'une table la restaure avec ses relations : ce comportement vous convient-il ?
