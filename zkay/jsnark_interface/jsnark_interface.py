import os
from typing import List

from zkay.config import cfg
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
    run_command(['java', '-Xms4096m', '-Xmx16384m', '-cp', f'{circuit_builder_jar}:{circuit_dir}', cfg.jsnark_circuit_classname, 'compile'], cwd=circuit_dir, key='jsnark')


def prepare_proof(circuit_dir: str, serialized_args: List[int]):
    serialized_arg_str = [format(arg, 'x') for arg in serialized_args]

    # Run jsnark to evaluate the circuit and compute prover inputs
    run_command(['java', '-Xms4096m', '-Xmx16384m', '-cp', f'{circuit_builder_jar}:{circuit_dir}', cfg.jsnark_circuit_classname, 'prove', *serialized_arg_str], cwd=circuit_dir, key='jsnark')


_class_template_str = '''\
import zkay.ZkayCircuitBase;
import static zkay.ZkayType.ZkUint;
import static zkay.ZkayType.ZkInt;
import static zkay.ZkayType.ZkBool;

public class {circuit_class_name} extends ZkayCircuitBase {{
    public {circuit_class_name}() {{
        super("{circuit_name}", "{crypto_backend}", {key_bits}, {pub_in_size}, {pub_out_size}, {priv_in_size}, {use_input_hashing});
    }}
{fdefs}
    @Override
    protected void buildCircuit() {{
        super.buildCircuit();
{init_inputs}

{constraints}
    }}

    public static void main(String[] args) {{
        {circuit_class_name} circuit = new {circuit_class_name}();
        circuit.run(args);
    }}
}}
'''


def get_jsnark_circuit_class_str(name: str, circuit, fdefs: List[str], input_init: List[str], constraints: List[str]):
    function_definitions = '\n\n'.join(fdefs)
    if function_definitions:
        function_definitions = f'\n{function_definitions}\n'
    return _class_template_str.format(circuit_class_name=cfg.jsnark_circuit_classname, crypto_backend=cfg.crypto_backend, circuit_name=name,
                                      key_bits=cfg.key_bits, pub_in_size=circuit.in_size_trans, pub_out_size=circuit.out_size_trans,
                                      priv_in_size=circuit.priv_in_size_trans, use_input_hashing=str(cfg.should_use_hash(circuit)).lower(),
                                      fdefs=indent(function_definitions),
                                      init_inputs=indent(indent('\n'.join(input_init))), constraints=indent(indent('\n'.join(constraints))))
