import logging
import os
import subprocess
import json
import argparse
from colorama import Fore, Style, init
from os_detection import detect_os, find_hypervisors
from utils import (
    prompt_input, get_available_memory, create_qcow2_disk, convert_disk_format,
    list_local_isos, download_iso, vm_exists, choose_from_list, is_docker_installed, create_docker_container
)

# Initialisation de Colorama pour Windows
init(autoreset=True)

def load_config(file_path="config.json"):
    """Charge la configuration depuis un fichier JSON si `--batch` est utilisé."""
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return json.load(file)
    return {}

def parse_arguments():
    """Analyse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(description="Gestionnaire de VMs et conteneurs Docker.")
    parser.add_argument("--batch", action="store_true", help="Mode automatique avec configuration prédéfinie.")
    parser.add_argument("--config", type=str, default="config.json", help="Chemin du fichier de configuration JSON.")
    return parser.parse_args()

def create_vm(hypervisor, name, arch, ram, iso_path, paths, dry_run=False):
    """Crée une machine virtuelle avec une meilleure gestion de l'expérience utilisateur."""

    while vm_exists(hypervisor, name, paths):
        print(f"{Fore.YELLOW}⚠️ La VM '{name}' existe déjà.{Style.RESET_ALL}")
        choix = choose_from_list("Que voulez-vous faire ?", ["Supprimer la VM", "Changer de nom"])

        if choix == "Supprimer la VM":
            print(f"{Fore.RED}🗑 Suppression de la VM existante '{name}'...{Style.RESET_ALL}")
            if hypervisor == "VirtualBox":
                subprocess.run([paths["VirtualBox"], "unregistervm", name, "--delete"], check=True)
            elif hypervisor == "VMware":
                subprocess.run([paths["VMware"], "-T", "ws", "deleteVM", f"{name}.vmx"], check=True)
            elif hypervisor == "Hyper-V":
                subprocess.run(["powershell.exe", "Remove-VM", "-Name", name, "-Force"], check=True)
            print(f"{Fore.GREEN}✅ VM '{name}' supprimée.{Style.RESET_ALL}")
        else:
            name = prompt_input("Entrez un nouveau nom pour la VM", required=True)

    if vm_exists(hypervisor, name, paths):
        print(f"{Fore.RED}❌ Impossible de créer la VM '{name}', elle existe toujours après modification.{Style.RESET_ALL}")
        return

    print(f"\n{Fore.CYAN}➡️ Création de la VM '{name}' avec {ram} Mo de RAM sous {hypervisor}...{Style.RESET_ALL}")

    qcow2_disk = create_qcow2_disk(name)
    if not qcow2_disk:
        return

    converted_disk = None
    cmd_vm = []

    if hypervisor == "VirtualBox":
        vbox_path = paths["VirtualBox"]
        converted_disk = convert_disk_format(qcow2_disk, f"{name}.vdi", "vdi")

        cmd_vm = [
            [vbox_path, "createvm", "--name", name, "--register"],
            [vbox_path, "modifyvm", name, "--memory", str(ram)],
            [vbox_path, "storagectl", name, "--name", "SATA Controller", "--add", "sata", "--controller", "IntelAhci"],
            [vbox_path, "storageattach", name, "--storagectl", "SATA Controller", "--port", "0", "--device", "0", "--type", "hdd", "--medium", converted_disk],
            [vbox_path, "storageattach", name, "--storagectl", "SATA Controller", "--port", "1", "--device", "0", "--type", "dvddrive", "--medium", iso_path],
        ]

    elif hypervisor == "QEMU":
        cmd_vm = [[
            paths["QEMU"], "-m", str(ram),
            "-hda", qcow2_disk, "-cdrom", iso_path, "-boot", "d",
            "-vga", "virtio",
            "-display", "gtk,gl=on",
            "-accel", "tcg",
            "-smp", "2",
            "-usb", "-device", "usb-tablet"
        ]]

    if dry_run:
        print(f"{Fore.MAGENTA}[Dry-run] Commandes : {cmd_vm}{Style.RESET_ALL}")
        return

    for cmd in cmd_vm:
        print(f"{Fore.BLUE}🖥️ Exécution : {' '.join(cmd)}{Style.RESET_ALL}")
        subprocess.run(cmd, check=True)

    print(f"{Fore.GREEN}✅ VM '{name}' créée avec succès.{Style.RESET_ALL}")


