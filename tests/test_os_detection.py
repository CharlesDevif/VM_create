import pytest
import platform
import shutil
import subprocess
from os_detection import detect_os, check_command_exists, run_command, find_hypervisors

@pytest.mark.parametrize("mocked_system, expected", [
    ("Windows", "Windows"),
    ("Linux", "Linux"),
    ("Darwin", "MacOS"),
    ("WSL", "WSL"),
])
def test_detect_os(mocker, mocked_system, expected):
    """✅ Teste la détection du système d'exploitation."""
    mock_system = mocker.patch("platform.system", return_value=mocked_system)
    
    if mocked_system == "Linux":
        mock_open = mocker.patch("builtins.open", mocker.mock_open(read_data=""))
        if expected == "WSL":
            mock_open.return_value.read.return_value = "microsoft"

    assert detect_os() == expected

def test_detect_os_wsl(mocker):
    """✅ Teste la détection de WSL (Windows Subsystem for Linux)."""
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch("builtins.open", mocker.mock_open(read_data="microsoft"))
    assert detect_os() == "WSL"

def test_check_command_exists(mocker):
    """✅ Teste si une commande est bien trouvée avec shutil.which()."""
    mocker.patch("shutil.which", return_value="/usr/bin/qemu-system-x86_64")
    assert check_command_exists("qemu-system-x86_64") is True

    mocker.patch("shutil.which", return_value=None)
    assert check_command_exists("fake-command") is False

def test_run_command_success(mocker):
    """✅ Teste si une commande s'exécute correctement sans erreur."""
    mock_run = mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(args=["VBoxManage", "-v"], returncode=0))
    assert run_command(["VBoxManage", "-v"]) is True
    mock_run.assert_called_once_with(["VBoxManage", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def test_run_command_failure(mocker):
    """❌ Teste si une commande échoue et est bien gérée."""
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "VBoxManage"))
    assert run_command(["VBoxManage", "-v"]) is False

def test_run_command_not_found(mocker):
    """❌ Teste le cas où la commande n'existe pas (FileNotFoundError)."""
    mocker.patch("subprocess.run", side_effect=FileNotFoundError)
    assert run_command(["VBoxManage", "-v"]) is False

def test_find_hypervisors(mocker):
    """✅ Teste la détection des hyperviseurs avec simulation des commandes et chemins absolus."""
    mocker.patch("os_detection.detect_os", return_value="Linux")
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("shutil.which", return_value=None)
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(args=["VBoxManage", "-v"], returncode=0))

    hypervisors, paths = find_hypervisors()

    assert isinstance(hypervisors, dict)
    assert "VirtualBox" in hypervisors
    assert "QEMU" in hypervisors
