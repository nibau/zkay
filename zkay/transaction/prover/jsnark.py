import os
from typing import List

import zkay.jsnark_interface.jsnark_interface as jsnark
import zkay.jsnark_interface.libsnark_interface as libsnark
from zkay.compiler.privacy.library_contracts import bn128_scalar_field
from zkay.transaction.interface import ZkayProverInterface


class JsnarkProver(ZkayProverInterface):
    def _generate_proof(self, verifier_dir: str, priv_values: List[int], in_vals: List[int], out_vals: List[int]) -> List[int]:
        args = list(map(int, priv_values + in_vals + out_vals))
        for arg in args:
            assert arg < bn128_scalar_field, 'argument overflow'

        jsnark.prepare_proof(verifier_dir, args)

        cwd = os.getcwd()
        os.chdir(verifier_dir)
        libsnark.generate_proof(verifier_dir, os.path.join(verifier_dir, 'circuit.in'), self.proving_scheme)
        os.chdir(cwd)

        with open(os.path.join(verifier_dir, 'proof.out')) as f:
            proof_lines = f.read().splitlines()
        proof = list(map(lambda x: int(x, 0), proof_lines))
        return proof
