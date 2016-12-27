import asyncio

import discord

from ... import command_decorator
from ... import helpers

# The vanity commands variable, set to -1 when not initialised
vanity_commands = -1


@command_decorator.command("role list", "PMs you with a list of all available vanity roles for this server.")
async def list_vanity_roles(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to list all available vanity roles on a server."""

    # We check if we should fill the vanity commands dict
    if vanity_commands == -1:
        await update_vanity_dictionary(client, config)

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


@command_decorator.command("role change",
                           "Use this to change to another vanity role (**role list** to list all available roles).")
async def change_vanity_role(message: discord.Message, client: discord.Client, config: dict):
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
    clean_message_content = helpers.remove_anna_mention(message)[len("role change "):].lower().strip()

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
            await helpers.remove_roles(client, message.author, vanity_roles)

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


@command_decorator.command("role remove", "Use this to remove all your vanity roles.")
async def remove_vanity_roles(message: discord.Message, client: discord.Client, config: dict):
    """This function is used to remove all vanity roles for a server from a user."""

    # We check if we should fill the vanity commands dict
    if vanity_commands == -1:
        await update_vanity_dictionary(client, config)

    # We check if the command was issued in a PM and if the server where the command was issued has any vanity roles
    if message.channel.is_private:
        # We tell the user that vanity roles do not exist in PMs
        await client.send_message(message.channel,
                                  "Vanity roles do not apply in PMs. Please use this command on a server that has enabled vanity roles.")

        return
    elif message.server.id not in vanity_commands:
        # We tell the user that the server doesn't have any vanity roles
        await client.send_message(message.channel, "This server does not have any vanity roles.")

        return

    # We check if we have permission to remove roles from this user
    if helpers.check_add_remove_roles(message.author, message.channel):

        # We create a list of all the vanity roles
        vanity_roles = [x for x in message.server.roles if
                        (int(x.id) in vanity_commands[message.server.id].values() and x in message.author.roles)]

        # We remove the vanity roles
        await helpers.remove_roles(client, message.author, vanity_roles)

        # We tell the user that we've removed their vanity role
        await client.send_message(message.channel,
                                  message.author.mention + ", I've now removed all vanity roles from you :D")

    else:

        await client.send_message(message.channel,
                                  message.author.mention + ", I do not have permission to give or remove roles for you, and I can therefore not give you a vanity role.")

        helpers.log_info(
            "Could not perform role operations on user {0} ({1}) because of too low permissions.".format(
                message.author.name, message.author.id))


async def update_vanity_dictionary(client: discord.Client, config: dict):
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
