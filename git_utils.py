import logging
import os
from typing import Optional

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

logger = logging.getLogger(__name__)


class GitUtilsError(Exception):
    """Base exception for git helper failures."""


class GitUtilsConfigurationError(GitUtilsError):
    """Raised when git helper configuration is invalid."""


class GitUtilsOperationError(GitUtilsError):
    """Raised when a git operation cannot be completed."""


class GitUtils(object):
    def __init__(self, repo: str, user: dict, path: str = ""):
        """GitUtils initial method
        Examples
        --------
        from .utils.git import GitUtils
        git = GitUtils(
            repo='git@github.com:zosimos/gitpython-example.git',
            user={
                'ssh': '/usr/local/bin/my_gitpython_ssh',
                'name': 'my_headless_coount',
                'email': 'my_headless_coount@gmail.com',
            }
        )
        # Some file change ...
        git.commit(branch='master', message='Auto commit by my testing headless account')
        Parameters
        ----------
        repo : str
            The Git repository SSH url.
            To be able to commit file by using SSH key, you must provide `git@` format.
        user : dict
            Git user information. You must provide `ssh` script path, Git user `name` and `email` with dictionary format, e.g:
            {
                'ssh': '/usr/local/bin/lorax_ssh',
                'name': 'my_account',
                'email': 'my_account@gmail.com'
            }
        path : str, optional
            The path where you would like tho checkout your repository.
            If you didn't specify this value, it will based on your current working directory.
            **Make sure that's an empty folder for `git clone`**
        """
        repo = repo.strip()
        path = os.path.abspath(os.path.expanduser(path.strip() or os.getcwd()))
        _ = {"ssh": "", "name": "nobody", "email": "nobody@gmail.com"}
        _.update(user)
        user = {key: str(value or "").strip() for key, value in _.items()}
        self.repo_url = repo
        self.path = path

        if not repo.startswith("git@"):
            raise GitUtilsConfigurationError(
                f"Invalid git checkout url: {repo}\n\n"
                "Please make sure you are using the valid SSH url with the correct `git@github.com:account/repository.git` format\n\n"
            )

        if not user["name"] or not user["email"]:
            raise GitUtilsConfigurationError("Missing git user name or email.")

        if not os.path.isfile(user["ssh"]):
            raise GitUtilsConfigurationError(
                "Missing custom SSH script.\n\n"
                "You must provide a custom SSH script which can be able to execute git commands with the correct SSH key.\n"
                "The bash script should contain this line:\n\n"
                'ssh -i <SSH_private_key> -oIdentitiesOnly=yes -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null "$@"\n\n'
            )

        os.environ["GIT_SSH"] = user["ssh"]
        self.git_env = {"GIT_SSH": user["ssh"]}
        self.repo = self._prepare_repository()
        self._configure_user(user["name"], user["email"])

    def _prepare_repository(self):
        if os.path.exists(self.path):
            if not os.path.isdir(self.path):
                raise GitUtilsConfigurationError(
                    f"Repository path must be a directory: {self.path}"
                )

            if not os.listdir(self.path):
                return self._clone_repository()

            try:
                repo = Repo(self.path)
            except InvalidGitRepositoryError as exc:
                raise GitUtilsConfigurationError(
                    "Repository path exists but is not a git repository. Use an empty directory or an existing clone."
                ) from exc

            self._pull_repository(repo)
            return repo

        os.makedirs(self.path)
        return self._clone_repository()

    def _clone_repository(self):
        try:
            return Repo.clone_from(self.repo_url, self.path, env=self.git_env)
        except GitCommandError as exc:
            raise GitUtilsOperationError(
                "Failed to clone repository from origin."
            ) from exc

    def _pull_repository(self, repo):
        if not any(remote.name == "origin" for remote in repo.remotes):
            raise GitUtilsConfigurationError(
                "Repository does not have an origin remote configured."
            )

        branch_name = self._resolve_branch(repo=repo)
        try:
            repo.remote("origin").pull(branch_name)
        except GitCommandError as exc:
            raise GitUtilsOperationError(
                f"Failed to pull latest changes from branch {branch_name}."
            ) from exc

    def _configure_user(self, name: str, email: str):
        config_writer = self.repo.config_writer()
        try:
            config_writer.set_value("user", "name", name)
            config_writer.set_value("user", "email", email)
        finally:
            config_writer.release()

    def _resolve_branch(self, branch: Optional[str] = None, repo=None):
        if branch:
            return branch

        current_repo = repo or self.repo
        try:
            return current_repo.active_branch.name
        except TypeError:
            pass

        try:
            remote_head = current_repo.git.symbolic_ref(
                "refs/remotes/origin/HEAD"
            ).strip()
        except GitCommandError as exc:
            raise GitUtilsConfigurationError(
                "Unable to determine which branch to use for git operations."
            ) from exc

        return os.path.basename(remote_head)

    def commit(self, branch: Optional[str] = None, message: str = "Auto commit"):
        """Basic commit method.
        This commit method will detect all file changes and doing `git add`, `git commit -m <message>`, and `git push <branch>` all at once.
        Parameters
        ----------
        branch : str, optional
            The branch you would like to commit. Default is the currently checked out branch.
        message : str, optionl
            Commit message
        """
        has_changed = False

        try:
            # Check if there's any untracked files
            for file in self.repo.untracked_files:
                logger.info("Adding untracked file: %s", file)
                self.repo.git.add(file)
                has_changed = True

            if self.repo.is_dirty() is True:
                for file in self.repo.git.diff(None, name_only=True).split("\n"):
                    if file == "":
                        continue
                    logger.info("Adding modified file: %s", file)
                    self.repo.git.add(file)
                    has_changed = True
        except GitCommandError as exc:
            raise GitUtilsOperationError("Failed to stage changes for commit.") from exc

        if has_changed is False:
            logger.info("No changes detected; skipping git commit.")
            return False

        branch_name = self._resolve_branch(branch)
        try:
            self.repo.git.commit("-m", message)
            self.repo.git.push("origin", branch_name)
        except GitCommandError as exc:
            raise GitUtilsOperationError(
                f"Failed to sync changes to branch {branch_name}."
            ) from exc

        return True
