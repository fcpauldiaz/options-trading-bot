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
        self.embeds = message_data.get("embeds", [])
        for embed in self.embeds:
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
    
    def is_spacemonkey(self):
        for embed in self.embeds:
            if isinstance(embed, dict):
                footer = embed.get("footer", {})
                if isinstance(footer, dict):
                    footer_text = footer.get("text", "")
                    if footer_text == "spacemonkey":
                        return True
        return False
    
    def get_embed_titles(self):
        titles = []
        for embed in self.embeds:
            if isinstance(embed, dict) and "title" in embed:
                titles.append(embed["title"])
        return titles

    def has_small_account_challenge(self):
        for embed in self.embeds:
            if isinstance(embed, dict):
                description = embed.get("description", "")
                if isinstance(description, str) and "SmallAccountChallenge" in description:
                    return True
        return False

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

    def mark_message_processed(self, message_id):
        if message_id not in self.processed_message_ids:
            self.processed_message_ids.add(message_id)
            self.save_processed_message_id(message_id)
            logger.debug(f"Marked message {message_id} as processed")

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
                spacemonkey_filtered_count = 0
                small_account_filtered_count = 0
                
                for msg_data in messages_data:
                    msg = Message(msg_data)
                    if msg.id not in self.processed_message_ids:
                        if msg.timestamp:
                            message_date = msg.timestamp.date()
                            if message_date == today:
                                if not msg.is_spacemonkey():
                                    spacemonkey_filtered_count += 1
                                    logger.debug(f"Filtered message {msg.id} (not spacemonkey)")
                                elif not msg.has_small_account_challenge():
                                    small_account_filtered_count += 1
                                    logger.debug(f"Filtered message {msg.id} (spacemonkey but not SmallAccountChallenge)")
                                else:
                                    messages.append(msg)
                            else:
                                filtered_count += 1
                                logger.debug(f"Filtered message {msg.id} from {message_date} (not today)")
                        else:
                            logger.warning(f"Message {msg.id} has no timestamp, skipping")
                
                if filtered_count > 0:
                    logger.debug(f"Filtered {filtered_count} messages from previous days")
                if spacemonkey_filtered_count > 0:
                    logger.debug(f"Filtered {spacemonkey_filtered_count} messages (not spacemonkey)")
                if small_account_filtered_count > 0:
                    logger.debug(f"Filtered {small_account_filtered_count} messages (spacemonkey but not SmallAccountChallenge)")
                
                if messages:
                    logger.info(f"Found {len(messages)} new spacemonkey SmallAccountChallenge messages from today")
                
                return messages
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return []

    async def close(self):
        if self.session:
            await self.session.close()
            logger.info("Discord API session closed")

