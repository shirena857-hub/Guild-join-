from flask import Flask, request, jsonify, Response
import requests
import jwt
import urllib3
import json
import time
from collections import OrderedDict
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import ReqCLan_pb2
import QuitClanReq_pb2
import my_pb2
import output_pb2

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

OB = "OB53"

API_INFO = {
    "developer": "RIZER",
    "telegram": "@Beotherjk",
    "api_name": "FF GUILD JOIN/LEAVE API",
    "version": OB
}

KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

GAME_HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/octet-stream",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": OB,
}
LOGIN_HEADERS = GAME_HEADERS.copy()
LOGIN_HEADERS.pop("Expect", None)

REGION_SERVER_MAP = {
    "IND": "https://client.ind.freefiremobile.com",
    "ME":  "https://clientbp.ggblueshark.com",
    "VN":  "https://clientbp.ggpolarbear.com",
    "BD":  "https://clientbp.ggwhitehawk.com",
    "PK":  "https://clientbp.ggblueshark.com",
    "SG":  "https://clientbp.ggpolarbear.com",
    "BR":  "https://client.us.freefiremobile.com",
    "NA":  "https://client.us.freefiremobile.com",
    "ID":  "https://clientbp.ggpolarbear.com",
    "RU":  "https://clientbp.ggpolarbear.com",
    "TH":  "https://clientbp.ggpolarbear.com",
}
DEFAULT_SERVER_URL = "https://clientbp.ggwhitehawk.com"

# বিভিন্ন পাথে ট্রাই করার জন্য লিস্ট
LOGIN_PATHS = [
    "",                    # বেস URL
    "/login",
    "/v1/login",
    "/garena/420/login",
    "/v1/auth/login"
]
LOGIN_BASE = "https://loginbp.ggpolarbear.com"

def encrypt_payload(data):
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return cipher.encrypt(pad(data, AES.block_size))

def decode_jwt(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return str(decoded.get("account_id")), decoded.get("nickname"), decoded.get("lock_region")
    except:
        return None, None, None

def get_server_url(region):
    return REGION_SERVER_MAP.get(region, DEFAULT_SERVER_URL)

def perform_major_login(access_token, open_id, region="BD"):
    # একাধিক পাথে চেষ্টা করবে
    for path in LOGIN_PATHS:
        login_url = LOGIN_BASE + path
        try:
            game = my_pb2.GameData()
            game.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            game.game_name = "free fire"
            game.game_version = 1
            game.version_code = "1.123.2"
            game.os_info = "Android OS 12 / API-31"
            game.device_type = "Handheld"
            game.network_provider = "Verizon"
            game.connection_type = "WIFI"
            game.screen_width = 1080
            game.screen_height = 2340
            game.dpi = "420"
            game.cpu_info = "ARM64"
            game.total_ram = 5951
            game.gpu_name = "Adreno"
            game.gpu_version = "OpenGL ES 3.0"
            game.user_id = f"Guest|{open_id}"
            game.ip_address = "172.190.111.97"
            game.language = "en"
            game.open_id = open_id
            game.access_token = access_token
            game.platform_type = 4
            game.field_99 = "4"
            game.field_100 = "4"
            encrypted = encrypt_payload(game.SerializeToString())
            
            print(f"Trying major login at: {login_url}")
            r = requests.post(login_url, headers=LOGIN_HEADERS, data=encrypted, verify=False, timeout=10)
            print(f"Status: {r.status_code}")
            if r.status_code == 200 and len(r.content) > 5:
                msg = output_pb2.Garena_420()
                msg.ParseFromString(r.content)
                if msg.token:
                    print(f"Success with path: {path}")
                    return msg.token
                else:
                    print("No token in response")
            else:
                print(f"Failed with {r.status_code}")
        except Exception as e:
            print(f"Error on path {path}: {e}")
            continue
    return None

def guest_login(uid, password):
    payload = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    headers = {"User-Agent": "GarenaMSDK/4.0.19P9"}
    try:
        r = requests.post("https://100067.connect.garena.com/oauth/guest/token/grant",
                          data=payload, headers=headers, verify=False, timeout=10)
        data = r.json()
        if "access_token" in data and "open_id" in data:
            return data["access_token"], data["open_id"]
        else:
            print("Guest login error:", data)
            return None, None
    except Exception as e:
        print("Guest login exception:", e)
        return None, None

def get_jwt_from_access_token(access_token):
    url = f"https://rizerxaccessjwt.vercel.app/rizer?access_token={access_token}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("success") and "jwt" in data:
            jwt_token = data["jwt"]
            uid, name, region = decode_jwt(jwt_token)
            return jwt_token, uid, name, region
        else:
            print("External API error:", data)
            return None, None, None, None
    except Exception as e:
        print("get_jwt_from_access_token error:", e)
        return None, None, None, None

def request_clan(jwt_token, clan_id, region):
    server_url = get_server_url(region)
    msg = ReqCLan_pb2.MyMessage()
    msg.field_1 = int(clan_id)
    payload = encrypt_payload(msg.SerializeToString())
    headers = GAME_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt_token}"
    url = f"{server_url}/RequestJoinClan"
    r = requests.post(url, headers=headers, data=payload, verify=False)
    return r.status_code, r.text

