import pytest
import subprocess
import logging
from vm_manager import create_vm
from utils import vm_exists, create_qcow2_disk, convert_disk_format

@pytest.fixture
def mock_paths():
    """Simule les chemins des hyperviseurs."""
    return {
        "VirtualBox": "/fake/path/VBoxManage",
        "VMware": "/fake/path/vmrun",
        "QEMU": "/fake/path/qemu-system-x86_64"
    }

def test_create_vm_normal(mocker, mock_paths):
    """✅ Teste la création d'une VM sans problème."""
    mocker.patch("utils.vm_exists", return_value=False)
    mocker.patch("utils.create_qcow2_disk", return_value="test.qcow2")
    mocker.patch("utils.convert_disk_format", return_value="test.vdi")
    mock_run = mocker.patch("subprocess.run")

    create_vm("VirtualBox", "TestVM", "x86_64", 2048, "/fake/path/debian.iso", mock_paths, dry_run=False)

    mock_run.assert_called()
    assert mock_run.call_count > 2  # Vérifie qu'au moins 2 commandes ont été exécutées
