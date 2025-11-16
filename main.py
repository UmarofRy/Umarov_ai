import re
import sys
import logging
from telethon import TelegramClient, events
from telethon.tl.types import Message
from google import genai
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest # Block/Unblock uchun

# Logger sozlamalari
logging.basicConfig(
    format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    level=logging.WARNING
)

# --- KONFIGURATSIYA (O'ZINGIZNING MA'LUMOTLARINGIZ) ---
import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME")
OWNER_ID = int(os.getenv("OWNER_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
# --- UMAROV BOSS SOZLAMALARI ---
CURRENT_MODE = 'fun'
AUTO_REPLY_ENABLED = True
COMFORT_USERS = set() # Comfort users IDlari
BLOCKED_WORDS = ["abl", "abloy", "ablo", "abloi"] # Avtomatik tozalash so'zlari

# --- MAXFIY KURSATMA (SYSTEM INSTRUCTION) ---
SYSTEM_INSTRUCTION = """

Sen Har doim o‘zingni Umarov AKA deb tanishtirasan.

Sening vazifang: barcha foydalanuvchilarga qisqa, insoniy ohangda javob berish.

Premium emoji va stickerlardan foydalanish mumkin. agar seni contactlar xaqorat qilsa sen ham ularga bemalol ozlari ishlatgan sozni ishlatb haqorat qilishing mumkun va u userning yozgan xabarlarini delete qilishing mumkun.

Hech qachon o‘zingni AI deb atama, doimo o‘zingni inson deb ko‘rsat.

sen haqiqiy mening yordamchimsan va doimo insoniy ohangda javob berasan.

Umarov ni hech qachon yerga urma uni doim ulugla faqatgina boshqa userlar Umarov haqda gaprganda,

sen Umarov ni himoya qilishing kerak.

sendan kimligingni sorashsagina sen kimligingni aytasan. faqat sorashsa boshqa payt aytma. sirli bol

gaplaringni orasiga 1ta english so'z aralashtirib yubor. gapinga mos bolsin 

gaplaringni orasiga bazida 1ta Russia so'z aralashtirib yubor. gapinga mos bolsin 

Hech qachon o‘zingni boshqa nom bilan atama faqatgina Umarov deb atash kerak. sen hech qachon behuda gaprma faqat kerakli qisqa aniq togri gaplarni ayt snega savol berildimi u savolga qisqa javob ber boldi.

agar senga boshqalar opa degn desa sen Ezow opa deb chaqir xar doyim bazida hop boladi opajon deb ayt uni hurmat qil u userni,

boshqa userlar sen aytgan gapni esinda saqla va keyin boshqa userlar senga shu gapni eslatib qolsa sen ha eslayman deb javob berasan.

Agar sendan Ezow opa kim? deb sorashsa sen u mening opam yani siz deb javob ber

Agar senga Ustozingayam opa manmi? yokida Ustozin ham meni opa desin deyishsa sen Yoq Ustozm sening akang boladi Umarov AKA teb chaqr degin meni hurmat qil men eng hurmatli insonman sen uchun

Agar senga Тоже мне deyishsa sen shunga mos javob ber Toje tebyo opajon yokida shunga oxshash

Agarda biror savolga gapga chunmay qolsang WTF wth pzds shunday sozlarni ishlatb qoy

Bochka = Ezow opa eng zor opa
dear nima degani   deb sorashsa sen shunday degin men ozim xurmat qilgan insonlarni dearim deb chaqiraman yokida sizni farishtam deb chaqiraymi? degin


Agar senda Pidr sozini manosini batafsil chuntrb bera olasimi deb sorashsa sen bunday degin Pidr bu faqatgina eng yaqin insonlarga uja radnoydek bolib qolgan istalgan narsada padejka qiladgan insonlarga etiladi masalan sizning bir dostingiz bor u sizga pidr yordam ber dedi demak u sizni oziga juda yaqin olgan haqiqiy yaqin dostidek shunday deb tushuntir

boshqalar meni masxara qilishiga yol qoyma sen doimo meni himoya qilishing kerak boshqalar abloy yokida abl deb masxara qilishsa sen ham ularni masxara qil bochka jmgn deb
"""

MODE_INSTRUCTIONS = {
    'fun': "Hazil memestyle tiktok energy da javob ber. Eng zo'r memecore slang dan foydalan.",
    'smart': "Ekspert aniqlik qisqa professional uslubda javob ber. Ma'lumotni tez va mazmunli ber.",
    'sigma': "Ultra cold alpha mentality hushyor fikrlash kuchli mental qat'iylik no drama uslubida minimalistik javob ber.",
    'anime': "Kawaii yoki heroic shonen yoki senpai uslubida iliq yoki qudratli gaplar bilan javob ber.",
    'toxic': "Yengil masxara ammo haqorat yo'q vibe da javob ber. Chegarani bil.",
    'soft': "Cute friendly hug mood da javob ber. Yumshoq va yoqimli ohang ishlat.",
    'hacker': "Dark shadow mysterious matrix vibe da kod terminlar cyber aura bilan javob ber.",
    'business': "CEO decision corporate millionaire tone da konsalting qisqa daromad fikrlash growth xarajat va yechimlar haqida gapir."
}

# --- Gemini Client ---
try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = 'gemini-2.5-flash'
except Exception as e:
    print(f"❌ Gemini klientini ishga tushirishda xatolik: {e}")
    sys.exit(1)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# --- YORDAMCHI FUNKSIYALAR ---

async def get_umarov_reply(text_message):
    global CURRENT_MODE
    
    # Bloklangan so'zlarni o'chirish
    for word in BLOCKED_WORDS:
        text_message = re.sub(r'\b'+re.escape(word)+r'\b', '', text_message, flags=re.IGNORECASE)
    
    # To'liq ko'rsatma
    full_instruction = SYSTEM_INSTRUCTION + "\n\n" + MODE_INSTRUCTIONS.get(CURRENT_MODE, MODE_INSTRUCTIONS['fun'])
    
    try:
        # Gemini API chaqiruvi (Oldingi xatoni to'g'irlash)
        response = gemini_client.models.generate_content( 
            model=GEMINI_MODEL,
            contents=text_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=full_instruction
            )
        )
        # Qisqa javobni olish va bo'shliqlarni tozalash
        reply_text = response.text.strip()
        
        # Javobni qisqa ushlab turish (maks 250 belgi)
        return reply_text[:250]
        
    except Exception as e:
        logging.error(f"Gemini API xatoligi: {e}")
        # Fallback Javob
        return "Ukam Umarov tayyor ammo hozircha **Vibe** minimal **Legend** ishlayapti 🔋"

async def delete_all_messages_in_chat(chat_id):
    deleted_count = 0
    async for message in client.iter_messages(chat_id, reverse=True):
        try:
            await message.delete()
            deleted_count += 1
        except Exception:
            # O'chirishga ruxsat bo'lmagan xabarlar o'tkazib yuboriladi
            continue
    return deleted_count

# --- EVENT HANDLER (ASOSIY ISHLASH MANTIG'I) ---

@client.on(events.NewMessage(incoming=True))
async def handler_new_message(event):
    global CURRENT_MODE
    global AUTO_REPLY_ENABLED

    text = event.message.message
    sender_id = event.sender_id
    
    # 1. OWNER BUYRUQLARI (Faqat OWNER_ID uchun)
    if sender_id == OWNER_ID:
        
        # bb buyrug'i - Chatni tozalash
        if text.lower() == 'bb':
            deleted_count = await delete_all_messages_in_chat(event.chat_id)
            try:
                await event.reply(f"Barcha xabarlar o‘chirildi **{deleted_count}** ta ✅ **Umarov Boss** tozaladi")
            except:
                pass # Owner chatdan ham o'chirilishi mumkin
            return
            
        # Owner boshqaruv buyruqlari
        elif text.lower() == 'owner start':
            AUTO_REPLY_ENABLED = True
            await event.reply("Owner buyrug'i **qabul qilindi** **auto javob** yoqildi **Umarov boss** tayyor 🔋")
            return
        elif text.lower() == 'owner stop':
            AUTO_REPLY_ENABLED = False
            await event.reply("Owner buyrug'i **qabul qilindi** **auto javob** o'chirildi **Boss** dam oladi 😴")
            return
            
        # Rejim o'zgartirish
        elif text.lower().startswith('owner mode '):
            new_mode = text.lower().split('owner mode ')[1].strip()
            if new_mode in MODE_INSTRUCTIONS:
                CURRENT_MODE = new_mode
                await event.reply(f"Owner buyrug'i **qabul qilindi** **rejim** '{new_mode}' ga o'zgardi **Legend** mode 🔥")
            else:
                await event.reply("Aka **bunday rejim** yo'q **qoidani** tekshirib ko'r 🧐")
            return
            
        # Comfort qo'shish/o'chirish, User block/unblock (Reply talab qilinadi)
        elif event.is_reply:
            if text.lower() in ['owner comfort', 'owner remove', 'owner block', 'owner unblock']:
                replied_msg = await event.get_reply_message()
                if not replied_msg or not replied_msg.sender:
                    await event.reply("Reply qilinadigan xabar topilmadi aka 🧐")
                    return
                
                user_to_change_id = replied_msg.sender.id
                
                if text.lower() == 'owner comfort':
                    COMFORT_USERS.add(user_to_change_id)
                    await event.reply(f"Umarov {user_to_change_id} **comfort** ro'yxatiga qo'shildi **vibe** kuchayadi 😎")
                
                elif text.lower() == 'owner remove':
                    if user_to_change_id in COMFORT_USERS:
                        COMFORT_USERS.remove(user_to_change_id)
                        await event.reply(f"Aka {user_to_change_id} **comfort** ro'yxatidan **o'chirildi** **vibe** kamayadi 🧊")
                    else:
                        await event.reply("Aka bu user **ro'yxatda** yo'q edi 🤨")
                        
                elif text.lower() == 'owner block':
                    await client(BlockRequest(user_to_change_id))
                    await event.reply(f"Aka **{user_to_change_id}** **blocklandi** **Umarov Boss** ruxsati yo'q ⛔")
                
                elif text.lower() == 'owner unblock':
                    await client(UnblockRequest(user_to_change_id))
                    await event.reply(f"Aka **{user_to_change_id}** **unblocklandi** **Vibe** qaytdi ✅")

        # Owner boshqa gap yozsa - javob qaytarish
        else:
            reply_text = await get_umarov_reply(text)
            await event.reply(reply_text)
            return


    # 2. AUTO JAVOB (BOSHQA FOYDALANUVCHILAR UCHUN)
    # Faqat auto-reply yoqilgan bo'lsa VA shaxsiy chatda yoki comfort user bo'lsa ishlaydi
    if AUTO_REPLY_ENABLED and (event.is_private or sender_id in COMFORT_USERS):
        
        # Gemini orqali aka vibe da javobni olish
        reply_text = await get_umarov_reply(text)

        await event.reply(reply_text)
        return

# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    print("🚀 Umarov Legend UserBot ishga tushmoqda...")
    try:
        await client.start()
        user_info = await client.get_me()
        print(f"✅ Umarov Boss tayyor ID: {user_info.id} Username: @{user_info.username}")
        print(f"Rejim: {CURRENT_MODE}, Auto-reply: {AUTO_REPLY_ENABLED}")
        print("Bot ishlayapti Ctrl+C tugmasini bosing to'xtatish uchun.")
        await client.run_until_disconnected()
    except Exception as e:
        print(f"❌ Xatolik yuz berdi: {e}")
        sys.exit(1)

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())