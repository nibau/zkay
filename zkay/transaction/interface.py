"""
This module defines the Runtime API, an abstraction layer which is used by the generated PythonOffchainSimulator classes.

It provides high level functions for
- blockchain interaction (deployment, state variable retrieval, transaction issuing, ...),
- cryptographic operations (encryption, decryption, key generation) and key management (local keystore)
- NIZK-proof generation
"""

import json
import os
from abc import ABCMeta, abstractmethod
from builtins import type
from typing import Tuple, List, Optional, Union, Any, Dict, Collection

from zkay.compiler.privacy.zkay_frontend import compile_zkay_file
from zkay.config import cfg, debug_print

from zkay.compiler.privacy.library_contracts import bn128_scalar_field
from zkay.compiler.privacy.manifest import Manifest
from zkay.transaction.types import AddressValue, MsgStruct, BlockStruct, TxStruct, PublicKeyValue, Value, PrivateKeyValue, CipherValue, \
    RandomnessValue, KeyPair
from zkay.utils.progress_printer import colored_print, TermColor
from zkay.utils.timer import time_measure


def parse_manifest(project_dir: str) -> Dict:
    """Returned parsed manifest json file located in project dir."""
    with open(os.path.join(project_dir, 'manifest.json')) as f:
        j = json.loads(f.read())
        j[Manifest.project_dir] = project_dir
    return j


class IntegrityError(Exception):
    """Exception which is raised when any part of a deployed zkay contract does not match the local contract file."""
    pass


class BlockChainError(Exception):
    """
    Exception which is raised when a blockchain interaction fails for any reason.
    """
    pass


class TransactionFailedException(BlockChainError):
    """Exception which is raised when a transaction fails."""
    pass


class ProofGenerationError(Exception):
    """Exception which is raised when proof generation fails."""
    pass


