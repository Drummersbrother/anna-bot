import asyncio
import concurrent.futures
import json
import time

import aiohttp
import async_timeout
import discord
import websockets.exceptions

import main_code.command_decorator
import main_code.commands.admin.broadcast
import main_code.commands.admin.change_icon
import main_code.commands.admin.list_referrals
import main_code.commands.regular.gen_bot_invite
import main_code.commands.regular.invite_link
import main_code.commands.regular.list_ids
import main_code.commands.regular.report_stats
import main_code.commands.regular.start_server
import main_code.commands.regular.vanity_role_commands
import main_code.commands.regular.voice_commands_playlist
import main_code.commands.regular.warning_commands
import main_code.commands.regular.who_r_u
from main_code import helpers

if __name__ == "__main__":
    # Setting up the client object
    client = helpers.actual_client


# TODO Handle group calls and messages, and/or move to the commands extension
# TODO think about adding a last-online webpage/webserver

@client.event
async def on_message(message: discord.Message):
    # We wait for a split second so we can be assured that ignoring of messages and other things have finished before the message is processed here
    # We make sure the message is a regular one
    if message.type != discord.MessageType.default:
        return

    await asyncio.sleep(0.1)

    global config

    # The weird mention for the bot user (mention code starts with an exclamation mark instead of just the user ID), the string manipulation is due to mention strings not being the same all the time
    client_mention = client.user.mention[:2] + "!" + client.user.mention[2:]

    # Log the message using proper formatting techniques (and some sanity checking so we log our own sent messages separately)
    if not message.author.name == client.user.name:
        # We check if we should ignore the message
        if message.author.name not in config["log_config"]["ignored_log_user_names"]:
            # Someone sent a message in a server or channel we have joined / have access to
            if message.channel.is_private:
                helpers.log_info(message.author.name + " said: \"" + message.content + "\" in a PM.")
            else:
                if message.channel.name not in config["log_config"]["ignored_log_channels"]:
                    helpers.log_info(
                        message.author.name + " said: \"" + message.content + "\" in channel: \"" + message.channel.name + "\" on server \"" + message.server.name + "\".")

            # We check if there were any attachments to the message, and if so, we log all the relevant info we can get about the attachment
            if message.attachments:
                # We log that the user sent attachments
                helpers.log_info("{0:s} attached {1:d} file(s)".format(message.author.name, len(message.attachments)))

                # We loop through all the attachments
                for attachment in message.attachments:
                    # We check for the image/video-like attributes width and height (in pixels obviously) and we output them if they exist
                    if ("width" in attachment) and ("height" in attachment):
                        # We log the attachment as an image/video-like file
                        helpers.log_info(
                            "User {0:s} attached image/video-like file \"{1:s}\" of dimensions X: {2:d} and Y: {3:d} and filesize {4:d} bytes.".format(
                                message.author.name, attachment["filename"], attachment["width"], attachment["height"],
                                attachment["size"]))

                    else:
                        # We log the attachment as a unknown filetype
                        helpers.log_info(
                            "User {0:s} attached file \"{1:s}\" of filesize {2:d} bytes.".format(
                                message.author.name, attachment["filename"], attachment["size"]))

    else:
        # We sent a message and we are going to increase the sent messages counter in the config
        # We first load the config
        with open("config.json", mode="r", encoding="utf-8") as config_file:
            current_config = json.load(config_file)

        # Now we change the actual value and then dump it back into the file
        current_config["stats"]["messages_sent"] += 1

        with open("config.json", mode="w", encoding="utf-8") as config_file:
            # Dump back the changed data
            json.dump(current_config, config_file, indent=2)

        # We sent a message and we are going to log it appropriately
        if message.channel.is_private:
            helpers.log_info("We said: \"" + message.content + "\" in a PM to " + message.channel.user.name + ".")
        else:
            if message.channel.name not in config["log_config"]["ignored_log_channels"]:
                helpers.log_info(
                    "We said: \"" + message.content + "\" in channel: \"" + message.channel.name + "\" on server \"" + message.server.name + "\".")

    # Checking if the user used a command, but we first wait to make sure that the message gets ignored if necessary
    await asyncio.sleep(0.4)

    # We need to define all the special params as globals to be able to access them without sneaky namespace stuff biting us in the ass
    global ignored_command_message_ids

    # We define the list of special parameters that may be sent to the message functions, and also have to be returned from them (in a list)
    special_params = [ignored_command_message_ids, config]

    # Checking if we sent the message, so we don't trigger ourselves and checking if the message should be ignored or not (such as it being a response to another command)
    # We also check if the message was sent by a bot account, as we don't allow them to use commands
    if not ((message.author.id == client.user.id) or (message.id in ignored_command_message_ids) or message.author.bot):
        # If a command is used with the message that was passed to the event, we know that a command has been triggered
        used_command = False

        # Check if the message was sent in a PM to anna
        if message.channel.is_private:

            # Going through all the public commands we've specified and checking if they match the message
            for command in public_commands:
                if message.content.lower().strip().startswith(command["command"]):
                    # We log what command was used by who
                    helpers.log_info("The " + command[
                        "command"] + " command was triggered by \"" + message.author.name + "\" in a PM.")

                    # The command matches, so we call the method that was specified in the command list
                    temp_result = await command["method"](message, client, config,
                                                          *[x[0] for x in
                                                            zip(special_params,
                                                                command["special_params"])
                                                            if x[1]])
                    x = 0
                    # We put back all the values that we got returned
                    if temp_result:
                        for i in range(len(special_params)):
                            if command["special_params"][i]:
                                set_special_param(i, temp_result[x])
                                x += 1

                    # We note that a command was triggered so we don't output the message about what "!" means
                    used_command = True
                    break

            # Checking if the issuing user is in the admin list
            if helpers.is_member_anna_admin(message.author, config):

                # Going through all the admin commands we've specified and checking if they match the message
                for command in admin_commands:
                    if message.content.lower().strip().startswith("admin " + command["command"]):
                        # We log what command was used by who
                        helpers.log_info("The " + command[
                            "command"] + " admin command was triggered by admin \"" + message.author.name + "\" in a PM.")

                        # The command matches, so we call the method that was specified in the command list
                        temp_result = await command["method"](message, client, config, *[x[0] for x in
                                                                                         zip(special_params,
                                                                                             command["special_params"])
                                                                                         if x[1]])
                        x = 0
                        # We put back all the values that we got returned
                        if temp_result:
                            for i in range(len(special_params)):
                                if command["special_params"][i]:
                                    set_special_param(i, temp_result[x])
                                    x += 1

                        # We note that a command was triggered so we don't output the message about what anna can do
                        used_command = True
                        break

            # If the message started with an command trigger and it didn't have a valid command we try to teach the user which commands are available
            if not used_command:
                # Sending the message to the user
                await client.send_message(message.channel,
                                          "You seemingly just tried to use an anna-bot command, but I couldn't figure out which one you wanted to use, if you want to know what commands I can do for you, please type \"" + client_mention + " help\" :smile:")
            else:
                # If the message was a command of any sort, we increment the commands received counter on anna
                # We first load the config
                with open("config.json", mode="r", encoding="utf-8") as config_file:
                    current_config = json.load(config_file)

                # Now we change the actual value and then dump it back into the file
                current_config["stats"]["commands_received"] += 1

                with open("config.json", mode="w", encoding="utf-8") as config_file:
                    # Dump back the changed data
                    json.dump(current_config, config_file, indent=2)

        # We're in a regular server channel
        else:
            # Checking if the message is a command, (starts with a mention of anna)
            if helpers.is_message_command(message, client):
                # Going through all the public commands we've specified and checking if they match the message
                for command in public_commands:
                    if helpers.remove_anna_mention(client, message).lower().strip().startswith(
                            command["command"]):
                        # We log what command was used by who and where
                        helpers.log_info("The " + command[
                            "command"] + " command was triggered by \"" + message.author.name + "\" in channel \"" + message.channel.name + "\" on server \"" + message.server.name + "\".")

                        # The command matches, so we call the method that was specified in the command list
                        temp_result = await command["method"](message, client, config, *[x[0] for x in
                                                                                         zip(special_params,
                                                                                             command["special_params"])
                                                                                         if x[1]])
                        x = 0
                        # We put back all the values that we got returned
                        if temp_result:
                            for i in range(len(special_params)):
                                if command["special_params"][i]:
                                    set_special_param(i, temp_result[x])
                                    x += 1

                        # We note that a command was triggered so we don't output the message about what anna can do
                        used_command = True
                        break

                # Checking if the issuing user is in the admin list
                if helpers.is_member_anna_admin(message.author, config):
                    # Going through all the admin commands we've specified and checking if they match the message
                    for command in admin_commands:
                        if helpers.remove_anna_mention(client, message).lower().strip().startswith(
                                        "admin " + command["command"]):

                            # We check if the command was triggered in a private channel/PM or not
                            if message.channel.is_private:

                                # We log what command was used by who
                                helpers.log_info("The " + command[
                                    "command"] + " admin command was triggered by admin \"" + message.author.name + "\" in a PM.")

                            else:
                                # We log what command was used by who and where
                                helpers.log_info("The " + command[
                                    "command"] + " admin command was triggered by admin \"" + message.author.name + "\" in channel \"" + message.channel.name + "\" on server \"" + message.server.name + "\".")

                            # The command matches, so we call the method that was specified in the command list
                            temp_result = await command["method"](message, client, config, *[x[0] for x in
                                                                                             zip(special_params,
                                                                                                 command[
                                                                                                     "special_params"])
                                                                                             if x[1]])
                            x = 0
                            # We put back all the values that we got returned
                            if temp_result:
                                for i in range(len(special_params)):
                                    if command["special_params"][i]:
                                        set_special_param(i, temp_result[x])
                                        x += 1

                            # We note that a command was triggered so we don't output the message about what anna can do
                            used_command = True
                            break

                # If the message started with an command trigger and it didn't have a valid command we try to teach the user which commands are available
                if not used_command:
                    # Sending the message to the user
                    await client.send_message(message.channel,
                                              message.author.mention + ", you seemingly just tried to use an anna-bot command, but I couldn't figure out which one you wanted to use, if you want to know what commands I can do for you, please type \"" + client_mention + " help\" :smile:")
                else:
                    # If the message was a command of any sort, we increment the commands received counter on anna
                    # We first load the config
                    with open("config.json", mode="r", encoding="utf-8") as config_file:
                        current_config = json.load(config_file)

                    # Now we change the actual value and then dump it back into the file
                    current_config["stats"]["commands_received"] += 1

                    with open("config.json", mode="w", encoding="utf-8") as config_file:
                        # Dump back the changed data
                        json.dump(current_config, config_file, indent=2)

                    # We remove stream players that are done playing, as this is done on every command and every commands can only create at most 1 stream player, we guarantee no memory leak
                    server_and_stream_players[:] = [x for x in server_and_stream_players if not x[1].is_done()]

    else:
        # Checking if we didn't check if the message was a command because the message id was in the ignored ids list
        if message.id in ignored_command_message_ids:
            # We remove the ignored id from the list so we don't accumulate ids to check against
            ignored_command_message_ids.remove(message.id)


