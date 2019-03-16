import sys
import os
import tarfile
import json
from subprocess import call
from splunk.rest import simpleRequest
from splunk import Intersplunk
import requests
import re
from splunk_logger import setup_logging
import shutil
from utils import load_pyden_config, write_pyden_config


def download_python(version, build_path):
    base_url = simpleRequest("/servicesNS/nobody/pyden-manager/properties/pyden/download/url",
                             sessionKey=session_key)[1]
    try:
        dpr = requests.get(base_url + "{0}/".format(version))
    except Exception as ex:
        Intersplunk.generateErrorResults("Exception thrown getting python: ({0}, {1})".format(type(ex), ex))
        sys.exit(1)
    else:
        if dpr.status_code in range(200, 300):
            python_link = [link for link in re.findall("href=\"(.*?)\"", dpr.content) if link.endswith('tgz')][0]
            dpr = requests.get(base_url + "{0}/{1}".format(version, python_link))
        else:
            Intersplunk.generateErrorResults(
                "Failed to reach www.python.org. Request returned - Status code: {0}, Response: {1}".format(
                    dpr.status_code, dpr.text))
            sys.exit(1)
    if dpr.status_code in range(200, 300):
        # save
        build_file = os.path.join(build_path, "Python-{0}.tgz".format(version))
        with open(build_file, "w") as download:
            download.write(dpr.content)
    else:
        Intersplunk.generateErrorResults(
            "Failed to download python. Request returned - Status code: {0}, Response: {1}".format(dpr.status_code,
                                                                                                   dpr.text))
        sys.exit(1)
    return build_file


def build_dist(version, download):
    pyden_location, config = load_pyden_config()
    if version in config.sections():
        Intersplunk.generateErrorResults("Version already exists.")
        sys.exit(1)
    sys.stdout.write("messages\n")
    sys.stdout.flush()
    build_path = os.path.join(os.getcwd(), 'build')
    if not os.path.isdir(build_path):
        os.mkdir(build_path)
    if download is True:
        logger.debug("Downloading Python")
        build_file = download_python(version, build_path)
    else:
        logger.debug("Using existing archive")
        build_file = os.path.join(build_path, download)

    # unpack
    if os.path.isdir(build_file[:-4]):
        shutil.rmtree(build_file[:-4], ignore_errors=True)
    os.chdir(build_path)
    list_before_extraction = os.listdir(os.getcwd())
    logger.debug("Extracting archive")
    with tarfile.open(build_file, "r:gz") as tarball:
        tarball.extractall()
    list_after_extraction = os.listdir(os.getcwd())
    extracted_members = [member for member in list_after_extraction if member not in list_before_extraction]
    if len(extracted_members) == 1:
        extracted_member = extracted_members[0]
    else:
        Intersplunk.generateErrorResults("Archive contained more than one item. Please use archive with single member.")
        sys.exit(1)

    # configure and build
    pyden_prefix = os.path.join(pyden_location, 'local', 'lib', 'dist', version)
    if not os.path.isdir(pyden_prefix):
        os.makedirs(pyden_prefix)
    os.chdir(os.path.join(os.getcwd(), extracted_member))
    optimize_conf = simpleRequest("/servicesNS/nobody/pyden-manager/properties/pyden/app/optimize",
                                  sessionKey=session_key)[1]
    optimize = '--enable-optimizations' if optimize_conf in ['true', 'True', '1'] else ''
    logger.debug("Configuring source")
    call([os.path.join(os.curdir, 'configure'),
          optimize,
          '--with-ensurepip=install',
          '--prefix={0}'.format(pyden_prefix)])
    logger.debug("Making")
    call(['make'])
    logger.debug("Make install")
    call(['make', 'altinstall'])

    logger.debug("Determining binary of %s" % pyden_prefix)
    bin_dir = os.path.join(pyden_prefix, 'bin')
    os.chdir(bin_dir)
    largest_size = 0
    py_exec = ""
    bins = os.listdir(bin_dir)
    for binary in bins:
        bin_size = os.path.getsize(binary)
        if bin_size > largest_size:
            py_exec = os.path.join(bin_dir, binary)
            largest_size = bin_size
    logger.debug("Found binary: %s" % py_exec)

    # Running get-pip and others
    logger.debug("Upgrading pip")
    call([py_exec, '-m', 'pip', 'install', '--upgrade', 'pip'])
    call([py_exec, '-m', 'pip', 'install', 'virtualenv'])
    logger.info("Finished building Python %s. Distribution available at %s." % (version, pyden_prefix))

    write_pyden_config(pyden_location, config, version, "executable", py_exec.lstrip(os.environ['SPLUNK_HOME']))
    if not config.has_section("default-pys") or not config.has_option("default-pys", "distribution"):
        write_pyden_config(pyden_location, config, 'default-pys', 'distribution', version)
    return


if __name__ == "__main__":
    logger = setup_logging()
    download_arg = True
    settings = dict()
    Intersplunk.readResults(settings=settings)
    session_key = settings['sessionKey']
    latest_python_search = r"""
    | getversions 
    | rex field=version "(?<v_M>\d+)\.(?<v_m>\d+)\.(?<v_mm>\d+)" 
    | eval v_M=tonumber(v_M), v_m=tonumber(v_m), v_mm=tonumber(v_mm) 
    | sort -v_M, -v_m, -v_mm 
    | table version 
    | head 1
    """
    try:
        r = simpleRequest("/servicesNS/nobody/pyden-manager/search/jobs",
                          postargs={'search': latest_python_search, 'exec_mode': 'oneshot', 'output_mode': 'json'},
                          sessionKey=session_key)
        dist_version = json.loads(r[1])['results'][0]['version']
    except Exception as e:
        Intersplunk.generateErrorResults("Failed to find latest version of Python: %s." % e)
        sys.exit(1)
    for arg in sys.argv:
        if "version" in arg:
            dist_version = arg.split("=")[1]
        if "download" in arg:
            download_arg = arg.split("=")[1]
    logger.info("Creating Python distribution version %s" % dist_version)
    build_dist(dist_version, download_arg)
