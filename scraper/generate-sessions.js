/**
 * Instagram Session Generator (Configurable)
 * 
 * This script helps generate session files for multiple Instagram accounts
 * with proper browser fingerprint isolation and best practices.
 * 
 * Features:
 * - Configurable session count (2, 3, or 5 sessions)
 * - Different browser fingerprints per session (viewport, user agent)
 * - Manual login with visual feedback
 * - Automatic session detection and saving
 * - Proper cleanup between sessions
 * 
 * Configuration:
 *   Change SESSION_COUNT below to generate 2, 3, or 5 sessions
 * 
 * Usage:
 *   node generate-sessions.js
 * 
 * The script will:
 * 1. Open browser for Account 1
 * 2. Wait for you to login manually
 * 3. Detect successful login
 * 4. Save session1.json
 * 5. Close browser
 * 6. Repeat for remaining accounts
 */

const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

chromium.use(stealth());

// ============================================
// CONFIGURATION
// ============================================
// Change this to generate 2, 3, or 5 sessions
// Recommended: Start with 2-3 to avoid Instagram blocking
const SESSION_COUNT = 3;  // Default: 3 sessions

// ============================================
// BROWSER CONFIGURATIONS (Dynamic)
// ============================================
/**
 * Generate browser configurations based on SESSION_COUNT
 * Each session gets unique fingerprint to avoid detection
 */
function generateBrowserConfigs(count) {
    // Base configurations for up to 5 sessions
    const baseConfigs = [
        {
            viewport: { width: 1920, height: 1080 },
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            timezone: 'America/New_York'
        },
        {
            viewport: { width: 1366, height: 768 },
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
            timezone: 'America/Los_Angeles'
        },
        {
            viewport: { width: 1440, height: 900 },
            userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            timezone: 'America/Chicago'
        },
        {
            viewport: { width: 1536, height: 864 },
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            timezone: 'America/Denver'
        },
        {
            viewport: { width: 1280, height: 720 },
            userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            timezone: 'America/Phoenix'
        }
    ];
    
    // Validate count
    if (count < 2 || count > 5) {
        console.error(`\n✗ ERROR: SESSION_COUNT must be between 2 and 5 (got ${count})`);
        console.error('Please update SESSION_COUNT in the script and try again.');
        process.exit(1);
    }
    
    // Generate configs
    const configs = [];
    for (let i = 0; i < count; i++) {
        const base = baseConfigs[i];
        configs.push({
            name: `Session ${i + 1}`,
            outputFile: `session${i + 1}.json`,
            viewport: base.viewport,
            userAgent: base.userAgent,
            locale: 'en-US',
            timezone: base.timezone
        });
    }
    
    return configs;
}

// Generate browser configs based on SESSION_COUNT
const BROWSER_CONFIGS = generateBrowserConfigs(SESSION_COUNT);

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Check if user is logged in to Instagram
 */
async function isLoggedIn(page) {
    try {
        // Check for elements that only appear when logged in
        const homeIcon = await page.locator('svg[aria-label*="Home"]').count();
        const searchIcon = await page.locator('svg[aria-label*="Search"]').count();
        return homeIcon > 0 || searchIcon > 0;
    } catch (error) {
        return false;
    }
}

/**
 * Wait for user to complete login manually
 */
async function waitForLogin(page, sessionName) {
    console.log(`\n[${ sessionName}] Waiting for you to login manually...`);
    console.log(`[${sessionName}] Please:`);
    console.log(`[${sessionName}]   1. Enter your Instagram username/email`);
    console.log(`[${sessionName}]   2. Enter your password`);
    console.log(`[${sessionName}]   3. Click "Log in"`);
    console.log(`[${sessionName}]   4. Complete any 2FA if required`);
    console.log(`[${sessionName}]   5. Wait for Instagram home page to load`);
    console.log(`[${sessionName}] `);
    console.log(`[${sessionName}] The script will automatically detect when you're logged in...`);

    // Poll every 2 seconds to check if logged in
    let attempts = 0;
    const maxAttempts = 300; // 10 minutes timeout

    while (attempts < maxAttempts) {
        await sleep(2000);
        attempts++;

        if (await isLoggedIn(page)) {
            console.log(`\n[${sessionName}] ✓ Login detected successfully!`);
            return true;
        }

        // Show progress every 30 seconds
        if (attempts % 15 === 0) {
            console.log(`[${sessionName}] Still waiting... (${Math.floor(attempts * 2 / 60)} minutes elapsed)`);
        }
    }

    console.log(`\n[${sessionName}] ✗ Timeout: Login not detected after 10 minutes`);
    return false;
}