@client.event
async def on_member_join(member: discord.Member):
    """This event is called when a member joins a server, we use it for various features."""

    # We wait as to not do stuff before the user has actually joined the server
    await asyncio.sleep(0.2)

    # We log that a user has joined the server
    helpers.log_info(
        "User {0:s} ({1:s}) has joined server {2:s} ({3:s}).".format(member.name, member.id, member.server.name,
                                                                     member.server.id))

    # We call all the join functions, and pass them the member who joined
    for join_function in join_functions:
        await join_function(member)


@client.event
async def on_member_remove(member: discord.Member):
    """This event is called when a member leaves a server, we use it for various features."""

    # We log that a user has left the server
    helpers.log_info(
        "User {0:s} ({1:s}) has left server {2:s} ({3:s}).".format(member.name, member.id, member.server.name,
                                                                   member.server.id))

    # We check if the server is on the list of servers who use the leave message feature
    if int(member.server.id) in [x[0] for x in config["leave_msg"]["server_and_channel_id_pairs"]]:

        # We send a message to the specified channels in that server (you can have however many channels you want, but we check if they are on the correct server)
        channel_ids = \
            [x[1:] for x in config["leave_msg"]["server_and_channel_id_pairs"] if x[0] == int(member.server.id)][0]

        # We loop through all the possible channels and check if they're valid
        for channel_id in [int(x) for x in channel_ids]:
            # We check if the channel id is on the server that the member left
            if discord.utils.find(lambda c: int(c.id) == channel_id, member.server.channels) is not None:
                # We send the leave message:
                await client.send_message(discord.utils.find(lambda c: int(c.id) == channel_id, member.server.channels),
                                          config["leave_msg"]["leave_msg"].format(member.mention, member.server.name))


