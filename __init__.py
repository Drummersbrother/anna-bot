import asyncio
import json
import subprocess
import time

import discord
import requests

import helpers

# Setting up the client object
client = discord.Client(cache_auth=False)


# TODO Handle group calls and messages, and/or move to the commands extension

@client.event
async def on_message(message: discord.Message):
    # We wait for a split second so we can be assured that ignoring of messages and other things have finished before the message is processed here
    await asyncio.sleep(0.1)

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

    # Checking if we sent the message, so we don't trigger ourselves and checking if the message should be ignored or not (such as it being a response to another command)
    if (message.author.id != client.user.id) and (message.id not in ignored_command_message_ids):
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
                    await command["method"](message)

                    # We note that a command was triggered so we don't output the message about what "!" means
                    used_command = True
                    break

            # Checking if the issuing user is in the admin list
            if int(message.author.id) in config["somewhat_weird_shit"]["admin_user_ids"]:

                # Going through all the admin commands we've specified and checking if they match the message
                for command in admin_commands:
                    if message.content.lower().strip().startswith("admin " + command["command"]):
                        # We log what command was used by who
                        helpers.log_info("The " + command[
                            "command"] + " admin command was triggered by admin \"" + message.author.name + "\" in a PM.")

                        # The command matches, so we call the method that was specified in the command list
                        await command["method"](message)

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
            if is_message_command(message):
                # Going through all the public commands we've specified and checking if they match the message
                for command in public_commands:
                    if remove_anna_mention(message).lower().strip().startswith(
                            command["command"]):
                        # We log what command was used by who and where
                        helpers.log_info("The " + command[
                            "command"] + " command was triggered by \"" + message.author.name + "\" in channel \"" + message.channel.name + "\" on server \"" + message.server.name + "\".)")

                        # The command matches, so we call the method that was specified in the command list
                        await command["method"](message)

                        # We note that a command was triggered so we don't output the message about what anna can do
                        used_command = True
                        break

                # Checking if the issuing user is in the admin list
                if int(message.author.id) in config["somewhat_weird_shit"]["admin_user_ids"]:
                    # Going through all the admin commands we've specified and checking if they match the message
                    for command in admin_commands:
                        if remove_anna_mention(message).lower().strip().startswith(
                                        "admin " + command["command"]):

                            # We check if the command was triggered in a private channel/PM or not
                            if message.channel.is_private:

                                # We log what command was used by who
                                helpers.log_info("The " + command[
                                    "command"] + " admin command was triggered by admin \"" + message.author.name + "\" in a PM.")

                            else:
                                # We log what command was used by who and where
                                helpers.log_info("The " + command[
                                    "command"] + " admin command was triggered by admin \"" + message.author.name + "\" in channel \"" + message.channel.name + "\" on server \"" + message.server.name + "\".)")

                            # The command matches, so we call the method that was specified in the command list
                            await command["method"](message)

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
            if member.server.me.permissions_in(member.server.default_channel).manage_roles:
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
            if member.server.me.permissions_in(member.server.default_channel).manage_roles:

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


async def cmd_invite_link(message: discord.Message):
    """This method is called to handle someone typing the message '!invite'."""

    # Telling the user that we're working on it
    await client.send_message(message.channel,
                              "Sure thing " + message.author.mention + ", you'll see the link in our PMs :smile:")

    # Checking if the bot and the user has permissions to generate an invite link
    if message.author.permissions_in(message.channel).create_instant_invite and message.server.me.permissions_in(
            message.channel).create_instant_invite:
        # Generating a join/invite link (for the channel in which the message was sent) and doing some formatting on a message so we can be more human
        invite_url = await client.create_invite(message.channel,
                                                max_age=60 * config["invite_cmd"]["invite_valid_time_min"],
                                                max_uses=config["invite_cmd"]["invite_max_uses"], temporary=False)
        invite_url = invite_url.url

        # Make a message with proper formatting and put it in the chat where the invite link was requested, also mention the person who requested the link
        await client.send_message(message.author, "Ok, here's an invite link :smile: " + invite_url +
                                  " (valid for " + str(config["invite_cmd"]["invite_valid_time_min"]) + "min and "
                                  + str(config["invite_cmd"]["invite_max_uses"]) + " use[s])")

    else:
        # Checking whether it is the bot or the user who doesn't have permissions
        if not message.author.permissions_in(message.channel).create_instant_invite:
            # Telling the user who wanted the invite link that they don't have permissions to create invites
            await client.send_message(message.author,
                                      "Sorry, I can't do that for you since you don't have permissions to create invite links in that channel.")

        else:
            # Telling the user who wanted the invite link that they don't have permissions to create invites
            await client.send_message(message.author,
                                      "Sorry, I can't do that for you since I don't have permissions to create invite links in that channel.")


async def cmd_start_server(message: discord.Message):
    """This method is called to handle when someone wants to launch the server (a bat file)"""
    if message.content.lower().startswith(
            config["start_server_cmd"]["start_server_command"]) and (
                config["start_server_cmd"]["start_server_allowed_channel_and_server_pairs"] == [message.channel.name,
                                                                                                message.server.id]):
        # Telling the caller that we're on it
        await client.send_message(message.channel, message.author.mention + ", I'm on it!")

        # We have a try except clause so we can output errors to the chat
        try:
            server = subprocess.Popen(config["start_server_command"]["start_bat_filepath"],
                                      creationflags=subprocess.CREATE_NEW_CONSOLE)
            await client.send_message(message.channel,
                                      "All done! But please note that it might take up to a minute before the server can accept any players :smile:")
        except Exception as e:
            # We output the error to the chat
            await client.send_message(message.channel, str(e))
    else:
        # Telling the caller that they do not have the appropriate permissions
        await client.send_message(message.channel,
                                  message.author.mention + ", it seems that you do not have the appropriate permissions to start the server, try using the command in a known authorised channel...")


async def cmd_help(message: discord.Message):
    """This method is called to handle someone needing information about the commands they can use anna for."""

    # We need to create the helptexts dynamically and on each use of this command as it depends on the bot user mention which needs the client to be logged in

    # The correct mention for the bot user, the string manipulation is due to mention strings not being the same depending on if a user or the library generated it
    client_mention = client.user.mention[:2] + "!" + client.user.mention[2:]

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
    if int(message.author.id) in config["somewhat_weird_shit"]["admin_user_ids"]:
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
        await client.send_message(message.channel,
                                  "Sure thing " + message.author.mention + ", you'll see the commands and how to use them in our PMs :smile:")

    # Checking if the issuer is an admin user, so we know if we should show them the admin commands
    if int(message.author.id) in config["somewhat_weird_shit"]["admin_user_ids"]:

        # Just putting the helptexts we made in the PM with the command issuer
        await client.send_message(message.author, "Ok, here are the commands you can use me for :smile:")

        # We send the helptexts in multiple messages to bypass the 2000 char limit, and we pause between each message to not get rate-limited
        for helptext in public_commands_helptext:
            # We wait for a bit to not get rate-limited
            await asyncio.sleep(cooldown_time)

            # We send the help message
            await client.send_message(message.author, helptext)

        # Informing the user that they're an admin
        await client.send_message(message.author, "\nSince you're an anna-bot admin, you also have access to:")

        for helptext in admin_commands_helptext:
            # We wait for a bit to not get rate-limited
            await asyncio.sleep(cooldown_time)

            # We send the help message
            await client.send_message(message.author, helptext)

    else:

        # Just putting the helptexts we made in the PM with the command issuer
        await client.send_message(message.author, "Ok, here are the commands you can use me for :smile:")

        # We send the helptexts in multiple messages to bypass the 2000 char limit, and we pause between each message to not get rate-limited
        for helptext in public_commands_helptext:
            # We wait for a bit to not get rate-limited
            await asyncio.sleep(cooldown_time)

            # We send the help message
            await client.send_message(message.author, helptext)

    # Sending a finishing message (on how to use the commands in a regular channel)
    await client.send_message(message.author,
                              "To use commands in a regular server channel, just do \"" + client_mention + " COMMAND\"")


