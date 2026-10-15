import asyncio
import os
from datetime import datetime, timedelta, date, timezone
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# Токен бота (читает из переменных Render или подставляет твой запасной)
TOKEN = os.environ.get("BOT_TOKEN", "ТОКЕН_ТВОЕГО_БОТА")

bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# Московский часовой пояс (UTC+3)
MSK_TZ = timezone(timedelta(hours=3))

def get_moscow_now() -> datetime:
    return datetime.now(MSK_TZ)

class UserState(StatesGroup):
    waiting_for_group = State()
    main_menu = State()

SCHEDULE_URL = "https://lk.gubkin.ru/schedule/"

WARNING_TEXT = (
    "⚠️ <b>Важное уведомление:</b>\n"
    "Расписание в боте составлено по данным от <b>15 октября 2026 г.</b> "
    "В течение семестра данные могут меняться, поэтому на всякий случай "
    "проверяйте актуальное расписание на официальном сайте:\n"
    "🔗 https://lk.gubkin.ru/schedule/"
)

def get_site_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Официальный сайт: lk.gubkin.ru/schedule", url=SCHEDULE_URL)]
    ])

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="📆 Завтра")],
            [KeyboardButton(text="📋 Эта неделя"), KeyboardButton(text="⏭️ След. неделя")],
            [KeyboardButton(text="🔄 Обновить"), KeyboardButton(text="🌐 Официальный сайт")],
            [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="💬 Обратная связь")]
        ],
        resize_keyboard=True
    )

# Шаблон ВЕРХНЕЙ недели (недели 7, 9, 11, 13, 15, 17)
UPPER_STANDARD = {
    0: [  # Понедельник
        "🕒 10:15 – 11:45 | 📚 <b>История России</b> (Семинар)\n👨‍🏫 Охапкина Н.К. | 🚪 Ауд. 1603",
        "🕒 12:00 – 13:30 | 📈 <b>Микроэкономика и основы экономических знаний</b> (Семинар)\n👨‍🏫 Морозов В.В. | 🚪 Ауд. 1603",
        "🕒 14:00 – 15:30 | 🛢️ <b>Углеводородная парадигма современности</b> (Лекция)\n👨‍🏫 Алексанян К.Г. | 🚪 Ауд. 725"
    ],
    1: [  # Вторник
        "🕒 10:15 – 13:30 | 💻 <b>Цифровые технологии в международном бизнесе</b> (Семинар)\n👨‍🏫 Бойко Д.С. | 🚪 Ауд. 511",
        "🕒 14:00 – 15:30 | 📚 <b>История России</b> (Семинар)\n👨‍🏫 Охапкина Н.К. | 🚪 Ауд. 1501Б"
    ],
    2: [  # Среда
        "🕒 15:45 – 17:15 | 📊 <b>Бизнес-аналитика и инновационные технологии</b> (Лекция)\n👨‍🏫 Голованова А.Е. | 🚪 Ауд. 1206",
        "🕒 17:20 – 18:50 | 📊 <b>Бизнес-аналитика и инновационные технологии</b> (Семинар)\n👨‍🏫 Голованова А.Е. | 🚪 Ауд. 1621"
    ],
    3: [  # Четверг
        "🕒 10:15 – 11:45 | 🔤 <b>Иностранный язык (английский)</b> (Семинар)\n👥 1 гр: Жарова Е.Е. | 🚪 Ауд. 2414",
        "🕒 12:00 – 13:30 | 🔤 <b>Иностранный язык (английский)</b> (Семинар)\n👥 1 гр: Жарова Е.Е. | 🚪 Ауд. 2414",
        "🕒 14:00 – 15:30 | 📐 <b>Математические методы экономического анализа</b> (Семинар)\n👨‍🏫 Бойко Д.С. | 🚪 Ауд. 1603",
        "🕒 15:45 – 17:15 | 📈 <b>Микроэкономика и основы экономических знаний</b> (Лекция)\n👨‍🏫 Морозов В.В. | 🚪 Ауд. 1104"
    ],
    4: [  # Пятница
        "🕒 10:15 – 11:45 | 🌐 <b>Кросс-культурные коммуникации: традиции и перспективы</b> (Лекция)\n👨‍🏫 Фальковская К.И. | 🚪 Ауд. 1603",
        "🕒 12:00 – 13:30 | 🌐 <b>Кросс-культурные коммуникации: традиции и перспективы</b> (Семинар)\n👨‍🏫 Фальковская К.И. | 🚪 Ауд. 1603",
        "🕒 14:00 – 15:30 | 📐 <b>Математические методы экономического анализа</b> (Лекция)\n👨‍🏫 Сулян Г.С. | 🚪 Ауд. 711"
    ],
    5: [],
    6: []
}

