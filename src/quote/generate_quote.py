from typing import List, Dict, TypedDict, Union
from near_api.account import Account
from eth_keys import keys
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from src.constants import ASSET_MAP

import re
import near_api
import os
import requests
import json
import base64
import random
import base58
import time

SOLVER_BUS_URL = "https://solver-relay-v2.chaindefuser.com/rpc"

class Trade(TypedDict):
    token_in: str
    amount_in: float
    token_out: str

class Intent(TypedDict):
    intent: str
    diff: Dict[str, str]

class Quote(TypedDict):
    nonce: str
    signer_id: str
    verifying_contract: str
    deadline: str
    intents: List[Intent] 

class AcceptQuote(TypedDict):
    nonce: str
    recipient: str
    message: str

class Commitment(TypedDict):
    standard: str
    payload: Union[AcceptQuote, str]
    signature: str

class PublishIntent(TypedDict):
    signed_data: Commitment
    quote_hashes: List[str] = []

class IntentRequest(object):
    """IntentRequest is a request to perform an action on behalf of the user."""
    
    def __init__(self, request=None, thread=None, min_deadline_ms=60000):
        self.request = request
        self.thread = thread
        self.min_deadline_ms = min_deadline_ms

    def asset_in(self, asset_name, amount):
        self.asset_in = {"asset": get_asset_id(asset_name), "amount": to_decimals(amount, ASSET_MAP[asset_name]['decimals'])}
        return self

    def asset_out(self, asset_name, amount=None):
        self.asset_out = {"asset": get_asset_id(asset_name), "amount": to_decimals(amount, ASSET_MAP[asset_name]['decimals']) if amount else None}
        return self

    def serialize(self):
        message = {
            "defuse_asset_identifier_in": self.asset_in["asset"],
            "defuse_asset_identifier_out": self.asset_out["asset"],
            "exact_amount_in": str(self.asset_in["amount"]),
            "exact_amount_out": str(self.asset_out["amount"]),
            "min_deadline_ms": self.min_deadline_ms,
        }
        if self.asset_in["amount"] is None:
            del message["exact_amount_in"]
        if self.asset_out["amount"] is None:
            del message["exact_amount_out"]
        return message


def get_asset_id(token):
    if token == 'NEAR':
        return 'nep141:' + ASSET_MAP[token]['token_id']
    else:
        return ASSET_MAP[token]['token_id']

def parse_llm_response(response: str, balances: Dict[str, float]) -> List[Trade]:
    """Parse LLM response to extract trade information using actual balances"""
    trades = []
    
    cleaned_response = '\n'.join(line.rstrip() for line in response.split('\n'))
    
    trade_patterns = re.finditer(
        r"(?:^|\n)"                                                     # Start of line or newline
        r"(?:\s*(?:Assistant:)?\s*)?"                                  # Optional "Assistant:" with spaces
        r"(?:\s*\d+[\.\)]\s*)?"                                       # Optional numbering (1. or 1))
        r"(?:\s*[-\*]+\s*)?"                                          # Optional dashes or asterisks
        r"(?:TRADE:?(?:\s*\d+)?:?)"                                   # TRADE header with optional number
        r"(?:\s*[-\*]+\s*)?\s*\n"                                     # Optional decorators and newline
        r"(?:\s*[-\*]?\s+)?(?:[-\*]\s+)?token_in\s*:\s*(\w+(?:\s*\+\s*\w+)?)\s*\n"  # token_in with all possible decorators
        r"(?:\s*[-\*]?\s+)?(?:[-\*]\s+)?amount_in\s*:\s*(\d+)\s*%?\s*of\s*(?:current\s*)?balance\s*\(([0-9.]+)\)\s*\n"  # amount_in with all possible decorators
        r"(?:\s*[-\*]?\s+)?(?:[-\*]\s+)?token_out\s*:\s*(\w+|[Nn]one)",  # token_out with all possible decorators
        cleaned_response,
        re.MULTILINE | re.IGNORECASE | re.DOTALL
    )
    
    for match in trade_patterns:
        try:
            token_in = match.group(1).strip()
            percentage = int(match.group(2).strip())
            amount_str = match.group(3).strip()
            token_out = match.group(4).strip()
            
            if token_out.lower() == 'none':
                continue
            
            if token_in not in ASSET_MAP or token_out not in ASSET_MAP:
                print(f"[LOG] Skipping trade with unsupported tokens: {token_in} -> {token_out}")
                continue
            
            amount_in = float(amount_str)
            
            if '+' in token_in:
                tokens = [t.strip() for t in token_in.split('+')]
                for single_token in tokens:
                    if single_token in balances:
                        amount = (balances[single_token] * percentage) / 100
                        trades.append({
                            "token_in": single_token,
                            "amount_in": amount,
                            "token_out": token_out
                        })
            else:
                trades.append({
                    "token_in": token_in,
                    "amount_in": amount_in,
                    "token_out": token_out
                })
                
        except Exception as e:
            
            continue
    
    if not trades:
        print("[LOG] No trades were parsed successfully")
    return trades