@client.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """This method handles people updating their status and such, it needs to run fast to not be a performance hog."""
    # We check if the user update is someone changing their online-status from not-offline to offline
    if (before.status != discord.Status.offline and after.status == discord.Status.offline) and (
    config["webserver_config"]["use_webserver"]):
        # We add the user to the last-online-list dict
        # We get the server list index of the server we want to add this user's info to
        info_dict_servers_index = [inx for inx, x in enumerate(last_online_time_dict["servers"]) if
                                   x["server_id"] == after.server.id]

        # We check if the server that the user is on exists
        if not info_dict_servers_index:
            # We add an entry for the new server
            info_dict_servers_index = len(last_online_time_dict["servers"])
            last_online_time_dict["servers"].append({"server_id": after.server.id, "users": []})
        else:
            info_dict_servers_index = info_dict_servers_index[0]

        # We add the user info to the server entry

        # We check if the user already has an entry
        info_dict_users_index = [inx for inx, x in
                                 enumerate(last_online_time_dict["servers"][info_dict_servers_index]["users"]) if
                                 x.get("username", "") == "#".join((after.name, str(after.discriminator)))]

        if not info_dict_users_index:
            # We add an entry for the new user
            info_dict_users_index = len(last_online_time_dict["servers"][info_dict_servers_index]["users"])
            last_online_time_dict["servers"][info_dict_servers_index]["users"].append({})
        else:
            info_dict_users_index = info_dict_users_index[0]

        # We actually add the data
        last_online_time_dict["servers"][info_dict_servers_index]["users"][info_dict_users_index][
            "username"] = "#".join((after.name, str(after.discriminator)))
        last_online_time_dict["servers"][info_dict_servers_index]["users"][info_dict_users_index][
            "icon_url"] = after.avatar_url if after.avatar_url is not "" else after.default_avatar_url
        last_online_time_dict["servers"][info_dict_servers_index]["users"][info_dict_users_index][
            "last_seen_time"] = time.asctime(time.gmtime())


