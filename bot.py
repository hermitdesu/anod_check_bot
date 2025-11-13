import asyncio
import logging
import sys
import os
from typing import Optional

from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    FSInputFile,
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from dotenv import load_dotenv
import asyncpg

load_dotenv()


TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in raw_admin_ids.split(",") if x.strip()]


if not TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не задан")


# Dispatcher с FSM-хранилищем
dp = Dispatcher(storage=MemoryStorage())

# ---------- FSM для рассылки ----------

class BroadcastStates(StatesGroup):
    waiting_for_message = State()


# ---------- Postgres ----------

db_pool: Optional[asyncpg.Pool] = None


async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY
            );
            """
        )


async def add_user(user_id: int):
    assert db_pool is not None, "DB pool is not initialized"
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING;
            """,
            user_id,
        )


async def get_all_users() -> list[int]:
    assert db_pool is not None, "DB pool is not initialized"
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users;")
    return [r["user_id"] for r in rows]


# ---------- Логика бота ----------

LOCAL_PATH = "Гайд по задачам АНОД 1.pdf"
doc = FSInputFile(LOCAL_PATH, filename="Гайд по задачам АНОД 1.pdf")

channel_id = "@official_anod"

check_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Я подписался!", callback_data="check")]]
)


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    # сохраняем пользователя в базе
    await add_user(message.from_user.id)

    await message.answer(
        f"Привет, {html.bold(message.from_user.full_name)}, "
        f"чтобы получить доступ к материалу подпишись на наш канал: "
        f"https://t.me/official_anod",
        reply_markup=check_kb,
    )


@dp.callback_query(F.data == "check")
async def check_subscription(callback: CallbackQuery):
    try:
        st = await callback.bot.get_chat_member(channel_id, callback.from_user.id)
        if st.status in ["creator", "administrator", "member"]:
            # на всякий случай тоже добавим в базу
            await add_user(callback.from_user.id)

            sent = await callback.message.answer_document(doc)
            new_fid = sent.document.file_id
            print("NEW FILE_ID:", new_fid)
        else:
            await callback.message.answer("Вы не подписаны на канал!")
    except TelegramBadRequest as e:
        await callback.message.answer(f"Произошла ошибка. {e.message}")
    await callback.answer()


# ---------- FSM-рассылка ----------

@dp.message(Command("broadcast"))
async def start_broadcast(message: Message, state: FSMContext):
    """
    Старт рассылки: только для админов.
    """
    if message.from_user.id not in ADMIN_IDS:
        # можно написать что-то вроде "нет доступа"
        return

    await state.set_state(BroadcastStates.waiting_for_message)
    await message.answer(
        "Отправьте сообщение для рассылки. \n\n"
        "Чтобы отменить — /cancel"
    )


@dp.message(Command("cancel"))
async def cancel_broadcast(message: Message, state: FSMContext):
    """
    Отмена рассылки.
    """
    if message.from_user.id not in ADMIN_IDS:
        return

    cur_state = await state.get_state()
    if cur_state is None:
        await message.answer("Нечего отменять.")
        return

    await state.clear()
    await message.answer("Рассылка отменена.")


@dp.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """
    Здесь мы уже получили message: Message,
    который нужно разослать всем.
    """
    if message.from_user.id not in ADMIN_IDS:
        # на всякий случай не даём левому человеку повлиять на рассылку
        return

    user_ids = await get_all_users()
    if not user_ids:
        await message.answer("В базе нет пользователей для рассылки.")
        await state.clear()
        return

    await message.answer(
        f"Начинаю рассылку этого сообщения по {len(user_ids)} пользователям..."
    )

    success = 0
    failed = 0

    for uid in user_ids:
        try:
            # Копируем ИМЕННО этот message (любой тип контента)
            await message.bot.copy_message(
                chat_id=uid,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            success += 1
            await asyncio.sleep(0.05)  # небольшой таймаут от flood limit
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception as e:
            failed += 1
            logging.exception(f"Ошибка при отправке пользователю %s: %s", uid, e)

    await message.answer(
        f"Рассылка завершена.\nУспешно: {success}\nНе доставлено: {failed}"
    )

    await state.clear()


# ---------- main ----------

async def main() -> None:
    await init_db()

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
