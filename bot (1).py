import telebot
from telebot import types
import sqlite3
import random
import os
from datetime import datetime, timedelta

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set!")

ADMIN_IDS = {int(os.environ.get("ADMIN_ID", "123456789")), 5073782575}

bot = telebot.TeleBot(BOT_TOKEN)

TG_CHANNEL_URL = "https://t.me/kuklin_D&quot;
TG_CHANNEL_ID = "@kuklin_D"
KICK_CHANNEL = "https://kick.com/kuklin666&quot;

user_states = {}

def init_db():
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, 
                  tg_done INTEGER DEFAULT 0, kick_done INTEGER DEFAULT 0, 
                  vk_done INTEGER DEFAULT 0, vk_link TEXT,
                  kick_username TEXT, joined INTEGER DEFAULT 0)""")
    for stmt in [
        "ALTER TABLE users ADD COLUMN vk_link TEXT",
        "ALTER TABLE users ADD COLUMN kick_username TEXT",
        "ALTER TABLE users ADD COLUMN ticket_number INTEGER",
    ]:
        try:
            c.execute(stmt)
        except Exception:
            pass
    conn.commit()
    conn.close()

def check_tg_subscription(user_id):
    try:
        member = bot.get_chat_member(TG_CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator", "restricted")
    except Exception:
        return False

def get_user_status(user_id):
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute(
        "SELECT tg_done, kick_done, vk_done FROM users WHERE user_id=?", (user_id,)
    )
    result = c.fetchone()
    conn.close()
    return result or (0, 0, 0)

def all_tasks_completed(user_id):
    tg, kick, vk = get_user_status(user_id)
    return bool(tg and kick and vk)

def get_tasks_markup(tg_done=False, kick_done=False, vk_done=False):
    markup = types.InlineKeyboardMarkup(row_width=1)
    tg_label = f"{'✅' if tg_done else '📱'} TG канал{' — подписан' if tg_done else ''}"
    vk_label = (
        f"{'✅' if vk_done else '🔄'} Репост ВК{' — отправлен' if vk_done else ''}"
    )

    btn1 = types.InlineKeyboardButton(tg_label, url=TG_CHANNEL_URL)
    markup.add(btn1)

    if not kick_done:
        btn_kick = types.InlineKeyboardButton(
            "🎥 Kick канал — подписаться", callback_data="kick_confirm"
        )
        markup.add(btn_kick)
    else:
        btn_kick_done = types.InlineKeyboardButton(
            "✅ Kick канал — подписан", callback_data="kick_already"
        )
        markup.add(btn_kick_done)

    btn3 = types.InlineKeyboardButton(vk_label, callback_data="vk_repost")
    btn4 = types.InlineKeyboardButton(
        "🔍 Проверить выполнение", callback_data="check_tasks"
    )
    markup.add(btn3)
    markup.add(btn4)
    return markup

def get_tasks_text(tg_done=False, kick_done=False, vk_done=False):
    return f"""📋 ПРАВИЛА РОЗЫГРЫША:

{"✅" if tg_done else "1️⃣"} Подписаться на Telegram канал
{"✅" if kick_done else "2️⃣"} Подписаться на Kick канал
{"✅" if vk_done else "3️⃣"} Сделать репост ВК (нажми кнопку ниже и пришли ссылку)