class ZkayBlockchainInterface(metaclass=ABCMeta):
    """
    API to interact with the blockchain.

    It automatically ensures that all needed library contracts are accessible.
    If cfg.blockchain_pki_address or cfg.blockchain_bn256g2_address is not specified, the corresponding library contract will
    be deployed automatically using ZkayBlockchainInterface.default_address as sender if cfg.blockchain_default_account is specified (useful for testing).

    Otherwise, the integrity of the contract at the designated address on the chain is verified.
    On success the already deployed library contract will be used, otherwise execution of the contract simulator terminates for safety reasons.
    """

    # PUBLIC API

    @property
    def default_address(self) -> Optional[AddressValue]:
        """Return wallet address to use as from address when no address is explicitly specified."""
        addr = self._default_address()
        return None if addr is None else AddressValue(addr)

    def create_test_accounts(self, count: int) -> Tuple:
        """
        Return addresses of pre-funded accounts (only implemented for w3-eth-tester and w3-ganache, for debugging).

        :param count: how many accounts
        :raise NotImplementedError: if the backend does not support dummy accounts
        :raise ValueError: if not enough unused pre-funded accounts are available
        :return: the account addresses (either a single value if count = 1 or a tuple otherwise)
        """
        # may not be supported by all backends
        raise NotImplementedError('Current blockchain backend does not support creating pre-funded test accounts.')

    @abstractmethod
    def get_special_variables(self, sender: AddressValue, wei_amount: int = 0) -> Tuple[MsgStruct, BlockStruct, TxStruct]:
        """
        Return message, block and transaction objects, populated according to the current chain state.

        :param sender: transaction sender address
        :param wei_amount: transaction value (if payable)
        :return: populated builtin objects
        """
        pass

    def get_balance(self, address: AddressValue) -> int:
        """Return the balance of the wallet with the designated address (in wei)."""
        return self._get_balance(address.val)

    def req_public_key(self, address: AddressValue) -> PublicKeyValue:
        """
        Request the public key for the designated address from the PKI contract.

        :param address: Address for which to request public key
        :raise BlockChainError: if request fails
        :return: the public key
        """
        assert isinstance(address, AddressValue)
        debug_print(f'Requesting public key for address "{address}"')
        return self._req_public_key(address.val)

    def announce_public_key(self, sender: AddressValue, pk: PublicKeyValue) -> Any:
        """
        Announce a public key to the PKI

        WARNING: THIS ISSUES A CRYPTO CURRENCY TRANSACTION (GAS COST)

        :param sender: public key owner, its eth private key must be hosted in the eth node to which the backend connects.
        :param pk: the public key to announce
        :raise BlockChainError: if there is an error in the backend
        :raise TransactionFailedException: if the announcement transaction failed
        :return: backend-specific transaction receipt
        """
        assert isinstance(sender, AddressValue)
        assert isinstance(pk, PublicKeyValue)
        debug_print(f'Announcing public key "{pk}" for address "{sender}"')
        return self._announce_public_key(sender.val, pk[:])

    def req_state_var(self, contract_handle, name: str, *indices) -> Union[bool, int, str, bytes]:
        """
        Request the contract state variable value name[indices[0]][indices[1]][...] from the chain.

        :param contract_handle: contract from which to read state
        :param name: name of the state variable
        :param indices: if the request is for an (nested) array/map index value, the values of all index keys.
        :raise BlockChainError: if request fails
        :return: The value
        """
        assert contract_handle is not None
        debug_print(f'Requesting state variable "{name}"')
        val = self._req_state_var(contract_handle, name, *Value.unwrap_values(list(indices)))
        debug_print(f'Got value {val} for state variable "{name}"')
        return val

    def call(self, contract_handle, name: str, *args) -> Union[bool, int, str, bytes, List]:
        """
        Call the specified pure/view function in the given contract with the provided arguments.

        :param contract_handle: the contract in which the function resides
        :param name: name of the function to call
        :param args: argument values
        :raise BlockChainError: if request fails
        :return: function return value
        """

        assert contract_handle is not None
        debug_print(f'Calling contract function {name}{Value.collection_to_string(args)}')
        val = self._req_state_var(contract_handle, name, *Value.unwrap_values(list(args)))
        debug_print(f'Got return value {val}')
        return val

    def transact(self, contract_handle, sender: AddressValue, function: str, actual_args: List, should_encrypt: List[bool], wei_amount: Optional[int] = None) -> Any:
        """
        Issue a transaction for the specified function in the given contract with the provided arguments

        WARNING: THIS ISSUES A CRYPTO CURRENCY TRANSACTION (GAS COST)

        :param contract_handle: the contract in which the function resides
        :param sender: sender address, its eth private key must be hosted in the eth node to which the backend connects.
        :param function: name of the function
        :param actual_args: the function argument values
        :param should_encrypt: a list which contains a boolean value for each argument, which should be true if the corresponding
                               parameter expects an encrypted/private value (this is only used for a last sanity-check)
        :param wei_amount: how much money to send along with the transaction (only for payable functions)
        :raise BlockChainError: if there is an error in the backend
        :raise TransactionFailedException: if the transaction failed
        :return: backend-specific transaction receipt
        """
        assert contract_handle is not None
        self.__check_args(actual_args, should_encrypt)
        debug_print(f'Issuing transaction for function "{function}"{Value.collection_to_string(actual_args)})')
        return self._transact(contract_handle, sender.val, function, *Value.unwrap_values(actual_args), wei_amount=wei_amount)

    def deploy(self, project_dir: str, sender: AddressValue, contract: str, actual_args: List, should_encrypt: List[bool], wei_amount: Optional[int] = None) -> Any:
        """
        Issue a deployment transaction which constructs the specified contract with the provided constructor arguments on the chain.

        WARNING: THIS ISSUES A CRYPTO CURRENCY TRANSACTION (GAS COST)

        :param project_dir: directory where the zkay file, manifest and snark keys reside
        :param sender: creator address, its eth private key must be hosted in the eth node to which the backend connects.
        :param contract: name of the contract to instantiate
        :param actual_args: the constructor argument values
        :param should_encrypt: a list which contains a boolean value for each argument, which should be true if the corresponding
                               parameter expects an encrypted/private value (this is only used for a last sanity-check)
        :param wei_amount: how much money to send along with the constructor transaction (only for payable constructors)
        :raise BlockChainError: if there is an error in the backend
        :raise TransactionFailedException: if the deployment transaction failed
        :return: backend-specific transaction receipt
        """
        self.__check_args(actual_args, should_encrypt)
        debug_print(f'Deploying contract {contract}{Value.collection_to_string(actual_args)}')
        return self._deploy(parse_manifest(project_dir), sender.val, contract, *Value.unwrap_values(actual_args), wei_amount=wei_amount)

    def connect(self, project_dir: str, contract: str, contract_address: AddressValue) -> Any:
        """
        Create a handle which can be used to interact with an existing contract on the chain after verifying its integrity.

        Project dir must contain a .zkay file, a manifest.json file as well as a
        subdirectory *_out containing 'proving.key' and 'verification.key' for each verification contract *.
        These files are referred to as 'local' files in the following explanation.

        If this function succeeds, it is guaranteed, that:
        - the remote main contract at contract_address, matches the solidity contract obtained by running zkay on the local zkay file
          using the configuration stored in the local manifest
        - the pki contract referenced in the remote main contract matches the correct zkay pki contract
        - the verification contracts referenced in the remote solidity contract were generated by running zkay on a zkay file
          equivalent to local zkay file, with zk-snark keys which match the local keys.
        - the library contract referenced in the verification contracts matches the correct zkay library contract

        -> This reduces the required trust to the zk-snark setup phase (i.e. you must trust that prover/verification keys
           were generated for the correct circuit), since you can inspect the source code of the local zkay file and check it
           for malicious behavior yourself (and the zkay implementation, which performs the transformation, is open source as well).

        Example Scenarios:
        a) the remote zkay contract is benign (generated by and deployed using zkay):
           -> you will only be able to connect if the local files are equivalent -> correctness is guaranteed
        b) the remote zkay contract was tampered with (any of the .sol files was modified was modified before deployment)
           -> connection will fail, because local zkay compilation will not produce matching evm bytecode
        c) the prover/verification keys were tampered with (they were generated for a different circuit than the one produced by zkay)
           -> if you have the genuine keys locally, connection will be refused because the keys don't match what is
              baked into the remote verification contract
           -> if you have the same tampered keys locally -> NO GUARANTEES, since the trust assumption is violated

        :param project_dir: directory where the zkay file, manifest and snark keys reside
        :param contract: name of the contract to connect to
        :param contract_address: address of the deployed contract
        :raise IntegrityError: if the integrity check fails (mismatch between local code and remote contract)
        :return: contract handle for the specified contract
        """
        manifest = parse_manifest(project_dir)

        # Compile zkay file to generate main and verification contracts (but don't generate new prover/verification keys and manifest)
        compile_zkay_file(os.path.join(project_dir, manifest[Manifest.zkay_contract_filename]), project_dir, import_keys=True)

        debug_print(f'Connecting to contract {contract}@{contract_address}')
        contract_on_chain = self._connect(manifest, contract, contract_address.val)

        pki_verifier_addresses = {}

        # Check pki integrity
        pki_address = self._req_state_var(contract_on_chain, f'{cfg.pki_contract_name}_inst')
        pki_verifier_addresses[cfg.pki_contract_name] = AddressValue(pki_address)
        with cfg.library_compilation_environment():
            self._verify_contract_integrity(pki_address, os.path.join(project_dir, manifest[Manifest.pki_lib]))

        # Check verifier contract and library integrity
        verifier_names = manifest[Manifest.verifier_names].values()
        if verifier_names:
            some_vname = next(iter(verifier_names))
            libraries = [('BN256G2', os.path.join(project_dir, manifest[Manifest.verify_lib]))]
            some_vcontract = self._req_state_var(contract_on_chain, f'{some_vname}_inst')
            libs = self._verify_library_integrity(libraries, some_vcontract, os.path.join(project_dir, f'{some_vname}.sol'))

            for verifier in verifier_names:
                v_address = self._req_state_var(contract_on_chain, f'{verifier}_inst')
                pki_verifier_addresses[verifier] = AddressValue(v_address)
                vcontract = self._verify_contract_integrity(v_address, os.path.join(project_dir, f'{verifier}.sol'), libraries=libs)

                # Verify prover key
                expected_hash = self._req_state_var(vcontract, cfg.prover_key_hash_name)
                from zkay.transaction.runtime import Runtime
                actual_hash = Runtime.prover().get_prover_key_hash(os.path.join(project_dir, f'{verifier}_out'))
                if expected_hash != actual_hash:
                    raise IntegrityError(f'Prover key hash in deployed verification contract does not match local prover key file for "{verifier}"')

        # Check zkay contract integrity
        self._verify_zkay_contract_integrity(contract_on_chain.address, os.path.join(project_dir, manifest[Manifest.contract_filename]), pki_verifier_addresses)

        with colored_print(TermColor.OKGREEN):
            debug_print(f'OK: Bytecode on blockchain matches local zkay contract')

        return contract_on_chain

    # INTERNAL FUNCTIONALITY

    @abstractmethod
    def _verify_contract_integrity(self, address: str, sol_filename: str, *,
                                   libraries: Dict = None, contract_name: str = None, is_library: bool = False) -> Any:
        """
        Check if the bytecode of the contract at address matches the bytecode obtained by locally compiling sol_filename.

        :param address: address of the remote contract
        :param sol_filename: path to the local contract code file
        :param libraries: library dict which should be passed during compilation (for linking)
        :param contract_name: contract name, if not specified, the first contract in the file is used
        :param is_library: set to true if this a library instead of a contract
        :raise IntegrityError: if there is a mismatch
        :return: a contract handle for the remote contract
        """
        pass

    @abstractmethod
    def _verify_library_integrity(self, libraries: List[Tuple[str, str]], contract_with_libs_addr: str, sol_with_libs_filename: str) -> Dict[str, str]:
        """
        Check if the libraries linked in contract_with_libs match library_sol and return the addresses of the library contracts.

        :param libraries: = List of (library name, library.sol) tuples
        :raise IntegrityError: if there is a mismatch
        :return Dict of library name -> address for all libs from libraries which occurred in contract@contract_with_libs_addr
        """
        pass

    @abstractmethod
    def _verify_zkay_contract_integrity(self, address: str, sol_file: str, pki_verifier_addresses: dict):
        """
        Check if the zkay main contract at address matches the local file

        :param address: address of the remote main contract
        :param sol_file: path to the local contract code file
        :param pki_verifier_addresses: dictionary which maps pki and verification contract names to the corresponding remote addresses
        :raise IntegrityError: if there is a mismatch
        """
        pass

    @abstractmethod
    def _default_address(self) -> Union[None, bytes, str]:
        pass

    @abstractmethod
    def _get_balance(self, address: Union[bytes, str]) -> int:
        pass

    @abstractmethod
    def _pki_verifier_addresses(self, sender: str, manifest) -> Dict[str, AddressValue]:
        pass

    @abstractmethod
    def _req_public_key(self, address: Union[bytes, str]) -> PublicKeyValue:
        pass

    @abstractmethod
    def _announce_public_key(self, address: Union[bytes, str], pk: Tuple[int, ...]) -> Any:
        pass

    @abstractmethod
    def _req_state_var(self, contract_handle, name: str, *indices) -> Union[bool, int, str]:
        pass

    @abstractmethod
    def _transact(self, contract_handle, sender: Union[bytes, str], function: str, *actual_args, wei_amount: Optional[int] = None) -> Any:
        pass

    @abstractmethod
    def _deploy(self, manifest, sender: Union[bytes, str], contract: str, *actual_args, wei_amount: Optional[int] = None) -> Any:
        pass

    @abstractmethod
    def _deploy_or_connect_libraries(self, sender: Union[bytes, str]):
        pass

    @abstractmethod
    def _connect(self, manifest, contract: str, address: Union[bytes, str]) -> Any:
        pass

    @staticmethod
    def __check_args(actual_args: List, should_encrypt: List[bool]):
        assert len(actual_args) == len(should_encrypt)
        for idx, arg in enumerate(actual_args):
            assert not isinstance(arg, PrivateKeyValue) and not isinstance(arg, RandomnessValue)
            assert should_encrypt[idx] == isinstance(arg, CipherValue)


