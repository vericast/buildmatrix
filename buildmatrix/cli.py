# Copyright (c) <2015-2016>, Eric Dill
#
# All rights reserved.  Redistribution and use in source and binary forms, with
# or without modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
CLI to build a folder full of recipes.

Example usage:

buildmatrix /folder/of/recipes --python 2.7 3.4 3.5 --numpy 1.10 1.11 -c some_conda_channel

buildmatrix --help
"""
import json
import itertools
import logging
import os
import pdb
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from argparse import ArgumentParser
from contextlib import contextmanager
from pprint import pformat

from conda.api import get_index
from conda_build.metadata import MetaData

logger = logging.getLogger('build.py')
current_subprocs = set()
shutdown = False

DEFAULT_PY = '3.5'
DEFAULT_NP_VER = '1.11'


@contextmanager
def env_var(key, value):
    old_val = os.environ.get(key)
    os.environ[key] = value
    yield
    if old_val:
        os.environ[key] = old_val
    else:
        del os.environ[key]


def handle_signal(signum, frame):
    # send signal recieved to subprocesses
    global shutdown
    shutdown = True
    for proc in current_subprocs:
        if proc.poll() is None:
            proc.send_signal(signum)
    print("Killing build script due to receiving signum={}"
          "".format(signum))
    sys.exit(1)


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def get_file_names_on_anaconda_channel(channel):
    """Get the names of **all** the files on a channel

    Parameters
    ----------
    channel : str

    Returns
    -------
    set
        The file names of all files on an anaconda channel.
        Something like 'linux-64/album-0.0.2.post0-0_g6b05c00_py27.tar.bz2'
    """
    index = get_index([channel], prepend=False)
    file_names = [v['channel'].split('/')[-1] + '/' + k.split('::')[1] for k, v in index.items()]
    return set(file_names)


def Popen(cmd):
    """Returns stdout, stderr and the return code

    Parameters
    ----------
    cmd : list
        List of strings to be sent to subprocess.Popen

    Returns
    -------
    stdout : """
    # capture the output with subprocess.Popen
    try:
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        current_subprocs.add(proc)
    except subprocess.CalledProcessError as cpe:
        print(cpe)
        # pdb.set_trace()
    stdout, stderr = proc.communicate()
    if stdout:
        stdout = stdout.decode()
    if stderr:
        stderr = stderr.decode()
    current_subprocs.remove(proc)
    return stdout, stderr, proc.returncode


def check_output(cmd):
    try:
        ret = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as cpe:
        print(cmd)
        print(cpe.output.decode())
        raise RuntimeError("{} raised with check_output command {}".format(
            cpe.output.decode(), cmd))
    else:
        name = ret.decode().strip().split('\n')
        return name


def determine_build_name(path_to_recipe, *conda_build_args):
    """Figure out what conda says the output built package name is going to be
    Parameters
    ----------
    path_to_recipe : str
        The location of the recipe on disk
    *conda_build_args : list
        List of extra arguments to be appeneded to the conda build command.
        For example, this might include ['--python', '3.4'], to tell
        conda-build to build a python 3.4 package

    Returns
    -------
    package_name : str
        Something like:
        /home/edill/mc/conda-bld/linux-64/pims-0.3.3.post0-0_g1bea480_py27.tar.bz2
    """
    conda_build_args = [] if conda_build_args is None else list(
        conda_build_args)
    logger.debug('conda_build_args=%s', conda_build_args)
    cmd = ['conda', 'build', path_to_recipe, '--output'] + conda_build_args
    logger.debug('cmd=%s', cmd)
    ret = check_output(cmd)
    logger.debug('ret=%s', ret)
    # if len(ret) > 1:
    #     logger.debug('recursing...')
    #     # Then this is the first time we are getting the build name and conda
    #     # has to check out the source. Call it a second time and you get the4
    #     # full path to the file that will be spit out by conda-build
    #     return determine_build_name(path_to_recipe, *conda_build_args)
    # we want to keep track of the exact command so we can run it later.
    # Obviously drop the `--output` flag so that conda-build actually builds
    # the package.
    cmd.remove('--output')
    logger.debug('cmd=%s', cmd)
    return ret[-1], cmd


def decide_what_to_build(recipes_path, python, packages, numpy):
    """Figure out which packages need to be built

    Parameters
    ----------
    recipes_path : str
        Path to folder containg conda recipes
    python : list
        List of python versions to build
    packages : list
        List of packages that already exist on the anaconda channel we are
        interested in
    numpy : list
        List of numpy versions to build.

    Returns
    -------
    metas_to_build : list
        the metadata for the conda build with three extra fields:
            - full_build_path
            - build_name
            - build_command
    metas_not_to_build : list
        Same as `packages_to_build`
    """

    metas_not_to_build = []
    metas_to_build = []
    # logger.info("Build Plan")
    # logger.info("Determining package build names...")
    # logger.info('{: <8} | {}'.format('to build', 'built package name'))
    recipes_path = os.path.abspath(recipes_path)
    logger.info("recipes_path = {}".format(recipes_path))
    if 'meta.yaml' in os.listdir(recipes_path):
        folders = [recipes_path]
    else:
        folders = sorted(os.listdir(recipes_path))
    logger.info("\nFiguring out which recipes need to build...")
    for folder in folders:
        recipe_dir = os.path.join(recipes_path, folder)
        if os.path.isfile(recipe_dir):
            continue
        if 'meta.yaml' not in os.listdir(recipe_dir):
            continue
        logger.debug('Evaluating recipe: {}'.format(recipe_dir))
        build, run, test = get_deps_from_metadata(recipe_dir)
        # only need to do multiple numpy builds if the meta.yaml pins the numpy
        # version in build and run.
        numpy_build_versions = numpy
        if 'numpy x.x' not in build:
            numpy_build_versions = [DEFAULT_NP_VER]
        python_build_versions = python
        if 'python' not in set(build + run):
            python_build_versions = [DEFAULT_PY]
        for py, npy in itertools.product(python_build_versions,
                                         numpy_build_versions):
            logger.debug("Checking py={} and npy={}".format(py, npy))
            try:
                with env_var('CONDA_NPY', npy):
                    path_to_built_package, build_cmd = determine_build_name(
                        recipe_dir, '--python', py, '--numpy', npy)
            except RuntimeError as re:
                logger.error(re)
                continue
            if '.tar.bz' not in path_to_built_package:
                on_anaconda_channel = True
                name_on_anaconda = "Skipping {}".format(
                    folder, py, npy
                )
            else:
                name_on_anaconda = os.sep.join(
                    path_to_built_package.split(os.sep)[-2:])
                # pdb.set_trace()
                meta = MetaData(recipe_dir)
                on_anaconda_channel = name_on_anaconda in packages
                meta.full_build_path = path_to_built_package
                meta.build_name = name_on_anaconda
                meta.build_command = build_cmd
                if on_anaconda_channel:
                    metas_not_to_build.append(meta)
                else:
                    metas_to_build.append(meta)

            logger.info('{:<8} | {:<5} | {:<5} | {}'.format(
                str(not bool(on_anaconda_channel)), py, npy, name_on_anaconda))

    return metas_to_build, metas_not_to_build


def get_deps_from_metadata(path):
    """
    Extract all dependencies from a recipe. Return tuple of (build, run, test)
    """
    meta = MetaData(path)
    test = meta.meta.get('test', {}).get('requires', [])
    run = meta.meta.get('requirements', {}).get('run', [])
    build = meta.meta.get('requirements', {}).get('build', [])
    return build or [], run or [], test or []


def sanitize_names(list_of_names):
    list_of_names = [name.split(' ')[0] for name in list_of_names]
    list_of_names = [name for name in
                     list_of_names]  # if name not in packages_on_conda_forge]
    return list_of_names


def build_dependency_graph(metas):
    """
    Given an input list of MetaData objects, build a directional graph of
    how the dependencies are related.  Gotchas include determining the
    package name without the version pinning and without conda selectors.

    Parameters
    ----------
    metas : iterable of MetaData objects

    Returns
    -------
    graph
        Networkx graph object

    Notes
    -----
    Example of version pinning:
    requirements:
        build:
            numpy >=1.11

    Example of selectors:
    requirements:
        build:
            python  # [not py2k]
    """
    run_deps = {}
    build_deps = {}
    test_deps = {}
    logger.debug("Building dependency graph for %s libraries", len(metas))

    for meta in metas:
        name = meta.meta['package']['name']
        logger.debug('name=%s', name)
        build_deps[name] = sanitize_names(
            meta.meta.get('requirements', {}).get('build', []))
        logger.debug('build_deps=%s', build_deps)
        run_deps[name] = sanitize_names(
            meta.meta.get('requirements', {}).get('run', []))
        logger.debug('run_deps=%s', run_deps)
        test_deps[name] = sanitize_names(
            meta.meta.get('test', {}).get('requires', []))
        logger.debug('test_deps=%s', test_deps)
    # pdb.set_trace()
    # union = copy.deepcopy(build_deps)
    union = {k: set(build_deps.get(k, []) + run_deps.get(k, []) +
                    test_deps.get(k, []))
             for k in set(list(run_deps.keys()) + list(build_deps.keys()) +
                          list(test_deps.keys()))}
    # logger.debug()
    # drop all extra packages that I do not have conda recipes for
    for name, items in union.items():
        union[name] = [item for item in items if item in union]
    return union


def resolve_dependencies(package_dependencies):
    """
    Given a dictionary mapping a package to its dependencies, return a
    generator of packages to install, sorted by the required install
    order.

    >>> deps = resolve_dependencies({'a': ['b', 'c'], 'b': ['c'],
                                     'c': ['d'], 'd': []})
    >>> list(deps)
    ['d', 'c', 'b', 'a']

    Notes
    -----
    copied from conda-build-all. Thanks @pelson!
    """
    remaining_dependencies = package_dependencies.copy()
    completed_packages = []

    # A maximum of 10000 iterations. Beyond that and there is probably a
    # problem.
    for failsafe in range(10000):
        for package, deps in sorted(remaining_dependencies.copy().items()):
            if all(dependency in completed_packages for dependency in deps):
                completed_packages.append(package)
                remaining_dependencies.pop(package)
                yield package
            else:
                # Put a check in to ensure that all the dependencies were
                # defined as packages, otherwise we will never succeed.
                for dependency in deps:
                    if dependency not in package_dependencies:
                        msg = ('The package {} depends on {}, but it was not '
                               'part of the package_dependencies dictionary.'
                               ''.format(package, dependency))
                        raise ValueError(msg)

        # Close off the loop if we've completed the dependencies.
        if not remaining_dependencies:
            break
    else:
        raise ValueError('Dependencies could not be resolved. '
                         'Remaining dependencies: {}'
                         ''.format(remaining_dependencies))


def run_build(build_order, allow_failures=False):
    """Build packages that do not already exist at {{ channel }}

    Parameters
    ----------
    build_order : iterable
        The order that the packages should be built in
    recipes_path : str
        Iterable of conda build Metadata objects.
        HINT: output of `decide_what_to_build` is probably what should be
        passed in here
    allow_failures : bool, optional

    """
    build_or_test_failed = []
    build_success = []
    # for each package
    for meta in build_order:
        full_build_path = meta.full_build_path
        build_name = meta.build_name
        build_command = meta.build_command
        # output the package build name
        print("Building: %s" % build_name)
        # need to run the build command with --output again or conda freaks out
        # stdout, stderr, returncode = Popen(build_command + ['--output'])
        # output the build command
        print("Build cmd: %s" % ' '.join(build_command))
        np = ''
        try:
            np_idx = build_command.index('--numpy')
        except ValueError:
            # --numpy is not in build_command
            pass
        else:
            # get the numpy version as the argument following the `--numpy`
            # flag
            np = build_command[np_idx+1]
        with env_var('CONDA_NPY', np):
            stdout, stderr, returncode = Popen(build_command)
        if returncode != 0:
            build_or_test_failed.append(build_name)
            message = ('\n\n========== STDOUT ==========\n'
                       '\n{}'
                       '\n\n========== STDERR ==========\n'
                       '\n{}'.format(pformat(stdout), pformat(stderr)))
            logger.error(message)
            if not allow_failures:
                sys.exit(1)

        build_success.append(build_name)

    return {
        'build_success': sorted(build_success),
        'build_or_test_failed': sorted(build_or_test_failed),
    }


def pdb_hook(exctype, value, traceback):
    pdb.post_mortem(traceback)


def cli():
    p = ArgumentParser(
        description="""
