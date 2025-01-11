import itchat
import time
import logging
import os
from datetime import datetime
from itchat.content import (
    TEXT, PICTURE, RECORDING, ATTACHMENT, VIDEO,
    MAP, CARD, NOTE, SHARING, FRIENDS
)

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/wechat_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Store chat room information
monitored_rooms = {}

def on_login():
    """Callback function when login is successful"""
    logger.info('Successfully logged in')
    try:
        # Get all chat rooms
        chat_rooms = itchat.get_chatrooms(update=True)
        logger.info(f'Found {len(chat_rooms)} chat rooms')
        for room in chat_rooms:
            room_name = room.get('NickName', 'Unknown')
            room_id = room.get('UserName', '')
            monitored_rooms[room_id] = room_name
            logger.info(f"Chat room: {room_name} (ID: {room_id})")
    except Exception as e:
        logger.error(f'Error getting chat rooms: {str(e)}')

def on_exit():
    """Callback function when logged out"""
    logger.info('Logged out')

@itchat.msg_register([TEXT, NOTE, PICTURE, RECORDING, ATTACHMENT, VIDEO], isGroupChat=True)
def handle_group_message(msg):
    """Handle messages from group chats"""
    try:
        # Get message details
        room_id = msg.FromUserName
        room_name = monitored_rooms.get(room_id, 'Unknown Group')
        sender = msg.actualNickName
        msg_time = datetime.fromtimestamp(msg.CreateTime).strftime('%Y-%m-%d %H:%M:%S')
        msg_type = msg.type
        
        # Handle different message types
        if msg_type == TEXT:
            content = msg.text
        elif msg_type in [PICTURE, RECORDING, ATTACHMENT, VIDEO]:
            # Create a unique filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"media/{timestamp}_{msg.fileName}"
            content = f"[{msg_type}] File: {filename}"
            # Download media files
            msg.download(filename)
        else:
            content = f"[{msg_type}]"
        
        # Prepare message data for logging
        msg_data = {
            'Group': room_name,
            'From': sender,
            'Time': msg_time,
            'Type': msg_type,
            'Content': content
        }
        
        # Log the message
        logger.info(f"Group: {room_name}")
        logger.info(f"From: {sender}")
        logger.info(f"Time: {msg_time}")
        logger.info(f"Content: {content}")
        logger.info("-" * 50)
        
        # Save message to daily log file
        save_message(msg_data)
        
    except Exception as e:
        logger.error(f'Error handling message: {str(e)}')

def save_message(msg_data):
    """Save message to a daily log file"""
    try:
        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f'logs/messages_{date_str}.log'
        
        with open(filename, 'a', encoding='utf-8') as f:
            f.write('-' * 50 + '\n')
            for key, value in msg_data.items():
                f.write(f'{key}: {value}\n')
            f.write('-' * 50 + '\n')
    except Exception as e:
        logger.error(f'Error saving message: {str(e)}')

def main():
    """Main function to run the WeChat monitor"""
    logger.info('Starting WeChat monitor...')
    
    try:
        # Create media directory for downloaded files
        os.makedirs('media', exist_ok=True)
        
        # Enable hot reload to maintain login state
        itchat.auto_login(
            hotReload=True,
            statusStorageDir='logs/wechat_login.pkl',
            loginCallback=on_login,
            exitCallback=on_exit,
            enableCmdQR=2  # For better compatibility in Linux environments
        )
        
        # Keep the bot running
        logger.info('WeChat monitor is running...')
        itchat.run()
    except Exception as e:
        logger.error(f'Error in WeChat monitor: {str(e)}')
        raise  # Re-raise the exception after logging

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info('WeChat monitor stopped by user')
    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}')
