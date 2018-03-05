import os
import sys
import json
import time
import argparse
import binascii
import threading
import logging

from functools import wraps
from json.decoder import JSONDecodeError
from tempfile import NamedTemporaryFile
from collections import defaultdict

import logzero

from klein import Klein, resource
from logzero import logger

from Crypto import Random

from twisted.internet import reactor, task, endpoints
from twisted.web.server import Request, Site
from twisted.python import log
from twisted.internet.protocol import Factory

# Allow importing 'neo' from parent path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, parent_dir)

from neo.Network.NodeLeader import NodeLeader
from neo.Implementations.Blockchains.LevelDB.LevelDBBlockchain import LevelDBBlockchain
from neo.Core.Blockchain import Blockchain
from neo.Settings import settings

from identity.sc_invoke_flow import IdentitySmartContract
from identity.utils import bytestr_to_str, parse_id_list, bytes_to_address, byte_to_int, byte_list_to_int_list

# Set constants from env vars or use default
API_PORT = os.getenv("IIDENTITY_API_PORT", "8090")

# COZ TEST CONFIG
PROTOCOL_CONFIG = os.path.join(parent_dir, "protocol.coz.json")
WALLET_FILE = os.getenv("IDENTITY_WALLET_FILE", os.path.join(parent_dir, "identity-wallets/coz-test-wallet.db3"))
WALLET_PWD = os.getenv("IDENTITY_WALLET_PWD", "identity123")
CONTRACT_HASH = os.getenv("IDENTITY_SC_HASH", "1bc5b3eda086169dac515353e5d914c20cf08c56")

# PRIVNET CONFIG
# PROTOCOL_CONFIG = os.path.join(parent_dir, "protocol.privnet.json")
# WALLET_FILE = os.getenv("IDENTITY_WALLET_FILE", os.path.join(parent_dir, "identity-wallets/neo-privnet.wallet"))
# WALLET_PWD = os.getenv("IDENTITY_WALLET_PWD", "coz")
# CONTRACT_HASH = os.getenv("IDENTITY_SC_HASH", "33127f8cbc573cea03ef35e9d1586e6aa208fc74")

print(PROTOCOL_CONFIG, API_PORT, CONTRACT_HASH, WALLET_FILE, WALLET_PWD)

LOGFILE = os.path.join(parent_dir, "identity.log")
logzero.logfile(LOGFILE, maxBytes=1e7, backupCount=3)

# API error codes
STATUS_ERROR_AUTH_TOKEN = 1
STATUS_ERROR_JSON = 2
STATUS_ERROR_GENERIC = 3

IS_DEV = True
API_AUTH_TOKEN = os.getenv("IDENTITY_API_AUTH_TOKEN")
if not API_AUTH_TOKEN:
    if IS_DEV:
        API_AUTH_TOKEN = "test-token"
    else:
        raise Exception("No IDENTITY_API_AUTH_TOKEN environment variable found")


# Setup the smart contract
smart_contract = IdentitySmartContract(CONTRACT_HASH, WALLET_FILE, WALLET_PWD)

# Setup web app
app = Klein()


def build_error(error_code, error_message, to_json=True):
    """ Builder for generic errors """
    res = {
        "errorCode": error_code,
        "errorMessage": error_message
    }
    return json.dumps(res) if to_json else res


def authenticated(func):
    """ @authenticated decorator, which makes sure the HTTP request has the correct access token """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if IS_DEV:
            return func(request, *args, **kwargs)

        # Make sure Authorization header is present
        if not request.requestHeaders.hasHeader("Authorization"):
            request.setHeader('Content-Type', 'application/json')
            request.setResponseCode(403)
            return build_error(STATUS_ERROR_AUTH_TOKEN, "Missing Authorization header")

        # Make sure Authorization header is valid
        user_auth_token = str(request.requestHeaders.getRawHeaders("Authorization")[0])
        if user_auth_token != "Bearer %s" % API_AUTH_TOKEN:
            request.setHeader('Content-Type', 'application/json')
            request.setResponseCode(403)
            return build_error(STATUS_ERROR_AUTH_TOKEN, "Wrong auth token")

        # If all good, proceed to request handler
        return func(request, *args, **kwargs)
    return wrapper


