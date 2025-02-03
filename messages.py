class Messages:
    START = """
Selamat datang di Bot Eksportir Indonesia! 🇮🇩

Silakan pilih menu di bawah ini:
- 🔍 Cari Importir - untuk mencari importir
- 📁 Kontak Tersimpan - untuk melihat kontak yang disimpan
- 📊 Statistik - untuk melihat statistik penggunaan
- ❓ Bantuan - untuk melihat panduan lengkap
"""

    HELP = """
Daftar perintah yang tersedia:

📍 /start - Mulai bot
🔍 /search <kata kunci> - Cari importir berdasarkan nama atau negara
📁 /saved - Lihat kontak yang tersimpan
📊 /stats - Lihat statistik penggunaan Anda
❓ /help - Tampilkan pesan ini

Contoh pencarian:
/search United States
/search Indonesia

Note: Kontak yang belum disimpan akan disensor. Simpan kontak untuk melihat informasi lengkap.
"""

    SEARCH_NO_QUERY = "Mohon masukkan kata kunci pencarian. Contoh: /search Indonesia"
    SEARCH_NO_RESULTS = "Maaf, tidak ada hasil yang ditemukan untuk pencarian Anda."
    RATE_LIMIT_EXCEEDED = "Mohon tunggu sebentar sebelum mengirim permintaan baru."
    ERROR_MESSAGE = "Maaf, terjadi kesalahan. Silakan coba lagi nanti."
    CONTACT_SAVED = "✅ Kontak berhasil disimpan! Gunakan /saved untuk melihat informasi lengkap."
    CONTACT_SAVE_FAILED = "❌ Gagal menyimpan kontak. Kontak mungkin sudah tersimpan sebelumnya."
    NO_SAVED_CONTACTS = "Anda belum memiliki kontak yang tersimpan. Gunakan perintah /search untuk mencari dan menyimpan kontak."

    @staticmethod
    def _censor_text(text: str, saved: bool = False) -> str:
        """Censor text by showing only first and last character"""
        if not text or saved:
            return text
        if len(text) <= 4:
            return "*" * len(text)
        return f"{text[0]}{'*' * (len(text)-2)}{text[-1]}"

    @staticmethod
    def _format_phone_for_whatsapp(phone: str) -> str:
        """Format phone number for WhatsApp URL"""
        if not phone:
            return None

        # Remove all non-digit characters
        phone_numbers = ''.join(filter(str.isdigit, phone))
        # Ensure it starts with country code
        if phone_numbers.startswith('0'):
            phone_numbers = '62' + phone_numbers[1:]
        return phone_numbers

    @staticmethod
    def format_importer(importer, saved=False):
        """Format importer data and return (message_text, whatsapp_number, callback_data)"""
        wa_status = "✅ Tersedia" if importer.get('wa_available') else "❌ Tidak Tersedia"

        # Censor information if not saved
        name = Messages._censor_text(importer['name'], saved)
        email = Messages._censor_text(importer.get('email', 'Tidak tersedia'), saved)
        phone = Messages._censor_text(importer.get('contact', ''), saved)
        website = Messages._censor_text(importer.get('website', 'Tidak tersedia'), saved)

        saved_at = importer.get('saved_at', '')

        message_text = f"""
🏢 *{name}*
🌏 Negara: {importer['country']}
📱 Kontak: {phone}
📧 Email: {email}
🌐 Website: {website}
📱 WhatsApp: {wa_status}
"""
        if saved_at:
            message_text += f"📅 Disimpan pada: {saved_at}\n"
        elif not saved:
            message_text += "\n💡 Simpan kontak untuk melihat informasi lengkap"

        # Return whatsapp number for button if available and saved
        whatsapp_number = None
        if importer.get('wa_available') and importer.get('contact') and saved:
            whatsapp_number = Messages._format_phone_for_whatsapp(importer['contact'])

        # Generate callback data for save button if not saved
        callback_data = None
        if not saved:
            callback_data = f"save_{importer['name']}"

        return message_text, whatsapp_number, callback_data

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