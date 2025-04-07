import pytest
from unittest.mock import patch, Mock
from src.scheduler.scheduler import MindshareScheduler

@pytest.fixture
def scheduler():
    with patch.dict('os.environ', {
        'KAITO_API_KEY': 'test_key',
        'ACCOUNT_PATH': 'test_path',
        'AGENT_PATH': 'test_agent_path'
    }):
        return MindshareScheduler(interval=1)

def test_scheduler_initialization(scheduler):
    assert scheduler.interval == 1
    assert scheduler.api_key == 'test_key'
    assert scheduler.account_path == 'test_path'
    assert scheduler.agent_path == 'test_agent_path'

@patch('subprocess.run')
def test_execute_agent_success(mock_run, scheduler):
    # Configurar el mock para simular una ejecución exitosa
    mock_process = Mock()
    mock_process.returncode = 0
    mock_process.stdout = "Success output"
    mock_run.return_value = mock_process
    
    scheduler.execute_agent()
    
    # Verificar que subprocess.run fue llamado con los argumentos correctos
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "nearai" in args
    assert "agent" in args
    assert "task" in args