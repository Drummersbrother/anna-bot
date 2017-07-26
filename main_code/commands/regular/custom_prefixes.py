import discord

from ... import command_decorator, helpers


@command_decorator.command("set prefix ", "Sets anna-bots prefix for this server. The prefix might take a minute to update. "
                                          "Set the prefix to @mention to use real @mention instead of a text prefix.")
@helpers.async_uses_persistent_file("configured_prefixes.json")
async def cmd_set_prefix(prefix_data: dict, message: discord.Message, client: discord.Client, config: dict):
    """Sets the prefix for a server, by writing it to disk. This means we don't actually update the dict in helpers.py."""

    # This can obviously not be used in PMs
    if message.channel.is_private:
        await client.send_message(message.author, "PM commands do not have prefixes, and as such, this command can not be used in PMs.")
        return

    # The issuing user needs to have the manage server permission or be an anna admin
    if ((not helpers.is_member_anna_admin(message.author, config)) or
        not (message.author.server_permissions.administrator or message.author.server_permissions.manage_server)):
        await client.send_message(message.channel, message.author.mention + ", you are not authorised to use this command. "
                            "This command requires either the `administrator` permission or the `manage server` permission.")
        return

    # Since the prefix file is a dict with server ids as keys and prefixes as values,
    # we parse the value, check the validity and then insert the value at the key
    raw_prefix_string = helpers.remove_anna_mention(client, message).strip()[len("set prefix "):].strip()

    # We check that the message is not too long or too short
    if not (1 < len(raw_prefix_string) < 50):
        await client.send_message(message.channel, message.author.mention +
                                  ", that prefix is not of proper length, minimum length is **1** and max is **50**.")
        return

    # If the data is @mention, we just remove the entry if it exists
    if raw_prefix_string == "@mention":
        prefix_data.pop(str(message.server.id), None)
    else:
        prefix_data[str(message.server.id)] = raw_prefix_string

    # We tell the user the command is done
    await client.send_message(message.channel, message.author.mention + ", the prefix is now **{0}**. "
                                                                        "This might take some time to activate."
                              .format(helpers.remove_discord_formatting(raw_prefix_string)[0]))

    return prefix_data,