def execute_trades(account: Account, trades: List[Trade]):
    """Execute trades suggested by LLM"""
    responses = []
    for trade in trades:
        try:

            if trade['amount_in'] > 0:
                print(f"\nProcessing trade: {trade['amount_in']} {trade['token_in']} -> {trade['token_out']}")
            
                response = intent_swap(
                    account,
                    trade["token_in"],
                    trade["amount_in"],
                    trade["token_out"]
                )
            
                responses.append({
                    "trade": trade,
                    "response": response
                })
            
        except Exception as e:
            print(f"Error executing trade: {str(e)}")
            responses.append({
                "trade": trade,
                "error": str(e)
            })
    
    return responses

def process_llm_suggestion(account_id: str, llm_response: str, balances: Dict[str, float]):
    """Process LLM suggestion and execute trades"""
    try:
        trades = parse_llm_response(llm_response, balances)
        if not trades:
            return {"error": "No trades found in LLM response"}
            
        responses = execute_trades(account_id, trades)
        
        all_failed = all('error' in r for r in responses)
        if all_failed:
            return {
                "error": "All trades failed to execute",
                "trades": trades,
                "execution_results": responses
            }
        
        return {
            "success": not all_failed,
            "trades": trades,
            "execution_results": responses
        }
        
    except Exception as e:
        return {"error": f"Error processing trades: {str(e)}"}
    
def intent_swap(account_id: Account, token_in: str, amount_in: float, token_out: str):
    
    actual_token_in = 'WNEAR' if token_in == 'NEAR' else token_in
    amount_in_yocto = to_decimals(amount_in, ASSET_MAP[token_in]['decimals'])

    request = IntentRequest().asset_in(actual_token_in, amount_in).asset_out(token_out)
    
    options = fetch_options(request)

    if not options:
        raise Exception("No options returned from solver bus")
    
    
    best_option = select_best_option(options)
    
    quote = create_token_diff_quote(account_id, token_in, str(request.asset_in["amount"]), token_out, best_option['amount_out'])
    
    return {
            "success": True,
            "execution_results": [{
                "quote": quote,
                "quote_hash": best_option['quote_hash']
            }]
        }

def fetch_options(request):
    """Fetches the trading options from the solver bus."""
    rpc_request = {
        "id": "dontcare",
        "jsonrpc": "2.0",
        "method": "quote",
        "params": [request.serialize()]
    }
    response = requests.post(SOLVER_BUS_URL, json=rpc_request)
    return response.json().get("result", [])

def select_best_option(options):
    """Selects the best option from the list of options."""
    best_option = None
    for option in options:
        if not best_option or option["amount_out"] < best_option["amount_out"]:
            best_option = option
    return best_option

def to_decimals(amount, decimals):

    try:
        amount = Decimal(str(amount))
        multiplier = Decimal('10') ** decimals
        
        result = (amount * multiplier).quantize(Decimal('1'), rounding=ROUND_DOWN)
        
        return str(result)
    except Exception as e:
        print(f"Error in to_decimals - amount: {amount}, decimals: {decimals}")
        raise


def create_token_diff_quote(account_id, token_in, amount_in, token_out, amount_out):
    token_in_fmt = get_asset_id(token_in)
    token_out_fmt = get_asset_id(token_out)
    nonce = base64.b64encode(random.getrandbits(256).to_bytes(32, byteorder='big')).decode('utf-8')
    quote = json.dumps(Quote(
        signer_id=account_id,
        nonce=nonce,
        verifying_contract="intents.near",
        deadline="2025-12-31T11:59:59.000Z",
        intents=[
            Intent(intent='token_diff', diff={token_in_fmt: "-" + amount_in, token_out_fmt: amount_out})
        ]
    ))
    return quote

def publish_intent(signed_intent: Commitment, quote_hashes: List[str]) -> dict:
    """Publishes the signed intent to the solver bus."""

    publish_data = {
        "signed_data": signed_intent,
        "quote_hashes": [quote_hashes]
    }
    
    rpc_request = {
        "id": "dontcare",
        "jsonrpc": "2.0",
        "method": "publish_intent",
        "params": [publish_data]
    }
    
    response = requests.post(SOLVER_BUS_URL, json=rpc_request)
    return response.json()


def create_commitment_from_mpc_signature_using_rsv(quote: str, signature: dict) -> dict:
    """Create commitment from MPC signature"""
    
    signature_base58 = signature_to_rsv(signature)
    
    return {
        "standard": "erc191",
        "payload": quote,
        "signature": signature_base58
    }

def signature_to_rsv(signature) -> str:
    """Convert signature to RSV format"""
    
    big_r_hex = signature['big_r']['affine_point'][2:]  
    s_hex = signature['s']['scalar']
    v = signature['recovery_id'] 
    
    signature = big_r_hex + s_hex + "0" + str(v)

    signature_bytes = bytes.fromhex(signature)
    signature_base58 = f"secp256k1:{base58.b58encode(signature_bytes).decode('utf-8')}"
    
    return signature_base58