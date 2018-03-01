import time
import threading

from logzero import logger
from twisted.internet import task

from neo.Implementations.Wallets.peewee.UserWallet import UserWallet
from neo.Prompt.Commands.Invoke import InvokeContract, TestInvokeContract, test_invoke
from neo.Prompt.Commands.Send import construct_and_send
from neo.Prompt.Utils import parse_param
from neo.Settings import settings
from neo.Core.Blockchain import Blockchain
from neo.Core.TX.Transaction import TransactionOutput
from neo.VM.InteropService import stack_item_to_py
from neo.VM.ScriptBuilder import ScriptBuilder
from neo.Blockchain import GetBlockchain
from neo.contrib.smartcontract import SmartContract
from neocore.Fixed8 import Fixed8

from identity.utils import bytes_to_address


# Setup the blockchain processor
class IdentitySmartContract():
    """
    wallet_mutex is necessary for handling many concurrent sc invokes.

    Eg. many api calls want to initiate a smart contract methods, they are locked
    until the last one finished, and they get processed as they can (eg. if gas is available)
    """
    smart_contract = None
    contract_hash = None

    wallet_path = None
    wallet_pass = None
    wallet_mutex = None

    tx_unconfirmed = None
    tx_failed = None
    _tx_unconfirmed_loop = None
    wallet = None
    _walletdb_loop = None

    def __init__(self, contract_hash, wallet_path, wallet_pass):

        self.contract_hash = contract_hash
        self.wallet_path = wallet_path
        self.wallet_pass = wallet_pass
        self.wallet_mutex = threading.Lock()

        self.smart_contract = SmartContract(contract_hash)

        self.tx_unconfirmed = dict()
        self.tx_failed = []
        self._tx_unconfirmed_loop = task.LoopingCall(self.update_tx_unconfirmed)
        self._tx_unconfirmed_loop.start(5)

        self.wallet = None

        settings.set_log_smart_contract_events(False)

        # Setup handler for smart contract Runtime.Notify event
        @self.smart_contract.on_notify
        def sc_notify(event):
            """ This method catches Runtime.Notify calls """
            logger.info("sc_notify event: %s", str(event))
            if not event.test_mode and event.event_payload[0].decode("utf-8") == "transfer":
                address_from = bytes_to_address(event.event_payload[1])
                address_to = bytes_to_address(event.event_payload[2])
                amount = int.from_bytes(event.event_payload[3], byteorder='little')
                self.transfer("neo", address_from, address_to, amount)

    def transfer(self, asset, address_from, address_to, amount):
        logger.info("Transfer %s %s from %s to %s", amount, asset, address_from, address_to)
        try:
            self.open_wallet()
            self.sync_wallet(10)
            tx = construct_and_send(None, self.wallet, [asset, address_to, str(amount)], False)
            if tx:
                sent_tx_hash = tx.Hash.ToString()
                logger.info("Transfer success, transaction underway: %s" % sent_tx_hash)
                self.tx_unconfirmed[sent_tx_hash] = 0
                return sent_tx_hash
            return False
        except Exception as e:
            logger.info("Transfer failed: %s" % str(e))
        finally:
            self.close_wallet()

    def claim_gas(self, usr_adr):
        return self.transfer("gas", "API", usr_adr, 100)

    def invoke_single(self, method_name, args, need_transaction=False, amount_neo=None):
        results, tx_hash = self._invoke_method([(method_name, args)], need_transaction, amount_neo)
        return results[0], list(self.tx_unconfirmed.keys()), self.tx_failed, tx_hash

    def invoke_multi(self, invoke_list, need_transaction=False, amount_neo=None):
        results, tx_hash = self._invoke_method(invoke_list, need_transaction, amount_neo)
        return results, list(self.tx_unconfirmed.keys()), self.tx_failed, tx_hash

    def open_wallet(self):
        """ Open a wallet. Needed for invoking contract methods. """
        assert self.wallet is None
        self.wallet_mutex.acquire()
        self.wallet = UserWallet.Open(self.wallet_path, self.wallet_pass)
        self._walletdb_loop = task.LoopingCall(self.wallet.ProcessBlocks)
        self._walletdb_loop.start(1)

    def close_wallet(self):
        if self.wallet is not None:
            self._walletdb_loop.stop()
            self._walletdb_loop = None
            self.wallet = None
            self.wallet_mutex.release()

    def reopen_wallet(self):
        self._walletdb_loop.stop()
        self.wallet = UserWallet.Open(self.wallet_path, self.wallet_pass)
        self._walletdb_loop = task.LoopingCall(self.wallet.ProcessBlocks)
        self._walletdb_loop.start(1)

    def sync_wallet(self, attempts):
        percent_synced = 0
        wallet_synced = False
        for i in range(0, attempts):
            percent_synced = int(100 * self.wallet._current_height / Blockchain.Default().Height)
            if percent_synced > 99:
                wallet_synced = True
                break
            logger.info("waiting for wallet sync... height: %s. percent synced: %s" % (
            self.wallet._current_height, percent_synced))
            time.sleep(5)
            self.reopen_wallet()
        if not wallet_synced:
            raise Exception("Wallet is not synced yet (%s/100). Try again later." % percent_synced)

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
        for (tx_hash, time_passed) in self.tx_unconfirmed.items():
            found = self.find_tx(tx_hash)
            if found:
                logger.info("Transaction found! %s" % tx_hash)
                self.tx_unconfirmed.pop(tx_hash)
                break
            time_passed += 5
            if time_passed > 120:  # wait 2 minutes
                logger.info("Transaction failed :( %s" % tx_hash)
                self.tx_unconfirmed.pop(tx_hash)
                self.tx_failed.append(tx_hash)
                break
            else:
                self.tx_unconfirmed[tx_hash] = time_passed

    def _invoke_method(self, invoke_list, send_tx_needed, neo_to_attach=None):
        """ invoke a method of the smart contract """

        logger.info("invoke_method: %s", str(invoke_list))
        logger.info("Block %s / %s" % (str(Blockchain.Default().Height), str(Blockchain.Default().HeaderHeight)))

        try:
            self.open_wallet()

            if not self.wallet:
                raise Exception("Open a wallet before invoking a smart contract method.")

            logger.info("making sure wallet is synced...")
            time.sleep(3)

            # Wait until wallet is synced:
            self.sync_wallet(5)

            # access contract
            BC = GetBlockchain()
            contract = BC.GetContract(self.contract_hash)
            if not contract:
                raise Exception("Contract %s not found" % self.contract_hash)

            # process attachments
            outputs = []
            if neo_to_attach:
                value = Fixed8.TryParse(int(neo_to_attach))
                output = TransactionOutput(AssetId=Blockchain.SystemShare().Hash,
                                           Value=value,
                                           script_hash=contract.Code.ScriptHash(),
                                           )
                outputs.append(output)

            # construct script
            sb = ScriptBuilder()
            for index, (method, args) in enumerate(invoke_list):
                params = parse_param(str(args))
                sb.EmitAppCallWithOperationAndArgs(contract.Code.ScriptHash(), method, params)
                logger.info("TestInvokeContract %s method: %s" % (str(index), str(method)))
                logger.info("TestInvokeContract %s args: %s" % (str(index), str(params)))

            # make testinvoke
            tx, fee, results, num_ops = test_invoke(sb.ToArray(), self.wallet, outputs)
            if not tx:
                raise Exception("TestInvokeContract failed")

            logger.info("TestInvokeContract fee: %s" % fee)
            logger.info("TestInvokeContract results: %s ", [stack_item_to_py(item) for item in results])
            logger.info("TestInvokeContract num_ops: %s" % num_ops)
            results = [stack_item_to_py(item) for item in results]

            if(len(results) == 1 and results[0] == b'\x00'):
                raise Exception("TestInvokeContract returned False")

            if not send_tx_needed:
                self.close_wallet()
                return results, None

            logger.info("TestInvokeContract done, calling InvokeContract now...")

            if not self.wallet_has_gas():
                logger.error("Oh no, wallet has no gas!")
                logger.info(self.wallet.GetSyncedBalances())
                raise Exception("Wallet has no gas.")

            sent_tx = InvokeContract(self.wallet, tx, fee)

            if sent_tx:
                sent_tx_hash = sent_tx.Hash.ToString()
                logger.info("InvokeContract success, transaction underway: %s" % sent_tx_hash)
                self.tx_unconfirmed[sent_tx_hash] = 0
                self.close_wallet()
                return results, sent_tx_hash

            else:
                raise Exception("InvokeContract failed")
        except:
            self.close_wallet()
            raise
