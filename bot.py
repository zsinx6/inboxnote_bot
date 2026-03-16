import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram.error import TelegramError
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

import git_utils

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

REQUIRED_ENV_VARS = (
    "TOKEN",
    "URL",
    "SSH_PATH",
    "GIT_USERNAME",
    "GIT_EMAIL",
    "REPO_PATH",
    "TELEGRAM_ID",
)


def build_runtime_settings():
    missing_vars = [
        env_name
        for env_name in REQUIRED_ENV_VARS
        if not (os.getenv(env_name) or "").strip()
    ]
    if missing_vars:
        raise ValueError(
            "Missing required environment variables: "
            + ", ".join(missing_vars)
            + ". Copy default.env to .env and set them before starting the bot."
        )

    try:
        telegram_id = int((os.getenv("TELEGRAM_ID") or "").strip())
    except ValueError as exc:
        raise ValueError("TELEGRAM_ID must be an integer.") from exc

    repo_path = os.path.abspath(
        os.path.expanduser((os.getenv("REPO_PATH") or "").strip())
    )

    return {
        "token": (os.getenv("TOKEN") or "").strip(),
        "url": (os.getenv("URL") or "").strip(),
        "ssh_path": (os.getenv("SSH_PATH") or "").strip(),
        "git_username": (os.getenv("GIT_USERNAME") or "").strip(),
        "git_email": (os.getenv("GIT_EMAIL") or "").strip(),
        "repo_path": repo_path,
        "telegram_id": telegram_id,
    }


def get_settings(context):
    return context.bot_data["settings"]


def get_git(context):
    return context.bot_data["git"]


def send_chat_message(update, context, message):
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)


def ensure_inbox_path(context):
    folder_path = os.path.join(get_settings(context)["repo_path"], "Inbox")
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def build_note_stem():
    return datetime.now().strftime("%Y%m%d%H%M%S_%f") + "_from_bot"


def run(updater):
    updater.start_polling()
    updater.idle()


def handle_user_id(update, context):
    user_id = update.message.from_user.id
    if user_id != get_settings(context)["telegram_id"]:
        logger.info("Rejected message from unauthorized user id=%s", user_id)
        message = "To use this, refer to https://github.com/zsinx6/inboxnote_bot"
        send_chat_message(update, context, message)
        return False
    return True


def commit_inbox_note(update, context):
    committed = get_git(context).commit(message="Auto commit for inbox note")
    if committed:
        send_chat_message(update, context, "Note created!")
        return
    send_chat_message(update, context, "Note saved, but no git changes were detected.")


def start(update, context):
    update.message.reply_text("Send a note, photo, or file to create an Inbox item.")


def text_message_handler(update, context):
    if not handle_user_id(update, context):
        return

    logger.info("Processing text note from user id=%s", update.message.from_user.id)

    filename = build_note_stem() + ".md"
    file_path = os.path.join(ensure_inbox_path(context), filename)

    try:
        with open(file_path, "w", encoding="utf-8") as note:
            note.write(update.message.text)
    except OSError as exc:
        logger.exception("Failed to save text note to %s", file_path)
        send_chat_message(update, context, f"Failed to save note: {exc}")
        return

    try:
        commit_inbox_note(update, context)
    except git_utils.GitUtilsOperationError as exc:
        logger.exception("Failed to sync text note from %s", file_path)
        send_chat_message(
            update, context, f"Note saved locally, but git sync failed: {exc}"
        )


def image_message_handler(update, context):
    if not handle_user_id(update, context):
        return

    logger.info("Processing photo note from user id=%s", update.message.from_user.id)

    folder_path = ensure_inbox_path(context)
    note_text = update.message.caption
    note_stem = build_note_stem()
    image_path = os.path.join(folder_path, note_stem + ".jpg")

    if note_text:
        note_path = os.path.join(folder_path, note_stem + ".md")
        try:
            with open(note_path, "w", encoding="utf-8") as note:
                note.write(note_text)
        except OSError as exc:
            logger.exception("Failed to save photo caption to %s", note_path)
            send_chat_message(update, context, f"Failed to save photo note: {exc}")
            return

    image = update.message.photo[-1]
    try:
        with open(image_path, "wb") as note:
            note.write(image.get_file().download_as_bytearray())
    except (OSError, TelegramError) as exc:
        logger.exception("Failed to save image to %s", image_path)
        send_chat_message(update, context, f"Failed to save image: {exc}")
        return

    try:
        commit_inbox_note(update, context)
    except git_utils.GitUtilsOperationError as exc:
        logger.exception("Failed to sync photo note from %s", image_path)
        send_chat_message(
            update, context, f"Note saved locally, but git sync failed: {exc}"
        )


def file_message_handler(update, context):
    if not handle_user_id(update, context):
        return

    logger.info("Processing file note from user id=%s", update.message.from_user.id)

    file = update.message.document
    file_name_extension = os.path.splitext(file.file_name or "")[-1]
    filename = build_note_stem() + file_name_extension
    file_path = os.path.join(ensure_inbox_path(context), filename)

    try:
        with open(file_path, "wb") as note:
            note.write(file.get_file().download_as_bytearray())
    except (OSError, TelegramError) as exc:
        logger.exception("Failed to save file to %s", file_path)
        send_chat_message(update, context, f"Failed to save file: {exc}")
        return

    try:
        commit_inbox_note(update, context)
    except git_utils.GitUtilsOperationError as exc:
        logger.exception("Failed to sync file note from %s", file_path)
        send_chat_message(
            update, context, f"Note saved locally, but git sync failed: {exc}"
        )


def add_handler(dispatcher):
    start_handler = CommandHandler("start", start)
    dispatcher.add_handler(start_handler)

    message_handler = MessageHandler(
        Filters.text & ~Filters.command, text_message_handler
    )
    dispatcher.add_handler(message_handler)

    image_handler = MessageHandler(Filters.photo, image_message_handler)
    dispatcher.add_handler(image_handler)

    file_handler = MessageHandler(Filters.document, file_message_handler)
    dispatcher.add_handler(file_handler)


def main():
    settings = build_runtime_settings()
    git = git_utils.GitUtils(
        repo=settings["url"],
        user={
            "ssh": settings["ssh_path"],
            "name": settings["git_username"],
            "email": settings["git_email"],
        },
        path=settings["repo_path"],
    )

    updater = Updater(token=settings["token"], use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.bot_data["settings"] = settings
    dispatcher.bot_data["git"] = git
    add_handler(dispatcher)
    logger.info("Starting inbox note bot for %s", settings["repo_path"])

    run(updater)


if __name__ == "__main__":
    try:
        main()
    except (
        git_utils.GitUtilsConfigurationError,
        git_utils.GitUtilsOperationError,
        ValueError,
    ) as exc:
        logger.error("Failed to start inbox note bot: %s", exc)
        raise SystemExit(1) from exc
