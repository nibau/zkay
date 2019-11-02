from typing import Tuple, Optional

from zkay.transaction.interface import PrivateKeyValue, PublicKeyValue, KeyPair
from zkay.transaction.interface import ZkayCryptoInterface
from zkay.compiler.privacy.library_contracts import bn128_scalar_field


class DummyCrypto(ZkayCryptoInterface):

    def _generate_or_load_key_pair(self) -> KeyPair:
        return KeyPair(PublicKeyValue(42), PrivateKeyValue(42))

    def _enc(self, plain: int, pk: int, rnd: Optional[int]) -> Tuple[int, int]:
        if rnd is not None:
            assert rnd == 69, f'rnd was {rnd}'
        cipher = (plain + pk) % bn128_scalar_field
        return cipher, 69

    def _dec(self, cipher: int, sk: int) -> Tuple[int, int]:
        if cipher == 0:
            # uninitialized value
            plain = cipher
        else:
            plain = (cipher - sk) % bn128_scalar_field
        return plain, 69