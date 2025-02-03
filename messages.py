class Messages:
    START = """
Selamat datang di Bot Eksportir Indonesia! 🇮🇩

Saya dapat membantu Anda mencari informasi tentang importir.
Gunakan perintah berikut:

/search <kata kunci> - Cari importir berdasarkan nama atau negara
/help - Lihat daftar perintah
/stats - Lihat statistik penggunaan

Silakan mulai dengan mengetik /help untuk melihat semua perintah yang tersedia.
"""

    HELP = """
Daftar perintah yang tersedia:

📍 /start - Mulai bot
🔍 /search <kata kunci> - Cari importir berdasarkan nama atau negara
📊 /stats - Lihat statistik penggunaan Anda
❓ /help - Tampilkan pesan ini

Contoh pencarian:
/search United States
/search Indonesia
"""

    SEARCH_NO_QUERY = "Mohon masukkan kata kunci pencarian. Contoh: /search Indonesia"
    SEARCH_NO_RESULTS = "Maaf, tidak ada hasil yang ditemukan untuk pencarian Anda."
    RATE_LIMIT_EXCEEDED = "Mohon tunggu sebentar sebelum mengirim permintaan baru."
    ERROR_MESSAGE = "Maaf, terjadi kesalahan. Silakan coba lagi nanti."

    @staticmethod
    def format_importer(importer):
        wa_status = "✅ Tersedia" if importer.get('wa_available') else "❌ Tidak Tersedia"
        email = importer.get('email', 'Tidak tersedia')
        website = importer.get('website', 'Tidak tersedia')

        return f"""
🏢 *{importer['name']}*
🌏 Negara: {importer['country']}
📱 Kontak: {importer['contact']}
📧 Email: {email}
🌐 Website: {website}
📱 WhatsApp: {wa_status}
"""

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