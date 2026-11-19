# AGENTS.md

HexDiff : comparateur hexadécimal de deux fichiers binaires, avec sortie HTML interactive.

## Commandes

- Lancer : `python hexdiff.py <gauche> <droite> [-o sortie.html]` (sortie par défaut : `hexdiff.html`, ignorée par git).
- Il n'y a ni build, ni tests automatisés, ni linter configuré : vérifier en comparant deux fichiers et en ouvrant la page produite.

## Architecture

Tout le code est dans `hexdiff.py` (Python 3, bibliothèque standard uniquement) :

- `compute_diff` / `_byte_diff` : diff par blocs (`difflib`) puis LCS octet par octet.
- `group_diffs` : fusionne les suppressions et insertions adjacentes en blocs de changement.
- `build_lines` : aligne les deux fichiers case par case (lignes de 16) et calcule les offsets.
- `render_side` / `render_ascii_side` / `generate_html` : rendu HTML (gabarit `HTML_TEMPLATE` avec son JavaScript).

Détail du rendu et des interactions : `README.md`.

## Conventions

- Documentation, messages et commentaires en français.
- Messages de commit au format Conventional Commits, en français (`feat: ...`, `fix: ...`, `docs: ...`).
- Pas de dépendance externe.
- Les fichiers `.frm` de test local ne sont jamais commités.
