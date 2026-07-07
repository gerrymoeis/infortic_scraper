/**
 * Instagram Parallel Scraper
 * 
 * Multi-session parallel scraping with 3 Instagram accounts.
 * Each session runs in isolated browser context with independent rate limits.
 * 
 * Architecture:
 * - Single Browser → 3 Contexts (parallel) → 3 Pages
 * - Context 1 (Session 1): Accounts 1-7
 * - Context 2 (Session 2): Accounts 8-14
 * - Context 3 (Session 3): Accounts 15-20
 * 
 * Features:
 * - Parallel execution (3x faster)
 * - Staggered start (human-like behavior)
 * - Session isolation (independent rate limits)
 * - Result merging (single output file)
 * - Comprehensive logging
 */

const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');
const SessionManager = require('./session-manager');
const ScraperCheckpoint = require('./checkpoint-manager');

chromium.use(stealth());

// Configuration
const config = require('../config/scraper.config.json');
const OUTPUT_FILE = path.join(__dirname, 'instagram_data.json');
const IMAGES_FOLDER = path.join(__dirname, 'instagram_images');  // Save to scraper/instagram_images/

// Helper functions
const sleep = (min, max) => new Promise(resolve => 
    setTimeout(resolve, Math.floor(Math.random() * (max - min + 1) + min))
);

/**
 * Load Instagram passwords from environment
 * Maps session number to password
 */
function loadInstagramPasswords() {
    const passwords = {};
    for (let i = 1; i <= 10; i++) {
        const password = process.env[`INSTAGRAM_PASSWORD_${i}`];
        if (password) {
            passwords[i] = password;
        }
    }
    return passwords;
}

/**
 * Type text with human-like delays
 * Simulates natural typing patterns with variation
 */
async function typeHumanLike(page, selector, text, sessionName) {
    try {
        const input = page.locator(selector).first();
        
        // Focus on input field
        await input.click();
        await sleep(200, 400);
        
        // Type each character with human-like delays
        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            
            // Base delay: 80-150ms
            let delay = Math.floor(Math.random() * 70 + 80);
            
            // Longer pause every 3-4 characters (150-200ms)
            if (i > 0 && i % 3 === 0) {
                delay = Math.floor(Math.random() * 50 + 150);
            }
            
            // Type character
            await input.pressSequentially(char, { delay: 0 });
            
            // Wait with variation
            await sleep(delay, delay + 20);
        }
        
        // Small pause after typing
        await sleep(300, 500);
        
        return true;
    } catch (error) {
        console.log(`[${sessionName}] Error typing: ${error.message}`);
        return false;
    }
}

/**
 * Detect and dismiss Instagram anti-bot popup
 * Handles "We suspect automated behavior" warning
 */
async function dismissAutomatedBehaviorPopup(page, sessionName) {
    try {
        // Check for automated behavior popup
        const popupSelectors = [
            'button[aria-label="Dismiss"]',
            'div[role="button"][aria-label="Dismiss"]',
            'div[role="button"]:has-text("Dismiss")',
            'button:has-text("Dismiss")'
        ];
        
        for (const selector of popupSelectors) {
            const dismissButton = page.locator(selector).first();
            const count = await dismissButton.count();
            
            if (count > 0) {
                console.log(`[${sessionName}] ⚠️  Automated behavior popup detected`);
                
                // Natural delay before clicking (human-like)
                await sleep(1500, 2500);
                
                // Click dismiss button
                await dismissButton.click();
                console.log(`[${sessionName}] ✓ Popup dismissed`);
                
                // Wait for popup to close
                await sleep(2000, 3000);
                
                return true;
            }
        }
        
        return false;
    } catch (error) {
        console.log(`[${sessionName}] Note: Popup check failed (${error.message})`);
        return false;
    }
}

/**
 * Handle Instagram account selection/confirmation screen
 * Detects and clicks "Continue" button when Instagram asks to confirm account
 * Uses multi-layer approach: getByRole.first() + CSS fallback + explicit error logging
 */
async function handleAccountSelectionScreen(page, sessionName) {
    try {
        const isAccountSelectionScreen =
            await page.getByText('Use another profile').isVisible().catch(() => false) ||
            await page.getByText('everyday moments').isVisible().catch(() => false);

        if (!isAccountSelectionScreen) return false;

        console.log(`[${sessionName}] 🔄 Account selection screen detected`);
        await takeDebugScreenshot(page, sessionName, 'account_selection_screen');

        // Short wait for DOM to fully settle before attempting click
        await sleep(800, 1000);

        let clicked = false;

        // Primary: getByRole with .first() to avoid strict mode violation
        try {
            const continueButton = page.getByRole('button', { name: 'Continue' }).first();
            if (await continueButton.isVisible()) {
                await sleep(1500, 2000);
                await continueButton.click();
                clicked = true;
            }
        } catch (e) {
            console.log(`[${sessionName}] ⚠️  Primary locator error: ${e.message}`);
        }

        // Fallback: CSS has-text on visible button — confirmed valid per Playwright docs
        if (!clicked) {
            try {
                const fallback = page.locator('button:has-text("Continue"):visible').first();
                if (await fallback.isVisible()) {
                    await sleep(1500, 2000);
                    await fallback.click();
                    clicked = true;
                    console.log(`[${sessionName}] ✓ Clicked Continue (fallback)`);
                }
            } catch (e) {
                console.log(`[${sessionName}] ⚠️  Fallback locator error: ${e.message}`);
            }
        }

        if (clicked) {
            console.log(`[${sessionName}] ✓ Clicked Continue button`);
            await sleep(3000, 4000);
            return true;
        }

        console.log(`[${sessionName}] ⚠️  Continue button not clickable on account selection screen`);
        return false;
    } catch (error) {
        console.log(`[${sessionName}] Note: Account selection check failed (${error.message})`);
        return false;
    }
}

