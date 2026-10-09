import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('kunjungan.db')
    c = conn.cursor()
    # Membuat tabel utama untuk menampung rencana dan laporan kunjungan
    c.execute('''
        CREATE TABLE IF NOT EXISTS rencana_kunjungan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sales_name TEXT,
            tanggal TEXT,
            kota TEXT,
            nama_customer TEXT,
            alasan_kunjungan TEXT,
            status TEXT DEFAULT 'Plan',
            laporan_hasil TEXT DEFAULT '',
            follow_up TEXT DEFAULT ''
        )
    ''')
    
    # Isi data contoh dummy jika tabel masih benar-benar kosong
    c.execute("SELECT COUNT(*) FROM rencana_kunjungan")
    if c.fetchone()[0] == 0:
        sample_data = [
            ('Budi Santoso', '2026-10-15', 'Semarang', 'PT Maju Jaya', 'Negosiasi perpanjangan kontrak tahunan dan demonstrasi produk baru.'),
            ('Budi Santoso', '2026-10-15', 'Semarang', 'Toko Elektronik Berkah', 'Sudah 3 bulan tidak melakukan repeat order, cek kendala di toko.'),
            ('Siti Aminah', '2026-10-16', 'Surabaya', 'CV Sumber Makmur', 'Penagihan invoice yang sudah jatuh tempo lebih dari 2 minggu.'),
            ('Siti Aminah', '2026-10-16', 'Surabaya', 'PT Global Niaga', 'Menyelesaikan klaim retur barang cacat produksi bulan lalu.')
        ]
        c.executemany('''
            INSERT INTO rencana_kunjungan (sales_name, tanggal, kota, nama_customer, alasan_kunjungan)
            VALUES (?, ?, ?, ?, ?)
        ''', sample_data)
        conn.commit()
    conn.close()

# Inisialisasi Database saat program berjalan pertama kali
init_db()

def get_connection():
    return sqlite3.connect('kunjungan.db')

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="Sales Visit & Report System", layout="wide")

st.title("🧳 Sistem Kunjungan Luar Kota Sales & Supervisor")
st.markdown("Manajemen jadwal keberangkatan, tracking alasan kunjungan, serta pengisian laporan daily report saat pulang kantor.")

# Sidebar Pengguna & Tambah Data
st.sidebar.header("👤 Profil Pengguna")
daftar_sales = ["Budi Santoso", "Siti Aminah"]
sales_aktif = st.sidebar.selectbox("Pilih Nama Anda:", daftar_sales)

st.sidebar.markdown("---")
st.sidebar.header("➕ Tambah Jadwal Baru")
with st.sidebar.form("form_tambah_jadwal"):
    new_date = st.date_input("Tanggal Kunjungan:", datetime.now())
    new_kota = st.text_input("Kota Tujuan:", placeholder="Contoh: Bandung")
    new_cust = st.text_input("Nama Customer:", placeholder="Contoh: PT Surya Abadi")
    new_alasan = st.text_area("Alasan Kunjungan:", placeholder="Contoh: Penawaran produk baru...")
    
    submit_jadwal = st.form_submit_button("Tambah ke Rencana")
    if submit_jadwal:
        if not new_kota.strip() or not new_cust.strip() or not new_alasan.strip():
            st.error("Semua kolom input jadwal wajib diisi!")
        else:
            conn = get_connection()
            c = conn.cursor()
            c.execute('''
                INSERT INTO rencana_kunjungan (sales_name, tanggal, kota, nama_customer, alasan_kunjungan)
                VALUES (?, ?, ?, ?, ?)
            ''', (sales_aktif, new_date.strftime('%Y-%m-%d'), new_kota, new_cust, new_alasan))
            conn.commit()
            conn.close()
            st.success("Jadwal baru berhasil ditambahkan!")
            st.rerun()

