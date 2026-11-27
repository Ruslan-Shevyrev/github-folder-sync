# GitHub Folder Sync

[Читать на русском](README.ru.md)

A Windows desktop utility for comparing local project folders with GitHub repositories. See which repositories exist locally or on GitHub, compare branch commits, and pull or clone from the same table.

## Download and run

When a release is available, download `GitHubFolderSync-{VERSION}-windows-x64.zip` from [GitHub Releases](https://github.com/Ruslan-Shevyrev/github-folder-sync/releases). Extract the entire archive and open `GitHubFolderSync.exe`. The portable build runs without a separate Python installation. Install Git and make sure it is in `PATH` to check branches and run Git operations.

## How to use

1. Click **Add user**, enter your GitHub username, and select the saved user.
2. Choose a **Local folder** with **Browse…**, or enter its path. The app matches the immediate subfolders to repository names without regard to case.
3. Click **Compare**. The table shows each repository's location, GitHub visibility, and branch status. Select **Needs attention** to show only missing counterparts, branch differences, and errors.
4. Click **Save as profile** to keep the folder and user together. Mark a profile as the default to load it at startup. Use **View users** and **View profiles** to manage saved entries.

The top-right menus switch between Russian and English and between **Dark** and **Light**. The app remembers both choices. The first launch uses the dark theme.

## Branches and row actions

- **Green** means the branch points to the same commit on both sides. **Red** marks the side that is behind. **Yellow** marks the side that is ahead or the only side with the branch. **Gray** marks diverged branches or an incomplete history.
- **↻** refreshes one row. **↓** clones a missing repository, creates a missing local branch, or pulls into a local branch that is behind. Pull uses `git pull --ff-only` and requires the target branch to be checked out with a clean working tree. The arrows in the branch column indicate direction.
- **Trash** deletes the local folder and its contents permanently after confirmation.
- Click a local path to open it in File Explorer or a GitHub URL to open it in your browser. If Git reports that `origin` points to another repository, click the message to review the current URL and confirm the correction.

## Private repositories

Public repositories are available without a token. To access private repositories, add a fine-grained GitHub personal access token to the saved user. Give it access to the relevant repositories and **Contents: Read** for checking branches, cloning, and pulling.

Enter the token directly or use `v{VARIABLE_NAME}` to read it from a Windows environment variable. A directly entered token is stored as plain text in the local settings file. The variable option stores only the reference. Profiles that select the same user share that user's token.

## Settings and cache

The app stores settings in `settings/settings.json` and the last comparison for each profile in `cache/`, next to the EXE or in the project root when running from source. Git ignores both folders.

Selecting a profile with a saved result opens its table immediately and shows **Cached results** above it. Click **Compare** for fresh results. The **Needs attention** filter works on the loaded table without contacting GitHub.

## Run from source

Run these commands from the project root in PowerShell with Python 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe github_folder_sync.py
```

The interface uses CustomTkinter. The app calls the system Git for branch comparisons and repository operations.

## Build for Windows x64

The build requires 64-bit Python. The script installs dependencies in `.venv` and packages the app with PyInstaller.

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
.\dist\GitHubFolderSync\GitHubFolderSync.exe
```

To build a ZIP for distribution, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1 -Zip -Version v{VERSION}
```

This creates `distGitHubFolderSync-v{VERSION}-windows-x64.zip`.

<table>
	<tr>
		<td valign="center" width="49%"><img src="https://github.com/Ruslan-Shevyrev/Ruslan-Shevyrev/blob/main/logoRS/logo_mini.gif" title="logo"></td>
		<td valign="center" width="49%"><img src="https://github.com/Ruslan-Shevyrev/Ruslan-Shevyrev/blob/main/logoRS/logoRS_FULL.png" title="RuslanShevyrev"></td>
	</tr>
</table>