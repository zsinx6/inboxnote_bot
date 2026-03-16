import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


def install_dependency_stubs():
    if "dotenv" not in sys.modules:
        dotenv_module = types.ModuleType("dotenv")
        dotenv_module.load_dotenv = lambda: None
        sys.modules["dotenv"] = dotenv_module

    if "telegram.error" not in sys.modules:
        telegram_module = types.ModuleType("telegram")
        telegram_error_module = types.ModuleType("telegram.error")

        class TelegramError(Exception):
            pass

        telegram_error_module.TelegramError = TelegramError
        telegram_module.error = telegram_error_module
        sys.modules["telegram"] = telegram_module
        sys.modules["telegram.error"] = telegram_error_module

    if "telegram.ext" not in sys.modules:
        telegram_ext_module = types.ModuleType("telegram.ext")

        class FilterToken(object):
            def __and__(self, other):
                return self

            def __invert__(self):
                return self

        class CommandHandler(object):
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class MessageHandler(object):
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class Updater(object):
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs
                self.dispatcher = SimpleNamespace(bot_data={})

            def start_polling(self):
                return None

            def idle(self):
                return None

        telegram_ext_module.CommandHandler = CommandHandler
        telegram_ext_module.Filters = SimpleNamespace(
            text=FilterToken(),
            command=FilterToken(),
            photo=FilterToken(),
            document=FilterToken(),
        )
        telegram_ext_module.MessageHandler = MessageHandler
        telegram_ext_module.Updater = Updater
        sys.modules["telegram.ext"] = telegram_ext_module

    if "git.exc" not in sys.modules:
        git_exc_module = types.ModuleType("git.exc")

        class GitCommandError(Exception):
            pass

        class InvalidGitRepositoryError(Exception):
            pass

        git_exc_module.GitCommandError = GitCommandError
        git_exc_module.InvalidGitRepositoryError = InvalidGitRepositoryError
        sys.modules["git.exc"] = git_exc_module

    if "git" not in sys.modules:
        git_module = types.ModuleType("git")

        class Repo(object):
            def __init__(self, path):
                raise sys.modules["git.exc"].InvalidGitRepositoryError(path)

            @classmethod
            def clone_from(cls, *args, **kwargs):
                raise AssertionError("clone_from should not be called in these tests")

        git_module.Repo = Repo
        git_module.exc = sys.modules["git.exc"]
        sys.modules["git"] = git_module


install_dependency_stubs()

import bot
import git_utils


class DummyBot(object):
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append({"chat_id": chat_id, "text": text})


class DummyGit(object):
    def __init__(self, result=True, error=None):
        self.result = result
        self.error = error
        self.commit_messages = []

    def commit(self, message):
        self.commit_messages.append(message)
        if self.error is not None:
            raise self.error
        return self.result


class DummyMessage(object):
    def __init__(self, user_id, text=None):
        self.from_user = SimpleNamespace(id=user_id)
        self.text = text
        self.caption = None
        self.document = None
        self.photo = []
        self.replies = []

    def reply_text(self, text):
        self.replies.append(text)


class DummyUpdate(object):
    def __init__(self, message, chat_id=1):
        self.message = message
        self.effective_chat = SimpleNamespace(id=chat_id)


class DummyContext(object):
    def __init__(self, settings, git):
        self.bot = DummyBot()
        self.bot_data = {"settings": settings, "git": git}


def set_required_env(monkeypatch, tmp_path, telegram_id="42"):
    ssh_path = tmp_path / "ssh_helper.sh"
    ssh_path.write_text("#!/bin/sh\n")

    env_vars = {
        "TOKEN": "telegram-token",
        "URL": "git@github.com:user/repo.git",
        "SSH_PATH": str(ssh_path),
        "GIT_USERNAME": "Inbox Bot",
        "GIT_EMAIL": "bot@example.com",
        "REPO_PATH": str(tmp_path / "notes-repo"),
        "TELEGRAM_ID": telegram_id,
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


def build_settings(tmp_path, telegram_id=42):
    return {
        "repo_path": str(tmp_path / "notes-repo"),
        "telegram_id": telegram_id,
    }


def test_build_runtime_settings_requires_all_env_vars(monkeypatch, tmp_path):
    set_required_env(monkeypatch, tmp_path)
    monkeypatch.delenv("TOKEN")

    with pytest.raises(
        ValueError, match="Missing required environment variables: TOKEN"
    ):
        bot.build_runtime_settings()


def test_build_runtime_settings_requires_integer_telegram_id(monkeypatch, tmp_path):
    set_required_env(monkeypatch, tmp_path, telegram_id="not-a-number")

    with pytest.raises(ValueError, match="TELEGRAM_ID must be an integer"):
        bot.build_runtime_settings()


def test_text_message_handler_creates_note_and_commits(tmp_path):
    settings = build_settings(tmp_path)
    git = DummyGit(result=True)
    context = DummyContext(settings, git)
    update = DummyUpdate(DummyMessage(user_id=42, text="remember the milk"))

    bot.text_message_handler(update, context)

    inbox_files = list((Path(settings["repo_path"]) / "Inbox").glob("*_from_bot.md"))
    assert len(inbox_files) == 1
    assert inbox_files[0].read_text(encoding="utf-8") == "remember the milk"
    assert git.commit_messages == ["Auto commit for inbox note"]
    assert context.bot.messages == [{"chat_id": 1, "text": "Note created!"}]


def test_text_message_handler_rejects_unauthorized_users(tmp_path):
    settings = build_settings(tmp_path, telegram_id=42)
    git = DummyGit(result=True)
    context = DummyContext(settings, git)
    update = DummyUpdate(DummyMessage(user_id=99, text="private note"))

    bot.text_message_handler(update, context)

    assert not Path(settings["repo_path"]).exists()
    assert git.commit_messages == []
    assert context.bot.messages == [
        {
            "chat_id": 1,
            "text": "To use this, refer to https://github.com/zsinx6/inboxnote_bot",
        }
    ]


def test_text_message_handler_reports_git_sync_failures(tmp_path):
    settings = build_settings(tmp_path)
    git = DummyGit(error=git_utils.GitUtilsOperationError("push failed"))
    context = DummyContext(settings, git)
    update = DummyUpdate(DummyMessage(user_id=42, text="sync this note"))

    bot.text_message_handler(update, context)

    inbox_files = list((Path(settings["repo_path"]) / "Inbox").glob("*_from_bot.md"))
    assert len(inbox_files) == 1
    assert inbox_files[0].read_text(encoding="utf-8") == "sync this note"
    assert context.bot.messages == [
        {
            "chat_id": 1,
            "text": "Note saved locally, but git sync failed: push failed",
        }
    ]


def test_git_utils_rejects_non_repo_non_empty_directory(tmp_path):
    ssh_path = tmp_path / "ssh_helper.sh"
    ssh_path.write_text("#!/bin/sh\n")

    repo_path = tmp_path / "notes-repo"
    repo_path.mkdir()
    (repo_path / "existing.txt").write_text("this is not a git repo")

    with pytest.raises(
        git_utils.GitUtilsConfigurationError,
        match="Repository path exists but is not a git repository",
    ):
        git_utils.GitUtils(
            repo="git@github.com:user/repo.git",
            user={
                "ssh": str(ssh_path),
                "name": "Inbox Bot",
                "email": "bot@example.com",
            },
            path=str(repo_path),
        )
