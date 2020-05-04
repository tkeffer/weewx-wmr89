#
#    Copyright (c) 2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Installer for the WMR89 driver"""

from weecfg.extension import ExtensionInstaller


def loader():
    return WMR89Installer()


class WMR89Installer(ExtensionInstaller):
    def __init__(self):
        super(WMR89Installer, self).__init__(
            version="1.0.0",
            name='wmr89',
            description='Driver for the Oregon Scientific WMR89',
            author="Thomas Keffer",
            author_email="tkeffer@gmail.com",
            files=[('bin/user', ['bin/user/wmr89.py'])]
        )