/**
 * Handle Instagram password challenge modal
 * Detects password prompt and enters password with human-like typing
 * Uses comprehensive selector list — passes the actually-matched selector to typeHumanLike
 */
async function handlePasswordChallenge(page, sessionName, sessionNumber, passwords) {
    try {
        // Comprehensive selector list — covers modal context, placeholder, type, name, and aria variants
        const passwordModalSelectors = [
            'input[placeholder="Password"]',
            'input[type="password"]',
            'input[name="password"]',
            'input[aria-label="Password"]',
            'div[role="dialog"] input[type="password"]',
            'div[role="dialog"] input[placeholder="Password"]'
        ];
        
        let matchedSelector = null;
        for (const selector of passwordModalSelectors) {
            const input = page.locator(selector).first();
            if (await input.isVisible().catch(() => false)) {
                matchedSelector = selector;
                break;
            }
        }
        
        if (!matchedSelector) {
            return false; // No password challenge
        }
        
        console.log(`[${sessionName}] 🔐 Password challenge detected`);
        
        // Take screenshot + dump DOM info for accurate debugging
        await takeDebugScreenshot(page, sessionName, 'password_prompt');
        await dumpPageDebugInfo(page, sessionName, 'password_prompt');
        
        // Get password for this session
        const password = passwords[sessionNumber];
        if (!password) {
            console.log(`[${sessionName}] ❌ No password configured for session ${sessionNumber}`);
            return false;
        }
        
        // Short wait for input to fully settle before typing
        await sleep(500, 800);
        
        // Type password using the selector that actually matched — human-like delays
        console.log(`[${sessionName}] ⌨️  Typing password...`);
        const typed = await typeHumanLike(page, matchedSelector, password, sessionName);
        
        if (!typed) {
            console.log(`[${sessionName}] ❌ Failed to type password`);
            return false;
        }
        
        console.log(`[${sessionName}] ✓ Password entered`);
        
        // Log in button — primary via getByRole (matches div[role="button"] too), fallback CSS selectors
        let loginClicked = false;

        // Primary: getByRole matches both <button> and div[role="button"]
        try {
            const loginBtn = page.getByRole('button', { name: 'Log in' }).first();
            if (await loginBtn.isVisible()) {
                await sleep(500, 800);
                await loginBtn.click();
                console.log(`[${sessionName}] ✓ Clicked Log in button`);
                loginClicked = true;
            }
        } catch (e) {
            console.log(`[${sessionName}] ⚠️  Primary Log in button error: ${e.message}`);
        }

        // CSS fallbacks if primary failed
        if (!loginClicked) {
            const loginButtonSelectors = [
                'div[role="button"]:has-text("Log in")',
                'button[type="submit"]',
                'button:has-text("Log in")'
            ];
            for (const selector of loginButtonSelectors) {
                const button = page.locator(selector).first();
                if (await button.isVisible().catch(() => false)) {
                    await sleep(500, 800);
                    await button.click();
                    console.log(`[${sessionName}] ✓ Clicked Log in button (fallback)`);
                    loginClicked = true;
                    break;
                }
            }
        }
        
        if (!loginClicked) {
            console.log(`[${sessionName}] ⚠️  Could not find Log in button`);
            return false;
        }
        
        // Wait for authentication (modal should close)
        await sleep(3000, 4000);
        
        // Take screenshot after login attempt
        await takeDebugScreenshot(page, sessionName, 'after_password_login');

        // Detect wrong password: check if modal still visible after login attempt
        const modalStillOpen = await page.locator('input[type="password"]').isVisible().catch(() => false);
        if (modalStillOpen) {
            console.error(`[${sessionName}] ❌ Password rejected — modal still open after login attempt`);
            await takeDebugScreenshot(page, sessionName, 'wrong_password');
            await dumpPageDebugInfo(page, sessionName, 'wrong_password');
        }
        
        return true;
        
    } catch (error) {
        console.log(`[${sessionName}] Note: Password challenge check failed (${error.message})`);
        return false;
    }
}

/**
 * Take screenshot for debugging (on error)
 */
async function takeDebugScreenshot(page, sessionName, context) {
    try {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `debug_${sessionName}_${context}_${timestamp}.png`;
        const filepath = path.join(__dirname, 'debug_screenshots', filename);
        
        // Create debug folder if not exists
        const debugFolder = path.join(__dirname, 'debug_screenshots');
        if (!fs.existsSync(debugFolder)) {
            fs.mkdirSync(debugFolder, { recursive: true });
        }
        
        await page.screenshot({ path: filepath, fullPage: true });
        console.log(`[${sessionName}] 📸 Debug screenshot saved: ${filename}`);
        
        return filename;
    } catch (error) {
        console.log(`[${sessionName}] Warning: Could not take screenshot: ${error.message}`);
        return null;
    }
}

