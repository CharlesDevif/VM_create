# Gestionnaire de machines virtuelles et conteneurs

Ce projet fournit un outil en ligne de commande pour créer des machines virtuelles (VirtualBox, VMware, QEMU) ou lancer des conteneurs Docker.

## Pré-requis
- Python ≥ 3.11
- Les hyperviseurs souhaités (VirtualBox, VMware ou QEMU) et/ou Docker doivent être installés sur la machine.

## Installation
1. Clonez le dépôt puis placez-vous à sa racine.
2. (Optionnel) Créez un environnement virtuel.

python3 -m venv .venv

3. ✅ Active l’environnement virtuel

source .venv/bin/activate

3. Installez les dépendances Python :
   ```bash
   python -m pip install -r requirements.txt
   ```

## Utilisation
Lancement interactif :
```bash
python src/vm_manager.py
```

Vous serez guidé pas à pas pour choisir entre la création d’un conteneur Docker ou d’une machine virtuelle.

Exécution en mode automatique avec un fichier de configuration :
```bash
python src/vm_manager.py --batch --config config.json
```

Le fichier `config.json` contient les paramètres par défaut utilisés lorsque l’option `--batch` est activée.

## Tests
Les tests unitaires utilisent `pytest`. Après installation des dépendances, exécutez :
```bash
pytest
```
