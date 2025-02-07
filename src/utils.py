import os
import shutil
import subprocess
import logging
import psutil
import requests
from colorama import Fore, Style

# Configuration du logging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

ISO_FOLDER = "isos/"
DEFAULT_ISO_URL = "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.9.0-amd64-netinst.iso"

def check_and_install_qemu_kvm():
    """Vérifie si QEMU/KVM est installé et propose son installation si nécessaire."""
    if shutil.which("qemu-system-x86_64") is None:
        print(f"{Fore.YELLOW}⚠️ QEMU/KVM n'est pas installé. Voulez-vous l'installer ? (y/n){Style.RESET_ALL}")
        choice = input("👉 Votre choix : ").strip().lower()
        if choice == "y":
            subprocess.run(["sudo", "apt", "update"], check=True)
            subprocess.run(["sudo", "apt", "install", "-y", "qemu-kvm", "libvirt-daemon-system", "virt-manager"], check=True)
            print(f"{Fore.GREEN}✅ QEMU/KVM a été installé avec succès !{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ QEMU/KVM est nécessaire pour certaines fonctionnalités.{Style.RESET_ALL}")

def get_available_memory():
    """Retourne la mémoire vive disponible en Mo."""
    return psutil.virtual_memory().available // (1024 * 1024)

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

def create_docker_container(container_name, image_name, volume_name=""):
    """Crée un conteneur Docker et s'assure qu'il reste actif."""
    print(f"{Fore.CYAN}🚀 Création du conteneur Docker '{container_name}'...{Style.RESET_ALL}")

    # Vérifie si un conteneur du même nom existe déjà et le supprime
    subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Commande de base
    cmd = ["docker", "run", "-d", "--name", container_name]

    # Ajoute un volume si spécifié
    if volume_name:
        cmd.extend(["-v", f"{volume_name}:/data"])

    # Ajoute l’image
    cmd.append(image_name)

    # Vérifie quelle commande de maintien fonctionne
    possible_commands = ["sleep infinity", "tail -f /dev/null", "while true; do sleep 3600; done"]
    selected_command = None

    for command in possible_commands:
        check_command = subprocess.run(
            ["docker", "run", "--rm", image_name, "sh", "-c", f"command -v {command.split()[0]}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if check_command.returncode == 0:
            selected_command = command
            break

    if selected_command is None:
        print(f"{Fore.RED}❌ Aucune commande de maintien trouvée dans l'image Docker !{Style.RESET_ALL}")
        return

    cmd.extend(["sh", "-c", selected_command])

    # Exécute la commande
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        print(f"{Fore.GREEN}✅ Conteneur '{container_name}' créé et en cours d'exécution.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ Erreur lors de la création du conteneur :{Style.RESET_ALL}")
        print(result.stderr)

def is_docker_installed():
    """Vérifie si Docker est installé et en cours d'exécution."""
    if shutil.which("docker") is None:
        print(f"{Fore.RED}❌ Docker n'est pas installé. Voulez-vous l'installer ? (y/n){Style.RESET_ALL}")
        choice = input("👉 Votre choix : ").strip().lower()
        if choice == "y":
            subprocess.run(["sudo", "apt", "update"], check=True)
            subprocess.run(["sudo", "apt", "install", "-y", "docker.io"], check=True)
            print(f"{Fore.GREEN}✅ Docker a été installé avec succès !{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}❌ Docker est nécessaire pour certaines fonctionnalités.{Style.RESET_ALL}")
            return False

    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "docker"])
        return True
    except subprocess.CalledProcessError:
        return False

if __name__ == "__main__":
    print(f"{Fore.CYAN}🌍 Détection du système : Ubuntu{Style.RESET_ALL}")

    # Vérification de QEMU/KVM
    check_and_install_qemu_kvm()

    # Vérification de Docker
    if is_docker_installed():
        print(f"{Fore.GREEN}✅ Docker est installé et fonctionne.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ Docker n'est pas installé ou ne fonctionne pas.{Style.RESET_ALL}")

    # Liste des ISOs locales
    isos = list_local_isos()
    if isos:
        print(f"{Fore.YELLOW}📂 ISOs disponibles : {isos}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ Aucune ISO trouvée. Téléchargement en cours...{Style.RESET_ALL}")
        download_iso()

    # Création d'un disque QCOW2
    create_qcow2_disk("test_disk", "20G")

    # Création d'un conteneur Docker de test
    create_docker_container("test_container", "ubuntu")
