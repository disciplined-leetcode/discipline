import datetime
import os

import discord
from discord.ext import tasks
import pandas as pd
import pymongo
import pytz
from discord import app_commands, Embed
from dotenv import load_dotenv

from leetmodel import leetmodel

load_dotenv("prod.env")
# TODO extract configs to "prod_config.hjson"
GUILD_ID = 1023711157011353672
MY_GUILD = discord.Object(id=GUILD_ID)
model = leetmodel(os.getenv("LEETCODE_ACCOUNT_NAME"), os.getenv("LEETCODE_ACCOUNT_PASSWORD"))

client = pymongo.MongoClient(os.getenv("ATLAS_URI"))
db = client.disciplined_leetcode_db
submission_collection = db.disciplined_leetcode_collecion
user_collection = db.user_collection


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
async def add_user(interaction: discord.Interaction, leetcode_username: str):
    user_data = model.get_user_data(leetcode_username)

    if not user_data:
        await interaction.response.send_message(f'Could not add {leetcode_username}: Check the username!')
        return

    now = datetime.datetime.utcnow()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")
    total = user_data['submitStats']['acSubmissionNum'][0]['count']
    easy = user_data['submitStats']['acSubmissionNum'][1]['count']
    medium = user_data['submitStats']['acSubmissionNum'][2]['count']
    hard = user_data['submitStats']['acSubmissionNum'][3]['count']
    total_subs = user_data['submitStats']['acSubmissionNum'][0]['submissions']
    myquery = {"leetcode_username": leetcode_username}
    user_collection.replace_one(myquery, {"leetcode_username": leetcode_username, "ac_count_total": total,
                                          "ac_count_easy": easy, "ac_count_medium": medium, "ac_count_hard": hard,
                                          "ac_count_total_submissions": total_subs,
                                          "updated_time": now_str
                                          }, upsert=True)

    await interaction.response.send_message(f'Added {leetcode_username}!')


async def setup_hook(self) -> None:
    # start the task to run in the background
    self.get_feed.start()


# Run checks every minute to find new submissions and upload them to the connected server
@tasks.loop(minutes=1)
async def get_feed(self):
    print("loop")
    max_recent = 20
    submission_feed_channel_id = int(os.getenv("SUBMISSION_FEED_CHANNEL_ID"))
    guild = client.get_guild(GUILD_ID)
    submission_feed_channel = guild.get_channel(submission_feed_channel_id)

    for document in user_collection.find({}, {"leetcode_username": 1, "ac_count_total_submissions": 1}):
        new_submissions = []
        prev_total = document["ac_count_total_submissions"]
        leetcode_user = document["leetcode_username"]
        user_data = model.get_user_data(leetcode_user)
        current_total = user_data['submitStats']['acSubmissionNum'][0]['submissions']

        if current_total > prev_total:
            recent_submissions = model.getRecentSubs(leetcode_user)
            num_new_submissions = current_total - prev_total

            for i in range(min(max_recent, num_new_submissions)):
                if recent_submissions[i]['statusDisplay'] == "Accepted":
                    new_submissions.append(
                        [leetcode_user, recent_submissions[i]['title'], recent_submissions[i]['lang'],
                         recent_submissions[i]['titleSlug'], recent_submissions[i]['statusDisplay']])

        for submission in new_submissions:
            desc = "User " + ''.join(submission[0]) + " has submitted an answer for [" + ''.join(submission[1]) \
                   + "](https://leetcode.com/problems/" + ''.join(submission[3]) \
                   + ") in " + ''.join(submission[2].capitalize()) + "."

            now = datetime.datetime.utcnow()
            current_time = now.strftime("%d-%m-%y %H:%M")
            embed: Embed = discord.Embed(title="Accepted", description=desc, color=5025616)
            embed.set_footer(text=current_time)

            await submission_feed_channel.send(embed=embed)

        # await interaction.response.send_message(f"Succeeded in sending {len(new_submissions)} new submission "
        #                                         f"to <#{submission_feed_channel_id}>")


@get_feed.before_loop
async def before_my_task(self):
    await self.wait_until_ready()  # wait until the bot logs in


@client.tree.command()
async def kick_inactive(interaction: discord.Interaction):
    if interaction.channel_id != 1024837572171681882:
        await interaction.response.send_message("Please invoke the command in the right channel.")
        return

    # TODO Filter by time and remove the Active role
    df = pd.read_csv('./user_files/submissions.csv')
    cutoff = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC) - datetime.timedelta(days=2)

    guild = client.get_guild(GUILD_ID)
    users_with_submissions = set(df["user_id"].unique())
    kicked = []
    warned = []

    for member in guild.members:
        join_date_time = member.joined_at

        if join_date_time and join_date_time < cutoff and not member.bot:
            goal = "regain access to member channels" if member.id in users_with_submissions else "rejoin the server"
            # await member.dm_channel.send(f"You have not made any LeetCode submission in the server {guild.name}"
            #                              "in the last few days.\n"
            #                              f"To {goal}, contact Zack#2664")

            if member.id in users_with_submissions:
                warned.append(f"{member.name} ({member.id})")
            else:
                kicked.append(f"{member.name} ({member.id})")
                # await guild.kick(member)

    await interaction.response.send_message(f"Kicked {len(kicked)} members.\n{', '.join(kicked)} \n"
                                            f"Warned {len(warned)} members.\n{', '.join(warned)}")


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