async def join_welcome_message(member: discord.Member):
    """This function is called when a user joins a server, and welcomes them if the server has enabled the welcome message feature."""

    # We check if the server is on the list of servers who use the welcome message feature
    if int(member.server.id) in [x[0] for x in config["join_msg"]["server_and_channel_id_pairs"]]:

        # We send a message to the specified channels in that server (you can have however many channels you want, but we check if they are on the correct server)
        channel_ids = \
            [x[1:] for x in config["join_msg"]["server_and_channel_id_pairs"] if x[0] == int(member.server.id)][0]

        # We loop through all the possible channels and check if they're valid
        for channel_id in [int(x) for x in channel_ids]:
            # We check if the channel id is on the server that the member joined
            if discord.utils.find(lambda c: int(c.id) == channel_id, member.server.channels) is not None:
                # We send the welcome message:
                await client.send_message(discord.utils.find(lambda c: int(c.id) == channel_id, member.server.channels),
                                          config["join_msg"]["welcome_msg"].format(member.mention, member.server.name))


async def join_automatic_role(member: discord.Member):
    """This function is called when a user joins a server and puts the user in a default role if the server has enabled the automatic role feature."""

    # We check if the user joined a server that has enabled the automatic role moving feature
    if int(member.server.id) in [x[0] for x in config["default_role"]["server_and_default_role_id_pairs"]]:

        # Logging that we're going to try putting the new user into the default role for the server
        helpers.log_info(
            "Going to try putting user {0:s} ({1:s}) in default role for server {2:s} ({3:s}).".format(member.name,
                                                                                                       member.id,
                                                                                                       member.server.name,
                                                                                                       member.server.id))

        # We store the role that we want to move the new user into
        target_role = discord.utils.get(member.server.roles, id=
        str([x[1] for x in config["default_role"]["server_and_default_role_id_pairs"] if x[0] == int(member.server.id)][
                0]))

        # The user has joined a server where we should put them into a role, so we check if we have the permission to do that (if we are higher up in the role hierarchy than the user and the target role and if we have the manage roles permission)
        if (max([x.position for x in member.server.me.roles]) > max([x.position for x in member.roles])) and (
                    max([x.position for x in member.server.me.roles]) > target_role.position):

            # We check if we have the manage roles permission
            if member.server.me.server_permissions.manage_roles:
                # Logging that we're putting the user in the target role
                helpers.log_info(
                    "Putting user {0:s} ({1:s}) into role {2:s} ({3:s}) which is the default role for server {4:s} ({5:s}).".format(
                        member.name,
                        member.id,
                        target_role.name,
                        target_role.id,
                        member.server.name,
                        member.server.id))

                # We have all the appropriate permissions to move the user to the target role, so we do it :)
                await client.add_roles(member, target_role)


