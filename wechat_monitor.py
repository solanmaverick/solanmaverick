import itchat
import time
import logging
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
from transformers import pipeline
from apscheduler.schedulers.background import BackgroundScheduler
from itchat.content import (
    TEXT, PICTURE, RECORDING, ATTACHMENT, VIDEO,
    MAP, CARD, NOTE, SHARING, FRIENDS
)
import qrcode
from PIL import Image

# Create required directories
os.makedirs('logs', exist_ok=True)
os.makedirs('media', exist_ok=True)
os.makedirs('summaries', exist_ok=True)

# Load or create config
CONFIG_FILE = 'config.json'
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
else:
    config = {
        'monitored_groups': [],  # List of group IDs to monitor
        'summary_time': '23:59',  # Time to generate daily summaries
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# Initialize summarization pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

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
def handle_group_msg(msg):
    """Handle messages from group chats"""
    handle_group_message(msg)

def handle_filehelper_command(msg):
    """Handle command messages sent to filehelper"""
    try:
        command = msg['Text'].strip()
        if command == '/list':
            # List all available groups
            groups_msg = "Available Groups:\n"
            monitored_count = 0
            for room_id, room_name in monitored_rooms.items():
                status = "✓" if room_id in config['monitored_groups'] else " "
                groups_msg += f"[{status}] {room_name} (ID: {room_id})\n"
                if status == "✓":
                    monitored_count += 1
            groups_msg += f"\nCurrently monitoring {monitored_count} groups"
            itchat.send(groups_msg, 'filehelper')
            logger.info(f"Listed {len(monitored_rooms)} groups ({monitored_count} monitored)")
        
        elif command.startswith('/monitor '):
            group_id = command[9:].strip()
            if group_id in monitored_rooms:
                if group_id not in config['monitored_groups']:
                    config['monitored_groups'].append(group_id)
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                    response = f'Now monitoring group: {monitored_rooms[group_id]}'
                    itchat.send(response, 'filehelper')
                    logger.info(f"Started monitoring group: {monitored_rooms[group_id]} ({group_id})")
                else:
                    itchat.send('This group is already being monitored.', 'filehelper')
            else:
                itchat.send('Invalid group ID. Use /list to see available groups.', 'filehelper')
        
        elif command.startswith('/unmonitor '):
            group_id = command[11:].strip()
            if group_id in config['monitored_groups']:
                config['monitored_groups'].remove(group_id)
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                itchat.send(f'Stopped monitoring group: {monitored_rooms[group_id]}', 'filehelper')
            else:
                itchat.send('This group is not being monitored.', 'filehelper')
        
        elif command == '/help':
            help_msg = """Available Commands:
/list - List all available groups
/monitor [group_id] - Start monitoring a group
/unmonitor [group_id] - Stop monitoring a group
/help - Show this help message"""
            itchat.send(help_msg, 'filehelper')
    
    except Exception as e:
        logger.error(f'Error handling command: {str(e)}')
        itchat.send('Error processing command. Please try again.', 'filehelper')

def handle_group_message(msg):
    """Handle messages from group chats"""
    try:
        # Get message details
        group_id = msg.FromUserName
        group_name = monitored_rooms.get(group_id, 'Unknown Group')
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
            'GroupId': group_id,
            'Group': group_name,
            'From': sender,
            'Time': msg_time,
            'Type': msg_type,
            'Content': content
        }
        
        # Log the message
        logger.info(f"Group: {group_name}")
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
        group_id = msg_data.get('GroupId', 'unknown')
        
        # Save to general log
        filename = f'logs/messages_{date_str}.log'
        with open(filename, 'a', encoding='utf-8') as f:
            f.write('-' * 50 + '\n')
            for key, value in msg_data.items():
                f.write(f'{key}: {value}\n')
            f.write('-' * 50 + '\n')
        
        # Save to group-specific log if group is monitored
        if group_id in config['monitored_groups']:
            group_log = f'logs/group_{group_id}_{date_str}.log'
            with open(group_log, 'a', encoding='utf-8') as f:
                f.write(f"{msg_data['Time']} - {msg_data['From']}: {msg_data['Content']}\n")
    
    except Exception as e:
        logger.error(f'Error saving message: {str(e)}')

