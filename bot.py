import logging
import random
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest, Forbidden


# Konfiguratsiya va global o'zgaruvchilar
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
MY_GROUP = os.getenv("MY_GROUP")  # Yangi: Guruh ID'si environment o'zgaruvchisidan olinadi
DATA_DIR = "data"
COURSES_FILE = os.path.join(DATA_DIR, "courses.json")
QUESTIONS_FILE = os.path.join(DATA_DIR, "questions.json")
SCHOOLS_FILE = os.path.join(DATA_DIR, "schools.json")
USER_DATA_FILE = os.path.join(DATA_DIR, "user_data.json")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")

# Log faylini sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ma'lumotlarni yuklash
def load_data():
    data = {}
    for filename in [COURSES_FILE, QUESTIONS_FILE, SCHOOLS_FILE, USER_DATA_FILE, RESULTS_FILE]:
        key = os.path.basename(filename).split('.')[0]
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data[key] = json.load(f)
            else:
                data[key] = {}
        except Exception as e:
            logger.error(f"Faylni yuklashda xato '{filename}': {e}")
            data[key] = {}
    return data['courses'], data['questions'], data['schools'], data['user_data'], data['results']

# Ma'lumotlarni saqlash
def save_data(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Faylni saqlashda xato '{filename}': {e}")

courses, questions_pool, schools, user_data, results = load_data()

# Asosiy menyu (oddiy foydalanuvchilar uchun)
MAIN_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📝 Sinov testi", callback_data="start_test")],
    [InlineKeyboardButton("📚 Kurslar haqida", callback_data="courses_list")],
    [InlineKeyboardButton("👨‍🏫 O'qituvchi haqida", callback_data="teacher_info")],
    [InlineKeyboardButton("📊 Natijalarim", callback_data="show_results")]
])

# Admin menyu
ADMIN_MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("👥 Barcha o'quvchilar", callback_data="admin_users")],
    [InlineKeyboardButton("📊 Barcha natijalar", callback_data="admin_results")],
    [InlineKeyboardButton("📢 Barchaga xabar", callback_data="admin_broadcast")],
    [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="main_menu")]
])

# Telefon raqami so'rash menyusi
PHONE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 Telefon raqamini kiritish", callback_data="enter_phone")],
    [InlineKeyboardButton("📞 Telegramdagi raqamni yuborish", callback_data="share_phone")]
])

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str):
    logger.info(f"Foydalanuvchi {user_id}: Asosiy menyu ko'rsatilmoqda.")
    quote = random.choice([
        "Matematika — bu olamning tilidir. — Galileo Galilei",
        "Matematikada hech qachon xato qilmagan odam hech qachon yangi narsani kashf etmagan. — Carl Friedrich Gauss",
        "Matematika — bu bilimning malikasi. — Johann Bernoulli"
    ])
    text = (
        f"📜 *{quote}*\n\n"
        f"Xush kelibsiz, {user_data.get(user_id, {}).get('first_name', 'aziz foydalanuvchi')}!\n"
        f"Matematika bilimlaringizni sinash uchun *Sinov testi* tugmasini bosing "
        f"yoki boshqa imkoniyatlarni ko'rish uchun tugmalardan birini tanlang."
    )
    
    if user_id == ADMIN_ID:
        keyboard = ADMIN_MENU_KEYBOARD
    else:
        keyboard = MAIN_KEYBOARD
    
    try:
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')
        elif update.message:
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        logger.info(f"Foydalanuvchi {user_id}: Asosiy menyu muvaffaqiyatli yuborildi.")
    except BadRequest as e:
        logger.error(f"Asosiy menyu yuborishda xato: {e}")
        if update.message:
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    logger.info(f"Foydalanuvchi {user_id}: /start buyrug'i qabul qilindi.")
    
    if user_id not in user_data:
        user_data[user_id] = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "class": None,
            "school": None,
            "phone": None,
            "group_joined": False,
            "last_test_date": None,
            "test_count_today": 0,
            "waiting_for": None
        }
        save_data(user_data, USER_DATA_FILE)

    if user_id not in results:
        results[user_id] = []
        save_data(results, RESULTS_FILE)
    
    if user_data.get(user_id, {}).get("class") and user_data.get(user_id, {}).get("school") and user_data.get(user_id, {}).get("phone") and user_data.get(user_id, {}).get("group_joined"):
        await show_main_menu(update, context, user_id)
        return
    
    if not user_data[user_id].get("class"):
        classes_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("5-sinf", callback_data="class_5"),
                InlineKeyboardButton("6-sinf", callback_data="class_6"),
                InlineKeyboardButton("7-sinf", callback_data="class_7")
            ],
            [
                InlineKeyboardButton("8-sinf", callback_data="class_8"),
                InlineKeyboardButton("9-sinf", callback_data="class_9"),
                InlineKeyboardButton("10-sinf", callback_data="class_10")
            ],
            [
                InlineKeyboardButton("11-sinf", callback_data="class_11")
            ]
        ])
        
        await update.message.reply_text(
            f"Xush kelibsiz, {user.first_name}! Siz bilan yaqinroq tanishish uchun nechanchi sinf o'quvchisi ekanligingizni tanlang:",
            reply_markup=classes_keyboard,
            parse_mode='Markdown'
        )
        return
    
    if not user_data[user_id].get("school"):
        # Bu yerda class tanlangan deb hisoblaymiz, lekin start da emas, handle_class dan chaqiriladi
        pass
    
    if not user_data[user_id].get("phone"):
        await update.message.reply_text(
            f"Telefon raqamingizni kiriting yoki Telegramdagi raqamingizni yuboring:",
            reply_markup=PHONE_KEYBOARD,
            parse_mode='Markdown'
        )
        return
    
    if not user_data[user_id].get("group_joined"):
        await handle_group_join(update, context)

