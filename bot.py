from datetime import datetime
import logging
import os

from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

from .git_utils import GitUtils


logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


TOKEN = os.getenv("TOKEN")
URL = os.getenv("URL")
SSH_PATH = os.getenv("SSH_PATH")
GIT_USERNAME = os.getenv("GIT_USERNAME")
GIT_EMAIL = os.getenv("GIT_EMAIL")
REPO_PATH = os.getenv("REPO_PATH")

git = GitUtils(
    repo=URL,
    user={
        'ssh': SSH_PATH,
        'name': GIT_USERNAME,
        'email': GIT_EMAIL,
    },
    path=REPO_PATH
)


def run(updater):
    updater.start_pooling()


def add_handler(dispatcher):
    start_handler = CommandHandler("start", start)
    dispatcher.add_handler(start_handler)

    message_handler = MessageHandler(Filters.text, send_message)
    dispatcher.add_handler(message_handler)


def start(update, context):
    update.message.reply_text("Just send the note to create one.")


def send_message(update, context):
    note_text = update.message.text

    logger.info(note_text)

    now = datetime.now()
    filename = now.strftime("%Y%m%d%H%M") + "_from_bot.md"

    folder_path = os.path.join(REPO_PATH, "Inbox")

    with open(os.path.join(folder_path, filename), 'w+') as note:
        note.write(note_text)

    git.commit(message='Auto commit for inbox note')
    context.bot.send_message(chat_id=update.effective_chat.id, text="Note created!")


if __name__ == "__main__":
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    add_handler(dispatcher)

    run(updater)
