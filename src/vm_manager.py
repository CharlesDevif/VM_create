import logging
import os
import subprocess
import json
import argparse
from colorama import Fore, Style, init
from os_detection import detect_os, find_hypervisors
from utils import (
    prompt_input, get_available_memory, create_qcow2_disk, convert_disk_format,
    list_local_isos, download_iso, vm_exists, choose_from_list,
    is_docker_installed, create_docker_container,detect_linux_bridge, create_linux_bridge
)
from network import (detect_bridgeable_interface,create_tap_interface)

# Initialisation de Colorama pour Windows
init(autoreset=True)

def load_config(file_path="config.json"):
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return json.load(file)
    return {}

def parse_arguments():
    parser = argparse.ArgumentParser(description="Gestionnaire de VMs et conteneurs Docker.")
    parser.add_argument("--batch", action="store_true", help="Mode automatique avec configuration prédéfinie.")
    parser.add_argument("--config", type=str, default="config.json", help="Chemin du fichier de configuration JSON.")
    parser.add_argument("--bridge", type=str, default=None, help="Interface de bridge à utiliser (sinon NAT sera utilisé)")
    parser.add_argument("--auto-bridge", action="store_true", help="Utilise automatiquement une interface bridge sans interaction")
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
            from network import create_tap_interface
            tap_iface = create_tap_interface()
            if not tap_iface:
                print(f"{Fore.RED}❌ Échec de la configuration réseau. Passage en NAT.{Style.RESET_ALL}")
                net_params = ["-net", "nic", "-net", "user"]
            else:
                net_params = [
                    "-netdev", f"tap,id=net0,ifname={tap_iface},script=no,downscript=no",
                    "-device", "virtio-net-pci,netdev=net0"
                ]


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


def main():
    args = parse_arguments()
    config = load_config(args.config) if args.batch else {}
    os_type = detect_os()

    mode = choose_from_list(
        f"{Fore.YELLOW}Voulez-vous créer une VM ou un conteneur Docker ?{Style.RESET_ALL}",
        ["docker", "hypervisor"]
    )

    if mode == "docker":
        if not is_docker_installed():
            print(f"{Fore.RED}❌ Docker n'est pas installé ou le service n'est pas en cours d'exécution.{Style.RESET_ALL}")
            exit(1)

        if args.batch:
            docker_config = config.get("docker", {})
            container_name = docker_config.get("container_name", "mon-conteneur")
            image_name = docker_config.get("image_name", "ubuntu:latest")
            volume_name = docker_config.get("volume_name", "")
            ports = docker_config.get("ports", {})
            env_vars = docker_config.get("env_vars", {})
            command = docker_config.get("command", "bash")
        else:
            container_name = prompt_input("Nom du conteneur Docker", default="mon-conteneur")
            image_name = prompt_input("Image Docker à utiliser", default="ubuntu:latest")
            volume_name = prompt_input("Nom du volume (laisser vide pour pas de volume)", default="")
            ports = {}
            while prompt_input("Ajouter un port ? (oui/non)", default="non").lower() == "oui":
                host_port = prompt_input("Port hôte", required=True)
                container_port = prompt_input("Port conteneur", required=True)
                ports[host_port] = container_port

            env_vars = {}
            while prompt_input("Ajouter une variable d'environnement ? (oui/non)", default="non").lower() == "oui":
                key = prompt_input("Nom de la variable", required=True)
                value = prompt_input("Valeur de la variable", required=True)
                env_vars[key] = value

            command = prompt_input("Commande à exécuter dans le conteneur", default="bash")

        create_docker_container(container_name, image_name, volume_name, ports, env_vars, command)
        return

    elif mode == "hypervisor":
        available_hypervisors, hypervisor_paths = find_hypervisors()
        if not available_hypervisors:
            print(f"{Fore.RED}❌ Aucun hyperviseur trouvé. Veuillez en installer un.{Style.RESET_ALL}")
            exit(1)

        hypervisor = choose_from_list("Choisissez un hyperviseur", list(available_hypervisors.keys()))

        if args.batch:
            hypervisor_config = config.get("hypervisors", {}).get(hypervisor, {})
            vm_name = hypervisor_config.get("vm_name", "MaVM")
            ram = hypervisor_config.get("ram", 2048)
            iso_path = hypervisor_config.get("iso_path", "isos/ubuntu.iso")
            dry_run = hypervisor_config.get("dry_run", False)
            bridge_interface = hypervisor_config.get("bridge", None)
        else:
            vm_name = prompt_input("Nom de la VM", default="MaVM")
            ram = int(prompt_input("Mémoire RAM (Mo)", default="2048"))
            iso_list = list_local_isos()
            iso_path = os.path.join("isos", choose_from_list("Choisissez une ISO", iso_list)) if iso_list else download_iso()
            dry_run = prompt_input("Mode simulation ? (oui/non)", default="non").lower() == "oui"

            if args.bridge:
                bridge_interface = args.bridge
            else:
                bridge_interface = detect_linux_bridge()
                if not bridge_interface:
                    default_iface = detect_bridgeable_interface()
                    if default_iface:
                        print(f"{Fore.YELLOW}🔧 Aucun bridge trouvé. Tentative de création d’un bridge 'br0' avec {default_iface}...{Style.RESET_ALL}")
                        if create_linux_bridge("br0", default_iface):
                            bridge_interface = "br0"
                            print(f"{Fore.GREEN}✅ Bridge 'br0' créé avec succès !{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}❌ Échec de la création du bridge. Utilisation du mode NAT par défaut.{Style.RESET_ALL}")
                            bridge_interface = None
                    else:
                        print(f"{Fore.RED}❌ Aucun bridge ni interface par défaut détectée. Utilisation du mode NAT.{Style.RESET_ALL}")
                        bridge_interface = None

        print(f"{Fore.CYAN}🚀 Création de la VM '{vm_name}' sous {hypervisor}...{Style.RESET_ALL}")
        create_vm(hypervisor, vm_name, "x86_64", ram, iso_path, hypervisor_paths, dry_run=dry_run, bridge_interface=bridge_interface)

if __name__ == "__main__":
    main()