# Sinf tanlaganda
async def handle_class_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    selected_class = query.data.split("_")[1]
    
    user_data[user_id]["class"] = selected_class
    save_data(user_data, USER_DATA_FILE)
    
    school_keys = list(schools.get("schools", {}).keys())
    keyboard_rows = []
    for i in range(0, len(school_keys), 2):
        row = school_keys[i:i+2]
        keyboard_rows.append([InlineKeyboardButton(f"{key} maktab", callback_data=f"school_{key}") for key in row])

    keyboard_rows.append([InlineKeyboardButton("Boshqa maktab", callback_data="school_other")])

    school_keyboard = InlineKeyboardMarkup(keyboard_rows)

    await query.edit_message_text(
        f"Tushundim, siz {selected_class}-sinf o'quvchisi ekansiz. Qaysi maktab o'quvchisisiz?",
        reply_markup=school_keyboard,
        parse_mode='Markdown'
    )

# Maktab tanlaganda
async def handle_school_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    school_data = query.data.split("_")[1]
    
    school_name = schools.get("schools", {}).get(school_data, "Boshqa maktab") if school_data != "other" else "Boshqa maktab"
    user_data[user_id]["school"] = school_name
    save_data(user_data, USER_DATA_FILE)
    
    await query.edit_message_text(
        f"Demak, siz {school_name} o'quvchisisiz! Telefon raqamingizni kiriting yoki Telegramdagi raqamingizni yuboring:",
        reply_markup=PHONE_KEYBOARD,
        parse_mode='Markdown'
    )

