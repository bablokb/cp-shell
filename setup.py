# -------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Local setup configuration.
# Run
#      pip3 install .
#
# to install.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# -------------------------------------------------------------------------

import os
from setuptools import setup

import sys
if sys.version_info < (3,4):
    print('cpshell requires Python 3.4 or newer.')
    sys.exit(1)

from cpshell.version import __version__

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name = 'cpshell',
    version = __version__,
    author = 'Bernhard Bablok',
    author_email = 'cpshell@noreply.github.com',
    description = ('A remote shell for working with CircuitPython boards.'),
    license = 'MIT',
    keywords = 'circuitpython shell',
    url = 'https://github.com/bablokb/cp-shell',
    download_url = 'https://github.com/bablokb/cp-shell',
    packages=['cpshell', 'cpshell/commands'],
    long_description=long_description,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Embedded Systems',
        'Topic :: System :: Shells',
        'Topic :: Terminals :: Serial',
        'Topic :: Utilities',
    ],
    install_requires=[
        'pyserial',
        'pyudev >= 0.16',
    ],
    entry_points = {
        'console_scripts': [
            'cpshell=cpshell.main:main'
        ],
    },
    extras_require={
        ':sys_platform == "win32"': [
            'pyreadline']
    }
)
