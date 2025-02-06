import os
import platform
import shutil
import subprocess
from colorama import Fore, Style

def detect_os():
    """Détecte le système d'exploitation et retourne un nom normalisé."""
    os_name = platform.system()

    if os_name == "Linux":
        try:
            with open("/proc/version", "r") as f:
                version_info = f.read().lower()
                if "microsoft" in version_info:
                    return "WSL"
        except FileNotFoundError:
            pass
        return "Linux"

    if os_name == "Darwin":
        return "MacOS"

    return os_name

def check_command_exists(command):
    """Vérifie si une commande est disponible sur le système."""
    return shutil.which(command) is not None

def run_command(command):
    """Exécute une commande et retourne True si elle réussit."""
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False

def find_docker():
    """Détecte si Docker est disponible sur le Système d'exploitation."""
    docker = {}
    os_type = detect_os()
    paths = {}

    docker_checks = {
        "Docker": {
            "command": ["docker", "--version"],
            "fallback": "docker",
            "paths": {
                "Windows": r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
                "Linux": "/usr/bin/docker",
                "WSL": "/usr/bin/docker",
                "MacOS": "/usr/local/bin/Docker"
            }
        }
    }

    print("\n🔍 Détection de Docker...\n")

    for name, check in docker_checks.items():
        found = False
        path_used = None

        # 1️⃣ Vérification avec la commande principale
        if run_command(check["command"]):
            found = True
            path_used = check["command"][0]

        # 2️⃣ Si échec, tenter avec `shutil.which`
        if not found and check["fallback"] and check_command_exists(check["fallback"]):
            found = True
            path_used = check["fallback"]

        # 3️⃣ Si toujours échec, essayer les chemins absolus
        if not found and os_type in check["paths"]:
            abs_path = check["paths"][os_type]
            if abs_path and os.path.exists(abs_path):
                found = True
                path_used = abs_path

        if found:
            docker[name] = path_used
            paths[name] = path_used
            print(f"{Fore.GREEN}[✔] Docker détecté : {name} ({path_used}){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[✖] Docker non trouvé : {name}{Style.RESET_ALL}")

    return docker, paths  # ✅ Retourne bien 2 valeurs

def find_hypervisors():
    """Détecte les hyperviseurs disponibles avec commandes et fallback vers chemins absolus."""
    os_type = detect_os()
    hypervisors = {}
    paths = {}

    hypervisor_checks = {
        "VirtualBox": {
            "command": ["VBoxManage", "-v"],
            "fallback": "VBoxManage",
            "paths": {
                "Windows": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe",
                "Linux": "/usr/bin/VBoxManage",
                "WSL": "/mnt/c/Program Files/Oracle/VirtualBox/VBoxManage.exe",
                "MacOS": "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
            }
        },
        "VMware": {
            "command": ["vmrun", "-v"],
            "fallback": "vmrun",
            "paths": {
                "Windows": "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe",
                "Linux": "/usr/bin/vmrun",
                "WSL": "/mnt/c/Program Files (x86)/VMware/VMware Workstation/vmrun.exe",
                "MacOS": "/Applications/VMware Fusion.app/Contents/Library/vmrun"
            }
        },
        "QEMU": {
            "command": ["qemu-system-x86_64", "--version"],
            "fallback": "qemu-system-x86_64",
            "paths": {
                "Windows": "C:\\Program Files\\qemu\\qemu-system-x86_64.exe",
                "Linux": "/usr/bin/qemu-system-x86_64",
                "WSL": "/mnt/c/msys64/ucrt64/bin/qemu-system-x86_64.exe",
                "MacOS": "/usr/local/bin/qemu-system-x86_64"
            }
        },
        "Hyper-V": {
            "command": ["powershell.exe", "Get-WindowsOptionalFeature", "-FeatureName", "Microsoft-Hyper-V-All"],
            "fallback": None,
            "paths": {}
        }
    }

    print("\n🔍 Détection des hyperviseurs...\n")

    for name, check in hypervisor_checks.items():
        found = False
        path_used = None

        # 1️⃣ Vérification avec la commande principale
        if run_command(check["command"]):
            found = True
            path_used = check["command"][0]

        # 2️⃣ Si échec, tenter avec `shutil.which`
        if not found and check["fallback"] and check_command_exists(check["fallback"]):
            found = True
            path_used = check["fallback"]

        # 3️⃣ Si toujours échec, essayer les chemins absolus
        if not found and os_type in check["paths"]:
            abs_path = check["paths"][os_type]
            if abs_path and os.path.exists(abs_path):
                found = True
                path_used = abs_path

        if found:
            hypervisors[name] = path_used
            paths[name] = path_used
            print(f"{Fore.GREEN}[✔] Hyperviseur détecté : {name} ({path_used}){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[✖] Hyperviseur non trouvé : {name}{Style.RESET_ALL}")

    return hypervisors, paths  # ✅ Retourne bien 2 valeurs

if __name__ == "__main__":
    detected_os = detect_os()
    print(f"{Fore.CYAN}🌍 OS détecté : {detected_os}{Style.RESET_ALL}")
    
    hypervisors = find_hypervisors()
    
    print(f"\n🔍 Hyperviseurs détectés : {Fore.YELLOW}{list(hypervisors.keys())}{Style.RESET_ALL}")