async def cmd_gen_bot_invite(message: discord.Message):
    """This method is called to handle someone wanting to invite anna-bot to their own server"""

    # Creating the Permissions object so the bot gets proper permissions to work when it is invited to a server
    bot_permissions = discord.Permissions().none()

    # Actually modifying all the properties of the permissions objects so we get the permissions
    bot_permissions.create_instant_invite = True
    bot_permissions.read_messages = True
    bot_permissions.send_messages = True
    bot_permissions.embed_links = True
    bot_permissions.read_message_history = True
    bot_permissions.connect = True
    bot_permissions.speak = True

    # Creating the url with all the proper settings
    invite_url = discord.utils.oauth_url(config["credentials"]["app_client_id"], bot_permissions)

    # Giving the url back to the user with proper formatting
    await client.send_message(message.channel,
                              message.author.mention + ", here is the bot invite link :smile: " + invite_url + " (it has good permission defaults but you can, of course, change that on your own later.)")


async def cmd_who_r_u(message: discord.Message):
    """This method is called to handle someone wanting to know who/what anna-bot is."""

    # Just sending an explanation back in the same channel as the command was issued in
    await client.send_message(message.channel,
                              "Anna-bot is a discord bot written in python (discord.py), created by Hugo Berg (drummersbrother), for the Evalonia minecraft server (mcevalonia.com).\nDo you want to host your own anna-bot, or just look at and maybe even contribute to the code?\nhttps://github.com/Drummersbrother/anna-bot :wink:")


