import os
from typing import List

import zkay.config as cfg
from zkay.utils.output_suppressor import output_suppressed
from zkay.utils.run_command import run_command
from zkay.zkay_ast.ast import indent

# path jo jsnark interface jar
circuit_builder_jar = os.path.join(os.path.dirname(os.path.realpath(__file__)),  'JsnarkCircuitBuilder.jar')
with open(circuit_builder_jar, 'rb') as jarfile:
    from hashlib import sha512
    circuit_builder_jar_hash = sha512(jarfile.read()).hexdigest()


def compile_circuit(circuit_dir: str, javacode: str):
    jfile = os.path.join(circuit_dir, cfg.jsnark_circuit_classname + ".java")
    with open(jfile, 'w') as f:
        f.write(javacode)

    # Compile the circuit java file
    run_command(['javac', '-cp', f'{circuit_builder_jar}', jfile], cwd=circuit_dir)

    # Run jsnark to generate the circuit
    with output_suppressed('jsnark'):
        out, err = run_command(['java', '-Xms4096m', '-Xmx16384m', '-cp', f'{circuit_builder_jar}:{circuit_dir}', cfg.jsnark_circuit_classname, 'compile'], cwd=circuit_dir)
        print(out, err)


def prepare_proof(circuit_dir: str, serialized_args: List[int]):
    serialized_arg_str = [hex(arg)[2:] for arg in serialized_args]

    # Run jsnark to evaluate the circuit and compute prover inputs
    with output_suppressed('jsnark'):
        out, err = run_command(['java', '-Xms8196m', '-Xmx16384m', '-cp', f'{circuit_builder_jar}:{circuit_dir}', cfg.jsnark_circuit_classname, 'prove', *serialized_arg_str], cwd=circuit_dir)
        print(out, err)


_class_template_str = '''\
import zkay.ZkayCircuitBase;

public class {circuit_class_name} extends ZkayCircuitBase {{
    public {circuit_class_name}() {{
        super("{circuit_name}", "{crypto_backend}", {key_bits}, {priv_size}, {pub_size}, {use_input_hashing});
    }}

    @Override
    protected void buildCircuit() {{
{init_inputs}

{constraints}{verify_hash_str}
    }}

    public static void main(String[] args) {{
        {circuit_class_name} circuit = new {circuit_class_name}();
        circuit.run(args);
    }}
}}
'''


def get_jsnark_circuit_class_str(name: str, priv_size: int, pub_size: int, should_hash: bool, input_init: List[str], constraints: List[str]):
    verify_hash = f'\n\n{8*" "}verifyInputHash();' if should_hash else ''
    return _class_template_str.format(circuit_class_name=cfg.jsnark_circuit_classname, crypto_backend=cfg.crypto_backend, circuit_name=name,
                                      key_bits=cfg.key_bits, priv_size=priv_size, pub_size=pub_size, use_input_hashing=str(should_hash).lower(),
                                      init_inputs=indent(indent('\n'.join(input_init))), constraints=indent(indent('\n'.join(constraints))),
                                      verify_hash_str=verify_hash)
