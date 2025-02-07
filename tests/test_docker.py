import pytest
import subprocess
from utils import is_docker_installed, create_docker_container

@pytest.mark.parametrize("docker_installed, expected", [
    (0, True),  # Code de retour 0 = Docker fonctionne
])

def test_is_docker_installed(mocker, docker_installed, expected):
    """✅ Teste si Docker est installé et en cours d'exécution."""
    mock_run = mocker.patch("subprocess.run")
    
    # Simule que `docker --version` fonctionne toujours
    mock_run.side_effect = [
        mocker.Mock(returncode=0),  # docker --version (réussi)
        mocker.Mock(returncode=docker_installed)  # docker info (succès ou échec)
    ]

    assert is_docker_installed() == expected

    # Vérifie que `docker info` a bien été appelé
    mock_run.assert_any_call(["docker", "info"], stdout=mocker.ANY, stderr=mocker.ANY, check=True)

def test_create_docker_container_no_volume(mocker):
    """✅ Teste la création d'un conteneur Docker sans volume."""
    mock_run = mocker.patch("subprocess.run")

    create_docker_container("test-container", "ubuntu:latest", "")

    # Vérification de la suppression de l'ancien conteneur
    mock_run.assert_any_call(["docker", "rm", "-f", "test-container"], stdout=-1, stderr=-1)

    # Vérifie que le conteneur est bien lancé
    mock_run.assert_any_call(["docker", "run", "-d", "--name", "test-container", "ubuntu:latest"], stdout=-1, stderr=-1, text=True)

def test_create_docker_container_with_volume(mocker):
    """✅ Teste la création d'un conteneur Docker avec un volume."""
    mock_run = mocker.patch("subprocess.run")

    create_docker_container("test-container", "ubuntu:latest", "test-volume")

    # Vérification de la suppression de l'ancien conteneur
    mock_run.assert_any_call(["docker", "rm", "-f", "test-container"], stdout=-1, stderr=-1)

    # Vérifie que le conteneur est bien lancé 
    mock_run.assert_any_call(["docker", "run", "-d", "--name", "test-container", "-v", "test-volume:/data", "ubuntu:latest"], stdout=-1, stderr=-1, text=True)