/**
 * Dump page DOM info for accurate debugging
 * Exports inputs, buttons, dialogs with visibility/attribute details to JSON
 */
async function dumpPageDebugInfo(page, sessionName, context) {
    try {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `debug_${sessionName}_${context}_${timestamp}.json`;
        const filepath = path.join(__dirname, 'debug_screenshots', filename);

        const debugFolder = path.join(__dirname, 'debug_screenshots');
        if (!fs.existsSync(debugFolder)) fs.mkdirSync(debugFolder, { recursive: true });

        const info = await page.evaluate(() => {
            const getAttrs = el => ({
                tag: el.tagName.toLowerCase(),
                type: el.type || null,
                name: el.name || null,
                placeholder: el.placeholder || null,
                ariaLabel: el.getAttribute('aria-label') || null,
                id: el.id || null,
                role: el.getAttribute('role') || null,
                text: (el.innerText || el.textContent || '').trim().substring(0, 100),
                visible: el.offsetParent !== null && getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden',
                disabled: el.disabled || false
            });
            return {
                url: window.location.href,
                inputs: Array.from(document.querySelectorAll('input')).map(getAttrs),
                buttons: Array.from(document.querySelectorAll('button, div[role="button"]')).map(getAttrs),
                dialogs: Array.from(document.querySelectorAll('div[role="dialog"]')).map(d => ({
                    childCount: d.children.length,
                    text: (d.innerText || '').substring(0, 200)
                }))
            };
        });

        fs.writeFileSync(filepath, JSON.stringify(info, null, 2));
        console.log(`[${sessionName}] 🔍 DOM debug info saved: ${filename}`);
        return filename;
    } catch (error) {
        console.log(`[${sessionName}] Warning: Could not dump debug info: ${error.message}`);
        return null;
    }
}

/**
 * Detect Instagram error pages
 * Returns: { hasError: boolean, errorType: string, canRetry: boolean, hasReloadButton: boolean }
 */
async function detectInstagramErrorPage(page, sessionName) {
    try {
        const pageState = await page.evaluate(() => {
            const bodyText = document.body.innerText || '';
            const bodyHTML = document.body.innerHTML || '';
            
            // Error Type 1: "Something went wrong"
            if (bodyText.includes('Something went wrong') && 
                bodyText.includes('page could not be loaded')) {
                return { 
                    hasError: true, 
                    errorType: 'something_went_wrong',
                    canRetry: true,
                    hasReloadButton: bodyText.includes('Reload page')
                };
            }
            
            // Error Type 2: "Sorry, this page isn't available"
            if (bodyText.includes("Sorry, this page isn't available") ||
                bodyText.includes("The link you followed may be broken")) {
                return { 
                    hasError: true, 
                    errorType: 'page_not_available',
                    canRetry: false,
                    hasReloadButton: false
                };
            }
            
            // Error Type 3: Rate limit / Try again later
            if (bodyText.includes('Try Again Later') ||
                bodyText.includes('Please wait a few minutes')) {
                return { 
                    hasError: true, 
                    errorType: 'rate_limit',
                    canRetry: true,
                    hasReloadButton: false
                };
            }
            
            // Error Type 4: Challenge required
            if (bodyText.includes('Challenge Required') ||
                bodyHTML.includes('challenge_required')) {
                return { 
                    hasError: true, 
                    errorType: 'challenge_required',
                    canRetry: false,
                    hasReloadButton: false
                };
            }
            
            // Error Type 5: Login required (session expired)
            if (bodyText.includes('Log in to continue') ||
                bodyHTML.includes('loginForm')) {
                return { 
                    hasError: true, 
                    errorType: 'session_expired',
                    canRetry: false,
                    hasReloadButton: false
                };
            }
            
            // Error Type 6: Scraping warning challenge
            if (window.location.href.includes('scraping_warning') ||
                bodyHTML.includes('scraping_warning')) {
                return {
                    hasError: true,
                    errorType: 'scraping_warning',
                    canRetry: false,
                    hasReloadButton: false
                };
            }
            
            return { hasError: false, errorType: null, canRetry: false, hasReloadButton: false };
        });
        
        return pageState;
        
    } catch (error) {
        console.log(`[${sessionName}] Error detection failed: ${error.message}`);
        return { hasError: false, errorType: null, canRetry: false, hasReloadButton: false };
    }
}

/**
 * Handle error page with smart retry
 * Max 2 retries with progressive backoff (5s, 15s)
 * Returns: { success: boolean, skipped: boolean, reason: string }
 */
