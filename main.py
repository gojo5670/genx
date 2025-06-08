import os
import telebot
import tempfile
import fal_client

# === API Keys ===
TELEGRAM_TOKEN = "7034099199:AAETuS13M8oHyLrzu4-vnX9J920qNnaxtOg"
FAL_API_KEY = "d0ef57c7-5a0e-4a87-aa66-281b437bc0ae:3aaa35e26a361b9783c55d6b2781fc48"
os.environ["FAL_KEY"] = FAL_API_KEY

# === Initialize bot and state ===
bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_states = {}  # chat_id: {"step": ..., "image_path": ...}

@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    user_states[chat_id] = {"step": "waiting_image", "image_path": None}
    bot.send_message(chat_id, "👋 Welcome! Please send me an image to get started.")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    
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
    text = message.text.strip()
    
    # Skip processing for /start command
    if text.startswith('/start'):
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
