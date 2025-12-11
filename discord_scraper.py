import aiohttp
import asyncio
import logging
import os
from datetime import datetime
from config import DISCORD_TOKEN, DISCORD_CHANNEL_ID

logger = logging.getLogger(__name__)

class Message:
    def __init__(self, message_data):
        self.id = int(message_data["id"])
        main_content = message_data.get("content", "")
        
        embed_descriptions = []
        embeds = message_data.get("embeds", [])
        for embed in embeds:
            if isinstance(embed, dict) and "description" in embed:
                embed_descriptions.append(embed["description"])
        
        if embed_descriptions:
            self.content = main_content + " " + " ".join(embed_descriptions)
        else:
            self.content = main_content
        
        timestamp_str = message_data.get("timestamp", "")
        if timestamp_str:
            try:
                self.timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse timestamp for message {self.id}: {e}")
                self.timestamp = None
        else:
            self.timestamp = None

class DiscordScraper:
    def __init__(self, processed_ids_file="processed_messages.txt"):
        self.token = DISCORD_TOKEN
        self.channel_id = DISCORD_CHANNEL_ID
        self.session = None
        self.processed_ids_file = processed_ids_file
        self.processed_message_ids = set()
        self.base_url = "https://discord.com/api/v9"
        self.load_processed_message_ids()

    def load_processed_message_ids(self):
        if not os.path.exists(self.processed_ids_file):
            logger.info(f"Processed messages file {self.processed_ids_file} does not exist. Starting fresh.")
            return

        try:
            with open(self.processed_ids_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            msg_id = int(line)
                            self.processed_message_ids.add(msg_id)
                        except ValueError:
                            logger.warning(f"Invalid message ID in file: {line}")
                            continue
            
            logger.info(f"Loaded {len(self.processed_message_ids)} processed message IDs from {self.processed_ids_file}")
        except Exception as e:
            logger.error(f"Error loading processed message IDs: {e}")

    def save_processed_message_id(self, message_id):
        try:
            with open(self.processed_ids_file, 'a') as f:
                f.write(f"{message_id}\n")
        except Exception as e:
            logger.error(f"Error saving processed message ID {message_id}: {e}")

    async def connect(self):
        if not self.token:
            raise ValueError("DISCORD_TOKEN not set")
        
        self.session = aiohttp.ClientSession()
        
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json"
        }
        
        try:
            async with self.session.get(
                f"{self.base_url}/users/@me",
                headers=headers
            ) as response:
                if response.status == 401:
                    logger.error("Failed to authenticate with Discord. Check your token.")
                    raise ValueError("Invalid Discord token")
                elif response.status != 200:
                    logger.error(f"Failed to connect to Discord: {response.status}")
                    raise ConnectionError(f"Discord API returned status {response.status}")
                
                user_data = await response.json()
                logger.info(f"Discord API connected as {user_data.get('username', 'Unknown')}")
                logger.info(f"Monitoring channel ID: {self.channel_id}")
        except aiohttp.ClientError as e:
            logger.error(f"Error connecting to Discord API: {e}")
            raise

    async def get_new_messages(self):
        if not self.session:
            await asyncio.sleep(1)
            return []
        
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/channels/{self.channel_id}/messages?limit=10"
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 401:
                    logger.error("Unauthorized: Invalid Discord token")
                    return []
                elif response.status == 404:
                    logger.error(f"Channel {self.channel_id} not found")
                    return []
                elif response.status != 200:
                    logger.error(f"Failed to fetch messages: {response.status}")
                    return []
                
                messages_data = await response.json()
                messages = []
                today = datetime.now().date()
                filtered_count = 0
                
                for msg_data in messages_data:
                    msg = Message(msg_data)
                    if msg.id not in self.processed_message_ids:
                        if msg.timestamp:
                            message_date = msg.timestamp.date()
                            if message_date == today:
                                messages.append(msg)
                                self.processed_message_ids.add(msg.id)
                                self.save_processed_message_id(msg.id)
                            else:
                                filtered_count += 1
                                logger.debug(f"Filtered message {msg.id} from {message_date} (not today)")
                        else:
                            logger.warning(f"Message {msg.id} has no timestamp, skipping")
                
                if filtered_count > 0:
                    logger.info(f"Filtered {filtered_count} messages from previous days")
                
                if messages:
                    logger.info(f"Found {len(messages)} new messages from today")
                
                return messages
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return []

    async def close(self):
        if self.session:
            await self.session.close()
            logger.info("Discord API session closed")