{"✅ Все задания выполнены! Нажми проверку." if (tg_done and kick_done and vk_done) else '⬇️ Выполни задания, затем нажми "Проверить выполнение"'}"""

@bot.message_handler(commands=["start"])
def start_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    user_states.pop(user_id, None)

    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    c.execute(
        "INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username)
    )
    conn.commit()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(
        "🎉 Участвовать в розыгрыше", callback_data="participate"
    )
    markup.add(btn)
    text = "Привет👋\n🎉 РОЗЫГРЫШ 5000₽!\n\nВыполни 3 задания и получи шанс выиграть 5000 рублей!"


bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_kick")
def receive_kick_username(message):
    user_id = message.from_user.id
    kick_username = message.text.strip().lstrip("@")

    if " " in kick_username or len(kick_username) < 2:
        bot.reply_to(
            message,
            "❌ Неверный формат. Пришли только свой никнейм на Kick, например: ivan123",
        )
        return

    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute(
        "UPDATE users SET kick_done=1, kick_username=? WHERE user_id=?",
        (kick_username, user_id),
    )
    conn.commit()
    conn.close()

    user_states.pop(user_id, None)

    tg_done, _, vk_done = get_user_status(user_id)
    markup = get_tasks_markup(bool(tg_done), True, bool(vk_done))
    bot.send_message(
        message.chat.id,
        f"✅ Kick никнейм *{kick_username}* сохранён!\n\n"
        + get_tasks_text(bool(tg_done), True, bool(vk_done)),
        parse_mode="Markdown",
        reply_markup=markup,
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_vk")
def receive_vk_link(message):
    user_id = message.from_user.id
    link = message.text.strip()

    if "vk.com" not in link and "vkontakte.ru" not in link and "vk.ru" not in link:
        bot.reply_to(
            message,
            "❌ Это не похоже на ссылку ВКонтакте. Пришли ссылку на свою запись с репостом (например: https://vk.ru/... или https://vk.com/...)&quot;,
        )
        return

    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("UPDATE users SET vk_done=1, vk_link=? WHERE user_id=?", (link, user_id))
    conn.commit()
    conn.close()

    user_states.pop(user_id, None)

    tg_done = check_tg_subscription(user_id)
    if tg_done:
        conn = sqlite3.connect("giveaway.db")
        c = conn.cursor()
        c.execute("UPDATE users SET tg_done=1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()

    _, kick_done, vk_done = get_user_status(user_id)
    tg_s, _, _ = get_user_status(user_id)

    markup = get_tasks_markup(
        tg_done=bool(tg_s), kick_done=bool(kick_done), vk_done=True
    )
    bot.send_message(
        message.chat.id,
        "✅ Ссылка на репост принята!\n\n"
        + get_tasks_text(tg_done=bool(tg_s), kick_done=bool(kick_done), vk_done=True),
        reply_markup=markup,
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    username = call.from_user.username or call.from_user.first_name

    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username),
    )
    conn.commit()
    conn.close()

    if call.data == "participate":
        tg_done, kick_done, vk_done = get_user_status(user_id)
        markup = get_tasks_markup(bool(tg_done), bool(kick_done), bool(vk_done))
        bot.edit_message_text(
            get_tasks_text(bool(tg_done), bool(kick_done), bool(vk_done)),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
        )

    elif call.data == "kick_confirm":
        user_states[user_id] = "waiting_kick"
        bot.answer_callback_query(call.id)
        markup_kick = types.InlineKeyboardMarkup()
        markup_kick.add(
            types.InlineKeyboardButton("🎥 Открыть Kick канал", url=KICK_CHANNEL)
        )
        bot.send_message(
            call.message.chat.id,
            "🎥 *Подписка на Kick*\n\n"
            "1. Нажми кнопку ниже и подпишись на канал\n"
            "2. Вернись сюда и пришли свой *никнейм на Kick*\n\n"
            "📎 Например: `ivan123`",
            parse_mode="Markdown",
            reply_markup=markup_kick,
        )

    elif call.data == "kick_already":
        bot.answer_callback_query(call.id, "✅ Уже засчитано!")

    elif call.data == "vk_repost":
        user_states[user_id] =


"waiting_vk"
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🔄 *Репост ВКонтакте*\n\n"
            "1. Сделай репост нашей записи на свою страницу ВКонтакте\n"
            "2. Открой свою запись с репостом\n"
            "3. Скопируй ссылку и отправь её сюда\n\n"
            "📎 Пришли ссылку вида: https://vk.ru/... или https://vk.com/...&quot;,
            parse_mode="Markdown",
        )

    elif call.data == "check_tasks":
        tg_done_db, kick_done_db, vk_done_db = get_user_status(user_id)

        tg_done = check_tg_subscription(user_id)
        conn = sqlite3.connect("giveaway.db")
        c = conn.cursor()
        if tg_done:
            c.execute("UPDATE users SET tg_done=1 WHERE user_id=?", (user_id,))
        else:
            c.execute(
                "UPDATE users SET tg_done=0, joined=0 WHERE user_id=?", (user_id,)
            )
        conn.commit()
        conn.close()

        kick_done = bool(kick_done_db)
        vk_done = bool(vk_done_db)

        if tg_done and kick_done and vk_done:
            conn = sqlite3.connect("giveaway.db")
            c = conn.cursor()
            c.execute("BEGIN IMMEDIATE")
            c.execute("SELECT ticket_number FROM users WHERE user_id=?", (user_id,))
            row = c.fetchone()
            ticket = row[0] if row and row[0] else None
            if not ticket:
                c.execute("SELECT COALESCE(MAX(ticket_number), 0) FROM users")
                ticket = c.fetchone()[0] + 1
                c.execute(
                    "UPDATE users SET tg_done=1, joined=1, ticket_number=? WHERE user_id=?",
                    (ticket, user_id),
                )
            else:
                c.execute(
                    "UPDATE users SET tg_done=1, joined=1 WHERE user_id=?", (user_id,)
                )
            conn.commit()
            conn.close()

            text = f"""🎉 Все задания выполнены! Вы участвуете в розыгрыше!

