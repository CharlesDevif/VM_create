import pytest
import os
import subprocess
import requests
from unittest.mock import MagicMock

import utils

@pytest.fixture
def mock_iso_folder(tmp_path):
    """Crée un dossier temporaire 'isos/' pour tester list_local_isos()."""
    iso_folder = tmp_path / "isos"
    iso_folder.mkdir()
    (iso_folder / "test.iso").touch()  # Crée un fichier ISO factice
    return iso_folder

# ✅ Test de get_available_memory()
def test_get_available_memory(mocker):
    """Test que get_available_memory() retourne une valeur positive."""
    mocker.patch("psutil.virtual_memory", return_value=MagicMock(available=8 * 1024 * 1024 * 1024))  # Simule 8GB libres
    assert utils.get_available_memory() == 8192  # Converti en Mo

# ✅ Test de choose_from_list()
def test_choose_from_list(mocker):
    """Test que choose_from_list() retourne bien la sélection correcte."""
    mocker.patch("builtins.input", return_value="2")  # Simule l'utilisateur choisissant "2"
    options = ["Option1", "Option2", "Option3"]
    assert utils.choose_from_list("Choisissez une option", options) == "Option2"

# ✅ Test de prompt_input()
def test_prompt_input_with_default(mocker):
    """Test que prompt_input() retourne bien la valeur par défaut si l'utilisateur appuie sur Entrée."""
    mocker.patch("builtins.input", return_value="")
    assert utils.prompt_input("Entrez une valeur", default="ValeurParDéfaut") == "ValeurParDéfaut"

def test_prompt_input_required(mocker):
    """Test que prompt_input() redemande l'entrée si elle est obligatoire."""
    mocker.patch("builtins.input", side_effect=["", "ValidInput"])  # Premier input vide, deuxième correct
    assert utils.prompt_input("Entrez une valeur", required=True) == "ValidInput"

# ✅ Test de create_qcow2_disk()
def test_create_qcow2_disk_success(mocker):
    """Test que create_qcow2_disk() appelle bien la commande qemu-img et retourne le chemin."""
    mock_run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    result = utils.create_qcow2_disk("test_vm")
    assert result == "test_vm.qcow2"
    mock_run.assert_called_once_with(["qemu-img", "create", "-f", "qcow2", "test_vm.qcow2", "10G"], check=True)


# ✅ Test de convert_disk_format()
def test_convert_disk_format_success(mocker):
    """Test que convert_disk_format() appelle la bonne commande."""
    mock_run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    result = utils.convert_disk_format("source.qcow2", "target.vdi", "vdi")
    assert result == "target.vdi"
    mock_run.assert_called_once_with(["qemu-img", "convert", "-O", "vdi", "source.qcow2", "target.vdi"], check=True)

def test_convert_disk_format_fail(mocker):
    """Test que convert_disk_format() retourne None si la conversion échoue."""
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "qemu-img"))
    result = utils.convert_disk_format("source.qcow2", "target.vdi", "vdi")
    assert result is None

# ✅ Test de list_local_isos()
def test_list_local_isos(mocker, mock_iso_folder):
    """Test que list_local_isos() retourne bien les fichiers ISO présents."""
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.listdir", return_value=["test.iso"])
    assert utils.list_local_isos() == ["test.iso"]

# ✅ Test de download_iso()
def test_download_iso_success(mocker, tmp_path):
    """Test que download_iso() télécharge bien un fichier."""
    mock_response = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b"data"])
    mock_response.raise_for_status = MagicMock()
    mocker.patch("requests.get", return_value=mock_response)

    iso_path = tmp_path / "debian.iso"
    mocker.patch("os.path.join", return_value=str(iso_path))

    result = utils.download_iso("http://fake-url/debian.iso")
    assert result == str(iso_path)
    mock_response.iter_content.assert_called()



# ✅ Test de vm_exists()
def test_vm_exists_virtualbox(mocker):
    """Test que vm_exists() détecte bien une VM VirtualBox existante."""
    mocker.patch("subprocess.run", return_value=MagicMock(stdout='"TestVM" {UUID}'))
    paths = {"VirtualBox": "/fake/path/VBoxManage"}
    assert utils.vm_exists("VirtualBox", "TestVM", paths) is True


def test_vm_exists_vmware(mocker):
    """Test que vm_exists() détecte une VM VMware existante."""
    mocker.patch("subprocess.run", return_value=MagicMock(stdout="TestVM"))
    paths = {"VMware": "/fake/path/vmrun"}
    assert utils.vm_exists("VMware", "TestVM", paths) is True



def test_vm_exists_hyper_v(mocker):
    """Test que vm_exists() détecte une VM Hyper-V existante."""
    mocker.patch("subprocess.run", return_value=MagicMock(stdout="TestVM"))
    paths = {"Hyper-V": "powershell.exe"}
    assert utils.vm_exists("Hyper-V", "TestVM", paths) is True

