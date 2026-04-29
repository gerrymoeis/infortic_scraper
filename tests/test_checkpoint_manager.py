"""
Unit Tests for Checkpoint Manager
Tests checkpoint creation, loading, validation, and cleanup
"""

import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

# Import the checkpoint manager
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from extraction.checkpoint_manager import CheckpointManager


@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Create temporary directory for checkpoint files"""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    return checkpoint_dir


@pytest.fixture
def sample_results():
    """Sample extraction results for testing"""
    return [
        {
            'post_id': 'ABC123',
            'title': 'Lomba Essay Nasional',
            'category': 'competition',
            'source_account': 'lombamahasiswa.id'
        },
        {
            'post_id': 'DEF456',
            'title': 'Beasiswa S2 Luar Negeri',
            'category': 'scholarship',
            'source_account': 'beasiswaindonesia'
        }
    ]


@pytest.fixture
def sample_accounts():
    """Sample account list for testing"""
    return ['account1', 'account2', 'account3', 'account4', 'account5']


class TestCheckpointManager:
    """Test suite for CheckpointManager class"""
    
    def test_initialization(self, temp_checkpoint_dir):
        """Test checkpoint manager initialization"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        assert manager.checkpoint_dir == temp_checkpoint_dir
        assert manager.state_file == temp_checkpoint_dir / "checkpoint_state.json"
        assert manager.results_file == temp_checkpoint_dir / "checkpoint_results.json"
        assert temp_checkpoint_dir.exists()
    
    def test_save_checkpoint_success(self, temp_checkpoint_dir, sample_results, sample_accounts):
        """Test successful checkpoint save"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        success = manager.save_checkpoint(
            account_index=1,
            account_name='account2',
            results=sample_results,
            total_accounts=5,
            accounts_list=sample_accounts
        )
        
        assert success is True
        assert manager.state_file.exists()
        assert manager.results_file.exists()
        
        # Verify state file content
        with open(manager.state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        assert state['checkpoint_version'] == CheckpointManager.CHECKPOINT_VERSION
        assert state['last_completed_account'] == 'account2'
        assert state['last_completed_index'] == 1
        assert state['total_accounts'] == 5
        assert state['results_count'] == 2
        assert state['status'] == 'in_progress'
        assert state['accounts_remaining'] == ['account3', 'account4', 'account5']
        
        # Verify results file content
        with open(manager.results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        assert len(results) == 2
        assert results[0]['post_id'] == 'ABC123'
    
    def test_load_checkpoint_success(self, temp_checkpoint_dir, sample_results, sample_accounts):
        """Test successful checkpoint load"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        # Save checkpoint first
        manager.save_checkpoint(
            account_index=2,
            account_name='account3',
            results=sample_results,
            total_accounts=5,
            accounts_list=sample_accounts
        )
        
        # Load checkpoint
        checkpoint, results = manager.load_checkpoint()
        
        assert checkpoint is not None
        assert checkpoint['last_completed_index'] == 2
        assert checkpoint['total_accounts'] == 5
        assert len(results) == 2
        assert results[0]['post_id'] == 'ABC123'
    
    def test_load_checkpoint_not_found(self, temp_checkpoint_dir):
        """Test load checkpoint when no checkpoint exists"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        checkpoint, results = manager.load_checkpoint()
        
        assert checkpoint is None
        assert results == []
    
    def test_validate_checkpoint_valid(self, temp_checkpoint_dir):
        """Test validation of valid checkpoint"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        valid_checkpoint = {
            'checkpoint_version': CheckpointManager.CHECKPOINT_VERSION,
            'last_completed_index': 2,
            'total_accounts': 5,
            'results_count': 10,
            'status': 'in_progress',
            'created_at': datetime.now().isoformat()
        }
        
        assert manager.validate_checkpoint(valid_checkpoint) is True
    
    def test_validate_checkpoint_invalid_missing_fields(self, temp_checkpoint_dir):
        """Test validation rejects checkpoint with missing fields"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        invalid_checkpoint = {
            'checkpoint_version': CheckpointManager.CHECKPOINT_VERSION,
            'last_completed_index': 2
            # Missing required fields
        }
        
        assert manager.validate_checkpoint(invalid_checkpoint) is False
    
    def test_validate_checkpoint_version_mismatch(self, temp_checkpoint_dir):
        """Test validation rejects checkpoint with wrong version"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        invalid_checkpoint = {
            'checkpoint_version': '0.9',  # Wrong version
            'last_completed_index': 2,
            'total_accounts': 5,
            'results_count': 10,
            'status': 'in_progress'
        }
        
        assert manager.validate_checkpoint(invalid_checkpoint) is False
    
    def test_validate_checkpoint_invalid_status(self, temp_checkpoint_dir):
        """Test validation rejects checkpoint with invalid status"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        invalid_checkpoint = {
            'checkpoint_version': CheckpointManager.CHECKPOINT_VERSION,
            'last_completed_index': 2,
            'total_accounts': 5,
            'results_count': 10,
            'status': 'completed'  # Invalid status
        }
        
        assert manager.validate_checkpoint(invalid_checkpoint) is False
    
    def test_validate_checkpoint_index_out_of_bounds(self, temp_checkpoint_dir):
        """Test validation rejects checkpoint with index out of bounds"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        invalid_checkpoint = {
            'checkpoint_version': CheckpointManager.CHECKPOINT_VERSION,
            'last_completed_index': 10,  # Greater than total
            'total_accounts': 5,
            'results_count': 10,
            'status': 'in_progress'
        }
        
        assert manager.validate_checkpoint(invalid_checkpoint) is False
    
    def test_validate_checkpoint_too_old(self, temp_checkpoint_dir):
        """Test validation rejects checkpoint older than 7 days"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        old_date = (datetime.now() - timedelta(days=8)).isoformat()
        
        old_checkpoint = {
            'checkpoint_version': CheckpointManager.CHECKPOINT_VERSION,
            'last_completed_index': 2,
            'total_accounts': 5,
            'results_count': 10,
            'status': 'in_progress',
            'created_at': old_date
        }
        
        assert manager.validate_checkpoint(old_checkpoint) is False
    
    def test_cleanup_checkpoint(self, temp_checkpoint_dir, sample_results, sample_accounts):
        """Test checkpoint cleanup"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        # Save checkpoint first
        manager.save_checkpoint(
            account_index=1,
            account_name='account2',
            results=sample_results,
            total_accounts=5,
            accounts_list=sample_accounts
        )
        
        assert manager.state_file.exists()
        assert manager.results_file.exists()
        
        # Cleanup
        success = manager.cleanup_checkpoint()
        
        assert success is True
        assert not manager.state_file.exists()
        assert not manager.results_file.exists()
    
    def test_cleanup_checkpoint_no_files(self, temp_checkpoint_dir):
        """Test cleanup when no checkpoint files exist"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        success = manager.cleanup_checkpoint()
        
        assert success is True
    
    def test_get_resume_index(self, temp_checkpoint_dir):
        """Test resume index calculation"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        checkpoint = {'last_completed_index': 5}
        resume_index = manager.get_resume_index(checkpoint)
        
        assert resume_index == 6
    
    def test_get_checkpoint_info(self, temp_checkpoint_dir, sample_results, sample_accounts):
        """Test getting checkpoint info without loading results"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        # Save checkpoint first
        manager.save_checkpoint(
            account_index=3,
            account_name='account4',
            results=sample_results,
            total_accounts=5,
            accounts_list=sample_accounts
        )
        
        # Get info
        info = manager.get_checkpoint_info()
        
        assert info is not None
        assert info['last_completed_index'] == 3
        assert info['total_accounts'] == 5
        assert 'results_count' in info
    
    def test_get_checkpoint_info_not_found(self, temp_checkpoint_dir):
        """Test getting checkpoint info when no checkpoint exists"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        info = manager.get_checkpoint_info()
        
        assert info is None
    
    def test_atomic_write(self, temp_checkpoint_dir, sample_results, sample_accounts):
        """Test atomic write mechanism (temp file then rename)"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        # Save checkpoint
        manager.save_checkpoint(
            account_index=1,
            account_name='account2',
            results=sample_results,
            total_accounts=5,
            accounts_list=sample_accounts
        )
        
        # Verify temp files don't exist (should be renamed)
        temp_state = manager.state_file.with_suffix('.tmp')
        temp_results = manager.results_file.with_suffix('.tmp')
        
        assert not temp_state.exists()
        assert not temp_results.exists()
        
        # Verify final files exist
        assert manager.state_file.exists()
        assert manager.results_file.exists()
    
    def test_load_checkpoint_results_count_mismatch(self, temp_checkpoint_dir, sample_results, sample_accounts):
        """Test load checkpoint rejects when results count doesn't match"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        # Save checkpoint
        manager.save_checkpoint(
            account_index=1,
            account_name='account2',
            results=sample_results,
            total_accounts=5,
            accounts_list=sample_accounts
        )
        
        # Manually modify state file to have wrong results_count
        with open(manager.state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        state['results_count'] = 999  # Wrong count
        
        with open(manager.state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f)
        
        # Try to load
        checkpoint, results = manager.load_checkpoint()
        
        assert checkpoint is None
        assert results == []
    
    def test_save_checkpoint_with_environment_variables(self, temp_checkpoint_dir, sample_results, sample_accounts):
        """Test checkpoint saves GitHub environment variables"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        # Set environment variables
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '12345', 'GITHUB_RUN_NUMBER': '42'}):
            manager.save_checkpoint(
                account_index=1,
                account_name='account2',
                results=sample_results,
                total_accounts=5,
                accounts_list=sample_accounts
            )
        
        # Verify environment variables saved
        with open(manager.state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        assert state['workflow_run_id'] == '12345'
        assert state['workflow_run_number'] == '42'
    
    def test_save_checkpoint_empty_results(self, temp_checkpoint_dir, sample_accounts):
        """Test checkpoint save with empty results"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        success = manager.save_checkpoint(
            account_index=0,
            account_name='account1',
            results=[],
            total_accounts=5,
            accounts_list=sample_accounts
        )
        
        assert success is True
        
        # Verify results file is empty array
        with open(manager.results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        assert results == []
    
    def test_save_checkpoint_last_account(self, temp_checkpoint_dir, sample_results, sample_accounts):
        """Test checkpoint save for last account"""
        manager = CheckpointManager(temp_checkpoint_dir)
        
        success = manager.save_checkpoint(
            account_index=4,  # Last account (0-indexed)
            account_name='account5',
            results=sample_results,
            total_accounts=5,
            accounts_list=sample_accounts
        )
        
        assert success is True
        
        # Verify accounts_remaining is empty
        with open(manager.state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        assert state['accounts_remaining'] == []


# Test convenience functions
def test_has_checkpoint(temp_checkpoint_dir, sample_results, sample_accounts):
    """Test has_checkpoint convenience function"""
    from extraction.checkpoint_manager import has_checkpoint
    
    # No checkpoint initially
    assert has_checkpoint(temp_checkpoint_dir) is False
    
    # Create checkpoint
    manager = CheckpointManager(temp_checkpoint_dir)
    manager.save_checkpoint(
        account_index=1,
        account_name='account2',
        results=sample_results,
        total_accounts=5,
        accounts_list=sample_accounts
    )
    
    # Should find checkpoint now
    assert has_checkpoint(temp_checkpoint_dir) is True


def test_load_checkpoint_if_exists(temp_checkpoint_dir, sample_results, sample_accounts):
    """Test load_checkpoint_if_exists convenience function"""
    from extraction.checkpoint_manager import load_checkpoint_if_exists
    
    # No checkpoint initially
    checkpoint, results = load_checkpoint_if_exists(temp_checkpoint_dir)
    assert checkpoint is None
    assert results == []
    
    # Create checkpoint
    manager = CheckpointManager(temp_checkpoint_dir)
    manager.save_checkpoint(
        account_index=2,
        account_name='account3',
        results=sample_results,
        total_accounts=5,
        accounts_list=sample_accounts
    )
    
    # Should load checkpoint now
    checkpoint, results = load_checkpoint_if_exists(temp_checkpoint_dir)
    assert checkpoint is not None
    assert len(results) == 2


def test_save_checkpoint_safe(temp_checkpoint_dir, sample_results, sample_accounts):
    """Test save_checkpoint_safe convenience function"""
    from extraction.checkpoint_manager import save_checkpoint_safe
    
    success = save_checkpoint_safe(
        checkpoint_dir=temp_checkpoint_dir,
        account_index=1,
        account_name='account2',
        results=sample_results,
        total_accounts=5,
        accounts_list=sample_accounts
    )
    
    assert success is True
    
    # Verify files created
    state_file = temp_checkpoint_dir / "checkpoint_state.json"
    results_file = temp_checkpoint_dir / "checkpoint_results.json"
    
    assert state_file.exists()
    assert results_file.exists()


def test_cleanup_checkpoint_safe(temp_checkpoint_dir, sample_results, sample_accounts):
    """Test cleanup_checkpoint_safe convenience function"""
    from extraction.checkpoint_manager import cleanup_checkpoint_safe
    
    # Create checkpoint first
    manager = CheckpointManager(temp_checkpoint_dir)
    manager.save_checkpoint(
        account_index=1,
        account_name='account2',
        results=sample_results,
        total_accounts=5,
        accounts_list=sample_accounts
    )
    
    # Cleanup
    success = cleanup_checkpoint_safe(temp_checkpoint_dir)
    
    assert success is True
    
    # Verify files deleted
    state_file = temp_checkpoint_dir / "checkpoint_state.json"
    results_file = temp_checkpoint_dir / "checkpoint_results.json"
    
    assert not state_file.exists()
    assert not results_file.exists()
