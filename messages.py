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
*Permudah Bisnis Ekspor Impor dengan Teknologi* 🚀

Selamat datang di Bot Eksportir Indonesia! 🇮🇩

Kami merupakan layanan data ekspor-impor *terlengkap* di Indonesia. 
Dapatkan kontak importir dan eksportir dengan mudah melalui bot ini.

*Sistem Kredit:*
• Kredit adalah mata uang dalam bot ini
• Digunakan untuk menyimpan kontak & akses fitur
• Setiap pengguna baru dapat 20 kredit gratis

*👋 Khusus untuk user baru, kamu bisa mendapatkan 10 Kredit GRATIS!*
1. Klik menu '💳 Kredit Saya'
2. Kemudian pilih '🎁 Klaim 20 Kredit Gratis'

💡 *Butuh data ekspor - impor lainnya? Hubungi Admin!*

"""
    HELP = """
*Panduan Penggunaan Bot Kancil Global* 🇮🇩

*Cara Mendapatkan Kontak:*
1. Pilih menu "📤 Kontak Supplier" atau "📥 Kontak Buyer"
2. Pilih kontak yang diinginkan
3. Tekan tombol simpan untuk menyimpan kontak
4. Akses kembali lewat menu "📁 Kontak Tersimpan"

*Sistem Kredit:*
• 3 kredit - Kontak lengkap dengan WhatsApp
• 2 kredit - Kontak lengkap tanpa WhatsApp  
• 1 kredit - Kontak tidak lengkap

*Menu Utama:*
• 📤 *Kontak Supplier* - Cari kontak supplier
• 📥 *Kontak Buyer* - Cari kontak buyer
• 📁 *Kontak Tersimpan* - Akses kontak tersimpan
• 💳 *Kredit Saya* - Cek sisa kredit
• 🌟 *Kancil Global Network* - Komunitas eksportir