async function handleErrorPageWithRetry(page, sessionName, username, maxRetries = 2) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        // Detect error
        const errorState = await detectInstagramErrorPage(page, sessionName);
        
        if (!errorState.hasError) {
            return { success: true, skipped: false, reason: null };
        }
        
        console.log(`[${sessionName}] ⚠️  Error detected: ${errorState.errorType} (Attempt ${attempt}/${maxRetries})`);
        
        // Take screenshot for debugging
        await takeDebugScreenshot(page, sessionName, `error_${errorState.errorType}_${username}_attempt_${attempt}`);
        
        // Check if retry is possible
        if (!errorState.canRetry) {
            console.log(`[${sessionName}] ❌ Error type '${errorState.errorType}' cannot be retried, skipping account`);
            return { success: false, skipped: true, reason: errorState.errorType };
        }
        
        // Progressive backoff: 5s, 15s (GitHub Actions friendly)
        const backoffTime = attempt === 1 ? 5000 : 15000;
        console.log(`[${sessionName}] ⏳ Waiting ${backoffTime/1000}s before retry...`);
        await sleep(backoffTime, backoffTime + 2000);
        
        // Try to reload
        if (errorState.hasReloadButton) {
            // Click "Reload page" button
            const reloadButtonSelectors = [
                'button:has-text("Reload page")',
                'button:text("Reload page")',
                'div[role="button"]:has-text("Reload page")'
            ];
            
            let clicked = false;
            for (const selector of reloadButtonSelectors) {
                const button = page.locator(selector).first();
                if (await button.count() > 0) {
                    await button.click();
                    console.log(`[${sessionName}] 🔄 Clicked "Reload page" button`);
                    clicked = true;
                    break;
                }
            }
            
            if (!clicked) {
                // Fallback: page.reload()
                await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
                console.log(`[${sessionName}] 🔄 Page reloaded (fallback)`);
            }
        } else {
            // No reload button, just reload page
            await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
            console.log(`[${sessionName}] 🔄 Page reloaded`);
        }
        
        // Wait for page to settle
        await sleep(3000, 4000);
        
        // Take screenshot after reload
        await takeDebugScreenshot(page, sessionName, `after_reload_${username}_attempt_${attempt}`);
        
        // Check if error resolved
        const recheckState = await detectInstagramErrorPage(page, sessionName);
        if (!recheckState.hasError) {
            console.log(`[${sessionName}] ✅ Error resolved after retry ${attempt}`);
            return { success: true, skipped: false, reason: null };
        }
        
        console.log(`[${sessionName}] ⚠️  Error persists after retry ${attempt}`);
    }
    
    // Max retries reached
    console.log(`[${sessionName}] ❌ Max retries (${maxRetries}) reached, skipping account`);
    return { success: false, skipped: true, reason: 'max_retries_exceeded' };
}

/**
 * Shuffle array using Fisher-Yates algorithm (anti-detection)
 * Randomizes account order to avoid predictable patterns
 */
function shuffleArray(array) {
    const shuffled = [...array];  // Create copy to avoid mutating original
    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
}

async function downloadImage(imageUrl, postId, retries = 3) {
    if (!imageUrl || !postId) return null;

    let extension = 'jpg';
    try {
        const urlPath = new URL(imageUrl).pathname;
        const match = urlPath.match(/\.(jpg|jpeg|png|gif|webp|heic)$/i);
        if (match) {
            extension = match[1].toLowerCase();
            if (extension === 'heic') extension = 'jpg';
        }
    } catch (e) {}

    const filename = `${postId}.${extension}`;
    const filepath = path.join(IMAGES_FOLDER, filename);

    if (fs.existsSync(filepath)) return filename;

    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            const response = await fetch(imageUrl);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const blob = await response.blob();
            const arrayBuffer = await blob.arrayBuffer();
            const buffer = Buffer.from(arrayBuffer);
            
            await fs.promises.writeFile(filepath, buffer);
            return filename;
        } catch (error) {
            if (attempt === retries) {
                return null;
            }
            await sleep(1000 * attempt, 2000 * attempt);
        }
    }
    return null;
}

/**
 * Scrape accounts using a single session/context
 */