async def cmd_report_stats(message: discord.Message):
    """This method is used to handle reporting stats about the bot to the user who used the anna stats command."""

    # Creating the formatted string about how long the bot has been up for this "session"
    uptime_string = helpers.get_formatted_duration_fromtime((time.time() - start_time) // 1)

    # Loading the config file so we can use the stats that exist in it
    with open("config.json", mode="r", encoding="utf-8") as config_file:
        current_config = json.load(config_file)

    # Reporting the stats back into the chat where the command was issued
    await client.send_message(message.channel,
                              "Some stats about anna-bot:\n\tIt has been up for %s. \n\tIt has sent %i message(s). \n\tIt has received %i command(s)." % (
                                  uptime_string, current_config["stats"]["messages_sent"],
                                  current_config["stats"]["commands_received"]))


async def cmd_join_voice_channel(message: discord.Message):
    """This command is issued to make anna join a voice channel if she has access to it on the server where this command was issued."""

    # We check if the command was issued in a PM or in a regular server, so we can tell user not to be an idiot
    if message.channel.is_private:

        # This message was sent in a private channel, and we can therefore deduce that the user is about as smart as Eva
        await client.send_message(message.author,
                                  "There aren't any voice channels in private messages you know, so I can't really join one.")
    else:

        # Removing the anna-bot mention
        cleaned_message = remove_anna_mention(message)

        # The user is not an idiot, so we parse the message for the voice channel name, if there are two or more channels with the same name, we tell the user to choose between them using channel order numbers that we give to them depending on the channel IDs
        voice_channel_name = cleaned_message[11:]

        # Checking how many voice channels in the server match the given name. If none match, we try to strip the name (the user might have been an idiot contrary to popular belief)
        num_matching_voice_channels = [
            (channel.type == discord.ChannelType.voice) and (channel.name == voice_channel_name) for channel in
            message.server.channels].count(True)

        # You can't be connected to multiple voice channels at the same time
        if not client.is_voice_connected(message.server):

            # We check to see if we have permissions to join the voice channel
            if not message.channel.permissions_for(message.server.me).connect:
                # We don't have permissions to join a voice channel in this server, so we tell the user to fuck off
                await client.send_message(message.channel,
                                          message.author.mention + ", I don't have permission to join a voice channel on this server.")

                # We're done here
                return

            # We check if there exists at least 1 matching channel or not
            if num_matching_voice_channels > 0:

                # We check if there are more than 1 matching channel, because that means trouble
                if num_matching_voice_channels > 1:

                    # We have some trouble on our hands
                    # We make a list of tuples of all the channel candidates that the user could mean
                    channel_candidates = [(channel, channel_number) for channel_number, channel in
                                          enumerate(message.server.channels) if
                                          (channel.name == voice_channel_name) and (
                                              channel.type == discord.ChannelType.voice)]

                    # We print the alternatives to the user so they can message us back with the channel they want us to join
                    await client.send_message(message.channel,
                                              message.author.mention + ", there are %i voice channels on this server with that name, please message me the number of the channel that you want me to join within 1 minute (e.g. \"@anna-bot 0\"):\n--------------------" % len(
                                                  channel_candidates) + "".join([(
                                                                                     "\nNumber %s:\n\t%s users currently connected.\n--------------------" % (
                                                                                         str(candidate[1]), str(len(
                                                                                             candidate[
                                                                                                 0].voice_members))))
                                                                                 for candidate in
                                                                                 channel_candidates]))

                    response_message = await client.wait_for_message(timeout=60, author=message.author,
                                                                     channel=message.channel,
                                                                     check=is_message_command)

                    # We add the response message id to the ignored list of message ids
                    ignored_command_message_ids.append(response_message.id)

                    # We wait for the caller to send back a message to us so we can determine what channel we should join
                    user_response = remove_anna_mention(response_message).strip()

                    if user_response is not None:
                        # We know that the user sent us a message that @mentioned us, so we parse the rest of the message
                        if user_response.isdecimal():

                            # We can convert the user response into a number and then check if it is a valid choice or not
                            if len(channel_candidates) > int(user_response) >= 0:
                                # Converting the response into an int
                                user_response = int(user_response)

                                # Choosing the channel to join
                                voice_channel = channel_candidates[user_response][0]

                    else:
                        # The waiting timed out, so we message the user that they waited to long
                        await client.send_message(message.channel,
                                                  message.author.mention + ", you waited to long with answering which channel you want me to connect to.")

                        # We're done here
                        return

                else:

                    # Everything went well, we can safely try to join the voice channel
                    # We get the channel from the channel name that the user specified
                    voice_channel = discord.utils.get(message.server.channels, name=voice_channel_name,
                                                      type=discord.ChannelType.voice)


            else:

                # We couldn't find a match, so we try the same thing with a stripped version of the desired channel name
                voice_channel_name = voice_channel_name.strip()

                # Checking how many voice channels in the server match the given name
                num_matching_voice_channels = [
                    (channel.type == discord.ChannelType.voice) and (channel.name == voice_channel_name) for channel in
                    message.server.channels].count(True)

                # We check if we found any matching channels this time
                if num_matching_voice_channels > 0:

                    # We have some trouble on our hands
                    # We make a list of tuples of all the channel candidates that the user could mean
                    channel_candidates = [(channel, channel_number) for channel_number, channel in
                                          enumerate(message.server.channels) if
                                          (channel.name == voice_channel_name) and (
                                              channel.type == discord.ChannelType.voice)]

                    # We print the alternatives to the user so they can message us back with the channel they want us to join
                    await client.send_message(message.channel,
                                              message.author.mention + ", there are %i voice channels on this server with that name, please message me the number of the channel that you want me to join within 1 minute (e.g. \"@anna-bot 0\"):\n--------------------" % len(
                                                  channel_candidates) + "".join([(
                                                                                     "\nNumber %s:\n\t%s users currently connected.\n--------------------" % (
                                                                                         str(candidate[1]), str(len(
                                                                                             candidate[
                                                                                                 0].voice_members))))
                                                                                 for candidate in
                                                                                 channel_candidates]))

                    response_message = await client.wait_for_message(timeout=60, author=message.author,
                                                                     channel=message.channel,
                                                                     check=is_message_command)

                    # We add the response message id to the ignored list of message ids
                    ignored_command_message_ids.append(response_message.id)

                    # We wait for the caller to send back a message to us so we can determine what channel we should join
                    user_response = remove_anna_mention(response_message).strip()

                    if user_response is not None:
                        # We know that the user sent us a message that @mentioned us, so we parse the rest of the message
                        if user_response.isdecimal():

                            # We can convert the user response into a number and then check if it is a valid choice or not
                            if len(channel_candidates) > int(user_response) >= 0:
                                # Converting the response into an int
                                user_response = int(user_response)

                                # Choosing the channel to join
                                voice_channel = channel_candidates[user_response][0]

                    else:
                        # The waiting timed out, so we message the user that they waited to long
                        await client.send_message(message.channel,
                                                  message.author.mention + ", you waited to long with answering which channel you want me to connect to.")

                        # We're done here
                        return

                else:

                    # We didn't find any matching channels, which means that the user is a fucking idiot
                    await client.send_message(message.channel,
                                              message.author.mention + ", I couldn't find any voice channels called \"" + voice_channel_name + "\".")

                    # We're done now
                    return

        else:

            # We tell the user to check their IQ and try again (because the bot is already connected to a voice channel)
            await client.send_message(message.channel,
                                      message.author.mention + ", I can't join a voice channel when I'm already connected to one. Please use the voice leave command if you want me to join another channel.")

            # We're done now
            return

        # Everything should have exited if something went wrong by this stage, so we can safely assume that it's fine to connect to the voice channel that the user has programmed
        # Telling the user that we found the channel and that we are joining right now
        await client.send_message(message.channel,
                                  message.author.mention + ", ok, I'm joining \"%s\" right now." % voice_channel_name)

        # Joining the channel
        await client.join_voice_channel(voice_channel)


async def cmd_leave_voice_channel(message: discord.Message):
    """This command is issued to make anna leave a voice channel if she is connected to it on the server where this command was issued."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:
        # We check if we were connected to a voice channel on the server where this command was issued
        if client.is_voice_connected(message.server):
            # We tell the issuing user that we've left the server
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm leaving the \"%s\" voice channel right now." % client.voice_client_in(
                                          message.server).channel.name)

            # We check if there are any stream players currently playing on that voice channel
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We stop the player
                    server_stream_pair[1].stop()

            # We remove the stopped entries in the list of players
            server_and_stream_players[:] = [x for x in server_and_stream_players if not x[1].is_done()]

            # We leave the voice channel that we're connected to on that server
            await client.voice_client_in(message.server).disconnect()

        else:
            # We aren't connected to a voice channel on the current server, the user is just being an idiot
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not connected to a voice channel on this server, if you want me to connect to one, please use the \"@anna-bot voice join CHANNELNAME\" command.")
    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_play_youtube(message: discord.Message):
    """This command is used to play the audio of a youtube video at the given link."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # We parse the url from the command message
        youtube_url = remove_anna_mention(message).strip()[19:]

        # We get the voice client on the server in which the command was issued
        voice = client.voice_client_in(message.server)

        # We check if we're connected to a voice channel in the server where the command was issued
        if voice is None:

            # We are not connected to a voice channel, so we tell the user to fuck off
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not connected to any voice channels on this server, so I can't play any audio.")

        else:

            # We check if there already exists a stream player for this server, if so, we terminate it and start playing the given video
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We stop the player
                    server_stream_pair[1].stop()

            # We remove the stopped entries in the list of players
            server_and_stream_players[:] = [x for x in server_and_stream_players if not x[1].is_done()]

            # We're connected to a voice channel, so we try to create the ytdl stream player
            youtube_player = await voice.create_ytdl_player(youtube_url)

            # We append the stream and server id pair to the stream list
            server_and_stream_players.append((message.server.id, youtube_player))

            # We start the stream player
            youtube_player.start()

            # Telling the user that we're playing the video
            await client.send_message(message.channel,
                                      message.author.mention + ", now playing youtube video with title: \"%s\", uploaded by: \"%s\"." % (
                                          youtube_player.title, youtube_player.uploader))

            # We log what video title and uploader the played video has
            helpers.log_info(
                "Playing youtube video with title: \"%s\", uploaded by: \"%s\" in voice channel: \"%s\" on server: \"%s\"" % (
                    youtube_player.title, youtube_player.uploader, voice.channel.name, voice.server.name))

    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_sound_effect(message: discord.Message):
    """This method is used to play a sound effect in the voice channel anna is connected to on the issuing server."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # We parse the sound effect name from the command TODO
        sound_effect_name = remove_anna_mention(message).strip()

        # We get the voice client on the server in which the command was issued
        voice = client.voice_client_in(message.server)

        # We check if we're connected to a voice channel in the server where the command was issued
        if voice is None:

            # We are not connected to a voice channel, so we tell the user to fuck off
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not connected to any voice channels on this server, so I can't play any audio.")

        else:

            # We're connected to a voice channel, so we check if the specified sound effect exists TODO

            # We create the stream player with the specified file name TODO

            # We append the stream and server id pair to the stream list
            server_and_stream_players.append((message.server.id, youtube_player))

            # We start the stream player
            youtube_player.start()

            # Telling the user that we're playing the video
            await client.send_message(message.channel,
                                      message.author.mention + ", now playing youtube video with title: \"%s\", uploaded by: \"%s\"." % (
                                          youtube_player.title, youtube_player.uploader))

            # We log what video title and uploader the played video has
            helpers.log_info(
                "Playing youtube video with title: \"%s\", uploaded by: \"%s\" in voice channel: \"%s\" on server: \"%s\"" % (
                    youtube_player.title, youtube_player.uploader, voice.channel.name, voice.server.name))

    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_set_volume(message: discord.Message):
    """This command is used to change the volume of the audio that anna plays."""

    # We first check if the command was issued in a PM channel
    if not message.channel.is_private:
        # We check if there we are connected to a voice channel on this server
        if client.voice_client_in(message.server) is not None:

            found_stream_player = False

            # We check if we have a stream player playing something on the server
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We note that we found atleast one stream player playing something
                    found_stream_player = True

            # We check if we found any stream players
            if found_stream_player:

                # We parse the command and check if the specified volume is a valid non-negative integer
                clean_argument = remove_anna_mention(message)[13:].strip()

                if clean_argument.isdigit():

                    # We create an int from the string and clamp it between 0-2 (inclusive on both ends)
                    volume = min(max(int(clean_argument), 0), 200) / 100

                    # We set the volume of all stream players on the server to be the desired volume
                    for server_stream_pair in server_and_stream_players:

                        # Checking if the server id matches the issuing user's server's id
                        if server_stream_pair[0] == message.server.id:
                            # Setting the volume of the stream player
                            server_stream_pair[1].volume = volume

                    # Telling the user that we've set the volume
                    await client.send_message(message.channel,
                                              message.author.mention + ", I've changed the volume to %i%%." % int(
                                                  volume * 100))

                else:
                    # Invalid volume argument (wasn't a positive int)
                    await client.send_message(message.channel,
                                              message.author.mention + ", that wasn't a valid volume level.")

            else:
                # We didn't find any stream players
                await client.send_message(message.channel,
                                          message.author.mention + ", I'm not playing any sound on this server.")

        else:
            # We aren't connected to any voice channel on this server
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not connected to any voice channels on this server.")

    else:
        # The command was issued in a PM channel, so we tell the user to fuck off
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_play_toggle(message: discord.Message):
    """This method is used to toggle playing (pausing and unpausing) the current playing stream players in that server (if there are any)."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # The command was issued in a regular channel
        # We check if there we are connected to a voice channel on this server
        if client.voice_client_in(message.server) is not None:

            found_stream_player = False

            # We check if we have a stream player playing something on the server
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We note that we found atleast one stream player playing something
                    found_stream_player = True

            # We check if we found any stream players
            if found_stream_player:

                # We loop through the stream players and toggle all of them
                for server_stream_pair in server_and_stream_players:

                    # Checking if the server id matches the issuing user's server's id
                    if server_stream_pair[0] == message.server.id:

                        # We toggle the playing status
                        if server_stream_pair[1].is_playing():
                            # The player is not paused, so we pause it
                            server_stream_pair[1].pause()
                        else:
                            # The player is paused, so we unpause it
                            server_stream_pair[1].resume()

                # We tell the user that we've toggled the stream player
                await client.send_message(message.channel, message.author.mention + ", I've now toggled the audio.")

            else:
                # We didn't find any stream players
                await client.send_message(message.channel,
                                          message.author.mention + ", I'm not playing any sound on this server.")

        else:
            # We aren't connected to any voice channel on this server
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not connected to any voice channels on this server.")

    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_play_stop(message: discord.Message):
    """This method is used to stop all audio from anna in a server."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # The command was issued in a regular channel
        # We check if there we are connected to a voice channel on this server
        if client.voice_client_in(message.server) is not None:

            found_stream_player = False

            # We check if we have a stream player playing something on the server
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We note that we found atleast one stream player playing something
                    found_stream_player = True

            # We check if we found any stream players
            if found_stream_player:

                # We loop through the stream players and toggle all of them
                for server_stream_pair in server_and_stream_players:

                    # Checking if the server id matches the issuing user's server's id
                    if server_stream_pair[0] == message.server.id:
                        # We stop the player
                        server_stream_pair[1].stop()

                    # We remove all stopped players from the player list
                    server_and_stream_players[:] = [x for x in server_and_stream_players if not x[1].is_done()]

                # We tell the user that we've toggled the stream player
                await client.send_message(message.channel, message.author.mention + ", I've now stopped the audio.")

            else:
                # We didn't find any stream players
                await client.send_message(message.channel,
                                          message.author.mention + ", I'm not playing any sound on this server.")

        else:
            # We aren't connected to any voice channel on this server
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not connected to any voice channels on this server.")

    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_list_ids(message: discord.Message):
    """This command is used to get a list of all the ids of all things in the server."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # We tell the user that we're going to send them a list of the ids in the server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm sending the list in our PMs right now.")

    # The command was issued in a PM
    else:

        # We tell the user that the command needs to be issued in a regular text channel on a regular server
        await client.send_message(message.channel,
                                  "This command does not work when issued in a PM, please issue it in a regular channel on a server")

    # We create the list of ids (server id, text channel ids, voice channel ids, role ids, user ids)
    list_of_ids = "Server name and ID:\n" + message.server.name + " - " + message.server.id + "\n\n"

    # We add the text channel ids
    list_of_ids += "Text channel names and ids:\n" + str.join("", [(x[0] + " - " + x[1] + "\n") for x in
                                                                   [(c.name, c.id) for c in message.server.channels if
                                                                    c.type == discord.ChannelType.text]]) + "\n"

    # We add the voice channel ids
    list_of_ids += "Voice channel names and ids:\n" + str.join("", [(x[0] + " - " + x[1] + "\n") for x in
                                                                    [(c.name, c.id) for c in message.server.channels if
                                                                     c.type == discord.ChannelType.voice]]) + "\n"

    # We add the role ids
    list_of_ids += "Role names and ids:\n" + str.join("", [(x[0] + " - " + x[1] + "\n") for x in
                                                           [(c.name, c.id) for c in message.server.roles]]) + "\n"

    # We add the user ids
    list_of_ids += "User names and ids:\n" + str.join("", [(x[0] + " - " + x[1] + "\n") for x in
                                                           [(str(c), c.id) for c in message.server.members]])

    # As the list of ids can become arbitrarily big and the message size limit for discord is 2000 chars, we split the list into <2000 char chunks
    # We first check if the list needs to be split
    if list_of_ids.__len__() > 1994:

        # The list needs to be split as it is longer than 2000 chars
        # We do this by splitting the list by newlines and then appending them together into new strings until just before it reaches >2000 chars
        # The list of lines in the list of ids
        split_list = list_of_ids.splitlines(True)

        # The list of strings that we're going to send in the chat
        list_of_messages = [""]

        # We append the lines to messages in the list
        for line in split_list:

            # We check if the last message in the message list fits one more line (We save 6 chars to use for the backticks for the formatting)
            if len(list_of_messages[-1] + line) < 1994:

                # We add the line to the message
                list_of_messages[-1] += line

            # There wasn't enough space left so we create a new message
            else:

                # We create the new message
                list_of_messages.append(line)

    # The whole list of ids fit in one message
    else:

        list_of_messages = [list_of_ids]

    # We message the user the list of ids
    await client.send_message(message.author, "Here is the list of ids:")

    # We send all the messages
    for message_chunk in list_of_messages:
        # We send the message chunk
        await client.send_message(message.author, "```" + message_chunk + "```")


