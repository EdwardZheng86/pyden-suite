import sys
import os
from utils import load_pyden_config
import shutil


if __name__ == "__main__":
    pm_config, config = load_pyden_config()
    pyden_location = pm_config.get('appsettings', 'location')
    local_conf = os.path.join(pyden_location, 'local', 'pyden.conf')
    local_dir = os.path.dirname(local_conf)
    name = sys.argv[1]
    if name not in config.sections():
        sys.exit(1)
    pytype = False
    dist_dir = os.path.join(local_dir, 'lib', 'dist')
    venv_dir = os.path.join(local_dir, 'lib', 'venv')
    if name in os.listdir(dist_dir):
        pytype = "dist"
    if name in os.listdir(venv_dir):
        pytype = "venv"
    if not pytype:
        sys.exit(1)
    config.remove_section(name)
    if not os.path.isdir(local_dir):
        os.mkdir(local_dir)
    with open(local_conf, 'w+') as configfile:
        config.write(configfile)
    shutil.rmtree(os.path.join(local_dir, 'lib', pytype, name))
