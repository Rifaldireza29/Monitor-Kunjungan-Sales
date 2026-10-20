from datetime import datetime
import io
import pandas as pd
import streamlit as st

# --- LIBRARY GOOGLE SHEETS ---
from google.oauth2.service_account import Credentials
import gspread

# --- SETUP Koneksi Google Sheets ---
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_gsheet_client():
  creds_dict = dict(st.secrets["gcp_service_account"])
  creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
  client = gspread.authorize(creds)
  return client


def get_worksheet():
  client = get_gsheet_client()
  sheet_name = "DB_Kunjungan_Sales"
  sh = client.open(sheet_name)
  worksheet = sh.worksheet("rencana_kunjungan")
  return worksheet


# --- LOAD DATA DENGAN CACHE & TTL ---
@st.cache_data(ttl=300)  # Cache data selama 5 menit agar tidak lambat
def load_data_to_df():
  ws = get_worksheet()
  data = ws.get_all_records()
  if not data:
    return pd.DataFrame(
        columns=[
            "id",
            "sales_name",
            "tanggal",
            "kota",
            "nama_customer",
            "alasan_kunjungan",
            "status",
            "laporan_hasil",
            "follow_up",
        ]
    )
  return pd.DataFrame(data)


# --- STREAMLIT UI SETUP ---
st.set_page_config(
    page_title="Sales Visit & Report System (GSheet)", layout="wide"
)

st.title("🧳 Sistem Kunjungan Luar Kota Sales & Supervisor (Cloud)")
st.markdown(
    "Manajemen jadwal keberangkatan, tracking alasan kunjungan, serta pengisian"
    " laporan daily report berbasis Google Sheets."
)

# Sidebar Pengguna & Tambah Data
st.sidebar.header("👤 Profil Pengguna")
daftar_sales = ["Alfian", "Asep", "Azia", "Dadan", "Didin", "Fajar", "Rizky"]
sales_aktif = st.sidebar.selectbox("Pilih Nama Anda:", daftar_sales)

st.sidebar.markdown("---")
st.sidebar.header("➕ Tambah Jadwal Baru")
with st.sidebar.form("form_tambah_jadwal"):
  new_date = st.date_input("Tanggal Kunjungan:", datetime.now())
  new_kota = st.text_input("Kota Tujuan:", placeholder="Contoh: Bandung")
  new_cust = st.text_input("Nama Customer:", placeholder="Contoh: PT Surya Abadi")
  new_alasan = st.text_area(
      "Alasan Kunjungan:", placeholder="Contoh: Penawaran produk baru..."
  )

  submit_jadwal = st.form_submit_button("Tambah ke Rencana")
  if submit_jadwal:
    if not new_kota.strip() or not new_cust.strip() or not new_alasan.strip():
      st.error("Semua kolom input jadwal wajib diisi!")
    else:
      # Bersihkan cache agar data terbaru langsung terbaca
      st.cache_data.clear()

      ws = get_worksheet()
      df_existing = ws.get_all_records()
      if df_existing:
        df_temp = pd.DataFrame(df_existing)
        numeric_ids = pd.to_numeric(df_temp["id"], errors="coerce")
        new_id = int(numeric_ids.max()) + 1 if not numeric_ids.isna().all() else 1
      else:
        new_id = 1

      row_data = [
          int(new_id),
          sales_aktif,
          new_date.strftime("%Y-%m-%d"),
          new_kota,
          new_cust,
          new_alasan,
          "Plan",
          "",
          "",
      ]
      ws.append_row(row_data)

      st.success("Jadwal baru berhasil ditambahkan ke Google Sheets!")
      st.rerun()

# Pembuatan Tab Menu Utama
tab1, tab2, tab3 = st.tabs(
    ["🗓️ Rencana Kunjungan", "📝 Input Report (Pulang Kantor)", "📊 Export Histori"]
)

# --- TAB 1: LIHAT RENCANA KUNJUNGAN ---
with tab1:
  col_title, col_btn = st.columns([4, 1])
  with col_title:
    st.header("Cek Jadwal Kunjungan Luar Kota")
  with col_btn:
    st.write("")  # Spacing vertikal agar sejajar
    if st.button("🔄 Refresh Data", key="ref_tab1"):
      st.cache_data.clear()
      st.success("Data berhasil diperbarui!")
      st.rerun()

  st.info(
      "Pilih tanggal keberangkatan Anda untuk memunculkan daftar target"
      " customer beserta alasan kunjungan."
  )

  tanggal_cari = st.date_input(
      "Pilih Tanggal Rencana Perjalanan:", datetime.now(), key="cari_tgl"
  )
  str_tanggal = tanggal_cari.strftime("%Y-%m-%d")

  df = load_data_to_df()
  if not df.empty:
    df["id"] = df["id"].astype(str)
    filtered_df = df[
        (df["sales_name"] == sales_aktif) & (df["tanggal"] == str_tanggal)
    ]

    display_df = filtered_df[
        ["kota", "nama_customer", "alasan_kunjungan", "status"]
    ].rename(
        columns={
            "kota": "Kota Tujuan",
            "nama_customer": "Nama Customer",
            "alasan_kunjungan": "Alasan Kunjungan",
            "status": "Status Laporan",
        }
    )

    if not display_df.empty:
      st.subheader(f"📋 Jadwal untuk {sales_aktif} pada {str_tanggal}")
      st.dataframe(display_df, use_container_width=True)
    else:
      st.warning(
          f"Tidak ada jadwal kunjungan luar kota terdaftar untuk {sales_aktif}"
          f" pada tanggal {str_tanggal}."
      )
  else:
    st.warning("Belum ada data sama sekali di Google Sheets.")