def generate_summary(group_id, date_str=None):
    """Generate summary for a specific group's messages"""
    try:
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        group_name = monitored_rooms.get(group_id, 'Unknown Group')
        group_log = f'logs/group_{group_id}_{date_str}.log'
        
        if not os.path.exists(group_log):
            logger.warning(f'No messages found for group {group_name} ({group_id}) on {date_str}')
            return None
        
        # Read messages and analyze
        message_types = defaultdict(int)
        user_messages = defaultdict(int)
        total_messages = 0
        
        with open(group_log, 'r', encoding='utf-8') as f:
            messages = []
            for line in f:
                total_messages += 1
                if ' - ' in line:
                    sender = line.split(' - ')[1].split(':')[0].strip()
                    user_messages[sender] += 1
                    if '[' in line and ']' in line:
                        msg_type = line[line.find('[')+1:line.find(']')]
                        message_types[msg_type] += 1
                messages.append(line)
            
            messages_text = ''.join(messages)
        
        # Generate summary using transformers
        if len(messages_text.strip()) > 0:
            summary = summarizer(messages_text, max_length=130, min_length=30, do_sample=False)[0]['summary_text']
            
            # Save detailed summary
            summary_file = f'summaries/summary_{group_id}_{date_str}.txt'
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"Daily Summary for {group_name} ({group_id})\n")
                f.write(f"Date: {date_str}\n")
                f.write("-" * 50 + "\n\n")
                f.write("Summary:\n")
                f.write(summary + "\n\n")
                f.write("Message Statistics:\n")
                f.write(f"Total messages: {total_messages}\n\n")
                
                if message_types:
                    f.write("Message Types:\n")
                    for msg_type, count in message_types.items():
                        f.write(f"- {msg_type}: {count}\n")
                    f.write("\n")
                
                if user_messages:
                    f.write("Top Contributors:\n")
                    sorted_users = sorted(user_messages.items(), key=lambda x: x[1], reverse=True)[:5]
                    for user, count in sorted_users:
                        f.write(f"- {user}: {count} messages\n")
            
            logger.info(f"Generated summary for {group_name} ({group_id}) with {total_messages} messages")
            return summary
        return None
    
    except Exception as e:
        logger.error(f'Error generating summary: {str(e)}')
        return None

def generate_daily_summaries():
    """Generate summaries for all monitored groups"""
    logger.info('Generating daily summaries...')
    for group_id in config['monitored_groups']:
        summary = generate_summary(group_id)
        if summary:
            logger.info(f'Generated summary for group {group_id}')
            logger.info(f'Summary: {summary}')

def main():
    """Main function to run the WeChat monitor"""
    logger.info('Starting WeChat monitor...')
    
    try:
        # Register command handler for filehelper
        @itchat.msg_register(['Text'])
        def filehelper_handler(msg):
            if msg['ToUserName'] == 'filehelper':
                handle_filehelper_command(msg)
        
        # Set up scheduler for daily summaries
        scheduler = BackgroundScheduler()
        summary_time = config['summary_time'].split(':')
        scheduler.add_job(
            generate_daily_summaries,
            'cron',
            hour=summary_time[0],
            minute=summary_time[1]
        )
        scheduler.start()
        
        # Enable hot reload to maintain login state
        def qr_callback(uuid, status, qrcode):
            if status == '0':
                try:
                    # Convert terminal QR code to image
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(f'https://login.weixin.qq.com/l/{uuid}')
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    qr_path = os.path.join('logs', 'QR.png')
                    img.save(qr_path)
                    logger.info(f'QR code saved as {qr_path}')
                except Exception as e:
                    logger.error(f'Error generating QR code image: {str(e)}')
                    return

        itchat.auto_login(
            hotReload=True,
            statusStorageDir='logs/wechat_login.pkl',
            loginCallback=on_login,
            exitCallback=on_exit,
            qrCallback=qr_callback,
            enableCmdQR=False
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