async def cmd_list_vanity_roles(message: discord.Message):
    """This method is used to list all available vanity roles on a server."""

    # We check if we should fill the vanity commands dict
    if vanity_commands == -1:
        await update_vanity_dictionary()

    # We check if the command was issued in a PM and if the server where the command was issued has any vanity roles
    if message.channel.is_private:
        # We tell the user that vanity roles do not exist in PMs
        await client.send_message(message.channel,
                                  "Vanity roles do not apply in PMs. Please use this command on a server that has enabled vanity roles.")

        return
    elif vanity_commands.get(message.server.id, {}) == {}:
        # We tell the user that the server doesn't have any vanity roles
        await client.send_message(message.channel, "This server does not have any vanity roles.")

        return

    # We tell the user that they're going to see the roles in their PMs
    await client.send_message(message.channel,
                              "Ok {0}! You'll see the roles in our PMs.".format(message.author.mention))

    # There are roles for this server, so we send them to the user in PMs (using the same mechanism for avoidance of the max char limit as we use in the help message)
    vanity_roles_chunks = ["The vanity roles for server **{0}** are:".format(message.server.name), ""]

    for vanity_role in vanity_commands[message.server.id]:
        # We make a formatted list entry
        role_list_entry = "--------------------\n\t**{0}**\n".format(vanity_role)

        # We check if we need to create a new chunk/message to send (because the total length would have been too high)
        if len(vanity_roles_chunks[-1] + role_list_entry) > 2000:
            vanity_roles_chunks.append(role_list_entry)
        else:
            vanity_roles_chunks[-1] += role_list_entry

    # The number of seconds to wait inbetween sending each chunk
    cooldown_duration = 0.5

    # We loop through all the chunks and send them in order
    for vanity_role_list_chunk in vanity_roles_chunks:
        # We send the chunk
        await client.send_message(message.author, vanity_role_list_chunk)
        # We wait the cooldown duration to not get ratelimited
        asyncio.sleep(cooldown_duration)


