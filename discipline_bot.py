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

max_recent = 20
load_dotenv("prod.env")
GUILD_ID = int(os.getenv("GUILD_ID"))
submission_feed_channel_id = int(os.getenv("SUBMISSION_FEED_CHANNEL_ID"))
MY_GUILD = discord.Object(id=GUILD_ID)
model = leetmodel(os.getenv("LEETCODE_ACCOUNT_NAME"), os.getenv("LEETCODE_ACCOUNT_PASSWORD"))

client = pymongo.MongoClient(os.getenv("ATLAS_URI"))
db = client.disciplined_leetcode_db
submission_collection = db.submission_collecion
user_collection = db.user_collection


class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.copy_global_to(guild=MY_GUILD)  # This copies the global commands over to your guild.
        await self.tree.sync(guild=MY_GUILD)
        self.get_feed.start()

    @tasks.loop(minutes=1)
    async def get_feed(self):
        guild = client.get_guild(GUILD_ID)
        submission_feed_channel = guild.get_channel(submission_feed_channel_id)

        for document in user_collection.find({}, {"discord_id": 1, "leetcode_username": 1, "ac_count_total_submissions": 1}):
            leetcode_username = document["leetcode_username"]
            user_data = model.get_user_data(leetcode_username)
            current_total = user_data['submitStats']['acSubmissionNum'][0]['submissions']
            prev_total = document["ac_count_total_submissions"]
            num_new_submissions = current_total - prev_total
            new_submissions = []

            if num_new_submissions:
                update_user(document["discord_id"], user_data, leetcode_username)
                recent_submissions = model.getRecentSubs(leetcode_username)

                for i in range(min(max_recent, num_new_submissions)):
                    if recent_submissions[i]['statusDisplay'] == "Accepted":
                        new_submissions.append(
                            [leetcode_username, recent_submissions[i]['title'], recent_submissions[i]['lang'],
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

    @get_feed.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in


client = MyClient()


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

    submission_collection.insert_one({
        "time":  datetime.datetime.utcnow(),
        "discord_id": interaction.user.id,
        "question_number": question_number,
        "submission_link": submission_link
    })

    await interaction.response.send_message(f'{interaction.user.mention} good job on completing {question_number} '
                                            f'at {submission_link} !')


@client.tree.command()
async def add_user(interaction: discord.Interaction, leetcode_username: str):
    user_data = model.get_user_data(leetcode_username)

    if not user_data:
        await interaction.response.send_message(f'Could not add {leetcode_username}: Check the username!')
        return

    update_user(interaction.user.id, user_data, leetcode_username)

    await interaction.response.send_message(f'Added {leetcode_username}!')


def update_user(discord_id, user_data, leetcode_username):
    now = datetime.datetime.utcnow()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")  # TODO extract this format out
    total = user_data['submitStats']['acSubmissionNum'][0]['count']
    easy = user_data['submitStats']['acSubmissionNum'][1]['count']
    medium = user_data['submitStats']['acSubmissionNum'][2]['count']
    hard = user_data['submitStats']['acSubmissionNum'][3]['count']
    total_subs = user_data['submitStats']['acSubmissionNum'][0]['submissions']
    myquery = {"leetcode_username": leetcode_username}
    user_collection.replace_one(myquery,
                                {
                                    "discord_id": discord_id,
                                    "leetcode_username": leetcode_username,
                                    "ac_count_total": total,
                                    "ac_count_easy": easy,
                                    "ac_count_medium": medium, "ac_count_hard": hard,
                                    "ac_count_total_submissions": total_subs,
                                    "updated_time": now_str
                                }
                                , upsert=True)


@client.tree.command()
async def kick_inactive(interaction: discord.Interaction):
    if interaction.channel_id != os.getenv("MOD_CHANNEL"):
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