# Telefon raqami kiritishni tanlaganda
async def handle_phone_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    if query.data == "enter_phone":
        user_data[user_id]["waiting_for"] = "phone"
        save_data(user_data, USER_DATA_FILE)
        await query.edit_message_text(
            "📱 Telefon raqamingizni quyidagi formatda kiriting: +998901234567\n"
            "Raqam '+' bilan boshlanishi va kamida 12 ta belgidan iborat bo'lishi kerak.",
            parse_mode='Markdown'
        )
    elif query.data == "share_phone":
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📞 Raqamni yuborish", request_contact=True)]],
            one_time_keyboard=True
        )
        await query.edit_message_text(
            "Quyidagi tugma orqali Telegramdagi raqamingizni yuboring:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

# Guruhga a'zo bo'lish
async def handle_group_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    group_link = f"t.me/{MY_GROUP}" if MY_GROUP.startswith('+') or MY_GROUP.startswith('-') else MY_GROUP
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_group")]])
    text = (
        f"Ro'yxatdan o'tishni yakunlash uchun quyidagi guruhga a'zo bo'ling:\n"
        f"{group_link}\n\n"
        f"A'zo bo'lganingizdan so'ng, *Tasdiqlash* tugmasini bosing."
    )
    
    try:
        if update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await context.bot.send_message(user_id, text, reply_markup=keyboard, parse_mode='Markdown')
    except BadRequest as e:
        logger.error(f"Guruh xabari yuborishda xato: {e}")

# Guruh a'zoligini tasdiqlash
async def handle_group_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    try:
        member = await context.bot.get_chat_member(MY_GROUP, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            user_data[user_id]["group_joined"] = True
            save_data(user_data, USER_DATA_FILE)
            await query.edit_message_text(
                "✅ Guruhga a'zo bo'ldingiz! Endi asosiy menyudan foydalanishingiz mumkin.",
                reply_markup=MAIN_KEYBOARD,
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "Siz hali guruhga a'zo bo'lmagansiz. Iltimos, guruhga qo'shiling va qayta tasdiqlang.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_group")]]),
                parse_mode='Markdown'
            )
    except Forbidden as e:
        logger.error(f"Guruh a'zoligini tekshirishda xato: {e}")
        await query.edit_message_text(
            "Bot guruhda admin sifatida bo'lishi kerak. Iltimos, botni guruhda admin qiling yoki ma'muriyat bilan bog'laning.",
            parse_mode='Markdown'
        )
    except BadRequest as e:
        logger.error(f"Guruh a'zoligini tekshirishda xato: {e}")
        await query.edit_message_text(
            "Guruhni tekshirishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring yoki ma'muriyat bilan bog'laning.",
            parse_mode='Markdown'
        )

# O'qituvchi haqida
async def show_teacher_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "👨‍🏫 **O'qituvchi haqida**\n\n"
        "Salom! Men Shoxrux Ibrohimovman. Matematika bo'yicha tajribali o'qituvchiman.\n"
        "10 yildan ortiq o'qituvchilik tajribam bor. O'quvchilarimni yuqori natijalarga erishishga yordam beraman.\n\n"
        "📞 Aloqa: +998507551023\n"
        "@Shoxrux_Ibrohimov"
    )
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Asosiy menyu", callback_data="main_menu")]])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

# Natijalarni ko'rsatish (oddiy user uchun)
async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user_results = results.get(user_id, [])
    
    if not user_results:
        text = "Sizda hali natijalar yo'q. Sinov testini topshirib ko'ring!"
        await query.edit_message_text(text, reply_markup=MAIN_KEYBOARD)
        return
    
    result_text = "📊 Sizning natijalaringiz:\n\n"
    for i, res in enumerate(user_results[-5:], 1):
        percentage = (res['score'] / res['total']) * 100 if res['total'] > 0 else 0
        result_text += (
            f"{i}. Fan: {res['subject'].capitalize()}\n"
            f"   Natija: {res['score']}/{res['total']} ({percentage:.1f}%)\n"
            f"   Sana: {res['date'][:19].replace('T', ' ')}\n\n"
        )
    
    await query.edit_message_text(result_text, reply_markup=MAIN_KEYBOARD, parse_mode='Markdown')

