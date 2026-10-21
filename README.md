# Bot Telegram Manajemen Tiket Broadband (Fiberstar) — Tim Pekanbaru

Sesuai dokumen spesifikasi **PRD & ERD Versi 1.1 (21 Oktober 2026)**.

Bot ini dirancang khusus untuk tim teknisi broadband Pekanbaru untuk menerima tiket gangguan CRT dari Fiberstar (FS), menyimpannya sebagai data terstruktur, melacak status sampai selesai, memantau SLA 1×24 jam, dan menghasilkan rekap harian format WhatsApp.

---

## 🚀 Fitur yang Telah Diimplementasikan (Sesuai PRD)

| Kode PRD | Fitur | Deskripsi |
| :--- | :--- | :--- |
| **FR-01** | Ingesti Tiket | Menerima dan mem-parsing teks format `[TSHOOT]` (single atau multi-tiket dipisah `====` atau `[TSHOOT]`). |
| **FR-02** | Konfirmasi | Menampilkan preview ringkasan data tiket sebelum disimpan dengan tombol **Simpan** dan **Batal**. |
| **FR-03** | Deteksi Duplikat | Nomor tiket (`ticket_no`) yang sudah ada ditolak otomatis. Jika nomor CRT masih punya tiket aktif, bot menampilkan banner peringatan. |
| **FR-04** | Tiket Sudah Selesai | Jika terdapat catatan teknisi sebelum `[TSHOOT]` (mis. `Back To. Normal`), tiket langsung disimpan dengan status `CLOSED` dan catatan tersebut. |
| **FR-05** | Ubah Status & Tombol Cepat | Tombol status inline yang dinamis dan idempotent. Tombol catatan cepat (`Back To Normal`, `Cancel Reschedule`, `Pelanggan Belum Ready`, `Ketik Manual`). Transisi di luar aturan PRD ditolak bot. |
| **FR-06** | Hitung SLA | Otomatis menghitung `sla_deadline = fu_at + 24 jam`. Saat tiket `CLOSED`, mencatat hasil `IN_SLA` atau `OUT_SLA`. |
| **FR-07** | Antrian `/open` | Menampilkan antrian tiket aktif diurutkan dari sisa SLA terkecil dengan badge: 🔴 Lewat SLA, 🟡 Kurang dari 1 jam, 🟢 Aman. |
| **FR-08** | Rekap `/rekap` | Menghasilkan teks laporan rekap harian siap salin ke WhatsApp (opsi hari ini, kemarin, atau tanggal kustom). Format persis standar Fiberstar. |
| **FR-09** | Generator Balasan FS | Saat tiket ditutup, bot menghasilkan format teks siap salin (catatan di atas + teks tiket asli) untuk ditempel ke grup WhatsApp FS. |
| **FR-10** | Pengingat SLA Otomatis | Background scheduler otomatis mengirim notifikasi peringatan **60 menit** dan **15 menit** sebelum batas waktu SLA terlewati. |
| **FR-11** | Riwayat & `/detail` | Menampilkan detail lengkap pelanggan, node jaringan (OLT/PON), sisa SLA, serta timeline jejak audit perubahan status tiket. |
| **FR-12** | Whitelist & Otorisasi | Middleware otorisasi pengguna (`TEKNISI`, `SUPERVISOR`, `ADMIN`). User non-whitelist akan ditolak secara otomatis. |
| **FR-13** | Penentuan Tim | Tiket yang masuk secara default dialokasikan ke tim Pekanbaru. |

---

## 📁 Struktur Direktori

