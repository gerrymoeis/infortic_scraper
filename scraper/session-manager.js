/**
 * Session Manager Module
 * 
 * Handles loading and validation of Instagram session files
 * for multi-account parallel scraping.
 * 
 * Features:
 * - Load session cookies from JSON files
 * - Validate session file structure
 * - Provide session metadata
 * - Error handling for missing/invalid files
 */

const fs = require('fs');
const path = require('path');

class SessionManager {
    /**
     * Create a SessionManager instance
     * @param {string} sessionFile - Session filename (e.g., 'session1.json')
     */
    constructor(sessionFile = 'session.json') {
        this.sessionFile = sessionFile;
        this.sessionPath = path.join(__dirname, sessionFile);
    }

    /**
     * Load session cookies from file
     * @returns {Array} Cookie array for Playwright context
     * @throws {Error} If file not found or invalid
     */
    loadSession() {
        if (!this.exists()) {
            throw new Error(`Session file not found: ${this.sessionPath}`);
        }

        try {
            const sessionData = fs.readFileSync(this.sessionPath, 'utf8');
            const cookies = JSON.parse(sessionData);
            
            // Validate structure
            if (!Array.isArray(cookies)) {
                throw new Error('Invalid session file: must contain cookies array');
            }

            if (cookies.length === 0) {
                throw new Error('Invalid session file: cookies array is empty');
            }

            // Validate critical cookies exist
            const hasCriticalCookies = this.validateCriticalCookies(cookies);
            if (!hasCriticalCookies) {
                console.warn(`[WARNING] Session ${this.sessionFile} missing critical cookies`);
            }

            return cookies;
        } catch (error) {
            if (error instanceof SyntaxError) {
                throw new Error(`Invalid JSON in session file: ${error.message}`);
            }
            throw error;
        }
    }

    /**
     * Validate that critical Instagram cookies are present
     * @param {Array} cookies - Cookie array
     * @returns {boolean} True if critical cookies found
     */
    validateCriticalCookies(cookies) {
        const criticalCookieNames = ['sessionid', 'csrftoken', 'ds_user_id'];
        const cookieNames = cookies.map(c => c.name);
        
        return criticalCookieNames.every(name => cookieNames.includes(name));
    }

    /**
     * Check if session file exists
     * @returns {boolean}
     */
    exists() {
        return fs.existsSync(this.sessionPath);
    }

    /**
     * Get session file information
     * @returns {Object} File metadata
     */
    getInfo() {
        if (!this.exists()) {
            return {
                exists: false,
                file: this.sessionFile,
                path: this.sessionPath
            };
        }

        try {
            const stats = fs.statSync(this.sessionPath);
            const cookies = JSON.parse(fs.readFileSync(this.sessionPath, 'utf8'));
            
            // Extract important cookie info
            const sessionCookie = cookies.find(c => c.name === 'sessionid');
            const userIdCookie = cookies.find(c => c.name === 'ds_user_id');
            
            return {
                exists: true,
                file: this.sessionFile,
                path: this.sessionPath,
                size: stats.size,
                modified: stats.mtime,
                cookieCount: cookies.length,
                hasCriticalCookies: this.validateCriticalCookies(cookies),
                userId: userIdCookie ? userIdCookie.value : null,
                sessionExpiry: sessionCookie && sessionCookie.expires 
                    ? new Date(sessionCookie.expires * 1000) 
                    : null
            };
        } catch (error) {
            return {
                exists: true,
                file: this.sessionFile,
                path: this.sessionPath,
                error: error.message
            };
        }
    }

    /**
     * Check if session is expired
     * @returns {boolean} True if session is expired
     */
    isExpired() {
        const info = this.getInfo();
        
        if (!info.exists || !info.sessionExpiry) {
            return true;
        }

        return new Date() > info.sessionExpiry;
    }

    /**
     * Get time until session expires
     * @returns {number|null} Seconds until expiry, or null if no expiry
     */
    getTimeUntilExpiry() {
        const info = this.getInfo();
        
        if (!info.exists || !info.sessionExpiry) {
            return null;
        }

        const now = new Date();
        const expiry = info.sessionExpiry;
        const diffMs = expiry - now;
        
        return Math.floor(diffMs / 1000); // Convert to seconds
    }
}

module.exports = SessionManager;
