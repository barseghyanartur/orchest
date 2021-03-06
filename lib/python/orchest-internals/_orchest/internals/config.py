import os

# TODO: add notice that some of these values have effect on the sdk!.

# General.
TEMP_DIRECTORY_PATH = '/tmp/orchest'
TEMP_VOLUME_NAME = 'tmp-orchest-{uuid}'
PIPELINE_DIR = '/pipeline-dir'

# Relative to the `PIPELINE_DIR`.
KERNELSPECS_PATH = '.orchest/kernels'
LOGS_PATH = '.orchest/logs'
PIPELINE_DESCRIPTION_FILE = 'pipeline.json'
PIPELINE_DESCRIPTION_PATH = os.path.join('.orchest', PIPELINE_DESCRIPTION_FILE)

# Networking
ORCHEST_API_ADDRESS = 'orchest-api'

# Images
DEFAULT_BASE_IMAGES = [
    {'name': 'orchestsoftware/custom-base-kernel-py', 'language': 'python'},
    {'name': 'orchestsoftware/custom-base-kernel-r', 'language': 'r'},
]

# memory-server
MEMORY_SERVER_SOCK_PATH = TEMP_DIRECTORY_PATH
