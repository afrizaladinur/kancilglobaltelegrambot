class Messages:
    START = """
Selamat datang di Bot Eksportir Indonesia! 🇮🇩

Saya dapat membantu Anda mencari informasi tentang importir.
Gunakan perintah berikut:

/search <kata kunci> - Cari importir
/help - Lihat daftar perintah
/stats - Lihat statistik penggunaan

Silakan mulai dengan mengetik /help untuk melihat semua perintah yang tersedia.
"""

    HELP = """
Daftar perintah yang tersedia:

📍 /start - Mulai bot
🔍 /search <kata kunci> - Cari importir berdasarkan nama atau produk
📊 /stats - Lihat statistik penggunaan Anda
❓ /help - Tampilkan pesan ini

Contoh pencarian:
/search electronics
"""

    SEARCH_NO_QUERY = "Mohon masukkan kata kunci pencarian. Contoh: /search electronics"
    SEARCH_NO_RESULTS = "Maaf, tidak ada hasil yang ditemukan untuk pencarian Anda."
    RATE_LIMIT_EXCEEDED = "Mohon tunggu sebentar sebelum mengirim permintaan baru."
    ERROR_MESSAGE = "Maaf, terjadi kesalahan. Silakan coba lagi nanti."

    @staticmethod
    def format_importer(importer):
        return f"""
🏢 *{importer['name']}*
🌏 Negara: {importer['country']}
📦 Produk: {', '.join(importer['products'])}
📧 Kontak: {importer['contact']}
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