Tool for building a folder of conda recipes where only the ones that don't
already exist are built.
""",
    )
    p.add_argument(
        'recipes_path',
        nargs='?',
        help="path to recipes that should be built"
    )
    p.add_argument(
        '-p', "--python",
        action='store',
        nargs='*',
        help="Python version to build conda packages for",
    )
    p.add_argument(
        '-c', "--channel",
        action='store',
        nargs='?',
        help="Conda channel to check for pre-existing artifacts",
        default="anaconda"
    )
    p.add_argument(
        '-l', '--log',
        nargs='?',
        help='Name of the log file to write'
    )
    p.add_argument(
        '--numpy', action='store', nargs='*',
        help=('List the numpy versions to build packages for. Defaults to '
              '%(default)s'),
        default=[DEFAULT_NP_VER]
    )
    p.add_argument(
        '-v', '--verbose', help="Enable DEBUG level logging. Default is INFO",
        default=False, action="store_true"
    )
    p.add_argument(
        '--pdb', help="Enable PDB debugging on exception",
        default=False, action="store_true"
    )
    p.add_argument(
        '--allow-failures', help=("Enable build.py to continue building conda "
                                  "packages if one of them fails"),
        default=False, action="store_true"
    )
    p.add_argument(
        '--dry-run', help="Figure out what to build and then exit",
        default=False, action="store_true"
    )
    p.add_argument(
        '--plan-file', help="File to output json version of the plan",
        action="store"
    )

    args = p.parse_args()
    if not args.python:
        args.python = [DEFAULT_PY]
    args_dct = dict(args._get_kwargs())
    use_pdb = args_dct.pop('pdb')
    if use_pdb:
        # set the pdb_hook as the except hook for all exceptions
        sys.excepthook = pdb_hook
    loglevel = logging.DEBUG if args_dct.pop('verbose') else logging.INFO
    log = args_dct.pop('log')
    init_logging(log_file=log, loglevel=loglevel)
    args_dct['recipes_path'] = os.path.abspath(args.recipes_path)
    if args_dct.get('channel') is None:
        p.print_help()
        print("\nError: Need to pass in an anaconda channel with '-c' or "
              "'--channel'\n")
        sys.exit(1)

    print(args_dct)
    run(**args_dct)


def init_logging(log_file=None, loglevel=logging.INFO):
    if not log_file:
        log_dirname = os.path.join(tempfile.gettempdir(), 'buildmatrix')
        if not os.path.exists(log_dirname):
            os.mkdir(log_dirname)

        log_filename = time.strftime("%Y.%m.%d-%H.%M")
        log = os.path.join(log_dirname, log_filename)
    # set up logging
    print('Logging summary to %s' % log)
    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(log)

    file_handler.setLevel(loglevel)
    stream_handler.setLevel(loglevel)
    logger.setLevel(loglevel)

    # FORMAT = "%(levelname)s | %(asctime)-15s | %(message)s"
    # file_handler.setFormatter(FORMAT)
    # stream_handler.setFormatter(FORMAT)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)


def run(recipes_path, python, channel, numpy, allow_failures=False,
        dry_run=False, plan_file=None):
    """
    Run the build for all recipes listed in recipes_path

    Parameters
    ----------
    recipes_path : str
        Folder that contains conda recipes
    python : iterable
        Iterable of python versions to build conda packages for
    channel : str
        The channel to check for packages
    numpy : iterable
        Iterable of numpy versions to build conda packages for
    allow_failures : bool, optional
        True: Continue building packages after one has failed.
        Defaults to False
    plan_file : str, optional
        If not None, then output the plan to a file in json format
    """
    # check to make sure that the recipes_path exists
    if not os.path.exists(recipes_path):
        logger.error("The recipes_path: '%s' does not exist." % recipes_path)
        sys.exit(1)
    if numpy is None:
        numpy = os.environ.get("CONDA_NPY", "1.11")
        if not isinstance(numpy, list):
            numpy = [numpy]
    # get all file names that are in the channel I am interested in
    packages = get_file_names_on_anaconda_channel(channel)

    metas_to_build, metas_to_skip = decide_what_to_build(
        recipes_path, python, packages, numpy)
    if metas_to_build == []:
        print('No recipes to build!. Exiting 0')
        sys.exit(0)

    # sort into the correct order
    dependency_graph = build_dependency_graph(metas_to_build)
    metas_name_order = resolve_dependencies(dependency_graph)
    build_order = [meta for name in metas_name_order for meta in metas_to_build
                   if meta.meta['package']['name'] == name]
    logger.info("\nThis is the determined build order...")
    for meta in build_order:
        logger.info(meta.build_name)

    if plan_file:
        plan = {}
        with open(plan_file, 'w') as f:
            json.dump([meta.meta for meta in build_order], f)

    # bail out if we're in dry run mode
    if dry_run:
        print("Dry run enabled. Exiting 0")
        sys.exit(0)


    # Run the actual build
    try:
        results = run_build(build_order, allow_failures=allow_failures)
        results['alreadybuilt'] = sorted([skip.build_name
                                          for skip in metas_to_skip])
    except Exception as e:
        tb = traceback.format_exc()
        message = ("Major error encountered in attempt to build\n{}\n{}"
                   "".format(tb, e))
        logger.error(message)
        # exit with a failed status code
        sys.exit(1)
    else:
        logger.info("Build summary")
        logger.info('Expected {} packages'.format(len(metas_to_build)))
        num_builds = {k: len(v) for k, v in results.items()}
        logger.info('Got {} packages.'.format(
            sum([n for n in num_builds.values()])))
        logger.info('Breakdown is as follows')
        for k, v in num_builds.items():
            logger.info('section: {:<25}. number build: {}'.format(k, v))
        if results['build_or_test_failed']:
            message = ("Some packages failed to build\n{}"
                       "\n{}".format(pformat(results['build_or_test_failed'])))
            logger.error(message)
        if results['build_success']:
            logger.info("Packages build successfully")
            logger.info(pformat(results['build_success']))
        if results['alreadybuilt']:
            logger.info('Packages that already exist in {}'.format(channel))
            logger.info(pformat(results['alreadybuilt']))

        if results['build_or_test_failed']:
            # exit with a failed status code
            sys.exit(1)

if __name__ == "__main__":
    cli()