# Шаблон НИЖНЕЙ недели (недели 8, 10, 12, 14, 16, 18)
LOWER_STANDARD = {
    0: [  # Понедельник
        "🕒 12:00 – 13:30 | 🛢️ <b>Углеводородная парадигма современности</b> (Лабораторная)\n👥 2 гр: Бронзова И.А. | 🚪 Ауд. 823",
        "🕒 14:00 – 15:30 | 📈 <b>Микроэкономика и основы экономических знаний</b> (Семинар)\n👨‍🏫 Морозов В.В. | 🚪 Ауд. 1815",
        "🕒 15:45 – 17:15 | 📚 <b>История России</b> (Лекция)\n👨‍🏫 Охапкина Н.К. | 🚪 Ауд. 1104"
    ],
    1: [  # Вторник
        "🕒 10:15 – 13:30 | 💻 <b>Цифровые технологии в международном бизнесе</b> (Семинар)\n👨‍🏫 Бойко Д.С. | 🚪 Ауд. 512",
        "🕒 14:00 – 15:30 | 🔤 <b>Иностранный язык (английский)</b> (Семинар)\n👥 1 гр: Жарова Е.Е. (ауд. 2414) / 2 гр: Савченко Е.В. (ауд. 2417)",
        "🕒 15:45 – 17:15 | 🔤 <b>Иностранный язык (английский)</b> (Семинар)\n👥 2 гр: Савченко Е.В. | 🚪 Ауд. 2417"
    ],
    2: [  # Среда
        "🕒 12:00 – 13:30 | 📊 <b>Бизнес-аналитика и инновационные технологии</b> (Семинар)\n👨‍🏫 Голованова А.Е. | 🚪 Ауд. 1501А",
        "🕒 14:00 – 15:30 | 📊 <b>Бизнес-аналитика и инновационные технологии</b> (Лекция)\n👨‍🏫 Голованова А.Е. | 🚪 Ауд. 1104",
        "🕒 15:45 – 17:15 | 🔤 <b>Иностранный язык (английский)</b> (Семинар)\n👥 2 гр: Савченко Е.В. | 🚪 Ауд. 2417"
    ],
    3: [  # Четверг
        "🕒 10:15 – 11:45 | 🛢️ <b>Углеводородная парадигма современности</b> (Лабораторная)\n👥 1 гр: Илькова А.А. | 🚪 Ауд. 823",
        "🕒 14:00 – 15:30 | 📈 <b>Микроэкономика и основы экономических знаний</b> (Лекция)\n👨‍🏫 Морозов В.В. | 🚪 Ауд. 725",
        "🕒 15:45 – 17:15 | 📐 <b>Математические методы экономического анализа</b> (Семинар)\n👨‍🏫 Бойко Д.С. | 🚪 Ауд. 1804Б"
    ],
    4: [  # Пятница
        "🕒 12:00 – 13:30 | 🛢️ <b>Углеводородная парадигма современности</b> (Лекция)\n👨‍🏫 Алексанян К.Г. | 🚪 Ауд. 725",
        "🕒 14:00 – 15:30 | 📐 <b>Математические методы экономического анализа</b> (Лекция)\n👨‍🏫 Сулян Г.С. | 🚪 Ауд. 725"
    ],
    5: [],
    6: []
}