def quit_clan(jwt_token, clan_id, region):
    server_url = get_server_url(region)
    msg = QuitClanReq_pb2.QuitClanReq()
    msg.field_1 = int(clan_id)
    payload = encrypt_payload(msg.SerializeToString())
    headers = GAME_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt_token}"
    url = f"{server_url}/QuitClan"
    r = requests.post(url, headers=headers, data=payload, verify=False)
    return r.status_code, r.text

def resolve_login(jwt_token=None, uid=None, password=None, access_token=None):
    if jwt_token:
        uid, name, region = decode_jwt(jwt_token)
        if uid:
            return jwt_token, uid, name, region, "JWT"
        return None, None, None, None, "Invalid JWT"
    if access_token:
        jwt_token, uid, name, region = get_jwt_from_access_token(access_token)
        if jwt_token:
            return jwt_token, uid, name, region, "ACCESS_TOKEN"
        return None, None, None, None, "Access token conversion failed"
    if uid and password:
        acc_token, open_id = guest_login(uid, password)
        if not acc_token:
            return None, None, None, None, "Guest login failed"
        # Try major login first
        jwt_token = perform_major_login(acc_token, open_id, region="BD")
        if jwt_token:
            uid, name, region = decode_jwt(jwt_token)
            if not region:
                region = "BD"
            return jwt_token, uid, name, region, "UID_PASS"
        # If major login fails, try access_token conversion
        print("Major login failed, falling back to access_token conversion")
        jwt_token, uid, name, region = get_jwt_from_access_token(acc_token)
        if jwt_token:
            return jwt_token, uid, name, region, "UID_PASS_ALT"
        else:
            return None, None, None, None, "Both major login and token conversion failed"
    return None, None, None, None, "No login credentials provided"

@app.route("/")
def home():
    return Response(json.dumps({
        "success": True,
        "message": "Free Fire Clan API (Auto path detection + fallback)",
        "default_region": "BD",
        "server_url": DEFAULT_SERVER_URL,
        "examples": {
            "request_clan_uidpass": "/request_clan?clan_id=123&uid=123&pass=PASS",
            "quit_clan_uidpass": "/quit_clan?clan_id=123&uid=123&pass=PASS"
        }
    }, indent=2), mimetype="application/json")

@app.route("/request_clan")
def api_request():
    clan_id = request.args.get("clan_id")
    jwt_token = request.args.get("jwt")
    uid = request.args.get("uid")
    password = request.args.get("pass")
    if not clan_id:
        return jsonify({"success": False, "error": "clan_id required"})
    final_jwt, uid, name, region, method = resolve_login(jwt_token=jwt_token, uid=uid, password=password)
    if not final_jwt:
        return jsonify({"success": False, "error": method})
    code, text = request_clan(final_jwt, clan_id, region)
    return jsonify({
        "success": code == 200,
        "action": "Join Clan",
        "clan_id": clan_id,
        "uid": uid,
        "name": name,
        "region": region,
        "login_method": method,
        "server_response": text
    })

@app.route("/quit_clan")
def api_quit():
    clan_id = request.args.get("clan_id")
    jwt_token = request.args.get("jwt")
    uid = request.args.get("uid")
    password = request.args.get("pass")
    if not clan_id:
        return jsonify({"success": False, "error": "clan_id required"})
    final_jwt, uid, name, region, method = resolve_login(jwt_token=jwt_token, uid=uid, password=password)
    if not final_jwt:
        return jsonify({"success": False, "error": method})
    code, text = quit_clan(final_jwt, clan_id, region)
    return jsonify({
        "success": code == 200,
        "action": "Quit Clan",
        "clan_id": clan_id,
        "uid": uid,
        "name": name,
        "region": region,
        "login_method": method,
        "server_response": text
    })

@app.route("/request_clan_access")
def api_request_access():
    clan_id = request.args.get("clan_id")
    access_token = request.args.get("access_token")
    if not clan_id or not access_token:
        return jsonify({"success": False, "error": "clan_id and access_token required"})
    final_jwt, uid, name, region, method = resolve_login(access_token=access_token)
    if not final_jwt:
        return jsonify({"success": False, "error": method})
    code, text = request_clan(final_jwt, clan_id, region)
    return jsonify({"success": code == 200, "action": "Join Clan", "clan_id": clan_id, "uid": uid, "name": name, "region": region, "login_method": method, "server_response": text})

@app.route("/quit_clan_access")
def api_quit_access():
    clan_id = request.args.get("clan_id")
    access_token = request.args.get("access_token")
    if not clan_id or not access_token:
        return jsonify({"success": False, "error": "clan_id and access_token required"})
    final_jwt, uid, name, region, method = resolve_login(access_token=access_token)
    if not final_jwt:
        return jsonify({"success": False, "error": method})
    code, text = quit_clan(final_jwt, clan_id, region)
    return jsonify({"success": code == 200, "action": "Quit Clan", "clan_id": clan_id, "uid": uid, "name": name, "region": region, "login_method": method, "server_response": text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)