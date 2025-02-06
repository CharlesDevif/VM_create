import os
import subprocess
import logging
import psutil
import requests
from colorama import Fore, Style


# Configuration du logging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

ISO_FOLDER = "isos/"
DEFAULT_ISO_URL = "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.9.0-amd64-netinst.iso"

def get_available_memory():
    """Retourne la mémoire vive disponible en Mo."""
    return psutil.virtual_memory().available // (1024 * 1024)

def choose_from_list(title, options):
    """
    Affiche un menu interactif pour choisir parmi une liste d'options.
    
    - title: Titre de la sélection
    - options: Liste des choix possibles (ex: ['VirtualBox', 'VMware'])
    
    Retourne l'élément sélectionné.
    """
    print(f"\n🔍 {title} :")
    for i, option in enumerate(options, 1):
        print(f"  [{i}] {option}")

    while True:
        choice = input(f"👉 Entrez le numéro de votre choix (1-{len(options)}) : ").strip()
        if choice.isdigit():
            choice = int(choice)
            if 1 <= choice <= len(options):
                return options[choice - 1]
        
        print("❌ Entrée invalide. Veuillez choisir un numéro valide.")


def prompt_input(prompt, default=None, required=False, validator=None):
    """Demande une entrée utilisateur avec validation et valeur par défaut."""
    while True:
        user_input = input(f"{prompt} ({'défaut: ' + str(default) if default else 'obligatoire'}) : ").strip()
        
        if not user_input:
            if default is not None:
                return default
            if required:
                logging.warning("⚠️ Cette information est obligatoire, veuillez entrer une valeur.")
                continue

        if validator:
            try:
                return validator(user_input)
            except ValueError as e:
                logging.error(f"❌ Erreur : {e}")
                continue
        
        return user_input

def create_qcow2_disk(disk_name, size="10G"):
    """Crée un disque virtuel QCOW2 avec QEMU."""
    logging.info(f"📦 Création du disque {disk_name}.qcow2 ({size})...")
    cmd = ["qemu-img", "create", "-f", "qcow2", f"{disk_name}.qcow2", size]

    try:
        subprocess.run(cmd, check=True)
        logging.info(f"✅ Disque {disk_name}.qcow2 créé.")
        return f"{disk_name}.qcow2"
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Erreur lors de la création du disque QCOW2 : {e}")
        return None

def convert_disk_format(source_disk, target_disk, format):
    """Convertit un disque QCOW2 dans un autre format (VDI, VMDK, VHD)."""
    logging.info(f"🔄 Conversion du disque {source_disk} en {format}...")
    cmd = ["qemu-img", "convert", "-O", format, source_disk, target_disk]

    try:
        subprocess.run(cmd, check=True)
        logging.info(f"✅ Disque converti en {target_disk}")
        return target_disk
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Erreur lors de la conversion du disque : {e}")
        return None

def list_local_isos():
    """Liste les ISOs disponibles dans le dossier 'isos/'."""
    if not os.path.exists(ISO_FOLDER):
        os.makedirs(ISO_FOLDER)
    return [f for f in os.listdir(ISO_FOLDER) if f.endswith(".iso")]

def download_iso(url=DEFAULT_ISO_URL):
    """Télécharge une ISO à partir d'une URL."""
    logging.info(f"📥 Téléchargement de l'ISO depuis {url}...")

    iso_path = os.path.join(ISO_FOLDER, os.path.basename(url))
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(iso_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"✅ ISO téléchargée : {iso_path}")
        return iso_path
    except requests.RequestException as e:
        logging.error(f"❌ Erreur lors du téléchargement de l'ISO : {e}")
        return None

def vm_exists(hypervisor, name, paths):
    """Vérifie si une VM existe déjà pour l'hyperviseur donné."""
    try:
        if hypervisor == "VirtualBox":
            cmd = [paths["VirtualBox"], "list", "vms"]
        elif hypervisor == "VMware":
            cmd = [paths["VMware"], "-T", "ws", "list"]
        elif hypervisor == "Hyper-V":
            cmd = ["powershell.exe", "Get-VM", "-Name", name]
        else:
            return False

        result = subprocess.run(cmd, capture_output=True, text=True)
        return name in result.stdout

    except subprocess.CalledProcessError:
        return False

def create_docker_container(container_name, image_name, volume_name=""):
    """Crée un conteneur Docker et s'assure qu'il reste actif."""
    print(f"{Fore.CYAN}🚀 Création du conteneur Docker '{container_name}'...{Style.RESET_ALL}")

    # Vérifie si un conteneur du même nom existe déjà
    subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Commande de base
    cmd = ["docker", "run", "-d", "--name", container_name]

    # Ajoute un volume si spécifié
    if volume_name:
        cmd.extend(["-v", f"{volume_name}:/data"])

    # Ajoute l’image
    cmd.append(image_name)

    # Ajoute un processus qui garde le conteneur en vie
    cmd.extend(["/bin/sh", "-c", "sleep infinity"])

    # Exécute la commande
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        print(f"{Fore.GREEN}✅ Conteneur '{container_name}' créé et en cours d'exécution.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ Erreur lors de la création du conteneur :{Style.RESET_ALL}")
        print(result.stderr)


def is_docker_installed():
    """Vérifie si Docker est installé et en cours d'exécution."""
    try:
        subprocess.run(["docker", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        subprocess.run(["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False

