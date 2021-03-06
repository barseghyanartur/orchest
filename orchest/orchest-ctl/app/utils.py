import logging
import os
import sys

import docker
from docker.types import Mount

import config
from connections import docker_client


def init_logger():
    logging.basicConfig(level=logging.INFO)

    root = logging.getLogger()
    if len(root.handlers) > 0:
        h = root.handlers[0]
        root.removeHandler(h)

    formatter = logging.Formatter(logging.BASIC_FORMAT)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)


def is_install_complete():
    missing_images = check_images()

    if len(missing_images) > 0:
        logging.warning("Missing images: %s" % missing_images)
        return False

    try:
        docker_client.networks.get(config.DOCKER_NETWORK)
    except docker.errors.NotFound as e:
        logging.warning("Docker network (%s) "
                        "not installed: %s" % (config.DOCKER_NETWORK, e))
        return False

    return True


def check_images():
    missing_images = []

    for image in config.ALL_IMAGES:
        try:
            docker_client.images.get(image)
            # logging.info("Image `%s` is installed." % image)
        except docker.errors.ImageNotFound:
            missing_images.append(image)
        except docker.errors.APIError as e:
            raise e

    return missing_images


def install_images():
    for image in config.ALL_IMAGES:
        try:
            docker_client.images.get(image)
        except docker.errors.ImageNotFound:
            logging.info("Pulling image `%s` ..." % image)
            docker_client.images.pull(image)
            logging.info("Pulled image `%s`." % image)


def install_network():
    try:
        docker_client.networks.get(config.DOCKER_NETWORK)
    except docker.errors.NotFound as e:

        logging.info("Orchest sends an anonymized ping to analytics.orchest.io. "
                     "You can disable this by adding "
                     "{ \"TELEMETRY_DISABLED\": true }"
                     "to config.json in %s" % config.HOST_CONFIG_DIR)

        logging.info("Docker network %s doesn't exist: %s. "
                     "Creating it." % (config.DOCKER_NETWORK, e))
        # Create Docker network named "orchest" with a custom subnet such that
        # containers can be spawned at custom static IP addresses.
        ipam_pool = docker.types.IPAMPool(subnet='172.31.0.0/16')
        ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
        docker_client.networks.create(
            config.DOCKER_NETWORK,
            driver="bridge",
            ipam=ipam_config
        )


def log_server_url():
    orchest_url = get_application_url()
    if len(orchest_url) > 0:
        logging.info("Orchest is running at: %s" % orchest_url)
    else:
        logging.warning("Orchest is not running.")


def clean_containers():
    running_containers = docker_client.containers.list(all=True)

    for container in running_containers:
        has_tags = len(container.image.tags) > 0
        is_orchest_image = has_tags and container.image.tags[0] in config.ALL_IMAGES
        has_exited = container.status == "exited"
        if is_orchest_image and has_exited:
            logging.info("Removing exited container `%s`" % container.name)
            container.remove()


def get_application_url():
    try:
        docker_client.containers.get("orchest-webserver")
    except Exception as e:
        print(e)
        return ""

    port = config.CONTAINER_MAPPING["orchestsoftware/nginx-proxy:latest"]["ports"]["80/tcp"]
    return "http://localhost:%i" % port


def dev_mount_inject(container_spec):
    """Injects mounts to run Orchest in DEV mode.

    The code is mounted at the correct locations inside the containers,
    so that you changes you make to the code are directly reflected in
    the application.

    """
    HOST_PWD = os.environ.get("HOST_PWD")

    # orchest-webserver
    orchest_webserver_spec = container_spec["orchestsoftware/orchest-webserver:latest"]
    orchest_webserver_spec['mounts'] += [
        {
            "source": os.path.join(HOST_PWD, "orchest", "orchest-webserver", "app"),
            "target": "/orchest/orchest/orchest-webserver/app"
        },
        # Internal library.
        {
            "source": os.path.join(HOST_PWD, "lib"),
            "target": "/orchest/lib"
        },
    ]

    orchest_webserver_spec['environment']["FLASK_ENV"] = "development"
    orchest_webserver_spec['command'] = [
       "./debug.sh"
    ]

    # auth-server
    orchest_auth_server_spec = container_spec["orchestsoftware/auth-server:latest"]
    orchest_auth_server_spec['mounts'] += [
        {
            "source": os.path.join(HOST_PWD, "orchest", "auth-server", "app"),
            "target": "/orchest/orchest/auth-server/app"
        }
    ]

    orchest_auth_server_spec['environment']["FLASK_APP"] = "main.py"
    orchest_auth_server_spec['environment']["FLASK_DEBUG"] = "1"
    orchest_auth_server_spec['command'] = [
       "flask",
       "run",
       "--host=0.0.0.0",
       "--port=80"
    ]

    # orchest-api
    orchest_api_spec = container_spec["orchestsoftware/orchest-api:latest"]
    orchest_api_spec["mounts"] += [
        {
            "source": os.path.join(HOST_PWD, "orchest", "orchest-api", "app"),
            "target": "/orchest/orchest/orchest-api/app"
        },
        # Internal library.
        {
            "source": os.path.join(HOST_PWD, "lib"),
            "target": "/orchest/lib"
        },
    ]
    # Forward the port so that the Swagger API can be accessed at :8080/api
    orchest_api_spec["ports"] = {
        "80/tcp": 8080
    }
    orchest_api_spec["environment"]["FLASK_APP"] = "main.py"
    orchest_api_spec["environment"]["FLASK_ENV"] = "development"
    orchest_api_spec["command"] = [
       "flask",
       "run",
       "--host=0.0.0.0",
       "--port=80"
    ]

    # nginx-proxy
    nginx_proxy_spec = container_spec["orchestsoftware/nginx-proxy:latest"]
    nginx_proxy_spec['ports'] = {
        "80/tcp": 80,
        "443/tcp": 443
    }


def convert_to_run_config(image_name, container_spec):
    # Convert every mount specification to a docker.types.Mount
    mounts = []
    for ms in container_spec.get('mounts', []):
        mount = Mount(target=ms['target'], source=ms['source'], type='bind')
        mounts.append(mount)

    run_config = {
        'image': image_name,
        'command': container_spec.get('command'),
        'name': container_spec['name'],
        'detach': True,
        'mounts': mounts,
        'network': config.DOCKER_NETWORK,
        'environment': container_spec.get('environment', {}),
        'ports': container_spec.get('ports', {}),
        'hostname': container_spec.get('hostname'),
    }
    return run_config
