import os

# Path constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_PATH = os.path.join(BASE_DIR, "src", "agent")

# Asset mapping
ASSET_MAP = {
    'USDC': { 
        'token_id': 'nep141:eth-0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.omft.near',
        'decimals': 6,
        'blockchain': 'eth',
        'symbol': 'USDC',
        'price': 0.999795,
        'price_updated_at': "2025-03-25T15:11:40.065Z",
        'contract_address': "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    },
    'NEAR': {
        'token_id': 'wrap.near',
        'decimals': 24,
    },
    'WNEAR': {
        'token_id': 'nep141:wrap.near',
        'decimals': 24,
        'blockchain': 'near',
        'symbol': 'wNEAR',
        'price': 3,
        'price_updated_at': "2025-03-25T15:11:40.065Z",
        'contract_address': "wrap.near"
    },
    'ETH': {
        'token_id': 'nep141:eth.omft.near',
        'decimals': 18,
        'blockchain': 'eth',
        'symbol': 'ETH',
        'price': 2079.16,
        'price_updated_at': "2025-03-25T15:11:40.065Z"
    },
    'BTC': {
        'token_id': 'nep141:btc.omft.near',
        'decimals': 8,
        'blockchain': 'btc',
        'symbol': 'BTC',
        'price': 88178,
        'price_updated_at': "2025-03-25T15:11:40.065Z"
    },
    'SOL': {    
        'token_id': 'nep141:sol.omft.near',
        'decimals': 9,
        'blockchain': 'sol',
        'symbol': 'SOL',
        'price': 146.28,
        'price_updated_at': "2025-03-25T15:11:40.065Z"
    },
    'TRUMP': {
        'token_id': 'nep141:sol-c58e6539c2f2e097c251f8edf11f9c03e581f8d4.omft.near',
        'decimals': 6,
        'blockchain': 'sol',
        'symbol': 'TRUMP',
        'price': 11.65,
        'price_updated_at': "2025-03-25T15:11:40.065Z",
        'contract_address': "c58e6539c2f2e097c251f8edf11f9c03e581f8d4"
    },
     'XRP': {
        'token_id': 'nep141:xrp.omft.near',
        'decimals': 6,
        'blockchain': 'xrp',
        'symbol': 'XRP',
        'price': 2.45,
        'price_updated_at': "2025-03-25T15:11:40.065Z"
    }
} 