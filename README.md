# Anna-bot

[![Join the chat at https://gitter.im/anna-bot/Lobby](https://badges.gitter.im/anna-bot/Lobby.svg)](https://gitter.im/anna-bot/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
A discord bot created for the https://mcevalonia.com minecraft server's discord server, but usable by all discord servers.

## Some demonstrations
![A command that gives a list of the available commands.](demo_gifs/output_gifs/help.gif)
![A command that warns a user.](demo_gifs/output_gifs/warn.gif)
![A command that runs arbitrary python code from an admin user.](demo_gifs/output_gifs/admin_eval.gif)
![A command that displays an image of a cat.](demo_gifs/output_gifs/cat.gif)
![A command that displays an image of a kitten.](demo_gifs/output_gifs/kitten.gif)
![A command that displays an image of a dog.](demo_gifs/output_gifs/dog.gif)
![A command that lets you play chess against the computer.](demo_gifs/output_gifs/chess.gif)
![A command that creates a discord invite link for the server.](demo_gifs/output_gifs/invite.gif)
![A command that plays a list of video links in order in a voice channel.](demo_gifs/output_gifs/playlist.gif)
![A command that displays info about a particular overwatch battletag.](demo_gifs/output_gifs/overwatch.gif)

## How to run
### Dependencies:
This bot uses Python 3.5.

Install the package dependencies with pip (probably useful to be done in a virtualenv):
```
pip3.5 install -r requirements.txt
```

### Running it
1. Clone the repository
2. Create a discord bot account ([here](https://discordapp.com/developers/applications/me))
3. Create a [Mashape](https://market.mashape.com/register) account and retrieve an api key for the default application ([instructions](http://docs.mashape.com/api-keys#changing))
4. Edit `config.json`, don't forget to put in the bot account auth tokens and Mashape api key:)
5. Run `python3.5 anna_launcher.py` with appropriate flags (`python3.5 anna_launcher -sr` to run and restart if it exits for some reason)
6. Exit the bot and launcher with `CTRL+C`.

(Btw, the bot's name comes from a swedish pop song ;) )