async def cmd_change_vanity_role(message: discord.Message):
    """This function is used to change or add a user to a vanity role of their choosing."""

    # We check if we should fill the vanity commands dict
    if vanity_commands == -1:
        await update_vanity_dictionary()

    # We check if the command was issued in a PM and if the server where the command was issued has any vanity roles
    if message.channel.is_private:
        # We tell the user that vanity roles do not exist in PMs
        await client.send_message(message.channel,
                                  "Vanity roles do not apply in PMs. Please use this command on a server that has enabled vanity roles.")

        return
    elif vanity_commands.get(message.server.id, {}) == {}:
        # We tell the user that the server doesn't have any vanity roles
        await client.send_message(message.channel, "This server does not have any vanity roles.")

        return

    # We remove the anna-bot mention and parse the role that the user wants to change to
    clean_message_content = remove_anna_mention(message)[len("role change "):].lower().strip()

    # We check if the role exists in the vanity command dictionary, if it doesn't we tell the user and return
    if not clean_message_content in vanity_commands[message.server.id]:
        await client.send_message(message.channel,
                                  message.author.mention + ", that role is not a vanity role, or does not exist.")

        return
    # We also check if the role exists right now, as the role may have been deleted
    elif str(vanity_commands[message.server.id][clean_message_content]) not in [x.id for x in message.server.roles]:
        await client.send_message(message.channel,
                                  message.author.mention + ", that role is not a vanity role, or does not exist.")

        return

    # We surround all this with a try except, to safeguard against permission errors
    try:

        # We check if we are higher in the hierarchy than the issuing user
        if message.server.me.top_role.position > message.author.top_role.position:

            # The role the user requested
            requested_role = discord.utils.find(
                lambda r: r.id == str(vanity_commands[message.server.id][clean_message_content]), message.server.roles)

            # We create a list of all the vanity roles
            vanity_roles = [x for x in message.server.roles if
                            (int(x.id) in vanity_commands[message.server.id].values() and x in message.author.roles)]

            # We remove the vanity roles
            await remove_roles(message.author, vanity_roles)

            # We log that we've given the user the role
            helpers.log_info(
                "Giving {0} ({1}), now has the role {2} ({3}) on server {4} ({5}), because they used the corresponding vanity command.".format(
                    message.author.name, message.author.id, requested_role.name, requested_role.id, message.server.name,
                    message.server.id))
            # We try to add the requested role to the user
            await client.add_roles(message.author, requested_role)

            # We tell the user that we've given them the vanity role
            await client.send_message(message.channel,
                                      message.author.mention + ", you now have the vanity role **{0}**".format(
                                          clean_message_content))
        else:
            # We go to the except clause
            raise PermissionError

    except discord.Forbidden as e:
        await client.send_message(message.channel,
                                  message.author.mention + ", I do not have permission to give or remove roles for you, and I can therefore not give you a vanity role.")
        helpers.log_info("Could not perform role operations on user {0} ({1}) because of too low permissions.".format(
            message.author.name, message.author.id))

    except PermissionError as e:
        await client.send_message(message.channel,
                                  message.author.mention + ", I do not have permission to give or remove roles for you, and I can therefore not give you a vanity role.")
        helpers.log_info("Could not perform role operations on user {0} ({1}) because of too low permissions.".format(
            message.author.name, message.author.id))


async def cmd_remove_vanity_roles(message: discord.Message):
    """This function is used to remove all vanity roles fort a server from a user."""

    # We check if we should fill the vanity commands dict
    if vanity_commands == -1:
        await update_vanity_dictionary()

    # We check if the command was issued in a PM and if the server where the command was issued has any vanity roles
    if message.channel.is_private:
        # We tell the user that vanity roles do not exist in PMs
        await client.send_message(message.channel,
                                  "Vanity roles do not apply in PMs. Please use this command on a server that has enabled vanity roles.")

        return
    elif vanity_commands.get(message.server.id, {}) == {}:
        # We tell the user that the server doesn't have any vanity roles
        await client.send_message(message.channel, "This server does not have any vanity roles.")

        return

    # We check if we have permission to remove roles from this user
    # We surround all this with a try except, to safeguard against permission errors
    try:
        # We check if we are higher in the hierarchy than the issuing user
        if message.server.me.top_role.position > message.author.top_role.position:

            # We create a list of all the vanity roles
            vanity_roles = [x for x in message.server.roles if
                            (int(x.id) in vanity_commands[message.server.id].values() and x in message.author.roles)]

            # We remove the vanity roles
            await remove_roles(message.author, vanity_roles)

            # We tell the user that we've removed their vanity role
            await client.send_message(message.channel,
                                      message.author.mention + ", I've now removed all vanity roles from you :D")

        else:

            # We go to the except clause
            raise PermissionError

    except discord.Forbidden as e:
        await client.send_message(message.channel,
                                  message.author.mention + ", I do not have permission to give or remove roles for you, and I can therefore not give you a vanity role.")

        helpers.log_info(
            "Could not perform role operations on user {0} ({1}) because of too low permissions.".format(
                message.author.name, message.author.id))

    except PermissionError as e:
        await client.send_message(message.channel,
                                  message.author.mention + ", I do not have permission to give or remove roles for you, and I can therefore not give you a vanity role.")
        helpers.log_info("Could not perform role operations on user {0} ({1}) because of too low permissions.".format(
            message.author.name, message.author.id))