def json_response(func):
    """ @json_response decorator adds header and dumps response object """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        res = func(request, *args, **kwargs)
        request.setHeader('Content-Type', 'application/json')
        return json.dumps(res) if isinstance(res, dict) else res
    return wrapper


def catch_exceptions(func):
    """ @catch_exceptions decorator which handles generic exceptions in the request handler """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            res = func(request, *args, **kwargs)
        except Exception as e:
            logger.exception(e)
            request.setResponseCode(500)
            request.setHeader('Content-Type', 'application/json')
            return build_error(STATUS_ERROR_GENERIC, str(e))
        return res
    return wrapper


@app.route('/identity/claim_gas/<usr_adr>', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def claim_gas(request, usr_adr):
    if IS_DEV:
        tx_hash = smart_contract.claim_gas(usr_adr)
        return {"result": tx_hash}
    return {"result": "Not supported"}


@app.route('/identity/tx/<tx_hash>', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def find_transaction(request, tx_hash):
    found = smart_contract.find_tx(tx_hash)
    return {"result": found}


@app.route('/identity/users/', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def get_users(request):
    results, tx_unconfirmed, tx_failed, tx_hash = smart_contract.invoke_single("getUserList", [])
    usr_adr_list = [bytes_to_address(item) for item in results]
    return {"result": usr_adr_list, "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed}


@app.route('/identity/users/<user_adr>/pubkey/', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def get_pubkey_by_user_id(request, user_adr):
    result, tx_unconfirmed, tx_failed, tx_hash = smart_contract.invoke_single("getUserPubKey", [user_adr])
    return {"result": bytestr_to_str(result), "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed}


@app.route('/identity/users/<user_adr>/pubkey/', methods=['POST'])
@authenticated
@catch_exceptions
@json_response
def set_pubkey_by_user_id(request, user_adr):
    try:
        body = json.loads(request.content.read().decode("utf-8"))
    except JSONDecodeError as e:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "JSON Error: %s" % str(e))

    if len(user_adr) != 34:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Address not 34 characters")

    if "pub_key" not in body:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Missing creator_adr")
    pub_key = body["pub_key"]
    result, tx_unconfirmed, tx_failed, tx_hash = smart_contract.invoke_single("setUserPubKey", [user_adr, pub_key], True)
    return {"result": byte_to_int(result), "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed, "tx_hash": tx_hash}


@app.route('/identity/users/<user_adr>/records/', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def get_records_by_user_id(request, user_adr):
    results, tx_unconfirmed, tx_failed, tx_hash = smart_contract.invoke_single("getRecordIdList", [user_adr])
    return {"result": byte_list_to_int_list(results), "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed}


@app.route('/identity/users/<user_adr>/records/', methods=['POST'])
@authenticated
@catch_exceptions
@json_response
def insert_record(request, user_adr):
    try:
        body = json.loads(request.content.read().decode("utf-8"))
    except JSONDecodeError as e:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "JSON Error: %s" % str(e))

    if len(user_adr) != 34:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Address not 34 characters")

    if "creator_adr" not in body:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Missing creator_adr")
    creator_adr = body["creator_adr"]

    if len(creator_adr) != 34:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Creator address not 34 characters")

    if "records" not in body or not isinstance(body["records"], list) or len(body["records"]) < 1:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "You should pass 'records': [{key1, data1}, {key2, data2}]")

    invoke_list = []
    for item in body["records"]:
        if "data_pub_key" not in item:
            request.setResponseCode(400)
            return build_error(STATUS_ERROR_JSON, "Missing data_pub_key")

        if "data_encr" not in item:
            request.setResponseCode(400)
            return build_error(STATUS_ERROR_JSON, "Missing data_encr")

        data_pub_key = item["data_pub_key"]
        data_encr = item["data_encr"]
        invoke_list.append(("createRecord", [creator_adr, user_adr, data_pub_key, data_encr]))

    results, tx_unconfirmed, tx_failed, tx_hash= smart_contract.invoke_multi(invoke_list, True)
    return {"result": byte_list_to_int_list(results), "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed, "tx_hash": tx_hash}


@app.route('/identity/records/<record_id>/verify', methods=['POST'])
@authenticated
@catch_exceptions
@json_response
def verify_record(request, record_id):
    record_id_list = parse_id_list(record_id)
    if not record_id_list:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Invalid record id list. Format: {i1:i2:i3}")

    invoke_list = []
    for id in record_id_list:
        invoke_list.append(("verifyRecord", [id]))

    results, tx_unconfirmed, tx_failed, tx_hash = smart_contract.invoke_multi(invoke_list, True)
    return {"result": byte_list_to_int_list(results), "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed, "tx_hash": tx_hash}


@app.route('/identity/records/<record_id>', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def get_record_by_id(request, record_id):
    record_id_list = parse_id_list(record_id)
    if not record_id_list:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Invalid record id list. Format: {i1:i2:i3}")

    invoke_list = []
    for id in record_id_list:
        invoke_list.append(("getRecord", [id]))

    results, tx_unconfirmed, tx_failed, tx_hash = smart_contract.invoke_multi(invoke_list)
    result_list = []
    for result in results:
        item = {}
        if len(result) == 5:
            item['usr_adr'] = bytes_to_address(result[0])
            item['pub_key'] = bytestr_to_str(result[1])
            item['creator_adr'] = bytes_to_address(result[2])
            item['is_verified'] = True if result[3] == b'\x01' else False
            item['data_encr'] = bytestr_to_str(result[4])
        else:
            item = {}
        result_list.append(item)

    return {"result": result_list, "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed}


@app.route('/identity/records/<record_id>', methods=['DELETE'])
@authenticated
@catch_exceptions
@json_response
def remove_record_by_id(request, record_id):
    result, tx_unconfirmed, tx_failed, tx_hash= smart_contract.invoke_single("deleteRecord", [record_id], True)
    return {"result": byte_to_int(result), "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed, "tx_hash": tx_hash}


@app.route('/identity/orders/', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def get_orders(request):
    results, tx_unconfirmed, tx_failed, tx_hash = smart_contract.invoke_single("getOrderIdList", [])
    id_list = [int.from_bytes(item, byteorder='little') for item in results]
    return {"result": id_list, "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed}


@app.route('/identity/users/<user_adr>/orders/', methods=['POST'])
@authenticated
@catch_exceptions
@json_response
def insert_order(request, user_adr):
    try:
        body = json.loads(request.content.read().decode("utf-8"))
    except JSONDecodeError as e:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "JSON Error: %s" % str(e))

    if len(user_adr) != 34:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Address not 34 characters")

    if "record_id_list" not in body:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Missing record_id_list")
    record_id_list = body["record_id_list"]

    if isinstance(record_id_list, str):
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Should be a list record_id_list")

    record_id_list_str = ""
    for record_id in record_id_list:
        record_id_list_str += str(int(record_id))
        record_id_list_str += ":"

    if len(record_id_list_str) == 0:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Empty list record_id_list")
    else:
        record_id_list_str = record_id_list_str[0:len(record_id_list_str)-1]

    if "price" not in body:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Missing price")

    price = int(body["price"])
    if price < 0:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Price can not be negative")

    result, tx_unconfirmed, tx_failed, tx_hash= smart_contract.invoke_single("createOrder", [user_adr, record_id_list_str, price], True)
    return {"result": byte_to_int(result), "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed, "tx_hash": tx_hash}


@app.route('/identity/orders/<order_id>', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def get_order_by_id(request, order_id):
    order_id_list = parse_id_list(order_id)
    if not order_id_list:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Invalid order_id list. Format: {i1:i2:i3}")

    invoke_list = []
    for id in order_id_list:
        invoke_list.append(("getOrder", [id]))

    results, tx_unconfirmed, tx_failed, tx_hash = smart_contract.invoke_multi(invoke_list)
    result_list = []
    for result in results:
        item = {}
        if len(result) == 4:
            item['usr_adr'] = bytes_to_address(result[0])
            item['record_list'] = parse_id_list(bytestr_to_str(str(result[1])))
            item['price'] = int.from_bytes(result[2], byteorder='little')
            item['customer'] = bytestr_to_str(result[3])
        else:
            item = {}
        result_list.append(item)

    return {"result": result_list, "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed}


@app.route('/identity/orders/<order_id>', methods=['DELETE'])
@authenticated
@catch_exceptions
@json_response
def remove_order_by_id(request, order_id):
    result, tx_unconfirmed, tx_failed, tx_hash= smart_contract.invoke_single("deleteOrder", [order_id], True)
    return {"result": byte_to_int(result), "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed, "tx_hash": tx_hash}


@app.route('/identity/orders/<order_id>/purchase', methods=['POST'])
@authenticated
@catch_exceptions
@json_response
def purchase_order_by_id(request, order_id):
    try:
        body = json.loads(request.content.read().decode("utf-8"))
    except JSONDecodeError as e:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "JSON Error: %s" % str(e))

    if "pub_key" not in body:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Missing pub_key")
    pub_key = body["pub_key"]

    if "attach_neo" not in body:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Missing attach_neo")

    attach_neo = int(body["attach_neo"])
    if attach_neo < 0:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "attach_neo can not be negative")

    order, tx_unconfirmed, tx_failed, tx_hash = smart_contract.invoke_single("getOrder", [order_id])
    if len(order) == 4:
        order[0] = bytes_to_address(order[0])
        order[1] = parse_id_list(bytestr_to_str(str(order[1])))
        order[2] = int.from_bytes(order[2], byteorder='little')
        order[3] = bytestr_to_str(order[3])
    else:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Order doesn't exist")

    if order[3] != '\\x00' and order[3] != '':
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "Already purchased")

    if attach_neo < order[2]:
        request.setResponseCode(400)
        return build_error(STATUS_ERROR_JSON, "NEO required: "+str(order[2]))

    result, tx_unconfirmed, tx_failed, tx_hash= smart_contract.invoke_single("purchaseData", [order_id, pub_key], True, attach_neo)
    return {"result": byte_to_int(result), "tx_unconfirmed": tx_unconfirmed, "tx_failed": tx_failed, "tx_hash": tx_hash}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", action="store", help="Config file (default. %s)" % PROTOCOL_CONFIG, default=PROTOCOL_CONFIG)
    args = parser.parse_args()
    settings.setup(args.config)

    logger.info("Starting api.py")
    logger.info("Config: %s", args.config)
    logger.info("Network: %s", settings.net_name)

    # Get the blockchain up and running
    blockchain = LevelDBBlockchain(settings.LEVELDB_PATH)
    Blockchain.RegisterBlockchain(blockchain)
    reactor.suggestThreadPoolSize(15)
    NodeLeader.Instance().Start()
    dbloop = task.LoopingCall(Blockchain.Default().PersistBlocks)
    dbloop.start(.1)
    Blockchain.Default().PersistBlocks()

    # Hook up Klein API to Twisted reactor
    endpoint_description = "tcp:port=%s:interface=0.0.0.0" % API_PORT
    endpoint = endpoints.serverFromString(reactor, endpoint_description)
    endpoint.listen(Site(app.resource()))

    # helper for periodic log output
    def log_infos():
        while True:
            logger.info("Block %s / %s", str(Blockchain.Default().Height), str(Blockchain.Default().HeaderHeight))
            time.sleep(60)

    t = threading.Thread(target=log_infos)
    t.setDaemon(True)
    t.start()

    # reactor.callInThread(sc_queue.run)
    reactor.run()
