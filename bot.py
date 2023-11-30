import requests
import json
import discord
import time
import asyncio
import sys
import os
import logging

intents = discord.Intents.default()

client = discord.Client(intents=intents)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)


def get_data():  # grab data from api
    try:
        data = requests.get('https://collablab.wpi.edu/lab/status',
                            headers={"User-Agent": "DiscordCollabLabBot"}, timeout=3).text
        logging.debug(f"Got data from API:\n{data}")
        return json.loads(data)
    except Exception as e:
        logging.error("Error Getting Data:", e)
    return {"open": "ERROR"}


def build_status(data):  # build status message
    STATUS_MESSAGE = "Lab Status:"
    CLOSED_MESSAGE = f"{STATUS_MESSAGE} 🔴 CLOSED"

    match (data['open']):
        case "OPEN":
            return f"{STATUS_MESSAGE} 🟢 ({str(len(data['members']))}) OPEN"
        case "CLOSED":
            return CLOSED_MESSAGE
        case "LIMITED":
            return f"{STATUS_MESSAGE} 🟡 ({(str(len(data['members'])))}) LIMITED"
        case "ERROR":
            return CLOSED_MESSAGE


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    CHANNEL_ID = 1019030265957458030
    channel = client.get_channel(CHANNEL_ID)
    new_state = channel.name

    logging.debug(f"Current Channel Name: {new_state}")

    while True:
        while channel.name == new_state:  # check for updates every 10 seconds
            await asyncio.sleep(10)
            new_state = build_status(get_data())

        logging.debug("Change in state, updating status in 15 seconds...")

        # wait to see if a bunch of people are about to log in at once
        await asyncio.sleep(15)
        current_state = build_status(get_data())

        logging.info("Updating channel")

        await channel.edit(name=current_state)  # update channel name
        logging.debug(f"Changed channel name to: {current_state}")
        # wait 6min to avoid rate limits (which are twice per 10 min)
        logging.debug("Sleeping for 6min after channel update")
        await asyncio.sleep(360)

if os.path.exists("./token"):
    token = open('./token', 'r').read()
    logging.info("Using token from ./token file")
else:
    token = os.getenv('DISCORD_TOKEN')
    logging.info("Using token from enviroment variable 'DISCORD_TOKEN'")

client.run(token)
