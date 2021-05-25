import os
from git import Repo


class GitUtils(object):

    def __init__(self, repo: str, user: dict, path: str = ''):
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
        path = os.path.join(os.getcwd(), path.strip())
        _ = {'ssh': '', 'name': 'nobody', 'email': 'nobody@gmail.com'}
        _.update(user)
        user = _

        if not repo.startswith('git@'):
            raise Exception(
                f'Invalid git checkout url: {repo}\n\n'
                'Please make sure you are using the valid SSH url with the correct `git@github.com:account/repository.git` format\n\n'
            )

        if not os.path.isfile(user['ssh']):
            raise Exception(
                f'Missing custom SSH script {user["ssh"]}!\n\n'
                'You must provide a custom SSH script which can be able to execute git commands with the correct SSH key.\n'
                'The bash script should contain this line:\n\n'
                'ssh -i <SSH_private_key> -oIdentitiesOnly=yes -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null "$@"\n\n'
            )

        os.environ['GIT_SSH'] = user['ssh']

        if os.path.isdir(path):
            self.repo = Repo(path)
            self.repo.git.pull('origin', 'main')
        else:
            os.makedirs(path)
            self.repo = Repo.clone_from(repo, path, env={'GIT_SSH': user['ssh']})
            self.repo.config_writer().set_value('user', 'name', user['name']).release()
            self.repo.config_writer().set_value('user', 'email', user['email']).release()

    def commit(self, branch: str = 'main', message: str = 'Auto commit'):
        """Basic commit method.
        This commit method will detect all file changes and doing `git add`, `git commit -m <message>`, and `git push <branch>` all at once.
        Parameters
        ----------
        branch : str, optional
            The branch you would like to commit. Default is master
        message : str, optionl
            Commit message
        """
        has_changed = False

        # Check if there's any untracked files
        for file in self.repo.untracked_files:
            print(f'Added untracked file: {file}')
            self.repo.git.add(file)
            if has_changed is False:
                has_changed = True

        if self.repo.is_dirty() is True:
            for file in self.repo.git.diff(None, name_only=True).split('\n'):
                print(f'Added file: {file}')
                self.repo.git.add(file)
                if has_changed is False:
                    has_changed = True

        if has_changed is True:
            self.repo.git.commit('-m', message)
            # self.repo.git.push('origin', branch)
