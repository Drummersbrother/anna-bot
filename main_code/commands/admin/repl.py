"""This file is mostly constructed from RoboDanny, a discord bot by Rapptz, so I include his copyright notice."""
"""
The MIT License (MIT)
   
   Copyright (c) 2015 Rapptz
   
   Permission is hereby granted, free of charge, to any person obtaining a
   copy of this software and associated documentation files (the "Software"),
   to deal in the Software without restriction, including without limitation
   the rights to use, copy, modify, merge, publish, distribute, sublicense,
   and/or sell copies of the Software, and to permit persons to whom the
   Software is furnished to do so, subject to the following conditions:
   
   The above copyright notice and this permission notice shall be included in
   all copies or substantial portions of the Software.
   
   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
   OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
   FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
   DEALINGS IN THE SOFTWARE.
"""

import io
import sys
import textwrap
import traceback
from contextlib import redirect_stdout

import discord

from ... import command_decorator
from ... import helpers

# The lastest result from eval, bot-wide (so different admins can use eachother's results)
last_result = None

def cleanup_code(content):
    """Automatically removes code blocks from the code."""
    # remove ```py\n```
    if content.startswith("```") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:])[:-3]

    # Remove trailing and leading `,  , or \n
    return content.strip('` \n')

def get_syntax_error(e):
    if e.text is None:
        return "```py\n{0.__class__.__name__}: {0}\n```".format(e)
    return "```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```".format(e, '^', type(e).__name__)

@command_decorator.command("eval", "Executes the specified code block (uses exec and not eval, but eval is a nicer name).\
    Be careful with what you execute, and note that you ARE able to use async code as it is run in a coroutine.\
    \nSome useful variables are: \n\
    \t__client__ -> The discord client of the bot. \n\
    \t__channel__ -> The channel in which the eval was issued. \n\
    \t__author__ -> The author of the issuing message (you). \n\
    \t__server__ -> The server in which the eval was issued. \n\
    \t__message__ -> The message which issued the eval. \n\
    \t__last_result__ -> The result of the last eval, if no eval has been done yet, this is None.", admin=True)
async def cmd_admin_eval(message: discord.Message, client: discord.Client, config: dict):
    global last_result

    # The variables we give access to
    env = {
        "client": client,
        "channel": message.channel,
        "author": message.author,
        "server": message.server,
        "message": message,
        "last_result": last_result
    }

    # We insert the globals into the environment
    env.update(globals())

    no_mention_content = helpers.remove_anna_mention(client,
                                                     message) if not message.channel.is_private else message.content

    # We make sure that there's code in the message
    if len(no_mention_content) < len("admin eval "):
        # We didn't get any code
        await client.send_message(message.channel, message.author.mention + ", you did not give any code to run.")
        return
    else:
        # We have atleast some maybe-valid input
        uncleaned_code = no_mention_content[11:]
        await client.send_message(message.channel, message.author.mention + ", ok, running now...")
        helpers.log_info(
            "Running code from eval command issued by {0} ({1}).".format(message.author.name, message.author.id))

    # We cleanup the message content so we only have code.
    # Most of the rest of this function is magic by Rapptz
    body = cleanup_code(uncleaned_code)

    to_compile = "async def func():\n{0}".format(textwrap.indent(body, '  '))

    try:
        exec(to_compile, env)
    except SyntaxError as e:
        return await client.send_message(message.channel,
                                         message.author.mention + ", got SyntaxError: \n" + get_syntax_error(e))

    func = env['func']
    try:
        # We don't want to spam the logs, but we don't want any output from the stdout
        with redirect_stdout(io.StringIO()):
            ret = await func()
    except Exception as e:
        traceback_list = traceback.format_exception(*sys.exc_info())
        # We don't want expose the filepath of the running bot in all exception reporting
        del traceback_list[1]
        await client.send_message(message.channel, '```py\n{}\n```'.format("".join(traceback_list)))
    else:
        try:
            await client.add_reaction(message, chr(128076))
        except:
            pass

        if ret is None:
            await client.send_message(message.channel,
                                      message.author.mention + ", code didn't return anything or returned `None`.")
        else:
            last_result = ret
            await helpers.send_long(client, "{0}".format(*helpers.escape_code_formatting(str(ret))), message.channel,
                                    prepend="```\n", append="\n```")
    finally:
        await client.send_message(message.channel, message.author.mention + ", I'm done running it now!")
