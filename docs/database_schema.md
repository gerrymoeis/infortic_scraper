# Database Schema

This document outlines the schema for the `infortic-scraper` database, managed in Supabase.

## Table: `events`

This is the primary table for storing all scraped event data.

| Column             | Type                      | Constraints                               | Description                                                                                               |
| ------------------ | ------------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `id`               | `uuid`                    | `PRIMARY KEY`, `default: uuid_generate_v4()` | Unique identifier for each event.                                                                         |
| `created_at`       | `timestamp with time zone`| `NOT NULL`, `default: now()`              | Timestamp of when the event record was created.                                                           |
| `title`            | `text`                    | `NOT NULL`                                | The title of the event.                                                                                   |
| `description`      | `text`                    |                                           | A detailed description of the event.                                                                      |
| `deadline`         | `timestamp with time zone`| **`NOT NULL`**                            | The registration or submission deadline for the event. **This field cannot be NULL.**                     |
| `poster_url`       | `text`                    | **`NOT NULL`**                            | A URL to the event's poster image. **This field cannot be NULL.**                                         |
| `registration_url` | `text`                    | **`NOT NULL`**, `UNIQUE`                  | The URL for event registration. Must be unique to prevent duplicate entries. **This field cannot be NULL.** |
| `source_id`        | `uuid`                    | `FOREIGN KEY` to `sources.id`             | The ID of the source where the event was scraped from.                                                    |
| `event_type_id`    | `uuid`                    | `FOREIGN KEY` to `event_types.id`         | The ID for the high-level type of the event (e.g., Lomba, Pelatihan).                                     |
| `is_online`        | `boolean`                 |                                           | Indicates if the event is held online.                                                                    |
| `is_free`          | `boolean`                 |                                           | Indicates if the event is free to attend/participate.                                                     |
| `raw_text`         | `text`                    |                                           | The raw, unprocessed text content from the original scrape, used for debugging and reprocessing.          |

### Key Constraints & Data Integrity

To ensure high-quality data, the following fields have been made mandatory (`NOT NULL`):

-   **`deadline`**: Every event must have a deadline. The scrapers and data cleaning pipeline are designed to parse or reject events without a valid deadline.
-   **`poster_url`**: A visual poster is critical for user engagement. All events must have a valid poster URL.
-   **`registration_url`**: The primary call-to-action for any event. This field is also used as a `UNIQUE` key to prevent duplicate event entries.

## Other Tables

-   **`sources`**: Stores information about the data sources (e.g., `infolomba.id`, `instagram`).
-   **`event_types`**: Stores high-level event classifications (`Lomba`, `Pelatihan`, `Sertifikasi`, `Magang`, `Beasiswa`).
-   **`categories`**: Stores thematic tags for events (`ui-ux-competition`, `web-development`, etc.).
-   **`event_categories`**: A junction table managing the many-to-many relationship between `events` and `categories`.

## Row Level Security (RLS)

All tables have Row Level Security (RLS) enabled to protect data. Data insertion and updates are handled exclusively through secure RPC (Remote Procedure Call) functions, such as `upsert_event_with_categories`.
