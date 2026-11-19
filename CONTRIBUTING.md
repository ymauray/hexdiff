# Contribuer à HexDiff

Merci de vous intéresser à HexDiff ! Ce document résume comment proposer une contribution.

## Avant de commencer

Pour une nouvelle fonctionnalité ou un changement important, ouvrez d'abord une issue ou une [discussion](https://github.com/ymauray/hexdiff/discussions) pour en parler avec le mainteneur.

## Environnement de développement

Python 3 suffit, sans dépendance externe. Il n'y a pas de build ni de suite de tests automatisée : vérifiez votre modification en comparant deux fichiers et en ouvrant la page produite.

```sh
python hexdiff.py fichier_gauche fichier_droite -o hexdiff.html
```

## Proposer une modification

1. Créez une branche dédiée depuis `main` (ex. `fix/...`, `feature/...`).
2. Faites des commits atomiques, au format [Conventional Commits](https://www.conventionalcommits.org/fr/v1.0.0/) et en français (ex. `feat: ajout de ...`, `fix: correction de ...`).
3. Vérifiez le résultat en local sur un jeu d'essai.
4. Ouvrez une pull request vers `main` en remplissant le modèle fourni. Les PR sont mergées en squash.
