from setuptools import setup, find_packages

setup(
    name='pybatterymonitor',
    version='0.1',
    license='GPL3',
    author='icasdri',
    author_email='icasdri@gmail.com',
    description='A small user daemon for GNU/Linux that monitors battery levels and notifies users',
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
        'console_scripts': ['pybatterymonitor = pybatterymonitor.pybatterymonitor:main']
    }
)