```text
fiberstar-bot/
├── config.py             # Konfigurasi aplikasi & environment variables
├── database/
│   ├── db.py             # Koneksi aiosqlite & inisialisasi tabel sesuai ERD
│   ├── queries.py        # Kumpulan query SQL asinkron
│   └── __init__.py
├── parser/
│   ├── ticket_parser.py  # Regex parser tangguh untuk format tiket [TSHOOT] Fiberstar
│   └── __init__.py
├── services/
│   ├── sla_service.py    # Perhitungan SLA 1x24 jam & status urgency
│   ├── report_service.py # Generator rekap harian WhatsApp sesuai Bagian 8 PRD
│   ├── reply_service.py  # Generator teks balasan siap salin (FR-09)
│   └── __init__.py
├── handlers/
│   ├── common.py         # /start, /help, /me, /cancel
│   ├── ingest.py         # Ingest pesan tiket [TSHOOT] & tombol konfirmasi
│   ├── status_flow.py    # Alur status, tombol cepat catatan, dan teks balasan
│   ├── tickets.py        # /open, /cari, /detail_<id>
│   ├── report.py         # /rekap (Hari ini, Kemarin, Pilih Tanggal)
│   ├── admin.py          # /whitelist, /adduser, /toggleuser, /setchat
│   └── __init__.py
├── middlewares/
│   ├── auth.py           # Whitelist Authorization Middleware
│   └── __init__.py
├── scheduler/
│   ├── reminders.py      # APScheduler untuk reminder SLA 60m & 15m
│   └── __init__.py
├── tests/
│   └── test_suite.py     # Unit test lengkap (100% Passed)
├── .env                  # Konfigurasi aktif (BOT_TOKEN, ADMIN_IDS, dll.)
├── .env.example          # Contoh template konfigurasi
├── requirements.txt      # Dependensi Python
└── main.py               # Entrypoint utama bot
```

---

## 🛠️ Cara Menjalankan Bot

### 1. Masuk ke Direktori Proyek
```bash
cd "C:\Users\ixuma\.gemini\antigravity\scratch\fiberstar-bot"
```

### 2. Isi Token Bot di File `.env`
Buka file `.env` dan masukkan:
- `BOT_TOKEN`: Token bot Telegram yang didapatkan dari `@BotFather`.
- `ADMIN_IDS`: ID Telegram Anda (dapat dilihat dengan mengirim pesan ke `@userinfobot` di Telegram).

Contoh isi `.env`:
```env
BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
ADMIN_IDS=987654321
DEFAULT_TEAM_NAME=Pekanbaru
TIMEZONE=Asia/Jakarta
DB_PATH=fiberstar.db
SLA_HOURS=24
```

### 3. Jalankan Pengujian (Testing)
Pastikan semua fungsionalitas berjalan normal:
```bash
.\.venv\Scripts\python.exe -m unittest tests.test_suite
```
Hasil: `Ran 7 tests in 0.400s - OK`.

### 4. Jalankan Bot
```bash
.\.venv\Scripts\python.exe main.py
```

---

## 💬 Contoh Penggunaan di Telegram

### A. Input Tiket FS
Kirim pesan seperti berikut ke bot:
```text
[TSHOOT]
Northern Sumatera
T0000001-201026-01
Dear Team Pekanbaru, mohon bantuan pengecekan
Nama : PT Mitra Fiber - Bapak Rahmad
Alamat : Jl. Sudirman No. 45, Pekanbaru, Riau
CRT : CRT10000234
OLT : PKU-OLT-01
PON : 1/1/4:12
Telp : 081234567890
Los Merah
20/10/2026 10:14 FU to FOP
Garansi Aktivasi DELTA
```
Bot akan membalas dengan ringkasan terstruktur dan tombol `[✅ Simpan Tiket]`.

### B. Cek Antrian Tiket Aktif
Ketik `/open` untuk melihat antrian berdasarkan sisa SLA. Klik salah satu tiket untuk membuka menu aksi ubah status.

### C. Membuat Rekap WhatsApp
Ketik `/rekap` lalu pilih `[📅 Rekap Hari Ini]`. Bot akan menghasilkan output format teks siap salin:
```text
List open tiket broadband 20/10/26
1. T0000001-201026-01 Bapak Rahmad CRT10000234 20/10/2026 10:14 Garansi delta (CLOSE IN SLA 14:06) ✅
2. T0000002-201026-01 Ibu Siti Aminah CRT10000555 20/10/2026 12:54

📊 Ringkasan Tiket:
• Total: 2
• Closed: 1
• Masih Aktif (Open/Progress): 1
• MS Lost: 0
• Pending: 0
• Cancelled: 0
```
