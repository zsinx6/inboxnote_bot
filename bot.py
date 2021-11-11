import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

from git_utils import GitUtils

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

TOKEN = os.getenv("TOKEN")
URL = os.getenv("URL")
SSH_PATH = os.getenv("SSH_PATH")
GIT_USERNAME = os.getenv("GIT_USERNAME")
GIT_EMAIL = os.getenv("GIT_EMAIL")
REPO_PATH = os.getenv("REPO_PATH")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")

git = GitUtils(
    repo=str(URL),
    user={
        "ssh": SSH_PATH,
        "name": GIT_USERNAME,
        "email": GIT_EMAIL,
    },
    path=str(REPO_PATH),
)


def run(updater):
    updater.start_polling()


def handle_user_id(user_id, update, context):
    if str(user_id) != str(TELEGRAM_ID):
        logger.info(f"Wrong User!, {update.message.from_user.id}")
        message = "To use this, refer to https://github.com/zsinx6/inboxnote_bot"
        context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        return False
    return True


def commit_inbox_note(update, context):
    git.commit(message="Auto commit for inbox note")
    context.bot.send_message(chat_id=update.effective_chat.id, text="Note created!")


def start(update, context):
    update.message.reply_text("Just send the note to create one.")


def text_message_handler(update, context):
    note_text = update.message.text
    logger.info(note_text)

    if not handle_user_id(update.message.from_user.id, update, context):
        return

    now = datetime.now()
    filename = now.strftime("%Y%m%d%H%M") + "_from_bot.md"
    folder_path = os.path.join(REPO_PATH, "Inbox")

    with open(os.path.join(folder_path, filename), "w+") as note:
        note.write(note_text)

    commit_inbox_note(update, context)


def image_message_handler(update, context):
    note_text = update.message.caption
    logger.info(note_text)

    if not handle_user_id(update.message.from_user.id, update, context):
        return

    now = datetime.now()
    filename = now.strftime("%Y%m%d%H%M") + "_from_bot.md"
    image_filename = now.strftime("%Y%m%d%H%M") + "_from_bot.jpg"
    folder_path = os.path.join(REPO_PATH, "Inbox")

    if note_text:
        with open(os.path.join(folder_path, filename), "w+") as note:
            note.write(note_text)

    image = update.message.photo[-1]
    with open(os.path.join(folder_path, image_filename), "wb") as note:
        note.write(image.get_file().download_as_bytearray())

    commit_inbox_note(update, context)


def file_message_handler(update, context):
    if not handle_user_id(update.message.from_user.id, update, context):
        return

    file = update.message.document
    file_name_extension = os.path.splitext(file.file_name)[-1]
    now = datetime.now()
    filename = now.strftime("%Y%m%d%H%M") + "_from_bot" + file_name_extension
    folder_path = os.path.join(REPO_PATH, "Inbox")

    with open(os.path.join(folder_path, filename), "wb") as note:
        note.write(file.get_file().download_as_bytearray())

    commit_inbox_note(update, context)


def add_handler(dispatcher):
    start_handler = CommandHandler("start", start)
    dispatcher.add_handler(start_handler)

    message_handler = MessageHandler(Filters.text, text_message_handler)
    dispatcher.add_handler(message_handler)

    image_handler = MessageHandler(Filters.photo, image_message_handler)
    dispatcher.add_handler(image_handler)

    file_handler = MessageHandler(Filters.document, file_message_handler)
    dispatcher.add_handler(file_handler)


if __name__ == "__main__":
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    add_handler(dispatcher)

    run(updater)
