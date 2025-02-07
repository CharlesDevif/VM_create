import logging
import os
import subprocess
import json
import argparse
from colorama import Fore, Style, init
from os_detection import detect_os, find_hypervisors, get_default_interface
from utils import (
    prompt_input, get_available_memory, create_qcow2_disk, convert_disk_format,
    list_local_isos, download_iso, vm_exists, choose_from_list, is_docker_installed, create_docker_container
)

# Initialisation de Colorama pour Windows
init(autoreset=True)

def load_config(file_path="config.json"):
    """Charge la configuration depuis un fichier JSON si '--batch' est utilisé."""
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return json.load(file)
    return {}

def parse_arguments():
    """Analyse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Gestionnaire de VMs et conteneurs Docker."
    )
    parser.add_argument("--batch", action="store_true", help="Mode automatique avec configuration prédéfinie.")
    parser.add_argument("--config", type=str, default="config.json", help="Chemin du fichier de configuration JSON.")
    # Ajout de l'argument pour l'interface de bridge
    parser.add_argument("--bridge", type=str, default=None,
                        help="Interface de bridge à utiliser (sinon NAT sera utilisé)")
    return parser.parse_args()

def create_vm(hypervisor, name, arch, ram, iso_path, paths, dry_run=False, bridge_interface=None):
    """Crée une machine virtuelle avec gestion optionnelle du bridge réseau."""
    # Vérification si la VM existe déjà
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
        # Conversion du disque pour VirtualBox (format VDI)
        converted_disk = convert_disk_format(qcow2_disk, f"{name}.vdi", "vdi")

        # Liste de commandes de base pour VirtualBox
        cmd_vm = [
            [vbox_path, "createvm", "--name", name, "--register"],
            [vbox_path, "modifyvm", name, "--memory", str(ram)],
            [vbox_path, "modifyvm", name, "--ioapic", "off"],
            [vbox_path, "modifyvm", name, "--apic", "on"],
            [vbox_path, "storagectl", name, "--name", "SATA Controller", "--add", "sata", "--controller", "IntelAhci"],
            [vbox_path, "storageattach", name, "--storagectl", "SATA Controller", "--port", "0", "--device", "0", "--type", "hdd", "--medium", converted_disk],
            [vbox_path, "storageattach", name, "--storagectl", "SATA Controller", "--port", "1", "--device", "0", "--type", "dvddrive", "--medium", iso_path],
            [vbox_path, "modifyvm", name, "--boot1", "dvd"],
            [vbox_path, "modifyvm", name, "--biosbootmenu", "messageandmenu"],
        ]

        # Configuration réseau : bridgé ou NAT (NAT par défaut)
        if bridge_interface:
            cmd_vm.append([vbox_path, "modifyvm", name, "--nic1", "bridged"])
            cmd_vm.append([vbox_path, "modifyvm", name, "--bridgeadapter1", bridge_interface])
        else:
            cmd_vm.append([vbox_path, "modifyvm", name, "--nic1", "nat"])

    elif hypervisor == "VMware":
        vmware_path = paths["VMware"]
        converted_disk = convert_disk_format(qcow2_disk, f"{name}.vmdk", "vmdk")
        # Choix du type de connexion en fonction de l'option bridge
        connection_type = "bridged" if bridge_interface else "nat"
        vmx_content = f"""
        .encoding = "UTF-8"
        config.version = "8"
        virtualHW.version = "16"
        displayName = "{name}"
        guestOS = "ubuntu-64"
        memsize = "{ram}"
        numvcpus = "2"
        scsi0.present = "TRUE"
        scsi0.virtualDev = "lsilogic"
        sata0.present = "TRUE"
        sata0:0.present = "TRUE"
        sata0:0.fileName = "{converted_disk}"
        sata0:0.deviceType = "disk"
        ide1:0.present = "TRUE"
        ide1:0.fileName = "{iso_path}"
        ide1:0.deviceType = "cdrom-image"
        ethernet0.present = "TRUE"
        ethernet0.connectionType = "{connection_type}"
        """
        vmx_path = f"{name}.vmx"
        with open(vmx_path, "w") as vmx_file:
            vmx_file.write(vmx_content.strip())
        logging.info(f"✅ Fichier VMX créé : {vmx_path}")

        cmd_vm = [[vmware_path, "-T", "ws", "start", vmx_path]]

    elif hypervisor == "QEMU":
        # Pour QEMU, configuration de la partie réseau en mode bridge ou NAT
        if bridge_interface:
            # Pour le mode bridge, il faut disposer d'une interface TAP déjà configurée et associée à un bridge
            net_params = [
                "-netdev", f"tap,id=net0,ifname={bridge_interface},script=no,downscript=no",
                "-device", "virtio-net-pci,netdev=net0"
            ]
        else:
            net_params = ["-net", "nic", "-net", "user"]

        cmd_vm = [[
            paths["QEMU"], "-m", str(ram),
            "-hda", qcow2_disk,
            "-cdrom", iso_path,
            "-boot", "d",
            "-vga", "virtio",
            "-display", "gtk,gl=on",
            "-accel", "tcg",
            "-smp", "2",
            "-usb", "-device", "usb-tablet"
        ] + net_params]

    if dry_run:
        print(f"{Fore.MAGENTA}[Dry-run] Commandes : {cmd_vm}{Style.RESET_ALL}")
        return

    # Exécution des commandes
    for cmd in cmd_vm:
        print(f"{Fore.BLUE}🖥️ Exécution : {' '.join(cmd)}{Style.RESET_ALL}")
        subprocess.run(cmd, check=True)

    print(f"{Fore.GREEN}✅ VM '{name}' créée avec succès.{Style.RESET_ALL}")

if __name__ == "__main__":
    args = parse_arguments()

    # Charger la configuration si '--batch' est activé
    config = load_config(args.config) if args.batch else {}

    os_type = detect_os()

    # Étape 1 : Choix entre Docker et Hyperviseur (toujours demandé)
    mode = choose_from_list(
        f"{Fore.YELLOW}Voulez-vous créer une VM ou un conteneur Docker ?{Style.RESET_ALL}",
        ["docker", "hypervisor"]
    )

    if mode == "docker":
        # Vérification de Docker
        if not is_docker_installed():
            print(f"{Fore.RED}❌ Docker n'est pas installé ou le service n'est pas en cours d'exécution.{Style.RESET_ALL}")
            exit(1)

        # Chargement de la config Docker en mode '--batch'
        if args.batch:
            docker_config = config.get("docker", {})
            container_name = docker_config.get("container_name", "mon-conteneur")
            image_name = docker_config.get("image_name", "ubuntu:latest")
            volume_name = docker_config.get("volume_name", "")
            ports = docker_config.get("ports", {})
            env_vars = docker_config.get("env_vars", {})
            command = docker_config.get("command", "bash")
        else:
            container_name = prompt_input(f"{Fore.CYAN}Nom du conteneur Docker{Style.RESET_ALL}", default="mon-conteneur")
            image_name = prompt_input(f"{Fore.CYAN}Image Docker à utiliser{Style.RESET_ALL}", default="ubuntu:latest")
            volume_name = prompt_input(f"{Fore.CYAN}Nom du volume (laisser vide pour pas de volume){Style.RESET_ALL}", default="")
            ports = {}  # Ajout des ports en mode interactif
            while True:
                add_port = prompt_input(f"{Fore.CYAN}Voulez-vous ajouter un port ? (oui/non){Style.RESET_ALL}", default="non").lower()
                if add_port == "oui":
                    host_port = prompt_input(f"{Fore.CYAN}Port hôte{Style.RESET_ALL}", required=True)
                    container_port = prompt_input(f"{Fore.CYAN}Port conteneur{Style.RESET_ALL}", required=True)
                    ports[host_port] = container_port
                else:
                    break

            env_vars = {}  # Ajout des variables d'environnement en mode interactif
            while True:
                add_env = prompt_input(f"{Fore.CYAN}Voulez-vous ajouter une variable d'environnement ? (oui/non){Style.RESET_ALL}", default="non").lower()
                if add_env == "oui":
                    key = prompt_input(f"{Fore.CYAN}Nom de la variable{Style.RESET_ALL}", required=True)
                    value = prompt_input(f"{Fore.CYAN}Valeur de la variable{Style.RESET_ALL}", required=True)
                    env_vars[key] = value
                else:
                    break

            command = prompt_input(f"{Fore.CYAN}Commande à exécuter dans le conteneur{Style.RESET_ALL}", default="bash")

        print(f"{Fore.CYAN}🚀 Lancement du conteneur Docker...{Style.RESET_ALL}")
        create_docker_container(container_name, image_name, volume_name, ports, env_vars, command)
        print(f"{Fore.GREEN}✅ Conteneur '{container_name}' créé avec succès !{Style.RESET_ALL}")
        exit(0)

    elif mode == "hypervisor":
        # Détection des hyperviseurs disponibles
        available_hypervisors, hypervisor_paths = find_hypervisors()
        if not available_hypervisors:
            print(f"{Fore.RED}❌ Aucun hyperviseur trouvé. Veuillez en installer un.{Style.RESET_ALL}")
            exit(1)

        # Choix de l'hyperviseur
        hypervisor = choose_from_list("Choisissez un hyperviseur", list(available_hypervisors.keys()))

        if args.batch:
            hypervisor_config = config.get("hypervisors", {}).get(hypervisor, {})
            vm_name = hypervisor_config.get("vm_name", "MaVM")
            ram = hypervisor_config.get("ram", 2048)
            iso_path = hypervisor_config.get("iso_path", "isos/ubuntu-24.04.1-live-server-amd64.iso")
            dry_run = hypervisor_config.get("dry_run", False)
            bridge_interface = hypervisor_config.get("bridge", None)
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
            
            # Si aucun argument --bridge n'est passé, on essaie de détecter automatiquement l'interface par défaut
            if args.bridge:
                bridge_interface = args.bridge
            else:
                detected_iface = get_default_interface()
                if detected_iface:
                    use_auto = choose_from_list(
                        f"{Fore.CYAN}Interface par défaut détectée : {detected_iface}. Voulez-vous l'utiliser ?{Style.RESET_ALL}",
                        ["Oui", "Non"]
                    )
                    if use_auto.lower() == "oui":
                        bridge_interface = detected_iface
                    else:
                        bridge_interface = prompt_input(f"{Fore.CYAN}Entrez le nom de l'interface de bridge{Style.RESET_ALL}", required=True)
                else:
                    bridge_interface = prompt_input(f"{Fore.CYAN}Aucune interface par défaut détectée. Entrez le nom de l'interface de bridge{Style.RESET_ALL}", required=True)

        print(f"{Fore.CYAN}🚀 Création de la VM '{vm_name}' sous {hypervisor}...{Style.RESET_ALL}")
        # On transmet l'option bridge selon le choix effectué
        create_vm(hypervisor, vm_name, "x86_64", ram, iso_path, hypervisor_paths, dry_run=dry_run, bridge_interface=bridge_interface)

    else:
        print(f"{Fore.RED}❌ Erreur : Mode non reconnu. Utilisez 'docker' ou 'hypervisor'{Style.RESET_ALL}")
        exit(1)
