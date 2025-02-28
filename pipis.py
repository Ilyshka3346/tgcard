import random
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from supabase import create_client, Client
from postgrest.exceptions import APIError

# Настройки Supabase
SUPABASE_URL = "https://zkhnijcxqhuljvufgrqa.supabase.co"  # Замените на ваш URL
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpraG5pamN4cWh1bGp2dWZncnFhIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MDEzOTQ4NiwiZXhwIjoyMDU1NzE1NDg2fQ.Iv4wqMu3inhLsLRnbj_Ifg5ZdAdWeA9vTpg0m3fCv3U"  # Замените на service_role ключ
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token="7527868872:AAECjTJXSQfbHJ1H7yLMHE2fFHL9Ai3MYoQ")  # Замените на свой токен
dp = Dispatcher()

# Пароль для админ-панели
ADMIN_PASSWORD = "pipiz123"

# Генерация 16-значного кода
def generate_card_number():
    return ''.join([str(random.randint(0, 9)) for _ in range(16)])

# Получение баланса пользователя
def get_balance(user_id: str):
    try:
        response = supabase.table("users").select("balance").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]["balance"]
        return 0
    except APIError as e:
        logger.error(f"Ошибка при получении баланса: {e}")
        return 0

# Обновление баланса пользователя
def update_balance(user_id: str, new_balance: float):
    try:
        supabase.table("users").update({"balance": new_balance}).eq("user_id", user_id).execute()
    except APIError as e:
        logger.error(f"Ошибка при обновлении баланса: {e}")

# Получение user_id по номеру карты
def get_user_id_by_card(card_number: str):
    try:
        response = supabase.table("users").select("user_id").eq("card_number", card_number).execute()
        if response.data:
            return response.data[0]["user_id"]
        return None
    except APIError as e:
        logger.error(f"Ошибка при поиске карты: {e}")
        return None

# Создание нового пользователя
def create_user(user_id: str, card_number: str):
    try:
        supabase.table("users").insert({
            "user_id": user_id,
            "card_number": card_number,
            "balance": 0  # Начальный баланс
        }).execute()
    except APIError as e:
        logger.error(f"Ошибка при создании пользователя: {e}")

# Проверка, есть ли у пользователя карта
def has_card(user_id: str):
    try:
        response = supabase.table("users").select("card_number").eq("user_id", user_id).execute()
        return bool(response.data)
    except APIError as e:
        logger.error(f"Ошибка при проверке карты: {e}")
        return False

# Главное меню
async def show_main_menu(message: types.Message):
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text="Проверить баланс"))
    keyboard.add(KeyboardButton(text="Перевести"))
    keyboard.add(KeyboardButton(text="Админ-панель"))
    keyboard.add(KeyboardButton(text="Открыть карту", web_app=WebAppInfo(url="https://ilyshka3346.github.io/tgcard/")))  # Укажите ваш URL
    await message.answer("Главное меню:", reply_markup=keyboard.as_markup(resize_keyboard=True))

# Команда /start
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    logger.info(f"Пользователь {user_id} вызвал команду /start")
    
    if has_card(user_id):
        await show_main_menu(message)
    else:
        # Создаем карту, если её нет
        card_number = generate_card_number()
        create_user(user_id, card_number)
        await message.answer(f"Ваш номер карты: {card_number}")
        await show_main_menu(message)

# Обработка нажатия на кнопку "Проверить баланс"
@dp.message(lambda message: message.text.strip().lower() == "проверить баланс")
async def check_balance(message: types.Message):
    user_id = str(message.from_user.id)
    balance = get_balance(user_id)
    
    # Показываем баланс и кнопку "Назад"
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text="Назад"))
    await message.answer(f"Ваш баланс: {balance} GOM", reply_markup=keyboard.as_markup(resize_keyboard=True))

# Обработка нажатия на кнопку "Перевести"
@dp.message(lambda message: message.text.strip().lower() == "перевести")
async def transfer_money(message: types.Message):
    user_id = str(message.from_user.id)
    logger.info(f"Пользователь {user_id} начал перевод")
    
    await message.answer("Введите номер карты получателя:")
    dp["awaiting_card"] = True

