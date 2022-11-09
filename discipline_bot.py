import asyncio
import collections
import datetime
import os

import discord
import pandas as pd
import pymongo
import pytz
from discord import app_commands, Embed, Member
from discord.ext import tasks
from discord.utils import get
from dotenv import load_dotenv

from leet_simulator import get_submission_details
from leetmodel import leetmodel
from util import printException, duration_till_next_day

DISCIPLINE_MODE = os.getenv('DISCIPLINE_MODE', "dev")
load_dotenv(f"{DISCIPLINE_MODE}.env")
SLEEP_INTERVAL_SECONDS = int(os.getenv("SLEEP_INTERVAL_SECONDS"))
max_recent = 20
GUILD_ID = int(os.getenv("GUILD_ID"))
submission_feed_channel_id = int(os.getenv("SUBMISSION_FEED_CHANNEL_ID"))
question_of_the_day_channel_id = int(os.getenv("QUESTION_OF_THE_DAY_CHANNEL_ID"))
MY_GUILD = discord.Object(id=GUILD_ID)
leetcode_model = leetmodel(os.getenv("LEETCODE_ACCOUNT_NAME"), os.getenv("LEETCODE_ACCOUNT_PASSWORD"))
leetcode_questions = pd.read_csv('./public_data/leetcode_questions.csv', header=0)
leetcode_questions["link"] = "https://leetcode.com/problems/" + leetcode_questions["titleSlug"] + "/"
leetcode_questions = leetcode_questions.set_index("titleSlug")
title_slug_to_data = leetcode_questions.to_dict('index')

client = pymongo.MongoClient(os.getenv("ATLAS_URI"))
db = client.disciplined_leetcode_db
submission_collection = db.submission_collecion
submission_feed_collection = db.submission_feed_collection
user_collection = db.user_collection


async def send_question_of_the_day():
    day_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + datetime.timedelta(hours=24)
    timestamp = int(day_end.replace(tzinfo=datetime.timezone.utc).timestamp())

    question_of_the_day = leetcode_model.get_question_of_the_day()
    guild = client.get_guild(GUILD_ID)
    question_of_the_day_channel = guild.get_channel(question_of_the_day_channel_id)

    embed = discord.Embed(title=f"Question of the Day - {question_of_the_day['date']}")
    embed.description = f"@everyone Friendly reminder 🎗\n" \
                        f"You must complete one of them by the end of {question_of_the_day['date']} UTC⏱️.\n" \
                        f"Likely <t:{timestamp}:f> your time.\n\n" \
                        f"The **senior** track question is {question_of_the_day['question']['frontendQuestionId']} " \
                        f"{question_of_the_day['question']['title']}: " \
                        f"https://leetcode.com{question_of_the_day['link']}\n\n" \
                        f"The **junior** track question is here: " \
                        f"https://docs.google.com/spreadsheets/d/1AROdK4Vvq6NYxK2oNFpCQLZfYPhphunJfQ7qCeE2CSA" \
                        f"/edit?usp=sharing\n"

    await question_of_the_day_channel.send(embed=embed)


async def verify_permissions(interaction):
    if interaction.channel_id != int(os.getenv("MOD_CHANNEL")):
        await interaction.response.send_message("Please invoke the command in the right channel.")
        return False

    return True