# Все точечные переносы, праздники и исключения
DATE_OVERRIDES = {
    date(2026, 11, 4): [],  # Выходной
    date(2026, 11, 7): [    # Суббота — перенос с 09.11
        "🕒 10:15 – 11:45 | 🛢️ <b>Углеводородная парадигма современности</b> (Лекция — <i>Перенесено с 09.11.2026</i>)\n👨‍🏫 Алексанян К.Г. | 🚪 Ауд. 725"
    ],
    date(2026, 11, 9): [    # Понедельник
        "🕒 10:15 – 11:45 | 📚 <b>История России</b> (Семинар)\n👨‍🏫 Охапкина Н.К. | 🚪 Ауд. 1603",
        "🕒 12:00 – 13:30 | 📈 <b>Микроэкономика и основы экономических знаний</b> (Семинар)\n👨‍🏫 Морозов В.В. | 🚪 Ауд. 1603",
        "🕒 15:45 – 17:15 | 🛢️ <b>Углеводородная парадигма современности</b> (Лабораторная)\n👥 2 гр: Бронзова И.А. | 🚪 Ауд. 823"
    ],
    date(2026, 11, 16): [   # Понедельник — 2 лабы подряд
        "🕒 10:15 – 11:45 | 🛢️ <b>Углеводородная парадигма современности</b> (Лабораторная)\n👥 2 гр: Бронзова И.А. | 🚪 Ауд. 823",
        "🕒 12:00 – 13:30 | 🛢️ <b>Углеводородная парадигма современности</b> (Лабораторная)\n👥 2 гр: Бронзова И.А. | 🚪 Ауд. 823",
        "🕒 14:00 – 15:30 | 📈 <b>Микроэкономика и основы экономических знаний</b> (Семинар)\n👨‍🏫 Морозов В.В. | 🚪 Ауд. 1815",
        "🕒 15:45 – 17:15 | 📚 <b>История России</b> (Лекция)\n👨‍🏫 Охапкина Н.К. | 🚪 Ауд. 1104"
    ],
    date(2026, 11, 18): [   # Среда — доп. семинар по истории
        "🕒 10:15 – 11:45 | 📚 <b>История России</b> (Семинар)\n👨‍🏫 Охапкина Н.К. | 🚪 Ауд. 1605",
        "🕒 12:00 – 13:30 | 📊 <b>Бизнес-аналитика и инновационные технологии</b> (Семинар)\n👨‍🏫 Голованова А.Е. | 🚪 Ауд. 1501А",
        "🕒 14:00 – 15:30 | 📊 <b>Бизнес-аналитика и инновационные технологии</b> (Лекция)\n👨‍🏫 Голованова А.Е. | 🚪 Ауд. 1104",
        "🕒 15:45 – 17:15 | 🔤 <b>Иностранный язык (английский)</b> (Семинар)\n👥 2 гр: Савченко Е.В. | 🚪 Ауд. 2417"
    ],
    date(2026, 11, 21): [   # Суббота
        "🕒 10:15 – 13:30 | 💻 <b>Цифровые технологии в международном бизнесе</b> (Семинар)\n👨‍🏫 Бойко Д.С. | 🚪 Ауд. 512"
    ],
    date(2026, 11, 28): [   # Суббота — англ у 2 гр
        "🕒 08:30 – 11:45 | 🔤 <b>Иностранный язык (английский)</b> (Семинар)\n👥 2 гр: Савченко Е.В. | 🚪 Ауд. 2417"
    ],
    date(2026, 12, 24): [   # Четверг
        "🕒 10:15 – 11:45 | 🔤 <b>Иностранный язык (английский)</b> (Семинар)\n👥 1 гр: Жарова Е.Е. | 🚪 Ауд. 2414",
        "🕒 14:00 – 15:30 | 📐 <b>Математические методы экономического анализа</b> (Семинар)\n👨‍🏫 Бойко Д.С. | 🚪 Ауд. 1603"
    ],
    date(2026, 12, 25): [   # Пятница
        "🕒 10:15 – 11:45 | 🌐 <b>Кросс-культурные коммуникации: традиции и перспективы</b> (Семинар — <i>Перенесено с 04.09.2026</i>)\n👨‍🏫 Фальковская К.И. | 🚪 Ауд. 1603",
        "🕒 12:00 – 13:30 | 🌐 <b>Кросс-культурные коммуникации: традиции и перспективы</b> (Семинар)\n👨‍🏫 Фальковская К.И. | 🚪 Ауд. 1603",
        "🕒 14:00 – 15:30 | 📐 <b>Математические методы экономического анализа</b> (Лекция)\n👨‍🏫 Сулян Г.С. | 🚪 Ауд. 711"
    ],
    date(2026, 12, 28): [
        "🕒 14:00 – 15:30 | 📈 <b>Микроэкономика и основы экономических знаний</b> (Семинар)\n👨‍🏫 Морозов В.В. | 🚪 Ауд. 1815"
    ],
    date(2026, 12, 29): [],
    date(2026, 12, 30): [],
    date(2026, 12, 31): [],
    date(2027, 1, 1): [],
    date(2027, 1, 2): [],
    date(2027, 1, 3): []
}

