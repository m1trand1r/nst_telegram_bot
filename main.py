from configuration import BOT_TOKEN
import io
import logging

from PIL import Image
import asyncio
from aiogram import Bot, types
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.utils.executor import start_webhook, start_polling
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from asgiref.sync import sync_to_async
from nst_class import NST
import os

# BOT_TOKEN = os.environ['BOT_TOKEN']
#
# # webhook settings
# HEROKU_APP_NAME = os.environ['HEROKU_APP_NAME']
# WEBHOOK_HOST = f'https://{HEROKU_APP_NAME}.herokuapp.com'
# WEBHOOK_PATH = f'/webhook/{BOT_TOKEN}'
# WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}'
#
# # webserver settings
# WEBAPP_HOST = '0.0.0.0'
# WEBAPP_PORT = os.environ['PORT']

storage = MemoryStorage()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())


@dp.message_handler(commands=['start'])
async def process_start_command(message: types.Message):
    await message.reply("Привет!\nОтправь /help чтоб узнать список доступных команд.")


@dp.message_handler(commands=['help'])
async def process_help_command(message: types.Message):
    help_message = 'Бот работает на сервере без GPU ускорителя, поэтому итоговое изображение будет с измененным ' \
                   'разрешением для адекватного времени ответа.\n' \
                   'Для начала работы отправьте команду /nst_start\n' \
                   'Для отмены во время любого шага по переносу стиля отправьте сообщение с текстом cancel ' \
                   '(не имеет разницы строчные или заглавные буквы)'
    await message.reply(help_message)


class ImageProcessor(StatesGroup):
    style = State()
    transfer = State()
    res = State()


class ImgSaver:
    def __init__(self):
        self.style = None
        self.content = None
        self.res = None
        self.starter = None


holder = ImgSaver()


@dp.message_handler(commands=['start'])
async def process_start_command(message: types.Message):
    await message.reply("Привет!\nНапиши мне что-нибудь!")


@dp.message_handler(commands=['help'])
async def process_help_command(message: types.Message):
    await message.reply("Напиши мне что-нибудь, и я отпрпавлю этот текст тебе в ответ!")


@dp.message_handler(commands='nst_start')
async def cmd_start(message: types.Message):
    """
    NST model entry point
    """
    await ImageProcessor.style.set()
    await message.reply("Давайте начнем.\nОтправьте изображение - стиль.")


@dp.message_handler(state=(ImageProcessor.style, ImageProcessor.transfer), commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state=(ImageProcessor.style, ImageProcessor.transfer))
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return
    # await bot.send_message(message.from_user.id, text=f'Cancelling state {current_state}')

    await state.finish()
    await message.reply('Успешно отменено.')


@dp.message_handler(state=ImageProcessor.style, content_types=types.ContentTypes.PHOTO)
async def process_first_img(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    image_data = await bot.download_file(file_path)
    img = Image.open(image_data)
    holder.style = img
    await ImageProcessor.next()
    await message.answer('Отправьте изображение на которое будет переноситься стиль')


@dp.message_handler(state=ImageProcessor.transfer, content_types=types.ContentTypes.PHOTO)
async def process_second_img(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    image_data = await bot.download_file(file_path)
    img = Image.open(image_data)
    holder.content = img

    inline_kb = InlineKeyboardMarkup()
    inline_btn = InlineKeyboardButton('Старт', callback_data='btn_start')
    inline_kb.add(inline_btn)
    await ImageProcessor.next()
    await message.answer('Нажмите на кнопку для начала переноса стиля', reply_markup=inline_kb)


@dp.message_handler(content_types=['voice', 'text', 'sticker'], state=(ImageProcessor.style, ImageProcessor.transfer))
async def invalid_message(message: types.Message, state: FSMContext):
    await message.answer('Отправьте изображение')


@dp.message_handler(lambda mess: mess.text, state=ImageProcessor.res)
async def invalid_message(message: types.Message, state: FSMContext):
    if message.text == '/nst_start':
        await message.answer('Для начала нового переноса стиля ожидайте окончание предыдущего переноса стиля.')
    else:
        await message.answer('Ожидайте 5 - 10 минут пока создается изображение.\n'
                             'Вы получите новое сообщение с готовым изображением')


# @dp.message_handler(state=ImageProcessor.res)
@dp.callback_query_handler(lambda c: c.data.startswith('btn'), state=ImageProcessor.res)
async def final_image(message: types.Message, state: FSMContext):
    await bot.send_message(message.from_user.id, text='Ожидайте 5 - 10 минут пока создается изображение.\n'
                                                      'Вы получите новое сообщение с готовым изображением')
    # await message.answer('Ожидайте 5 - 10 минут пока создается изображение.\n'
    #                      'Вы получите новое сообщение с готовым изображением')
    style_transfer = NST(holder.style, holder.content)
    holder.res = sync_to_async(style_transfer.compose)()
    holder.starter = await holder.res  # изображение PIL
    bio = io.BytesIO()
    bio.name = 'image.jpeg'
    holder.starter.save(bio, 'JPEG')
    bio.seek(0)
    await bot.send_photo(message.from_user.id, photo=bio, caption='Результат переноса стиля')
    # await asyncio.sleep(10)
    await state.finish()
    # await state.update_data(res=style_transfer.compose())


# async def on_startup(dp: 'Dispatcher') -> None:
#     logging.warning('Starting connection. ')
#     await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
#
#
# async def on_shutdown(dp: 'Dispatcher') -> None:
#     logging.warning('Bye! Shutting down webhook connection')

if __name__ == '__main__':
    start_polling(dp, skip_updates=True)
    logging.basicConfig(level=logging.INFO)
    # start_webhook(
    #     dispatcher=dp,
    #     webhook_path=WEBHOOK_PATH,
    #     skip_updates=True,
    #     on_startup=on_startup,
    #     on_shutdown=on_shutdown,
    #     host=WEBAPP_HOST,
    #     port=WEBAPP_PORT,
    # )
