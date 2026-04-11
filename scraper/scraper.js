const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');
const config = require('../config/scraper.config.json');

chromium.use(stealth());

const SESSION_FILE = 'session.json';
const OUTPUT_FILE = path.join(__dirname, 'instagram_data.json');  // Absolute path in scraper folder
const IMAGES_FOLDER = path.join(__dirname, '..', 'data', 'images');  // Absolute path to data/images

const sleep = (min, max) => new Promise(resolve => setTimeout(resolve, Math.floor(Math.random() * (max - min + 1) + min)));

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
                // Silent fail on final attempt - will be tracked in summary
                return null;
            }
            await sleep(1000 * attempt, 2000 * attempt);
        }
    }
    return null;
}

async function main() {
    console.log("\n" + "=".repeat(60));
    console.log("[SCRAPER] Instagram Scraper Starting...");
    console.log("=".repeat(60));
    console.log(`[CONFIG] Target accounts: ${config.accounts.length} (${config.accounts.map(a => '@' + a).join(', ')})`);
    console.log(`[CONFIG] Scroll count: ${config.scrollCount} per account`);
    console.log(`[CONFIG] Deep scrape mode: ${config.deepScrapeMode ? 'enabled' : 'disabled'}`);
    console.log(`[CONFIG] Download images: ${config.downloadImages ? 'enabled' : 'disabled'}`);
    console.log("=".repeat(60) + "\n");
    
    if (config.downloadImages && !fs.existsSync(IMAGES_FOLDER)) {
        fs.mkdirSync(IMAGES_FOLDER, { recursive: true });
        console.log(`[SETUP] Created images folder: ${IMAGES_FOLDER}`);
    }
    
    const browser = await chromium.launch({ 
        headless: true,  // Changed to true for GitHub Actions compatibility
        args: [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',  // Required for GitHub Actions
            '--disable-setuid-sandbox',  // Required for GitHub Actions
            '--disable-dev-shm-usage'  // Prevents crashes in containerized environments
        ]
    });
    
    const context = await browser.newContext({
        viewport: { width: 1280, height: 900 },
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    });

    if (fs.existsSync(SESSION_FILE)) {
        console.log("[SESSION] Loading saved session...");
        await context.addCookies(JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8')));
    }

    const page = await context.newPage();
    console.log("[BROWSER] Navigating to Instagram...");
    await page.goto('https://www.instagram.com/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(3000, 4000);

    const isLoggedIn = await page.locator('svg[aria-label*="Search"], svg[aria-label*="Home"]').count() > 0;

    if (!isLoggedIn) {
        console.log("[AUTH] ERROR: Not logged in!");
        console.log("[AUTH] Please ensure INSTAGRAM_SESSION secret is set correctly in GitHub");
        console.log("[AUTH] Run scraper locally once to generate session.json, then copy to GitHub Secret");
        await browser.close();
        process.exit(1);  // Exit with error code
    } else {
        console.log("[AUTH] Already logged in");
    }

    let allResults = {};
    let totalStats = {
        totalPosts: 0,
        totalCaptions: 0,
        totalImages: 0,
        totalDeepScraped: 0
    };

    for (let accountIndex = 0; accountIndex < config.accounts.length; accountIndex++) {
        const username = config.accounts[accountIndex];
        console.log(`\n${"=".repeat(60)}`);
        console.log(`[ACCOUNT] Processing @${username} (${accountIndex + 1}/${config.accounts.length})`);
        console.log("=".repeat(60));
        
        await page.goto(`https://www.instagram.com/${username}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await sleep(2000, 3000);
        
        try {
            await page.waitForSelector('a[href*="/p/"], a[href*="/reel/"]', { timeout: 15000 });
            console.log("[GRID] Post grid detected successfully");
        } catch (e) {
            console.log("[WARNING] Could not detect post grid - account may be private or empty");
        }

        let scrapedPosts = new Map();
        let downloadedImages = 0;
        let deepScrapedCount = 0;

        console.log(`[SCROLL] Starting scroll sequence (${config.scrollCount} scrolls)...`);
        
        for (let i = 0; i < config.scrollCount; i++) {
            console.log(`  [SCROLL ${i + 1}/${config.scrollCount}] Loading posts...`);
            
            await sleep(2000, 3000);
            
            try {
                await page.waitForSelector('div.x1s85apg h2 span', { timeout: 5000 });
            } catch (e) {
                // Caption elements may load slower, continue anyway
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
            console.log(`    [PROGRESS] Posts: ${scrapedPosts.size} total (${newPosts} new) | Captions: ${postsWithCaptions}/${scrapedPosts.size} (${(postsWithCaptions/scrapedPosts.size*100).toFixed(1)}%)`);
            
            if (config.downloadImages && newPosts > 0) {
                console.log(`    [IMAGES] Downloaded: ${downloadedImages}/${scrapedPosts.size} images`);
            }
            
            if (config.deepScrapeMode && postsNeedingDeepScrape.length > 0) {
                console.log(`    [DEEP] Deep scraping ${postsNeedingDeepScrape.length} posts with missing captions...`);
                
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
                                    if (text) return { caption: text, found: true, strategy: "h1 with full classes" };
                                }
                                
                                const h1WithClass = modal.querySelector('h1._ap3a');
                                if (h1WithClass) {
                                    const text = (h1WithClass.innerText || h1WithClass.textContent || "").trim();
                                    if (text) return { caption: text, found: true, strategy: "h1._ap3a" };
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
                        // Silent fail, continue with next post
                        try {
                            await page.keyboard.press('Escape');
                            await sleep(400, 600);
                        } catch (e) {}
                    }
                }
                
                deepScrapedCount += deepScrapedSuccess;
                console.log(`    [DEEP] Recovered: ${deepScrapedSuccess}/${postsNeedingDeepScrape.length} captions`);
            }

            if (i < config.scrollCount - 1) {
                const scrollDistance = Math.floor(Math.random() * 400 + 800);
                await page.evaluate((distance) => window.scrollBy(0, distance), scrollDistance);
                await sleep(2500, 3500);
            }
        }
        
        const finalCaptionCount = Array.from(scrapedPosts.values()).filter(p => p.caption && p.caption.trim()).length;
        const emptyCaptions = scrapedPosts.size - finalCaptionCount;
        
        console.log(`\n[ACCOUNT SUMMARY] @${username}:`);
        console.log(`  Total Posts:        ${scrapedPosts.size}`);
        console.log(`  Captions Extracted: ${finalCaptionCount}/${scrapedPosts.size} (${(finalCaptionCount/scrapedPosts.size*100).toFixed(1)}%)`);
        console.log(`  Empty Captions:     ${emptyCaptions}/${scrapedPosts.size} (${(emptyCaptions/scrapedPosts.size*100).toFixed(1)}%)`);
        if (config.downloadImages) {
            console.log(`  Images Downloaded:  ${downloadedImages}/${scrapedPosts.size} (${(downloadedImages/scrapedPosts.size*100).toFixed(1)}%)`);
        }
        if (config.deepScrapeMode && deepScrapedCount > 0) {
            console.log(`  Deep Scraped:       ${deepScrapedCount} captions recovered`);
        }

        allResults[username] = Array.from(scrapedPosts.values());
        
        totalStats.totalPosts += scrapedPosts.size;
        totalStats.totalCaptions += finalCaptionCount;
        totalStats.totalImages += downloadedImages;
        totalStats.totalDeepScraped += deepScrapedCount;
    }

    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(allResults, null, 2));
    await browser.close();
    
    console.log(`\n${"=".repeat(60)}`);
    console.log("[COMPLETE] Scraping Complete!");
    console.log("=".repeat(60));
    console.log("[SUMMARY] Overall Statistics:");
    console.log(`  Accounts Processed: ${config.accounts.length}`);
    console.log(`  Total Posts:        ${totalStats.totalPosts}`);
    console.log(`  Captions Extracted: ${totalStats.totalCaptions}/${totalStats.totalPosts} (${(totalStats.totalCaptions/totalStats.totalPosts*100).toFixed(1)}%)`);
    if (config.downloadImages) {
        console.log(`  Images Downloaded:  ${totalStats.totalImages}/${totalStats.totalPosts} (${(totalStats.totalImages/totalStats.totalPosts*100).toFixed(1)}%)`);
    }
    if (config.deepScrapeMode && totalStats.totalDeepScraped > 0) {
        console.log(`  Deep Scraped:       ${totalStats.totalDeepScraped} captions recovered`);
    }
    console.log(`  Output File:        ${OUTPUT_FILE}`);
    console.log("=".repeat(60) + "\n");
}

main().catch(console.error);