async function scrapeWithContext(context, accounts, sessionName, sessionNumber, passwords) {
    console.log(`\n[${sessionName}] Starting scraper for ${accounts.length} accounts`);
    console.log(`[${sessionName}] Accounts: ${accounts.map(a => '@' + a).join(', ')}`);
    
    const page = await context.newPage();
    const results = {};
    const completedAccounts = [];  // Track successfully completed accounts
    let stats = {
        totalPosts: 0,
        totalCaptions: 0,
        totalImages: 0,
        totalDeepScraped: 0
    };

    try {
        // Navigate to Instagram and verify login
        console.log(`[${sessionName}] Navigating to Instagram...`);
        try {
            await page.goto('https://www.instagram.com/', { 
                waitUntil: 'domcontentloaded', 
                timeout: 30000 
            });
        } catch (gotoError) {
            if (gotoError.message.includes('ERR_TOO_MANY_REDIRECTS')) {
                console.error(`[${sessionName}] ✗ Redirect loop detected — session cookie expired/invalid or account flagged for scraping`);
                console.error(`[${sessionName}] ℹ️  Fix: Regenerate session${sessionNumber}.json and update GitHub Secret INSTAGRAM_SESSION_${sessionNumber}`);
            } else {
                console.error(`[${sessionName}] ✗ Navigation failed: ${gotoError.message}`);
            }
            await takeDebugScreenshot(page, sessionName, 'initial_goto_failed');
            throw gotoError;
        }
        await sleep(3000, 4000);

        // Check and dismiss automated behavior popup (after login)
        await dismissAutomatedBehaviorPopup(page, sessionName);

        // Handle account selection screen (Continue button)
        await handleAccountSelectionScreen(page, sessionName);

        // Handle password challenge (if prompted)
        const passwordHandled = await handlePasswordChallenge(page, sessionName, sessionNumber, passwords);
        if (!passwordHandled) {
            console.log(`[${sessionName}] ⚠️  Password challenge not resolved`);
        }

        const isLoggedIn = await page.locator('svg[aria-label*="Search"], svg[aria-label*="Home"]').count() > 0;

        if (!isLoggedIn) {
            console.log(`[${sessionName}] ERROR: Not logged in!`);
            await takeDebugScreenshot(page, sessionName, 'not_logged_in');
            throw new Error(`Session ${sessionName} is not authenticated`);
        }

        console.log(`[${sessionName}] ✓ Authenticated successfully`);

        // Scrape each account
        const failedAccounts = [];  // Track failed accounts with reasons
        
        for (let i = 0; i < accounts.length; i++) {
            const username = accounts[i];
            console.log(`\n[${sessionName}] ${"=".repeat(50)}`);
            console.log(`[${sessionName}] Processing @${username} (${i + 1}/${accounts.length})`);
            console.log(`[${sessionName}] ${"=".repeat(50)}`);
            
            await page.goto(`https://www.instagram.com/${username}/`, { 
                waitUntil: 'domcontentloaded', 
                timeout: 30000 
            });
            await sleep(2000, 3000);
            
            // Check and dismiss automated behavior popup (after profile navigation)
            await dismissAutomatedBehaviorPopup(page, sessionName);
            
            // Handle account selection screen (can appear at any point, not just on initial login)
            await handleAccountSelectionScreen(page, sessionName);
            
            // NEW: Check for error page and retry if needed
            const errorHandleResult = await handleErrorPageWithRetry(page, sessionName, username);
            if (!errorHandleResult.success) {
                console.log(`[${sessionName}] ⚠️  Skipping @${username} due to error: ${errorHandleResult.reason}`);
                failedAccounts.push({ username, reason: errorHandleResult.reason });
                continue; // Skip to next account
            }
            
            try {
                await page.waitForSelector('a[href*="/p/"], a[href*="/reel/"]', { timeout: 15000 });
                console.log(`[${sessionName}] Post grid detected`);
            } catch (e) {
                console.log(`[${sessionName}] WARNING: Could not detect post grid`);
                await takeDebugScreenshot(page, sessionName, `no_grid_${username}`);
                failedAccounts.push({ username, reason: 'no_post_grid' });
                continue;
            }

            let scrapedPosts = new Map();
            let downloadedImages = 0;
            let deepScrapedCount = 0;

            console.log(`[${sessionName}] Starting scroll sequence (${config.scrollCount} scrolls)...`);
            
            for (let scrollIndex = 0; scrollIndex < config.scrollCount; scrollIndex++) {
                console.log(`[${sessionName}]   Scroll ${scrollIndex + 1}/${config.scrollCount}...`);
                
                await sleep(2000, 3000);
                
                try {
                    await page.waitForSelector('div.x1s85apg h2 span', { timeout: 5000 });
                } catch (e) {
                    // Caption elements may load slower
                }
                
                const visibleData = await page.evaluate(() => {
                    const results = [];
                    const anchors = Array.from(document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]'));
                    
                    anchors.forEach(link => {
                        const url = link.href;
                        const match = url.match(/\/(?:p|reel)\/([^\/\?]+)/);
                        const postId = match ? match[1] : null;
                        if (!postId) return;

                        const img = link.querySelector('img');
                        let caption = "";
                        let needsDeepScrape = false;
                        
                        let container = link.closest('div.x1lliihq.x1n2onr6.xh8yej3.x4gyw5p.x1mpyi22.x1j53mea');
                        if (container && container.parentElement) {
                            const siblings = Array.from(container.parentElement.children);
                            for (const sibling of siblings) {
                                if (sibling.classList.contains('x1s85apg')) {
                                    const captionSpan = sibling.querySelector('h2 span.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft');
                                    if (captionSpan) {
                                        caption = captionSpan.innerText || captionSpan.textContent || "";
                                        if (caption.trim()) break;
                                    }
                                }
                            }
                        }
                        
                        if (!caption.trim()) {
                            const imgAlt = img ? (img.alt || "").trim() : "";
                            if (imgAlt && !imgAlt.startsWith('Photo by') && !imgAlt.startsWith('Photo shared by')) {
                                caption = imgAlt;
                            } else {
                                needsDeepScrape = true;
                            }
                        }
                        
                        results.push({
                            url: url,
                            post_id: postId,
                            caption: caption.trim(),
                            image_url: img ? img.src : null,
                            needs_deep_scrape: needsDeepScrape
                        });
                    });
                    return results;
                });

                let newPosts = 0;
                let postsNeedingDeepScrape = [];
                
                for (const p of visibleData) {
                    const existingPost = scrapedPosts.get(p.post_id);
                    
                    if (!existingPost) {
                        newPosts++;
                        
                        if (p.needs_deep_scrape && config.deepScrapeMode) {
                            postsNeedingDeepScrape.push(p);
                        }
                        
                        let downloadedFilename = null;
                        if (config.downloadImages && p.image_url) {
                            downloadedFilename = await downloadImage(p.image_url, p.post_id);
                            if (downloadedFilename) downloadedImages++;
                        }
                        
                        const { needs_deep_scrape, ...postData } = p;
                        if (downloadedFilename) postData.downloaded_image = downloadedFilename;
                        
                        scrapedPosts.set(p.post_id, postData);
                    } else if (!existingPost.caption && p.needs_deep_scrape && config.deepScrapeMode) {
                        if (!postsNeedingDeepScrape.find(post => post.post_id === p.post_id)) {
                            postsNeedingDeepScrape.push(p);
                        }
                    }
                }
                
                const postsWithCaptions = Array.from(scrapedPosts.values()).filter(p => p.caption && p.caption.trim()).length;
                console.log(`[${sessionName}]     Posts: ${scrapedPosts.size} total (${newPosts} new) | Captions: ${postsWithCaptions}/${scrapedPosts.size} (${(postsWithCaptions/scrapedPosts.size*100).toFixed(1)}%)`);
                
                if (config.downloadImages && newPosts > 0) {
                    console.log(`[${sessionName}]     Images: ${downloadedImages}/${scrapedPosts.size}`);
                }
                
                if (config.deepScrapeMode && postsNeedingDeepScrape.length > 0) {
                    console.log(`[${sessionName}]     Deep scraping ${postsNeedingDeepScrape.length} posts...`);
                    
                    let deepScrapedSuccess = 0;
                    for (const post of postsNeedingDeepScrape) {
                        try {
                            const postLink = await page.locator(`a[href*="/${post.post_id}/"]`).first();
                            if (await postLink.count() > 0) {
                                await postLink.click();
                                
                                try {
                                    await page.waitForSelector('div[role="dialog"]', { timeout: 5000 });
                                    await sleep(1500, 2000);
                                } catch (e) {}
                                
                                const detailResult = await page.evaluate(() => {
                                    const modal = document.querySelector('div[role="dialog"]');
                                    if (!modal) return { caption: "", found: false };
                                    
                                    const h1Caption = modal.querySelector('h1._ap3a._aaco._aacu._aacx._aad7._aade');
                                    if (h1Caption) {
                                        const text = (h1Caption.innerText || h1Caption.textContent || "").trim();
                                        if (text) return { caption: text, found: true };
                                    }
                                    
                                    const h1WithClass = modal.querySelector('h1._ap3a');
                                    if (h1WithClass) {
                                        const text = (h1WithClass.innerText || h1WithClass.textContent || "").trim();
                                        if (text) return { caption: text, found: true };
                                    }
                                    
                                    return { caption: "", found: false };
                                });
                                
                                if (detailResult.found && detailResult.caption) {
                                    const updatedPost = scrapedPosts.get(post.post_id);
                                    if (updatedPost) {
                                        updatedPost.caption = detailResult.caption;
                                        scrapedPosts.set(post.post_id, updatedPost);
                                        deepScrapedSuccess++;
                                    }
                                }
                                
                                await page.keyboard.press('Escape');
                                await sleep(600, 900);
                            }
                        } catch (err) {
                            try {
                                await page.keyboard.press('Escape');
                                await sleep(400, 600);
                            } catch (e) {}
                        }
                    }
                    
                    deepScrapedCount += deepScrapedSuccess;
                    console.log(`[${sessionName}]     Recovered: ${deepScrapedSuccess}/${postsNeedingDeepScrape.length} captions`);
                }

                if (scrollIndex < config.scrollCount - 1) {
                    const scrollDistance = Math.floor(Math.random() * 400 + 800);
                    await page.evaluate((distance) => window.scrollBy(0, distance), scrollDistance);
                    await sleep(2500, 3500);
                }
            }
            
            const finalCaptionCount = Array.from(scrapedPosts.values()).filter(p => p.caption && p.caption.trim()).length;
            
            console.log(`\n[${sessionName}] @${username} Summary:`);
            console.log(`[${sessionName}]   Posts: ${scrapedPosts.size}`);
            console.log(`[${sessionName}]   Captions: ${finalCaptionCount}/${scrapedPosts.size} (${(finalCaptionCount/scrapedPosts.size*100).toFixed(1)}%)`);
            if (config.downloadImages) {
                console.log(`[${sessionName}]   Images: ${downloadedImages}/${scrapedPosts.size}`);
            }
            if (deepScrapedCount > 0) {
                console.log(`[${sessionName}]   Deep scraped: ${deepScrapedCount}`);
            }

            results[username] = Array.from(scrapedPosts.values());
            completedAccounts.push(username);  // Mark account as completed
            
            stats.totalPosts += scrapedPosts.size;
            stats.totalCaptions += finalCaptionCount;
            stats.totalImages += downloadedImages;
            stats.totalDeepScraped += deepScrapedCount;
        }

        await page.close();
        
        // Enhanced logging with failed accounts summary
        console.log(`\n[${sessionName}] ✓ Completed: ${stats.totalPosts} posts from ${completedAccounts.length}/${accounts.length} accounts`);
        
        if (failedAccounts.length > 0) {
            console.log(`[${sessionName}] ⚠️  Failed accounts: ${failedAccounts.length}`);
            failedAccounts.forEach(({ username, reason }) => {
                console.log(`[${sessionName}]   - @${username}: ${reason}`);
            });
        }
        
        return { results, stats, completedAccounts, failedAccounts };

    } catch (error) {
        console.error(`\n[${sessionName}] ✗ Error:`, error.message);
        try { await takeDebugScreenshot(page, sessionName, 'fatal_error'); } catch (e) {}
        try {
            await page.close();
        } catch (e) {}
        
        // Return partial results with completed and failed accounts
        return { results, stats, completedAccounts, failedAccounts: [] };
    }
}