async def join_referral_asker(member: discord.Member):
    """This function is called when a user joins a server, and asks the user if they were invited / referred to the server by another user on the server."""

    # We check if the server has enabled referrals
    if str(member.server.id) in config["referral_config"]:
        retried = False

        # We loop until we've got a correct answer or been ignored until the timeout
        while True:
            # We check if this is the first time we ask or not
            if not retried:
                # We PM the user and ask them who referred them (if anyone)
                await client.send_message(member,
                                          "Hi {0:s}! I'm a bot on **{1}**, which you just joined, and I want to know if someone referred you to **{1}**.\nIf so, please tell me within {2} minutes, by responding with \"*referrer: <REFERRER'S USERNAME#DISCRIMINATOR>*\", *\"referrer: <REFERRER'S NICK ON {1}>\"*, or just ignore this if you weren't referred by anyone.".format(
                                              member.name, member.server.name,
                                              config["referral_config"][str(member.server.id)]["referral_timeout_min"]))
            else:
                # We PM the user and ask them to try again
                await client.send_message(member,
                                          "That user does not exist on **{0}**, please try again, or ignore until the timeout".format(
                                              member.server.name))

            # We create a function that checks if a message is a referrer answer
            check_response = lambda x: x.content.lower().strip().startswith("referrer: ") and len(
                x.content.lower().strip()) > len("referrer: ")

            # We wait for a response, if we don't get one within the configured number of minutes we just exit
            response_message = await client.wait_for_message(
                timeout=config["referral_config"][str(member.server.id)]["referral_timeout_min"] * 60, author=member,
                channel=client.get_channel(member.id), check=check_response)

            # We check if we got a response, if not, we exit
            if response_message:

                # We add the message to the "messages to ignore" list
                ignored_command_message_ids.append(response_message.id)

                # We check if the user specified in the response exists on the server that the user joined
                referrer = member.server.get_member_named(response_message.content.strip()[len("referrer: "):])

                if referrer:

                    # We load the referrals file
                    with open("referrals.json", mode="r", encoding="utf-8") as referrals_file:
                        referrals = json.load(referrals_file)

                    # We check if the server exists in the referrals data
                    if not str(member.server.id) in referrals["servers"]:
                        # We add the server to the servers list (in the referrals data)
                        referrals["servers"][str(member.server.id)] = {"been_referred": {}, "have_referred": []}

                    # We check if the referring user has referred before, if they have, we tell them that they have already referred and exit
                    if not member.id in referrals["servers"][str(member.server.id)]["have_referred"]:

                        # We check if we should announce that a user has been referred
                        if config["referral_config"][str(member.server.id)]["announce_channel_id"] != 0:
                            # We get and check that the announce channel id is valid
                            announce_channel = client.get_channel(
                                config["referral_config"][str(member.server.id)]["announce_channel_id"])

                            if announce_channel is not None:
                                if announce_channel.server.id == member.server.id:
                                    # We send the announcement that a user has been referred
                                    await client.send_message(announce_channel,
                                                              "{0} has been referred by {1}! :tada::tada::tada:".format(
                                                                  referrer.mention, member.mention))

                        # We check if the referrer exists in the server referrals data
                        if not str(referrer.id) in referrals["servers"][str(member.server.id)]["been_referred"]:
                            # We add the referrer to the server referrals data
                            referrals["servers"][str(member.server.id)]["been_referred"][str(referrer.id)] = 1

                        else:
                            # If the user already exists in the data we just increment the number of times the user has been referred
                            referrals["servers"][str(member.server.id)]["been_referred"][str(referrer.id)] += 1

                        # We add the referred to the "have_referred" list
                        referrals["servers"][str(member.server.id)]["have_referred"].append(member.id)

                        # We log that the referred has referred the referrer
                        helpers.log_info(
                            "User {0} has referred user {1} to server {2}.".format(member.name, referrer.name,
                                                                                   member.server.name))

                        # We tell the user that their referral has been registered
                        await client.send_message(member, "Ok, your referral has been registered.")

                        # We call the referral reward function and pass the referrer and the number of referrals that member now has
                        await referral_reward_handler(referrer,
                                                      referrals["servers"][str(member.server.id)]["been_referred"][
                                                          str(referrer.id)])

                    else:
                        # We tell the user that they have already referred before, and then we exit
                        await client.send_message(member,
                                                  "You have already referred a user on {0}, and you can not do that again.".format(
                                                      member.server.name))

                    # We write the modified referrals back to the file
                    with open("referrals.json", mode="w", encoding="utf-8") as referrals_file:
                        json.dump(referrals, referrals_file, indent=2, sort_keys=True)

                else:
                    # The user did not exist on the server, we try again
                    retried = True
                    continue

            else:
                # We tell the user that the referral period has ended
                await client.send_message(member,
                                          "The referral timeout has been reached, you can no longer refer someone (for **{0}**, does not apply to other servers)".format(
                                              member.server.name))

            # If we haven't redone the loop by now we exit the loop
            break


async def referral_reward_handler(member: discord.Member, num_refs: int):
    """This method is used to (according to the config) reward users with roles once they get a certain amount of referrals."""

    # We make a list of all the roles that we need to be higher than in the role hierarchy
    reward_roles = {int(x): discord.utils.get(member.server.roles, id=int(
        config["referral_config"][str(member.server.id)]["referral_rewards"][x])) for x in
                    config["referral_config"][str(member.server.id)]["referral_rewards"] if
                    x.isdigit() and discord.utils.get(member.server.roles, id=int(
                        config["referral_config"][str(member.server.id)]["referral_rewards"][x])) is not None}

    # We check if there are any reward roles at all
    if len(reward_roles) > 0:
        # We store the highest hierarchy position of the reward roles
        max_reward_role_position = max([reward_roles[x].position for x in reward_roles])

        # We check if we have the proper permissions to add and remove all the roles that can be gotten from referrals
        if (member.server.me.top_role.position > member.top_role.position) and (
                    member.server.me.top_role.position > max_reward_role_position):

            # We check if we have the manage roles permission
            if member.server.me.server_permissions.manage_roles:

                # We have all the permissions we need, so we get the role for the current referral level. If there isn't a reward for the current referral level, we exit, as we know that we have already given the user the reward
                if num_refs in reward_roles:
                    current_reward_role = reward_roles[num_refs]

                    # We log that we're going to move a user to a higher level reward role
                    helpers.log_info(
                        "Moving user {0} to role {1} on server {2} because user reached {3} referrals.".format(
                            member.name,
                            current_reward_role.name,
                            member.server.name,
                            num_refs))

                    # We make a list of all the reward roles under the current level so we can remove them. We can't just remove the previous role here, as the timespans for referrals may be quite large, and the config may therefore have changed in ways that require us to use all previous roles.
                    prev_reward_roles = [x for i, x in reward_roles if i < num_refs and x in member.roles]

                    # We remove all the previous roles
                    await client.remove_roles(member, *prev_reward_roles)

                    # We add the current reward level's role
                    await client.add_roles(member, current_reward_role)


