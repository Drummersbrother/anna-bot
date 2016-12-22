import discord


async def list_ids(message: discord.Message, client: discord.Client, config: dict):
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