/**
 * Generate session for a single Instagram account
 */
async function generateSession(config) {
    console.log("\n" + "=".repeat(70));
    console.log(`[${config.name}] Starting session generation`);
    console.log("=".repeat(70));
    console.log(`[${config.name}] Output file: ${config.outputFile}`);
    console.log(`[${config.name}] Viewport: ${config.viewport.width}x${config.viewport.height}`);
    console.log(`[${config.name}] User Agent: ${config.userAgent.substring(0, 50)}...`);
    console.log(`[${config.name}] Timezone: ${config.timezone}`);
    console.log("=".repeat(70));

    // Launch browser with unique fingerprint
    const browser = await chromium.launch({
        headless: false,  // Must be visible for manual login
        args: [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage'
        ]
    });

    try {
        // Create context with unique fingerprint
        const context = await browser.newContext({
            viewport: config.viewport,
            userAgent: config.userAgent,
            locale: config.locale,
            timezoneId: config.timezone,
            // Additional fingerprint variations
            deviceScaleFactor: 1,
            isMobile: false,
            hasTouch: false,
            colorScheme: 'light'
        });

        const page = await context.newPage();

        console.log(`\n[${config.name}] Opening Instagram login page...`);
        await page.goto('https://www.instagram.com/accounts/login/', {
            waitUntil: 'domcontentloaded',
            timeout: 30000
        });

        await sleep(2000);

        // Check if already logged in (shouldn't happen, but handle it)
        if (await isLoggedIn(page)) {
            console.log(`\n[${config.name}] ⚠️  Already logged in! Please logout first.`);
            console.log(`[${config.name}] Waiting 10 seconds for you to logout...`);
            await sleep(10000);
        }

        // Wait for manual login
        const loginSuccess = await waitForLogin(page, config.name);

        if (!loginSuccess) {
            console.log(`\n[${config.name}] ✗ Failed to detect login. Skipping session save.`);
            await browser.close();
            return false;
        }

        // Give Instagram a moment to fully load and set all cookies
        console.log(`\n[${config.name}] Waiting 5 seconds for Instagram to fully load...`);
        await sleep(5000);

        // Navigate to home to ensure all cookies are set
        console.log(`[${config.name}] Navigating to Instagram home...`);
        await page.goto('https://www.instagram.com/', {
            waitUntil: 'domcontentloaded',
            timeout: 30000
        });
        await sleep(3000);

        // Verify still logged in
        if (!await isLoggedIn(page)) {
            console.log(`\n[${config.name}] ✗ Login verification failed. Please try again.`);
            await browser.close();
            return false;
        }

        // Extract cookies (Playwright's native format)
        console.log(`\n[${config.name}] Extracting session cookies...`);
        const cookies = await context.cookies();
        console.log(`[${config.name}] Found ${cookies.length} cookies`);

        // Save to file
        const outputPath = path.join(__dirname, config.outputFile);
        fs.writeFileSync(outputPath, JSON.stringify(cookies, null, 2));
        console.log(`[${config.name}] ✓ Session saved to: ${outputPath}`);

        // Show file info
        const stats = fs.statSync(outputPath);
        console.log(`[${config.name}] File size: ${stats.size} bytes`);

        // Show important cookies (for verification)
        const importantCookies = cookies.filter(c => 
            c.name.includes('sessionid') || 
            c.name.includes('csrftoken') ||
            c.name.includes('ds_user_id')
        );
        console.log(`\n[${config.name}] Important cookies found:`);
        importantCookies.forEach(c => {
            console.log(`[${config.name}]   - ${c.name}: ${c.value.substring(0, 20)}...`);
        });

        console.log(`\n[${config.name}] ✓ Session generation complete!`);
        console.log("=".repeat(70));

        // Keep browser open for 3 seconds so user can see success
        await sleep(3000);
        await browser.close();

        return true;

    } catch (error) {
        console.error(`\n[${config.name}] ✗ Error during session generation:`, error.message);
        await browser.close();
        return false;
    }
}

