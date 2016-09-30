import pytest
from buildmatrix import cli


def test_sorting(examples_dir):
    # This test uses the two package in the examples directory (package-a and
    # package-b) and makes sure that package-a is built first since package-b
    # depends on package-a
    cli.init_logging()
    packages = cli.get_file_names_on_anaconda_channel("anaconda")

    metas_to_build, metas_to_skip = cli.decide_what_to_build(
        examples_dir, ['2.7', '3.4', '3.5'], packages, ['1.10', '1.11'])

    dependency_graph = cli.build_dependency_graph(metas_to_build)
    metas_name_order = cli.resolve_dependencies(dependency_graph)
    build_order = [meta for name in metas_name_order for meta in metas_to_build
                   if meta.meta['package']['name'] == name]

    assert len(build_order) == 9

    assert build_order[0].meta['package']['name'] == 'package-a'
    assert build_order[6].meta['package']['name'] == 'package-b'
