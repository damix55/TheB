from github import Github
import keys

key = keys.GITHUB
repo_path = keys.REPO
repo = Github(key).get_repo(repo_path)
repo_url = 'https://github.com/' + repo_path

def get_repo():
    return repo

def write(path, data, message, branch):
    #Updates existing file
    try:
        contents = repo.get_contents(path, ref=branch)
        return repo.update_file(path, message, data, contents.sha, branch=branch)

    #Create file if it doesn't exist
    except:
        return repo.create_file(path, message, data, branch=branch)

def create_branch(target_branch):
    source_branch = 'master'
    sb = repo.get_branch(source_branch)
    return repo.create_git_ref(ref='refs/heads/' + target_branch, sha=sb.commit.sha)

def branch_exists(branch):
    try:
        repo.get_branch(branch)
        return True
    except:
        return False

def delete_branch(branch):
    gref = repo.get_git_ref(ref='heads/' + branch)
    return gref.delete()

def create_pull(*args, **kwargs):
    return repo.create_pull(*args, **kwargs)

def get_pull(*args, **kwargs):
    return repo.get_pull(*args, **kwargs)

def get_pulls(*args, **kwargs):
    return repo.get_pulls(*args, **kwargs)

def pull_get_files(pr):
    return pr.get_files()

def pull_get_issue_comments(pr):
    return pr.get_issue_comments()

def pull_merge(pr, *args, **kwargs):
    pr.merge(*args, **kwargs)

def pull_edit(pr, *args, **kwargs):
    pr.edit(*args, **kwargs)

def load_dir(path, branch):
    try:                                        # To avoid errors when the directory doesn't exist anymore in GitHub
        contents = repo.get_contents(path, ref=branch)
        files = []
        while len(contents) > 0:                # Loads recursively all the files in the path
            file_content = contents.pop(0)
            if file_content.type == 'dir':      # If it is a directory, then load the content inside
                contents.extend(repo.get_contents(file_content.path, ref=branch))
            else:
                files.append(file_content)
    except:
        return []

    return files

def delete_folder(path, branch, message):
    for f in load_dir(path, branch):
        repo.delete_file(f.path, message, f.sha, branch=branch)

def move(old_path, new_path, branch, message):
    for f in load_dir(old_path, branch):
        path = f.path.replace(old_path, new_path)
        write(path, f.decoded_content, message, branch)
    delete_folder(old_path, branch, message)

def path_exists(path, branch):
    try:
        contents = repo.get_contents(path, ref=branch)
        return True
    except:
        return False

def get_file(path, branch):
    try:
        return repo.get_file_contents(path, ref=branch).decoded_content
    except:
        return ''