# Pembuatan Tab Menu Utama
tab1, tab2, tab3 = st.tabs(["🗓️ Rencana Kunjungan", "📝 Input Report (Pulang Kantor)", "📊 Export Laporan & Histori"])

# --- TAB 1: LIHAT RENCANA KUNJUNGAN ---
with tab1:
    st.header("Cek Jadwal Kunjungan Luar Kota")
    st.info("Pilih tanggal keberangkatan Anda untuk memunculkan daftar target customer beserta alasan kunjungan.")
    
    tanggal_cari = st.date_input("Pilih Tanggal Rencana Perjalanan:", datetime.now(), key="cari_tgl")
    str_tanggal = tanggal_cari.strftime('%Y-%m-%d')
    
    conn = get_connection()
    query = """
        SELECT kota as [Kota Tujuan], nama_customer as [Nama Customer], 
               alasan_kunjungan as [Alasan Kunjungan], status as [Status Laporan]
        FROM rencana_kunjungan 
        WHERE sales_name = ? AND tanggal = ?
    """
    df = pd.read_sql_query(query, conn, params=(sales_aktif, str_tanggal))
    conn.close()
    
    if not df.empty:
        st.subheader(f"📋 Jadwal untuk {sales_aktif} pada {str_tanggal}")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning(f"Tidak ada jadwal kunjungan luar kota terdaftar untuk {sales_aktif} pada tanggal {str_tanggal}.")

# --- TAB 2: INPUT LAPORAN & FOLLOW-UP (PULANG KANTOR) ---
with tab2:
    st.header("Laporan Hasil Kunjungan Akhir Hari")
    st.markdown("Isi form di bawah ini ketika Anda telah kembali atau sebelum jam pulang kantor selesai.")
    
    conn = get_connection()
    query_laporan = """
        SELECT id, nama_customer, tanggal, alasan_kunjungan 
        FROM rencana_kunjungan 
        WHERE sales_name = ? AND status = 'Plan'
    """
    df_lap = pd.read_sql_query(query_laporan, conn, params=(sales_aktif,))
    conn.close()
    
    if not df_lap.empty:
        pilihan_customer = {f"{row['nama_customer']} (Rencana: {row['tanggal']})": row['id'] for _, row in df_lap.iterrows()}
        selected_cust_label = st.selectbox("Pilih Customer yang Baru Selesai Dikunjungi:", list(pilihan_customer.keys()))
        
        selected_id = pilihan_customer[selected_cust_label]
        detail_cust = df_lap[df_lap['id'] == selected_id].iloc[0]
        
        st.info(f"📌 **Tujuan Awal Kunjungan:** {detail_cust['alasan_kunjungan']}")
        
        with st.form("form_report"):
            laporan_hasil = st.text_area("📝 Tulis Laporan Hasil Kunjungan (Report):", 
                                         placeholder="Contoh: Pemilik toko sepakat meningkatkan volume pembelian 15%...")
            follow_up = st.text_area("🚀 Tindakan Tindak Lanjut (Follow-Up):", 
                                     placeholder="Contoh: Kirim draf PO revisi besok pagi...")
            
            submit_btn = st.form_submit_button("💾 Simpan Laporan Kunjungan")
            
            if submit_btn:
                if not laporan_hasil.strip() or not follow_up.strip():
                    st.error("Gagal menyimpan! Kolom Laporan Hasil dan Follow-Up wajib diisi.")
                else:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute('''
                        UPDATE rencana_kunjungan 
                        SET laporan_hasil = ?, follow_up = ?, status = 'Selesai'
                        WHERE id = ?
                    ''', (laporan_hasil, follow_up, selected_id))
                    conn.commit()
                    conn.close()
                    st.success(f"Sukses! Laporan untuk {detail_cust['nama_customer']} telah tersimpan.")
                    st.rerun()
    else:
        st.success("🎉 Hebat! Semua agenda kunjungan Anda telah terlaporkan hari ini.")

