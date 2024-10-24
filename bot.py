import discord
import asyncio
import requests
import logging
import os

# Constants
CHANNEL_ID = 1019030265957458030  # Replace with your actual channel ID
# Replace with your actual ping channel ID
PING_CHANNEL_ID = 861745331729334285
ROLE_ID = 1195517531587362826  # Replace with your actual role ID

STATUS_CHECK_INTERVAL = 10  # seconds
STATUS_CHANGE_CONFIRMATION_DELAY = 15  # seconds
RATE_LIMIT_WINDOW = 600  # 10 minutes in seconds
MAX_CHANNEL_NAME_CHANGES = 2
NOTIFICATION_DELAY = 300  # 5 minutes

DO_NOTIFICATIONS = False  # Set to False to disable notifications
DO_CHANNEL_UPDATES = True  # Set to False to disable channel name updates

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

# Read the Discord bot token from file or environment variable
token = None
if os.path.exists('./token'):
    with open('./token', 'r') as f:
        token = f.read().strip()
else:
    token = os.getenv('DISCORD_TOKEN')

if not token:
    logging.error('Discord token not found.')
    exit(1)


class LabStatusBot(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.channel_name_changes_times = []
        self.last_lab_status = None
        self.last_member_count = None
        self.lab_open_time = None
        self.notification_sent = False
        self.status_channel = None
        self.ping_channel = None
        self.monitor_task = self.loop.create_task(self.monitor_lab_status())

    async def on_ready(self):
        logging.info(f'Logged in as {self.user}')
        self.status_channel = self.get_channel(CHANNEL_ID)
        if not self.status_channel:
            logging.error(f'Could not find channel with ID {CHANNEL_ID}')
            await self.close()
            return
        self.ping_channel = self.get_channel(PING_CHANNEL_ID)
        if not self.ping_channel:
            logging.error(f'Could not find ping channel with ID {
                          PING_CHANNEL_ID}')
            await self.close()
            return
        logging.info('Bot is ready and monitoring lab status.')

    async def monitor_lab_status(self):
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                # Fetch lab status
                headers = {'User-Agent': 'DiscordCollabLabBot'}
                response = requests.get(
                    'https://collablab.wpi.edu/lab/status', headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    lab_open = data.get('open', False)
                    members = data.get('members', [])
                    member_count = len(members)

                    now = self.loop.time()

                    # If lab status has changed
                    if lab_open != self.last_lab_status:
                        # Wait 15 seconds to confirm the change
                        logging.info(
                            'Detected a status change, confirming after delay...')
                        await asyncio.sleep(STATUS_CHANGE_CONFIRMATION_DELAY)

                        # Fetch the status again
                        response_confirm = requests.get(
                            'https://collablab.wpi.edu/lab/status', headers=headers, timeout=3)
                        if response_confirm.status_code == 200:
                            data_confirm = response_confirm.json()
                            confirmed_lab_open = data_confirm.get(
                                'open', False)
                            confirmed_members = data_confirm.get('members', [])
                            confirmed_member_count = len(confirmed_members)

                            if confirmed_lab_open == lab_open:
                                # Proceed to update the channel name
                                # Remove timestamps older than RATE_LIMIT_WINDOW
                                self.channel_name_changes_times = [
                                    t for t in self.channel_name_changes_times if now - t < RATE_LIMIT_WINDOW]
                                if len(self.channel_name_changes_times) < MAX_CHANNEL_NAME_CHANGES:
                                    if DO_CHANNEL_UPDATES:
                                        # Update the channel name
                                        if lab_open:
                                            new_channel_name = f'Lab Status: 🟢 ({
                                                confirmed_member_count}) OPEN'
                                            self.lab_open_time = now
                                            self.notification_sent = False
                                            self.last_member_count = confirmed_member_count
                                        else:
                                            new_channel_name = 'Lab Status: 🔴 CLOSED'
                                            self.lab_open_time = None
                                            self.notification_sent = False
                                            self.last_member_count = None

                                        await self.status_channel.edit(name=new_channel_name)
                                        logging.info(f'Channel name changed to: {
                                                     new_channel_name}')
                                        self.channel_name_changes_times.append(
                                            now)
                                    else:
                                        logging.info(
                                            'Channel updates are disabled.')
                                else:
                                    logging.warning(
                                        'Reached max channel name changes per rate limit window')
                            else:
                                logging.info(
                                    'Status change not confirmed, ignoring...')
                        else:
                            logging.error(f'Error confirming lab status: HTTP {
                                          response_confirm.status_code}')
                    else:
                        # Lab status hasn't changed
                        if lab_open:
                            # Check if member count has changed
                            if member_count != self.last_member_count:
                                # Remove timestamps older than RATE_LIMIT_WINDOW
                                self.channel_name_changes_times = [
                                    t for t in self.channel_name_changes_times if now - t < RATE_LIMIT_WINDOW]
                                if len(self.channel_name_changes_times) < MAX_CHANNEL_NAME_CHANGES:
                                    if DO_CHANNEL_UPDATES:
                                        new_channel_name = f'Lab Status: 🟢 ({
                                            member_count}) OPEN'
                                        await self.status_channel.edit(name=new_channel_name)
                                        logging.info(f'Channel name updated to: {
                                                     new_channel_name}')
                                        self.channel_name_changes_times.append(
                                            now)
                                        self.last_member_count = member_count
                                    else:
                                        logging.info(
                                            'Channel updates are disabled.')
                                else:
                                    logging.warning(
                                        'Reached max channel name changes per rate limit window')
                        else:
                            self.last_member_count = None

                    # If lab is open and notification not sent, check if it's time to send notification
                    if lab_open:
                        if self.lab_open_time and not self.notification_sent:
                            if now - self.lab_open_time >= NOTIFICATION_DELAY:
                                if DO_NOTIFICATIONS:
                                    # Send notification
                                    message_content = f'Lab is now open <@&{
                                        ROLE_ID}>'
                                    await self.ping_channel.send(content=message_content)
                                    logging.info('Notification sent')
                                    self.notification_sent = True
                                else:
                                    logging.info('Notifications are disabled.')
                    else:
                        # Lab is closed
                        self.lab_open_time = None
                        self.notification_sent = False

                    # Update last_lab_status
                    self.last_lab_status = lab_open
                else:
                    logging.error(f'Error fetching lab status: HTTP {
                                  response.status_code}')
            except Exception as e:
                logging.error(f'Exception during lab status check: {e}')

            # Wait for next check
            await asyncio.sleep(STATUS_CHECK_INTERVAL)


intents = discord.Intents.default()
bot = LabStatusBot(intents=intents)

bot.run(token)
