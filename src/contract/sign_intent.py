import asyncio
import os
import json
import base58
import re
import base64
import random 
import httpx
import datetime
import traceback

from py_near.account import Account
from typing import Dict, Any
from src.worker.keypair import AgentWorker
from eth_utils import keccak
from src.tappd.tappd import AsyncTappdClient
from dotenv import load_dotenv

class SignIntentContract:
    def __init__(self, worker_public_key: str, worker_account_id: str = None, worker_signing_key: str = None, worker_account=None):
        load_dotenv()
        self.worker_account = worker_account
        self.worker_public_key = worker_public_key
        self.contract_id = os.getenv('SIGN_INTENT_CONTRACT')
        self.use_static_account = os.getenv('USE_STATIC_ACCOUNT', 'false').lower() == 'true'
        self._is_initialized = False
                
    async def startup(self):
        """Initialize contract if not already initialized"""
        try:
            if self._is_initialized:
                return
                
            if self.worker_account is None:
                raise ValueError("Worker account not provided")
                
            print("Contract ready to operate!")
            self._is_initialized = True
                
        except Exception as e:
            print(f"[ERROR] Failed to initialize contract: {str(e)}")
            print(f"[ERROR] Full error details: {traceback.format_exc()}")
            raise
    
    async def sign_quote(self, quote: str) -> Dict[str, Any]:
        """Send quote to contract for signing"""
        try:
            if self.worker_account is None:
                await self.startup()

            result = await self.worker_account.function_call(
                self.contract_id,
                "sign_trade",
                {
                    "quote": quote,
                },
                gas=300000000000000,
                amount=1000000000000000000000 
            )
            
            if hasattr(result, 'status'):
                success_value = result.status['SuccessValue']
                decoded_bytes = base64.b64decode(success_value)
                decoded_json = json.loads(decoded_bytes.decode('utf-8'))
                return {"result": decoded_json}
            
            return {"error": "No response data found"}
            
        except Exception as e:
            print(f"[LOG] Error calling sign_trade: {str(e)}")
            return {"error": str(e)} 
        
    async def register_worker(self):
        """Main registration method that decides which registration flow to use"""
        try:
            if self.worker_account is None:
                await self.startup()
                
            print(f"[LOG] Registering worker: {self.worker_account.account_id}")

            if self.use_static_account:
                # Use test registration if static account
                return await self.register_test()
            else:
                # Use production registration with Phala TEE
                return await self.register()

        except Exception as e:
            print(f"[ERROR] Failed to register worker: {str(e)}")
            return {"error": str(e)}

    async def register(self):
        """Register this worker agent in smart contract so that it can access restricted methods e.g. sign_trade"""
        try:

            if self.worker_account is None:
                await self.startup()

            print("[LOG] Starting worker registration process...")
            
            tcb_info_dict = await AsyncTappdClient().get_info()
            
            parsed_tcb_info = json.loads(tcb_info_dict["tcb_info"])
            
            tcb_info = json.dumps(parsed_tcb_info, ensure_ascii=False, separators=(',', ':'))

            random_num_string = str(random.random())

            quote_response = await AsyncTappdClient().tdx_quote(
                report_data=random_num_string,
                hash_algorithm='sha256'
            )
            
            quote_hex = quote_response.quote 
            
            files = {
                'hex': (None, quote_hex, 'text/plain')  # (filename, data, content_type)
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://proof.t16z.com/api/upload',
                    files=files,
                    headers={'Accept': 'application/json'}
                )
                response.raise_for_status()
                res_data = response.json()
                
                checksum = res_data['checksum']
                collateral = json.dumps(res_data['quote_collateral'])
        
            result = await self.worker_account.function_call(
                self.contract_id,
                "register_worker",
                {
                    "quote_hex": quote_hex,
                    "collateral": collateral,
                    "checksum": checksum,
                    "tcb_info": tcb_info,
                },
                gas=300000000000000,
            )
                       
            if hasattr(result, 'status'):
                if isinstance(result.status, dict):
                    if 'Failure' in result.status:
                        error_details = result.status['Failure']
                        print(f"[ERROR] Contract execution failed: {error_details}")
                        return {"success": False, "error": f"Contract error: {error_details}"}
                    elif 'SuccessValue' in result.status:
                        success_value = result.status['SuccessValue']
                        if success_value:
                            try:
                                decoded_bytes = base64.b64decode(success_value)
                                decoded_json = json.loads(decoded_bytes.decode('utf-8'))
                                return {"success": True, "result": decoded_json}
                            except Exception as e:
                                print(f"\n[ERROR] Failed to decode success value: {e}")
                                return {"success": False, "error": f"Failed to decode response: {e}"}
            
            return {"success": False, "error": "Registration failed - unexpected response format"}
            
        except Exception as e:
            print(f"[ERROR] Failed to register worker: {str(e)}")
            print(f"[ERROR] Full error details: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}
        
    async def generate_payload(self, quote: str) -> Dict[str, Any]:
        """Generate payload from quote"""
        try:
            if self.worker_account is None:
                await self.startup()

            quote_bytes = quote.encode('utf-8')
            quote_u8_list = list(quote_bytes)

            result = await self.worker_account.view_function(
                self.contract_id,
                "generate_payload",
                {"data": quote_u8_list}
            )
            
            if result.result and len(result.result) == 32:
                payload_hex = bytes(result.result).hex()
                return {
                    "result": {
                        "payload": payload_hex,
                        "raw_bytes": result.result
                    }
                }
            
            print(f"[LOG] Invalid result format: {result.result}")  
            return {"error": f"Invalid payload format. Got: {result.result}"}
                
        except Exception as e:
            print(f"[LOG] Error generating payload: {str(e)}")
            return {"error": str(e)} 
    
    async def register_test(self):
        """Register worker with test values"""
        try:
            print("[LOG] Using test registration values")
            
            checksum = "test_checksum"

            with open('samples/tcb_info.json', 'r') as file:
                tcb_info = json.load(file)

            with open('samples/quote_collateral.json', 'r') as file:
                quote_collateral = json.load(file)

            quote_hex = os.getenv('QUOTE_HEX')
            with open('samples/quote_hex.json', 'r') as file:
                quote_hex = json.load(file)

            result = await self.worker_account.function_call(
                self.contract_id,
                "register_worker",
                {
                    "quote_hex": quote_hex,
                    "collateral": json.dumps(quote_collateral),
                    "checksum": checksum,
                    "tcb_info": json.dumps(tcb_info)
                },
                gas=300000000000000
            )
            
            print(f"\n[LOG] Full transaction result: {result.__dict__}")
            
            if hasattr(result, 'logs') and result.logs:
                print(f"[LOG] Transaction logs:")
                for log in result.logs:
                    print(f"  - {log}")
                
            if hasattr(result, 'status'):
                print(f"\n[LOG] Transaction status: {result.status}")
                if isinstance(result.status, dict):
                    if 'Failure' in result.status:
                        error_details = result.status['Failure']
                        print(f"[ERROR] Contract execution failed: {error_details}")
                        return {"success": False, "error": f"Contract error: {error_details}"}
                    elif 'SuccessValue' in result.status:
                        success_value = result.status['SuccessValue']
                        if success_value:
                            try:
                                decoded_bytes = base64.b64decode(success_value)
                                decoded_json = json.loads(decoded_bytes.decode('utf-8'))
                                print("[LOG] Registration successful (TEST)")
                                return {"success": True, "result": decoded_json}
                            except Exception as e:
                                print(f"\n[ERROR] Failed to decode success value: {e}")
                                return {"success": False, "error": f"Failed to decode response: {e}"}
            
            return {"success": False, "error": "Registration failed - unexpected response format"}
            
        except Exception as e:
            print(f"[ERROR] Failed to register worker: {str(e)}")
            print(f"[ERROR] Full error details: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}
        
            
    async def initialize_worker(self):
        """Initialize and verify worker account"""
        try:
            # Initialize worker account
            await self.startup()
            
            try:
                result = await self.worker_account.view_function(
                    self.contract_id,
                    "get_worker",
                    {"account_id": self.worker_account.account_id}
                )
                
                return True
                    
            except Exception as e:
                error_message = str(e)
                
                if "worker not found" in error_message.lower() or "option::unwrap()" in error_message.lower():
                    print("\n[LOG] Worker not registered")
                    return False
                else:
                    print(f"[LOG] Unexpected error in get_worker: {error_message}")
                    raise  # Re-raise unexpected errors
                    
        except Exception as e:
            print(f"[LOG] Critical error in initialize_worker: {str(e)}")
            raise
        
            
                
                
        