class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.copy_global_to(guild=MY_GUILD)  # This copies the global commands over to your guild.
        await self.tree.sync(guild=MY_GUILD)
        self.kicker_task.start()
        self.question_of_the_day_task.start()
        self.get_feed.start()

    @tasks.loop(hours=24)
    async def kicker_task(self):
        sleep_duration = (duration_till_next_day() + datetime.timedelta(minutes=1)).seconds
        print(f"sleep - kicker_task: {sleep_duration}")
        await asyncio.sleep(sleep_duration)
        await handle_kicking(3)

    @tasks.loop(hours=24)
    async def question_of_the_day_task(self):
        sleep_duration = (duration_till_next_day() + datetime.timedelta(minutes=2)).seconds
        print(f"sleep - question_of_the_day_task: {sleep_duration}")
        await asyncio.sleep(sleep_duration)
        await send_question_of_the_day()

    @tasks.loop(seconds=int(os.getenv("REFRESH_INTERVAL_SECONDS")))
    async def get_feed(self):
        guild = client.get_guild(GUILD_ID)
        active_role = get(guild.roles, id=int(os.getenv("ACTIVE_ROLE_ID")))
        submission_feed_channel = guild.get_channel(submission_feed_channel_id)

        for member in active_role.members:
            discord_user_id = member.id
            document = user_collection.find_one({'discord_user_id': discord_user_id},
                                                {"leetcode_username": 1,
                                                 "ac_count_total_submissions": 1})

            if not document:
                print(f"WARNING: user document not found for member {member} with id {discord_user_id}")
                continue

            try:
                leetcode_username = document["leetcode_username"]
                discord_user = await client.fetch_user(discord_user_id)
                user_data = leetcode_model.get_user_data(leetcode_username)
                await asyncio.sleep(SLEEP_INTERVAL_SECONDS)
                current_total = user_data['submitStats']['acSubmissionNum'][0]['submissions']
                prev_total = document["ac_count_total_submissions"]
                num_new_submissions = current_total - prev_total

                if not num_new_submissions:
                    continue

                update_user(discord_user_id, user_data, leetcode_username)
                recent_submissions = leetcode_model.get_recent_submissions(leetcode_username)
                await asyncio.sleep(SLEEP_INTERVAL_SECONDS)

                for i in range(min(max_recent, num_new_submissions)):
                    submission = recent_submissions[i]

                    if submission["statusDisplay"] != "Accepted":
                        continue

                    timestamp = datetime.datetime.fromtimestamp(int(submission["timestamp"]))
                    submission["time"] = timestamp.strftime(os.getenv("DATETIME_FORMAT"))
                    submission["leetcode_username"] = leetcode_username
                    submission["discord_user_id"] = discord_user_id
                    submission.update(title_slug_to_data[submission["titleSlug"]])
                    submission_feed_collection.insert_one(submission)
                    submission_detail = collections.defaultdict(lambda: '')

                    try:
                        submission_detail = get_submission_details(submission['id'])
                        await asyncio.sleep(SLEEP_INTERVAL_SECONDS)
                    except Exception as e:
                        printException(e)

                    desc = f"Congrats! {discord_user.display_name} solved " \
                           f"[{submission['title']}](https://leetcode.com/submissions/detail/{submission['id']}/) "

                    if submission_detail['runtime']:
                        desc += f"in {submission_detail['lang']}.\n" \
                                f"It beat by\n" \
                                f"**runtime {submission_detail['runtime']}**, and by\n" \
                                f"**memory {submission_detail['memory']}**.\n" \
                                f"```{submission_detail['lang'].removesuffix('3')}\n" \
                                f"{submission_detail['code']}" \
                                f"```"

                    embed: Embed = discord.Embed(title="Accepted", description=desc, timestamp=timestamp,
                                                 color=5025616)

                    icon_url = discord_user.avatar.url if discord_user.avatar else None
                    embed.set_footer(text=f"{discord_user.display_name}", icon_url=icon_url)

                    await submission_feed_channel.send(embed=embed)
            except Exception as e:
                print(document)
                printException(e)

    @question_of_the_day_task.before_loop
    @get_feed.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in

    @kicker_task.before_loop
    @get_feed.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in


client = MyClient()


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("------")


@client.tree.command()
@app_commands.describe(
    question_number="Question number (the one that shows up in front of the question name)",
    submission_link="Your submission link",
)
async def submit(interaction: discord.Interaction, question_number: int, submission_link: str):
    await interaction.response.send_message(f'This function is deprecated. Please use /add_user to link your account '
                                            f'to the bot.')


@client.tree.command()
async def announce_question_of_the_day(interaction: discord.Interaction):
    await send_question_of_the_day()
    await interaction.response.send_message("Announced")


def insert_submission(discord_user_id, question_number, submission_link):
    submission_collection.insert_one({
        "time": datetime.datetime.utcnow(),
        "discord_user_id": discord_user_id,
        "question_number": question_number,
        "submission_link": submission_link
    })


@client.tree.command()
async def add_user(interaction: discord.Interaction, leetcode_username: str):
    await handle_add_user(interaction, leetcode_username, interaction.user)


@client.tree.command()
async def admin_add_user(interaction: discord.Interaction, leetcode_username: str, discord_user: Member):
    if not await verify_permissions(interaction):
        return

    await handle_add_user(interaction, leetcode_username, discord_user)


