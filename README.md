buildmatrix
-----------
[![Build Status](https://travis-ci.org/ericdill/buildmatrix.svg?branch=master)](https://travis-ci.org/ericdill/buildmatrix)
[![codecov](https://codecov.io/gh/ericdill/buildmatrix/branch/master/graph/badge.svg)](https://codecov.io/gh/ericdill/buildmatrix)
[![PyPI version](https://badge.fury.io/py/buildmatrix.svg)](https://badge.fury.io/py/buildmatrix)

buildmatrix is a thin wrapper around conda-build that does three things:

#. Build conda packages for the outer product of python versions and numpy versions with one command line
   invocation, e.g.:

    - python 2.7 and numpy 1.10
    - python 3.4 and numpy 1.10
    - python 3.5 and numpy 1.10
    - python 2.7 and numpy 1.11
    - python 3.4 and numpy 1.11
    - python 3.5 and numpy 1.11

#. Compare against a channel on an anaconda server (defaults to anaconda.org/anaconda) and only build the packages that
   do not already exist

#. Build conda packages from git source in addition to tarballs. This is the primary difference between this tool
   and [conda-build-all](https://github.com/SciTools/conda-build-all).  You can use the conda GIT_* variables
   in your conda recipes and `buildmatrix` will go and clone the git repo and evaluate the GIT_* variables
   when determining if it should build the package or not (the second point above)
