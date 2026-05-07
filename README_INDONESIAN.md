<div align="center">
  <img src="Nexus_Logo.png" alt="Nexus Logo" width="300">
</div>

<h1 align="center">Nexus - Anomaly Detector for Asentinel</h1>

<div align="center">
  <a href="README.md">English</a> | <strong>Indonesia</strong>
</div>

Mendeteksi anomali pada data pemantauan kesehatan API menggunakan **Isolation Forest**.

## Cara Kerjanya

1. Data pemantauan mentah masuk (dari CSV atau database)
2. Fitur direkayasa dari data mentah (`feature_engineer.py`)
3. Model Isolation Forest menilai setiap catatan (record)
4. Jika skor di bawah threshold, endpoint mendapat **strike** — belum ditandai sebagai anomali
5. Setelah **3 strike berturut-turut**, endpoint dikonfirmasi sebagai anomali dan dicatat
6. Untuk pulih, endpoint harus melewati **3 pemeriksaan normal berturut-turut**
7. Saat retraining, `summarizer.py` mengelompokkan log anomali menjadi ringkasan lalu membersihkan log
8. Endpoint `/recommend` meneruskan ringkasan ke LLM (`engine.py`) untuk menghasilkan rencana perbaikan teknis

> Strike mencegah alarm palsu akibat lonjakan sementara. Dapat dikonfigurasi melalui `CONFIRM_STRIKES` dan `RECOVER_STRIKES` di `config.py`.

## Struktur Proyek

| File | Fungsi |
|------|--------|
| `config.py` | Semua pengaturan (path, DB, parameter model, jadwal, LLM) |
| `detector.py` | Mesin deteksi utama |
| `feature_engineer.py` | Membangun fitur dari data pemantauan mentah |
| `nexus.py` | Server FastAPI — endpoint deteksi dan rekomendasi |
| `batch_detector.py` | Deteksi batch dari CSV (dev) atau polling DB (prod) |
| `retrain_scheduler.py` | Melatih ulang model dan memicu summarizer |
| `summarizer.py` | Mengelompokkan log anomali menjadi ringkasan JSON |
| `engine.py` | Mengirim ringkasan ke LLM dan mengembalikan rencana perbaikan |
| `run.py` | Menu CLI interaktif untuk menjalankan bagian mana pun dari sistem |

## Persiapan Setup

1. Salin `.env.example` ke `.env` dan isi kredensial DB serta LLM API key Anda.
2. Instal dependencies:
```bash
pip install -r requirements.txt
```

## Penggunaan

Nexus dapat digunakan dengan dua cara:

### Otomatis (via CLI)

Cara yang direkomendasikan untuk penggunaan internal/operasional. Jalankan menu interaktif:

```bash
python run.py
```

Dari menu ini Anda dapat menjalankan deteksi batch (CSV atau DB), deteksi tunggal, retrain model, dan mengelola log — semua dari satu tempat.

### API Endpoint (untuk payload tunggal)

Untuk sistem eksternal (misalnya backend Asentinel) yang ingin mengirim satu record dan mendapatkan hasil deteksi anomali secara langsung. Jalankan server API:

```bash
uvicorn nexus:app --reload --env-file .env
```

Kemudian kirim request `POST` ke `/detect` dengan satu record pemantauan. Lihat `NEXUS API DOCUMENTATION.md` untuk referensi endpoint lengkap.

## Database

Saat DB Anda sudah di-host:

1. Atur `DB_ENABLED = True` di `config.py`
2. Isi kredensial DB di `.env`
3. Tabel `log_monitor` harus memiliki kolom berikut:
   `id_log_monitor`, `id_aplikasi`, `id_service`, `url`, `status`, `http_status_code`, `response_time_ms`, `checked_at`, `created_at`, `updated_at`
