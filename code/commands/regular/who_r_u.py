import discord


async def who_r_u(message: discord.Message, client: discord.Client, config: dict):
    """This method is called to handle someone wanting to know who/what anna-bot is."""

    # Just sending an explanation back in the same channel as the command was issued in
    await client.send_message(message.channel,
                              "Anna-bot is a discord bot written in python (discord.py), created by Hugo Berg (drummersbrother), for the Evalonia minecraft server (mcevalonia.com).\nDo you want to host your own anna-bot, or just look at and maybe even contribute to the code?\nhttps://github.com/Drummersbrother/anna-bot :wink:")
