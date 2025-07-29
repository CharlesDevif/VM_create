import platform
import subprocess
import logging
import psutil

def detect_bridgeable_interface():
    os_type = platform.system()
    
    if os_type == "Linux":
        blacklist = ("lo", "docker", "virbr", "veth", "br-", "wl", "vmnet", "tap", "tun")
        interfaces = psutil.net_if_stats()
        for name, stats in interfaces.items():
            if stats.isup and not name.startswith(blacklist):
                return name

    elif os_type == "Windows" or "microsoft" in platform.release().lower() or "WSL" in platform.platform():
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-Command",
                    r"Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.HardwareInterface -eq $true } | Select-Object -ExpandProperty Name"
                ],
                capture_output=True,
                text=True,
                timeout=5
            )
            interfaces = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
            for iface in interfaces:
                if not any(bad in iface.lower() for bad in ["virtual", "loopback", "vmware", "hyper-v", "host-only"]):
                    return iface
        except Exception as e:
            logging.warning(f"⚠️ Impossible de détecter une interface Windows bridgeable : {e}")
            return None

    elif os_type == "Darwin":
        try:
            result = subprocess.run(["networksetup", "-listallhardwareports"], capture_output=True, text=True)
            blocks = result.stdout.split("Hardware Port:")
            for block in blocks[1:]:
                if "Device" in block and "Wi-Fi" in block:
                    lines = block.strip().splitlines()
                    for line in lines:
                        if "Device" in line:
                            return line.split(":")[1].strip()
        except Exception as e:
            logging.warning(f"⚠️ Impossible de détecter une interface macOS bridgeable : {e}")
            return None

    return None

def create_tap_interface(tap_name="tap0", bridge_name="br0"):
    try:
        result = subprocess.run(["ip", "link", "show", tap_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            print(f"⚠️ L'interface {tap_name} existe déjà, utilisation directe.")
            return tap_name

        subprocess.run(["sudo", "ip", "tuntap", "add", "dev", tap_name, "mode", "tap"], check=True)
        subprocess.run(["sudo", "ip", "link", "set", tap_name, "up"], check=True)
        subprocess.run(["sudo", "ip", "link", "set", tap_name, "master", bridge_name], check=True)
        return tap_name

    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de la création de l'interface TAP : {e}")
        return None