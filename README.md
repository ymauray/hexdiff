# HexDiff

[![Licence : MIT](https://img.shields.io/github/license/ymauray/hexdiff)](LICENSE)
[![repocheck](https://img.shields.io/badge/repocheck%201.3.0-83%2F100-green)](https://github.com/ymauray/repocheck)

Comparateur hexadécimal de deux fichiers binaires, avec sortie HTML interactive.

## Utilisation

```
python hexdiff.py <fichier_gauche> <fichier_droite> [-o sortie.html]
```

Par défaut, le résultat est écrit dans `hexdiff.html` (ignoré par git). Ouvrez-le dans un navigateur.

Python 3 suffit, sans dépendance externe.

## Rendu

Les deux fichiers sont affichés côte à côte, alignés case par case, 16 octets par ligne :
hex gauche, ASCII gauche, hex droite, ASCII droite. Il n'y a pas d'offsets dans les lignes.

| Couleur | Signification |
| ------- | ------------- |
| Gris | Octets identiques |
| Noir | Modification (suppression et ajout de même longueur) |
| Rouge | Octets supprimés (présents seulement à gauche) |
| Bleu | Octets ajoutés (présents seulement à droite) |
| `··` gris | Case vide en face d'une suppression ou d'un ajout |

Dans les colonnes ASCII, tout octet hors de la plage `0x20`–`0x7E` est remplacé par un point médian `·`.

## Interactions

- **Clic** sur un octet : mise en évidence (fond pastel) de l'octet et de son vis-à-vis, dans les quatre colonnes.
- **Glisser** : sélection d'une plage, figée au relâchement.
- **Offsets** : sous le nom de chaque fichier, l'offset réel de l'octet ou de la plage sélectionnée, propre à chaque fichier (différent à gauche et à droite après un décalage).
- Un second clic sur un octet seul annule la sélection.

## Fonctionnement

1. Comparaison par blocs (16 octets, 64 au-delà de 1 Mo) avec `difflib.SequenceMatcher`.
2. LCS octet par octet dans les blocs différents (au-delà de 65 536 octets par bloc, le bloc est traité comme remplacé).
3. Les suppressions et insertions adjacentes sont fusionnées en un bloc de changement.

## Limites

- Plusieurs plus longues sous-séquences communes sont possibles : le découpage en blocs identiques et différents peut être arbitraire dans les zones ambiguës.
- La comparaison octet par octet est quadratique : les fichiers très différents et volumineux peuvent être lents.