# --- TAB 2: INPUT LAPORAN & FOLLOW-UP (PULANG KANTOR) ---
with tab2:
  col_title2, col_btn2 = st.columns([4, 1])
  with col_title2:
    st.header("Laporan Hasil Kunjungan Akhir Hari")
  with col_btn2:
    st.write("")
    if st.button("🔄 Refresh Data", key="ref_tab2"):
      st.cache_data.clear()
      st.success("Data berhasil diperbarui!")
      st.rerun()

  st.markdown(
      "Isi form di bawah ini ketika Anda telah kembali atau sebelum jam pulang"
      " kantor selesai."
  )

  df = load_data_to_df()
  if not df.empty:
    df_lap = df[
        (df["sales_name"] == sales_aktif) & (df["status"] == "Plan")
    ].copy()

    if not df_lap.empty:
      pilihan_customer = {
          f"{row['nama_customer']} (Rencana: {row['tanggal']})": row["id"]
          for _, row in df_lap.iterrows()
      }
      selected_cust_label = st.selectbox(
          "Pilih Customer yang Baru Selesai Dikunjungi:",
          list(pilihan_customer.keys()),
      )

      selected_id = pilihan_customer[selected_cust_label]
      detail_cust = df_lap[df_lap["id"] == selected_id].iloc[0]

      st.info(f"📌 **Tujuan Awal Kunjungan:** {detail_cust['alasan_kunjungan']}")

      with st.form("form_report"):
        laporan_hasil = st.text_area(
            "📝 Tulis Laporan Hasil Kunjungan (Report):",
            placeholder=(
                "Contoh: Pemilik toko sepakat meningkatkan volume pembelian"
                " 15%..."
            ),
        )
        follow_up = st.text_area(
            "🚀 Tindakan Tindak Lanjut (Follow-Up):",
            placeholder="Contoh: Kirim draf PO revisi besok pagi...",
        )

        submit_btn = st.form_submit_button("💾 Simpan Laporan Kunjungan")

        if submit_btn:
          if not laporan_hasil.strip() or not follow_up.strip():
            st.error(
                "Gagal menyimpan! Kolom Laporan Hasil dan Follow-Up wajib"
                " diisi."
            )
          else:
            st.cache_data.clear()
            ws = get_worksheet()
            cell = ws.find(str(selected_id))
            if cell:
              row_idx = cell.row
              ws.update_cell(row_idx, 7, "Selesai")
              ws.update_cell(row_idx, 8, laporan_hasil)
              ws.update_cell(row_idx, 9, follow_up)

              st.success(
                  f"Sukses! Laporan untuk {detail_cust['nama_customer']} telah"
                  " tersimpan di Google Sheets."
              )
              st.rerun()
    else:
      st.success("🎉 Hebat! Semua agenda kunjungan Anda telah terlaporkan hari ini.")
  else:
    st.warning("Belum ada data di Google Sheets.")

# --- TAB 3: EXPORT LAPORAN & HISTORI ---
with tab3:
  col_title3, col_btn3 = st.columns([4, 1])
  with col_title3:
    st.header("📥 Pusat Unduh & Cetak Laporan")
  with col_btn3:
    st.write("")
    if st.button("🔄 Refresh Data", key="ref_tab3"):
      st.cache_data.clear()
      st.success("Data berhasil diperbarui!")
      st.rerun()

  st.markdown(
      "Anda dapat melihat seluruh riwayat kunjungan kerja yang telah selesai"
      " dan mengunduhnya ke berbagai format berkas."
  )

  df = load_data_to_df()
  if not df.empty:
    df_export = df[
        (df["sales_name"] == sales_aktif) & (df["status"] == "Selesai")
    ].copy()

    if not df_export.empty:
      df_display_export = df_export[
          [
              "tanggal",
              "kota",
              "nama_customer",
              "alasan_kunjungan",
              "laporan_hasil",
              "follow_up",
          ]
      ].rename(
          columns={
              "tanggal": "Tanggal",
              "kota": "Kota Tujuan",
              "nama_customer": "Nama Customer",
              "alasan_kunjungan": "Alasan Kunjungan",
              "laporan_hasil": "Hasil Laporan",
              "follow_up": "Rencana Follow-Up",
          }
      )

      st.subheader(f"📊 Riwayat Data Laporan Kerja: {sales_aktif}")
      st.dataframe(df_display_export, use_container_width=True)

      # PROSES EXPORT EXCEL
      buffer_excel = io.BytesIO()
      with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Laporan Kunjungan")
      buffer_excel.seek(0)

      st.markdown("### 💾 Opsi Unduh Berkas")
      st.download_button(
          label="🟢 Download Dokumen Excel (.xlsx)",
          data=buffer_excel,
          file_name=f"Laporan_Kunjungan_{sales_aktif.replace(' ', '_')}.xlsx",
          mime=(
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          ),
      )
    else:
      st.warning(
          "Belum ada riwayat laporan kunjungan yang berstatus 'Selesai' untuk"
          " diekspor."
      )
  else:
    st.warning("Belum ada data di Google Sheets.")