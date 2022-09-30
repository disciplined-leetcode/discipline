import os

import discord
from discord import app_commands
import datetime
from dotenv import load_dotenv
import pandas as pd

load_dotenv("prod.env")
# TODO extract configs to "prod_config.hjson"
GUILD_ID = 1023711157011353672
MY_GUILD = discord.Object(id=GUILD_ID)


class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


intents = discord.Intents.default()
client = MyClient(intents=intents)


@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')


@client.tree.command()
@app_commands.describe(
    question_number='Question number (the one that shows up in front of the question name)',
    submission_link='Your submission link',
)
async def submit(interaction: discord.Interaction, question_number: int, submission_link: str):
    # TODO check with LeetCode API or scrape it
    if "submissions/" not in submission_link:
        await interaction.response.send_message(f'Submission link must look like '
                                                f'"https://leetcode.com/submissions/detail/808758751/" or '
                                                f'"https://leetcode.com/problems/valid-anagram/submissions/811812564/"'
                                                f'\n'
                                                f'Your input arguments are "{question_number}", "{submission_link}"')
        return

    # TODO use a proper database
    submission_db = open("user_files/submissions.csv", "a")  # append mode
    submission_db.write(f"{datetime.datetime.utcnow()},{interaction.user.id},{question_number},{submission_link}\n")
    submission_db.close()

    await interaction.response.send_message(f'{interaction.user.mention} good job on completing {question_number} '
                                            f'at {submission_link} !')


@client.tree.command()
async def kick_inactive(interaction: discord.Interaction):
    if interaction.channel_id != 1024837572171681882:
        await interaction.response.send_message("Please invoke the command in the right channel.")
        return

    # TODO Filter by time and remove the Active role
    df = pd.read_csv('./user_files/submissions.csv')

    guild = client.get_guild(GUILD_ID)
    members = {member for member in guild.members}
    active_user_ids = set(df["user_id"].unique())
    kicked = []

    for member in members:
        if member.id not in active_user_ids and not member.bot:
            kicked.append(f"{member.name} ({member.id})")
            await guild.kick(member, reason="You have not made any LeetCode submission in the server "
                                            "in the last few days.\n"
                                            "To rejoin, contact Zack#2664")

    await interaction.response.send_message(f"Removed {len(kicked)} members.\n{', '.join(kicked)}")


@client.tree.context_menu(name='Report to Moderators')
async def report_message(interaction: discord.Interaction, message: discord.Message):
    # We're sending this response message with ephemeral=True, so only the command executor can see it
    await interaction.response.send_message(
        f'Thanks for reporting this message by {message.author.mention} to our moderators.', ephemeral=True
    )

    # Handle report by sending it into a log channel
    log_channel = interaction.guild.get_channel(int(os.getenv("REPORT_CHANNEL_ID")))

    embed = discord.Embed(title='Reported Message')
    if message.content:
        embed.description = message.content

    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.timestamp = message.created_at

    url_view = discord.ui.View()
    url_view.add_item(discord.ui.Button(label='Go to Message', style=discord.ButtonStyle.url, url=message.jump_url))

    await log_channel.send(embed=embed, view=url_view)


client.run(os.getenv("TOKEN"))
