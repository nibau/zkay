import json
import os
import pathlib
import re
import shutil
import tempfile
import uuid
from copy import deepcopy
from typing import Tuple

from zkay import my_logging
from zkay.compiler.privacy import library_contracts
from zkay.compiler.privacy.circuit_generation.backends.jsnark_generator import JsnarkGenerator
from zkay.compiler.privacy.circuit_generation.circuit_generator import CircuitGenerator
from zkay.compiler.privacy.manifest import Manifest
from zkay.compiler.privacy.proving_schemes.gm17 import ProvingSchemeGm17
from zkay.compiler.privacy.proving_schemes.proving_scheme import ProvingScheme
from zkay.compiler.privacy.transformer.zkay_contract_transformer import transform_ast
from zkay.compiler.solidity.compiler import check_compilation, SolcException
from zkay.config import cfg
from zkay.utils.helpers import read_file, lines_of_code, without_extension
from zkay.utils.progress_printer import print_step
from zkay.utils.timer import time_measure
from zkay.zkay_ast.process_ast import get_processed_ast, ParseExeception, PreprocessAstException, TypeCheckException


def compile_zkay_file(input_file_path: str, output_dir: str, import_keys: bool = False):
    code = read_file(input_file_path)

    # log specific features of compiled program
    my_logging.data('originalLoc', lines_of_code(code))
    m = re.search(r'\/\/ Description: (.*)', code)
    if m:
        my_logging.data('description', m.group(1))
    m = re.search(r'\/\/ Domain: (.*)', code)
    if m:
        my_logging.data('domain', m.group(1))
    _, filename = os.path.split(input_file_path)

    # compile
    with time_measure('compileFull'):
        cg, _ = compile_zkay(code, output_dir, without_extension(filename), import_keys)


def compile_zkay(code: str, output_dir: str, output_filename_without_ext: str, import_keys: bool = False) -> Tuple[CircuitGenerator, str]:
    # Copy zkay code to output
    zkay_filename = f'{output_filename_without_ext}.zkay'
    if not import_keys:
        with open(os.path.join(output_dir, zkay_filename), 'w') as f:
            f.write(code)
    else:
        if not os.path.exists(os.path.join(output_dir, zkay_filename)):
            raise RuntimeError('')
    output_filename = f'{output_filename_without_ext}.sol'

    try:
        ast = get_processed_ast(code)
    except (ParseExeception, PreprocessAstException, TypeCheckException, SolcException) as e:
        if cfg.is_unit_test:
            raise e
        else:
            exit(3)

    with print_step("Transforming zkay -> public contract"):
        ast, zkt = transform_ast(deepcopy(ast))

    with print_step("Write library contract files"):
        # Write pki contract
        pki_filename = os.path.join(output_dir, f'{cfg.pki_contract_name}.sol')
        with open(pki_filename, 'w') as f:
            f.write(library_contracts.get_pki_contract())

        # Write library contract
        verifylib_filename = os.path.join(output_dir, ProvingScheme.verify_libs_contract_filename)
        with open(verifylib_filename, 'w') as f:
            f.write(library_contracts.get_verify_libs_code())

    # Write public contract file
    with print_step('Write public solidity code'):
        contract_filename = os.path.join(output_dir, output_filename)
        with open(contract_filename, 'w') as f:
            solidity_code_output = ast.code()
            f.write(solidity_code_output)

    with print_step("Dry-run solc compilation (libs)"):
        for f in [pki_filename, verifylib_filename]:
            check_compilation(f, show_errors=False)

    ps = ProvingSchemeGm17()
    if cfg.snark_backend == 'jsnark':
        cg = JsnarkGenerator(ast, list(zkt.circuit_generators.values()), ps, output_dir)
    else:
        raise ValueError(f"Selected invalid backend {cfg.snark_backend}")

    # Generate manifest
    if not import_keys:
        with print_step("Writing manifest file"):
            manifest = {
                Manifest.uuid: uuid.uuid1().hex,
                Manifest.zkay_version: cfg.zkay_version,
                Manifest.solc_version: cfg.solc_version,
                Manifest.zkay_contract_filename: zkay_filename,
                Manifest.contract_filename: output_filename,
                Manifest.proving_scheme: ps.name,
                Manifest.pki_lib: f'{cfg.pki_contract_name}.sol',
                Manifest.verify_lib: ProvingScheme.verify_libs_contract_filename,
                Manifest.verifier_names: {
                    f'{cc.fct.parent.idf.name}.{cc.fct.name}': cc.verifier_contract_type.code() for cc in
                    cg.circuits_to_prove
                }
            }
            with open(os.path.join(output_dir, 'manifest.json'), 'w') as f:
                f.write(json.dumps(manifest))
    elif not os.path.exists(os.path.join(output_dir, 'manifest.json')):
        raise RuntimeError('Zkay contract import failed: Manifest file is missing')

    # Generate circuits and corresponding verification contracts
    cg.generate_circuits(import_keys=import_keys)

    # Check that all the solidity files would compile
    with print_step("Dry-run solc compilation (main contracts + verifiers)"):
        for f in [contract_filename] + cg.get_verification_contract_filenames():
            check_compilation(f, show_errors=False)

    return cg, solidity_code_output


def package_zkay(zkay_input_filename: str, cg: CircuitGenerator):
    with print_step('Packaging for distribution'):
        # create archive with zkay code + all verification and prover keys
        root = pathlib.Path(cg.output_dir)
        infile = pathlib.Path(zkay_input_filename)
        manifestfile = root.joinpath("manifest.json")
        filenames = [pathlib.Path(p) for p in cg.get_all_key_paths()]
        for p in filenames + [infile, manifestfile]:
            if not p.exists():
                raise FileNotFoundError()

        with tempfile.TemporaryDirectory() as tmpdir:
            shutil.copyfile(infile, os.path.join(tmpdir, infile.name))
            shutil.copyfile(manifestfile, os.path.join(tmpdir, manifestfile.name))
            for p in filenames:
                pdir = os.path.join(tmpdir, p.relative_to(root).parent)
                if not os.path.exists(pdir):
                    os.makedirs(pdir)
                shutil.copyfile(p.absolute(), os.path.join(tmpdir, p.relative_to(root)))

            output_basename = infile.name.replace('.sol', '')

            shutil.make_archive(os.path.join(cg.output_dir, output_basename), 'zip', tmpdir)

        os.rename(os.path.join(cg.output_dir, f'{output_basename}.zip'), os.path.join(cg.output_dir, f'{output_basename}.zkpkg'))


def import_pkg(filename: str):
    pass
