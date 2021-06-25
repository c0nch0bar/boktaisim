#!/usr/bin/var python
# -*- coding: utf-8 -*-

import sys
#import ez_setup
#ez_setup.use_setuptools()
from setuptools import setup
from glob import glob


def readme():
    with open('README.rst') as f:
        return f.read()


try:
    from boktaisim.version import __version__
except ImportError:
    pass

exec(open('boktaisim/version.py').read())

if sys.platform == 'darwin':
    extra_options = dict(
         setup_requires=['py2app'],
         app=['boktaisim.py'],
         # Cross-platform applications generally expect sys.argv to
         # be used for opening files.
         options=dict(
             py2app=dict(
                 argv_emulation=False,
                 iconfile='boktaisim/resources/Solar_Sensor_Icon.icns'
             )
         ),
    )
elif sys.platform == 'win32':
    extra_options = dict(
         setup_requires=['py2exe'],
         app=['boktaisim.py']
    )
else:
    extra_options = dict(
         # Normally unix-like platforms will use "setup.py install"
         # and install the main script as such
         scripts=['boktaisim.py'],
    )

data_file_paths = glob('resources/*.wav')
data_file_paths.extend(glob('resources/*.gif'))
data_file_paths.extend(glob('resources/*.csv'))
data_file_paths.extend(glob('resources/*.db'))
DATA_FILES = [
    ('resources', data_file_paths),
]

setup(
    name='boktaisim',
    version=__version__,
    description='Stiles\' Solar Simulator for the Boktai Trilogy',
    long_description=readme(),
    long_description_content_type='text/x-rst',
    author='c0nch0b4r',
    author_email='lp1.on.fire@gmail.com',
    packages=[
        'boktaisim'
    ],
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],
    keywords='gaming',
    url='https://bitbucket.org/c0nch0b4r/boktaisim',
    download_url='https://bitbucket.org/c0nch0b4r/boktaisim/get/' + __version__ + '.tar.gz',
    project_urls={
        'Source': 'https://bitbucket.org/c0nch0b4r/boktaisim/src'
    },
    python_requires='>=3.6, <4',
    install_requires=[
        'typing',
        'requests',
        'pyzipcode',
        'appdirs',
        'simpleaudio'
    ],
    entry_points={
        'console_scripts': ['boktaisim=boktaisim.boktaisim:main'],
    },
    include_package_data=True,
    package_data={'': ['resources/*.gif', 'resources/*.wav', 'resources/*.csv', 'resources/*.db']},
    data_files=DATA_FILES,
    **extra_options
)
