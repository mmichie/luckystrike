from distutils.core import setup
import luckystrike

setup(
    name='luckystrike',
    author='Matt Michie',
    maintainer_email='mmichie@gmail.com',
    version=luckystrike.version,
    url='https://github.com/mmichie/luckystrike',
    license='The MIT License (MIT)',
    description='IRC to Campfire Bridge',
    long_description=open('README.md').read(),
    packages=['luckystrike'],
    scripts=['lstrike.py'],
    classifiers=[
        'Topic :: Communications :: Chat :: Internet Relay Chat',
        'Programming Language :: Python :: 2.7',
        'License :: OSI Approved :: MIT License',
    ],
    install_requires=[
        'pinder >= 1.0',
        'twisted >= 13.2.0',
        'pycrypto >= 2.6.1',
        'pyopenssl >= 0.14',
        'pyasn1 >= 0.1.7',
    ],
)