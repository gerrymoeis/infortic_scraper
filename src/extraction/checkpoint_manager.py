"""
Checkpoint Manager for Extraction Pipeline
Handles checkpoint creation, loading, validation, and cleanup for fault-tolerant workflow

This module is COMPLETELY ISOLATED and does NOT modify existing code.
It provides optional checkpoint/resume functionality that can be integrated later.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Import logger from existing utils
from .utils.logger import setup_logger

logger = setup_logger('checkpoint')


class CheckpointManager:
    """
    Manages checkpoint creation, loading, and cleanup for extraction pipeline
    
    Features:
    - Save checkpoint after each account processed
    - Load checkpoint on startup for resume capability
    - Validate checkpoint integrity
    - Cleanup checkpoint on successful completion
    - Atomic writes to prevent corruption
    """
    
    CHECKPOINT_VERSION = "1.0"
    STATE_FILE = "checkpoint_state.json"
    RESULTS_FILE = "checkpoint_results.json"
    
    def __init__(self, checkpoint_dir: Path):
        """
        Initialize checkpoint manager
        
        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.checkpoint_dir / self.STATE_FILE
        self.results_file = self.checkpoint_dir / self.RESULTS_FILE
        
        logger.info(f"[CHECKPOINT] Manager initialized: {self.checkpoint_dir}")
    
    def save_checkpoint(
        self,
        account_index: int,
        account_name: str,
        results: List[Dict],
        total_accounts: int,
        accounts_list: List[str]
    ) -> bool:
        """
        Save checkpoint after processing an account
        
        Uses atomic write (write to temp file, then rename) to prevent corruption
        
        Args:
            account_index: Index of account just completed (0-based)
            account_name: Name of account just completed
            results: All results accumulated so far
            total_accounts: Total number of accounts to process
            accounts_list: List of all account names
            
        Returns:
            True if checkpoint saved successfully, False otherwise
        """
        try:
            # Prepare checkpoint state
            checkpoint_state = {
                "checkpoint_version": self.CHECKPOINT_VERSION,
                "workflow_run_id": os.getenv('GITHUB_RUN_ID', 'local'),
                "workflow_run_number": os.getenv('GITHUB_RUN_NUMBER', '0'),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "last_completed_account": account_name,
                "last_completed_index": account_index,
                "total_accounts": total_accounts,
                "accounts_remaining": accounts_list[account_index + 1:] if account_index + 1 < len(accounts_list) else [],
                "results_count": len(results),
                "status": "in_progress"
            }
            
            # Atomic write: write to temp file, then rename
            temp_state = self.state_file.with_suffix('.tmp')
            temp_results = self.results_file.with_suffix('.tmp')
            
            # Write state
            with open(temp_state, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_state, f, indent=2, ensure_ascii=False)
            
            # Write results
            with open(temp_results, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            # Atomic rename (POSIX guarantees atomicity)
            temp_state.replace(self.state_file)
            temp_results.replace(self.results_file)
            
            logger.info(
                f"[CHECKPOINT] Saved: account {account_index + 1}/{total_accounts} "
                f"(@{account_name}), {len(results)} results"
            )
            return True
            
        except Exception as e:
            logger.error(f"[CHECKPOINT] Failed to save: {e}")
            return False
    
    def load_checkpoint(self) -> Tuple[Optional[Dict], List[Dict]]:
        """
        Load checkpoint if exists and valid
        
        Returns:
            Tuple of (checkpoint_state, results) or (None, []) if no valid checkpoint
        """
        try:
            if not self.state_file.exists() or not self.results_file.exists():
                logger.info("[CHECKPOINT] No checkpoint found")
                return None, []
            
            # Load state
            with open(self.state_file, 'r', encoding='utf-8') as f:
                checkpoint_state = json.load(f)
            
            # Validate checkpoint
            if not self.validate_checkpoint(checkpoint_state):
                logger.warning("[CHECKPOINT] Invalid checkpoint, ignoring")
                return None, []
            
            # Load results
            with open(self.results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            # Verify results count matches
            if len(results) != checkpoint_state['results_count']:
                logger.warning(
                    f"[CHECKPOINT] Results count mismatch: "
                    f"expected {checkpoint_state['results_count']}, "
                    f"got {len(results)}"
                )
                return None, []
            
            logger.info(
                f"[CHECKPOINT] Loaded: account {checkpoint_state['last_completed_index'] + 1}/"
                f"{checkpoint_state['total_accounts']}, {len(results)} results"
            )
            return checkpoint_state, results
            
        except Exception as e:
            logger.error(f"[CHECKPOINT] Failed to load: {e}")
            return None, []
    
    def validate_checkpoint(self, checkpoint: Dict) -> bool:
        """
        Validate checkpoint structure and version
        
        Args:
            checkpoint: Checkpoint state dictionary
            
        Returns:
            True if checkpoint is valid, False otherwise
        """
        required_fields = [
            'checkpoint_version',
            'last_completed_index',
            'total_accounts',
            'results_count',
            'status'
        ]
        
        # Check required fields
        for field in required_fields:
            if field not in checkpoint:
                logger.warning(f"[CHECKPOINT] Missing field: {field}")
                return False
        
        # Check version compatibility
        if checkpoint['checkpoint_version'] != self.CHECKPOINT_VERSION:
            logger.warning(
                f"[CHECKPOINT] Version mismatch: "
                f"expected {self.CHECKPOINT_VERSION}, "
                f"got {checkpoint['checkpoint_version']}"
            )
            return False
        
        # Check status
        if checkpoint['status'] != 'in_progress':
            logger.warning(f"[CHECKPOINT] Invalid status: {checkpoint['status']}")
            return False
        
        # Check index bounds
        if checkpoint['last_completed_index'] >= checkpoint['total_accounts']:
            logger.warning("[CHECKPOINT] Index out of bounds")
            return False
        
        # Check if checkpoint is too old (> 7 days)
        try:
            created_at = datetime.fromisoformat(checkpoint.get('created_at', ''))
            age_days = (datetime.now() - created_at).days
            if age_days > 7:
                logger.warning(f"[CHECKPOINT] Checkpoint too old: {age_days} days")
                return False
        except Exception:
            # If can't parse date, continue (not critical)
            pass
        
        return True
    
    def cleanup_checkpoint(self) -> bool:
        """
        Delete checkpoint files on successful completion
        
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            deleted_count = 0
            
            if self.state_file.exists():
                self.state_file.unlink()
                deleted_count += 1
            
            if self.results_file.exists():
                self.results_file.unlink()
                deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"[CHECKPOINT] Cleanup complete ({deleted_count} files deleted)")
            else:
                logger.info("[CHECKPOINT] No checkpoint files to clean up")
            
            return True
            
        except Exception as e:
            logger.error(f"[CHECKPOINT] Cleanup failed: {e}")
            return False
    
    def get_resume_index(self, checkpoint: Dict) -> int:
        """
        Get index to resume from (next account after last completed)
        
        Args:
            checkpoint: Checkpoint state dictionary
            
        Returns:
            Index of next account to process (0-based)
        """
        return checkpoint['last_completed_index'] + 1
    
    def get_checkpoint_info(self) -> Optional[Dict]:
        """
        Get checkpoint information without loading full results
        
        Returns:
            Checkpoint state dictionary or None if no checkpoint
        """
        try:
            if not self.state_file.exists():
                return None
            
            with open(self.state_file, 'r', encoding='utf-8') as f:
                checkpoint_state = json.load(f)
            
            if self.validate_checkpoint(checkpoint_state):
                return checkpoint_state
            
            return None
            
        except Exception as e:
            logger.error(f"[CHECKPOINT] Failed to get info: {e}")
            return None


# Convenience functions for easy integration

def has_checkpoint(checkpoint_dir: Path) -> bool:
    """
    Check if a valid checkpoint exists
    
    Args:
        checkpoint_dir: Directory to check for checkpoint
        
    Returns:
        True if valid checkpoint exists, False otherwise
    """
    manager = CheckpointManager(checkpoint_dir)
    return manager.get_checkpoint_info() is not None


def load_checkpoint_if_exists(checkpoint_dir: Path) -> Tuple[Optional[Dict], List[Dict]]:
    """
    Load checkpoint if exists, otherwise return empty
    
    Args:
        checkpoint_dir: Directory to check for checkpoint
        
    Returns:
        Tuple of (checkpoint_state, results) or (None, [])
    """
    manager = CheckpointManager(checkpoint_dir)
    return manager.load_checkpoint()


def save_checkpoint_safe(
    checkpoint_dir: Path,
    account_index: int,
    account_name: str,
    results: List[Dict],
    total_accounts: int,
    accounts_list: List[str]
) -> bool:
    """
    Save checkpoint with error handling
    
    Args:
        checkpoint_dir: Directory to save checkpoint
        account_index: Index of account just completed
        account_name: Name of account just completed
        results: All results accumulated so far
        total_accounts: Total number of accounts
        accounts_list: List of all account names
        
    Returns:
        True if saved successfully, False otherwise
    """
    manager = CheckpointManager(checkpoint_dir)
    return manager.save_checkpoint(
        account_index,
        account_name,
        results,
        total_accounts,
        accounts_list
    )


def cleanup_checkpoint_safe(checkpoint_dir: Path) -> bool:
    """
    Cleanup checkpoint with error handling
    
    Args:
        checkpoint_dir: Directory containing checkpoint
        
    Returns:
        True if cleanup successful, False otherwise
    """
    manager = CheckpointManager(checkpoint_dir)
    return manager.cleanup_checkpoint()
