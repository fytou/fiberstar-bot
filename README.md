# Bot Telegram Manajemen Tiket Broadband (Fiberstar) — Tim Pekanbaru

Sesuai dokumen spesifikasi **PRD & ERD Versi 1.1** dan pembagian peran tim lapangan Fiberstar (DELTA & INEO).

---

## 👥 Struktur Peran & Hak Akses Pengguna

| Peran (Role) | Vendor | Hak Akses & Tugas |
| :--- | :--- | :--- |
| **SUPERADMIN** | `ALL` | Memiliki akses penuh terhadap seluruh fitur: kelola whitelist (`/adduser`, `/setvendor`, `/toggleuser`), pantau seluruh antrian, rekap, dan pengaturan sistem. |
| **ADMIN** | `ALL` | **Khusus Petugas Input Tiket**: Mengirim/paste teks tiket format `[TSHOOT]` Fiberstar dari Medan ke dalam sistem Pekanbaru. |
| **SUPERVISOR** | `ALL` | **Pengawas & Pemantau**: Memantau tiket masuk, mengecek garansi vendor, melihat progress pengerjaan teknisi (Open, Progress, Pending, Done), memantau SLA, dan membuat rekap laporan WhatsApp. |
| **TEKNISI DELTA** | `DELTA` | Hanya melihat dan menangani tiket garansi **DELTA**. Memiliki tombol khusus **`Oper ke INEO (ODP Lost)`** jika mendapati kendala ODP Lost. |
| **TEKNISI INEO** | `INEO` | Menangani tiket garansi **INEO** serta menerima seluruh tiket limpahan/operan **ODP Lost** dari vendor DELTA. |

---

## ⚡ Alur Khusus: Operan ODP Lost (DELTA ➡️ INEO)

Sesuai aturan operasional: **Kendala ODP Lost hanya ditangani oleh vendor INEO**.
1. Saat teknisi **DELTA** memeriksa tiket di lapangan dan menemukan bahwa ODP Lost:
   - Teknisi menekan tombol **`🔄 Oper ke INEO (ODP Lost)`** pada tiket (atau mengetik catatan "ODP Lost").
2. Bot secara otomatis:
   - Mengalihkan kepemilikan vendor tiket dari **DELTA** ke **INEO**.
   - Menyimpan jejak audit (`transferred_from = 'DELTA'`, `transfer_reason = 'ODP Lost'`).
   - Tiket otomatis **keluar dari antrian DELTA** dan langsung **masuk ke antrian teknisi INEO** dengan label badge khusus `🚨 [OPERAN DELTA: ODP LOST]`.
   - Mengirim notifikasi pengalihan tiket ke grup tim jika grup telah didaftarkan.

---

## 🛠️ Perintah Tambah Pengguna (Whitelist) oleh Superadmin

Format perintah `/adduser`:
```text
/adduser <telegram_id> <role> <vendor> <nama>
```

**Pilihan Role:** `SUPERADMIN`, `ADMIN`, `SUPERVISOR`, `TEKNISI`  
**Pilihan Vendor:** `DELTA`, `INEO`, `ALL`

Contoh penggunaan:
- **Tambah Teknisi DELTA**:
  `/adduser 123456789 TEKNISI DELTA Budi Santoso`
- **Tambah Teknisi INEO**:
  `/adduser 987654321 TEKNISI INEO Ahmad Fauzi`
- **Tambah Admin (Input Tiket)**:
  `/adduser 112233445 ADMIN ALL Rian Medan`
- **Tambah Supervisor**:
  `/adduser 556677889 SUPERVISOR ALL Pak Hendra SPV`

Perintah lainnya:
- `/whitelist` — Menampilkan seluruh daftar user beserta role & vendornya.
- `/setvendor <id> <DELTA/INEO>` — Mengubah vendor teknisi.
- `/toggleuser <id>` — Mengaktifkan / menonaktifkan akun.

---

## 🚀 Cara Update di VPS Tencent Cloud

Di terminal VPS Tencent Cloud Anda, cukup jalankan:
```bash
cd ~/fiberstar-bot && git pull && sudo systemctl restart fiberstar-bot
```