@main_code.command_decorator.command("help", "Do I really need to explain this...")
async def cmd_help(message: discord.Message, passed_client: discord.Client, passed_config: dict):
    """This method is called to handle someone needing information about the commands they can use anna for.
    Because of code simplicity this is one of the command functions that needs to stay in the __init__py file."""

    # We need to create the helptexts dynamically and on each use of this command as it depends on the bot user mention which needs the client to be logged in

    # The correct mention for the bot user, the string manipulation is due to mention strings not being the same depending on if a user or the library generated it
    client_mention = passed_client.user.mention[:2] + "!" + passed_client.user.mention[2:]

    # Generating the combined and formatted helptext of all the public commands (we do this in <2000 char chunks, as 2000 chars is the max length of a discord message)
    public_commands_helptext = [""]

    # Looping through all the public commands to add their helptexts to the correct chunks
    for helpcommand in public_commands:

        # We check if the last chunk is too will become too large or not
        if len(public_commands_helptext[-1] + "\n-------------------------\n\t" + "**" + helpcommand[
            "command"] + "**\n" + helpcommand["helptext"] + "\n-------------------------") > 2000:
            # We add another string to he list of messages we want to send
            public_commands_helptext.append("")

        public_commands_helptext[-1] += "\n-------------------------\n\t" + "**" + helpcommand[
            "command"] + "**\n" + helpcommand["helptext"] + "\n-------------------------"

    # Checking if the issuer is an admin user, so we know if we should show them the admin commands
    if int(message.author.id) in passed_config["somewhat_weird_shit"]["admin_user_ids"]:
        # Generating the combined and formatted helptext of all the admin commands (we do this in >2000 char chunks, as 2000 chars is the max length of a discord message)
        admin_commands_helptext = [""]

        # Looping through all the admin commands to add their helptexts to the correct chunks
        for helpcommand in admin_commands:

            # We check if the last chunk is too will become too large or not
            if len(admin_commands_helptext[-1] + "\n-------------------------\n\t" + "*admin* **" + helpcommand[
                "command"] + "**\n" + helpcommand["helptext"] + "\n-------------------------") > 2000:
                # We add another string to he list of messages we want to send
                admin_commands_helptext.append("")

            admin_commands_helptext[-1] += "\n-------------------------\n\t" + "*admin* **" + helpcommand[
                "command"] + "**\n" + helpcommand["helptext"] + "\n-------------------------"

    # How many seconds we should wait between each message
    cooldown_time = 0.5

    # Checking if we're in a private channel or a public channel so we can format our messages properly
    if not message.channel.is_private:
        # Telling the user that we're working on it
        await passed_client.send_message(message.channel,
                                         "Sure thing " + message.author.mention + ", you'll see the commands and how to use them in our PMs :smile:")

    # Checking if the issuer is an admin user, so we know if we should show them the admin commands
    if int(message.author.id) in passed_config["somewhat_weird_shit"]["admin_user_ids"]:

        # Just putting the helptexts we made in the PM with the command issuer
        await passed_client.send_message(message.author, "Ok, here are the commands you can use me for :smile:")

        # We send the helptexts in multiple messages to bypass the 2000 char limit, and we pause between each message to not get rate-limited
        for helptext in public_commands_helptext:
            # We wait for a bit to not get rate-limited
            await asyncio.sleep(cooldown_time)

            # We send the help message
            await passed_client.send_message(message.author, helptext)

        # Informing the user that they're an admin
        await passed_client.send_message(message.author, "\nSince you're an anna-bot admin, you also have access to:")

        for helptext in admin_commands_helptext:
            # We wait for a bit to not get rate-limited
            await asyncio.sleep(cooldown_time)

            # We send the help message
            await passed_client.send_message(message.author, helptext)

    else:

        # Just putting the helptexts we made in the PM with the command issuer
        await passed_client.send_message(message.author, "Ok, here are the commands you can use me for :smile:")

        # We send the helptexts in multiple messages to bypass the 2000 char limit, and we pause between each message to not get rate-limited
        for helptext in public_commands_helptext:
            # We wait for a bit to not get rate-limited
            await asyncio.sleep(cooldown_time)

            # We send the help message
            await passed_client.send_message(message.author, helptext)

    # Sending a finishing message (on how to use the commands in a regular channel)
    await passed_client.send_message(message.author,
                                     "To use commands in a regular server channel, just do \"" + client_mention + " COMMAND\"")


