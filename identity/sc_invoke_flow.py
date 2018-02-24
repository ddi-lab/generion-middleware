import time
import threading

from logzero import logger
from twisted.internet import task

from neo.Implementations.Wallets.peewee.UserWallet import UserWallet
from neo.Prompt.Commands.Invoke import InvokeContract, TestInvokeContract, test_invoke
from neo.Prompt.Commands.Send import construct_and_send
from neo.Settings import settings
from neo.Core.Blockchain import Blockchain
from neo.contrib.smartcontract import SmartContract
from neo.VM.InteropService import stack_item_to_py
from neocore.UInt160 import UInt160
from neocore.Cryptography.Crypto import Crypto


# Setup the blockchain task queue
class IdentitySmartContract():
    """
    Invoke queue is necessary for handling many concurrent sc invokes.

    Eg. many api calls want to initiate a smart contract methods, they add them
    to this queue, and they get processed as they can (eg. if gas is available)
    """
    smart_contract = None
    contract_hash = None

    wallet_path = None
    wallet_pass = None
    wallet_mutex = None

    tx_unconfirmed = None
    _tx_unconfirmed_loop = None
    wallet = None
    _walletdb_loop = None


    def __init__(self, contract_hash, wallet_path, wallet_pass):

        self.contract_hash = contract_hash
        self.wallet_path = wallet_path
        self.wallet_pass = wallet_pass
        self.wallet_mutex = threading.Lock()

        self.smart_contract = SmartContract(contract_hash)

        self.tx_unconfirmed = set()
        self._tx_unconfirmed_loop = task.LoopingCall(self.update_tx_unconfirmed)
        self._tx_unconfirmed_loop.start(5)

        self.wallet = None

        settings.set_log_smart_contract_events(False)

        # Setup handler for smart contract Runtime.Notify event
        @self.smart_contract.on_notify
        def sc_notify(event):
            """ This method catches Runtime.Notify calls """
            logger.info("sc_notify event: %s", str(event))
            if event.event_payload[0].decode("utf-8") == "transfer":
                address_from = self.bytes_to_address(event.event_payload[1])
                address_to = self.bytes_to_address(event.event_payload[2])
                amount = int.from_bytes(event.event_payload[3], byteorder='big')
                self.transfer("neo", address_from, address_to, amount)

    def bytes_to_address(self, bytes):
        script_hash = UInt160(data=bytes)
        address = Crypto.ToAddress(script_hash)
        return address

    def transfer(self, asset, address_from, address_to, amount):
        logger.info("Transfer %s %s from %s to %s", amount, asset, address_from, address_to)
        try:
            self.open_wallet()
            tx = construct_and_send(None, self.wallet, [asset, address_to, str(amount)], False)
            if tx:
                sent_tx_hash = tx.Hash.ToString()
                logger.info("Transfer success, transaction underway: %s" % sent_tx_hash)
                self.tx_unconfirmed.add(sent_tx_hash)
                return sent_tx_hash
            return False
        finally:
            self.close_wallet()

    def claim_gas(self, usr_adr):
        return self.transfer("gas", "API", usr_adr, 100)

    def test_invoke(self, method_name, *args):
        result = self._invoke_method(False, method_name, *args)
        return result, list(self.tx_unconfirmed)

    def invoke(self, method_name, *args):
        result, tx = self._invoke_method(True, method_name, *args)
        return result, list(self.tx_unconfirmed), tx

    def open_wallet(self):
        """ Open a wallet. Needed for invoking contract methods. """
        assert self.wallet is None
        self.wallet_mutex.acquire()
        self.wallet = UserWallet.Open(self.wallet_path, self.wallet_pass)
        self._walletdb_loop = task.LoopingCall(self.wallet.ProcessBlocks)
        self._walletdb_loop.start(1)

    def close_wallet(self):
        self._walletdb_loop.stop()
        self._walletdb_loop = None
        self.wallet = None
        self.wallet_mutex.release()

    def wallet_has_gas(self):
        # Make sure no tx is in progress and we have GAS
        synced_balances = self.wallet.GetSyncedBalances()
        for balance in synced_balances:
            asset, amount = balance
            logger.info("- balance %s: %s", asset, amount)
            if asset == "NEOGas" and amount > 0:
                return True

        return False

    def find_tx(self, tx_hash):
        _tx, height = Blockchain.Default().GetTransaction(tx_hash)
        if height > -1:
            return True
        return False

    def update_tx_unconfirmed(self):
        for tx_hash in self.tx_unconfirmed:
            found = self.find_tx(tx_hash)
            if found:
                logger.info("Transaction found! %s" % tx_hash)
                self.tx_unconfirmed.remove(tx_hash)
                break

    def _invoke_method(self, send_tx_needed, method_name, *args):
        """ invoke a method of the smart contract """

        logger.info("invoke_method: method_name=%s, args=%s", method_name, args)
        logger.info("Block %s / %s" % (str(Blockchain.Default().Height), str(Blockchain.Default().HeaderHeight)))

        self.open_wallet()

        if not self.wallet:
            raise Exception("Open a wallet before invoking a smart contract method.")

        logger.info("making sure wallet is synced...")
        time.sleep(3)

        # Wait until wallet is synced:
        while True:
            # TODO rebuild wallet ???
            percent_synced = int(100 * self.wallet._current_height / Blockchain.Default().Height)
            if percent_synced > 99:
                break
            logger.info("waiting for wallet sync... height: %s. percent synced: %s" % (self.wallet._current_height, percent_synced))
            time.sleep(5)

        _args = [self.contract_hash, method_name, str(list(args))]

        logger.info("TestInvokeContract args: %s" % _args)
        tx, fee, results, num_ops = TestInvokeContract(self.wallet, _args)
        logger.info("TestInvokeContract fee: %s" % fee)
        logger.info("TestInvokeContract results: %s" % [str(item) for item in results])
        logger.info("TestInvokeContract RESULT: %s ", stack_item_to_py(results[0]))
        logger.info("TestInvokeContract num_ops: %s" % num_ops)
        result = stack_item_to_py(results[0])
        if not tx:
            self.close_wallet()
            raise Exception("TestInvokeContract failed")

        if not send_tx_needed:
            self.close_wallet()
            return result

        logger.info("TestInvokeContract done, calling InvokeContract now...")

        if not self.wallet_has_gas():
            logger.error("Oh no, wallet has no gas!")
            self.close_wallet()
            raise Exception("Wallet has no gas.")

        sent_tx = InvokeContract(self.wallet, tx, fee)

        if sent_tx:
            sent_tx_hash = sent_tx.Hash.ToString()
            logger.info("InvokeContract success, transaction underway: %s" % sent_tx_hash)
            self.tx_unconfirmed.add(sent_tx_hash)
            self.close_wallet()
            return result, sent_tx_hash

        else:
            self.close_wallet()
            raise Exception("InvokeContract failed")