BASE_MONDAY = date(2026, 10, 12)

def get_study_week_num(target_date: date) -> int:
    days_diff = (target_date - BASE_MONDAY).days
    return 7 + (days_diff // 7)

def get_week_type(target_date: date) -> str:
    study_week = get_study_week_num(target_date)
    return "верхняя" if study_week % 2 == 1 else "нижняя"

def get_schedule_for_date(target_date: datetime):
    d = target_date.date()
    if d < date(2026, 10, 12) or d > date(2027, 1, 3):
        return []
    if d in DATE_OVERRIDES:
        return DATE_OVERRIDES[d]
    weekday = d.weekday()
    if get_week_type(d) == "верхняя":
        return UPPER_STANDARD.get(weekday, [])
    else:
        return LOWER_STANDARD.get(weekday, [])

DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 БС-26-05", callback_data="group_bs_26_05")],
        [InlineKeyboardButton(text="🌐 Официальный сайт (lk.gubkin.ru)", url=SCHEDULE_URL)]
    ])
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "Я бот-помощник с расписанием занятий.\n\n"
        f"{WARNING_TEXT}\n\n"
        "Пожалуйста, выбери свою группу для начала работы:",
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await state.set_state(UserState.waiting_for_group)

@dp.callback_query(F.data == "group_bs_26_05")
async def process_group_choice(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(group="БС-26-05")
    await state.set_state(UserState.main_menu)
    await callback.message.answer(
        "✅ Группа <b>БС-26-05</b> успешно выбрана!\n\n"
        f"{WARNING_TEXT}\n\n"
        "Используй кнопки меню ниже для просмотра расписания:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()

@dp.message(F.text == "📅 Сегодня")
async def cmd_today(message: types.Message):
    now = get_moscow_now()
    d = now.date()
    day_name = DAYS_RU[d.weekday()]
    w_type = get_week_type(d)
    w_num = get_study_week_num(d)
    lessons = get_schedule_for_date(now)
    
    response = (
        f"📅 <b>Расписание на сегодня ({d.strftime('%d.%m.%Y')})</b>\n"
        f"📌 {day_name} | {w_num} неделя ({w_type})\n\n"
    )
    if lessons:
        response += "\n\n".join(lessons)
    else:
        response += "🎉 Пар на сегодня нет! Можно отдохнуть или закрыть долги. ☕"
        
    response += "\n\n🔗 Официальный сайт: https://lk.gubkin.ru/schedule/"
    await message.answer(
        response,
        reply_markup=get_site_inline_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.message(F.text == "📆 Завтра")
async def cmd_tomorrow(message: types.Message):
    tomorrow = get_moscow_now() + timedelta(days=1)
    d = tomorrow.date()
    day_name = DAYS_RU[d.weekday()]
    w_type = get_week_type(d)
    w_num = get_study_week_num(d)
    lessons = get_schedule_for_date(tomorrow)
    
    response = (
        f"📆 <b>Расписание на завтра ({d.strftime('%d.%m.%Y')})</b>\n"
        f"📌 {day_name} | {w_num} неделя ({w_type})\n\n"
    )
    if lessons:
        response += "\n\n".join(lessons)
    else:
        response += "🎉 Пар на завтра нет! Отличный день для отдыха. ☕"
        
    response += "\n\n🔗 Официальный сайт: https://lk.gubkin.ru/schedule/"
    await message.answer(
        response,
        reply_markup=get_site_inline_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.message(F.text == "🔄 Обновить")
async def cmd_refresh(message: types.Message):
    now = get_moscow_now()
    d = now.date()
    day_name = DAYS_RU[d.weekday()]
    w_type = get_week_type(d)
    w_num = get_study_week_num(d)
    lessons = get_schedule_for_date(now)
    
    response = (
        f"🔄 <b>Данные обновлены! ({d.strftime('%d.%m.%Y')})</b>\n"
        f"📌 {day_name} | {w_num} неделя ({w_type})\n\n"
    )
    if lessons:
        response += "\n\n".join(lessons)
    else:
        response += "🎉 Пар на сегодня нет! ☕"
        
    response += "\n\n🔗 Официальный сайт: https://lk.gubkin.ru/schedule/"
    await message.answer(
        response,
        reply_markup=get_site_inline_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def send_week_schedule(message: types.Message, ref_date: datetime, title: str):
    start_of_week = ref_date - timedelta(days=ref_date.weekday())
    w_type = get_week_type(start_of_week.date())
    w_num = get_study_week_num(start_of_week.date())
    end_of_week = start_of_week + timedelta(days=6)
    
    response = (
        f"{title} <b>({start_of_week.strftime('%d.%m')} – {end_of_week.strftime('%d.%m.%Y')})</b>\n"
        f"📌 <b>{w_num} неделя, {w_type.upper()}</b>\n\n"
        "─────────────────────────\n\n"
    )
    
    days_blocks = []
    for i in range(6):
        day_dt = start_of_week + timedelta(days=i)
        day_name = DAYS_RU[i]
        lessons = get_schedule_for_date(day_dt)
        
        if i == 5 and not lessons:
            continue
            
        day_text = f"🔹 <b>{day_name} ({day_dt.strftime('%d.%m')}):</b>\n"
        if lessons:
            day_text += "\n".join(lessons)
        else:
            day_text += "Пар нет 🎉"
            
        days_blocks.append(day_text)
    
    response += "\n\n─────────────────────────\n\n".join(days_blocks)
    response += "\n\n─────────────────────────\n\n"
    response += "🔗 Официальный сайт: https://lk.gubkin.ru/schedule/"
    
    await message.answer(
        response,
        reply_markup=get_site_inline_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.message(F.text == "📋 Эта неделя")
async def cmd_this_week(message: types.Message):
    await send_week_schedule(message, get_moscow_now(), "📋 <b>Расписание на эту неделю</b>")

@dp.message(F.text == "⏭️ След. неделя")
async def cmd_next_week(message: types.Message):
    await send_week_schedule(message, get_moscow_now() + timedelta(weeks=1), "⏭️ <b>Расписание на следующую неделю</b>")

@dp.message(F.text == "🌐 Официальный сайт")
async def cmd_official_site(message: types.Message):
    await message.answer(
        "🌐 <b>Официальное расписание Губкинского университета:</b>\n"
        "🔗 https://lk.gubkin.ru/schedule/\n\n"
        f"{WARNING_TEXT}",
        reply_markup=get_site_inline_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    await message.answer(
        "❓ <b>Инструкция по использованию бота:</b>\n\n"
        "• Нажимайте на кнопки главного меню, чтобы узнать расписание на нужный день или неделю.\n"
        "• Кнопка <b>🔄 Обновить</b> загружает актуальные данные на текущий момент.\n"
        "• Бот учитывает все даты, номера учебных недель, переносы и подгруппы вплоть до конца декабря.\n"
        "• По всем вопросам и ошибкам обращайтесь в раздел «Обратная связь».\n\n"
        f"{WARNING_TEXT}",
        reply_markup=get_site_inline_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.message(F.text == "💬 Обратная связь")
async def cmd_feedback(message: types.Message):
    await message.answer(
        "💬 <b>Обратная связь</b>\n\n"
        "Нашли ошибку в расписании или есть идея, как улучшить бота?\n"
        "Напишите разработчику: <b>@bbtbnzg</b>\n\n"
        "🔗 Официальное расписание: https://lk.gubkin.ru/schedule/",
        reply_markup=get_site_inline_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# --- Фоновый веб-сервер против засыпания на Render ---
async def handle_ping(request):
    return web.Response(text="Bot is running 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())