import logging
import os
import subprocess
from os_detection import detect_os, find_hypervisors
from utils import (
    prompt_input, get_available_memory, create_qcow2_disk, convert_disk_format,
    list_local_isos, download_iso, vm_exists, choose_from_list, is_docker_installed, create_docker_container
)

def create_vm(hypervisor, name, arch, ram, iso_path, paths, dry_run=False):
    """Crée une machine virtuelle avec une meilleure gestion de l'expérience utilisateur."""

    while vm_exists(hypervisor, name, paths):
        logging.warning(f"⚠️ La VM '{name}' existe déjà.")
        
        choix = choose_from_list("Que voulez-vous faire ?", ["Supprimer la VM", "Changer de nom"])
        if choix == "Supprimer la VM":
            logging.info(f"🗑 Suppression de la VM existante '{name}'...")
            if hypervisor == "VirtualBox":
                subprocess.run([paths["VirtualBox"], "unregistervm", name, "--delete"], check=True)
            elif hypervisor == "VMware":
                subprocess.run([paths["VMware"], "-T", "ws", "deleteVM", f"{name}.vmx"], check=True)
            elif hypervisor == "Hyper-V":
                subprocess.run(["powershell.exe", "Remove-VM", "-Name", name, "-Force"], check=True)
            logging.info(f"✅ VM '{name}' supprimée.")
        else:
            name = prompt_input("Entrez un nouveau nom pour la VM", required=True)

    if vm_exists(hypervisor, name, paths):
        logging.error(f"❌ Impossible de créer la VM '{name}', elle existe toujours après modification.")
        return

    logging.info(f"\n➡️ Création de la VM '{name}' avec {ram} Mo de RAM sous {hypervisor}...")

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

    elif hypervisor == "VMware":
        vmware_path = paths["VMware"]
        converted_disk = convert_disk_format(qcow2_disk, f"{name}.vmdk", "vmdk")
        
        # 1️⃣ Créer un fichier VMX de base
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
        ethernet0.connectionType = "nat"
        """
        
        vmx_path = f"{name}.vmx"
        with open(vmx_path, "w") as vmx_file:
            vmx_file.write(vmx_content.strip())

        logging.info(f"✅ Fichier VMX créé : {vmx_path}")

        # 2️⃣ Démarrer la VM avec vmrun
        cmd_vm = [[vmware_path, "-T", "ws", "start", vmx_path]]

    elif hypervisor == "QEMU":
        cmd_vm = [[
            paths["QEMU"], "-m", str(ram),
            "-hda", qcow2_disk, "-cdrom", iso_path, "-boot", "d",
            "-vga", "virtio",
            "-display", "gtk,gl=on",
            "-accel", "tcg",  # 🔄 Utilise l'émulation logicielle si KVM est absent
            "-smp", "2",
            "-usb", "-device", "usb-tablet"
        ]]

    if dry_run:
        logging.info(f"[Dry-run] Commandes : {cmd_vm}")
        return

    for cmd in cmd_vm:
        logging.info(f"🖥️ Exécution : {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    logging.info(f"✅ VM '{name}' créée avec succès.")


if __name__ == "__main__":
    os_type = detect_os()

    # 1️⃣ Demander si l'utilisateur veut un conteneur Docker ou une VM
    use_docker = prompt_input("Voulez-vous créer un conteneur Docker plutôt qu'une VM ? (oui/non)", default="non").lower() == "oui"

    if use_docker:
        if not is_docker_installed():
            logging.critical("❌ Docker n'est pas installé ou le service n'est pas en cours d'exécution.")
            exit(1)

        container_name = prompt_input("Nom du conteneur Docker", default="mon-conteneur")
        image_name = prompt_input("Image Docker à utiliser", default="ubuntu:latest")
        volume_name = prompt_input("Nom du volume (ou laisser vide pour pas de volume)", default="")

        create_docker_container(container_name, image_name, volume_name)
        exit(0)  # Fin du script si Docker est utilisé

    # 2️⃣ Recherche des hyperviseurs seulement si Docker n'est pas choisi
    available_hypervisors, hypervisor_paths = find_hypervisors()

    if not available_hypervisors:
        logging.critical("❌ Aucun hyperviseur trouvé. Veuillez en installer un.")
        exit(1)

    hypervisor = choose_from_list("Choisissez un hyperviseur", list(available_hypervisors.keys()))
    vm_name = prompt_input("Nom de la VM", default="MaVM")
    arch = prompt_input("Architecture (x86_64, arm, etc.)", default="x86_64")
    ram = prompt_input("Mémoire RAM (Mo)", default=str(min(2048, get_available_memory())), validator=lambda x: int(x) if int(x) > 0 and int(x) <= get_available_memory() else ValueError("Valeur invalide."))

    iso_list = list_local_isos()
    if iso_list:
        iso_path = choose_from_list("Choisissez une ISO", iso_list)
        iso_path = os.path.join("isos", iso_path)
    else:
        logging.info("Aucune ISO trouvée. Téléchargement en cours...")
        iso_path = download_iso()

    dry_run = prompt_input("Mode simulation ? (oui/non)", default="non").lower() == "oui"

    create_vm(hypervisor, vm_name, arch, ram, iso_path, hypervisor_paths, dry_run=dry_run)