class ZkayCryptoInterface(metaclass=ABCMeta):
    """API to generate cryptographic keys and perform encryption/decryption operations."""

    def generate_or_load_key_pair(self, address: AddressValue) -> KeyPair:
        """
        Return cryptographic keys for the account with the specified address.

        If the pre-existing keys are found for this address, they are loaded from the filesystem,
        otherwise new keys are generated.
        :param address: the address for which to generate keys
        :return: cryptographic keys for address
        """
        return self._generate_or_load_key_pair(address.val.hex())

    def enc(self, plain: Union[int, AddressValue], pk: PublicKeyValue) -> Tuple[CipherValue, RandomnessValue]:
        """
        Encrypt plain with the provided public key.

        :param plain: plain text to encrypt
        :param pk: public key
        :return: Tuple(cipher text, randomness which was used to encrypt plain)
        """
        if isinstance(plain, AddressValue):
            plain = int.from_bytes(plain.val, byteorder='big')
        assert not isinstance(plain, Value), f"Tried to encrypt value of type {type(plain).__name__}"
        assert isinstance(pk, PublicKeyValue), f"Tried to use public key of type {type(pk).__name__}"
        assert int(plain) < bn128_scalar_field, f"Integer overflow, plaintext is > field prime"
        debug_print(f'Encrypting value {plain} with public key "{pk}"')

        while True:
            # Retry until cipher text is not 0
            cipher, rnd = self._enc(int(plain), self.deserialize_bigint(pk[:]))
            cipher, rnd = CipherValue(cipher), RandomnessValue(rnd)
            if cipher != CipherValue():
                break
        return cipher, rnd

    def dec(self, cipher: CipherValue, sk: PrivateKeyValue) -> Tuple[int, RandomnessValue]:
        """
        Decrypt cipher with the provided secret key.

        :param cipher: encrypted value
        :param sk: secret key
        :return: Tuple(plain text, randomness which was used to encrypt plain)
        """
        assert isinstance(cipher, CipherValue), f"Tried to decrypt value of type {type(cipher).__name__}"
        assert isinstance(sk, PrivateKeyValue), f"Tried to use private key of type {type(sk).__name__}"
        debug_print(f'Decrypting value {cipher} with secret key "{sk}"')
        if len(cipher) == 1 and isinstance(cipher[0], AddressValue):
            cipher = CipherValue(cipher[0].val)
            was_address = True
        else:
            was_address = False

        if cipher == CipherValue():
            ret = 0, RandomnessValue()
        else:
            plain, rnd = self._dec(cipher[:], sk.val)
            ret = plain, RandomnessValue(rnd)

        if was_address:
            ret = AddressValue(ret[0]), ret[1]
        return ret

    @staticmethod
    def serialize_bigint(key: int, total_bytes: int) -> List[int]:
        """Serialize a large integer into an array of {cfg.pack_chunk_size}-byte ints."""
        bin = key.to_bytes(total_bytes, byteorder='big')
        return ZkayCryptoInterface.pack_byte_array(bin)

    @staticmethod
    def deserialize_bigint(arr: Collection[int]) -> int:
        """Deserialize an array of {cfg.pack_chunk_size}-byte ints into a single large int"""
        bin = ZkayCryptoInterface.unpack_to_byte_array(arr, 0)
        return int.from_bytes(bin, byteorder='big')

    @staticmethod
    def pack_byte_array(bin: bytes, chunk_size=cfg.pack_chunk_size) -> List[int]:
        """Pack byte array into an array of {chunk_size}-byte ints"""
        total_bytes = len(bin)
        first_chunk_size = total_bytes % chunk_size
        arr = [] if first_chunk_size == 0 else [int.from_bytes(bin[:first_chunk_size], byteorder='big')]
        for i in range(first_chunk_size, total_bytes - first_chunk_size, chunk_size):
            arr.append(int.from_bytes(bin[i:i + chunk_size], byteorder='big'))
        return list(reversed(arr))

    @staticmethod
    def unpack_to_byte_array(arr: Collection[int], desired_length: int) -> bytes:
        """Unpack an array of {cfg.pack_chunk_size}-byte ints into a byte array"""
        return b''.join(chunk.to_bytes(cfg.pack_chunk_size, byteorder='big') for chunk in reversed(list(arr)))[-desired_length:]

    # Interface implementation

    @abstractmethod
    def _generate_or_load_key_pair(self, address: str) -> KeyPair:
        pass

    @abstractmethod
    def _enc(self, plain: int, pk: int) -> Tuple[List[int], List[int]]:
        pass

    @abstractmethod
    def _dec(self, cipher: Tuple[int, ...], sk: Any) -> Tuple[int, List[int]]:
        pass


