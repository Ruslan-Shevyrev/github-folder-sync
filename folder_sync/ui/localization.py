"""Russian source strings and their English translations."""

import re
from string import Formatter


ENGLISH = {
    'Есть в обоих местах': 'Both locations',
    'Только на GitHub': 'GitHub only',
    'Только локально': 'Local only',
    'Отмена': 'Cancel',
    'Подтвердить': 'Confirm',
    'Сохранить': 'Save',
    'Сохранить как профиль': 'Save as profile',
    'Не удалось сохранить': 'Could not save',
    'Необходимо для приватных токенов': 'Required for private repositories',
    'Токен или v{ИМЯ_ПЕРЕМЕННОЙ}': 'Token or v{VARIABLE_NAME}',
    'Редактирование пользователя': 'Edit user',
    'Добавить пользователя': 'Add user',
    'Логин GitHub': 'GitHub username',
    'Токен GitHub (необязательно)': 'GitHub token (optional)',
    'Редактирование профиля': 'Edit profile',
    'Сохранение профиля': 'Save profile',
    'Имя профиля': 'Profile name',
    'Пользователь GitHub': 'GitHub user',
    'Локальная папка': 'Local folder',
    'Обзор…': 'Browse…',
    'Настройки по умолчанию': 'Default settings',
    'Папки и репозитории GitHub': 'GitHub folders and repositories',
    'Выберите папку и сохранённого пользователя GitHub.': 'Select a local folder and a saved GitHub user.',
    'Не удалось прочитать настройки: {error}': 'Could not read settings: {error}',
    'Репозитории GitHub': 'GitHub repositories',
    'Профиль': 'Profile',
    'Пользователь выбран.': 'User selected.',
    'Не удалось открыть список пользователей': 'Could not open the user list',
    'Просмотр пользователей': 'View users',
    'Этот пользователь больше не сохранён.': 'This user is no longer saved.',
    'Пользователь с таким логином уже сохранён.': 'A user with this username is already saved.',
    'Логин «{name}» сохранён.': 'Username “{name}” saved.',
    'Удаление пользователя': 'Delete user',
    'Удалить пользователя «{name}» и все связанные с ним профили?': 'Delete user “{name}” and all associated profiles?',
    'Не удалось удалить пользователя': 'Could not delete user',
    'Пользователь «{name}» и его профили удалены.': 'User “{name}” and their profiles have been deleted.',
    'Редактировать': 'Edit',
    'Удалить': 'Delete',
    'Закрыть': 'Close',
    'Введите имя профиля.': 'Enter a profile name.',
    'Укажите локальную папку.': 'Select a local folder.',
    'Выберите сохранённого пользователя GitHub.': 'Select a saved GitHub user.',
    'Этот профиль уже удалён.': 'This profile has already been deleted.',
    'Профиль с таким именем уже существует.': 'A profile with this name already exists.',
    'Профиль уже существует': 'Profile already exists',
    'Заменить профиль «{name}»?': 'Replace profile “{name}”?',
    'Профиль «{name}» сохранён.': 'Profile “{name}” saved.',
    'Укажите папку и выберите пользователя GitHub.': 'Select a folder and a GitHub user.',
    'Не удалось открыть профили': 'Could not open profiles',
    'Просмотр профилей': 'View profiles',
    'По умолчанию': 'Default',
    'Да': 'Yes',
    'Удаление профиля': 'Delete profile',
    'Удалить профиль «{name}»?': 'Delete profile “{name}”?',
    'Не удалось удалить профиль': 'Could not delete profile',
    'Профиль «{name}» удалён.': 'Profile “{name}” deleted.',
    'Выберите папку': 'Select a folder',
    'Сравнение устарело': 'Comparison is out of date',
    'Сначала повторите сравнение для выбранных настроек.': 'Compare again with the selected settings first.',
    'Не удалось перепроверить ветки.': 'Could not check branches again.',
    'Обновление строки': 'Refreshing row',
    'Удаление локальной папки': 'Delete local folder',
    'Папка, все её файлы и локальные коммиты будут удалены безвозвратно.\n\n{path}': 'The folder, all its files, and local commits will be permanently deleted.\n\n{path}',
    'Удаление': 'Deleting',
    'Создать локальную ветку': 'Create local branch',
    'Обновить через git pull': 'Update with git pull',
    'Создание ветки': 'Creating branch',
    'Мерж (git pull)': 'Pulling changes (git pull)',
    'Создать ветку': 'Create branch',
    'Обновить': 'Refresh',
    'Клонировать репозиторий': 'Clone repository',
    'Клонирование': 'Cloning',
    'Клонировать': 'Clone',
    '\nВетка: {branch_name}': '\nBranch: {branch_name}',
    'Не удалось определить адрес': 'Could not determine the URL',
    'Исправление origin': 'Fix origin',
    'Текущий origin:\n{display_origin}\n\nКоманда:\n{command}': 'Current origin:\n{display_origin}\n\nCommand:\n{command}',
    'ОК': 'OK',
    'Папка недоступна: {path}': 'Folder unavailable: {path}',
    'Не удалось открыть папку': 'Could not open folder',
    'Данные из кэша': 'Cached results',
    'Требуют внимания': 'Needs attention',
    'Нажмите «Сравнить», чтобы получить данные.': 'Click Compare to load results.',
    '  ·  Не удалось сохранить кэш.': '  ·  Could not save the cache.',
    'Обработано репозиториев: {count}': 'Repositories checked: {count}',
    'Не удалось завершить действие': 'Could not complete the action',
    'Укажите папку и выберите сохранённого пользователя GitHub.': 'Select a folder and a saved GitHub user.',
    'Сравниваем папки с репозиториями GitHub…': 'Comparing local folders with GitHub repositories…',
    'Сравнение': 'Comparing',
    'Сравнить': 'Compare',
    'Язык': 'Language',
    'Название': 'Name',
    'Статус': 'Status',
    'Видимость': 'Visibility',
    'Ветки': 'Branches',
    'Локальный путь': 'Local path',
    'Ссылка на GitHub': 'GitHub URL',
    'совпадает': 'matches',
    'только локально': 'local only',
    'только на GitHub': 'GitHub only',
    'ветки разошлись': 'branches diverged',
    'неполная история': 'incomplete history',
    'git fetch — создать локальную ветку': 'git fetch — create a local branch',
    'Локально': 'Local',
    'Локально —': 'Local —',
    'Введите токен GitHub или ссылку вида v{ИМЯ_ПЕРЕМЕННОЙ}.': 'Enter a GitHub token or a reference like v{VARIABLE_NAME}.',
    'Переменная окружения «{name}» не задана или пуста.': 'Environment variable “{name}” is missing or empty.',
    'Переменная окружения «{name}» содержит недопустимое значение токена.': 'Environment variable “{name}” contains an invalid token.',
    'Некорректный формат файла настроек.': 'Invalid settings file format.',
    'Некорректный формат токенов.': 'Invalid token format.',
    'Origin ведёт на другой репозиторий.': 'Origin points to another repository.',
    'Для проверки веток установите Git.': 'Install Git to check branches.',
    'Истекло время ожидания ответа Git.': 'Git timed out.',
    'Не удалось запустить Git.': 'Could not start Git.',
    'Git не смог прочитать ветки или их историю.': 'Git could not read the branches or their history.',
    'Токен можно передать только GitHub по HTTPS.': 'Tokens can only be sent to GitHub over HTTPS.',
    'В локальной папке нет Git-репозитория.': 'The local folder does not contain a Git repository.',
    'У локального репозитория отсутствует origin.': 'The local repository has no origin remote.',
    'Не удалось определить адрес репозитория GitHub.': 'Could not determine the GitHub repository URL.',
    'Локальный репозиторий изменился. Повторите сравнение.': 'The local repository changed. Compare again.',
    'Origin уже изменился. Повторите сравнение.': 'Origin has already changed. Compare again.',
    'Не удалось определить репозиторий GitHub.': 'Could not determine the GitHub repository.',
    'Локальная папка больше недоступна.': 'The local folder is no longer available.',
    'Origin изменился. Повторите сравнение.': 'Origin changed. Compare again.',
    'Локальная ветка изменилась. Повторите сравнение.': 'The local branch changed. Compare again.',
    'Ветка на GitHub больше недоступна. Повторите сравнение.': 'The GitHub branch is no longer available. Compare again.',
    'Это состояние ветки не поддерживает обновление.': 'This branch cannot be updated in its current state.',
    'Переключитесь на ветку «{branch_name}» в локальном репозитории и повторите обновление.': 'Switch to branch “{branch_name}” in the local repository and try again.',
    'В рабочей папке есть изменения. Сохраните их перед обновлением.': 'The working tree has changes. Save them before updating.',
    'Папка уже существует. Повторите сравнение.': 'The folder already exists. Compare again.',
    'Введите логин GitHub, например octocat.': 'Enter a GitHub username, for example octocat.',
    'Достигнут лимит запросов GitHub. Попробуйте позже.': 'The GitHub API rate limit was reached. Try again later.',
    'GitHub вернул ошибку HTTP {code}.': 'GitHub returned HTTP error {code}.',
    'Не удалось загрузить репозитории. Проверьте подключение к GitHub.': 'Could not load repositories. Check your connection to GitHub.',
    'Токен GitHub принадлежит другому пользователю.': 'The GitHub token belongs to another user.',
    'Аккаунт GitHub «{login}» не найден.': 'GitHub account “{login}” was not found.',
    'Локальная папка «{root}» недоступна.': 'Local folder “{root}” is unavailable.',
    'Папка находится вне каталога сравнения.': 'The folder is outside the comparison directory.',
    'Выбранный путь не является обычной локальной папкой.': 'The selected path is not a regular local folder.',
    'Не удалось прочитать папку «{root}».': 'Could not read folder “{root}”.',
}


LANGUAGES = {"ru": "Русский", "en": "English"}
_language = "ru"


def set_language(language):
    global _language
    _language = language


def tr(message, **values):
    text = ENGLISH.get(message, message) if _language == "en" else message
    return text.format(**values) if values else text


def error_text(message):
    if _language != "en":
        return message
    if message in ENGLISH:
        return ENGLISH[message]
    for pattern, english in ERROR_PATTERNS:
        match = pattern.fullmatch(message)
        if match:
            return english.format(**match.groupdict())
    return message


ERROR_PATTERNS = [
    (re.compile("".join(re.escape(text) + (f"(?P<{field}>.+?)" if field else "")
                        for text, field, _, _ in Formatter().parse(source))), english)
    for source, english in ENGLISH.items()
    if "{" in source and "v{" not in source and "\n" not in source
]
