from nearai.agents.environment import Environment
import near_api
import json
import os
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from src.constants import ASSET_MAP

def get_account(account_id, private_key, provider):
    near_provider = near_api.providers.JsonProvider(provider)
    key_pair = near_api.signer.KeyPair(private_key)
    signer = near_api.signer.Signer(account_id, key_pair)
    return near_api.account.Account(near_provider, signer, account_id)

def get_asset_id(token):
    if token == 'NEAR':
        return 'nep141:' + ASSET_MAP[token]['token_id']
    else:
        return ASSET_MAP[token]['token_id']
   
def get_account_balances(account):
    """Get all assets for an account in intents.near contract"""
    balances = {}
    
    for token, info in ASSET_MAP.items():
        try:
            result = account.view_function(
                "intents.near",
                "mt_balance_of",
                {
                    "account_id": account.account_id,
                    "token_id": get_asset_id(token)
                }
            )
            
            if isinstance(result, dict) and 'result' in result:
                balance_str = result['result']
                if balance_str:
                    balance = Decimal(balance_str) / Decimal(str(10 ** info['decimals']))
                    if balance > 0:
                        balances[token] = float(balance)
                    else:
                        balances[token] = 0
            
        except Exception as e:
            print(f"Error getting balance for {token}: {str(e)}")
            continue
    
    return balances

def get_mindshare(token, api_key, use_mock=None):
    print(f"Getting mindshare for token: {token}")  # Debug log
    if use_mock is None:
        use_mock = os.getenv('USE_MOCK_MINDSHARE', 'false').lower() == 'true'

    if use_mock:
        mock_data = {
            "BTC": {"mindshare": 0.75},
            "ETH": {"mindshare": 0.29},
            "SOL": {"mindshare": 0.85},
            "NEAR": {"mindshare": 0.80},
            "USDC": {"mindshare": 0.05},
            "TRUMP": {"mindshare": 0.05},
            "XRP": {"mindshare": 0.05},
        }
        result = mock_data.get(token, {"error": "Token not found"})
        print(f"Mock mindshare result for {token}: {result}")  # Debug log
        return result
    else:
        # KAITO API Connection

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        base_url = f"https://api.kaito.ai/api/v1/mindshare?token={token}&start_date={yesterday}&end_date={today}"
        headers = {"x-api-key": api_key}
        response = requests.get(base_url, headers=headers)
        print(f"Kaito API response for {token}: {response.text}")  # Debug log
        if response.status_code == 200:
            data = response.json()
            mindshare_value = list(data['mindshare'].values())[0]
            return {"mindshare": mindshare_value}
        else:
            return {"error": "Failed to get mindshare"}


            return

def get_provider(network):
    if network == 'testnet':
        return 'https://rpc.testnet.near.org'
    else:
        return 'https://rpc.mainnet.near.org'

def run(env: Environment):

    api_key = env.env_vars.get('KAITO_API_KEY')
    account_id = env.env_vars.get('ACCOUNT_ID')
    private_key = env.env_vars.get('PRIVATE_KEY')
    network = env.env_vars.get('NETWORK')
    use_mock = env.env_vars.get('USE_MOCK_MINDSHARE', 'false').lower() == 'true'

    provider = get_provider(network)

    print("Getting account balances")
    account = get_account(account_id, private_key, provider)
    balances = get_account_balances(account)
    print(f"Retrieved balances: {balances}")

    token_data = {}
    for token, amount in balances.items():
        mindshare = get_mindshare(token, api_key, use_mock)
        if "error" not in mindshare:
            mindshare_value = mindshare["mindshare"]
            token_data[token] = {"balance": amount, "mindshare": mindshare_value}
            env.add_reply(f"I have {amount} {token} and mindshare for this token is: {mindshare_value}")
        else:
            env.add_reply(f"Error: No data available for {token}")

    prompt = {
        "role": "system", 
        "content": f"""Analyze ONLY the following tokens in the whitelist asset map {list(ASSET_MAP.keys())} and user'sportfolio: {list(balances.keys())} (do not add or assume other tokens). 
        For each suggested trade, consider that EXACT_AMOUNT MUST be less than the users's balance to avoid overflow or insufficient balance problems to pay the fees, provide the exact format:
        TRADE:
        - token_in: [TOKEN]
        - amount_in: [PERCENTAGE]% of current balance ([EXACT_AMOUNT])
        - token_out: [TOKEN]
        
        Example format:
        TRADE:
        - token_in: ETH
        - amount_in: 15% of current balance (39.31539)
        - token_out: USDC
        
        Provide trading decisions and explain the rationale after listing all trades. Keep in mind that the user's balance is limited and you need to consider the fees. So if the amount 
        to be trade is equal to the balance of that token, apply a 10% fee to the amount to be traded, to be able to pay the fees."""
    
    }
    
    print(f"Sending prompt to LLM: {prompt}")
    messages = env.list_messages()
    result = env.completion([prompt] + messages)
    
    env.add_reply(result)
    env.request_user_input()
    
run(env)