💰 Приз: 5000 рублей
🏆 Победителей: 1
🎫 Ваш билет: #{ticket}

📅 Начало розыгрыша: 15.03.2026
📅 Окончание: 30.03.2026 в 20:00 по Мск

Список участников доступен администратору."""
            bot.answer_callback_query(call.id, "✅ Вы в розыгрыше!")
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
        else:
            missing = []
            if not tg_done:
                missing.append("• Подписка на Telegram канал")
            if not kick_done:
                missing.append("• Подписка на Kick канал")
            if not vk_done:
                missing.append("• Репост ВКонтакте")

            bot.answer_callback_query(call.id, "❌ Не все задания выполнены!")
            markup = get_tasks_markup(tg_done, kick_done, vk_done)
            bot.edit_message_text(
                get_tasks_text(tg_done, kick_done, vk_done)
                + "\n\n❌ Не выполнено:\n"
                + "\n".join(missing),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
            )

    elif call.data == "admin_participants":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "Только для админа!")
            return
        conn = sqlite3.connect("giveaway.db")
        c = conn.cursor()
        c.execute(
            "SELECT user_id, username, kick_username, vk_link, ticket_number FROM users WHERE joined=1 ORDER BY ticket_number"
        )
        participants = c.fetchall()
        conn.close()
        if participants:
            text = "📋 УЧАСТНИКИ РОЗЫГРЫША:\n\n"
            for uid, uname, kick_uname, vk_link, ticket in participants:
                text += f"🎫 #{ticket} — {uname} (ID: {uid})\n"
                if kick_uname:
                    text += f"   🎥 Kick: {kick_uname}\n"
                if vk_link:
                    text += f"   🔄 VK: {vk_link}\n"
                text += "\n"
            text += f"👥 Всего: {len(participants)} чел."
        else:
            text = "❌ Нет участников"
call.id – Domain name for sale
call.id


bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text)

    elif call.data == "admin_restart":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "Только для админа!")
            return
        bot.answer_callback_query(call.id, "🔄 Перезапуск...")
        bot.send_message(call.message.chat.id, "🔄 Бот перезапускается...")
        bot.stop_polling()

    elif call.data == "randomize":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "Только для админа!")
            return
        conn = sqlite3.connect("giveaway.db")
        c = conn.cursor()
        c.execute("SELECT user_id, username FROM users WHERE joined=1")
        all_joined = c.fetchall()

        valid = []
        removed = []
        for uid, uname in all_joined:
            if check_tg_subscription(uid):
                valid.append((uid, uname))
            else:
                c.execute(
                    "UPDATE users SET tg_done=0, joined=0 WHERE user_id=?", (uid,)
                )
                removed.append(uname)
        conn.commit()
        conn.close()

        if valid:
            winner = random.choice(valid)
            extra = f"\n⚠️ Исключены за отписку: {', '.join(removed)}" if removed else ""
            text = f"""🎉 ПОБЕДИТЕЛЬ РОЗЫГРЫША! 🎉

