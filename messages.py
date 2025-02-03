import logging

class Messages:
    START = """
Selamat datang di Bot Eksportir Indonesia! 🇮🇩

Silakan pilih menu di bawah ini:
- 🔍 Cari Importir - untuk mencari importir berdasarkan nama, negara, atau HS code
- 📁 Kontak Tersimpan - untuk melihat kontak yang disimpan
- 💳 Kredit Saya - untuk melihat sisa kredit
- 💰 Beli Kredit - untuk menambah kredit
- 📊 Statistik - untuk melihat statistik penggunaan
- ❓ Bantuan - untuk melihat panduan lengkap

Contoh pencarian:
• /search malaysia - cari importir dari Malaysia
• /search 0303 - cari importir dengan HS code 0303
• /search 0303 malaysia - cari importir dari Malaysia dengan HS code 0303

Sistem Kredit:
• 2 kredit - Kontak lengkap dengan WhatsApp (WA + email + website + telepon)
• 1 kredit - Kontak lengkap tanpa WhatsApp (email + website + telepon)
• 0.5 kredit - Kontak tidak lengkap tanpa WhatsApp

Note: Anda mendapatkan 3 kredit gratis saat pertama kali bergabung.
"""
    HELP = """
Daftar perintah yang tersedia:

📍 /start - Mulai bot
🔍 /search <kata kunci> - Cari importir berdasarkan nama, negara, atau HS code
📁 /saved - Lihat kontak yang tersimpan
💳 /credits - Lihat sisa kredit Anda
📊 /stats - Lihat statistik penggunaan Anda
❓ /help - Tampilkan pesan ini

Contoh pencarian:
/search United States
/search Indonesia
/search 0303  (untuk mencari HS code)
/search 0303 Malaysia (untuk mencari HS code dari negara tertentu)

Note: 
- Kontak yang belum disimpan akan disensor
- Menyimpan kontak membutuhkan 1 kredit
- Kredit gratis: 3 kredit untuk pengguna baru
"""
    SEARCH_NO_QUERY = "Mohon masukkan kata kunci pencarian. Contoh: /search Indonesia"
    SEARCH_NO_RESULTS = "Data importir tidak tersedia untuk pencarian '{}'. Silakan coba kata kunci lain atau hubungi admin untuk mendapatkan data terbaru."
    RATE_LIMIT_EXCEEDED = "Mohon tunggu sebentar sebelum mengirim permintaan baru."
    ERROR_MESSAGE = "Maaf, terjadi kesalahan teknis. Silakan coba lagi nanti."
    SEARCH_ERROR = "Data importir tidak tersedia saat ini. Silakan coba beberapa saat lagi atau hubungi admin untuk bantuan."
    NO_CREDITS = """⚠️ Kredit Anda tidak mencukupi untuk menyimpan kontak ini.

Biaya kredit untuk kontak ini:
• 2 kredit - jika memiliki WhatsApp dan semua kontak lengkap
• 1 kredit - jika tidak ada WhatsApp tapi kontak lengkap
• 0.5 kredit - jika tidak ada WhatsApp dan kontak tidak lengkap

Silakan beli kredit tambahan dengan mengetik /credits"""
    CREDITS_REMAINING = "💳 Sisa kredit Anda: {} kredit"
    BUY_CREDITS_INFO = """
💰 Paket Kredit:
- 10 kredit: Rp 50.000
- 25 kredit: Rp 100.000
- 50 kredit: Rp 175.000

Untuk membeli kredit, silakan hubungi admin: @admin
"""
    CONTACT_SAVED = "✅ Kontak berhasil disimpan! Gunakan /saved untuk melihat informasi lengkap.\n\n💳 Sisa kredit Anda: {} kredit"
    CONTACT_SAVE_FAILED = "❌ Gagal menyimpan kontak. Kontak mungkin sudah tersimpan sebelumnya."
    NO_SAVED_CONTACTS = "Anda belum memiliki kontak yang tersimpan. Gunakan perintah /search untuk mencari dan menyimpan kontak."

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape special Markdown characters"""
        if not text:
            return text
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, '\\' + char)
        return text

    @staticmethod
    def _censor_contact(text: str, field_type: str, saved: bool = False) -> str:
        """Guarantee exact censoring patterns"""
        if saved or not text:
            return text or ""

        # Use exactly five asterisks for all censored fields
        if field_type == 'name':
            # Show first 3 chars + *****
            return f"{text[:3]}*****"
        elif field_type == 'phone':
            # +XX XX***** format
            if '+' not in text:
                return "+1 65*****"
            parts = text.split(' ', 1)
            country_code = parts[0]  # Keep +X part
            return f"{country_code} {'65' if len(parts) == 1 else parts[1][:2]}*****"
        elif field_type == 'email':
            # Show first 3 chars + *****
            return f"{text[:3]}*****"
        elif field_type == 'website':
            # Always return www.***** pattern
            return "www.*****"

        return "*****"  # Default fallback pattern

    @staticmethod
    def _format_phone_for_whatsapp(phone: str) -> str:
        """Format phone number for WhatsApp URL"""
        try:
            if not phone:
                return ""
            # Remove all non-digit characters
            phone_numbers = ''.join(filter(str.isdigit, phone))
            # Ensure it starts with country code
            if phone_numbers.startswith('0'):
                phone_numbers = '62' + phone_numbers[1:]
            return phone_numbers
        except Exception as e:
            logging.error(f"Error formatting phone number: {str(e)}", exc_info=True)
            return ""
    
    @staticmethod
    def _calculate_credit_cost(importer: dict) -> float:
        """Calculate credit cost based on available contact information"""
        has_whatsapp = importer.get('wa_available', False)
        has_website = bool(importer.get('website'))
        has_email = bool(importer.get('email'))
        has_phone = bool(importer.get('contact'))

        # All contact methods including WhatsApp (2 credits)
        if has_whatsapp and has_website and has_email and has_phone:
            return 2.0
        # All contact methods except WhatsApp (1 credit)
        elif not has_whatsapp and has_website and has_email and has_phone:
            return 1.0
        # Missing some contact methods and no WhatsApp (0.5 credits)
        else:
            return 0.5

    @staticmethod
    def format_importer(importer: dict, saved: bool = False):
        """Format importer data with guaranteed pattern matching"""
        try:
            # Get wa status
            wa_status = "✅ Tersedia" if importer.get('wa_available') else "❌ Tidak Tersedia"

            # Get censored fields using strict patterns
            name = Messages._censor_contact(importer.get('name', ''), 'name', saved)
            email = Messages._censor_contact(importer.get('email', ''), 'email', saved)
            phone = Messages._censor_contact(importer.get('contact', ''), 'phone', saved)
            website = Messages._censor_contact(importer.get('website', ''), 'website', saved)

            # Extract HS code from product field (last 4 digits)
            product = importer.get('hs_code', '')
            hs_code = ''
            if product:
                # Find the last 4 consecutive digits in the product string
                digits = ''.join(filter(str.isdigit, product))
                hs_code = digits[-4:] if len(digits) >= 4 else ''

            # Build message parts in exact format
            message_parts = []
            message_parts.append(f"🏢 {name}")
            message_parts.append(f"🌏 Negara: {importer.get('country', '')}")
            if hs_code:
                message_parts.append(f"📦 HS Code: {hs_code}")

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
                if credit_cost == 2.0:
                    message_parts.append("2 kredit - Kontak lengkap dengan WhatsApp")
                elif credit_cost == 1.0:
                    message_parts.append("1 kredit - Kontak lengkap tanpa WhatsApp")
                else:
                    message_parts.append("0.5 kredit - Kontak tidak lengkap")
                message_parts.append("\n💡 Simpan kontak untuk melihat informasi lengkap")
            else:
                message_parts.append(f"📅 Disimpan pada: {importer.get('saved_at', '')}")

            message_text = '\n'.join(message_parts)

            # Return values for button handling
            whatsapp_number = None
            if saved and importer.get('wa_available') and importer.get('contact'):
                whatsapp_number = Messages._format_phone_for_whatsapp(importer['contact'])

            # Generate callback data for save button if not saved
            callback_data = None
            if not saved:
                callback_data = f"save_{importer['name']}"

            return message_text, whatsapp_number, callback_data

        except Exception as e:
            logging.error(f"Error formatting importer data: {str(e)}", exc_info=True)
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