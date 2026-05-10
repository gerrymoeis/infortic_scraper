/**
 * Scraper Checkpoint Manager
 * 
 * Manages checkpoint state for resumable scraping.
 * Allows workflow to resume from last successful point on failure.
 * 
 * Features:
 * - Track completed accounts
 * - Save progress after each session
 * - Resume from checkpoint
 * - Clear checkpoint on success
 */

const fs = require('fs');
const path = require('path');

class ScraperCheckpoint {
    constructor(checkpointFile = 'scraper_checkpoint.json') {
        this.checkpointPath = path.join(__dirname, checkpointFile);
    }

    /**
     * Check if checkpoint exists
     */
    exists() {
        return fs.existsSync(this.checkpointPath);
    }

    /**
     * Load checkpoint from file
     */
    load() {
        if (!this.exists()) {
            return null;
        }

        try {
            const data = fs.readFileSync(this.checkpointPath, 'utf8');
            const checkpoint = JSON.parse(data);
            
            console.log(`[CHECKPOINT] Found existing checkpoint`);
            console.log(`[CHECKPOINT]   Created: ${checkpoint.created_at}`);
            console.log(`[CHECKPOINT]   Completed: ${checkpoint.completed_accounts.length}/${checkpoint.total_accounts} accounts`);
            console.log(`[CHECKPOINT]   Remaining: ${checkpoint.remaining_accounts.length} accounts`);
            
            return checkpoint;
        } catch (error) {
            console.error(`[CHECKPOINT] Error loading checkpoint: ${error.message}`);
            return null;
        }
    }

    /**
     * Save checkpoint to file
     */
    save(completedAccounts, remainingAccounts, totalAccounts, sessionStats = {}) {
        const checkpoint = {
            run_id: new Date().toISOString().replace(/[:.]/g, '-'),
            created_at: new Date().toISOString(),
            total_accounts: totalAccounts,
            completed_accounts: completedAccounts,
            remaining_accounts: remainingAccounts,
            session_stats: sessionStats,
            progress_percentage: Math.round((completedAccounts.length / totalAccounts) * 100)
        };

        try {
            fs.writeFileSync(
                this.checkpointPath,
                JSON.stringify(checkpoint, null, 2),
                'utf8'
            );
            
            console.log(`[CHECKPOINT] Progress saved`);
            console.log(`[CHECKPOINT]   Completed: ${completedAccounts.length}/${totalAccounts} accounts`);
            console.log(`[CHECKPOINT]   Progress: ${checkpoint.progress_percentage}%`);
            
            return true;
        } catch (error) {
            console.error(`[CHECKPOINT] Error saving checkpoint: ${error.message}`);
            return false;
        }
    }

    /**
     * Get remaining accounts to scrape
     * If checkpoint exists, return remaining accounts
     * Otherwise, return all accounts
     */
    getRemainingAccounts(allAccounts) {
        const checkpoint = this.load();
        
        if (!checkpoint) {
            console.log(`[CHECKPOINT] No checkpoint found - processing all accounts`);
            return allAccounts;
        }

        // Validate checkpoint accounts still exist in config
        const validRemaining = checkpoint.remaining_accounts.filter(
            account => allAccounts.includes(account)
        );

        if (validRemaining.length === 0) {
            console.log(`[CHECKPOINT] All accounts completed - clearing checkpoint`);
            this.clear();
            return [];
        }

        console.log(`[CHECKPOINT] Resuming from checkpoint`);
        console.log(`[CHECKPOINT]   Will process: ${validRemaining.length} remaining accounts`);
        
        return validRemaining;
    }

    /**
     * Clear checkpoint file
     */
    clear() {
        if (this.exists()) {
            try {
                fs.unlinkSync(this.checkpointPath);
                console.log(`[CHECKPOINT] Checkpoint cleared`);
                return true;
            } catch (error) {
                console.error(`[CHECKPOINT] Error clearing checkpoint: ${error.message}`);
                return false;
            }
        }
        return true;
    }

    /**
     * Update checkpoint with completed account
     */
    updateProgress(completedAccount, allAccounts, completedAccounts) {
        const remaining = allAccounts.filter(
            account => !completedAccounts.includes(account)
        );

        this.save(completedAccounts, remaining, allAccounts.length);
    }
}

module.exports = ScraperCheckpoint;