@main_code.command_decorator.command("reload config", "Reloads the config file that anna-bot uses.", admin=True)
async def cmd_admin_reload_config(message: discord.Message, passed_client: discord.Client, passed_config: dict):
    """This method is used to handle an admin user wanting us to reload the config file.
    Because of code simplicity this is one of the command functions that needs to stay in the __init__py file."""

    # Telling the issuing user that we're reloading the config
    # Checking if we're in a private channel or if we're in a regular channel so we can format our message properly
    if message.channel.is_private:
        await passed_client.send_message(message.channel, "Ok, I'm reloading it right now!")
    else:
        await passed_client.send_message(message.channel,
                                         "Ok " + message.author.mention + ", I'm reloading it right now!")

    # Telling the issuing user that we're reloading the config file
    await passed_client.send_message(message.channel, "Reloading the config file...")

    # Logging that we're loading the config
    helpers.log_info("Reloading the config file...")

    # Loading the config file and then parsing it as json and storing it in a python object
    with open("config.json", mode="r", encoding="utf-8") as opened_config_file:
        global config
        config = json.load(opened_config_file)

    # Logging that we're done loading the config
    helpers.log_info("Done reloading the config")

    # Telling the issuing user that we're done reloading the config file
    await passed_client.send_message(message.channel, "Done reloading the config file!")

    # Telling the issuing user that we're updating the vanity command dict
    await passed_client.send_message(message.channel, "Updating vanity commands...")

    # Logging that we're updating the vanity commands
    helpers.log_info("Updating vanity commands...")

    # Updating the vanity command dict because the config file could have changed the vanity setup
    await main_code.commands.regular.vanity_role_commands.update_vanity_dictionary(passed_client, passed_config)

    # Logging that we're done updating the vanity commands
    helpers.log_info("Done updating vanity commands")

    # Telling the issuing user that we're done updating the vanity command dict
    await passed_client.send_message(message.channel, "Done updating vanity commands!")

    # Telling the issuing user that we're reloading the config
    # Checking if we're in a private channel or if we're in a regular channel so we can format our message properly
    if message.channel.is_private:
        await passed_client.send_message(message.channel, "Ok, I'm done reloading now :smile:")
    else:
        await passed_client.send_message(message.channel,
                                         "Ok " + message.author.mention + ", I'm done reloading it now :smile:")


def set_special_param(index: int, value):
    """This function handles resolving a special param index into being able to set that variable (it can be immutable) to the inputted value.
    We need this function since python doesn't have a concept of references."""

    global ignored_command_message_ids
    global config

    # This code is really ugly because we need performance (dictionaries with lambdas with exec it very slow since it compiles every time we define it),
    # because python doesn't have any concept of references, and because python doesn't have any equivalent to switch/case
    if index == 0:
        ignored_command_message_ids = value
    elif index == 1:
        config = value


async def webserver_post_last_online_list(server_address: str, server_port: int, interval: int):
    """This method is called periodically and handler posting data about last online times for users
    on a discord server to an anna-falcon-server instance."""

    async def do_async_list_post(passed_session: aiohttp.ClientSession):
        try:
            with async_timeout.timeout(interval / 2, loop=client.loop):
                return await asyncio.wait_for(
                    passed_session.post("http://" + server_address + ":{0}/lastseen".format(server_port),
                                        timeout=interval / 2,
                                        data=json.dumps(last_online_time_dict)), interval / 2, loop=client.loop)
        except (asyncio.TimeoutError, asyncio.CancelledError) as e:
            helpers.log_warning("Got error when trying to send data to webserver, info: \n{0}".format(e))

    # This runs forever (until the bot exits)
    while True:
        # We log
        helpers.log_info("Sending last-online-list info to webserver at {0}:{1}.".format(server_address, server_port))

        # We post the data to the appropriate address and port
        async with aiohttp.ClientSession(loop=client.loop, connector=aiohttp.TCPConnector(verify_ssl=False,
                                                                                          keepalive_timeout=5)) as session:
            try:
                (await do_async_list_post(session)).close()
            except Exception as e:
                helpers.log_warning("Got unusual error when trying to send data to webserver, info: \n{0}".format(e))
        helpers.log_info(
            "Sent last-online-list info to webserver at {0}:{1}. Now waiting for {2} seconds.".format(server_address,
                                                                                                      server_port,
                                                                                                      interval))

        # We wait until the next time we're supposed to send the info.
        await asyncio.sleep(interval)


