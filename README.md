# Infortic Scraper

Proyek Python ini bertanggung jawab untuk melakukan scraping data event IT (kompetisi, pelatihan, sertifikasi) dari berbagai sumber di internet.

Data yang telah di-scrape akan dibersihkan dan dimasukkan ke dalam database Supabase untuk ditampilkan di platform Infortic.

## Setup

1.  Buat dan aktifkan virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    .\venv\Scripts\activate  # Windows
    ```

2.  Install dependensi:
    ```bash
    pip install -r requirements.txt
    ```

3.  Jalankan scraper:
    ```bash
    python scraper.py
    ```
