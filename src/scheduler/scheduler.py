import subprocess
import time
import os
import json
import asyncio
import base58
import base64
import hashlib
import binascii
import near_api
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

from hashlib import sha256
from coincurve import PublicKey
from datetime import datetime
from dotenv import load_dotenv
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError, util
from ecdsa.util import sigdecode_string, sigdecode_der
from typing import Dict, Any
from eth_keys import keys
from eth_utils import decode_hex
from near_api.providers import JsonProvider, JsonProviderError

from src.worker.keypair import AgentWorker
from src.quote.generate_quote import process_llm_suggestion
from src.contract.sign_intent import SignIntentContract
from src.quote.generate_quote import create_commitment_from_mpc_signature_using_rsv
from src.quote.generate_quote import publish_intent
from src.quote.generate_quote import PublishIntent
from src.constants import AGENT_PATH
load_dotenv(override=True)

class MindshareScheduler:
    def __init__(self, interval=300):
        self.interval = interval
        self.agent_path = AGENT_PATH
        self.api_key = os.getenv('KAITO_API_KEY')
        self.account_id = os.getenv('INTENT_ACCOUNT_ID')
        self.private_key = os.getenv('INTENT_PRIVATE_KEY')
        self.network = os.getenv('NETWORK')
        self.worker = AgentWorker()
        self.sign_contract = None 
        self.setup_logging()

    def setup_logging(self):
        """Setup logging configuration"""
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Get current date for filename
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Configure file handler with daily rotation
        file_handler = TimedRotatingFileHandler(
            f'logs/mindshare.{current_date}.log',
            when='midnight',     # Rotate at midnight
            interval=1,          # Rotate every day
            backupCount=2,       # Keep 2 backups
            encoding='utf-8'
        )
        
        # Configure logging format
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Setup root logger
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)  
        self.logger.addHandler(file_handler)

    async def setup(self, max_attempts=3, retry_delay=10):
        """Initialize everything in the correct order with retries"""
        self.logger.info("Setting up mindshare agent...")
        for attempt in range(max_attempts):
            try:
                account_id = None
                signing_key = None
                
                if not self.worker.use_static_account:
                    print(f"\nSetting up ephemeral account (Attempt {attempt + 1}/{max_attempts})")
                    account_id, signing_key = self.worker.derive_ephemeral_account()
                    self.logger.debug(f"Ephemeral account created: {account_id}")
                    funded = await self.wait_for_funds(timeout=300)
                    if not funded:
                        print("[ERROR] Account funding timeout reached")
                        if attempt < max_attempts - 1:
                            print(f"[LOG] Retrying setup in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            continue
                        raise Exception("Failed to fund account after all attempts")
                else:
                    account_id = self.worker.account_id
                    signing_key = self.worker.signing_key
                
                await self.worker.initialize_account(account_id, signing_key, self.network)
                
                if self.sign_contract is None:
                    self.sign_contract = SignIntentContract(
                        worker_public_key=self.worker.public_key,
                        worker_account_id=self.worker.account_id,
                        worker_signing_key=self.worker.signing_key,
                        worker_account=self.worker.account  
                    )
                    await self.sign_contract.startup()
                
                registration_success = await self.register_worker(max_attempts=3, retry_delay=10)
                self.logger.info(f"Worker registration result: {registration_success}")
                if registration_success:
                    print("Setup completed successfully")
                    return True
                    
            except Exception as e:
                print(f"[ERROR] Setup attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_attempts - 1:
                    print(f"[LOG] Retrying setup in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    raise Exception(f"Setup failed after {max_attempts} attempts: {str(e)}")
        
        return False

    def get_rpc(self):
        if self.network == 'mainnet':
            return 'https://rpc.mainnet.near.org'
        else:
            return 'https://rpc.testnet.near.org'

    async def wait_for_funds(self, timeout=300, check_interval=10):
        """Wait for account to be funded with timeout"""
        self.logger.info("Waiting for funds...")
        start_time = time.time()

        rpc = self.get_rpc()
        provider = JsonProvider(rpc)

        while time.time() - start_time < timeout:
            try:
                # Get account state directly from provider
                account_state = provider.get_account(self.worker.account_id)
                amount = int(account_state['amount']) / 10**24  # Convert yoctoNEAR to NEAR
                
                if amount > 0:
                    print(f"\nFunds detected! Available balance: {amount} NEAR")
                    return True
                    
                print(f"Waiting for funds... (timeout in {int(timeout - (time.time() - start_time))}s)")
            except JsonProviderError as e:
                # This will happen if account doesn't exist yet - this is expected
                if "does not exist" in str(e):
                    print(f"Account doesn't exist yet. Waiting for first transfer...")
                else:
                    print(f"[LOG] Error checking balance: {str(e)}")
            
            await asyncio.sleep(check_interval)
        return False
    
    async def register_worker(self, max_attempts=3, retry_delay=10):
        """Register worker with retries"""
        self.logger.info("Registering worker...")
        for attempt in range(max_attempts):
            try:
                is_registered = await self.sign_contract.initialize_worker()
                if is_registered:
                    print("Worker already registered")
                    return True
                    
                print("Attempting worker registration...")
                registration_result = await self.sign_contract.register_worker()
                
                if registration_result.get("success"):
                    print("Worker registration successful")
                    return True
                else:
                    print(f"[ERROR] Registration failed: {registration_result.get('error')}")
                    if attempt < max_attempts - 1:
                        print(f"Retrying registration in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        
            except Exception as e:
                print(f"[ERROR] Registration attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_attempts - 1:
                    print(f"Retrying registration in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    
        return False

    async def start(self):
        """Start the scheduler after setup"""
        self.logger.info("Starting scheduler...")
        try:
            setup_success = await self.setup()
            if not setup_success:
                raise Exception("Failed to complete setup")
                
            while True:
                try:
                    await self.execute_with_worker()
                    await asyncio.sleep(self.interval)
                except KeyboardInterrupt:
                    print("\nManual stop of scheduler")
                    break
                except Exception as e:
                    print(f"Critical error in scheduler: {str(e)}")
                    await asyncio.sleep(10)
        except Exception as e:
            print(f"Fatal error in scheduler: {str(e)}")
            raise

    async def execute_with_worker(self):
        """Main execution flow"""
        try:
            await self.execute_agent()
                
        except Exception as e:
            print(f"[ERROR] Error in worker execution: {str(e)}")

    async def sign_quotes(self, response):
        """Sign each quote in the response"""
        self.logger.info("Signing quotes...")
        if not response.get('success'):
            return response
            
        try:
            execution_results = response.get('execution_results', [])
            
            for result in execution_results:
                inner_response = result.get('response', {})
                inner_execution_results = inner_response.get('execution_results', [])
                
                if inner_execution_results and len(inner_execution_results) > 0:
                    quote_data = inner_execution_results[0]
                    quote = quote_data.get('quote')
                    quote_hash = quote_data.get('quote_hash')
                    
                    if not quote:
                        print("[LOG] No quote found in nested result")
                        continue
                    
                    try:
                        sign_result = await self.sign_contract.sign_quote(quote)
                        if "result" in sign_result:
                            new_format_quote = format_erc191_message(quote)
                            payload_response = await self.sign_contract.generate_payload(new_format_quote)
                            
                            result['sign_result'] = sign_result
                            result['quote_hash'] = quote_hash
                            result['payload'] = payload_response
                        else:
                            print(f"[LOG] Error signing quote: {sign_result.get('error')}")
                            continue
                          
                    except Exception as e:
                        print(f"[LOG] Error processing quote: {str(e)}")
                        continue
            
            return response
            
        except Exception as e:
            print(f"[LOG] Error in sign_quotes: {str(e)}")
            return {"error": str(e), "original_response": response}

    async def execute_agent(self):
        """Execute agent with retries if no trades are found"""
        self.logger.info("Executing mindshare agent...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"\nExecuting mindshare agent... (Attempt {attempt + 1}/{max_retries})")
                self.logger.debug(f"\nExecuting mindshare agent... (Attempt {attempt + 1}/{max_retries})")
                env_vars = {
                    "KAITO_API_KEY": self.api_key,
                    "ACCOUNT_ID": self.account_id,
                    "PRIVATE_KEY": self.private_key,
                    "NETWORK": self.network,
                    "DEBUG": "false"
                }
                
                command = [
                    "nearai",
                    "agent",
                    "task",
                    self.agent_path,
                    "According to my current token balances, evaluate the mindshare of them, suggest me trading decision (hold, sell, buy) and how to rebalance my portfolio, remember that the user's balance is limited and you need to consider the fees.",
                    "--local",
                    "--env_vars",  
                    json.dumps(env_vars)  
                ]
                
                #print("\n[LOG] Executing command:", " ".join(command))
                
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("\nAgent executed successfully")

                    #print(f"\n[LOG] Result FROM LLM: {result.stdout}")
                    self.logger.debug(f"\nResult FROM LLM: {result.stdout}")
                    
                    balances = {}
                    for line in result.stdout.split('\n'):
                        if line.startswith('Retrieved balances:'):
                            balances_str = line.replace('Retrieved balances: ', '')
                            balances = eval(balances_str) 
                            break
                    
                    if not balances:
                        print("\n[LOG] No balances found, retrying...")
                        continue
                    
                    response = process_llm_suggestion(
                        self.account_id,
                        result.stdout, 
                        balances
                    )
                    
                    self.logger.debug(f"\nResponse from process_llm_suggestion: {response}\n")
                    
                    #response = {'error': 'No trades found in LLM response'}
                    
                    if "error" in response:
                        print(f"\n[LOG] Error processing trades: {response['error']}")
                        if attempt < max_retries - 1:
                            print(f"\n[LOG] Retrying... ({attempt + 2}/{max_retries})")
                            time.sleep(2)
                            continue
                        else:
                            stdout_lines = result.stdout.split('\n')
                            last_response = ""
                            for line in reversed(stdout_lines):
                                if line.startswith("Assistant: <|start_header_id|>assistant<|end_header_id|>"):
                                    start_idx = stdout_lines.index(line) + 1
                                    last_response = "\n".join(stdout_lines[start_idx:])
                                    break
                            if last_response:
                                print("\nNo trades could be processed automatically. Here is the AI suggestion for manual trading:")
                                print(last_response)
                    elif response.get('success', False):
                        print("\nTrades obtained successfully, obtaining MPC signature...")
                    
                        sign_response = await self.sign_quotes(response)
                        
                        for result in sign_response.get('execution_results', []):
                            quote = result.get('response', {}).get('execution_results', [])[0].get('quote') if result.get('response', {}).get('execution_results') else None
                            quote_hash = result.get('response', {}).get('execution_results', [])[0].get('quote_hash') if result.get('response', {}).get('execution_results') else []
                            
                            if isinstance(quote, dict):
                                quote = json.dumps(quote)
                            
                            sign_result = result.get('sign_result')
                            payload = result.get('payload')
                            
                            if sign_result and isinstance(sign_result, dict):
                                if 'result' in sign_result:
                                    signature_data = sign_result['result']
                        
                                    print("\nSignature received from MPC contract, verifying signature...")
                                   
                                    is_valid =  verify_signature(payload, signature_data) 
                                    self.logger.debug(f"\nSignature verification result: {is_valid}")
                                    if is_valid:
                                        commitment_rsv = create_commitment_from_mpc_signature_using_rsv(
                                            quote=quote,  
                                            signature=signature_data
                                        )
                                        
                                        print(f"\nPublishing intent...")
                                        print("Response from publish_intent: ", publish_intent(commitment_rsv, quote_hash))
                                        self.logger.debug(f"\nResponse from publish_intent: {publish_intent(commitment_rsv, quote_hash)}")
                                        
                                elif 'error' in sign_result:
                                    error_str = str(sign_result['error'])
                                    if "TIMEOUT_ERROR" in error_str:
                                        print("[LOG] Timeout detected in RPC response...")
                                        print("[LOG] Transaction might be successful, check the block explorer")
                                        return response
                                    else:
                                        print(f"[LOG] Error signing quote: {sign_result['error']}")
                                        continue
                        break  # Exit retry loop on success
                    else:
                        print("\n[LOG] No trades were executed successfully")
                        if attempt < max_retries - 1:
                            print(f"\n[LOG] Retrying... ({attempt + 2}/{max_retries})")
                            time.sleep(2)
                            continue
                else:
                    print(f"\n[LOG] Error executing agent: {result.stderr}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                
            except Exception as e:
                print(f"\n[LOG] Error in execute_agent: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"\n[LOG] Retrying... ({attempt + 2}/{max_retries})")
                    time.sleep(2)
                    continue
        
        if attempt == max_retries:
            print(f"\n[LOG] Failed to execute trades after {max_retries} attempts")
    
def format_erc191_message(quote: str) -> str:
    """Format message according to ERC-191"""
    quote_data = quote.encode('utf-8')
    quote_len = len(quote_data)
    
    prefix = b"\x19Ethereum Signed Message:\n" + str(quote_len).encode('utf-8')
    message = prefix + quote_data
    
    return message.decode('utf-8', errors='replace')

def near_to_eth_public_key(near_public_key: str) -> bytes:
    stripped_key = near_public_key.split(':')[1]
    decoded_key = base58.b58decode(stripped_key)
    return decoded_key[:-2]

def verify_signature(payload: dict, signature: dict) -> bool:
    """Verify signature of payload"""
    # Get SIGNER_PUBLIC_KEY from environment variables
    SIGNER_PUBLIC_KEY = os.getenv('SIGNER_PUBLIC_KEY_USING_MINDSHARE_ACCOUNT')
    if not SIGNER_PUBLIC_KEY:
        raise ValueError("SIGNER_PUBLIC_KEY environment variable is not set")
    
    payload_hex = payload['result']['payload']

    v = signature['recovery_id']
    big_r_hex = signature['big_r']['affine_point'][2:]  
    r = int(big_r_hex, 16)
    s = int(signature['s']['scalar'], 16)
    
    sig = keys.Signature(vrs=(v, r, s))
    
    message_hash = decode_hex(payload_hex)
    
    recovered_public_key = sig.recover_public_key_from_msg_hash(message_hash)

    public_key = "secp256k1:" + base58.b58encode(recovered_public_key.to_bytes()).decode('utf-8')
    
    if public_key == SIGNER_PUBLIC_KEY:
        return True
    else:
        return False

def validate_env_vars():
    """Validate all required environment variables are set"""
    
    required_vars = {
        # Scheduler vars
        'KAITO_API_KEY': 'API key for Kaito service',
        'INTENT_ACCOUNT_ID': 'Account ID for intents',
        'INTENT_PRIVATE_KEY': 'Private key for intents',
        'NETWORK': 'Network to use (mainnet/testnet)',
        'SCHEDULE_INTERVAL': 'Interval for scheduler execution',
        'USE_MOCK_MINDSHARE': 'Whether to use mock mindshare',
        # Contract vars
        'SIGN_INTENT_CONTRACT': 'Contract ID for signing intents',
        'USE_STATIC_ACCOUNT': 'Whether to use static account',
        'SIGNER_PUBLIC_KEY_USING_MINDSHARE_ACCOUNT': 'Public key for signature verification',
    }
    
    missing_vars = []
    
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"- {var}: {description}")
    
    use_static = os.getenv('USE_STATIC_ACCOUNT', '').lower() == 'true'
    if use_static:
        static_account_vars = {
            'AGENT_ID': 'Agent account ID (required when USE_STATIC_ACCOUNT is true)',
            'AGENT_KEY': 'Agent private key (required when USE_STATIC_ACCOUNT is true)'
        }
        for var, description in static_account_vars.items():
            if not os.getenv(var):
                missing_vars.append(f"- {var}: {description}")
            
    if missing_vars:
        error_msg = "Missing required environment variables:\n" + "\n".join(missing_vars)
        raise ValueError(error_msg)
        
    # Additional type/format validations
    try:
        int(os.getenv('SCHEDULE_INTERVAL'))
    except ValueError:
        raise ValueError("SCHEDULE_INTERVAL must be a valid integer")
        
    if os.getenv('NETWORK') not in ['mainnet', 'testnet']:
        raise ValueError("NETWORK must be either 'mainnet' or 'testnet'")
        
    if os.getenv('USE_STATIC_ACCOUNT').lower() not in ['true', 'false']:
        raise ValueError("USE_STATIC_ACCOUNT must be either 'true' or 'false'")


def main():
    print("\nStarting Scheduler...")
    
    # Validate environment variables
    try:
        validate_env_vars()
    except ValueError as e:
        print(f"[ERROR] Environment validation failed:\n{str(e)}")
        return
    
    interval = int(os.getenv('SCHEDULE_INTERVAL', '300'))
    scheduler = MindshareScheduler(interval=interval)
    
    # Create a single event loop for the entire application
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(scheduler.start())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
