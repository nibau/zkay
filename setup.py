from setuptools import setup, find_packages

setup(
    name='zkay',
    version='0.2',
    packages=find_packages(),
    package_data={
        'zkay.examples': ['**/*.sol', 'scenarios/*.py'],
        'zkay.jsnark_interface': ['JsnarkCircuitBuilder.jar', 'run_snark'],

        'zkay.compiler.privacy.legacy': ['pki.sol'],
        'zkay.compiler.zokrates': ['verify_libs.sol'],
    },
    url='',
    license='',
    install_requires=[
        'Cython==0.29.14',
        'typing-extensions==3.7.4.1',
        'web3[tester]==v5.3.1',
        'antlr4-python3-runtime==4.7.2',
        'parameterized==0.7.1',
        'py-solc-x==0.6.0',
        'pycryptodome==3.9.4',
    ],
    python_requires='>=3.7,<4',
    author='nicbauma',
    author_email='',
    description=''
)
