import logging

class Messages:
    START = """
Selamat datang di Bot Eksportir Indonesia! 🇮🇩

*Menu Utama:*
• 🔍 *Cari Importir* - Pencarian data importir:
  ├ *Berdasarkan Negara:*

    @staticmethod
    def get_country_emoji(country: str) -> str:
        """Get emoji for a country"""
        country_emojis = {
            'China': '🇨🇳',
            'Japan': '🇯🇵',
            'Korea': '🇰🇷',
            'United States': '🇺🇸',
            'Vietnam': '🇻🇳',
            'Thailand': '🇹🇭',
            'Singapore': '🇸🇬',
            'Malaysia': '🇲🇾',
            'Indonesia': '🇮🇩',
            'India': '🇮🇳'
        }
        return country_emojis.get(country, '🌐')


  │ Format: /search [nama negara]
  │ Contoh: `/search malaysia`, `/search japan`
  │
  ├ *Berdasarkan Kode HS:*
  │ Format: /search [kode 4 digit]
  │ Contoh: `/search 0302` untuk produk ikan segar
  │        `/search 0303` untuk produk ikan beku
  │
  └ *Pencarian Kombinasi:*
    Format: /search [kode hs] [negara]
    Contoh: `/search 0302 malaysia`
           `/search 0303 japan`

• 📁 *Kontak Tersimpan* - Melihat kontak yang sudah disimpan
• 💳 *Kredit Saya* - Cek saldo kredit Anda
• 💰 *Beli Kredit* - Tambah kredit untuk menyimpan kontak
• 📊 *Statistik* - Lihat riwayat penggunaan
• ❓ *Bantuan* - Panduan lengkap
• 📦 *Data Tersedia* - Lihat daftar kode HS yang tersedia

*Sistem Kredit:*
• 3 kredit - Kontak lengkap dengan WhatsApp
• 2 kredit - Kontak lengkap tanpa WhatsApp
• 1 kredit - Kontak tidak lengkap

*Tips Pencarian:*
• Gunakan kode HS untuk hasil lebih spesifik
• Kombinasikan negara + kode HS untuk filter terbaik
• Simpan kontak penting agar bisa diakses kapan saja

Kredit awal: 10 kredit (gratis untuk pengguna baru)
"""
    HELP = """
Daftar perintah yang tersedia:

📍 /start - Mulai bot
🔍 /search <kata kunci> - Cari importir berdasarkan nama, negara, atau kode HS
📁 /saved - Lihat kontak yang tersimpan
💳 /credits - Lihat sisa kredit Anda
📊 /stats - Lihat statistik penggunaan Anda
❓ /help - Tampilkan pesan ini

Contoh pencarian:
/search malaysia
/search 0303
/search 0303 malaysia

*Data Tersedia*

*Data Importir:*
• 0301 - Ikan hidup
• 0302 - Ikan segar
• 0303 - Ikan beku
• 0304 - Fillet ikan
• 0901 - Kopi

Catatan: 
- Kontak yang belum disimpan akan disensor
- Menyimpan kontak membutuhkan kredit
- Kredit gratis: 10 kredit untuk pengguna baru
"""
    SEARCH_NO_QUERY = """🔍 *Panduan Pencarian Importir*

*A. Cari berdasarkan Negara:*
   Format: /search [nama negara]
   Contoh: `/search malaysia`
          `/search japan`

*B. Cari berdasarkan Kode HS:*
   Format: /search [kode 4 digit]
   Contoh: `/search 0302` (ikan segar)
          `/search 0303` (ikan beku)

*C. Pencarian Kombinasi:*
   Format: /search [kode hs] [negara]
   Contoh: `/search 0302 malaysia`
          `/search 0303 japan`

💡 *Tips:*
• Gunakan kode HS untuk hasil yang lebih spesifik
• Kombinasikan dengan negara untuk filter terbaik
• Data akan diperbarui secara berkala"""
    SEARCH_NO_RESULTS = "Data importir tidak tersedia untuk pencarian '{}'. Silakan coba kata kunci lain atau hubungi admin untuk mendapatkan data terbaru."
    RATE_LIMIT_EXCEEDED = "Mohon tunggu sebentar sebelum mengirim permintaan baru."
    ERROR_MESSAGE = "Maaf, terjadi kesalahan teknis. Silakan coba lagi nanti."
    SEARCH_ERROR = "Data importir tidak tersedia saat ini. Silakan coba beberapa saat lagi atau hubungi admin untuk bantuan."
    NO_CREDITS = """⚠️ Kredit Anda tidak mencukupi untuk menyimpan kontak ini.

Biaya kredit untuk kontak ini:
• 3 kredit - Kontak lengkap dengan WhatsApp
• 2 kredit - Kontak lengkap tanpa WhatsApp
• 1 kredit - Kontak tidak lengkap tanpa WhatsApp

Silakan beli kredit tambahan dengan mengetik /credits"""
    CREDITS_REMAINING = "💳 Sisa kredit Anda: {} kredit"
    BUY_CREDITS_INFO = """
💰 Paket Kredit:
- 20 kredit: Rp 50.000
- 45 kredit: Rp 100.000
- 100 kredit: Rp 200.000
"""
    CONTACT_SAVED = "✅ Kontak berhasil disimpan! Gunakan /saved untuk melihat informasi lengkap.\n\n💳 Sisa kredit Anda: {} kredit"
    CONTACT_SAVE_FAILED = "❌ Gagal menyimpan kontak. Kontak mungkin sudah tersimpan sebelumnya."
    NO_SAVED_CONTACTS = "Anda belum memiliki kontak yang tersimpan. Gunakan perintah /search untuk mencari dan menyimpan kontak."

    @staticmethod
    def _escape_markdown(text: str) -> str:
        if not text:
            return text
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, '\\' + char)
        return text

    @staticmethod 
    def _censor_contact(text: str, field_type: str, saved: bool = False) -> str:
        CENSOR = "X" * 6

        if saved:
            return text or ""

        if not text:
            return CENSOR

        def prefix_with_censor(prefix: str) -> str:
            return prefix + CENSOR

        censor_rules = {
            'name': lambda t: prefix_with_censor(t[:6]) if len(t) > 3 else t,
            'email': lambda t: prefix_with_censor(t[:6]),
            'phone': lambda t: prefix_with_censor("+1 65") if '+' not in t else \
                    prefix_with_censor(t.split()[0] + " " + (t.split()[1][:2] if len(t.split()) > 1 else "65")),
            'website': lambda t: prefix_with_censor("www.")
        }

        return censor_rules.get(field_type, lambda t: CENSOR)(text)

    @staticmethod
    def _format_phone_for_whatsapp(phone: str) -> str:
        try:
            if not phone:
                return ""
            phone_numbers = ''.join(filter(str.isdigit, phone))
            if phone_numbers.startswith('0'):
                phone_numbers = '62' + phone_numbers[1:]
            return phone_numbers
        except Exception as e:
            logging.error(f"Kesalahan format nomor telepon: {str(e)}", exc_info=True)
            return ""

    @staticmethod
    def _calculate_credit_cost(importer: dict) -> float:
        has_whatsapp = importer.get('wa_available', False)

        if has_whatsapp:
            return 3.0

        has_website = bool(importer.get('website'))
        has_email = bool(importer.get('email'))
        has_phone = bool(importer.get('contact'))

        if has_website and has_email and has_phone:
            return 2.0
        else:
            return 1.0

    @staticmethod
    def format_importer(importer: dict, saved: bool = False):
        try:
            wa_status = "✅ Tersedia" if importer.get('wa_available') else "❌ Tidak Tersedia"

            name = Messages._censor_contact(importer.get('name', ''), 'name', saved)
            email = Messages._censor_contact(importer.get('email', ''), 'email', saved)
            phone = Messages._censor_contact(importer.get('contact', ''), 'phone', saved)
            website = Messages._censor_contact(importer.get('website', ''), 'website', saved)

            product = importer.get('hs_code', '')
            hs_code = ''
            if product:
                digits = ''.join(filter(str.isdigit, product))
                hs_code = digits[-4:] if len(digits) >= 4 else ''

            message_parts = []
            message_parts.append(f"🏢 {name}")
            country = importer.get('country', '')
            country_emoji = Messages.get_country_emoji(country)
            message_parts.append(f"🌏 Negara: {country_emoji} {country}")
            if hs_code:
                message_parts.append(f"📦 Kode HS: {hs_code}")

            if phone:
                message_parts.append(f"📱 Kontak: {phone}")
            if email:
                message_parts.append(f"📧 Email: {email}")
            if website:
                message_parts.append(f"🌐 Website: {website}")

            message_parts.append(f"📱 WhatsApp: {wa_status}")

            if not saved:
                credit_cost = Messages._calculate_credit_cost(importer)
                message_parts.append("\n💳 Biaya kredit yang diperlukan:")
                if credit_cost == 3.0:
                    message_parts.append("3 kredit - Kontak lengkap dengan WhatsApp")
                elif credit_cost == 2.0:
                    message_parts.append("2 kredit - Kontak lengkap tanpa WhatsApp")
                else:
                    message_parts.append("1 kredit - Kontak tidak lengkap tanpa WhatsApp")
                message_parts.append("\n💡 Simpan kontak untuk melihat informasi lengkap")
            else:
                message_parts.append(f"📅 Disimpan pada: {importer.get('saved_at', '')}")

            message_text = '\n'.join(message_parts)

            whatsapp_number = None
            if saved and importer.get('wa_available') and importer.get('contact'):
                whatsapp_number = Messages._format_phone_for_whatsapp(importer['contact'])

            callback_data = None
            if not saved:
                callback_data = f"save_{importer['name']}"

            return message_text, whatsapp_number, callback_data

        except Exception as e:
            logging.error(f"Kesalahan format data importir: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def format_stats(stats):
        total = stats['total_commands']
        commands = stats['commands']

        command_stats = '\n'.join([
            f"/{cmd}: {count} kali"
            for cmd, count in commands.items()
        ])

        return f"""
📊 *Statistik Penggunaan Anda*

Total perintah: {total}

Rincian perintah:
{command_stats}
"""