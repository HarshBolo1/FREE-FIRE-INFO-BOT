from flask import Flask
from threading import Thread
import os
import asyncio
import time
import json
import httpx
import base64
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# --- Protobuf & Crypto Imports (Requires 'ff_proto' folder in same directory) ---
from ff_proto import freefire_pb2, core_pb2, account_show_pb2
from google.protobuf import json_format, message
from google.protobuf.message import Message
from Crypto.Cipher import AES
from typing import Tuple

# ================= TELEGRAM CONFIG =================
BOT_TOKEN = "8779390298:AAESD4PYHnsd-jSnu9_X8AXyS-klzrldO9I"
ALLOWED_GROUP_ID = -5264730215
OWNER_ID = 6022911800
SERVERS = ["BD", "IND", "PK"]
SPAM_DELAY = 0.8
MAX_LENGTH = 800
user_last_message = {}

# ================= FREE FIRE API CONFIG =================
MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
RELEASEVERSION = "OB48"
USERAGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
SUPPORTED_REGIONS = ["IND", "BR", "SG", "RU", "ID", "TW", "US", "VN", "TH", "ME", "PK", "CIS"]

# Updated with your new IND credentials
ACCOUNTS = {
    'IND': "uid=4575495117&password=6E06B647BEEEF5CEAB9F06B7A94AF4147EE4E90EB5C8C2079CB8DE2C07525FA4",
    'SG': "uid=3158350464&password=70EA041FCF79190E3D0A8F3CA95CAAE1F39782696CE9D85C2CCD525E28D223FC",
    'RU': "uid=3301239795&password=DD40EE772FCBD61409BB15033E3DE1B1C54EDA83B75DF0CDD24C34C7C8798475",
    'ID': "uid=3301269321&password=D11732AC9BBED0DED65D0FED7728CA8DFF408E174202ECF1939E328EA3E94356",
    'TW': "uid=3301329477&password=359FB179CD92C9C1A2A917293666B96972EF8A5FC43B5D9D61A2434DD3D7D0BC",
    'US': "uid=3301387397&password=BAC03CCF677F8772473A09870B6228ADFBC1F503BF59C8D05746DE451AD67128",
    'VN': "uid=3301447047&password=044714F5B9284F3661FB09E4E9833327488B45255EC9E0CCD953050E3DEF1F54",
    'TH': "uid=3301470613&password=39EFD9979BD6E9CCF6CBFF09F224C4B663E88B7093657CB3D4A6F3615DDE057A",
    'ME': "uid=3301535568&password=BEC9F99733AC7B1FB139DB3803F90A7E78757B0BE395E0A6FE3A520AF77E0517",
    'PK': "uid=3301828218&password=3A0E972E57E9EDC39DC4830E3D486DBFB5DA7C52A4E8B0B8F3F9DC4450899571",
    'CIS': "uid=3309128798&password=412F68B618A8FAEDCCE289121AC4695C0046D2E45DB07EE512B4B3516DDA8B0F",
    'BR': "uid=3158668455&password=44296D19343151B25DE68286BDC565904A0DA5A5CC5E96B7A7ADBE7C11E07933"
}

# Add more pet IDs here as you discover them
PET_MAP = {
    1300000001: "Kitty"
}

# ================= FF API CORE FUNCTIONS =================
async def json_to_proto(json_data: str, proto_message: Message) -> bytes:
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

def pad(text: bytes) -> bytes:
    padding_length = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([padding_length] * padding_length)

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    aes = AES.new(key, AES.MODE_CBC, iv)
    return aes.encrypt(pad(plaintext))

def decode_protobuf(encoded_data: bytes, message_type: message.Message) -> message.Message:
    message_instance = message_type()
    message_instance.ParseFromString(encoded_data)
    return message_instance

async def getAccess_Token(account):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = account + "&response_type=token&client_type=2&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    headers = {
        'User-Agent': USERAGENT, 'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip", 'Content-Type': "application/x-www-form-urlencoded"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload, headers=headers)
        data = response.json()
        return data.get("access_token", "0"), data.get("open_id", "0")

async def create_jwt(region: str) -> Tuple[str, str, str]:
    account = ACCOUNTS.get(region)
    access_token, open_id = await getAccess_Token(account)
    json_data = json.dumps({
      "open_id": open_id, "open_id_type": "4",
      "login_token": access_token, "orign_platform_type": "4"
    })
    encoded_result = await json_to_proto(json_data, freefire_pb2.LoginReq())
    payload = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, encoded_result)
    url = "https://loginbp.ggblueshark.com/MajorLogin"
    headers = {
        'User-Agent': USERAGENT, 'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip", 'Content-Type': "application/octet-stream",
        'Expect': "100-continue", 'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1", 'ReleaseVersion': RELEASEVERSION
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload, headers=headers)
        message = json.loads(json_format.MessageToJson(decode_protobuf(response.content, freefire_pb2.LoginRes)))
        return f"Bearer {message.get('token', '0')}", message.get("lockRegion", "0"), message.get("serverUrl", "0")

