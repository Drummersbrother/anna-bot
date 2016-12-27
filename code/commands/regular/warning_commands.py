import discord

from ... import command_decorator
from ... import helpers


@command_decorator.command("warn",
                           "Gives a warning to a user, if they reach the maximum number of warnings, (depending on the server's settings) they are banned or kicked. This command can only be used by certain roles.")
async def add_warning(message: discord.Message, client: discord.Client, config: dict):
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
    username_raw = helpers.remove_anna_mention(client, message.content.strip())[len("warn "):].strip()

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
            not helpers.check_add_remove_roles(target_user, message.channel)) or (not (
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
    await helpers.remove_roles(client, target_user, [warning_role_list[inx] for inx in warning_role_list if
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


@command_decorator.command("unwarn", "Removes a warning from a user. This command can only be used by certain roles.")
async def remove_warning(message: discord.Message, client: discord.Client, config: dict):
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
    username_raw = helpers.remove_anna_mention(client, message.content.strip())[len("unwarn "):].strip()

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
            not helpers.check_add_remove_roles(target_user, message.channel)) or (not (
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
    await helpers.remove_roles(client, target_user, [warning_role_list[inx] for inx in warning_role_list if
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
