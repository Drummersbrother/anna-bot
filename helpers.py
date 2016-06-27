import json
import logging

# Setting up logging with the built in discord.py logger
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# We load the log file depending on what log file filename the user has specified in the config
with open("config.json", mode="r", encoding="utf-8") as config_file:
    config = json.load(config_file)
    handler = logging.FileHandler(filename=config["logging"]["log_file_name"], encoding='utf-8', mode='a')

# Continuing the logger setup
handler.setFormatter(logging.Formatter('%(asctime)s: %(levelname)s: %(name)s: %(message)s'))
logger.addHandler(handler)


def get_formatted_duration_fromtime(duration_seconds_noformat):
    # How many weeks the duration is
    duration_weeks = duration_seconds_noformat // (7 * 24 * 3600)

    # Subtracting the weeks from the unformatted seconds
    duration_seconds_noformat %= (7 * 24 * 3600)

    # How many days duration is
    duration_days = duration_seconds_noformat // (24 * 3600)

    # Subtracting the days from the unformatted seconds
    duration_seconds_noformat %= (24 * 3600)

    # How many hours the duration is
    duration_hours = duration_seconds_noformat // (3600)

    # Subtracting the hours from the unformatted seconds
    duration_seconds_noformat %= 3600

    # How many minutes the duration is
    duration_minutes = duration_seconds_noformat // 60

    # Subtracting the minutes from the unformatted seconds
    duration_seconds_noformat %= 60

    # Creating the formatted duration string
    formatted_duration = "%i weeks, %i days, %i hours, %i minutes, and %i seconds" % (
        duration_weeks, duration_days, duration_hours, duration_minutes, duration_seconds_noformat)

    return formatted_duration


def log_text(text, level):
    print(text)
    logger.log(level, text)


def log_debug(text):
    log_text(text, 10)


def log_info(text):
    log_text(text, 20)


def log_warning(text):
    log_text(text, 30)


def log_error(text):
    log_text(text, 40)


def log_critical(text):
    log_text(text, 50)
