# GitHub Secrets Setup Guide

## Required Action: Add GEMINI_API_KEYS Secret

The workflow now uses `GEMINI_API_KEYS` (plural) to support intelligent API key rotation across all scrapers.

### Steps to Add the Secret:

1. Go to your GitHub repository: https://github.com/gerrymoeis/infortic_scraper
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secret:

**Name:** `GEMINI_API_KEYS`

**Value:** (comma-separated, no spaces)
```
AIzaSyA-KzZKzm6wZJCklIfZOOLfMaN9uA-gOmk,AIzaSyBUTzSufdqqiwolXq17BmQsv2NxUCwwcYM,AIzaSyDXmYfhIW6UWQpcMbaTOEspXzPUDadeGmk
```

### How It Works:

- **Before:** Each scraper was assigned ONE key at workflow start. When that key hit quota, it gave up.
- **After:** All scrapers use ALL keys. When one key hits quota, the system automatically rotates through ALL available keys before giving up.

### Adding More Keys Later:

When you get more API keys, simply:
1. Edit the `GEMINI_API_KEYS` secret
2. Add new keys to the comma-separated list
3. No code changes needed - the system will automatically use all keys

### Example with 5 Keys:
```
key1,key2,key3,key4,key5
```

### Local Development:

Your local `.env` file already has the correct format:
```env
GEMINI_API_KEYS=key1,key2,key3
```

The system supports both:
- `GEMINI_API_KEYS` (preferred, comma-separated)
- `GEMINI_API_KEY` (fallback, single key for backward compatibility)

### Verification:

After adding the secret, the next workflow run will:
1. Try key #1 → if quota exceeded
2. Try key #2 → if quota exceeded
3. Try key #3 → if quota exceeded
4. Only then give up with clear error message

Check the logs for:
```
Rotating to API key #2
Retrying with API key #2 (tried 2/3 keys)
```

This confirms the rotation is working correctly.