# Обработка ввода номера карты для перевода
@dp.message(lambda message: dp.get("awaiting_card"))
async def enter_card_for_transfer(message: types.Message):
    card_number = message.text.strip()
    recipient_user_id = get_user_id_by_card(card_number)
    
    if not recipient_user_id:
        await message.answer("Карта не найдена.")
        dp["awaiting_card"] = False
        return
    
    dp["recipient_user_id"] = recipient_user_id
    dp["awaiting_amount"] = True
    dp["awaiting_card"] = False
    await message.answer("Введите сумму для перевода:")

# Обработка ввода суммы для перевода
@dp.message(lambda message: dp.get("awaiting_amount"))
async def enter_amount_for_transfer(message: types.Message):
    try:
        amount = float(message.text.strip())
        user_id = str(message.from_user.id)
        balance = get_balance(user_id)
        
        if amount > balance:
            await message.answer("Недостаточно средств на балансе.")
        else:
            # Обновляем баланс отправителя
            new_balance_sender = balance - amount
            update_balance(user_id, new_balance_sender)
            
            # Обновляем баланс получателя
            recipient_user_id = dp["recipient_user_id"]
            recipient_balance = get_balance(recipient_user_id)
            new_balance_recipient = recipient_balance + amount
            update_balance(recipient_user_id, new_balance_recipient)
            
            await message.answer(f"Перевод успешно выполнен! Новый баланс: {new_balance_sender} GOM")
    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму.")
    finally:
        dp["awaiting_amount"] = False
        await show_main_menu(message)

# Обработка нажатия на кнопку "Админ-панель"
@dp.message(lambda message: message.text.strip().lower() == "админ-панель")
async def admin_panel(message: types.Message):
    await message.answer("Введите пароль для доступа к админ-панели:")
    dp["awaiting_password"] = True

# Обработка ввода пароля
@dp.message(lambda message: dp.get("awaiting_password"))
async def check_password(message: types.Message):
    password = message.text.strip()
    
    if password == ADMIN_PASSWORD:
        await message.answer("Доступ разрешен. Введите номер карты для пополнения:")
        dp["awaiting_card_for_topup"] = True
        dp["awaiting_password"] = False
    else:
        await message.answer("Неверный пароль. Попробуйте снова.")

# Обработка ввода номера карты для пополнения
@dp.message(lambda message: dp.get("awaiting_card_for_topup"))
async def enter_card_for_topup(message: types.Message):
    card_number = message.text.strip()
    recipient_user_id = get_user_id_by_card(card_number)
    
    if not recipient_user_id:
        await message.answer("Карта не найдена.")
        dp["awaiting_card_for_topup"] = False
        return
    
    dp["recipient_user_id"] = recipient_user_id
    dp["awaiting_amount_for_topup"] = True
    dp["awaiting_card_for_topup"] = False
    await message.answer("Введите сумму для пополнения:")

# Обработка ввода суммы для пополнения
@dp.message(lambda message: dp.get("awaiting_amount_for_topup"))
async def enter_amount_for_topup(message: types.Message):
    try:
        amount = float(message.text.strip())
        recipient_user_id = dp["recipient_user_id"]
        current_balance = get_balance(recipient_user_id)
        new_balance = current_balance + amount
        update_balance(recipient_user_id, new_balance)
        
        await message.answer(f"Баланс карты успешно пополнен на {amount} GOM. Новый баланс: {new_balance} GOM")
    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму.")
    finally:
        dp["awaiting_amount_for_topup"] = False
        await show_main_menu(message)

# Обработка нажатия на кнопку "Назад"
@dp.message(lambda message: message.text.strip().lower() == "назад")
async def back_to_menu(message: types.Message):
    # Сбрасываем все состояния
    dp["awaiting_password"] = False
    dp["awaiting_card"] = False
    dp["awaiting_amount"] = False
    dp["awaiting_card_for_topup"] = False
    dp["awaiting_amount_for_topup"] = False
    
    await show_main_menu(message)

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())