from setuptools import setup, find_packages
import versioneer


setup(
    name='buildmatrix',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author='Eric Dill',
    author_email='thedizzle@gmail.com',
    packages=find_packages(exclude="test"),
    description='Build a matrix of conda packages',
    url='http://github.com/ericdill/buildmatrix',
    platforms='Cross platform (Linux, Mac OSX, Windows)',
    license='BSD 3-Clause',
    entry_points={"console_scripts": ['buildmatrix = buildmatrix.cli:cli',
                                      'bm = buildmatrix.cli:cli']},
)