async def handle_add_user(interaction: discord.Interaction, leetcode_username: str, discord_user: Member):
    await interaction.response.send_message("Working")

    discord_user_id = discord_user.id
    user_data = leetcode_model.get_user_data(leetcode_username)
    guild = client.get_guild(GUILD_ID)
    active_role = get(guild.roles, id=int(os.getenv("ACTIVE_ROLE_ID")))

    if not user_data:
        await interaction.followup.send(f'Could not add {leetcode_username}: Check the username')
        return

    # If necessary, remove user
    user_document = user_collection.find_one({'discord_user_id': discord_user_id}, {"leetcode_username": 1})

    if user_document:
        old_leetcode_username = user_document["leetcode_username"]

        if active_role not in discord_user.roles:
            await interaction.followup.send(f'Your discord account has joined in the past!\n'
                                            f'If you do not have access to channels, '
                                            f'unlock it via <#{os.getenv("SUPPORT_CHANNEL_ID")}> ')
            return

        user_collection.delete_one({'leetcode_username': old_leetcode_username})
        await interaction.followup.send(f'Removed {old_leetcode_username}\n'
                                        f'Resubmit LeetCode solutions if necessary.')

    # Add user
    update_user(discord_user_id, user_data, leetcode_username)

    if not user_document:
        await interaction.user.add_roles(active_role, reason="Grant newly associated user access to channels.")

    await interaction.followup.send(f'Added {leetcode_username}')


def update_user(discord_user_id, user_data, leetcode_username):
    now = datetime.datetime.utcnow()
    now_str = now.strftime(os.getenv("DATETIME_FORMAT"))
    total = user_data['submitStats']['acSubmissionNum'][0]['count']
    easy = user_data['submitStats']['acSubmissionNum'][1]['count']
    medium = user_data['submitStats']['acSubmissionNum'][2]['count']
    hard = user_data['submitStats']['acSubmissionNum'][3]['count']
    total_subs = user_data['submitStats']['acSubmissionNum'][0]['submissions']
    myquery = {"leetcode_username": leetcode_username}
    user_collection.replace_one(myquery,
                                {
                                    "discord_user_id": discord_user_id,
                                    "leetcode_username": leetcode_username,
                                    "ac_count_total": total,
                                    "ac_count_easy": easy,
                                    "ac_count_medium": medium, "ac_count_hard": hard,
                                    "ac_count_total_submissions": total_subs,
                                    "updated_time": now_str
                                }
                                , upsert=True)


@client.tree.command()
async def kick_inactive(interaction: discord.Interaction, days_before: int):
    # Only the mod can invoke this command
    if not await verify_permissions(interaction):
        return

    await interaction.response.send_message("Working")
    warned = await handle_kicking(days_before)
    await interaction.followup.send(f"Warned {len(warned)} members.")


async def handle_kicking(days_before: int = 7):
    cutoff = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC) - datetime.timedelta(days=days_before)
    # We go from submission_feed_collection to active users instead of the other way around to
    # facilitate user redemption.
    iterator = submission_feed_collection.find({"timestamp": {"$gte": str(cutoff.timestamp())}})
    leetcode_users_with_submissions = {document["leetcode_username"] for document in iterator}
    discord_users_with_submissions = [user_collection.find_one(filter={"leetcode_username": leetcode_username},
                                                               projection={"discord_user_id": 1})['discord_user_id']
                                      for leetcode_username in leetcode_users_with_submissions]

    warned = []
    guild = client.get_guild(GUILD_ID)
    prospective_chat_channel = guild.get_channel(int(os.getenv("PROSPECTIVE_CHAT_CHANNEL_ID")))
    active_role = get(guild.roles, id=int(os.getenv("ACTIVE_ROLE_ID")))

    for member in active_role.members:
        join_date_time = member.joined_at

        if not (join_date_time and join_date_time < cutoff and not member.bot
                and member.id not in discord_users_with_submissions):
            continue

        goal = "regain access to member channels"
        await prospective_chat_channel.send(
            f"{member.mention} You have not made any LeetCode submission in the last few days.\n"
            f"To {goal}, please make a donation at "
            f"<#{os.getenv('SUPPORT_CHANNEL_ID')}>")

        warned.append(f"{member.name} ({member.id})")
        await member.remove_roles(active_role, reason="Lack of submissions")

    print(f"Warned {len(warned)} members.\n{', '.join(warned)}")
    return warned


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
