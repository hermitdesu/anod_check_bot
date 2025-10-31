import asyncio
import logging
import sys
import os

from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile

from dotenv import load_dotenv

load_dotenv()


TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()


LOCAL_PATH = "Гайд по задачам АНОД 1.pdf"
doc = FSInputFile(LOCAL_PATH, filename="Гайд по задачам АНОД 1.pdf")


channel_id = "@official_anod"

check_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Я подписался!", callback_data="check")]]
    )


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Привет, {html.bold(message.from_user.full_name)}, чтобы получить доступ к материалу подпишись на наш канал: https://t.me/official_anod",
                         reply_markup=check_kb)



@dp.callback_query(F.data == "check")
async def check_subscription(callback: CallbackQuery):
    try:
        st = await callback.bot.get_chat_member(channsel_id, callback.from_user.id)
        if st.status in ["creator", "administrator", "member"]:
            sent = await callback.message.answer_document(doc)
            new_fid = sent.document.file_id
            print("NEW FILE_ID:", new_fid)
        else:
            await callback.message.answer("Вы не подписаны на канал!")
    except TelegramBadRequest as e:
        await callback.message.answer(f"Произошла ошибка.{e.message}")
    await callback.answer()
    


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())