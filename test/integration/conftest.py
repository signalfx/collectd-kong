from shutil import copyfile, rmtree
from subprocess import check_call
from tempfile import mkdtemp
from textwrap import dedent
from io import BytesIO
import sys
import os

from collectdtesting.containers import get_docker_client
from docker.errors import APIError
import pytest


def absjoin(f, relative_path):
    return os.path.abspath(os.path.join(os.path.dirname(f), relative_path))


@pytest.fixture(scope='session')
def collectd_kong():
    try:
        pkgs = absjoin(__file__, '../../requirements.txt')
        kong = absjoin(__file__, '../../')
        plugin = absjoin(__file__, '../../kong_plugin.py')
        tgt = mkdtemp()
        check_call([sys.executable, '-m', 'pip', 'install', '--upgrade',
                    '--target', tgt, kong])
        check_call([sys.executable, '-m', 'pip', 'install', '--upgrade',
                    '--target', tgt + '/kong', '-r', pkgs])
        copyfile(plugin, tgt + '/kong_plugin.py')
        yield tgt
    finally:
        rmtree(tgt)


@pytest.fixture(scope='session',
                params=(('1.0-centos', 38), ('0.15-centos', 38), ('0.14-centos', 38),
                        ('0.13-centos', 38), ('0.12-centos', 35), ('0.11', 34)),
                ids=('10', '015', '014', '013', '012', '011'))
def kong_image_and_version(request):
    version, shared_dict_line_number = request.param
    dockerfile = BytesIO(bytes(dedent(r'''
        from kong:{version}
        RUN yum install -y epel-release
        RUN yum install -y python-pip postgresql
        RUN pip install cqlsh
        WORKDIR /usr/local/share/lua/5.1/kong
        RUN sed -i '{line_num}ilua_shared_dict kong_signalfx_aggregation 10m;' templates/nginx_kong.lua
        RUN sed -i '{line_num}ilua_shared_dict kong_signalfx_locks 100k;' templates/nginx_kong.lua
        RUN sed -i '29i\ \ "signalfx",' constants.lua
        WORKDIR /
        RUN mkdir -p /usr/local/kong/logs
        RUN ln -s /dev/stderr /usr/local/kong/logs/error.log
        RUN ln -s /dev/stdout /usr/local/kong/logs/access.log
    '''.format(version=version, line_num=shared_dict_line_number)), 'ascii'))
    client = get_docker_client()
    image, _ = client.images.build(fileobj=dockerfile, forcerm=True)
    try:
        yield image.short_id, version
    finally:
        try:
            client.images.remove(image=image.id, force=True)
        except APIError as exc:
            # conflict errors must be resolved manually
            if exc.status_code != 409:
                raise
