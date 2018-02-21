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


# Set constants from env vars or use default
API_PORT = os.getenv("IIDENTITY_API_PORT", "8090")
CONTRACT_HASH = os.getenv("IDENTITY_SC_HASH", "d63a0b437a16579288361ccb593570e5c5f71149")

PROTOCOL_CONFIG = os.path.join(parent_dir, "protocol.coz.json")
WALLET_FILE = os.getenv("IDENTITY_WALLET_FILE", os.path.join(parent_dir, "identity-wallets/coz-test-wallet.db3"))
WALLET_PWD = os.getenv("IDENTITY_WALLET_PWD", "identity123")

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


@app.route('/')
@authenticated
def pg_root(request):
    return 'I am the root page!'


@app.route('/identity/tx/<tx_hash>', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def find_transaction(request, tx_hash):
    logger.info("/identity/tx/<tx_hash>")
    found = smart_contract.find_tx(tx_hash)
    return {"result": found}


@app.route('/identity/records/<record_id>', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def get_record_by_id(request, record_id):
    logger.info("/identity/records/<record_id>")
    result, tx_unconfirmed = smart_contract.test_invoke("getRecord", record_id)
    return {"result": str(result), "tx_unconfirmed": tx_unconfirmed}


@app.route('/identity/users/', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def get_users(request):
    logger.info("/identity/users/")
    result, tx_unconfirmed = smart_contract.test_invoke("getUserList")
    return {"result": result, "tx_unconfirmed": tx_unconfirmed}


@app.route('/identity/users/<user_adr>/records/', methods=['GET'])
@authenticated
@catch_exceptions
@json_response
def get_records_by_user_id(request, user_adr):
    logger.info("/identity/users/<user_id>/records/")
    result, tx_unconfirmed = smart_contract.test_invoke("getRecordIdList", user_adr)
    return {"result": str(result), "tx_unconfirmed": tx_unconfirmed}


@app.route('/identity/users/<user_adr>/records/', methods=['POST'])
@authenticated
@catch_exceptions
@json_response
def inser_record(request, user_adr, record_id):
    logger.info("/identity/users/<user_id>/records/<record_id>")
    return "Not implemented yet"


@app.route('/identity/users/<user_adr>/records/<record_id>', methods=['DELETE'])
@authenticated
@catch_exceptions
@json_response
def remove_record(request, user_adr, record_id):
    logger.info("/identity/users/<user_id>/records/<record_id>")
    return "Not implemented yet"


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