# Admin: Barcha o'quvchilar
async def admin_show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not user_data:
        text = "O'quvchilar yo'q."
        await query.edit_message_text(text, reply_markup=ADMIN_MENU_KEYBOARD)
        return
    
    users_text = "👥 **Barcha o'quvchilar:**\n\n"
    for i, (uid, info) in enumerate(user_data.items(), 1):
        phone = info.get('phone', 'Kiritilmagan')
        school = info.get('school', 'Kiritilmagan')
        cls = info.get('class', 'Kiritilmagan')
        full_name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip() or 'Noma\'lum'
        users_text += f"{i}. {full_name} (Sinf: {cls}, Maktab: {school}, Telefon: {phone})\n"
    
    await query.edit_message_text(users_text, reply_markup=ADMIN_MENU_KEYBOARD, parse_mode='Markdown')

# Admin: Barcha natijalar
async def admin_show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not results:
        text = "Natijalar yo'q."
        await query.edit_message_text(text, reply_markup=ADMIN_MENU_KEYBOARD)
        return
    
    results_text = "📊 **Barcha natijalar:**\n\n"
    for uid, user_results in results.items():
        if not user_results:
            continue
        info = user_data.get(uid, {})
        full_name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip() or 'Noma\'lum'
        results_text += f"**{full_name} (ID: {uid}):**\n"
        for res in user_results[-3:]:
            percentage = (res['score'] / res['total']) * 100 if res['total'] > 0 else 0
            results_text += f"   - {res['subject'].capitalize()}: {res['score']}/{res['total']} ({percentage:.1f}%) - {res['date'][:19].replace('T', ' ')}\n"
        results_text += "\n"
    
    await query.edit_message_text(results_text, reply_markup=ADMIN_MENU_KEYBOARD, parse_mode='Markdown')

# Admin: Barchaga xabar tayyorlash
async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    user_data[user_id]["waiting_for"] = "broadcast"
    save_data(user_data, USER_DATA_FILE)
    
    text = "📢 Xabaringizni yuboring (matn yoki rasm + izoh bilan). Yuborganingizdan keyin barcha o'quvchilarga jo'natiladi."
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_cancel_broadcast")]])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

# Admin: Broadcast bekor qilish
async def admin_cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    if user_data[user_id].get("waiting_for") == "broadcast":
        user_data[user_id]["waiting_for"] = None
        save_data(user_data, USER_DATA_FILE)
    
    await show_main_menu(update, context, user_id)

# Testni boshlash
async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user = user_data.get(user_id, {})
    
    if not user.get("class") or not user.get("school") or not user.get("phone") or not user.get("group_joined"):
        await query.edit_message_text("Iltimos, avval sinfingiz, maktabingiz, telefon raqamingizni kiriting va guruhga a'zo bo'ling.", reply_markup=MAIN_KEYBOARD)
        return

    today = datetime.now().date()
    last_test_date = user.get("last_test_date")
    if last_test_date:
        last_test_date = datetime.strptime(last_test_date, "%Y-%m-%d").date()
    
    if last_test_date == today and user.get("test_count_today", 0) >= 3:
        text = "Kechirasiz, siz bugun maksimal 3 marta test topshira olasiz. Ertaga qayta urinib ko'ring."
        await query.edit_message_text(text, reply_markup=MAIN_KEYBOARD)
        return
    
    if last_test_date != today:
        user_data[user_id]["test_count_today"] = 0
    
    user_data[user_id]["test_count_today"] += 1
    user_data[user_id]["last_test_date"] = today.strftime("%Y-%m-%d")
    save_data(user_data, USER_DATA_FILE)
    
    questions_list = questions_pool.get("matem", [])
    if not questions_list:
        await query.edit_message_text("Kechirasiz, savollar bazasida savollar topilmadi.", reply_markup=MAIN_KEYBOARD)
        return

    user_questions = []
    for i in range(0, 100, 10):
        group_questions = [q for q in questions_list if i < q.get('id', 0) <= i + 10]
        if group_questions:
            user_questions.append(random.choice(group_questions))
        else:
            logger.warning(f"ID oralig'i {i+1}-{i+10} bo'yicha savol topilmadi.")
            
    if len(user_questions) < 10:
        await query.edit_message_text("Test uchun yetarli savollar topilmadi. Iltimos, ma'muriyat bilan bog'laning.", reply_markup=MAIN_KEYBOARD)
        return
        
    user_data[user_id]["current_test"] = {
        'subject': "matem",
        'score': 0,
        'current_question': 0,
        'questions': user_questions,
        'answers': [],
        'question_message_id': None
    }
    save_data(user_data, USER_DATA_FILE)
    
    await ask_question(update, context)