🏆 {winner[1]} (ID: {winner[0]})
💰 Получает 5000 рублей!

Всего участников: {len(valid)}{extra}"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "Нет участников!")

@bot.message_handler(commands=["check"])
def check_tasks(message):
    user_id = message.from_user.id
    tg_done_db, kick_done_db, vk_done_db = get_user_status(user_id)

    tg_done = check_tg_subscription(user_id)
    if tg_done:
        conn = sqlite3.connect("giveaway.db")
        c = conn.cursor()
        c.execute("UPDATE users SET tg_done=1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
    else:
        tg_done = bool(tg_done_db)

    kick_done = bool(kick_done_db)
    vk_done = bool(vk_done_db)

    if tg_done and kick_done and vk_done:
        conn = sqlite3.connect("giveaway.db")
        c = conn.cursor()
        c.execute("UPDATE users SET joined=1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ Все задания выполнены! Вы участвуете в розыгрыше!")
    else:
        missing = []
        if not tg_done:
            missing.append("• Подписка на Telegram канал")
        if not kick_done:
            missing.append("• Подписка на Kick канал")
        if not vk_done:
            missing.append("• Репост ВКонтакте (нажми /start и выбери задание)")
        bot.reply_to(message, "❌ Не все задания выполнены:\n" + "\n".join(missing))

@bot.message_handler(commands=["participants"])
def show_participants(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute(
        "SELECT user_id, username, kick_username, vk_link, ticket_number FROM users WHERE joined=1 ORDER BY ticket_number"
    )
    participants = c.fetchall()
    conn.close()
    if participants:
        text = "📋 УЧАСТНИКИ РОЗЫГРЫША:\n\n"
        for uid, uname, kick_uname, vk_link, ticket in participants:
            text += f"🎫 #{ticket} — {uname} (ID: {uid})\n"
            if kick_uname:
                text += f"   🎥 Kick: {kick_uname}\n"
            if vk_link:
                text += f"   🔄 VK: {vk_link}\n"
            text += "\n"
        text += f"👥 Всего: {len(participants)} чел."
        bot.reply_to(message, text)
    else:
        bot.reply_to(message, "❌ Нет участников")

@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE joined=1")
    count = c.fetchone()[0]
    conn.close()

    markup =
call.id – Domain name for sale
call.id


types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            f"🎲 Запустить рандомайзер ({count} участн.)", callback_data="randomize"
        ),
        types.InlineKeyboardButton(
            "📋 Список участников", callback_data="admin_participants"
        ),
        types.InlineKeyboardButton(
            "🔄 Перезапустить бота", callback_data="admin_restart"
        ),
    )
    bot.reply_to(
        message, "⚙️ *Панель администратора*", parse_mode="Markdown", reply_markup=markup
    )

@bot.message_handler(commands=["restart"])
def restart_bot(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    bot.reply_to(message, "🔄 Перезапуск бота...")
    bot.stop_polling()

@bot.message_handler(commands=["winner"])
def pick_winner(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("SELECT user_id, username FROM users WHERE joined=1")
    all_joined = c.fetchall()

    valid = []
    removed = []
    for uid, uname in all_joined:
        if check_tg_subscription(uid):
            valid.append((uid, uname))
        else:
            c.execute("UPDATE users SET tg_done=0, joined=0 WHERE user_id=?", (uid,))
            removed.append(uname)
    conn.commit()
    conn.close()

    if valid:
        winner = random.choice(valid)
        extra = f"\n⚠️ Исключены за отписку: {', '.join(removed)}" if removed else ""
        bot.reply_to(
            message,
            f"🎉 ПОБЕДИТЕЛЬ: {winner[1]} (ID: {winner[0]})\nВсего участников: {len(valid)}{extra}",
        )
    else:
        bot.reply_to(message, "Нет участников для розыгрыша.")

if __name__ == "__main__":
    init_db()
    while True:
        try:
            print("Бот запущен...")
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Ошибка: {e}. Перезапуск через 5 секунд...")
            import time

            time.sleep(5)