if __name__ == "__main__":
    args = parse_arguments()

    # ** Charger la config SEULEMENT si `--batch` est activé **
    config = load_config(args.config) if args.batch else {}

    os_type = detect_os()

    # ** Étape 1 : Choix entre Docker et Hyperviseur (toujours demandé) **
    mode = choose_from_list(
        f"{Fore.YELLOW}Voulez-vous créer une VM ou un conteneur Docker ?{Style.RESET_ALL}",
        ["docker", "hypervisor"]
    )

    if mode == "docker":
        # Vérifie si Docker est installé
        if not is_docker_installed():
            print(f"{Fore.RED}❌ Docker n'est pas installé ou le service n'est pas en cours d'exécution.{Style.RESET_ALL}")
            exit(1)

        # ** Étape 2A : Chargement de la config Docker SEULEMENT en mode `--batch` **
        if args.batch:
            container_name = config.get("docker", {}).get("container_name", "mon-conteneur")
            image_name = config.get("docker", {}).get("image_name", "ubuntu:latest")
            volume_name = config.get("docker", {}).get("volume_name", "")
        else:
            container_name = prompt_input(f"{Fore.CYAN}Nom du conteneur Docker{Style.RESET_ALL}", default="mon-conteneur")
            image_name = prompt_input(f"{Fore.CYAN}Image Docker à utiliser{Style.RESET_ALL}", default="ubuntu:latest")
            volume_name = prompt_input(f"{Fore.CYAN}Nom du volume (laisser vide pour pas de volume){Style.RESET_ALL}", default="")

        print(f"{Fore.CYAN}🚀 Lancement du conteneur Docker...{Style.RESET_ALL}")
        create_docker_container(container_name, image_name, volume_name)
        print(f"{Fore.GREEN}✅ Conteneur '{container_name}' créé avec succès !{Style.RESET_ALL}")
        exit(0)

    elif mode == "hypervisor":
        # Détection des hyperviseurs disponibles
        available_hypervisors, hypervisor_paths = find_hypervisors()
        if not available_hypervisors:
            print(f"{Fore.RED}❌ Aucun hyperviseur trouvé. Veuillez en installer un.{Style.RESET_ALL}")
            exit(1)

        # ** Étape 2B : Choix de l'hyperviseur (toujours demandé) **
        hypervisor = choose_from_list(
            "Choisissez un hyperviseur",
            list(available_hypervisors.keys())
        )

        # ** Étape 3 : Chargement de la config SEULEMENT en mode `--batch` **
        if args.batch:
            hypervisor_config = config.get("hypervisors", {}).get(hypervisor, {})
            vm_name = hypervisor_config.get("vm_name", "MaVM")
            ram = hypervisor_config.get("ram", 2048)
            iso_path = hypervisor_config.get("iso_path", "isos/ubuntu-24.04.1-live-server-amd64.iso")
            dry_run = hypervisor_config.get("dry_run", False)
        else:
            vm_name = prompt_input(f"{Fore.CYAN}Nom de la VM{Style.RESET_ALL}", default="MaVM")
            ram = int(prompt_input(f"{Fore.CYAN}Mémoire RAM (Mo){Style.RESET_ALL}", default="2048"))
            iso_list = list_local_isos()
            if iso_list:
                iso_path = choose_from_list(f"{Fore.CYAN}Choisissez une ISO{Style.RESET_ALL}", iso_list)
                iso_path = os.path.join("isos", iso_path)
            else:
                print(f"{Fore.YELLOW}⚠️ Aucune ISO trouvée. Téléchargement en cours...{Style.RESET_ALL}")
                iso_path = download_iso()
            dry_run = prompt_input(f"{Fore.CYAN}Mode simulation ? (oui/non){Style.RESET_ALL}", default="non").lower() == "oui"

        print(f"{Fore.CYAN}🚀 Création de la VM '{vm_name}' sous {hypervisor}...{Style.RESET_ALL}")
        create_vm(hypervisor, vm_name, "x86_64", ram, iso_path, hypervisor_paths, dry_run=dry_run)

    else:
        print(f"{Fore.RED}❌ Erreur : Mode non reconnu. Utilisez 'docker' ou 'hypervisor'{Style.RESET_ALL}")
        exit(1)