# Savol so'rash
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_test = user_data.get(user_id, {}).get("current_test")
    
    if not user_test:
        return

    current_q_index = user_test.get('current_question', 0)
    total_q_count = len(user_test['questions'])

    if current_q_index >= total_q_count:
        await finish_test(update, context)
        return
    
    question_data = user_test['questions'][current_q_index]
    
    keyboard = [[InlineKeyboardButton(option, callback_data=f'answer_{i}')] for i, option in enumerate(question_data['options'])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    question_text = f"📝 Savol {current_q_index + 1}/{total_q_count}:\n\n{question_data['question']}"
    
    try:
        if user_test.get('question_message_id'):
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=user_test['question_message_id'],
                text=question_text,
                reply_markup=reply_markup
            )
        else:
            message = await context.bot.send_message(
                chat_id=user_id,
                text=question_text,
                reply_markup=reply_markup
            )
            user_test['question_message_id'] = message.message_id
        
        save_data(user_data, USER_DATA_FILE)
    except BadRequest as e:
        logger.error(f"Savol yuborishda xato: {e}")
        await context.bot.send_message(user_id, "Test jarayonida xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
        await finish_test(update, context)

# Javobni qayta ishlash
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    user_test = user_data.get(user_id, {}).get("current_test")
    if not user_test:
        return

    answer_index = int(query.data.split('_')[1])
    question_data = user_test['questions'][user_test['current_question']]
    
    is_correct = (answer_index == question_data['correct'])
    if is_correct:
        user_test['score'] += 1
    
    user_test['answers'].append({
        'question_id': question_data['id'],
        'user_answer': answer_index,
        'correct_answer': question_data['correct'],
        'is_correct': is_correct,
        'explanation': question_data.get('explanation', "Yechim topilmadi.")
    })
    
    user_test['current_question'] += 1
    save_data(user_data, USER_DATA_FILE)
    
    await ask_question(update, context)

# Testni yakunlash
async def finish_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_test = user_data.get(user_id, {}).get("current_test")
    
    if not user_test:
        return
        
    score = user_test['score']
    total = len(user_test['questions'])
    subject = user_test['subject']
    
    # Natijani saqlash
    results.setdefault(user_id, []).append({
        "score": score,
        "total": total,
        "subject": subject,
        "date": datetime.now().isoformat()
    })
    save_data(results, RESULTS_FILE)
    
    # Noto'g'ri javoblar uchun yechimlarni yig'ish
    wrong_answers_explanations = ""
    for ans in user_test['answers']:
        if not ans['is_correct']:
            original_question = next((q for q in questions_pool.get(subject, []) if q['id'] == ans['question_id']), None)
            if original_question:
                wrong_answers_explanations += (
                    f"❌ **{original_question['question']}**\n"
                    f"To'g'ri javob: {original_question['options'][original_question['correct']]}\n"
                    f"Yechim: {original_question.get('explanation', 'Yechim topilmadi.')}\n\n"
                )

    # Test ma'lumotlarini o'chirish
    if "current_test" in user_data[user_id]:
        del user_data[user_id]["current_test"]
    save_data(user_data, USER_DATA_FILE)
    
    # Natija xabarini tayyorlash
    percentage = (score / total) * 100 if total > 0 else 0
    level = "boshlang'ich"
    if percentage >= 80:
        level = "yuqori"
    elif percentage >= 50:
        level = "o'rta"
    
    course_data = courses.get(subject, {})
    recommended_course = course_data.get("levels", {}).get(level, {})
    
    result_text = (
        f"🎯 Test yakunlandi!\n\n"
        f"📊 *Test natijangiz:*\n"
        f"✅ To'g'ri javoblar: {score}/{total}\n"
        f"📈 Foiz: {percentage:.1f}%\n"
        f"🎯 Sizning darajangiz: *{level.capitalize()}*\n\n"
    )
    
    if wrong_answers_explanations:
        result_text += "*Noto'g'ri javoblaringiz yechimlari:*\n"
        result_text += wrong_answers_explanations

    result_text += (
        f"📚 Sizga tavsiya etilayotgan kurs: *{course_data.get('name', 'Nomalum')}*\n"
        f"🕐 Vaqti: {recommended_course.get('time', 'Malumot kiritilmagan')}\n"
        f"👨‍🏫 O'qituvchi: {recommended_course.get('teacher', 'Malumot kiritilmagan')}\n"
        f"📍 Manzil: {recommended_course.get('location', 'Malumot kiritilmagan')}\n"
        f"💰 Narxi: {recommended_course.get('price', 'Malumot kiritilmagan')}\n\n"
        f"📚 Kitoblar: {recommended_course.get('description', 'Malumot kiritilmagan')}\n\n"
        f"📞 *Ro'yxatdan o'tish uchun: +998507551023*\n"
        f"*@Shoxrux_Ibrohimov*"
    )
    
    try:
        if update.callback_query:
            await update.callback_query.message.reply_text(result_text, reply_markup=MAIN_KEYBOARD, parse_mode='Markdown')
            try:
                await update.callback_query.message.delete()
            except BadRequest:
                pass
        else:
            await context.bot.send_message(
                user_id,
                result_text,
                reply_markup=MAIN_KEYBOARD,
                parse_mode='Markdown'
            )
    except BadRequest as e:
        logger.error(f"Natija xabarini yuborishda xato: {e}")

# Callback querylarni boshqarish
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data.startswith('class_'):
        await handle_class_selection(update, context)
    elif data.startswith('school_'):
        await handle_school_selection(update, context)
    elif data == 'enter_phone' or data == 'share_phone':
        await handle_phone_selection(update, context)
    elif data == 'confirm_group':
        await handle_group_confirmation(update, context)
    elif data == 'teacher_info':
        await show_teacher_info(update, context)
    elif data == 'courses_list':
        await show_courses_info(update, context)
    elif data.startswith('course_info_'):
        await show_course_details(update, context)
    elif data == 'show_results':
        await show_results(update, context)
    elif data == 'start_test':
        await start_test(update, context)
    elif data == 'main_menu':
        await show_main_menu(update, context, str(query.from_user.id))
    elif data == 'admin_users':
        await admin_show_users(update, context)
    elif data == 'admin_results':
        await admin_show_results(update, context)
    elif data == 'admin_broadcast':
        await admin_broadcast_start(update, context)
    elif data == 'admin_cancel_broadcast':
        await admin_cancel_broadcast(update, context)

# Kurslar haqida ma'lumot
async def show_courses_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton(course['name'], callback_data=f"course_info_{key}")] for key, course in courses.items()]
    reply_markup = InlineKeyboardMarkup(keyboard + [[InlineKeyboardButton("🏠 Asosiy menyu", callback_data="main_menu")]])
    
    text = "📚 Bizning kurslarimiz haqida ma'lumot olish uchun quyidagi tugmalardan birini tanlang: kurs o'qituvchisi tel raqami: +998507551023"
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Kurs haqida batafsil ma'lumot
async def show_course_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    course_key = query.data.split("_")[2]
    course_data = courses.get(course_key, {})
    
    if not course_data:
        await query.edit_message_text("Kurs ma'lumoti topilmadi.", reply_markup=MAIN_KEYBOARD)
        return
    
    course_text = f"📚 **{course_data['name']}**\n\n"
    for level, level_data in course_data.get('levels', {}).items():
        course_text += (
            f"🎯 **{level.capitalize()} daraja:**\n"
            f"   🕐 Vaqt: {level_data.get('time', 'Malumot kiritilmagan')}\n"
            f"   👨‍🏫 O'qituvchi: {level_data.get('teacher', 'Malumot kiritilmagan')}\n"
            f"   📍 Manzil: {level_data.get('location', 'Malumot kiritilmagan')}\n"
            f"   💰 Narx: {level_data.get('price', 'Malumot kiritilmagan')}\n\n"
            f"   📚 Kitoblar: {level_data.get('description', 'Malumot kiritilmagan')}\n\n"
        )
    
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kurslar ro'yxati", callback_data="courses_list")]])
    await query.edit_message_text(course_text, reply_markup=reply_markup, parse_mode='Markdown')

