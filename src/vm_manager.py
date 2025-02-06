import logging
import os
import subprocess
from colorama import Fore, Style, init
from os_detection import detect_os, find_hypervisors
from utils import (
    prompt_input, get_available_memory, create_qcow2_disk, convert_disk_format,
    list_local_isos, download_iso, vm_exists, choose_from_list, is_docker_installed, create_docker_container
)

# Initialisation de Colorama pour Windows
init(autoreset=True)

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
            [vbox_path, "modifyvm", name, "--ioapic", "off"],  # IO-APIC doit rester activé
            [vbox_path, "modifyvm", name, "--apic", "on"],  # APIC doit rester activé
            [vbox_path, "storagectl", name, "--name", "SATA Controller", "--add", "sata", "--controller", "IntelAhci"],
            [vbox_path, "storageattach", name, "--storagectl", "SATA Controller", "--port", "0", "--device", "0", "--type", "hdd", "--medium", converted_disk],
            [vbox_path, "storageattach", name, "--storagectl", "SATA Controller", "--port", "1", "--device", "0", "--type", "dvddrive", "--medium", iso_path],
            [vbox_path, "modifyvm", name, "--boot1", "dvd"],  # Priorité boot sur l'ISO
            [vbox_path, "modifyvm", name, "--biosbootmenu", "messageandmenu"],  # Active le menu BIOS
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
    print(f"\n{Fore.CYAN}🌍 Détection du système d'exploitation...{Style.RESET_ALL}")
    os_type = detect_os()

    # Demander si l'utilisateur veut un conteneur Docker ou une VM
    use_docker = prompt_input(f"\n{Fore.YELLOW}Voulez-vous créer un conteneur Docker plutôt qu'une VM ? (oui/non){Style.RESET_ALL}", default="non").lower() == "oui"

    if use_docker:
        if not is_docker_installed():
            print(f"{Fore.RED}❌ Docker n'est pas installé ou le service n'est pas en cours d'exécution.{Style.RESET_ALL}")
            exit(1)

        container_name = prompt_input(f"{Fore.CYAN}Nom du conteneur Docker{Style.RESET_ALL}", default="mon-conteneur")
        image_name = prompt_input(f"{Fore.CYAN}Image Docker à utiliser{Style.RESET_ALL}", default="ubuntu:latest")
        volume_name = prompt_input(f"{Fore.CYAN}Nom du volume (laisser vide pour pas de volume){Style.RESET_ALL}", default="")

        create_docker_container(container_name, image_name, volume_name)
        print(f"{Fore.GREEN}✅ Conteneur '{container_name}' créé avec succès !{Style.RESET_ALL}")
        exit(0)

    print(f"\n{Fore.CYAN}🔍 Détection des hyperviseurs disponibles...{Style.RESET_ALL}")
    available_hypervisors, hypervisor_paths = find_hypervisors()

    if not available_hypervisors:
        print(f"{Fore.RED}❌ Aucun hyperviseur trouvé. Veuillez en installer un.{Style.RESET_ALL}")
        exit(1)

    hypervisor = choose_from_list("Choisissez un hyperviseur", list(available_hypervisors.keys()))
    vm_name = prompt_input(f"{Fore.CYAN}Nom de la VM{Style.RESET_ALL}", default="MaVM")
    arch = prompt_input(f"{Fore.CYAN}Architecture (x86_64, arm, etc.){Style.RESET_ALL}", default="x86_64")
    ram = prompt_input(f"{Fore.CYAN}Mémoire RAM (Mo){Style.RESET_ALL}", default=str(min(2048, get_available_memory())), validator=lambda x: int(x) if int(x) > 0 and int(x) <= get_available_memory() else ValueError("Valeur invalide."))

    iso_list = list_local_isos()
    if iso_list:
        iso_path = choose_from_list(f"{Fore.CYAN}Choisissez une ISO{Style.RESET_ALL}", iso_list)
        iso_path = os.path.join("isos", iso_path)
    else:
        print(f"{Fore.YELLOW}⚠️ Aucune ISO trouvée. Téléchargement en cours...{Style.RESET_ALL}")
        iso_path = download_iso()

    dry_run = prompt_input(f"{Fore.CYAN}Mode simulation ? (oui/non){Style.RESET_ALL}", default="non").lower() == "oui"

    create_vm(hypervisor, vm_name, arch, ram, iso_path, hypervisor_paths, dry_run=dry_run)
