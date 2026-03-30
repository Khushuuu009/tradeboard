import pyotp
import logging
import os
from SmartApi import SmartConnect
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ANGEL_CONFIG = {
    "api_key":     os.getenv("ANGEL_API_KEY"),
    "client_id":   os.getenv("ANGEL_CLIENT_ID"),
    "password":    os.getenv("ANGEL_MPIN"),
    "totp_secret": os.getenv("ANGEL_TOTP_SECRET"),
}

logger = logging.getLogger(__name__)

_smartapi_obj = None
_auth_token   = None
_session_time = None

INDEX_TOKENS = {
    "NIFTY":     "99926000",
    "BANKNIFTY": "99926009",
    "SENSEX":    "99919000",
    "FINNIFTY":  "99926037",
}


def get_totp():
    return pyotp.TOTP(ANGEL_CONFIG["totp_secret"]).now()


def login():
    global _smartapi_obj, _auth_token, _session_time

    try:
        # Reuse session if less than 6 hours old
        if _smartapi_obj and _session_time:
            elapsed = (datetime.now() - _session_time).seconds
            if elapsed < 21600:
                return _smartapi_obj

        if not ANGEL_CONFIG["api_key"]:
            raise Exception("ANGEL_API_KEY missing from .env")
        if not ANGEL_CONFIG["totp_secret"]:
            raise Exception("ANGEL_TOTP_SECRET missing from .env")

        obj  = SmartConnect(api_key=ANGEL_CONFIG["api_key"])
        totp = get_totp()

        data = obj.generateSession(
            clientCode=ANGEL_CONFIG["client_id"],
            password=ANGEL_CONFIG["password"],
            totp=totp
        )

        if data["status"] is False:
            raise Exception(f"Login failed: {data['message']}")

        _auth_token   = data["data"]["jwtToken"]
        _smartapi_obj = obj
        _session_time = datetime.now()

        logger.info("Angel One login successful")
        return obj

    except Exception as e:
        logger.error(f"Angel One login error: {str(e)}")
        return None


def get_smartapi():
    obj = login()
    if obj is None:
        raise Exception("Could not connect to Angel One. Check your .env file.")
    return obj


def get_profile():
    try:
        obj     = get_smartapi()
        profile = obj.getProfile(_auth_token)
        return {
            "status":  "success",
            "name":    profile["data"]["name"],
            "email":   profile["data"]["email"],
            "broker":  "Angel One",
            "message": "Connected successfully"
        }
    except Exception as e:
        return {
            "status":  "error",
            "message": str(e)
        }