async def cmd_add_warning(message: discord.Message):
    """This command is used to warn a player and keep adding warnings until the max warning number and then taking action on it"""

    # We check if the server supports warnings
    if message.server.id not in config["warning_roles"]:
        # Tell the user that this server doesn't support warnings
        await client.send_message(message.channel,
                                  message.author.mention + ", you can't warn people on this server because this server has not configured warning roles.")
        # Log it
        helpers.log_info(
            "User {0} tried to warn another user, but server {1} does not support warnings.".format(
                helpers.log_ob(message.author), helpers.log_ob(message.server)))
        # We're done here
        return

    # We check if the issuer has one of the authorised roles to add and remove warnings
    if not (any(i in [str(x.id) for x in message.author.roles] for i in config["warning_roles"][message.server.id][
        "roles_that_can_warn"]) or message.author == message.server.owner):
        # We tell the issuer that they are not authorised to add or remove warnings
        await client.send_message(message.channel,
                                  message.author.mention + ", you are not authorised to add or remove warnings from people on this server.")
        # We log it
        helpers.log_info(
            "User {0} tried to warn on server {1}, but was not authorised.".format(helpers.log_ob(message.author),
                                                                                   helpers.log_ob(message.server)))
        # We're done here
        return

    # We strip the message of the username, and then we check if it is a valid one
    username_raw = remove_anna_mention(message.content.strip())[len("warn "):].strip()

    # We try to get the user, by getting the one that the issuer mentioned
    target_user = discord.utils.get(message.server.members, mention=username_raw)

    # We check if the user actually exists
    if not isinstance(target_user, discord.Member):
        # We tell the user that they did not specify a valid user
        await client.send_message(message.channel,
                                  message.author.mention + ", you did not specify a valid user. Make sure to use @mentions :smiley:")
        # Log it
        helpers.log_info("User {0} tried to warn user on server {1}, but did not specify a valid user.".format(
            helpers.log_ob(message.author), helpers.log_ob(message.server)))
        # We're done here
        return

    # We check that we have role add, role remove, ban/kick, and higher role list position that the target. We also check that the issuer is higher in the role hierarchy than the target
    if (message.author.top_role.position <= target_user.top_role.position) or (
            not check_add_remove_roles(target_user, message.channel)) or (not (
            message.channel.permissions_for(message.server.me).ban_members if
            config["warning_roles"][message.server.id][
                "ban_after_warnings"] else message.channel.permissions_for(message.server.me).kick_members)):
        print(message.author.top_role.position <= target_user.top_role.position)

        # We tell the user that we do not have the proper permissions
        await client.send_message(message.channel,
                                  message.author.mention + ", you or I do not have the proper permissions to warn that player.")
        # Log it
        helpers.log_info("User {0} tried to warn user {1} on server {2}, but did not have proper permissions.".format(
            helpers.log_ob(message.author), helpers.log_ob(target_user), helpers.log_ob(message.server)))

        # We're done here
        return

    # Telling the user and logging that we're warning someone
    await client.send_message(message.channel, message.author.mention + " ok, warning " + target_user.mention + ".")
    helpers.log_info(
        "User {0} is adding a warning to user {1} on server {2}".format(helpers.log_ob(message.author),
                                                                        helpers.log_ob(target_user),
                                                                        helpers.log_ob(message.server)))

    # We check what warning the target user is on
    target_user_warning_level = -1

    for warning_level, warning_role_id in enumerate(config["warning_roles"][message.server.id]["warning_role_ids"]):
        # We check if the user has the role
        if warning_role_id in [str(x.id) for x in target_user.roles]:
            target_user_warning_level = warning_level

    # The dict of warning roles
    warning_role_list = {}

    # We generate a list of all the warning roles, we do this in the correct order aswell
    for warning_level, warning_role_id in enumerate(config["warning_roles"][message.server.id]["warning_role_ids"]):
        # We get the role, if it doesn't exist we just let it be None
        warning_role_list[warning_level] = discord.utils.get(message.server.roles, id=str(warning_role_id))

    # We remove all warning roles from the user
    await remove_roles(target_user, [warning_role_list[inx] for inx in warning_role_list if
                                     isinstance(warning_role_list[inx], discord.Role)])

    # We check if the user is going to exceed the max warning level
    if target_user_warning_level == len(config["warning_roles"][message.server.id]["warning_role_ids"]) - 1:
        # We check if we should kick or ban them
        if config["warning_roles"][message.server.id]["ban_after_warnings"]:
            # We ban them
            await client.ban(target_user, 0)
            # We tell the issuer that we banned them
            await client.send_message(message.channel,
                                      message.author.mention + ", " + target_user.mention + " has been banned since they reached the maximum number of warnings.")
            # Log it
            helpers.log_info(
                "User {0} got banned by {1} from server {0}.".format(helpers.log_ob(target_user),
                                                                     helpers.log_ob(message.author),
                                                                     helpers.log_ob(message.server)))
            # We're done now
            return
        else:
            # We kick them
            await client.kick(target_user)
            # We tell the issuer that we kicked them
            await client.send_message(message.channel,
                                      message.author.mention + ", " + target_user.mention + " has been kicked since they reached the maximum number of warnings.")
            # Log it
            helpers.log_info(
                "User {0} got kicked by {1} from server {0}.".format(helpers.log_ob(target_user),
                                                                     helpers.log_ob(message.author),
                                                                     helpers.log_ob(message.server)))
            # We're done now
            return

    # We get the role that the target user should get
    new_warning_role = discord.utils.get(message.server.roles, id=str(
        config["warning_roles"][message.server.id]["warning_role_ids"][target_user_warning_level + 1]))

    # We check if the configured warning is valid
    if isinstance(new_warning_role, discord.Role):
        # We give the target user the role
        await client.add_roles(target_user, new_warning_role)
        # We tell the issuer that the target has been warned
        await client.send_message(message.channel,
                                  message.author.mention + ", ok, I have now warned " + target_user.mention + ", who now has " + str(
                                      (target_user_warning_level + 2)) + " warning(s).")
        # We log it
        helpers.log_info(
            "User {0} warned user {1} on server {2}".format(helpers.log_ob(message.author), helpers.log_ob(target_user),
                                                            helpers.log_ob(message.server)))
    else:
        # We tell the issuer that the warning roles aren't set up correctly
        await client.send_message(message.channel,
                                  message.author.mention + ", I tried to warn " + target_user.mention + ", but the warning role configuration for this server is incorrect.")
        # We log it
        helpers.log_warning(
            "User {0} tried to warn user {1} on server {2}, but the server warning role configuration was incorrect".format(
                helpers.log_ob(message.author), helpers.log_ob(target_user), helpers.log_ob(message.server)))


async def cmd_remove_warning(message: discord.Message):
    """This command is used to remove a warning from a player if they have one"""

    # We check if the server supports warnings
    if message.server.id not in config["warning_roles"]:
        # Tell the user that this server doesn't support warnings
        await client.send_message(message.channel,
                                  message.author.mention + ", you can't remove warnings from people on this server because this server has not configured warning roles.")
        # Log it
        helpers.log_info(
            "User {0} tried to unwarn another user, but server {1} does not support warnings.".format(
                helpers.log_ob(message.author), helpers.log_ob(message.server)))
        # We're done here
        return

    # We check if the issuer has one of the authorised roles to add and remove warnings
    if not (any(i in [str(x.id) for x in message.author.roles] for i in config["warning_roles"][message.server.id][
        "roles_that_can_warn"]) or message.author == message.server.owner):
        # We tell the issuer that they are not authorised to add or remove warnings
        await client.send_message(message.channel,
                                  message.author.mention + ", you are not authorised to add or remove warnings from people on this server.")
        # We log it
        helpers.log_info(
            "User {0} tried to warn on server {1}, but was not authorised.".format(helpers.log_ob(message.author),
                                                                                   helpers.log_ob(message.server)))
        # We're done here
        return

    # We strip the message of the username, and then we check if it is a valid one
    username_raw = remove_anna_mention(message.content.strip())[len("unwarn "):].strip()

    # We try to get the user, by getting the one that the issuer mentioned
    target_user = discord.utils.get(message.server.members, mention=username_raw)

    # We check if the user actually exists
    if not isinstance(target_user, discord.Member):
        # We tell the user that they did not specify a valid user
        await client.send_message(message.channel,
                                  message.author.mention + ", you did not specify a valid user. Make sure to use @mentions :smiley:")
        # Log it
        helpers.log_info("User {0} tried to unwarn user on server {1}, but did not specify a valid user.".format(
            helpers.log_ob(message.author), helpers.log_ob(message.server)))
        # We're done here
        return

    # We check that we have role add, role remove, ban/kick, and higher role list position that the target. We also check that the issuer is higher in the role hierarchy than the target
    if (message.author.top_role.position <= target_user.top_role.position) or (
            not check_add_remove_roles(target_user, message.channel)) or (not (
            message.channel.permissions_for(message.server.me).ban_members if
            config["warning_roles"][message.server.id][
                "ban_after_warnings"] else message.channel.permissions_for(message.server.me).kick_members)):
        # We tell the user that we do not have the proper permissions
        await client.send_message(message.channel,
                                  message.author.mention + ", you or I do not have the proper permissions to remove a warning from that player.")
        # Log it
        helpers.log_info("User {0} tried to unwarn user {1} on server {2}, but did not have proper permissions.".format(
            helpers.log_ob(message.author), helpers.log_ob(target_user), helpers.log_ob(message.server)))

        # We're done here
        return

    # Telling the user and logging that we're unwarning someone
    await client.send_message(message.channel,
                              message.author.mention + " ok, removing a warning from " + target_user.mention + ".")
    helpers.log_info(
        "User {0} is removing a warning from user {1} on server {2}".format(helpers.log_ob(message.author),
                                                                            helpers.log_ob(target_user),
                                                                            helpers.log_ob(message.server)))

    # We check what warning the target user is on
    target_user_warning_level = -1

    for warning_level, warning_role_id in enumerate(config["warning_roles"][message.server.id]["warning_role_ids"]):
        # We check if the user has the role
        if warning_role_id in [str(x.id) for x in target_user.roles]:
            target_user_warning_level = warning_level

    # The dict of warning roles
    warning_role_list = {}

    # We generate a list of all the warning roles, we do this in the correct order aswell
    for warning_level, warning_role_id in enumerate(config["warning_roles"][message.server.id]["warning_role_ids"]):
        # We get the role, if it doesn't exist we just let it be None
        warning_role_list[warning_level] = discord.utils.get(message.server.roles, id=str(warning_role_id))

    # We remove all warning roles from the user
    await remove_roles(target_user, [warning_role_list[inx] for inx in warning_role_list if
                                     isinstance(warning_role_list[inx], discord.Role)])

    # We check if the user should get a lower warnings level, or if they now should have 0 warnings
    if target_user_warning_level == 0:
        # We tell the issuer that we've removed a warning
        await client.send_message(message.channel,
                                  message.author.mention + ", ok, I have now removed the warning from " + target_user.mention + ".")
        # We log it
        helpers.log_info(
            "User {0} has removed the last warning from user {1} on server {2}".format(helpers.log_ob(message.author),
                                                                                       helpers.log_ob(target_user),
                                                                                       helpers.log_ob(message.server)))
        # We're done here
        return

    # We get the role that the target user should get
    new_warning_role = discord.utils.get(message.server.roles, id=str(
        config["warning_roles"][message.server.id]["warning_role_ids"][target_user_warning_level - 1]))

    # We check if the configured warning is valid
    if isinstance(new_warning_role, discord.Role):
        # We give the target user the role
        await client.add_roles(target_user, new_warning_role)
        # We tell the issuer that the target has been warned
        await client.send_message(message.channel,
                                  message.author.mention + ", ok, I have now removed a warning from " + target_user.mention + ", who now has " + str(
                                      target_user_warning_level) + " warning(s).")
        # We log it
        helpers.log_info("User {0} unwarned user {1} on server {2}".format(helpers.log_ob(message.author),
                                                                           helpers.log_ob(target_user),
                                                                           helpers.log_ob(message.server)))
    else:
        # We tell the issuer that the warning roles aren't set up correctly
        await client.send_message(message.channel,
                                  message.author.mention + ", I tried to remove a warning from " + target_user.mention + ", but the warning role configuration for this server is incorrect.")
        # We log it
        helpers.log_warning(
            "User {0} tried to unwarn user {1} on server {2}, but the server warning role configuration was incorrect".format(
                helpers.log_ob(message.author), helpers.log_ob(target_user), helpers.log_ob(message.server)))


