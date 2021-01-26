# from configuration import BOT_TOKEN
import io
import logging

from PIL import Image
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.utils.executor import start_webhook, start_polling
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from nst_class import NST
import os

BOT_TOKEN = os.environ['BOT_TOKEN']

# webhook settings
HEROKU_APP_NAME = os.environ['HEROKU_APP_NAME']
WEBHOOK_HOST = f'https://{HEROKU_APP_NAME}.herokuapp.com'
WEBHOOK_PATH = f'/webhook/{BOT_TOKEN}'
WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}'

# webserver settings
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = os.environ['PORT']

storage = MemoryStorage()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())


@dp.message_handler(commands=['start'])
async def process_start_command(message: types.Message):
    await message.reply("Привет!\nНапиши мне что-нибудь!")


@dp.message_handler(commands=['help'])
async def process_help_command(message: types.Message):
    await message.reply("Напиши мне что-нибудь, и я отпрпавлю этот текст тебе в ответ!")


class ImageProcessor(StatesGroup):
    style = State()
    transfer = State()
    res = State()


class ImgSaver:
    def __init__(self):
        self.style = None
        self.content = None
        self.res = None


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
    await message.reply("Hi there, let's start.\nSend style image for transfer.")


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return

    await bot.send_message(message.from_user.id, text=f'Cancelling state {current_state}')

    await state.finish()
    await message.reply('Cancelled.')


@dp.message_handler(state=ImageProcessor.style, content_types=types.ContentTypes.PHOTO)
async def process_first_img(message: types.Message, state: FSMContext):

    file_id = message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    image_data = await bot.download_file(file_path)
    img = Image.open(image_data)
    holder.style = img
    await ImageProcessor.next()
    await message.answer('Send content image')


@dp.message_handler(state=ImageProcessor.transfer, content_types=types.ContentTypes.PHOTO)
async def process_second_img(message: types.Message, state: FSMContext):

    file_id = message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    image_data = await bot.download_file(file_path)
    img = Image.open(image_data)
    holder.content = img
    await ImageProcessor.next()
    await message.answer('Send something to start transfer')


@dp.message_handler(lambda mess: mess.text, state=(ImageProcessor.style, ImageProcessor.transfer))
async def invalid_message(message: types.Message, state: FSMContext):
    await message.answer('Send image, not text')
    # message.photo.


@dp.message_handler(state=ImageProcessor.res)
async def final_image(message: types.Message, state: FSMContext):

    await message.answer('Wait for 5 - 10 minutes, you will get message with ready picture')
    style_transfer = NST(holder.style, holder.content)
    holder.res = style_transfer.compose()
    img_data = holder.res  # изображение PIL
    bio = io.BytesIO()
    bio.name = 'image.jpeg'
    img_data.save(bio, 'JPEG')
    bio.seek(0)
        # await message.answer('Result of style transfer')
    await bot.send_photo(message.from_user.id, photo=bio, caption='Result of style transfer')
    await state.finish()
    # await state.update_data(res=style_transfer.compose())


@dp.message_handler()
async def echo_message(msg: types.Message):
    await bot.send_message(msg.from_user.id, msg.text)


async def on_startup(dp: 'Dispatcher') -> None:
    logging.warning('Starting connection. ')
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)


async def on_shutdown(dp: 'Dispatcher') -> None:
    logging.warning('Bye! Shutting down webhook connection')

if __name__ == '__main__':
    # start_polling(dp, skip_updates=True)
    # logging.basicConfig(level=logging.INFO)
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
