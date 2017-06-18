import asyncio
import string
import time
from io import BytesIO
from urllib.parse import quote

import aiohttp
import async_timeout
import chess as chess
import chess.uci as uci
import discord

from ... import command_decorator
from ... import helpers

# The current chess game sessions, indexed by user id
chess_sessions = {}


# TODO implement matches user-user

class ChessSession(object):
    """Represents one chess game for one user. This is used with async with. Can be used multiple times, but only within async with statements."""

    def __init__(self, user: discord.User, computation_timeout_seconds: float, operation_timeout: float,
                 difficulty: int,
                 engine_path: str, num_search_threads: int = 1, user_side_is_white: bool = True):
        self.user = user
        self.num_search_threads = num_search_threads
        self.cpu_timeout = computation_timeout_seconds
        self.op_timeout = operation_timeout
        self.difficulty = difficulty
        self.last_time_used = time.time()
        self.board = chess.Board()
        self.engine_path = engine_path
        self.user_side_is_white = user_side_is_white
        self.is_thinking = False
        self.engine = None
        self._in_with_statement = False

    @staticmethod
    def get_coord_from_raw(raw):
        """Takes an int which represents a board position and returns a stringsuch as e8."""
        return str("abcdefgh"[raw % 8]) + str((raw // 8) + 1)

    def get_board_png_link(self, highlist_last_move: bool = True, highlight_check: bool = True):
        """Returns a link that shows a png version of the board. No url quoting needed."""
        return "https://backscattering.de/web-boardimage/board.png?fen={0}{1}{2}".format(
            quote(self.board.fen()),
            "" if not highlist_last_move else "&lastMove=" + self.board.peek().uci(),
            "" if not (highlight_check and self.board.is_check()) else "&check=" + self.get_coord_from_raw(
                self.board.king(self.board.turn)))

    async def wait_for(self, future):
        """Does what asyncio.wait_for does, but with self.op_timeout as timeout. Do not mess with this, this is some fucking asyncio and concurrent.futures dark magic."""
        if future.done():
            return future.result()
        else:
            return await helpers.actual_client.loop.run_in_executor(None, future.result)

    async def __aenter__(self):
        """Starts a chess engine and prepares it for commands."""
        # We make sure we aren't running in an async with statement
        self._check_not_in_awith()

        # We initialise the engine
        self.engine = uci.popen_engine(self.engine_path, setpgrp=True)

        # We set the difficulty
        await self.wait_for(self.engine.setoption({"Skill Level": self.difficulty, "Threads": self.num_search_threads},
                                                  async_callback=True))

        # We set the board position to the saved one
        await self.wait_for(self.engine.position(self.board, async_callback=True))

        # We're longer in an async with statement
        self._in_with_statement = True

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exits the chess engine."""
        # We make sure we are running in an async with statement
        self._check_in_awith()

        # Quit the chess engine
        await self.wait_for(self.engine.quit(async_callback=True))

        # We're no longer in an async with statement
        self._in_with_statement = False

    async def apply_user_step(self, move: str):
        """Gets a chess move as a string in coordinate notation, that is, coordinate notation after stripping non-alphanum chars,
        applies it to the board. Raises ValueError if the move was invalid. Returns False if the move was semantically invalid, True if it wasn't and was applied to the board."""

        # We have to be in a async with statement
        self._check_in_awith()

        # It has to be the user's turn
        self._check_is_user_turn()

        # We try to parse the move
        cleaned_move = "".join([char for char in move if char in string.ascii_letters or char in string.digits])

        try:
            uci_move = chess.Move.from_uci(cleaned_move)

        except ValueError:
            # The chess move was invalid
            raise

        # We check if the move is valid
        if not uci_move in self.board.generate_legal_moves():
            return False

        # We push the move
        self.board.push(uci_move)

        await self.wait_for(self.engine.position(self.board, async_callback=True))

        # We update the last_time used
        self.last_time_used = time.time()

        return True

    async def do_think_and_move(self):
        """Makes the engine think for the configured time, and then applies that move to the board. Returns True if everything went well, False otherwise.
        Raises RuntimeError if it's not executed within an async with statement or if it's not the computer's turn."""

        # We have to be in a async with statement
        self._check_in_awith()

        # It needs to be the computer's turn
        self._check_is_not_user_turn()

        # We check that the engine is ready for commands and we give it the current board
        await self.wait_for(self.engine.isready(async_callback=True))
        await self.wait_for(self.engine.position(self.board, async_callback=True))

        # We start the thinking
        self.is_thinking = True

        # The think command ;)
        computer_best_move = \
            (await self.wait_for(self.engine.go(movetime=self.cpu_timeout * 1000, async_callback=True)))[0]

        # We're done thinking
        self.is_thinking = False

        # If the move is None, we apply a null move, else we apply the move to our board
        if computer_best_move is None:
            apply_move = chess.Move.null()
        else:
            apply_move = computer_best_move

        # We apply the move
        self.board.push(apply_move)

        return True

    def game_state(self):
        """Returns the current state of the game. The possible return values are:
        "white": White has won.
        "black": Black has won.
        "draw": The game is a draw (stalemate, seventy-five-fold repetition and so on).
        "ongoing": The game is still going.
        """

        # We get board state
        board_state = self.board.result(claim_draw=True)

        if board_state == "1-0":
            return "white"
        elif board_state == "0-1":
            return "black"
        elif board_state == "1/2-1/2":
            return "draw"
        else:
            return "ongoing"

    def _check_in_awith(self):
        """Makes sure that the session is in a with statement."""
        if not self._in_with_statement:
            raise RuntimeError("Chess session was not used in an async with statement when it should have been.")

    def _check_not_in_awith(self):
        """Makes sure that the session in not in a with statement."""
        if self._in_with_statement:
            raise RuntimeError("Chess session was used in an async with statement when it shouldn't have been.")

    def _check_is_user_turn(self):
        """Makes sure that it is the user's turn."""
        if self.board.turn != self.user_side_is_white:
            raise RuntimeError("Turn was not the user's when it should have been, user's side was {0}.".format(
                "white" if self.user_side_is_white else "black"))

    def _check_is_not_user_turn(self):
        """Makes sure that it isn't the user's turn."""
        if self.board.turn == self.user_side_is_white:
            raise RuntimeError("Turn was not the user's when it should have been, user's side was {0}.".format(
                "white" if self.user_side_is_white else "black"))


def check_chess_enabled(func):
    """A decorator that makes sure chess commands are enabled before the enclosed command is called"""

    async def decorated(*args, **kwargs):
        # The third arg will be the config, the second the client, and the first the calling message
        if args[2]["chess_cmd"]["use_chess_commands"]:
            return await func(*args, **kwargs)
        else:
            await args[1].send_message(args[0].channel, "Chess commands are not enabled.")

    return decorated


@command_decorator.command("chess",
                           "Starts a chess game, you can specify a difficulty if you want to. Valid difficulties are 0-20, "
                           "where 20 is grandmaster level and 0 is not very good. "
                           "Only integers are allowed (`19.5` doesn't work, but `19` works), default difficulty is 10. "
                           "Engine is stockfish. Moves are made with the `move` command.")
@check_chess_enabled
async def start_chess_cmd(message: discord.Message, client: discord.Client, config: dict):
    """Creates new chess session if none exists. User plays white."""

    # We check if the user already has a session
    if message.author.id in [session.user.id for session in chess_sessions.values()]:
        await client.send_message(message.channel, "You're already in a chess game.")

        # We're done here
        return

    # We check if the user specified a difficulty
    cleaned_content = helpers.remove_anna_mention(client, message)[
                      len("chess "):] if not message.channel.is_private else message.content[len("chess "):]
    cleaned_content = cleaned_content[:2]

    # We get the value to use as difficulty
    try:
        user_difficulty = int(cleaned_content)

        # We clamp the difficulty
        user_difficulty = min(max(0, user_difficulty), 20)
    except ValueError:
        user_difficulty = 10

    # We create a new chess session
    chess_sessions[message.author.id] = ChessSession(message.author,
                                                     config["chess_cmd"]["search_time_milliseconds"] / 1000,
                                                     config["chess_cmd"]["search_time_milliseconds"] / 1000,
                                                     user_difficulty, config["chess_cmd"]["stockfish_path"],
                                                     config["chess_cmd"]["search_threads"])

    await client.send_message(message.channel,
                              "I created a new chess game for you with difficulty **{0}**!".format(user_difficulty))

    await asyncio.sleep(1)

    # We send a picture of the board
    await send_board_image(client, message.channel, chess_sessions[message.author.id])


@command_decorator.command("stop chess",
                           "Stops the chess game you're playing, obviously doesn't work if you aren't playing a chess game.")
@check_chess_enabled
async def stop_chess_cmd(message: discord.Message, client: discord.Client, config: dict):
    """Stops chess session if one exists."""

    # We check if the user already has a session
    if not message.author.id in [session.user.id for session in chess_sessions.values()]:
        await client.send_message(message.channel, "You're not in a chess game.")

        # We're done here
        return

    # We delete the chess session
    del chess_sessions[message.author.id]

    helpers.log_info("Deleted chess session of user {0}.".format(helpers.log_info(message.author)))

    # We tell the user
    await client.send_message(message.channel, "{0}I stopped your chess session.".format(
        message.author.mention + " " if not message.channel.is_private else ""))


@command_decorator.command("move",
                           "Moves one of your chess pieces as specified. The move format is \"coordinate notation\", "
                           "check wikipedia for a description. https://en.wikipedia.org/wiki/Chess_notation#Notation_systems_for_humans ."
                           "Moves are not strictly coordinate notation, only alphanumeric characters "
                           "will be taken into consideration (alphabet + digits)")
@check_chess_enabled
async def chess_move_cmd(message: discord.Message, client: discord.Client, config: dict):
    """Moves a chess piece for a user."""

    # We check if the user is in a chess session
    if chess_sessions.get(message.author.id, None) is None:
        await client.send_message(message.channel,
                                  "You're not in a chess game, you need to use the `chess` command to start a chess game.")
        return

    # We parse the message content (the raw move string)
    if message.channel.is_private:
        raw_move_str = message.content.strip()[len("move "):]
    else:
        raw_move_str = helpers.remove_anna_mention(client, message).strip()[len("move "):]

    # We try to apply the move
    async with chess_sessions[message.author.id] as chess_session:
        try:
            successful = await chess_session.apply_user_step(raw_move_str)

            # We make sure the move was legal
            if not successful:
                await client.send_message(message.channel,
                                          "That wasn't a legal move. Please try again.")
                return
        except ValueError as e:
            print(e)
            # The move was not in the proper syntax/notation
            await client.send_message(message.channel,
                                      "That move wasn't properly formatted according to coordinate notation. "
                                      "Please check out https://en.wikipedia.org/wiki/Chess_notation#Notation_systems_for_humans for more info about coordinate notation.")
            return

        helpers.log_info(
            "User {0} successfully applied move {1} to their chess session.".format(helpers.log_ob(message.author),
                                                                                    raw_move_str))

        # We send a picture of the board
        await send_board_image(client, message.channel, chess_session)

        # We check if the game ended
        if await handle_game_done(client, message.author, message.channel, chess_session):
            # The game ended
            return

        await asyncio.sleep(1)

        # The move was successful, we tell the user and let the computer think
        await client.send_message(message.channel,
                                  "{0}The computer will now think.".format(
                                      "" if message.channel.is_private else message.author.mention + " "))

        # We need to make sure that the number of concurrent searches are less than the max
        while True:
            if sum([session.is_thinking for session in chess_sessions.values()]) >= config["chess_cmd"][
                "max_concurrent_searches"]:
                # We wait until we check again
                await asyncio.sleep(config["chess_cmd"]["search_time_milliseconds"] / 1000)
            else:
                # We let the computer think
                try:
                    did_chess_move = await chess_session.do_think_and_move()
                    if not did_chess_move:
                        raise RuntimeError("Got False return from computer think command.")

                except RuntimeError as e:
                    await client.send_message(message.channel,
                                              "{0}The computer had an error, please try again later.".format(
                                                  "" if message.channel.is_private else message.author.mention + " "))

                    helpers.log_info("Got RuntimeError in chess computer thinking, error message:\n{0}".format(str(e)))
                    # We're done here
                    return

                break

        # We tell the user about the computer's move
        await send_board_image(client, message.channel, chess_session,
                               content="The computer has now made a move, here is the current board!")

        # We check if the game ended
        if await handle_game_done(client, message.author, message.channel, chess_session):
            # The game ended
            return


async def handle_game_done(client: discord.Client, member: discord.Member, channel: discord.Channel,
                           chess_session: ChessSession):
    """Checks if a chess session is over and sends the appropriate message to the user that was playing.
    Returns True if the game ended, False otherwise"""

    # We check if the game was won
    game_state = chess_session.game_state()
    if game_state is not "ongoing":

        # Ratelimit avoidance
        await asyncio.sleep(1)

        # We check if the game was a draw
        if game_state == "draw":
            await client.send_message(channel, "{0}The game was a draw, and is now over.".format(
                "" if channel.is_private else member.mention + " "))
        else:
            # The game is either a win for white or a win for black
            await client.send_message(channel, "{0}**{1}** has won, and the game is now over.".format(
                "" if channel.is_private else member.mention + " ", game_state.capitalize()))

        # We delete the session from the session dict
        chess_sessions.pop(member.id, None)

        # We're done here
        return True
    return False


async def send_board_image(client: discord.Client, channel: discord.Channel, chess_session: ChessSession,
                           content="Here is the current board!"):
    """Sends an image of the chess board to a target channel. Raises ValueError if the server didn't return HTTP 200.
    Raises asyncio.TimeoutError if the request wasn't completed within a timeout."""

    # We get the image
    try:
        # We use a timeout
        with async_timeout.timeout(5):
            async with aiohttp.ClientSession() as session:
                if len(chess_session.board.move_stack) == 0:
                    image_link = chess_session.get_board_png_link(highlist_last_move=False)
                else:
                    image_link = chess_session.get_board_png_link()
                async with session.get(image_link) as response:
                    # We verify that everything went well
                    if response.status == 200:
                        image_bytes = BytesIO(await response.content.read())
                    else:
                        raise ValueError

    except asyncio.TimeoutError as e:
        # We log
        helpers.log_info("Getting the board image for {0} failed with timeout error".format(chess_session.board.fen()))
        await client.send_message(channel, "Was not able to get an image of this board because of a timeout.")
        return
    except ValueError:
        # We log
        helpers.log_info(
            "Getting the board image for {0} failed with a non-200 status.".format(chess_session.board.fen()))
        await client.send_message(channel, "Was not able to get an image of this board because of an HTTP error.")
        return

    # We send the image
    await client.send_file(channel, image_bytes, filename="chess_board.png", content=content)


async def clean_outdated_chess_sessions():
    """An async background task to remove all timeouted chess sessions periodically."""

    # This is a background task, so we have a while True loop and await sleeps
    while True:
        await asyncio.sleep(120)

        # The time in minutes until a session times out
        timeout_minutes = 10

        # We might aswell cache the time
        time_now = time.time()

        # We loop through the chess sessions and check them
        for key, session in chess_sessions.items():

            # We check if the session has expired
            if time_now - session.last_time_used > timeout_minutes * 60:
                helpers.log_info(
                    "Removing chess game because of timeout. Game info: \n  User: {0} ({1})\n  Seconds since used:{2}".format(
                        session.user.name, session.user.id,
                        round(time_now - session.last_time_used > timeout_minutes * 60, 2)))

                # We remove the item from the dict
                chess_sessions.pop(key, None)