async def cmd_admin_broadcast(message: discord.Message):
    """This method is used to handle admins wanting to broadcast a message to all servers and channel that anna-bot is in."""

    # We know that the issuing user is an admin
    if not message.channel.is_private:
        # The message to send in all the channels, we do this by just stripping off the first characters (the command part of the issuing message)
        message_content = remove_anna_mention(message).strip()[16:]

    else:
        message_content = message.content

    # Logging that we're going to broadcast the message
    helpers.log_info(message.author.name + " issued a broadcast of the message \"" + message_content + "\"!")

    # Telling the issuing user that we're broadcasting
    await client.send_message(message.channel, "I'm on it!")

    # Looping through all the channels on all the servers we have access to
    for server in client.servers:
        for channel in server.channels:

            # Doing some sanity checking (you can't send a message in a voice client)
            if channel.type == discord.ChannelType.text:
                # Checking permissions for our bot user in the current channel
                if channel.permissions_for(server.me).send_messages:
                    # We can (probably, since there might be channel level overrides):
                    await client.send_message(channel, "Broadcast: " + message_content)

    # Logging that we're done doing the broadcasting
    helpers.log_info(message.author.name + "'s broadcast of the message \"" + message_content + "\" is now done.")

    # Telling the issuing user that we're done broadcasting
    await client.send_message(message.channel, "Ok I'm done broadcasting :smile:")


async def cmd_admin_reload_config(message: discord.Message):
    """This method is used to handle an admin user wanting us to reload the config file."""

    # Telling the issuing user that we're reloading the config
    # Checking if we're in a private channel or if we're in a regular channel so we can format our message properly
    if message.channel.is_private:
        await client.send_message(message.channel, "Ok, I'm reloading it right now!")
    else:
        await client.send_message(message.channel, "Ok " + message.author.mention + ", I'm reloading it right now!")

    # Telling the issuing user that we're reloading the config file
    await client.send_message(message.channel, "Reloading the config file...")

    # Logging that we're loading the config
    helpers.log_info("Reloading the config file...")

    # Loading the config file and then parsing it as json and storing it in a python object
    with open("config.json", mode="r", encoding="utf-8") as config_file:
        global config
        config = json.load(config_file)

    # Logging that we're done loading the config
    helpers.log_info("Done reloading the config")

    # Telling the issuing user that we're done reloading the config file
    await client.send_message(message.channel, "Done reloading the config file!")

    # Telling the issuing user that we're updating the vanity command dict
    await client.send_message(message.channel, "Updating vanity commands...")

    # Logging that we're updating the vanity commands
    helpers.log_info("Updating vanity commands...")

    # Updating the vanity command dict because the config file could have changed the vanity setup
    await update_vanity_dictionary()

    # Logging that we're done updating the vanity commands
    helpers.log_info("Done updating vanity commands")

    # Telling the issuing user that we're done updating the vanity command dict
    await client.send_message(message.channel, "Done updating vanity commands!")

    # Telling the issuing user that we're reloading the config
    # Checking if we're in a private channel or if we're in a regular channel so we can format our message properly
    if message.channel.is_private:
        await client.send_message(message.channel, "Ok, I'm done reloading now :smile:")
    else:
        await client.send_message(message.channel,
                                  "Ok " + message.author.mention + ", I'm done reloading it now :smile:")


async def cmd_admin_change_icon(message: discord.Message):
    """This admin command is used to change the icon of the bot user to a specified image."""

    # Checking if the message has an attachment
    if message.attachments:

        # Looping through the attachments until we find a valid one to use for an icon
        for attachment in message.attachments:

            # Checking if the message has a valid image attachment (just checking if the height and width dict keys exist)
            if ("width" in attachment) and ("height" in attachment):
                # We tell the user that we're changing the icon
                await client.send_message(message.channel,
                                          "Ok {0:s}, now changing the icon to the image you sent!".format(
                                              message.author.mention))

                # We break out of the for loop as we are done
                # Note that as python does not change the last value of a for loop "counter" (in this case attachment) after the for loop has been exited,
                # and that neither for loops nor if statements create new namespaces, the last value of that variable is still a regular variable after the for loop has been executed.
                break

        # This is an else statement for the for loop (no pun intended), which executes after a for loop if the for loop doesn't stop because of a break statement
        else:

            # We tell the user that they didn't attach a valid icon image to their command message
            await client.send_message(message.channel,
                                      "I can't do that {0:s} because you didn't attach an image for me to set my icon to.".format(
                                          message.author.mention))

            # We're done here now
            return

    # The command message didn't have any attachments
    else:

        # We tell the user that they didn't attach a valid icon image to their command message
        await client.send_message(message.channel,
                                  "I can't do that {0:s} because you didn't attach an image for me to set my icon to.".format(
                                      message.author.mention))

        # We're done here now
        return

    # Logging that we're going to change the icon of the bot account
    helpers.log_info(
        "Changing {0:s}'s icon to {1:s} because admin {2:s} ({3:s}) triggered the change icon command.".format(
            client.user.name, attachment["url"], message.author.name, message.author.mention))

    # We download the image and upload it to the discord command simultaneously
    await client.edit_profile(avatar=requests.get(attachment["url"]).content)

    # Logging and telling the user that we're done changing the icon
    helpers.log_info("Now done changing the icon.")
    await client.send_message(message.channel, "Now done changing the icon.")


