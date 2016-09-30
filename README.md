# buildmatrix

[![Build Status](https://travis-ci.org/ericdill/buildmatrix.svg?branch=master)](https://travis-ci.org/ericdill/buildmatrix)
[![codecov](https://codecov.io/gh/ericdill/buildmatrix/branch/master/graph/badge.svg)](https://codecov.io/gh/ericdill/buildmatrix)
[![PyPI version](https://badge.fury.io/py/buildmatrix.svg)](https://badge.fury.io/py/buildmatrix)

buildmatrix is a thin wrapper around conda-build that does four things:

1. Build conda packages for the outer product of python versions and 
   numpy versions with one command line invocation. 
   
2. Compare against a channel on an anaconda server (defaults to 
   anaconda.org/anaconda) and only build the packages that do not 
   already exist

3. Build conda packages from git source in addition to tarballs. This 
   is the primary difference between this tool and 
   [conda-build-all](https://github.com/SciTools/conda-build-all).  
   You can use the conda GIT_* variables in your conda recipes and 
   `buildmatrix` will go and clone the git repo and evaluate the GIT_* 
   variables when determining if it should build the package or not 
   (the second point above)

4. If you point buildmatrix at a folder full of conda recipes, it will
   examine all of the build/run/test time dependencies that are found in
   all of the recipes and build a dependency graph.  The build order
   will then be determined by starting with the recipes that are not
   dependent on other recipes that are slated to be built.

## Usage

`buildmatrix` depends on conda and conda_build.  You can pip install
buildmatrix and it will add the `buildmatrix` command line app and its
alias `bm` for those of you that abhor typing more than is absolutely 
necessary

### Most usage will look like this:

`buildmatrix /path/to/recipe --python 2.7 3.4 3.5 --numpy 1.10 1.11`

The above command will produce one of two things depending on if your package
depends on a numpy version at build time (e.g., numpy x.x is a build requirement)
   
   
If your package depends on numpy at build time:

- python 2.7 and numpy 1.10
- python 3.4 and numpy 1.10
- python 3.5 and numpy 1.10
- python 2.7 and numpy 1.11
- python 3.4 and numpy 1.11
- python 3.5 and numpy 1.11

If your package does not depend on numpy at build time:

- python 2.7 and numpy 1.11
- python 3.4 and numpy 1.11
- python 3.5 and numpy 1.11

### --dry-run

`buildmatrix tests/example-recipes/ --python 2.7 3.4 3.5 --numpy 1.10 1.11 --dry-run`

    Logging summary to /tmp/buildmatrix/2016.09.30-15.19
    {'allow_failures': False, 'numpy': ['1.10', '1.11'], 'dry_run': True, 'python': ['2.7', '3.4', '3.5'], 'channel': 'anaconda', 'recipes_path': '/home/eric/dev/conda/buildmatrix/tests/example-recipes'}
    Using Anaconda API: https://api.anaconda.org
    Fetching package metadata .....
    recipes_path = /home/eric/dev/conda/buildmatrix/tests/example-recipes

    Figuring out which recipes need to build...
    True     | 2.7   | 1.11  | linux-64/package-b-1-py27_0.tar.bz2
    True     | 3.4   | 1.11  | linux-64/package-b-1-py34_0.tar.bz2
    True     | 3.5   | 1.11  | linux-64/package-b-1-py35_0.tar.bz2
    True     | 2.7   | 1.10  | linux-64/package-a-1-np110py27_0.tar.bz2
    True     | 2.7   | 1.11  | linux-64/package-a-1-np111py27_0.tar.bz2
    True     | 3.4   | 1.10  | linux-64/package-a-1-np110py34_0.tar.bz2
    True     | 3.4   | 1.11  | linux-64/package-a-1-np111py34_0.tar.bz2
    True     | 3.5   | 1.10  | linux-64/package-a-1-np110py35_0.tar.bz2
    True     | 3.5   | 1.11  | linux-64/package-a-1-np111py35_0.tar.bz2

    This is the determined build order...
    linux-64/package-a-1-np110py27_0.tar.bz2
    linux-64/package-a-1-np111py27_0.tar.bz2
    linux-64/package-a-1-np110py34_0.tar.bz2
    linux-64/package-a-1-np111py34_0.tar.bz2
    linux-64/package-a-1-np110py35_0.tar.bz2
    linux-64/package-a-1-np111py35_0.tar.bz2
    linux-64/package-b-1-py27_0.tar.bz2
    linux-64/package-b-1-py34_0.tar.bz2
    linux-64/package-b-1-py35_0.tar.bz2
    Dry run enabled. Exiting 0
    
Note a couple of things.  

1. package-a has a numpy compile-time dependency
   and so you see that it is slated to build against numpy 1.10 and numpy 1.11 along with
   the three python versions for six total.  The other package (package-b)
   has no numpy build-time dependency, so it builds against the highest numpy version listed
   in the --numpy flag
   
2. package-b depends on package-a in this contrived example.  In the 
   determined build order section you can see that package-a will be
   built before package-b. 
