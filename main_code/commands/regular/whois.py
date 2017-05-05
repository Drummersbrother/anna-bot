import discord

from ... import command_decorator
from ... import helpers


@command_decorator.command("whois", "Use this to get info about a user.")
async def whois(message: discord.Message, client: discord.Client, config: dict):
	"""This method is called to handle someone wanting to know some info about a user."""

	# We strip the message of the username, and then we check if it is a valid one
	username_raw = helpers.remove_anna_mention(client, message.content.strip())[len("whois "):].strip()

	# We try to get the user, by getting the one that the issuer mentioned
	target_user = discord.utils.get(message.server.members, mention=username_raw)

	# We check if the user actually exists
	if not target_user:
		# We tell the user that they did not specify a valid user
		await client.send_message(message.channel,
								  message.author.mention + ", you did not specify a valid user. Make sure to use @mentions.")
		# Log it
		helpers.log_info(
			"User {0} tried to use the whois command on server {1}, but did not specify a valid user.".format(
				helpers.log_ob(message.author), helpers.log_ob(message.server)))
		# We're done here
		return

	# The non-cleaned username + discriminator of the target user
	target_username_full_uncleaned = target_user.name + "#" + target_user.discriminator

	# The username + discriminator of the target user, cleaned up to be safe for discord
	target_username_full = helpers.remove_discord_formatting(
		target_user.name)[0] + "#" + target_user.discriminator

	# We create the embed that shows user info
	user_embed = discord.Embed(title="Who is **{0}**?".format(
		target_username_full), colour=discord.Colour.dark_grey())

	# We add a thumbnail, which is the user's icon
	user_embed.set_thumbnail(
		url=(target_user.default_avatar_url if not target_user.avatar_url else target_user.avatar_url))

	# We add an author field, looks good
	user_embed.set_author(name="{0}.".format(target_username_full),
						  icon_url="https://discordapp.com/assets/2c21aeda16de354ba5334551a883b481.png")

	# We add some info fields about the user
	user_embed.add_field(name="Join date:", value=target_user.joined_at.strftime("%Y, %b-%d, %H:%M:%S %Z"))
	user_embed.add_field(name="Current status:", value=str(target_user.status))
	user_embed.add_field(name="Currently playing:",
						 value=target_user.game.name if target_user.game else "(Not playing anything)")
	user_embed.add_field(name="Highest role on this server:",
						 value=target_user.top_role.name if not target_user.top_role.is_everyone else "This user doesn't have any roles.")
	user_embed.add_field(name="Nickname:",
						 value=target_user.nick if target_user.nick else "This user doesn't have a nickname.")

	# We check if the user is a bot account
	if target_user.bot:
		user_embed.set_footer(
			text="This user is a bot. More info about bots here: https://discordapp.com/developers/docs/topics/oauth2#bot-vs-user-accounts")

	# We send back the message with user info embed
	await client.send_message(message.channel, message.author.mention + ", here is some info about **{0}**".format(
		target_username_full), embed=user_embed)

	# We log it
	helpers.log_info("Sent user info about {0} ({1}) to {2} ({3}).".format(
		target_username_full_uncleaned, target_user.id, message.author.name, message.author.id))