async def cmd_admin_list_referrals(message: discord.Message):
    """This function is used to send back the contents of the referrals file to the issuing admin. Mostly for debug purposes."""

    # We tell the user that we're sending the file in a PM
    await client.send_message(message.channel, "Ok! You'll see the file in our PMs.")

    # We open the file and send it
    with open("referrals.json", mode="rb") as referrals_file:
        # We send the file
        await client.send_file(message.author, referrals_file, content="Here you go!")


def is_message_command(message: discord.Message):
    """This function is used to check whether a message is trying to issue an anna-bot command"""

    # The weird mention for the bot user, the string manipulation is due to mention strings not being the same all the time
    client_mention = client.user.mention[:2] + "!" + client.user.mention[2:]

    # We return if the message is a command or not
    return message.content.lower().strip().startswith(client_mention) or message.content.lower().strip().startswith(
        client.user.mention)


def remove_anna_mention(message):
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


def check_add_remove_roles(member: discord.Member, channel: discord.Channel) -> bool:
    """This method returns true if the currently logged in client can remove and add roles from the passed member in the passed channel."""

    return channel.permissions_for(
        member.server.me).manage_roles and member.top_role.position < member.server.me.top_role.position


async def remove_roles(member: discord.Member, roles: list):
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
    helpers.log_info(
        "Removing roles from user {0} took {1} retries.".format(helpers.log_ob(member), i))


async def update_vanity_dictionary():
    """This function uses the config to create a dictionary for the role command, which makes it possible to change roles to a predetermined list of roles."""

    # We wait until the client is logged in
    await client.wait_until_ready()

    # The lookup dictionary for vanity commands
    vanity_dict = {}

    # We fill the dict with the commands that are enabled
    for server_id in config["vanity_role_commands"]["server_ids_and_roles"]:
        # This is the dict for the current server, which we will fill with command/role name, to role id mappings
        vanity_dict[server_id] = {}

        # We get the server object and a list of the role ids the server has
        server = client.get_server(server_id)

        if server is not None:
            server_role_ids = [x.id for x in server.roles]

            # We loop through all the commands
            for role_name in config["vanity_role_commands"]["server_ids_and_roles"][server_id]:
                # We check if the role id exists on the specified server
                if str(config["vanity_role_commands"]["server_ids_and_roles"][server_id][role_name]) in server_role_ids:
                    # It exists, so we add it to the dictionary
                    vanity_dict[server_id][role_name.lower().strip()] = \
                        config["vanity_role_commands"]["server_ids_and_roles"][server_id][role_name]

                else:
                    # The role does not exist, so we tell the user to fix their config
                    helpers.log_warning(
                        "Vanity command \"{0:s}\", could not be created as role with id {1:d} does not exist on server {2:s}.".format(
                            role_name, config["vanity_role_commands"]["server_ids_and_roles"][server_id][role_name],
                            server.name))

    global vanity_commands
    vanity_commands = vanity_dict


# Logging that we're loading the config
helpers.log_info("Loading the config file...")

# The config object
config = {}

# Loading the config file and then parsing it as json and storing it in a python object
with open("config.json", mode="r", encoding="utf-8") as config_file:
    config = json.load(config_file)

# Logging that we're done loading the config
helpers.log_info("Done loading the config")

# The commands people can use (excluding the exclamation mark) and the method that will be called when a command is used
public_commands = [dict(command="invite", method=cmd_invite_link,
                        helptext="Generate an invite link to the current channel, the link will be valid for " + str(
                            config["invite_cmd"]["invite_valid_time_min"]) + " minutes and " + str(
                            config["invite_cmd"]["invite_max_uses"]) + " use[s]."),
                   dict(command="add-bot", method=cmd_gen_bot_invite,
                        helptext="Generate an invite link so you can add the bot to your own server, (with proper permissions of course)."),
                   dict(command="anna-stats", method=cmd_report_stats,
                        helptext="Report some stats about anna."),
                   dict(command="voice join", method=cmd_join_voice_channel,
                        helptext="Joins the specified voice channel if anna can access it."),
                   dict(command="voice leave", method=cmd_leave_voice_channel,
                        helptext="Leaves the specified voice channel if anna is connected to it."),
                   dict(command="voice play youtube", method=cmd_voice_play_youtube,
                        helptext="Plays the audio of the given youtube link at the (optional) specified volume (0% -> 200%). This might work with other types of video streaming sites, but I give no guarantee."),
                   dict(command="voice volume", method=cmd_voice_set_volume,
                        helptext="Change the volume of the audio that anna plays (0% -> 200%)."),
                   dict(command="voice toggle", method=cmd_voice_play_toggle,
                        helptext="Toggle (pause or unpause) the audio anna is currently playing."),
                   dict(command="voice stop", method=cmd_voice_play_stop,
                        helptext="Stop the audio that anna is currently playing."),
                   dict(command=config["start_server_cmd"]["start_server_command"], method=cmd_start_server,
                        helptext="Start the minecraft server (if the channel and users have the necessary permissions to do so)."),
                   dict(command="list ids", method=cmd_list_ids,
                        helptext="PMs you with a list of all the ids of all the things on the server. This includes roles, users, channels, and the server itself."),
                   dict(command="role change", method=cmd_change_vanity_role,
                        helptext="Use this to change to another vanity role (**role list** to list all available roles)."),
                   dict(command="role remove", method=cmd_remove_vanity_roles,
                        helptext="Use this to remove all your vanity roles."),
                   dict(command="role list", method=cmd_list_vanity_roles,
                        helptext="PMs you with a list of all available roles for this server."),
                   dict(command="whoru", method=cmd_who_r_u,
                        helptext="Use this if you want an explanation as to what anna-bot is."),
                   dict(command="help", method=cmd_help, helptext="Do I really need to explain this..."),
                   dict(command="warn", method=cmd_add_warning,
                        helptext="Gives a warning to a player, if they reach the maximum number of warnings, (depending on the server's settings) they are banned or kicked. This command can only be used by certain roles."),
                   dict(command="unwarn", method=cmd_remove_warning,
                        helptext="Removes a warning from a player. This command can only be used by certain players.")
                   ]

# The commands authorised users can use, these are some pretty powerful commands, so be careful with which users you give administrative access to the bot to
admin_commands = [dict(command="broadcast", method=cmd_admin_broadcast,
                       helptext="Broadcasts a message to all the channels that anna-bot has access to."),
                  dict(command="reload config", method=cmd_admin_reload_config,
                       helptext="Reloads the config file that anna-bot uses."),
                  dict(command="change icon", method=cmd_admin_change_icon,
                       helptext="Changes the anna-bot's profile icon to an image that the user attaches to the command message."),
                  dict(command="list referrals", method=cmd_admin_list_referrals,
                       helptext="Sends a copy of the referrals file.")
                  ]

# The functions to call when someone joins the server, these get passed the member object of the user who joined
join_functions = [join_welcome_message,
                  join_automatic_role,
                  join_referral_asker]

# We define the vanity command dictionary, this will be filled with information the first time a user uses a vanity command or if an admin uses the reload config command
vanity_commands = -1

# The list of message ids (this list will fill and empty) that the command checker should ignore
ignored_command_message_ids = []

# The list of tuples of voice stream players and server ids
server_and_stream_players = []

# Logging that we're starting the bot
helpers.log_info("Anna-bot is now logging in (you'll notice if we get any errors)")

# Storing the time at which the bot was started
start_time = time.time()

# Starting and authenticating the bot
client.run(config["credentials"]["token"])

# Calculating and formatting how long the bot was online so we can log it, this is on multiple statements for clarity
end_time = time.time()
uptime_secs_noformat = (end_time - start_time) // 1
formatted_uptime = helpers.get_formatted_duration_fromtime(uptime_secs_noformat)

# Logging that we've stopped the bot
helpers.log_info(
    "Anna-bot is now exiting (you'll notice if we get any errors), we have been up for %s." % formatted_uptime)
