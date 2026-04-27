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

chromium.use(stealth());

// Configuration
const config = require('../config/scraper.config.json');
const OUTPUT_FILE = path.join(__dirname, 'instagram_data.json');
const IMAGES_FOLDER = path.join(__dirname, 'instagram_images');  // Save to scraper/instagram_images/

// Helper functions
const sleep = (min, max) => new Promise(resolve => 
    setTimeout(resolve, Math.floor(Math.random() * (max - min + 1) + min))
);

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
async function scrapeWithContext(context, accounts, sessionName) {
    console.log(`\n[${sessionName}] Starting scraper for ${accounts.length} accounts`);
    console.log(`[${sessionName}] Accounts: ${accounts.map(a => '@' + a).join(', ')}`);
    
    const page = await context.newPage();
    const results = {};
    let stats = {
        totalPosts: 0,
        totalCaptions: 0,
        totalImages: 0,
        totalDeepScraped: 0
    };

    try {
        // Navigate to Instagram and verify login
        console.log(`[${sessionName}] Navigating to Instagram...`);
        await page.goto('https://www.instagram.com/', { 
            waitUntil: 'domcontentloaded', 
            timeout: 30000 
        });
        await sleep(3000, 4000);

        const isLoggedIn = await page.locator('svg[aria-label*="Search"], svg[aria-label*="Home"]').count() > 0;

        if (!isLoggedIn) {
            console.log(`[${sessionName}] ERROR: Not logged in!`);
            throw new Error(`Session ${sessionName} is not authenticated`);
        }

        console.log(`[${sessionName}] ✓ Authenticated successfully`);

        // Scrape each account
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
            
            try {
                await page.waitForSelector('a[href*="/p/"], a[href*="/reel/"]', { timeout: 15000 });
                console.log(`[${sessionName}] Post grid detected`);
            } catch (e) {
                console.log(`[${sessionName}] WARNING: Could not detect post grid`);
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
            
            stats.totalPosts += scrapedPosts.size;
            stats.totalCaptions += finalCaptionCount;
            stats.totalImages += downloadedImages;
            stats.totalDeepScraped += deepScrapedCount;
        }

        await page.close();
        
        console.log(`\n[${sessionName}] ✓ Completed: ${stats.totalPosts} posts from ${accounts.length} accounts`);
        
        return { results, stats };

    } catch (error) {
        console.error(`\n[${sessionName}] ✗ Error:`, error.message);
        try {
            await page.close();
        } catch (e) {}
        throw error;
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
    
    // Split accounts into 3 groups
    const allAccounts = config.accounts;
    const accountsPerSession = Math.ceil(allAccounts.length / 3);
    
    const session1Accounts = allAccounts.slice(0, accountsPerSession);
    const session2Accounts = allAccounts.slice(accountsPerSession, accountsPerSession * 2);
    const session3Accounts = allAccounts.slice(accountsPerSession * 2);
    
    console.log(`[CONFIG] Total accounts: ${allAccounts.length}`);
    console.log(`[CONFIG] Session 1: ${session1Accounts.length} accounts`);
    console.log(`[CONFIG] Session 2: ${session2Accounts.length} accounts`);
    console.log(`[CONFIG] Session 3: ${session3Accounts.length} accounts`);
    console.log(`[CONFIG] Scroll count: ${config.scrollCount} per account`);
    console.log(`[CONFIG] Deep scrape: ${config.deepScrapeMode ? 'enabled' : 'disabled'}`);
    console.log(`[CONFIG] Download images: ${config.downloadImages ? 'enabled' : 'disabled'}`);
    console.log("=".repeat(70));

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
        // Load sessions
        console.log("[SETUP] Loading sessions...");
        const session1Manager = new SessionManager('session1.json');
        const session2Manager = new SessionManager('session2.json');
        const session3Manager = new SessionManager('session3.json');

        // Create 3 browser contexts with sessions
        console.log("[SETUP] Creating browser contexts...");
        
        const context1 = await browser.newContext({
            viewport: { width: 1280, height: 900 },
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        });
        await context1.addCookies(session1Manager.loadSession());
        console.log("[SETUP] ✓ Context 1 created (Session 1)");

        const context2 = await browser.newContext({
            viewport: { width: 1280, height: 900 },
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        });
        await context2.addCookies(session2Manager.loadSession());
        console.log("[SETUP] ✓ Context 2 created (Session 2)");

        const context3 = await browser.newContext({
            viewport: { width: 1280, height: 900 },
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        });
        await context3.addCookies(session3Manager.loadSession());
        console.log("[SETUP] ✓ Context 3 created (Session 3)");

        console.log("\n[PARALLEL] Starting parallel scraping with staggered delays...");
        console.log("[PARALLEL] Session 1: Starting immediately");
        console.log("[PARALLEL] Session 2: Starting after 15-30 seconds");
        console.log("[PARALLEL] Session 3: Starting after 30-60 seconds");
        console.log("=".repeat(70));

        // Run all 3 sessions in parallel with staggered starts
        const [result1, result2, result3] = await Promise.all([
            scrapeWithContext(context1, session1Accounts, 'SESSION-1'),
            (async () => {
                const delay = Math.floor(Math.random() * 15000 + 15000); // 15-30 sec
                console.log(`\n[SESSION-2] Waiting ${Math.floor(delay/1000)}s before starting...`);
                await sleep(delay, delay);
                return scrapeWithContext(context2, session2Accounts, 'SESSION-2');
            })(),
            (async () => {
                const delay = Math.floor(Math.random() * 30000 + 30000); // 30-60 sec
                console.log(`\n[SESSION-3] Waiting ${Math.floor(delay/1000)}s before starting...`);
                await sleep(delay, delay);
                return scrapeWithContext(context3, session3Accounts, 'SESSION-3');
            })()
        ]);

        const endTime = Date.now();
        const totalDuration = Math.round((endTime - startTime) / 1000);

        // Merge results
        console.log("\n" + "=".repeat(70));
        console.log("[MERGE] Merging results from all sessions...");
        
        const allResults = {
            ...result1.results,
            ...result2.results,
            ...result3.results
        };

        const totalStats = {
            totalPosts: result1.stats.totalPosts + result2.stats.totalPosts + result3.stats.totalPosts,
            totalCaptions: result1.stats.totalCaptions + result2.stats.totalCaptions + result3.stats.totalCaptions,
            totalImages: result1.stats.totalImages + result2.stats.totalImages + result3.stats.totalImages,
            totalDeepScraped: result1.stats.totalDeepScraped + result2.stats.totalDeepScraped + result3.stats.totalDeepScraped
        };

        // Save merged results
        fs.writeFileSync(OUTPUT_FILE, JSON.stringify(allResults, null, 2));

        console.log("[MERGE] ✓ Results merged successfully");
        console.log("=".repeat(70));
        console.log("[COMPLETE] Multi-Session Scraping Complete!");
        console.log("=".repeat(70));
        console.log("[SUMMARY] Overall Statistics:");
        console.log(`  Sessions Used:      3`);
        console.log(`  Accounts Processed: ${allAccounts.length}`);
        console.log(`  Total Posts:        ${totalStats.totalPosts}`);
        console.log(`  Captions Extracted: ${totalStats.totalCaptions}/${totalStats.totalPosts} (${(totalStats.totalCaptions/totalStats.totalPosts*100).toFixed(1)}%)`);
        if (config.downloadImages) {
            console.log(`  Images Downloaded:  ${totalStats.totalImages}/${totalStats.totalPosts} (${(totalStats.totalImages/totalStats.totalPosts*100).toFixed(1)}%)`);
        }
        if (config.deepScrapeMode && totalStats.totalDeepScraped > 0) {
            console.log(`  Deep Scraped:       ${totalStats.totalDeepScraped} captions recovered`);
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
    process.exit(1);
});
