import os
import platform
import shutil
import subprocess
from colorama import Fore, Style

def detect_os():
    """Détecte l'OS actuel et retourne un nom normalisé."""
    os_name = platform.system()

    if os_name == "Linux":
        try:
            with open("/etc/os-release", "r") as f:
                os_info = f.read().lower()
                if "ubuntu" in os_info:
                    return "Ubuntu"
                elif "debian" in os_info:
                    return "Debian"
                elif "arch" in os_info:
                    return "Arch"
                elif "fedora" in os_info:
                    return "Fedora"
                elif "centos" in os_info:
                    return "CentOS"
        except FileNotFoundError:
            pass
        
        # Vérifier si on est sur WSL
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    return "WSL"
        except FileNotFoundError:
            pass

        return "Linux"

    elif os_name == "Darwin":
        return "macOS"

    elif os_name == "Windows":
        try:
            # Vérifie si Hyper-V est activé
            result = subprocess.run(["systeminfo"], stdout=subprocess.PIPE, text=True, errors="ignore")
            if "Hyper-V Requirements" in result.stdout:
                return "Windows (Hyper-V)"
        except Exception:
            pass
        return "Windows"

    return os_name

def check_command_exists(command):
    """Vérifie si une commande est disponible."""
    return shutil.which(command) is not None

def run_command(command):
    """Exécute une commande et retourne True si elle réussit."""
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def find_hypervisors():
    """Détecte les hyperviseurs disponibles sur le système."""
    os_type = detect_os()
    hypervisors = {}

    hypervisor_checks = {
        "KVM": {
            "command": ["kvm-ok"],
            "fallback": "kvm",
            "paths": ["/usr/sbin/kvm-ok"]
        },
        "VirtualBox": {
            "command": ["VBoxManage", "-v"],
            "fallback": "VBoxManage",
            "paths": ["/usr/bin/VBoxManage", "C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe"]
        },
        "VMware": {
            "command": ["vmrun", "-v"],
            "fallback": "vmrun",
            "paths": ["/usr/bin/vmrun", "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"]
        },
        "QEMU": {
            "command": ["qemu-system-x86_64", "--version"],
            "fallback": "qemu-system-x86_64",
            "paths": ["/usr/bin/qemu-system-x86_64", "/opt/homebrew/bin/qemu-system-x86_64"]
        },
        "Hyper-V": {
            "command": ["powershell", "Get-WindowsOptionalFeature", "-FeatureName", "Microsoft-Hyper-V-All", "-Online"],
            "fallback": None,
            "paths": []
        },
        "Parallels": {
            "command": ["prlctl", "--version"],
            "fallback": "prlctl",
            "paths": ["/usr/local/bin/prlctl"]
        }
    }

    print("\n🔍 Détection des hyperviseurs...\n")

    for name, check in hypervisor_checks.items():
        found = False
        path_used = None

        # Vérification avec la commande principale
        if check["command"] and run_command(check["command"]):
            found = True
            path_used = check["command"][0]

        # Vérification avec `shutil.which`
        if not found and check["fallback"] and check_command_exists(check["fallback"]):
            found = True
            path_used = check["fallback"]

        # Vérification des chemins connus
        if not found:
            for path in check["paths"]:
                if os.path.exists(path):
                    found = True
                    path_used = path
                    break

        if found:
            hypervisors[name] = path_used
            print(f"{Fore.GREEN}[✔] Hyperviseur détecté : {name} ({path_used}){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[✖] Hyperviseur non trouvé : {name}{Style.RESET_ALL}")

    return hypervisors  # ✅ Retourne bien les hyperviseurs trouvés

def is_docker_installed():
    """Vérifie si Docker est installé et en cours d'exécution."""
    if not check_command_exists("docker"):
        return False  # Docker n'est pas installé

    os_type = detect_os()

    try:
        if os_type == "Windows":
            result = subprocess.run(["wsl", "-l", "-v"], stdout=subprocess.PIPE, text=True)
            return "docker-desktop" in result.stdout.lower()
        elif os_type == "macOS":
            return check_command_exists("brew") and run_command(["brew", "services", "list"])
        else:  # Linux
            status = subprocess.run(["systemctl", "is-active", "docker"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if status.stdout.strip() == "active":
                return True
            status = subprocess.run(["service", "docker", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return "running" in status.stdout.lower()
    except Exception:
        return False  # Erreur lors de la vérification

if __name__ == "__main__":
    detected_os = detect_os()
    print(f"{Fore.CYAN}🌍 OS détecté : {detected_os}{Style.RESET_ALL}")

    hypervisors = find_hypervisors()
    
    print(f"\n🔍 Hyperviseurs détectés : {Fore.YELLOW}{list(hypervisors.keys())}{Style.RESET_ALL}")

    if is_docker_installed():
        print(f"{Fore.GREEN}✅ Docker est installé et fonctionne.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ Docker n'est pas installé ou ne fonctionne pas.{Style.RESET_ALL}")
