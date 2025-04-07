from py_near.account import Account
from near_api.signer import KeyPair
from src.tappd.tappd import TappdClient
from nacl.signing import SigningKey
from nacl.encoding import RawEncoder
import secrets
import hashlib
import os
import base58

class AgentWorker:
    def __init__(self):
        self.use_static_account = os.getenv('USE_STATIC_ACCOUNT', 'false').lower() == 'true'
        self.account_id = os.getenv('AGENT_ID') if self.use_static_account else None
        self.signing_key = os.getenv('AGENT_KEY') if self.use_static_account else None
        self.account = None
        self.public_key = None
        if self.use_static_account:
            keypair = KeyPair(self.signing_key)
            self.public_key = keypair._public_key

    async def initialize_account(self, account_id, signing_key, network):
        """Initialize NEAR account instance"""
        if self.account is None:
            if not signing_key.startswith("ed25519:"):
                signing_key = f"ed25519:{signing_key}"
            
            self.account = Account(
                account_id,
                signing_key,  
                self.get_provider(network)
            )
            await self.account.startup()

    def get_provider(self, network):
        if network == 'testnet':
            return 'https://rpc.testnet.near.org'
        else:
            return 'https://rpc.mainnet.near.org'
            
    def derive_ephemeral_account(self):
        """Generate ephemeral account using TEE entropy"""
        print(f"\n Deriving ephemeral account")
        
        client = TappdClient()
        
        random_array = secrets.token_bytes(32) 
        random_string = random_array.hex()
        key_from_tee = client.derive_key(random_string, random_string)
        
        tee_bytes = key_from_tee.toBytes(32)
        combined = random_array + tee_bytes
        
        hash_bytes = hashlib.sha256(combined).digest()
        signing_key = SigningKey(seed=hash_bytes, encoder=RawEncoder)
        verify_key = signing_key.verify_key
        secret_key_bytes = signing_key.encode() + verify_key.encode()
        secret_key = base58.b58encode(secret_key_bytes).decode('utf-8')

        keypair = KeyPair(secret_key)

        self.signing_key = secret_key     
        self.public_key = keypair._public_key
        
        # Generate implicit account ID from public key
        self.account_id = self.get_implicit_account_id()
        
        print(f"Created ephemeral account: {self.account_id}")
        return self.account_id, self.signing_key

    def get_implicit_account_id(self):
        """Convert public key to implicit account ID
        Returns a 64-character lowercase hex string for use as an implicit account
        """
        if not self.public_key:
            raise ValueError("Public key not initialized")
        
        if isinstance(self.public_key, str):
            base58_key = self.public_key.split(':')[1]
            public_key_bytes = base58.b58decode(base58_key)
        else:
            public_key_bytes = self.public_key.to_bytes()
        
        implicit_account = public_key_bytes.hex().lower()
        
        if len(implicit_account) != 64:
            raise ValueError(f"Invalid public key length. Expected 64 chars, got {len(implicit_account)}")
        
        return implicit_account
