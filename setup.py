from setuptools import setup, find_packages
from pybatterymonitor.pybatterymonitorconfig import VERSION, DESCRIPTION

setup(
    name='pybatterymonitor',
    version=VERSION,
    license='GPL3',
    author='icasdri',
    author_email='icasdri@gmail.com',
    description=DESCRIPTION,
    url='https://github.com/icasdri/pybatterymonitor',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Utilities',
        'License :: OSI Approved :: GPL License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3'
    ],
    packages=find_packages(),
    entry_points={
        'console_scripts': ['pybatterymonitor = pybatterymonitor.batterymonitor:main']
    }
)
