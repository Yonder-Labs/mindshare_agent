import pytest
from unittest.mock import Mock

# Constantes para testing
ASSET_MAP = {
    'USDC': { 
        'token_id': 'usdc.fakes.testnet',
        'omft': 'usdc.fakes.testnet',
        'decimals': 6,
    },
    'NEAR': {
        'token_id': 'wrap.near',
        'decimals': 24,
    },
    'ETH': {
        'token_id': 'eth.fakes.testnet',
        'omft': 'eth.fakes.testnet',
        'decimals': 18,
    },
    'DAI': {
        'token_id': 'dai.fakes.testnet',
        'omft': 'dai.fakes.testnet',
        'decimals': 18,
    },
}

def get_mindshare(token, api_key, use_mock=True):
    if use_mock:
        mock_data = {
            "BTC": {"mindshare": 0.75},
            "ETH": {"mindshare": 0.29},
            "SOL": {"mindshare": 0.85},
            "NEAR": {"mindshare": 0.15},
            "USDC": {"mindshare": 0.05},
            "DAI": {"mindshare": 0.05}
        }
        return mock_data.get(token, {"error": "Token not found"})
    else:
        return {"error": "Live API not available in tests"}

def get_account_balances(account):
    balances = {}
    
    # Get NEAR balance
    near_balance = account.state['amount'] if isinstance(account.state, dict) else account.state
    balances['NEAR'] = float(near_balance) / 10**24
    
    # Get other token balances
    for token_symbol, token_info in ASSET_MAP.items():
        if token_symbol == 'NEAR':
            continue
            
        try:
            balance = account.view_function(
                token_info['token_id'],
                'ft_balance_of',
                {'account_id': account.account_id}
            )['result']
            
            if balance:
                balances[token_symbol] = float(balance) / 10**token_info['decimals']
            else:
                balances[token_symbol] = 0
        except Exception as e:
            balances[token_symbol] = 0
    
    return balances

# Tests
def test_get_mindshare_mock_data():
    result = get_mindshare("NEAR", "fake_api_key", use_mock=True)
    assert "mindshare" in result
    assert result["mindshare"] == 0.15

def test_get_mindshare_invalid_token():
    result = get_mindshare("INVALID_TOKEN", "fake_api_key", use_mock=True)
    assert "error" in result
    assert result["error"] == "Token not found"

@pytest.fixture
def mock_account():
    account = Mock()
    account.account_id = "test.near"
    account.state = {"amount": "1000000000000000000000000"}  # 1 NEAR
    
    def mock_view_function(contract_id, method, params):
        if contract_id == ASSET_MAP['USDC']['token_id']:
            return {"result": "1000000"}  # 1 USDC
        elif contract_id == ASSET_MAP['ETH']['token_id']:
            return {"result": "1000000000000000000"}  # 1 ETH
        return {"result": "0"}
    
    account.view_function = mock_view_function
    return account

def test_get_account_balances(mock_account):
    balances = get_account_balances(mock_account)
    
    assert balances['NEAR'] == 1.0  # 1 NEAR
    assert balances['USDC'] == 1.0  # 1 USDC
    assert balances['ETH'] == 1.0   # 1 ETH
    assert balances['DAI'] == 0.0   # 0 DAI 