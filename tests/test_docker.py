import pytest
import subprocess
from utils import is_docker_installed, create_docker_container

@pytest.mark.parametrize("docker_installed, expected", [
    (0, True),  # Code de retour 0 = Docker fonctionne
])
def test_is_docker_installed(mocker, docker_installed, expected):
    """✅ Teste si Docker est installé et en cours d'exécution."""
    mock_run = mocker.patch("subprocess.run")

    # Simule `docker --version` et `docker info`
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
    mock_run.assert_any_call(["docker", "rm", "-f", "test-container"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Vérifie que le conteneur est bien lancé
    mock_run.assert_any_call(
        ["docker", "run", "-dit", "--name", "test-container", "ubuntu:latest", "sh", "-c", "bash"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def test_create_docker_container_with_volume(mocker):
    """✅ Teste la création d'un conteneur Docker avec un volume."""
    mock_run = mocker.patch("subprocess.run")

    create_docker_container("test-container", "ubuntu:latest", "test-volume")

    # Vérification de la suppression de l'ancien conteneur
    mock_run.assert_any_call(["docker", "rm", "-f", "test-container"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Vérifie que le conteneur est bien lancé avec un volume
    mock_run.assert_any_call(
        ["docker", "run", "-dit", "--name", "test-container", "-v", "test-volume:/data", "ubuntu:latest", "sh", "-c", "bash"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def test_create_docker_container_with_ports(mocker):
    """✅ Teste la création d'un conteneur Docker avec des ports exposés."""
    mock_run = mocker.patch("subprocess.run")

    ports = {"8080": "80", "2222": "22"}
    create_docker_container("test-container", "ubuntu:latest", "", ports=ports)

    # Vérification de la suppression de l'ancien conteneur
    mock_run.assert_any_call(["docker", "rm", "-f", "test-container"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Vérifie que le conteneur est bien lancé avec les ports exposés
    mock_run.assert_any_call(
        ["docker", "run", "-dit", "--name", "test-container", "-p", "8080:80", "-p", "2222:22", "ubuntu:latest", "sh", "-c", "bash"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def test_create_docker_container_with_env_vars(mocker):
    """✅ Teste la création d'un conteneur Docker avec des variables d'environnement."""
    mock_run = mocker.patch("subprocess.run")

    env_vars = {"MY_VAR": "value", "DEBUG": "true"}
    create_docker_container("test-container", "ubuntu:latest", "", env_vars=env_vars)

    # Vérification de la suppression de l'ancien conteneur
    mock_run.assert_any_call(["docker", "rm", "-f", "test-container"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Vérifie que le conteneur est bien lancé avec les variables d'environnement
    mock_run.assert_any_call(
        ["docker", "run", "-dit", "--name", "test-container", "-e", "MY_VAR=value", "-e", "DEBUG=true", "ubuntu:latest", "sh", "-c", "bash"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def test_create_docker_container_with_custom_command(mocker):
    """✅ Teste la création d'un conteneur Docker avec une commande personnalisée."""
    mock_run = mocker.patch("subprocess.run")

    create_docker_container("test-container", "ubuntu:latest", "", command="nginx -g 'daemon off;'")

    # Vérification de la suppression de l'ancien conteneur
    mock_run.assert_any_call(["docker", "rm", "-f", "test-container"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Vérifie que le conteneur est bien lancé avec la commande personnalisée
    mock_run.assert_any_call(
        ["docker", "run", "-dit", "--name", "test-container", "ubuntu:latest", "sh", "-c", "nginx -g 'daemon off;'"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