# --- TAB 3: EXPORT LAPORAN & HISTORI ---
with tab3:
    st.header("📥 Pusat Unduh & Cetak Laporan")
    st.markdown("Anda dapat melihat seluruh riwayat kunjungan kerja yang telah selesai dan mengunduhnya ke berbagai format berkas.")
    
    conn = get_connection()
    query_all = """
        SELECT tanggal as [Tanggal], kota as [Kota Tujuan], nama_customer as [Nama Customer], 
               alasan_kunjungan as [Alasan Kunjungan], laporan_hasil as [Hasil Laporan], follow_up as [Rencana Follow-Up]
        FROM rencana_kunjungan 
        WHERE sales_name = ? AND status = 'Selesai'
        ORDER BY tanggal DESC
    """
    df_export = pd.read_sql_query(query_all, conn, params=(sales_aktif,))
    conn.close()
    
    if not df_export.empty:
        st.subheader(f"📊 Riwayat Data Laporan Kerja: {sales_aktif}")
        st.dataframe(df_export, use_container_width=True)
        
        # PROSES EXPORT EXCEL
        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Laporan Kunjungan')
        buffer_excel.seek(0)
        
        # PROSES EXPORT HTML / PDF
        html_content = f"""
        <html>
        <head>
            <title>Laporan Kunjungan Sales - {sales_aktif}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; color: #333; }}
                h2 {{ text-align: center; color: #1F4E79; font-size: 22px; margin-bottom: 5px; }}
                p.subtitle {{ text-align: center; font-size: 14px; color: #666; margin-top: 0; margin-bottom: 25px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ border: 1px solid #cbd5e1; padding: 12px; text-align: left; font-size: 12px; vertical-align: top; }}
                th {{ background-color: #f1f5f9; color: #1e293b; font-weight: bold; }}
                .meta {{ font-size: 14px; margin-bottom: 20px; line-height: 1.6; }}
            </style>
        </head>
        <body>
            <h2>LAPORAN KUNJUNGAN KERJA LUAR KOTA</h2>
            <p class="subtitle">Sistem Pelaporan Otomatis Akhir Hari Kantor</p>
            <div class="meta">
                <strong>Nama Anggota Tim:</strong> {sales_aktif}<br>
                <strong>Tanggal Cetak Dokumen:</strong> {datetime.now().strftime('%d %B %Y - %H:%M')} WIB
            </div>
            <table>
                <thead>
                    <tr>
                        <th style="width: 10%;">Tanggal</th>
                        <th style="width: 12%;">Kota</th>
                        <th style="width: 18%;">Nama Customer</th>
                        <th style="width: 20%;">Alasan Kunjungan</th>
                        <th style="width: 20%;">Hasil Laporan (Report)</th>
                        <th style="width: 20%;">Rencana Follow-Up</th>
                    </tr>
                </thead>
                <tbody>
        """
        for _, row in df_export.iterrows():
            html_content += f"""
                    <tr>
                        <td>{row['Tanggal']}</td>
                        <td>{row['Kota Tujuan']}</td>
                        <td>{row['Nama Customer']}</td>
                        <td>{row['Alasan Kunjungan']}</td>
                        <td>{row['Hasil Laporan']}</td>
                        <td>{row['Rencana Follow-Up']}</td>
                    </tr>
            """
        html_content += """
                </tbody>
            </table>
        </body>
        </html>
        """
        
        st.markdown("### 💾 Opsi Unduh Berkas")
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="🟢 Download Dokumen Excel (.xlsx)",
                data=buffer_excel,
                file_name=f"Laporan_Kunjungan_{sales_aktif.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        with col2:
            st.download_button(
                label="🔵 Download Cetak PDF / HTML (.html)",
                data=html_content,
                file_name=f"Laporan_Kunjungan_{sales_aktif.replace(' ', '_')}.html",
                mime="text/html"
            )
    else:
        st.warning("Belum ada riwayat laporan kunjungan yang berstatus 'Selesai' untuk diekspor.")