class ZkayKeystoreInterface:
    """API to add and retrieve local key pairs, and to request public keys."""

    def __init__(self, conn: ZkayBlockchainInterface):
        self.conn = conn
        self.local_pk_store: Dict[AddressValue, PublicKeyValue] = {}
        self.local_key_pairs: Dict[AddressValue, KeyPair] = {}

    def add_keypair(self, address: AddressValue, key_pair: KeyPair):
        """
        Import cryptographic keys for address into this keystore and announce the public key to the pki if necessary.

        :param address: Address to which the keys belong
        :param key_pair: cryptographic keys
        :raise TransactionFailedException: if announcement transaction fails
        """
        self.local_key_pairs[address] = key_pair
        # Announce if not yet in pki
        try:
            self.conn.req_public_key(address)
        except BlockChainError:
            self.conn.announce_public_key(address, key_pair.pk)

    def has_initialized_keys_for(self, address: AddressValue) -> bool:
        """Return true if keys for address are already in the store."""
        return address in self.local_key_pairs

    def getPk(self, address: AddressValue) -> PublicKeyValue:
        """
        Return public key for address.

        If the key is cached locally, returned the cached copy, otherwise request from pki contract.
        :param address: address to which the public key belongs
        :raise BlockChainError: if key request fails
        :return: the public key
        """
        assert isinstance(address, AddressValue)
        debug_print(f'Requesting public key for address {address.val}')
        if address in self.local_pk_store:
            return self.local_pk_store[address]
        else:
            pk = self.conn.req_public_key(address)
            self.local_pk_store[address] = pk
            return pk

    def sk(self, address: AddressValue) -> PrivateKeyValue:
        """
        Return secret key for address from the local key store.

        Only works for keys which were previously added through add_keypair
        :param address: address to which the private key belongs
        :raise KeyError: if key not in local store
        :return: private key
        """
        return self.local_key_pairs[address].sk

    def pk(self, address: AddressValue) -> PublicKeyValue:
        """
        Return public key for address from the local key store.

        Only works for keys which were previously added through add_keypair
        :param address: address to which the public key belongs
        :raise KeyError: if key not in local store
        :return: public key
        """
        return self.local_key_pairs[address].pk