# Matnli xabarlarni qayta ishlash (telefon va broadcast uchun)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    waiting_for = user_data[user_id].get("waiting_for")
    
    if waiting_for == "phone":
        phone = update.message.text.strip()
        if phone.startswith('+') and len(phone) >= 12:
            user_data[user_id]["phone"] = phone
            user_data[user_id]["waiting_for"] = None
            save_data(user_data, USER_DATA_FILE)
            await update.message.reply_text(
                f"Raqam saqlandi: {phone}\n\nEndi guruhga a'zo bo'ling!",
                parse_mode='Markdown'
            )
            await handle_group_join(update, context)
        else:
            await update.message.reply_text(
                "Noto'g'ri format. Qayta yozing (masalan: +998901234567):",
                reply_markup=PHONE_KEYBOARD,
                parse_mode='Markdown'
            )
        return
    
    elif waiting_for == "broadcast" and user_id == ADMIN_ID:
        message_text = update.message.text
        sent_count = 0
        failed_count = 0
        for uid in user_data.keys():
            if uid == user_id:
                continue
            try:
                await context.bot.send_message(chat_id=uid, text=message_text, parse_mode='Markdown')
                sent_count += 1
            except Exception as e:
                logger.error(f"Foydalanuvchiga xabar yuborishda xato {uid}: {e}")
                failed_count += 1
        
        user_data[user_id]["waiting_for"] = None
        save_data(user_data, USER_DATA_FILE)
        
        await update.message.reply_text(f"Xabar {sent_count} o'quvchiga yuborildi. Muvaffaqiyatsiz: {failed_count}")
        await show_main_menu(update, context, user_id)
        return
    
    if "current_test" in user_data.get(user_id, {}):
        await context.bot.send_message(user_id, "Iltimos, testni tugatish uchun tugmalardan foydalaning.")
    else:
        await show_main_menu(update, context, user_id)

