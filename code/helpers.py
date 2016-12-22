import asyncio
import json
import logging.handlers

import discord

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

# We check if the user wants to use email to report errors
if config["log_config"]["use_email_notifications"]:
    # We create the SMTP loghandler with the proper settings from the config
    mail_notification_handler = logging.handlers.SMTPHandler((config["log_config"]["email_settings"]["smtp_server"],
                                                              config["log_config"]["email_settings"][
                                                                  "smtp_port"]),
                                                             config["log_config"]["email_settings"]["from_address"],
                                                             config["log_config"]["email_settings"]["send_to"],
                                                             config["log_config"]["email_settings"]["subject"],
                                                             credentials=(
                                                             config["log_config"]["email_settings"]["username"],
                                                             config["log_config"]["email_settings"]["password"]),
                                                             secure=())

    # We change the level so it only sends emails about warnings or errors
    mail_notification_handler.setLevel(logging.WARNING)
    # We change the formatter to the formatter we use in the file handler
    mail_notification_handler.setFormatter(handler.formatter)

    # We add the mail handler to the logger
    logger.addHandler(mail_notification_handler)


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


def log_ob(dis_object) -> str:
    """This method returns a string that contains the passed object's name and id, in the format of '{0} ({1})'.format(object.name, object.id)."""
    return "{0} ({1})".format(dis_object.name, dis_object.id)


async def remove_roles(client: discord.Client, member: discord.Member, roles: list):
    """This function is used to remove all roles from a list from a user until the user does not have any of those roles, or the max retries have been attempted.
    This raises Forbidden if the client does not have permissions to remove roles from the target user.
    May also raise HTTPException if the network operations failed."""

    # We basically work with the assumption that local membership operations are a lot faster than discord network operations

    # The duration to wait between each batch of role removals
    role_removal_cooldown = 0.1

    # We remove the roles a user has. We do this multiple times or until the user no longer has any of the roles (as doing it once is not reliable)
    for i in range(5):

        # We check if the user has any of the roles (just so we don't need to issue a network operation)
        # We check if the two lists (the member's roles and the removal roles) share any elements
        if any(x in max(roles, member.roles, key=len) for x in
               min(roles, member.roles, key=len)):
            # We remove all the roles from the user
            for role in [x for x in roles if x in member.roles]:
                await client.remove_roles(member, role)

            # We wait so we don't get rate limited, and so we have time to receive the updated member
            await asyncio.sleep(role_removal_cooldown)

        else:
            # We have removed all the roles
            i -= 1
            break

    # We log how many retries it took to remove the roles from the user
    log_info(
        "Removing roles from user {0} took {1} retries.".format(log_ob(member), i))


def check_add_remove_roles(member: discord.Member, channel: discord.Channel) -> bool:
    """This method returns true if the currently logged in client can remove and add roles from the passed member in the passed channel."""

    return channel.permissions_for(
        channel.server.me).manage_roles and member.top_role.position < member.server.me.top_role.position


def remove_anna_mention(client: discord.Client, message):
    """This function is used to remove the first part of an anna message so that the command code can more easily parse the command"""

    # The weird mention for the bot user, the string manipulation is due to mention strings not being the same all the time
    client_mention = client.user.mention[:2] + "!" + client.user.mention[2:]

    # We check if the input is a message or just a string
    if isinstance(message, discord.Message):
        content = message.content
    else:
        content = message

    # We first check if discord is fucking with us by using the weird mention
    if content.lstrip().startswith(client_mention):
        # Removing the anna bot mention in the message so we can parse the arguments more easily
        cleaned_message = content.lstrip()[len(client_mention) + 1:]
    else:
        # Removing the anna bot mention in the message so we can parse the arguments more easily
        cleaned_message = content.lstrip()[len(client.user.mention) + 1:]

    return cleaned_message


def is_message_command(message: discord.Message, client):
    """This function is used to check whether a message is trying to issue an anna-bot command"""

    # The weird mention for the bot user, the string manipulation is due to mention strings not being the same all the time
    client_mention = client.user.mention[:2] + "!" + client.user.mention[2:]

    # We return if the message is a command or not
    return message.content.lower().strip().startswith(client_mention) or message.content.lower().strip().startswith(
        client.user.mention)
