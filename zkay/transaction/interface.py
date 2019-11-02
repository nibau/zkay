import json
import os
from abc import ABCMeta, abstractmethod
from builtins import type
from typing import Tuple, List, Optional, Union, Any, Dict

from zkay.compiler.privacy.manifest import Manifest
from zkay.config import default_proving_scheme
from zkay.utils.timer import time_measure

__debug_print = True


def debug_print(*args):
    if __debug_print:
        print(*args)


class Value:
    def __init__(self, val):
        self.val = val

    def __str__(self):
        return f'{type(self).__name__}({self.val})'

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.val == other.val

    def __hash__(self):
        return self.val.__hash__()

    @staticmethod
    def unwrap_values(v: Union[int, bool, 'Value', List]) -> Union[int, List]:
        if isinstance(v, List):
            return list(map(Value.unwrap_values, v))
        else:
            return v.val if isinstance(v, Value) else v

    @staticmethod
    def list_to_string(v: Union[int, bool, 'Value', List]) -> str:
        if isinstance(v, List):
            return f"[{', '.join(map(Value.list_to_string, v))}]"
        else:
            return str(v)


class CipherValue(Value):
    pass


class PrivateKeyValue(Value):
    pass


class PublicKeyValue(Value):
    pass


class RandomnessValue(Value):
    pass


class AddressValue(Value):
    def __init__(self, val: str):
        super().__init__(val)


class KeyPair:
    def __init__(self, pk: PublicKeyValue, sk: PrivateKeyValue):
        self.pk = pk
        self.sk = sk


def parse_manifest(project_dir: str):
    with open(os.path.join(project_dir, 'manifest.json')) as f:
        j = json.loads(f.read())
        j[Manifest.project_dir] = project_dir
    return j


class ZkayBlockchainInterface(metaclass=ABCMeta):
    @property
    def my_address(self) -> AddressValue:
        #debug_print(f'Requesting own address ("{self._my_address().val}")')
        return self._my_address()

    def pki_verifier_addresses(self, project_dir: str) -> Dict[str, AddressValue]:
        return self._pki_verifier_addresses(parse_manifest(project_dir))

    def req_public_key(self, address: AddressValue) -> PublicKeyValue:
        assert isinstance(address, AddressValue)
        debug_print(f'Requesting public key for address "{address.val}"')
        return self._req_public_key(address)

    def announce_public_key(self, address: AddressValue, pk: PublicKeyValue):
        assert isinstance(address, AddressValue)
        assert isinstance(pk, PublicKeyValue)
        debug_print(f'Announcing public key "{pk.val}" for address "{address.val}"')
        self._announce_public_key(address, pk)

    def req_state_var(self, contract_handle, name: str, *indices) -> Union[bool, int, str]:
        assert contract_handle is not None
        debug_print(f'Requesting state variable "{name}"')
        val = self._req_state_var(contract_handle, name, *Value.unwrap_values(list(indices)))
        debug_print(f'Got value {val} for state variable "{name}"')
        return val

    def transact(self, contract_handle, function: str, actual_args: List, should_encrypt: List[bool]) -> Any:
        assert contract_handle is not None
        self.__check_args(actual_args, should_encrypt)
        debug_print(f'Issuing transaction for function "{function}"{Value.list_to_string(actual_args)})')
        return self._transact(contract_handle, function, *Value.unwrap_values(actual_args))

    def deploy(self, project_dir: str, contract: str, actual_args: List, should_encrypt: List[bool]) -> Any:
        self.__check_args(actual_args, should_encrypt)
        debug_print(f'Deploying contract {contract}[{Value.list_to_string(actual_args)}]')
        return self._deploy(parse_manifest(project_dir), contract, *Value.unwrap_values(actual_args))

    def connect(self, project_dir: str, contract: str, address: AddressValue) -> Any:
        debug_print(f'Connecting to contract {contract}@{address.val}')
        return self._connect(parse_manifest(project_dir), contract, address.val)

    @abstractmethod
    def _my_address(self) -> AddressValue:
        pass

    @abstractmethod
    def _pki_verifier_addresses(self, manifest) -> Dict[str, AddressValue]:
        pass

    @abstractmethod
    def _req_public_key(self, address: AddressValue) -> PublicKeyValue:
        pass

    @abstractmethod
    def _announce_public_key(self, address: AddressValue, pk: PublicKeyValue) -> PublicKeyValue:
        pass

    @abstractmethod
    def _req_state_var(self, contract_handle, name: str, *indices) -> Union[bool, int, str]:
        pass

    @abstractmethod
    def _transact(self, contract_handle, function: str, *actual_args) -> Any:
        pass

    @abstractmethod
    def _deploy(self, manifest, contract: str, *actual_args) -> Any:
        pass

    @abstractmethod
    def _connect(self, manifest, contract: str, address: str) -> Any:
        pass

    @staticmethod
    def __check_args(actual_args: List, should_encrypt: List[bool]):
        assert len(actual_args) == len(should_encrypt)
        for idx, arg in enumerate(actual_args):
            assert not isinstance(arg, PrivateKeyValue) and not isinstance(arg, RandomnessValue)
            assert should_encrypt[idx] == isinstance(arg, CipherValue)