# Kontakt yuborilganda (Telegram raqami)
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_data[user_id].get("waiting_for") == "phone":
        contact = update.message.contact
        phone = contact.phone_number
        user_data[user_id]["phone"] = phone
        user_data[user_id]["waiting_for"] = None
        save_data(user_data, USER_DATA_FILE)
        await update.message.reply_text(
            f"Raqam saqlandi: {phone}\n\nEndi guruhga a'zo bo'ling!",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        await handle_group_join(update, context)

# Rasmli xabarlar uchun (broadcast uchun)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    waiting_for = user_data[user_id].get("waiting_for")
    
    if waiting_for == "broadcast" and user_id == ADMIN_ID:
        photo = update.message.photo[-1]
        caption = update.message.caption or ""
        sent_count = 0
        failed_count = 0
        for uid in user_data.keys():
            if uid == user_id:
                continue
            try:
                await context.bot.send_photo(chat_id=uid, photo=photo.file_id, caption=caption, parse_mode='Markdown')
                sent_count += 1
            except Exception as e:
                logger.error(f"Foydalanuvchiga rasm yuborishda xato {uid}: {e}")
                failed_count += 1
        
        user_data[user_id]["waiting_for"] = None
        save_data(user_data, USER_DATA_FILE)
        
        await update.message.reply_text(f"Rasmli xabar {sent_count} o'quvchiga yuborildi. Muvaffaqiyatsiz: {failed_count}")
        await show_main_menu(update, context, user_id)
        return

# Asosiy funksiya
def main():
    logger.info("Bot ishga tushirildi.")
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    
    application.run_polling()

if __name__ == "__main__":
    main()