if __name__ == "__main__":

    # Logging that we're loading the config
    helpers.log_info("Loading the config file...")

    # The config object
    config = {}

    # Loading the config file and then parsing it as json and storing it in a python object
    with open("config.json", mode="r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    # We store the bot start time in the volatile stats section
    config["stats"]["volatile"]["start_time"] = time.time()

    # We write the modified config back to the file
    with open("config.json", mode="w", encoding="utf-8") as config_file:
        json.dump(config, config_file, indent=2, sort_keys=False)

    # Logging that we're done loading the config
    helpers.log_info("Done loading the config")

    commands = main_code.command_decorator.get_command_lists()

    # The commands people can use and the method that will be called when a command is used
    # The special params are defined in the on_message function, but they basically just pass all the special params as KW arguments
    # Most commands use the helpers.command(command_trigger, description, special_params, admin) decorator, but these cannot use that since they have config based command parameters
    public_commands = [dict(command="invite", method=main_code.commands.regular.invite_link.invite_link,
                            helptext="Generate an invite link to the current channel, the link will be valid for " + str(
                                config["invite_cmd"]["invite_valid_time_min"] if config["invite_cmd"][
                                                                                     "invite_valid_time_min"] > 0 else "infinite") + " minutes and " + str(
                                config["invite_cmd"]["invite_max_uses"] if config["invite_cmd"][
                                                                               "invite_max_uses"] > 0 else "infinite") + " use[s].",
                            special_params=[False, False]),
                       dict(command=config["start_server_cmd"]["start_server_command"],
                            method=main_code.commands.regular.start_server.start_server,
                            helptext="Start the minecraft server (if the channel and users have the necessary permissions to do so).",
                            special_params=[False, False])
                       ]

    # The commands authorised users can use, these are some pretty powerful commands, so be careful with which users you give administrative access to the bot to
    admin_commands = []

    # We extend the lists with the decorator commands
    public_commands.extend(commands[0])
    admin_commands.extend(commands[1])

    # The functions to call when someone joins the server, these get passed the member object of the user who joined
    join_functions = [join_welcome_message,
                      join_automatic_role,
                      join_referral_asker]

    # The list of message ids (this list will fill and empty) that the command checker should ignore
    ignored_command_message_ids = []

    # The list of tuples of voice stream players and server ids
    server_and_stream_players = []

    # Logging that we're starting the bot
    helpers.log_info("Anna-bot is now logging in (you'll notice if we get any errors)")

    # Storing the time at which the bot was started
    config["stats"]["volatile"]["start_time"] = time.time()

    # We set up the webserver handling if the user has indicated that we're using a webserver
    if config["webserver_config"]["use_webserver"]:
        # We create the object we're going to send to the webserver
        last_online_time_dict = {"servers": [], "auth_token": config["webserver_config"]["auth_token"]}

        webserver_task = client.loop.create_task(
            webserver_post_last_online_list(config["webserver_config"]["server_address"],
                                            config["webserver_config"]["server_port"],
                                            config["webserver_config"]["update_interval_seconds"]))

    try:
        # We have a while loop here because some errors are only catchable from the client.run method, as they are raised by tasks in the event loop
        # Some of these errors are not, and shouldn't, be fatal to the bot, so we catch them and relaunch the client.
        # The errors we don't catch however, rise to the next try except and actually turn off the bot
        while True:
            try:
                # Starting and authenticating the bot
                client.run(config["credentials"]["token"])
            except concurrent.futures.TimeoutError:
                # We got a TimeoutError, which in general shouldn't be fatal.
                helpers.log_info("Got a TimeoutError from client.run, logging in again.")
            except discord.ConnectionClosed:
                # We got a ConnectionClosed error, which should mean that the client was disconnected from the websocket for un-handlable reasons
                # We wait for a bit to not overload/ddos the discord servers if the problem is on their side
                time.sleep(1)
                helpers.log_info("Got a discord.ConnectionClosed from client.run, logging in again.")
            except websockets.exceptions.ConnectionClosed:
                # We got a ConnectionClosed error, which should mean that the client was disconnected from the websocket for un-handlable reasons
                # We wait for a bit to not overload/ddos the discord servers if the problem is on their side
                time.sleep(1)
                helpers.log_info("Got a websockets.exceptions.ConnectionClosed from client.run, logging in again.")
            except ConnectionResetError:
                # We got a ConnectionReset error, which should mean that the client was disconnected from the websocket for un-handlable reasons
                # We wait for a bit to not overload/ddos the discord servers if the problem is on their side (((it is)))
                time.sleep(1)
                helpers.log_info("Got a ConnectionResetError from client.run, logging in again.")
            else:
                # If we implement a stop feature in the future, we will need this to be able to stop the bot without using exceptions
                break
    except:
        # How did we exit?
        helpers.log_warning("Did not get user interrupt, but still got an error, re-raising...")
        raise
    else:
        # No error but we exited
        helpers.log_info("Client exited, but we didn't get an error, probably CTRL+C or command exit...")

    # Calculating and formatting how long the bot was online so we can log it, this is on multiple statements for clarity
    end_time = time.time()
    uptime_secs_noformat = (end_time - config["stats"]["volatile"]["start_time"]) // 1
    formatted_uptime = helpers.get_formatted_duration_fromtime(uptime_secs_noformat)

    # Logging that we've stopped the bot
    helpers.log_info(
        "Anna-bot has now exited (you'll notice if we got any errors), we have been up for {0}.".format(
            formatted_uptime))