/**
 * Main parallel scraping function
 */
async function main() {
    const startTime = Date.now();
    
    console.log("\n" + "=".repeat(70));
    console.log("[PARALLEL SCRAPER] Instagram Multi-Session Scraper Starting...");
    console.log("=".repeat(70));
    
    // Load Instagram passwords
    const passwords = loadInstagramPasswords();
    console.log(`[SETUP] Loaded passwords for ${Object.keys(passwords).length} sessions`);
    
    // Initialize checkpoint manager
    const checkpoint = new ScraperCheckpoint();
    
    // Check for existing checkpoint and get accounts to process
    const configAccounts = config.accounts;
    let accountsToProcess = checkpoint.getRemainingAccounts(configAccounts);
    
    // If no accounts to process (all completed), clear checkpoint and use all accounts
    if (accountsToProcess.length === 0) {
        accountsToProcess = configAccounts;
    }
    
    // Shuffle accounts for anti-detection (randomize order)
    const allAccounts = shuffleArray(accountsToProcess);
    console.log(`[ANTI-DETECTION] Accounts shuffled randomly`);
    console.log(`[ANTI-DETECTION] Order changes each run to avoid patterns`);
    console.log(`[CONFIG] Processing ${allAccounts.length} accounts`);

    // Create images folder
    if (config.downloadImages && !fs.existsSync(IMAGES_FOLDER)) {
        fs.mkdirSync(IMAGES_FOLDER, { recursive: true });
        console.log(`[SETUP] Created images folder`);
    }

    // Launch browser
    console.log("\n[SETUP] Launching browser...");
    const browser = await chromium.launch({
        headless: true,
        args: [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage'
        ]
    });

    try {
        // Auto-detect available sessions (dynamic, scalable)
        console.log("[SETUP] Auto-detecting available sessions...");
        const availableSessions = [];
        
        for (let i = 1; i <= 10; i++) {  // Support up to 10 sessions
            const sessionFile = `session${i}.json`;
            const sessionPath = path.join(__dirname, sessionFile);
            
            if (fs.existsSync(sessionPath)) {
                try {
                    const sessionManager = new SessionManager(sessionFile);
                    const cookies = sessionManager.loadSession();
                    
                    // Validate session has cookies
                    if (cookies && cookies.length > 0) {
                        const sessionInfo = sessionManager.getInfo();
                        const expiryNote = sessionInfo.sessionExpiry
                            ? (new Date() > sessionInfo.sessionExpiry ? ' ⚠️  cookie may be expired' : '')
                            : '';
                        availableSessions.push({
                            id: i,
                            file: sessionFile,
                            manager: sessionManager,
                            cookies: cookies
                        });
                        console.log(`[SETUP] ✓ Session ${i} detected (${cookies.length} cookies)${expiryNote}`);
                    } else {
                        console.log(`[SETUP] ⚠️  Session ${i} file exists but empty, skipping`);
                    }
                } catch (error) {
                    console.log(`[SETUP] ⚠️  Session ${i} invalid, skipping: ${error.message}`);
                }
            }
        }
        
        if (availableSessions.length === 0) {
            console.error("[ERROR] No valid sessions found! Please generate sessions first.");
            console.error("[ERROR] Run: node generate-sessions.js");
            process.exit(1);
        }
        
        console.log(`[SETUP] Found ${availableSessions.length} valid sessions`);
        
        // Split accounts dynamically based on available sessions
        const accountsPerSession = Math.ceil(allAccounts.length / availableSessions.length);
        const sessionAccountGroups = [];
        
        for (let i = 0; i < availableSessions.length; i++) {
            const start = i * accountsPerSession;
            const end = Math.min(start + accountsPerSession, allAccounts.length);
            sessionAccountGroups.push(allAccounts.slice(start, end));
        }
        
        console.log(`[SETUP] Accounts distribution:`);
        sessionAccountGroups.forEach((group, i) => {
            console.log(`[SETUP]   Session ${i + 1}: ${group.length} accounts`);
        });

        // Create browser contexts dynamically
        console.log("[SETUP] Creating browser contexts...");
        const contexts = [];
        
        for (let i = 0; i < availableSessions.length; i++) {
            const session = availableSessions[i];
            const context = await browser.newContext({
                viewport: { width: 1280, height: 900 },
                userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            });
            await context.addCookies(session.cookies);
            contexts.push(context);
            console.log(`[SETUP] ✓ Context ${i + 1} created (Session ${session.id})`);
        }

        console.log(`\n[PARALLEL] Starting ${availableSessions.length} parallel sessions with staggered delays...`);
        for (let i = 0; i < availableSessions.length; i++) {
            const delayMin = i * 15;  // 0s, 15s, 30s, 45s, 60s...
            const delayMax = delayMin + 15;
            console.log(`[PARALLEL] Session ${i + 1}: Starting after ${delayMin}-${delayMax} seconds`);
        }
        console.log("=".repeat(70));

        // Run all sessions in parallel with staggered starts (dynamic)
        const scrapePromises = contexts.map((context, i) => {
            return (async () => {
                const delayMin = i * 15000;  // 0ms, 15s, 30s, 45s, 60s...
                const delayMax = delayMin + 15000;
                const delay = Math.floor(Math.random() * (delayMax - delayMin) + delayMin);
                
                if (delay > 0) {
                    console.log(`\n[SESSION-${i + 1}] Waiting ${Math.floor(delay/1000)}s before starting...`);
                    await sleep(delay, delay);
                }
                
                return scrapeWithContext(
                    context, 
                    sessionAccountGroups[i], 
                    `SESSION-${i + 1}`,
                    availableSessions[i].id,  // Pass session number
                    passwords  // Pass passwords map
                );
            })();
        });
        
        const results = await Promise.all(scrapePromises);

        const endTime = Date.now();
        const totalDuration = Math.round((endTime - startTime) / 1000);

        // Merge results dynamically
        console.log("\n" + "=".repeat(70));
        console.log("[MERGE] Merging results from all sessions...");
        
        const allResults = {};
        const allCompletedAccounts = [];  // Track all completed accounts
        const allFailedAccounts = [];  // Track all failed accounts
        const totalStats = {
            totalPosts: 0,
            totalCaptions: 0,
            totalImages: 0,
            totalDeepScraped: 0
        };
        
        results.forEach(result => {
            Object.assign(allResults, result.results);
            allCompletedAccounts.push(...result.completedAccounts);
            if (result.failedAccounts && result.failedAccounts.length > 0) {
                allFailedAccounts.push(...result.failedAccounts);
            }
            totalStats.totalPosts += result.stats.totalPosts;
            totalStats.totalCaptions += result.stats.totalCaptions;
            totalStats.totalImages += result.stats.totalImages;
            totalStats.totalDeepScraped += result.stats.totalDeepScraped;
        });

        // Save merged results
        fs.writeFileSync(OUTPUT_FILE, JSON.stringify(allResults, null, 2));

        // Save failed accounts to separate file for review
        if (allFailedAccounts.length > 0) {
            const failedAccountsFile = path.join(__dirname, 'failed_accounts.json');
            const failedAccountsData = {
                timestamp: new Date().toISOString(),
                total_failed: allFailedAccounts.length,
                failed_accounts: allFailedAccounts
            };
            fs.writeFileSync(failedAccountsFile, JSON.stringify(failedAccountsData, null, 2));
            console.log(`[MERGE] ⚠️  Saved ${allFailedAccounts.length} failed accounts to failed_accounts.json`);
        }

        // Update checkpoint with completed accounts
        if (allCompletedAccounts.length > 0) {
            const remainingAccounts = configAccounts.filter(
                account => !allCompletedAccounts.includes(account)
            );
            
            if (remainingAccounts.length === 0) {
                // All accounts completed - clear checkpoint
                console.log("[CHECKPOINT] All accounts processed successfully");
                checkpoint.clear();
            } else {
                // Save progress for resume
                checkpoint.save(
                    allCompletedAccounts,
                    remainingAccounts,
                    configAccounts.length,
                    totalStats
                );
            }
        }

        console.log("[MERGE] ✓ Results merged successfully");
        console.log("=".repeat(70));
        console.log("[COMPLETE] Multi-Session Scraping Complete!");
        console.log("=".repeat(70));
        console.log("[SUMMARY] Overall Statistics:");
        console.log(`  Sessions Used:      ${availableSessions.length}`);
        console.log(`  Accounts Processed: ${allCompletedAccounts.length}/${allAccounts.length}`);
        console.log(`  Total Posts:        ${totalStats.totalPosts}`);
        console.log(`  Captions Extracted: ${totalStats.totalCaptions}/${totalStats.totalPosts} (${(totalStats.totalCaptions/totalStats.totalPosts*100).toFixed(1)}%)`);
        if (config.downloadImages) {
            console.log(`  Images Downloaded:  ${totalStats.totalImages}/${totalStats.totalPosts} (${(totalStats.totalImages/totalStats.totalPosts*100).toFixed(1)}%)`);
        }
        if (config.deepScrapeMode && totalStats.totalDeepScraped > 0) {
            console.log(`  Deep Scraped:       ${totalStats.totalDeepScraped} captions recovered`);
        }
        
        // Enhanced logging for failed accounts
        if (allFailedAccounts.length > 0) {
            console.log(`  Failed Accounts:    ${allFailedAccounts.length}`);
            console.log(`\n[FAILED ACCOUNTS] Summary:`);
            
            // Group by error type
            const errorGroups = {};
            allFailedAccounts.forEach(({ username, reason }) => {
                if (!errorGroups[reason]) {
                    errorGroups[reason] = [];
                }
                errorGroups[reason].push(username);
            });
            
            // Display grouped errors
            Object.entries(errorGroups).forEach(([reason, accounts]) => {
                console.log(`  ${reason}: ${accounts.length} accounts`);
                accounts.forEach(username => {
                    console.log(`    - @${username}`);
                });
            });
        }
        
        console.log(`  Total Duration:     ${totalDuration}s (~${Math.round(totalDuration/60)} minutes)`);
        console.log(`  Output File:        ${OUTPUT_FILE}`);
        console.log("=".repeat(70) + "\n");

    } finally {
        await browser.close();
    }
}

main().catch(error => {
    console.error("\n✗ Fatal error:", error);
    console.error("[ERROR] Scraping failed - checkpoint may have been saved for resume");
    process.exit(1);
});
