import logging

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
🔍 /search <kata kunci> - Cari importir berdasarkan nama, negara, atau HS code
📁 /saved - Lihat kontak yang tersimpan
📊 /stats - Lihat statistik penggunaan Anda
❓ /help - Tampilkan pesan ini

Contoh pencarian:
/search United States
/search Indonesia
/search 0302  (untuk mencari HS code)
/search 0302 Malaysia (untuk mencari HS code dari negara tertentu)

Note: Kontak yang belum disimpan akan disensor. Simpan kontak untuk melihat informasi lengkap.
"""
    SEARCH_NO_QUERY = "Mohon masukkan kata kunci pencarian. Contoh: /search Indonesia"
    SEARCH_NO_RESULTS = "Data importir tidak tersedia untuk pencarian '{}'. Silakan coba kata kunci lain atau hubungi admin untuk mendapatkan data terbaru."
    RATE_LIMIT_EXCEEDED = "Mohon tunggu sebentar sebelum mengirim permintaan baru."
    ERROR_MESSAGE = "Maaf, terjadi kesalahan teknis. Silakan coba lagi nanti."
    SEARCH_ERROR = "Data importir tidak tersedia saat ini. Silakan coba beberapa saat lagi atau hubungi admin untuk bantuan."
    CONTACT_SAVED = "✅ Kontak berhasil disimpan! Gunakan /saved untuk melihat informasi lengkap."
    CONTACT_SAVE_FAILED = "❌ Gagal menyimpan kontak. Kontak mungkin sudah tersimpan sebelumnya."
    NO_SAVED_CONTACTS = "Anda belum memiliki kontak yang tersimpan. Gunakan perintah /search untuk mencari dan menyimpan kontak."

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape special Markdown characters"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, '\\' + char)
        return text

    @staticmethod
    def _censor_text(text: str, field_type: str = 'default', saved: bool = False) -> str:
        """Censor text based on field type with specific formatting"""
        try:
            if saved:
                return text or ""  # Return original text or empty string if saved

            if not text:
                return ""  # Return empty string for unavailable info

            if not isinstance(text, str):
                text = str(text)

            text = text.strip()
            if not text:
                return ""

            # Different censoring rules based on field type
            if field_type == 'name':
                # Show only first character for company names
                return f"{text[0]}{'*' * (len(text)-1)}"
            elif field_type == 'phone':
                # Show first 5 digits of phone numbers
                visible_length = min(5, len(text))
                return f"{text[:visible_length]}{'*' * (len(text)-visible_length)}"
            elif field_type == 'email':
                # Show first 5 chars of email
                at_index = text.find('@')
                if at_index == -1:
                    visible_length = min(5, len(text))
                else:
                    visible_length = min(5, at_index)
                return f"{text[:visible_length]}{'*' * (len(text)-visible_length)}"
            elif field_type == 'website':
                # Show protocol and first part of domain
                if text.startswith('http'):
                    protocol_end = text.find('://') + 3
                    visible_length = min(protocol_end + 5, len(text))
                    return f"{text[:visible_length]}{'*' * (len(text)-visible_length)}"
                else:
                    visible_length = min(5, len(text))
                    return f"{text[:visible_length]}{'*' * (len(text)-visible_length)}"
            else:
                # Default censoring for other fields
                visible_length = min(5, len(text))
                return f"{text[:visible_length]}{'*' * (len(text)-visible_length)}"

        except Exception as e:
            logging.error(f"Error in _censor_text: {str(e)}", exc_info=True)
            return "*****"  # Return safe fallback if censoring fails

    @staticmethod
    def _format_phone_for_whatsapp(phone: str) -> str:
        """Format phone number for WhatsApp URL"""
        try:
            if not phone:
                logging.debug("Empty phone number provided")
                return ""

            # Remove all non-digit characters
            phone_numbers = ''.join(filter(str.isdigit, phone))
            logging.debug(f"Cleaned phone number: {phone} -> {phone_numbers}")

            # Ensure it starts with country code
            if phone_numbers.startswith('0'):
                phone_numbers = '62' + phone_numbers[1:]
                logging.debug(f"Added country code: {phone_numbers}")
            return phone_numbers
        except Exception as e:
            logging.error(f"Error formatting phone number: {str(e)}", exc_info=True)
            return ""
    
    @staticmethod
    def format_importer(importer, saved=False):
        """Format importer data and return (message_text, whatsapp_number, callback_data)"""
        try:
            logging.info(f"Formatting importer data: saved={saved}, name={importer.get('name', 'N/A')}")

            wa_status = "✅ Tersedia" if importer.get('wa_available') else "❌ Tidak Tersedia"

            # Censor information if not saved
            name = Messages._censor_text(importer.get('name', ''), 'name', saved)
            email = Messages._censor_text(importer.get('email', ''), 'email', saved)
            phone = Messages._censor_text(importer.get('contact', ''), 'phone', saved)
            website = Messages._censor_text(importer.get('website', ''), 'website', saved)
            product = importer.get('product', '')  # HS code doesn't need censoring

            # Escape Markdown characters in all fields
            name = Messages._escape_markdown(name)
            email = Messages._escape_markdown(email)
            phone = Messages._escape_markdown(phone)
            website = Messages._escape_markdown(website)
            country = Messages._escape_markdown(importer.get('country', ''))
            product = Messages._escape_markdown(product)

            logging.debug(f"Processed fields - Name: {name}, Phone: {phone}, Email: {email}")

            saved_at = importer.get('saved_at', '')

            # Base message with required fields
            message_text = f"""
🏢 *{name}*
🌏 Negara: {country}"""

            # Add HS code if available (moved up in the order)
            if product:
                message_text += f"\n📦 HS Code: {product}"

            # Add optional fields only if they have content
            if phone:
                message_text += f"\n📱 Kontak: {phone}"
            if email:
                message_text += f"\n📧 Email: {email}"
            if website:
                message_text += f"\n🌐 Website: {website}"

            message_text += f"\n📱 WhatsApp: {wa_status}"

            if saved_at:
                message_text += f"\n📅 Disimpan pada: {saved_at}"
            elif not saved:
                message_text += "\n\n💡 Simpan kontak untuk melihat informasi lengkap"

            # Return whatsapp number for button if available and saved
            whatsapp_number = None
            if importer.get('wa_available') and importer.get('contact') and saved:
                whatsapp_number = Messages._format_phone_for_whatsapp(importer['contact'])
                logging.debug(f"WhatsApp number formatted: {whatsapp_number}")

            # Generate callback data for save button if not saved
            callback_data = None
            if not saved:
                callback_data = f"save_{importer['name']}"
                logging.debug(f"Generated callback data: {callback_data}")

            logging.info(f"Successfully formatted message for importer {name}")
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