class ZkayCryptoInterface(metaclass=ABCMeta):
    def __init__(self, conn: ZkayBlockchainInterface, key_dir: str = os.path.dirname(os.path.realpath(__file__))):
        self.key_dir = key_dir
        self.__my_keys = self._generate_or_load_key_pair()
        conn.announce_public_key(conn.my_address, self.local_keys.pk)

    @property
    def local_keys(self):
        return self.__my_keys

    def enc(self, plain: int, pk: PublicKeyValue, rnd: Optional[RandomnessValue] = None) -> Tuple[CipherValue, RandomnessValue]:
        """
        Encrypts plain with the provided public key
        :param plain: plain text to encrypt
        :param pk: public key
        :param rnd: if specified, this particular randomness will be used for encryption
        :return: Tuple(cipher text, randomness which was used to encrypt plain)
        """
        assert not isinstance(plain, Value), f"Tried to encrypt value of type {type(plain).__name__}"
        assert isinstance(pk, PublicKeyValue), f"Tried to use public key of type {type(pk).__name__}"
        debug_print(f'Encrypting value {plain} with public key "{pk.val}"')
        cipher, rnd = self._enc(int(plain), pk.val, None if rnd is None else rnd.val)
        if cipher == 0:
            raise Exception("Encryption resulted in cipher text 0 which is a reserved value. Please try again.")
        return CipherValue(cipher), RandomnessValue(rnd)

    def dec(self, cipher: CipherValue, sk: PrivateKeyValue) -> Tuple[int, RandomnessValue]:
        """
        Decrypts cipher with the provided secret key
        :param cipher: encrypted value
        :param sk: secret key
        :return: Tuple(plain text, randomness which was used to encrypt plain)
        """
        assert isinstance(cipher, CipherValue), f"Tried to decrypt value of type {type(cipher).__name__}"
        assert isinstance(sk, PrivateKeyValue), f"Tried to use private key of type {type(sk).__name__}"
        debug_print(f'Decrypting value {cipher.val} with secret key "{sk.val}"')
        plain, rnd = self._dec(cipher.val, sk.val)
        return plain, RandomnessValue(rnd)

    @abstractmethod
    def _generate_or_load_key_pair(self) -> KeyPair:
        pass

    @abstractmethod
    def _enc(self, plain: int, pk: int, rnd: Optional[int]) -> Tuple[int, int]:
        pass

    @abstractmethod
    def _dec(self, cipher: int, sk: int) -> Tuple[int, int]:
        pass


class ZkayKeystoreInterface:
    def __init__(self, conn: ZkayBlockchainInterface, crypto: ZkayCryptoInterface):
        self.conn = conn
        self.local_pk_store: Dict[AddressValue, PublicKeyValue] = {}
        self.my_keys = crypto.local_keys

        self.local_pk_store[conn.my_address] = self.my_keys.pk

    def getPk(self, address: AddressValue) -> PublicKeyValue:
        assert isinstance(address, AddressValue)
        debug_print(f'Requesting public key for address {address.val}')
        if address in self.local_pk_store:
            return self.local_pk_store[address]
        else:
            pk = self.conn.req_public_key(address)
            self.local_pk_store[address] = pk
            return pk

    @property
    def sk(self) -> PrivateKeyValue:
        return self.my_keys.sk

    @property
    def pk(self) -> PublicKeyValue:
        return self.my_keys.pk


class ZkayProverInterface(metaclass=ABCMeta):
    def __init__(self, proving_scheme: str = default_proving_scheme):
        self.proving_scheme = proving_scheme

    def generate_proof(self, project_dir: str, contract: str, function: str, priv_values: List[int], in_vals: List, out_vals: List[Union[int, CipherValue]]) -> List[int]:
        for arg in priv_values:
            assert not isinstance(arg, Value) or isinstance(arg, RandomnessValue)
        manifest = parse_manifest(project_dir)
        debug_print(f'Generating proof for {contract}.{function}')
        with time_measure(f'generate_proof_{contract}.{function}', True):
            return self._generate_proof(os.path.join(project_dir, manifest[Manifest.verifier_names][f'{contract}.{function}']),
                                        Value.unwrap_values(priv_values), Value.unwrap_values(in_vals), Value.unwrap_values(out_vals))

    @abstractmethod
    def _generate_proof(self, verifier_dir: str, priv_values: List[int], in_vals: List[int], out_vals: List[int]) -> List[int]:
        pass