async def GetAccountInformation(ID, UNKNOWN_ID, regionMain, endpoint):
    regionMain = regionMain.upper()
    if regionMain not in SUPPORTED_REGIONS:
        return {"error": True, "message": "Unsupported region."}
    
    encoded_result = await json_to_proto(json.dumps({"a": ID, "b": UNKNOWN_ID}), core_pb2.GetPlayerPersonalShow())
    payload = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, encoded_result)
    
    try:
        token, region, serverUrl = await create_jwt(regionMain)
    except Exception as e:
        return {"error": True, "message": f"Auth failed: {e}"}

    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 13; A063 Build/TKQ1.221220.001)",
        'Connection': "Keep-Alive", 'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream", 'Expect': "100-continue",
        'Authorization': token, 'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1", 'ReleaseVersion': RELEASEVERSION
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(serverUrl + endpoint, data=payload, headers=headers)
        if response.status_code != 200:
            return {"error": True, "message": "Server returned non-200 status."}
            
        try:
            return json.loads(json_format.MessageToJson(decode_protobuf(response.content, account_show_pb2.AccountPersonalShowInfo)))
        except Exception as e:
            return {"error": True, "message": "Failed to decode protobuf response."}

# ================= TELEGRAM BOT LOGIC =================
async def anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text or ""
    now = time.time()

    if chat_id != ALLOWED_GROUP_ID or user_id == OWNER_ID:
        return

    if len(text) > MAX_LENGTH or now - user_last_message.get(user_id,0) < SPAM_DELAY:
        try: await update.message.delete()
        except: pass
        return

    user_last_message[user_id] = now

def ts_to_date(ts):
    try:
        # Prevent 1970 fallback if timestamp is 0 or invalid
        if not ts or ts == "0": return "N/A"
        return datetime.utcfromtimestamp(int(ts)).strftime("%d-%m-%Y %H:%M:%S")
    except:
        return "N/A"

async def inf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id != ALLOWED_GROUP_ID and user_id != OWNER_ID:
        await update.message.reply_text("❌ This bot works only in the official group.")
        return

    if len(context.args) not in [1, 2]:
        await update.message.reply_text("❗ Wrong command format!\nUse:\n/inf <uid>\n/inf <server> <uid>")
        return

    msg = await update.message.reply_text("⚡ Initiating Backend Handshake...")
    
    server = None
    data = None

    try:
        if len(context.args) == 2:
            server = context.args[0].upper()
            uid = context.args[1]
            await msg.edit_text(f"⚡ Fetching directly from {server} Servers...")
            data = await GetAccountInformation(uid, "0", server, "/GetPlayerPersonalShow")
            if data.get("error"):
                await msg.edit_text(f"❌ {data.get('message', 'Invalid UID or Server')}")
                return
        else:
            uid = context.args[0]
            await msg.edit_text("⚡ Auto-detecting server (This may take a moment)...")
            for s in SERVERS:
                r = await GetAccountInformation(uid, "0", s, "/GetPlayerPersonalShow")
                if not r.get("error") and r:
                    server = s
                    data = r
                    break
            if not server or not data:
                await msg.edit_text("❌ UID not found in any supported server")
                return

        # -------- Parse Data based on actual Protobuf keys --------
        basic = data.get("basicInfo", {})
        clan = data.get("clanBasicInfo", {})
        pet = data.get("petInfo", {})
        
        # Mapping Pet ID to Name
        pet_id = pet.get('id', 0)
        pet_name = PET_MAP.get(pet_id, f"Unknown ID: {pet_id}" if pet_id else "None")

        # -------- Format Text --------
        text = f"""
🔥 FREE FIRE FULL PROFILE 🔥

👤 Name: {basic.get('nickname','N/A')}
🆔 UID: {basic.get('accountId', uid)}
🌍 Server: {basic.get('region', server)}
⭐ Level: {basic.get('level','N/A')}
📈 EXP: {basic.get('exp','N/A')}
👍 Likes: {basic.get('liked','N/A')}
📅 Account Created: {ts_to_date(basic.get('createAt','0'))}
🕒 Last Login: {ts_to_date(basic.get('lastLoginAt','0'))}

🏆 RANK INFO
🥇 CS Rank: {basic.get('csRank','N/A')}
⭐ CS Max Rank: {basic.get('csMaxRank','N/A')}
⭐ Ranking Points: {basic.get('rankingPoints','N/A')}

🏰 GUILD INFO
Guild Name: {clan.get('clanName','No Guild')}
Guild Level: {clan.get('clanLevel','N/A')}

🐾 PET INFO
🐶 Pet: {pet_name}
⭐ Pet Level: {pet.get('level','N/A')}
"""
        await msg.edit_text(text)

    except Exception as e:
        print("Error:", e)
        await msg.edit_text("⚠️ System error, try again later.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 FF INFO BOT READY 🔥\n\nUse:\n/inf uid\n/inf server uid")

# ================= RENDER KEEP-ALIVE HACK =================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🔥 FF Bot is awake and running!"

def run_flask():
    # Render assigns a dynamic port, so we must grab it from the environment
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()
# ==========================================================


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("inf", inf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam))
    
    print("Starting Keep-Alive Web Server...")
    keep_alive() # <--- THIS STARTS THE FLASK SERVER
    
    print("Bot is polling...")
    app.run_polling()
