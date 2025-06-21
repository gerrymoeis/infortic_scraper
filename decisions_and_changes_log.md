# Development and Decisions Log

This document records key architectural decisions, principles, and learnings from the development of the infortic-scraper project. Its purpose is to ensure consistency and promote effective, efficient development practices.

## 2025-06-21: Fixing Google Sheets Scraper Date Parsing

### 1. Principle: Root Cause Analysis over Symptom Fixing

**Observation:** Initial attempts to fix individual scrapers (e.g., `RkimScraper`) failed to resolve the core issue of valid events being discarded. The problem appeared to be widespread across all Google Sheets scrapers.

**Decision & Principle:** Instead of patching individual scrapers, we conducted a deeper investigation that led to the root cause: a critical bug in the `core.data_cleaner.parse_dates` function. The principle is to **always prioritize identifying and fixing the root cause of a bug rather than addressing its symptoms.** This prevents recurring issues and leads to a more stable system.

### 2. Method: Robust and Resilient Data Parsing

**Observation:** The original `parse_dates` function was complex, fragile, and used convoluted logic to infer dates, leading to incorrect parsing of valid future deadlines.

**Decision & Principle:** The function was completely rewritten to be simpler and more robust.
- **Leverage Specialized Libraries:** Use `dateparser` to handle the complexity of finding and parsing dates from natural language text.
- **Simplify Logic:** The new logic is straightforward: find all dates in the text and use the latest one as the deadline. This is more predictable and less prone to errors.
- **Handle Edge Cases:** The new function explicitly handles empty inputs and translates Indonesian month abbreviations to ensure consistency.
- **Principle:** **Write data parsers that are simple, rely on robust libraries, and are resilient to varied or malformed input.**

### 3. Method: Systematic and Incremental Verification

**Observation:** After fixing the core date parsing bug, it was crucial to ensure that all dependent components (the scrapers) now functioned as expected.

**Decision & Principle:** We adopted a systematic, one-by-one verification process for each of the five Google Sheets scrapers. This involved reviewing the code of each scraper (`Sahakara`, `RKIM`, `Himakom`, `RndInfoCenter`, `HmitItsPortal`) to confirm its logic was sound in light of the fix.
- **Principle:** **When a core dependency is changed, methodically test and verify all dependent components to ensure system integrity. Do not assume the fix will work everywhere without verification.**

### 4. Concept: Configuration-Driven and Modular Design

**Observation:** The scrapers, particularly `HmitItsPortalScraper`, demonstrate a powerful design pattern where the specific logic for handling different table structures is defined in configuration objects, not hardcoded.

**Principle:** **Favor a configuration-driven design.** By defining keywords, column mappings, and event types in dictionaries (`table_configs`), the core scraping logic in `BaseGoogleSheetScraper` remains generic and reusable. This makes the system:
- **Modular:** Easy to add new scrapers or support new table layouts without changing the core processing logic.
- **Maintainable:** Changes to a sheet's format only require updating a configuration object, not rewriting code.
- **Readable:** The intent of the scraper is clearly defined in its configuration.

### 5. Concept: Defensive Programming in Scrapers

**Observation:** The scrapers include several checks to ensure data quality and prevent errors.

**Principle:** **Apply defensive programming principles when scraping.**
- **Explicit Status Checks:** Filter events based on a specific status (e.g., `status == 'open'` or `status == 'Buka'`). This prevents processing of irrelevant events.
- **Data Integrity Checks:** Ensure essential data like a `registration_url` exists before processing an event.
- **Graceful Error Handling:** Use `try-except` blocks to handle potential `IndexError` or `AttributeError` when parsing rows, preventing the entire scraper from crashing due to a single malformed row.
