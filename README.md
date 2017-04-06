# Anna-bot

[![Join the chat at https://gitter.im/anna-bot/Lobby](https://badges.gitter.im/anna-bot/Lobby.svg)](https://gitter.im/anna-bot/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
A discord bot created for the https://mcevalonia.com minecraft server's discord server, but usable by all discord servers.

## How to run
### Dependencies:
```
python3.5
discord.py 0.16.X (https://github.com/Rapptz/discord.py)
youtube_dl
ffmpeg/avconv
aiohttp
cchardet
aiodns
overwatch-api
```

### Running it
1. Clone the repository
2. Create a discord bot account ([here](https://discordapp.com/developers/applications/me))
3. Edit `config.json`, don't forget the bot account auth tokens :)
4. Run `python3.5 anna_launcher.py` with appropriate flags (`python3.5 anna_launcher -sr` to run and restart if it exits for some reason)
5. Exit the bot and launcher with `CTRL+C`, or exit double-tapping `CTRL+C` if you used the `-r` flag.

(Btw, the bot's name comes from a swedish pop song ;) )
