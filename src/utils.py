import os
import subprocess
import logging
import psutil
import requests
from colorama import Fore, Style
from bs4 import BeautifulSoup
from tqdm import tqdm




# Configuration du logging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

def detect_linux_bridge():
    """Détecte automatiquement un bridge réseau actif comme 'br0' ou 'virbr0'."""
    bridges = []
    blacklist = ("lo", "docker", "veth", "vmnet", "tap", "tun", "wl")

    for iface, stats in psutil.net_if_stats().items():
        if stats.isup and any(prefix in iface for prefix in ("br", "virbr")) and not any(bad in iface for bad in blacklist):
            bridges.append(iface)

    return bridges[0] if bridges else None

def create_linux_bridge(bridge_name="br0", physical_iface=None):
    """Crée un bridge Linux avec l'interface physique donnée."""
    try:
        subprocess.run(["sudo", "ip", "link", "add", bridge_name, "type", "bridge"], check=True)
        subprocess.run(["sudo", "ip", "link", "set", bridge_name, "up"], check=True)
        if physical_iface:
            subprocess.run(["sudo", "ip", "link", "set", physical_iface, "master", bridge_name], check=True)
            subprocess.run(["sudo", "ip", "link", "set", physical_iface, "up"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de la création du bridge : {e}")
        return False


def get_latest_debian_netinst_url():
    """
    Scrape la page Debian pour récupérer dynamiquement l'URL de la dernière ISO netinst AMD64.
    """
    base_url = "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/"
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Trouver le lien vers une ISO netinst
        for link in soup.find_all("a"):
            href = link.get("href")
            if href and href.endswith("-netinst.iso"):
                full_url = base_url + href
                logging.info(f"🔗 Dernière ISO détectée : {full_url}")
                return full_url

        logging.warning("⚠️ Aucune ISO netinst trouvée.")
        return None
    except requests.RequestException as e:
        logging.error(f"❌ Erreur lors de la récupération de l'ISO Debian : {e}")
        return None


ISO_FOLDER = "isos/"

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

def download_iso(url=None):
    """
    Télécharge une ISO à partir d'une URL (défaut = Debian netinst dernière version),
    avec une barre de progression grâce à tqdm.
    """
    if url is None:
        url = get_latest_debian_netinst_url()
        if url is None:
            logging.error("❌ Impossible de récupérer l'URL ISO automatiquement.")
            return None

    logging.info(f"📥 Téléchargement de l'ISO depuis {url}...")
    iso_path = os.path.join(ISO_FOLDER, os.path.basename(url))

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192  # 8 KB

        with open(iso_path, "wb") as f, tqdm(
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            desc="Téléchargement ISO"
        ) as pbar:
            for chunk in response.iter_content(chunk_size=block_size):
                f.write(chunk)
                pbar.update(len(chunk))

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

def create_docker_container(container_name, image_name, volume_name="", ports=None, env_vars=None, command="bash"):
    """
    Crée un conteneur Docker de manière robuste.

    - container_name : Nom du conteneur
    - image_name : Image Docker à utiliser
    - volume_name : Nom du volume (optionnel)
    - ports : Dictionnaire de ports {hôte: conteneur} (ex: {8080: 80})
    - env_vars : Dictionnaire des variables d'environnement {clé: valeur}
    - command : Commande à exécuter à l'intérieur du conteneur (ex: "bash")

    """


    print(f"{Fore.CYAN}🚀 Création du conteneur Docker '{container_name}'...{Style.RESET_ALL}")

    # 🗑 Supprime le conteneur s'il existe déjà
    subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # ⚙️ Commande de base
    cmd = ["docker", "run", "-dit", "--name", container_name]

    # 📦 Ajout du volume si spécifié
    if volume_name:
        cmd.extend(["-v", f"{volume_name}:/data"])

    # 🔌 Ajout des ports s'ils sont définis
    if ports:
        for host_port, container_port in ports.items():
            cmd.extend(["-p", f"{host_port}:{container_port}"])

    # 🌍 Ajout des variables d'environnement
    if env_vars:
        for key, value in env_vars.items():
            cmd.extend(["-e", f"{key}={value}"])

    # 🖼 Ajout de l’image
    cmd.append(image_name)

    # 🏁 Ajout de la commande personnalisée
    cmd.extend(["sh", "-c", command])

    # 🏗 Exécution de la commande
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        print(f"{Fore.GREEN}✅ Conteneur '{container_name}' créé avec succès !{Style.RESET_ALL}")
        print(f"👉 Pour entrer dans le conteneur : {Fore.YELLOW}docker exec -it {container_name} bash{Style.RESET_ALL}")
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