class ZkayProverInterface(metaclass=ABCMeta):
    """API to generate zero knowledge proofs for a particular circuit and arguments."""

    def __init__(self, proving_scheme: str = cfg.proving_scheme):
        self.proving_scheme = proving_scheme

    def generate_proof(self, project_dir: str, contract: str, function: str, priv_values: List, in_vals: List, out_vals: List[Union[int, CipherValue]]) -> List[int]:
        """
        Generate a NIZK-proof using the provided circuit for the given arguments.

        Note: circuit arguments must be in the same order as they are declared inside the circuit. (i.e. in execution order)
        :param project_dir: directory where the manifest and the prover keys are located
        :param contract: contract of which the function which requires verification is part of
        :param function: the contract member function for which a proof needs to be generated
        :param priv_values: private/auxiliary circuit inputs in correct order
        :param in_vals: public circuit inputs in correct order
        :param out_vals: public circuit outputs in correct order
        :raise ProofGenerationError: if proof generation fails
        :return: the proof, serialized into an uint256 array
        """
        for i in range(len(priv_values)):
            arg = priv_values[i]
            assert not isinstance(arg, Value) or isinstance(arg, (RandomnessValue, AddressValue))
            if isinstance(arg, AddressValue):
                priv_values[i] = int.from_bytes(arg.val, byteorder='big')

        debug_print(f'Generating proof for {contract}.{function} [priv: {Value.collection_to_string(priv_values)}] '
                    f'[in: {Value.collection_to_string(in_vals)}] [out: {Value.collection_to_string(out_vals)}]')

        priv_values, in_vals, out_vals = Value.unwrap_values(Value.flatten(priv_values)), Value.unwrap_values(in_vals), Value.unwrap_values(out_vals)

        # Check for overflows
        for arg in priv_values + in_vals + out_vals:
            assert int(arg) < bn128_scalar_field, 'argument overflow'

        manifest = parse_manifest(project_dir)
        with time_measure(f'generate_proof_{contract}.{function}', True):
            return self._generate_proof(os.path.join(project_dir, f"{manifest[Manifest.verifier_names][f'{contract}.{function}']}_out"),
                                        priv_values, in_vals, out_vals)

    @abstractmethod
    def _generate_proof(self, verifier_dir: str, priv_values: List[int], in_vals: List[int], out_vals: List[int]) -> List[int]:
        pass

    @abstractmethod
    def get_prover_key_hash(self, verifier_directory: str) -> bytes:
        """Return the hash of the prover key stored in the given verification contract output directory."""
        pass
