import os
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import requests
import json
import sqlite3
import time
import threading
from datetime import datetime, timedelta
import hashlib
import string

TOKEN = os.environ["VK_TOKEN"]
GROUP_ID = int(os.environ["VK_GROUP_ID"])

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   name TEXT, 
                   city TEXT, 
                   status TEXT, 
                   reg_date TEXT, 
                   rank INTEGER DEFAULT 1,
                   stars INTEGER DEFAULT 0,
                   age INTEGER DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS blacklist
                  (owner_id INTEGER, 
                   blocked_id INTEGER)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS templates
                  (user_id INTEGER, 
                   name TEXT, 
                   content TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS timers
                  (user_id INTEGER, 
                   chat_id INTEGER, 
                   message TEXT, 
                   trigger_time INTEGER)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS triggers
                  (user_id INTEGER, 
                   keyword TEXT, 
                   response TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS marriages
                  (user1 INTEGER, 
                   user2 INTEGER, 
                   date TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS likes
                  (user_id INTEGER, 
                   post_id INTEGER, 
                   type TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS stickers
                  (user_id INTEGER, 
                   sticker_id TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS quotes
                  (text TEXT, 
                   author TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS poems
                  (title TEXT, 
                   content TEXT, 
                   author TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS polls
                  (poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   creator_id INTEGER,
                   question TEXT,
                   options TEXT,
                   votes TEXT)''')

conn.commit()

quotes_db = [
    ("Будь собой", "Народная"),
    ("Жизнь прекрасна", "Кто-то мудрый"),
    ("Учиться, учиться и еще раз учиться", "Ленин")
]

poems_db = [
    ("У лукоморья дуб зеленый", "Златая цепь на дубе том...", "Пушкин"),
    ("Я помню чудное мгновенье", "Передо мной явилась ты...", "Пушкин")
]

horoscopes = [
    "Сегодня отличный день для новых начинаний",
    "Будьте осторожны в финансовых вопросах",
    "Любовь ждет вас за углом",
    "Успех в работе гарантирован",
    "Время для отдыха и релаксации"
]

weather_cache = {}
currency_rates = {"USD": 75, "EUR": 85, "RUB": 1}

def get_user_rank(user_id):
    cursor.execute("SELECT rank FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 1

def add_stars(user_id, stars):
    cursor.execute("UPDATE users SET stars = stars + ? WHERE user_id = ?", (stars, user_id))
    conn.commit()

def get_user_info(user_id):
    cursor.execute("SELECT name, city, status, reg_date, rank, stars FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def register_user(user_id, name):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, name, reg_date, rank) VALUES (?, ?, ?, 1)",
                   (user_id, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def send_message(peer_id, text, keyboard=None):
    params = {"peer_id": peer_id, "message": text, "random_id": random.randint(1, 999999999)}
    if keyboard:
        params["keyboard"] = json.dumps(keyboard)
    vk.messages.send(**params)

def get_weather(city):
    if city in weather_cache and time.time() - weather_cache[city]["time"] < 3600:
        return weather_cache[city]["data"]
    try:
        api_key = os.environ.get("OPENWEATHER_API_KEY", "")
        response = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=ru")
        data = response.json()
        if data["cod"] == 200:
            weather_info = f"Погода в {city}: {data['weather'][0]['description']}, температура: {data['main']['temp']}°C, влажность: {data['main']['humidity']}%"
            weather_cache[city] = {"data": weather_info, "time": time.time()}
            return weather_info
        return "Город не найден"
    except:
        return "Ошибка получения погоды"

def search_music(query):
    return f"Поиск музыки: {query}\n🎵 Найденные треки:\n1. Пример трека - Исполнитель\n2. Другой трек - Артист"

def generate_password(length=12):
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(chars) for _ in range(length))

def convert_currency(amount, from_curr, to_curr):
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()
    if from_curr in currency_rates and to_curr in currency_rates:
        result = amount * (currency_rates[to_curr] / currency_rates[from_curr])
        return round(result, 2)
    return None

def translate_text(text, target_lang):
    return f"[Перевод на {target_lang}]: {text}"

def game_rps(user_choice, user_id):
    choices = ["камень", "ножницы", "бумага"]
    bot_choice = random.choice(choices)
    if user_choice == bot_choice:
        result = "Ничья!"
        stars = 1
    elif (user_choice == "камень" and bot_choice == "ножницы") or \
         (user_choice == "ножницы" and bot_choice == "бумага") or \
         (user_choice == "бумага" and bot_choice == "камень"):
        result = "Вы победили!"
        stars = 5
    else:
        result = "Вы проиграли!"
        stars = 0
    add_stars(user_id, stars)
    return f"{result}\nБот выбрал: {bot_choice}\nВы получили {stars} ⭐"

def create_meme(template, top_text, bottom_text):
    return f"Мем создан: {template}\nТекст: {top_text} | {bottom_text}"

def check_timers():
    while True:
        current_time = int(time.time())
        cursor.execute("SELECT user_id, chat_id, message FROM timers WHERE trigger_time <= ?", (current_time,))
        timers = cursor.fetchall()
        for timer in timers:
            send_message(timer[1], f"🔔 Напоминание: {timer[2]}")
            cursor.execute("DELETE FROM timers WHERE user_id = ? AND trigger_time = ?", (timer[0], current_time))
            conn.commit()
        time.sleep(30)

threading.Thread(target=check_timers, daemon=True).start()

for quote in quotes_db:
    cursor.execute("INSERT OR IGNORE INTO quotes (text, author) VALUES (?, ?)", quote)
for poem in poems_db:
    cursor.execute("INSERT OR IGNORE INTO poems (title, content, author) VALUES (?, ?, ?)", poem)
conn.commit()

print("Бот запущен, слушаю события...")

while True:
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                msg = event.message.text.lower().strip()
                peer_id = event.message.peer_id
                user_id = event.message.from_id
                user_name = event.message.from_id

                try:
                    user_info = vk.users.get(user_ids=user_id, fields="city, sex, bdate")[0]
                    user_name = user_info.get("first_name", "Пользователь")
                    city = user_info.get("city", {}).get("title", "Не указан")
                    bdate = user_info.get("bdate", "")
                    age = 0
                    if bdate and len(bdate.split('.')) == 3:
                        birth_year = int(bdate.split('.')[2])
                        age = datetime.now().year - birth_year
                    register_user(user_id, user_name)
                    cursor.execute("UPDATE users SET city = ?, age = ? WHERE user_id = ?", (city, age, user_id))
                    conn.commit()
                except:
                    register_user(user_id, str(user_id))

                rank = get_user_rank(user_id)

                cursor.execute("SELECT 1 FROM blacklist WHERE owner_id = ? AND blocked_id = ?", (user_id, peer_id))
                if cursor.fetchone():
                    continue

                if msg == "профиль":
                    user_data = get_user_info(user_id)
                    if user_data:
                        send_message(peer_id, f"👤 Профиль:\nИмя: {user_data[0]}\nГород: {user_data[1]}\nСтатус: {user_data[2] or 'Нет'}\nДата регистрации: {user_data[3]}\nРанг: {user_data[4]}\n⭐ Звёздочки: {user_data[5]}")

                elif msg.startswith("погода "):
                    city = msg.replace("погода ", "").strip()
                    send_message(peer_id, get_weather(city))

                elif msg.startswith("поиск песни "):
                    query = msg.replace("поиск песни ", "").strip()
                    send_message(peer_id, search_music(query))

                elif msg == "цитата":
                    quote = random.choice(quotes_db)
                    send_message(peer_id, f"📖 {quote[0]}\n— {quote[1]}")

                elif msg == "стих":
                    poem = random.choice(poems_db)
                    send_message(peer_id, f"📜 {poem[0]}\n{poem[1]}\n— {poem[2]}")

                elif msg == "гороскоп":
                    send_message(peer_id, f"🔮 {random.choice(horoscopes)}")

                elif msg.startswith("шаблон сохранить "):
                    parts = msg.replace("шаблон сохранить ", "").split(" ", 1)
                    if len(parts) == 2:
                        template_name, template_content = parts[0], parts[1]
                        cursor.execute("INSERT OR REPLACE INTO templates (user_id, name, content) VALUES (?, ?, ?)",
                                       (user_id, template_name, template_content))
                        conn.commit()
                        send_message(peer_id, f"✅ Шаблон '{template_name}' сохранён")

                elif msg.startswith("шаблон "):
                    template_name = msg.replace("шаблон ", "").strip()
                    cursor.execute("SELECT content FROM templates WHERE user_id = ? AND name = ?", (user_id, template_name))
                    template = cursor.fetchone()
                    if template:
                        send_message(peer_id, template[0])
                    else:
                        send_message(peer_id, "❌ Шаблон не найден")

                elif msg == "шаблоны":
                    cursor.execute("SELECT name FROM templates WHERE user_id = ?", (user_id,))
                    templates = cursor.fetchall()
                    if templates:
                        template_list = "\n".join([t[0] for t in templates])
                        send_message(peer_id, f"📋 Ваши шаблоны:\n{template_list}")
                    else:
                        send_message(peer_id, "У вас нет сохранённых шаблонов")

                elif msg.startswith("чс добавить "):
                    if rank >= 3:
                        try:
                            blocked_id = int(msg.replace("чс добавить ", "").strip())
                            cursor.execute("INSERT INTO blacklist (owner_id, blocked_id) VALUES (?, ?)", (user_id, blocked_id))
                            conn.commit()
                            send_message(peer_id, f"🚫 Пользователь {blocked_id} добавлен в ЧС")
                        except:
                            send_message(peer_id, "Ошибка: укажите ID пользователя")
                    else:
                        send_message(peer_id, "Недостаточно прав")

                elif msg.startswith("чс удалить "):
                    if rank >= 3:
                        try:
                            blocked_id = int(msg.replace("чс удалить ", "").strip())
                            cursor.execute("DELETE FROM blacklist WHERE owner_id = ? AND blocked_id = ?", (user_id, blocked_id))
                            conn.commit()
                            send_message(peer_id, f"✅ Пользователь {blocked_id} удалён из ЧС")
                        except:
                            send_message(peer_id, "Ошибка: укажите ID пользователя")
                    else:
                        send_message(peer_id, "Недостаточно прав")

                elif msg == "чс список":
                    cursor.execute("SELECT blocked_id FROM blacklist WHERE owner_id = ?", (user_id,))
                    blacklist = cursor.fetchall()
                    if blacklist:
                        bl_list = "\n".join([str(b[0]) for b in blacklist])
                        send_message(peer_id, f"🚫 Ваш чёрный список:\n{bl_list}")
                    else:
                        send_message(peer_id, "Чёрный список пуст")

                elif msg.startswith("лайк "):
                    parts = msg.replace("лайк ", "").split()
                    if len(parts) >= 1:
                        post_id = parts[0]
                        cursor.execute("INSERT INTO likes (user_id, post_id, type) VALUES (?, ?, 'like')", (user_id, post_id))
                        conn.commit()
                        send_message(peer_id, f"❤️ Вы поставили лайк посту {post_id}")

                elif msg.startswith("дизлайк "):
                    parts = msg.replace("дизлайк ", "").split()
                    if len(parts) >= 1:
                        post_id = parts[0]
                        cursor.execute("DELETE FROM likes WHERE user_id = ? AND post_id = ?", (user_id, post_id))
                        conn.commit()
                        send_message(peer_id, f"💔 Вы убрали лайк с поста {post_id}")

                elif msg.startswith("таймер "):
                    parts = msg.replace("таймер ", "").split(" ", 1)
                    if len(parts) == 2:
                        try:
                            minutes = int(parts[0])
                            message_text = parts[1]
                            trigger_time = int(time.time()) + (minutes * 60)
                            cursor.execute("INSERT INTO timers (user_id, chat_id, message, trigger_time) VALUES (?, ?, ?, ?)",
                                           (user_id, peer_id, message_text, trigger_time))
                            conn.commit()
                            send_message(peer_id, f"⏰ Таймер на {minutes} минут установлен")
                        except:
                            send_message(peer_id, "Ошибка: таймер минут 'текст'")
                    else:
                        send_message(peer_id, "Пример: таймер 10 Купить хлеб")

                elif msg.startswith("триггер добавить "):
                    if rank >= 3:
                        parts = msg.replace("триггер добавить ", "").split(" -> ")
                        if len(parts) == 2:
                            keyword, response = parts[0], parts[1]
                            cursor.execute("INSERT INTO triggers (user_id, keyword, response) VALUES (?, ?, ?)", (user_id, keyword, response))
                            conn.commit()
                            send_message(peer_id, f"✅ Триггер '{keyword}' добавлен")
                        else:
                            send_message(peer_id, "Формат: триггер добавить ключевое слово -> ответ")
                    else:
                        send_message(peer_id, "Недостаточно прав (нужен ранг 3+)")

                elif msg == "кнб камень":
                    send_message(peer_id, game_rps("камень", user_id))
                elif msg == "кнб ножницы":
                    send_message(peer_id, game_rps("ножницы", user_id))
                elif msg == "кнб бумага":
                    send_message(peer_id, game_rps("бумага", user_id))

                elif msg.startswith("брак "):
                    parts = msg.replace("брак ", "").split()
                    if len(parts) == 1:
                        try:
                            partner_id = int(parts[0])
                            cursor.execute("SELECT * FROM marriages WHERE user1 = ? AND user2 = ?", (user_id, partner_id))
                            if not cursor.fetchone():
                                cursor.execute("INSERT INTO marriages (user1, user2, date) VALUES (?, ?, ?)",
                                               (user_id, partner_id, datetime.now().strftime("%Y-%m-%d")))
                                conn.commit()
                                send_message(peer_id, f"💍 Брак заключён между {user_id} и {partner_id}")
                            else:
                                send_message(peer_id, "Брак уже существует")
                        except:
                            send_message(peer_id, "Укажите ID партнёра")
                    else:
                        send_message(peer_id, "Пример: брак 123456789")

                elif msg.startswith("развод "):
                    parts = msg.replace("развод ", "").split()
                    if len(parts) == 1:
                        try:
                            partner_id = int(parts[0])
                            cursor.execute("DELETE FROM marriages WHERE (user1 = ? AND user2 = ?) OR (user1 = ? AND user2 = ?)",
                                           (user_id, partner_id, partner_id, user_id))
                            conn.commit()
                            send_message(peer_id, "💔 Брак расторгнут")
                        except:
                            send_message(peer_id, "Ошибка при разводе")
                    else:
                        send_message(peer_id, "Пример: развод 123456789")

                elif msg == "браки":
                    cursor.execute("SELECT user1, user2, date FROM marriages")
                    marriages = cursor.fetchall()
                    if marriages:
                        mar_list = "\n".join([f"{m[0]} + {m[1]} ({m[2]})" for m in marriages])
                        send_message(peer_id, f"💒 Пары:\n{mar_list}")
                    else:
                        send_message(peer_id, "Браков пока нет")

                elif msg.startswith("пароль"):
                    length = 12
                    if msg.startswith("пароль "):
                        try:
                            length = int(msg.replace("пароль ", "").strip())
                            length = max(6, min(32, length))
                        except:
                            pass
                    send_message(peer_id, f"🔐 Сгенерированный пароль: {generate_password(length)}")

                elif msg.startswith("конверт "):
                    parts = msg.replace("конверт ", "").split()
                    if len(parts) == 3:
                        try:
                            amount = float(parts[0])
                            from_curr = parts[1].upper()
                            to_curr = parts[2].upper()
                            result = convert_currency(amount, from_curr, to_curr)
                            if result:
                                send_message(peer_id, f"💰 {amount} {from_curr} = {result} {to_curr}")
                            else:
                                send_message(peer_id, "Неверная валюта. Доступны: USD, EUR, RUB")
                        except:
                            send_message(peer_id, "Ошибка: конверт 100 USD EUR")
                    else:
                        send_message(peer_id, "Пример: конверт 100 USD EUR")

                elif msg.startswith("перевод "):
                    parts = msg.replace("перевод ", "").split(" ", 1)
                    if len(parts) == 2:
                        lang, text = parts[0], parts[1]
                        send_message(peer_id, translate_text(text, lang))

                elif msg.startswith("мем "):
                    parts = msg.replace("мем ", "").split(" | ")
                    if len(parts) == 2:
                        top_text, bottom_text = parts[0], parts[1]
                        send_message(peer_id, create_meme("шаблон", top_text, bottom_text))

                elif msg.startswith("опрос "):
                    if rank >= 3:
                        parts = msg.replace("опрос ", "").split(" | ")
                        if len(parts) >= 2:
                            question = parts[0]
                            options = parts[1:]
                            options_str = "|".join(options)
                            votes_str = "0" * len(options)
                            cursor.execute("INSERT INTO polls (creator_id, question, options, votes) VALUES (?, ?, ?, ?)",
                                           (user_id, question, options_str, votes_str))
                            poll_id = cursor.lastrowid
                            poll_text = f"📊 ОПРОС #{poll_id}\n{question}\n\n"
                            for i, opt in enumerate(options, 1):
                                poll_text += f"{i}. {opt}\n"
                            poll_text += f"\nГолосуйте: опрос голос #{poll_id} [номер]"
                            send_message(peer_id, poll_text)

                elif msg.startswith("опрос голос "):
                    parts = msg.replace("опрос голос ", "").split()
                    if len(parts) == 2:
                        try:
                            poll_id = int(parts[0])
                            option_num = int(parts[1]) - 1
                            cursor.execute("SELECT options, votes FROM polls WHERE poll_id = ?", (poll_id,))
                            result = cursor.fetchone()
                            if result:
                                options, votes = result[0].split("|"), list(result[1])
                                if 0 <= option_num < len(options):
                                    votes[option_num] = str(int(votes[option_num]) + 1)
                                    new_votes = "".join(votes)
                                    cursor.execute("UPDATE polls SET votes = ? WHERE poll_id = ?", (new_votes, poll_id))
                                    conn.commit()
                                    send_message(peer_id, f"✅ Ваш голос за {options[option_num]} принят")
                                else:
                                    send_message(peer_id, "Неверный номер варианта")
                        except:
                            send_message(peer_id, "Ошибка: опрос голос #ID номер")

                elif msg == "помощь" or msg == "команды":
                    help_text = """🤖 Доступные команды:

📌 Основные:
профиль - информация о вас
погода [город] - узнать погоду
поиск песни [запрос] - найти музыку
цитата - случайная цитата
стих - случайный стих
гороскоп - предсказание

📝 Шаблоны:
шаблон сохранить [название] [текст]
шаблон [название] - использовать
шаблоны - список

🚫 Чёрный список (ранг 3+):
чс добавить [id] - добавить в ЧС
чс удалить [id] - удалить из ЧС
чс список - показать ЧС

❤️ Лайки:
лайк [id поста]
дизлайк [id поста]

⏰ Таймеры:
таймер [минуты] [напоминание]

🎮 Игры:
кнб камень/ножницы/бумага - игра, начисляет ⭐

💍 Браки:
брак [id] - жениться
развод [id] - развестись
браки - список всех пар

🔧 Другие:
пароль [длина] - генератор пароля
конверт [сумма] [из] [в] - конвертер валют
перевод [язык] [текст] - переводчик
мем [верхний текст] | [нижний текст]
опрос [вопрос] | [вариант1] | [вариант2]...
опрос голос [#ID] [номер]

⭐ Звёздочки начисляются за КНБ и активность!"""
                    send_message(peer_id, help_text)

                for word, response in [("привет", "Привет! 👋"), ("как дела", "Отлично! А у тебя?"), ("спасибо", "Пожалуйста! 🌟")]:
                    if word in msg:
                        send_message(peer_id, response)
                        break

                cursor.execute("SELECT response FROM triggers WHERE keyword = ?", (msg,))
                trigger = cursor.fetchone()
                if trigger:
                    send_message(peer_id, trigger[0])

    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(1)