/**
 * Main function - generate sessions based on SESSION_COUNT
 */
async function main() {
    console.log("\n" + "=".repeat(70));
    console.log("Instagram Multi-Session Generator (Configurable)");
    console.log("=".repeat(70));
    console.log(`\nThis script will help you generate ${SESSION_COUNT} session files for parallel scraping.`);
    console.log("\nIMPORTANT:");
    console.log(`  - Use ${SESSION_COUNT} DIFFERENT Instagram accounts`);
    console.log("  - Each account should be aged (not brand new)");
    console.log("  - Each account should have access to target profiles");
    console.log("  - You will login MANUALLY for each account");
    console.log("\nThe script will:");
    console.log("  1. Open browser with unique fingerprint");
    console.log("  2. Navigate to Instagram login");
    console.log("  3. Wait for you to login manually");
    console.log("  4. Detect successful login automatically");
    console.log("  5. Save session file");
    console.log("  6. Close browser");
    console.log("  7. Repeat for next account");
    console.log("\n" + "=".repeat(70));
    console.log(`\n📝 Configuration: SESSION_COUNT = ${SESSION_COUNT}`);
    console.log(`   To change: Edit SESSION_COUNT constant in this file`);
    console.log("=".repeat(70));

    // Ask for confirmation
    console.log("\nPress Ctrl+C to cancel, or wait 5 seconds to continue...");
    await sleep(5000);

    const results = [];

    // Generate each session sequentially
    for (let i = 0; i < BROWSER_CONFIGS.length; i++) {
        const config = BROWSER_CONFIGS[i];
        
        console.log(`\n\n${"#".repeat(70)}`);
        console.log(`# ACCOUNT ${i + 1} of ${SESSION_COUNT}`);
        console.log(`${"#".repeat(70)}`);

        const success = await generateSession(config);
        results.push({ session: config.name, success });

        if (success && i < BROWSER_CONFIGS.length - 1) {
            console.log(`\n\n[INFO] Waiting 10 seconds before starting next session...`);
            console.log(`[INFO] This delay helps avoid Instagram rate limiting.`);
            await sleep(10000);
        }
    }

    // Final summary
    console.log("\n\n" + "=".repeat(70));
    console.log("SESSION GENERATION SUMMARY");
    console.log("=".repeat(70));
    
    results.forEach((result, index) => {
        const status = result.success ? '✓ SUCCESS' : '✗ FAILED';
        const file = BROWSER_CONFIGS[index].outputFile;
        console.log(`${status} - ${result.session} (${file})`);
    });

    const successCount = results.filter(r => r.success).length;
    console.log(`\nTotal: ${successCount}/${SESSION_COUNT} sessions generated successfully`);

    if (successCount === SESSION_COUNT) {
        console.log("\n✓ All sessions generated successfully!");
        console.log("\nNext steps:");
        console.log(`  1. Verify all ${SESSION_COUNT} session files exist:`);
        for (let i = 1; i <= SESSION_COUNT; i++) {
            console.log(`     - session${i}.json`);
        }
        console.log("\n  2. Add to GitHub Secrets:");
        for (let i = 1; i <= SESSION_COUNT; i++) {
            console.log(`     - INSTAGRAM_SESSION_${i} = <content of session${i}.json>`);
        }
        console.log("\n  3. Test locally:");
        console.log("     node scraper-parallel.js");
    } else {
        console.log("\n⚠️  Some sessions failed to generate.");
        console.log("Please run the script again for failed sessions.");
    }

    console.log("\n" + "=".repeat(70));
}

// Run the script
main().catch(error => {
    console.error("\n✗ Fatal error:", error);
    process.exit(1);
});
