import os
import telebot
import tempfile
import fal_client
from telebot import types

# === API Keys ===
TELEGRAM_TOKEN = "034099199:AAETuS13M8oHyLrzu4-vnX9J920qNnaxtOg"
FAL_API_KEY = "d0ef57c7-5a0e-4a87-aa66-281b437bc0ae:3aaa35e26a361b9783c55d6b2781fc48"
os.environ["FAL_KEY"] = FAL_API_KEY

# === Admin Settings ===
ADMIN_IDS = [1074750898]  # User's chat ID

# === Required Channels ===
REQUIRED_CHANNELS = [
    {
        "username": "OSINT", 
        "url": "https://t.me/+g0PXmxFjHWs1MTE1", 
        "chat_id": "-1002830525000"  # OSINT private channel chat ID
    },
    {
        "username": "UR_IMAGE", 
        "url": "https://t.me/UR_IMAGE", 
        "chat_id": "-1002508479565"  # UR_IMAGE public channel chat ID
    }
]

# === Initialize bot and state ===
bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_states = {}  # chat_id: {"step": ..., "image_path": ...}

def check_user_membership(user_id):
    """Check if user is a member of all required channels"""
    # Admin bypass - admins don't need to join channels
    if user_id in ADMIN_IDS:
        return True
        
    for channel in REQUIRED_CHANNELS:
        try:
            # For the private channel, we'll need to get the actual chat_id
            # Now we have the actual chat IDs for both channels
            member = bot.get_chat_member(channel["chat_id"], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                print(f"User {user_id} is not a member of {channel['username']}")
                return False
        except Exception as e:
            print(f"Error checking membership for {channel['username']}: {str(e)}")
            # If we can't check, we'll assume they're not a member
            return False
    return True

def generate_channels_keyboard():
    """Generate inline keyboard with channel join buttons"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    for channel in REQUIRED_CHANNELS:
        button = types.InlineKeyboardButton(
            text=f"Join @{channel['username']}", 
            url=channel["url"]
        )
        markup.add(button)
    
    # Add check button
    check_button = types.InlineKeyboardButton(
        text="✅ I've joined all channels",
        callback_data="check_membership"
    )
    markup.add(check_button)
    
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership_callback(call):
    """Handle the callback when user clicks the check button"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if check_user_membership(user_id):
        bot.delete_message(chat_id, call.message.message_id)
        user_states[chat_id] = {"step": "waiting_image", "image_path": None}
        bot.send_message(chat_id, "👋 Welcome! Please send me an image to get started.")
    else:
        bot.answer_callback_query(
            call.id,
            "❌ You need to join all channels to use this bot.",
            show_alert=True
        )

@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if check_user_membership(user_id):
        user_states[chat_id] = {"step": "waiting_image", "image_path": None}
        bot.send_message(chat_id, "👋 Welcome! Please send me an image to get started.")
    else:
        bot.send_message(
            chat_id,
            "🔒 To use this bot, you need to join our channels first:",
            reply_markup=generate_channels_keyboard()
        )

@bot.message_handler(commands=['id'])
def get_id_command(message):
    """Command to get user ID"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    bot.send_message(
        chat_id,
        f"Your User ID: `{user_id}`\nChat ID: `{chat_id}`",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['getchatid'])
def get_chat_id_command(message):
    """Admin command to get the ID of a channel"""
    user_id = message.from_user.id
    
    # Check if user is an admin
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "❌ This command is only available to administrators.")
        return
    
    # Check if a channel username was provided
    if len(message.text.split()) < 2:
        bot.reply_to(message, "Please provide a channel username or ID.\nExample: /getchatid @channel_name")
        return
    
    channel = message.text.split()[1]
    
    try:
        chat = bot.get_chat(channel)
        bot.reply_to(message, f"Channel: {chat.title}\nID: {chat.id}")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Check if user is a member of required channels
    if not check_user_membership(user_id):
        bot.send_message(
            chat_id,
            "🔒 To use this bot, you need to join our channels first:",
            reply_markup=generate_channels_keyboard()
        )
        return
    
    # Initialize user state if not already set
    if chat_id not in user_states:
        user_states[chat_id] = {"step": "waiting_image", "image_path": None}
    
    bot.send_message(chat_id, "📥 Downloading your image...")
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_file.write(downloaded_file)
        temp_file_path = temp_file.name

    user_states[chat_id]["image_path"] = temp_file_path
    user_states[chat_id]["step"] = "waiting_prompt"
    bot.send_message(chat_id, "✅ Image saved. Now send the prompt you want to apply to the image.")

@bot.message_handler(content_types=['text'])
def handle_prompt(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Skip processing for /start command
    if text.startswith('/start'):
        return
    
    # Check if user is a member of required channels
    if not check_user_membership(user_id):
        bot.send_message(
            chat_id,
            "🔒 To use this bot, you need to join our channels first:",
            reply_markup=generate_channels_keyboard()
        )
        return

    if chat_id not in user_states:
        bot.send_message(chat_id, "Please send an image first.")
        return

    if user_states[chat_id]["step"] != "waiting_prompt":
        bot.send_message(chat_id, "Please send an image first.")
        return

    image_path = user_states[chat_id]["image_path"]
    prompt = text

    try:
        bot.send_message(chat_id, "🔄 Proccessing...")
        image_url = fal_client.upload_file(image_path)

        bot.send_message(chat_id, f"🎨 Editing image with prompt: *{prompt}*", parse_mode="Markdown")

        result = fal_client.submit(
            "fal-ai/flux-pro/kontext",
            arguments={
                "prompt": prompt,
                "guidance_scale": 3.5,
                "num_images": 2,
                "safety_tolerance": "6",
                "output_format": "png",
                "image_url": image_url
            }
        ).get()

        for i, image in enumerate(result["images"], start=1):
            bot.send_photo(chat_id, image["url"], caption=f"✅ Image {i}")

        bot.send_message(chat_id, "🎉 Done! Want to generate more images? Send me an image first.")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Error: {str(e)}")

    finally:
        if os.path.exists(image_path):
            os.remove(image_path)
        user_states.pop(chat_id, None)

print("🚀 Bot is running...")
bot.infinity_polling()
