import logging
from typing import Optional

class Messages:

    COMMUNITY_INFO = """
*Kancil Global Network* 🌟

Komunitas eksklusif untuk pelaku ekspor impor Indonesia yang berbasis teknologi dan pemuda. 

*Apa yang Anda dapatkan:*
• 📊 Berbagi informasi dan peluang bisnis
• 🤝 Networking dengan pelaku ekspor impor
• 📱 Updates teknologi terbaru
• 👥 Kolaborasi antar anggota
• 💡 Sharing knowledge dan pengalaman

Biaya: 5 kredit

Join sekarang dan mulai ekspansi bisnis Anda! 🚀
"""

    START = """
Selamat datang di Bot Eksportir Indonesia! 🇮🇩

*Fitur Terbaru:* Gabung Kancil Global Network! 🌟

*Menu Utama:*
• 📤 *Kontak Supplier* - Eksportir Indonesia
• 📥 *Kontak Buyer* - Importir Lokal & Global
• 📁 *Kontak Tersimpan* - Akses kontak yang sudah disimpan
• 💳 *Kredit Saya* - Cek saldo kredit dan beli kredit
• ❓ *Bantuan* - Panduan lengkap

*Sistem Kredit:*
• Kredit adalah mata uang dalam bot ini
• Digunakan untuk menyimpan kontak & akses fitur
• Setiap pengguna baru dapat 10 kredit gratis

*Biaya per Kontak:*
• 3 kredit - Kontak lengkap dengan WhatsApp
• 2 kredit - Kontak lengkap tanpa WhatsApp
• 1 kredit - Kontak tidak lengkap

*Tips Pencarian:*
• Gunakan kode HS untuk hasil lebih spesifik
• Kombinasikan negara + kode HS untuk filter terbaik
• Simpan kontak penting agar bisa diakses kapan saja

*👋 Khusus untuk user baru, kamu bisa mendapatkan 10 Kredit GRATIS!*
1. Klik menu '💳 Kredit Saya'
2. Kemudian pilih '🎁 Klaim 10 Kredit Gratis'
"""
    HELP = """
*Panduan Penggunaan Bot Eksportir Indonesia* 🇮🇩

*Cara Mencari Kontak Importir:*
1. Pilih menu "📦 Kontak Tersedia"
2. Pilih kategori produk yang sesuai
3. Pilih jenis produk spesifik
4. Simpan kontak yang diinginkan

*Sistem Kredit:*
• 3 kredit - Kontak lengkap dengan WhatsApp
• 2 kredit - Kontak lengkap tanpa WhatsApp
• 1 kredit - Kontak tidak lengkap

*Fitur Utama:*
• 📦 *Kontak Tersedia* - Lihat daftar kontak per kategori
• 📁 *Kontak Tersimpan* - Akses kontak yang telah disimpan
• 💳 *Kredit Saya* - Cek saldo kredit dan beli kredit

*Catatan Penting:*
• Kontak yang belum disimpan akan disensor
• Kredit gratis: 10 kredit untuk pengguna baru
• Kontak bisa diekspor ke CSV untuk pencatatan
"""
    SEARCH_NO_QUERY = """*Panduan Pencarian Kontak* 📦

Silakan pilih kategori produk melalui menu "Kontak Tersedia" untuk melihat daftar kontak importir yang tersedia.

Kategori yang tersedia:
• 🌊 Produk Laut (ikan segar, beku, dll)
• 🌿 Produk Agrikultur (kopi, manggis, dll)
• 🌳 Produk Olahan (briket, minyak kelapa)

Pilih kategori untuk melihat daftar kontak:"""
    SEARCH_NO_RESULTS = "Kontak importir tidak tersedia untuk pencarian '{}'. Silakan coba kata kunci lain atau hubungi admin untuk mendapatkan kontak terbaru."
    RATE_LIMIT_EXCEEDED = "Mohon tunggu sebentar sebelum mengirim permintaan baru."
    ERROR_MESSAGE = "Maaf, terjadi kesalahan teknis. Silakan coba lagi nanti."
    SEARCH_ERROR = "Kontak importir tidak tersedia saat ini. Silakan coba beberapa saat lagi atau hubungi admin untuk bantuan."
    NO_CREDITS = """⚠️ Kredit Anda tidak mencukupi untuk menyimpan kontak ini.

Biaya kredit untuk kontak ini:
• 3 kredit - Kontak lengkap dengan WhatsApp
• 2 kredit - Kontak lengkap tanpa WhatsApp
• 1 kredit - Kontak tidak lengkap tanpa WhatsApp

Silakan beli kredit tambahan dengan mengetik /credits"""
    CREDITS_REMAINING = "💳 Sisa kredit Anda: {} kredit"
    BUY_CREDITS_INFO = """
💡 Sistem Kredit:

Kredit digunakan untuk:
• Menyimpan kontak importir (1-3 kredit)
• Mengakses komunitas (5 kredit)

Biaya kredit per kontak:
• 3 kredit - Kontak lengkap dengan WhatsApp
• 2 kredit - Kontak lengkap tanpa WhatsApp 
• 1 kredit - Kontak tidak lengkap

Setiap pengguna baru mendapat 10 kredit gratis!
"""
    CONTACT_SAVED = "✅ Kontak berhasil disimpan! Gunakan /saved untuk melihat informasi lengkap.\n\n💳 Sisa kredit Anda: {} kredit"
    CONTACT_SAVE_FAILED = "❌ Gagal menyimpan kontak. Kontak mungkin sudah tersimpan sebelumnya."
    NO_SAVED_CONTACTS = "Anda belum memiliki kontak yang tersimpan. Gunakan perintah /search untuk mencari dan menyimpan kontak."


    SUPPLIER_CATEGORIES = {
        'Marine': {
            'emoji': '🌊',
            'subcategories': {
                'Anchovy': {'emoji': '🐟', 'search': 'ID Anchovy'}
            }
        },
        'Agriculture': {
            'emoji': '🌾',
            'subcategories': {
                'Coffee': {'emoji': '☕', 'search': 'ID Coffee'},
                'Betel Nut': {'emoji': '🌰', 'search': 'ID Betel Nut'},
                'Birdnest': {'emoji': '🪺', 'search': 'ID Birdnest'}
            }
        },
        'Industrial': {
            'emoji': '🏭',
            'subcategories': {
                'Briquette': {'emoji': '🪵', 'search': 'ID Briquette'},
                'Damar': {'emoji': '💎', 'search': 'ID Damar'},
                'Palm Kernel Shell': {'emoji': '🌴', 'search': 'ID Palm Kernel Shell'},
                'Cashew': {'emoji': '🥜', 'search': 'ID Cashew'}
            }
        },
        'Spices': {
            'emoji': '🌶️',
            'subcategories': {
                'Cinnamon': {'emoji': '🌿', 'search': 'ID Cinnamon'},
                'Clove': {'emoji': '🌺', 'search': 'ID Clove'}
            }
        }
    }

    BUYER_CATEGORIES = {
        'Palm & Furniture': {
            'emoji': '🏭',
            'subcategories': {
                'Palm Oil': {'emoji': '🌴', 'search': 'ID 1511'},
                'Furniture': {'emoji': '🪑', 'search': 'ID 94035'}
            }
        },
        'Marine Products': {
            'emoji': '🌊',
            'subcategories': {
                'Fresh Fish': {'emoji': '🐟', 'search': 'WW 0302'},
                'Frozen Fish': {'emoji': '❄️', 'search': 'WW 0303'},
                'Fish Fillet': {'emoji': '🍣', 'search': 'WW 0304'},
                'Anchovy': {'emoji': '🐟', 'search': 'WW Anchovy'}
            }
        },
        'Agriculture': {
            'emoji': '🌾',
            'subcategories': {
                'Coffee': {'emoji': '☕', 'search': 'WW 0901'},
                'Banana Leaves': {'emoji': '🍌', 'search': 'WW Banana Leaves'},
                'Candle Nut': {'emoji': '🌰', 'search': 'WW Candle Nut'},
                'Coconut Oil': {'emoji': '🥥', 'search': 'WW Coconut Oil'},
                'Birdnest': {'emoji': '🪺', 'search': 'ID Birdnest'}
            }
        },
        'Industrial': {
            'emoji': '🏭',
            'subcategories': {
                'Briquette': {'emoji': '🪵', 'search': 'WW 44029010'},
                'Damar': {'emoji': '💎', 'search': 'ID Damar'},
                'Cashew': {'emoji': '🥜', 'search': 'ID Cashew'}
            }
        }
    }

    @staticmethod
    def get_country_emoji(country: str) -> str:
        """Get emoji for a country"""
        country_emojis = {
            'China': '🇨🇳',
            'Japan': '🇯🇵',
            'Korea': '🇰🇷',
            'South Korea': '🇰🇷',
            'United States': '🇺🇸',
            'USA': '🇺🇸',
            'U.S.': '🇺🇸',
            'Vietnam': '🇻🇳',
            'Thailand': '🇹🇭',
            'Singapore': '🇸🇬',
            'Malaysia': '🇲🇾',
            'Indonesia': '🇮🇩',
            'India': '🇮🇳',
            'Taiwan': '🇹🇼',
            'Hong Kong': '🇭🇰',
            'Philippines': '🇵🇭',
            'Australia': '🇦🇺',
            'New Zealand': '🇳🇿',
            'Canada': '🇨🇦',
            'Mexico': '🇲🇽',
            'Brazil': '🇧🇷',
            'United Kingdom': '🇬🇧',
            'UK': '🇬🇧',
            'Germany': '🇩🇪',
            'France': '🇫🇷',
            'Italy': '🇮🇹',
            'Spain': '🇪🇸',
            'Netherlands': '🇳🇱',
            'Russia': '🇷🇺',
            'Saudi Arabia': '🇸🇦',
            'UAE': '🇦🇪',
            'United Arab Emirates': '🇦🇪'
        }
        # Case-insensitive lookup
        for key, value in country_emojis.items():
            if country.lower() == key.lower():
                return value
        return '🌐'


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
    def format_search_results(results, page, items_per_page=2):
        """Format search results with pagination"""
        total_pages = (len(results) + items_per_page - 1) // items_per_page
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        return results[start_idx:end_idx], total_pages

    @staticmethod
    def format_importer(importer: dict, saved: bool = False):
        """Format importer information for display"""
        try:
            wa_status = "✅ Tersedia" if importer.get('wa_available') else "❌ Tidak Tersedia"

            # Determine if they have imported from Indonesia before
            role = importer.get('role', '')
            product = importer.get('product', '')
            has_imported = None
            if role == 'Importer':
                if product.startswith('ID '):
                    has_imported = True
                elif product.startswith('WW '):
                    has_imported = False

            name = Messages._censor_contact(importer.get('name', ''), 'name', saved)
            email = Messages._censor_contact(importer.get('email', ''), 'email', saved)
            phone = Messages._censor_contact(importer.get('contact', ''), 'phone', saved)
            website = Messages._censor_contact(importer.get('website', ''), 'website', saved)

            message_parts = []
            message_parts.append(f"🏢 {Messages._escape_markdown(name)}")
            message_parts.append(f"Peran: {role}")

            if role == 'Importer':
                import_status = "Ya" if has_imported else "Tidak"
                message_parts.append(f"Pernah Impor dari Indonesia?: {import_status}")

            country = importer.get('country', '')
            country_emoji = Messages.get_country_emoji(country)
            message_parts.append(f"🌏 Negara: {country_emoji} {Messages._escape_markdown(country)}")

            # Extract HS code/product
            hs_code = product.replace('ID ', '').replace('WW ', '') if product else ''
            if hs_code:
                message_parts.append(f"📦 Kode HS/Product: {Messages._escape_markdown(hs_code)}")

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
                safe_name = importer['name'].strip()[:30]
                callback_data = f"save_{safe_name}"

            return message_text, whatsapp_number, callback_data

        except Exception as e:
            logging.error(f"Error formatting importer: {str(e)}", exc_info=True)
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