*Catatan:*
• Kontak yang belum disimpan akan disensor
• Member baru dapat 20 kredit gratis
• Gabung Kancil Global Network (5 kredit)
• Hubungi admin untuk informasi lebih lanjut
"""

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

Setiap pengguna baru mendapat 20 kredit gratis!
"""
    CONTACT_SAVED = "✅ Kontak berhasil disimpan! Gunakan /saved untuk melihat informasi lengkap.\n\n💳 Sisa kredit Anda: {} kredit"
    CONTACT_SAVE_FAILED = "❌ Gagal menyimpan kontak. Kontak mungkin sudah tersimpan sebelumnya."
    NO_SAVED_CONTACTS = "Anda belum memiliki kontak yang tersimpan. Gunakan perintah /search untuk mencari dan menyimpan kontak."


    SUPPLIER_CATEGORIES = {
        'Hasil Laut': {
            'emoji': '🐟',
            'subcategories': {
                'Anchovy': {'emoji': '🐟', 'search': 'ID Anchovy'}
            }
        },
        'Agrikultur': {
            'emoji': '🌱',
            'subcategories': {
                'Coffee': {'emoji': '☕', 'search': 'ID Coffee'},
                'Betel Nut': {'emoji': '🥥', 'search': 'ID Betel Nut'},
                'Kayu Manis': {'emoji': '🍂', 'search': 'ID Cinnamon'},
                'Cengkeh': {'emoji': '🌸', 'search': 'ID Clove'}
            }
        },
        'Industri': {
            'emoji': '🏭',
            'subcategories': {
                'Briket Batok Kelapa': {'emoji': '🔥', 'search': 'ID Briquette'},
                'Damar Batu': {'emoji': '🪨', 'search': 'ID Damar'},
                'Cangkang Sawit': {'emoji': '🌴', 'search': 'ID Palm Kernel Shell'},
                'Cashew': {'emoji': '🥜', 'search': 'ID Cashew'},
                'Birdnest': {'emoji': '🕊️', 'search': 'ID Birdnest'}
            }
        }
    }

    BUYER_CATEGORIES = {
        'Industri': {
            'emoji': '🏭',
            'subcategories': {
                'Minyak Sawit': {'emoji': '🌴', 'search': 'ID 1511'},
                'Furniture': {'emoji': '🛋️', 'search': 'ID 94035'},
                'Briket Batok Kelapa': {'emoji': '🔥', 'search': 'WW 44029010'},
                'Damar': {'emoji': '🪨', 'search': 'ID Damar'},
                'Cashew': {'emoji': '🥜', 'search': 'ID Cashew'}
            }
        },
        'Hasil Laut': {
            'emoji': '🐠',
            'subcategories': {
                'Fresh Fish (HS 0302)': {'emoji': '🐟', 'search': 'WW 0302'},
                'Frozen Fish (HS 0303)': {'emoji': '❄️', 'search': 'WW 0303'},
                'Fish Fillet (HS 0304)': {'emoji': '🍣', 'search': 'WW 0304'},
                'Anchovy': {'emoji': '🐟', 'search': 'WW Anchovy'}
            }
        },
        'Agrikultur': {
            'emoji': '🌾',
            'subcategories': {
                'Kopi': {'emoji': '☕', 'search': 'WW 0901'},
                'Daun Pisang': {'emoji': '🍌', 'search': 'WW Banana Leaves'},
                'Kemiri': {'emoji': '🥥', 'search': 'WW Candle Nut'},
                'Minyak Kelapa': {'emoji': '🥥', 'search': 'WW Coconut Oil'},
                'Sarang Burung Wallet': {'emoji': '🕊️', 'search': 'ID Birdnest'}
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
            'website': lambda _: prefix_with_censor("www.")
        }

        return censor_rules.get(field_type, lambda _: CENSOR)(text)

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
    def _calculate_credit_cost(importer: dict) -> int:
        has_whatsapp = importer.get('wa_available', False)
        has_website = bool(importer.get('website'))
        has_email = bool(importer.get('email'))
        has_phone = bool(importer.get('contact'))

        if has_whatsapp:
            return 3
        elif has_website and has_email and has_phone:
            return 2
        else:
            return 1

    @staticmethod
    def format_search_results(results, page, items_per_page=2):
        """Format search results with pagination"""
        total_pages = (len(results) + items_per_page - 1) // items_per_page
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        return results[start_idx:end_idx], total_pages

    @staticmethod
    def format_importer(importer: dict, saved: bool = False):
        try:
            # Basic info formatting
            name = Messages._censor_contact(importer.get('name', ''), 'name', saved)
            email = Messages._censor_contact(importer.get('email', ''), 'email', saved)
            phone = Messages._censor_contact(importer.get('contact', ''), 'phone', saved)
            website = Messages._censor_contact(importer.get('website', ''), 'website', saved)
            role = importer.get('role', '')
            product = importer.get('product', '')
            country = importer.get('country', '')
            wa_status = "✅ Tersedia" if importer.get('wa_available') else "❌ Tidak Tersedia"
    
            # Build message without formatting tags
            message_parts = []
            message_parts.append(f"🏢 {name}")
            message_parts.append(f"Peran: {role}")
    
            if role == 'Importer':
                import_status = "Ya" if product.startswith('ID ') else "Tidak"
                message_parts.append(f"Pernah Impor dari Indonesia?: {import_status}")
    
            country_emoji = Messages.get_country_emoji(country)
            message_parts.append(f"🌏 Negara: {country_emoji} {country}")
    
            hs_code = product.replace('ID ', '').replace('WW ', '') if product else ''
            if hs_code:
                message_parts.append(f"📦 Kode HS/Product: {hs_code}")
    
            if phone:
                message_parts.append(f"📱 Kontak: {phone}")
            if email:
                message_parts.append(f"📧 Email: {email}")
            if website:
                clean_url = website.strip()
                if '//' in clean_url:
                    base_url = clean_url.split('/')[0] + '//' + clean_url.split('/')[2]
                    message_parts.append(f"🌐 Website: {base_url}")
                else:
                    message_parts.append(f"🌐 Website: {clean_url}")
    
            message_parts.append(f"📱 WhatsApp: {wa_status}")
            whatsapp_number = Messages._format_phone_for_whatsapp(importer.get('contact', ''))
            callback_data = None
            
            if not saved:
                credit_cost = Messages._calculate_credit_cost(importer)
                message_parts.append("\n💳 Biaya kredit yang diperlukan:")
                cost_text = {
                    3: "3 kredit - Kontak lengkap dengan WhatsApp",
                    2: "2 kredit - Kontak lengkap tanpa WhatsApp",
                    1: "1 kredit - Kontak tidak lengkap tanpa WhatsApp"
                }.get(credit_cost, "1 kredit - Kontak tidak lengkap tanpa WhatsApp")
                message_parts.append(cost_text)
                message_parts.append("\n💡 Simpan kontak untuk melihat informasi lengkap")
            else:
                saved_at = importer.get('saved_at', '')
                message_parts.append(f"📅 Disimpan pada: {saved_at}")
    
            message_text = '\n'.join(message_parts)
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