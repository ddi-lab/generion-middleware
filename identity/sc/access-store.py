"""
Identity Smart Contract
===================================
Testing:

neo> build identity/sc/access-store.py test 0710 05 True False getUserList []
neo> build identity/sc/access-store.py test 0710 05 True False setUserPubKey ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT", "PUB_KEY"]
neo> build identity/sc/access-store.py test 0710 05 True False getUserPubKey ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT"]
neo> build identity/sc/access-store.py test 0710 05 True False getRecordList ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT"]
neo> build identity/sc/access-store.py test 0710 05 True False getRecordIdList ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT"]
neo> build identity/sc/access-store.py test 0710 05 True False createRecord ["AG92fB2ZM7wnRXcxp7sn5CWiNVkJmXYwy6","AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT","DATA_PUB_KEY","DATA_ENCR"]
neo> build identity/sc/access-store.py test 0710 05 True False verifyRecord [1]
neo> build identity/sc/access-store.py test 0710 05 True False getRecord [1]
neo> build identity/sc/access-store.py test 0710 05 True False deleteRecord [1]
neo> build identity/sc/access-store.py test 0710 05 True False getOrderList []
neo> build identity/sc/access-store.py test 0710 05 True False getOrderIdList []
neo> build identity/sc/access-store.py test 0710 05 True False createOrder ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT","1:2:3",2]
neo> build identity/sc/access-store.py test 0710 05 True False getOrder [1]
neo> build identity/sc/access-store.py test 0710 05 True False deleteOrder [1]
neo> build identity/sc/access-store.py test 0710 05 True False purchaseData [1,"03d8a47c4d9c33e552c93195b9b23b81c2372bc36bf15d9ac9b2b5f985bf837282"] --attach-neo=3


Importing:

neo> import contract identity/sc/access-store.avm 0710 05 True False
neo> contract search ...

Using:

neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 setUserPubKey ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT", "PUB_KEY"]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 getUserPubKey ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT"]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 getUserList []
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 getRecordList ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT"]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 getRecordIdList ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT"]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 createRecord ["AG92fB2ZM7wnRXcxp7sn5CWiNVkJmXYwy6","AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT","DATA_PUB_KEY","DATA_ENCR"]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 verifyRecord [1]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 getRecord [1]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 deleteRecord [1]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 getOrderList []
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 getOrderIdList []
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 createOrder ["AYRd6wrG1BXDwbBMrg3nQFD6jH2uEvN4ZT","1:2:3",2]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 getOrder [1]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 deleteOrder [1]
neo> testinvoke 0743b0887b29484a78fc8568c1d146f6c8cd4252 purchaseData [1,"03d8a47c4d9c33e552c93195b9b23b81c2372bc36bf15d9ac9b2b5f985bf837282"] --attach-neo=3

"""
from boa.interop.Neo.Runtime import Log, Notify
from boa.interop.Neo.Runtime import CheckWitness
from boa.interop.Neo.Storage import GetContext, Get, Put, Delete
from boa.interop.Neo.Output import GetScriptHash, GetValue, GetAssetId
from boa.interop.Neo.Action import RegisterAction
from boa.interop.Neo.Transaction import Transaction, GetReferences, GetOutputs,GetUnspentCoins
from boa.interop.System.ExecutionEngine import GetScriptContainer, GetExecutingScriptHash
from boa.builtins import concat, list, range, substr

# Script hash of the contract owner
#OWNER = b'\x04\x00A\xfb4\xd5\xa1\t\xce\xe7\x03\x1b\x7fD4\xc2\xec\xf9\xcd\xf4'  #coz-test-wallet.db3
OWNER = b'#\xba\'\x03\xc52c\xe8\xd6\xe5"\xdc2 39\xdc\xd8\xee\xe9'  # neo-privnet.wallet

# Constants
NEO_ASSET_ID = b'\x9b|\xff\xda\xa6t\xbe\xae\x0f\x93\x0e\xbe`\x85\xaf\x90\x93\xe5\xfeV\xb3J\\"\x0c\xcd\xcfn\xfc3o\xc5'

USR_ADR_LIST_KEY = 'usr_adr_list'
USR_ADR_PUBKEY_PREFIX = 'usr_adr_pk_'

RECORD_ID_LIST_PREFIX = 'ridl_'
RECORD_ID_META_PREFIX = 'ridm_'
RECORD_ID_DATA_PREFIX = 'ridd_'
NEXT_RECORD_ID_KEY = 'next_rid'

ORDER_ID_LIST_PREFIX = 'oidl_'
ORDER_ID_PREFIX = 'orid_'
NEXT_ORDER_ID_KEY = 'next_oid'

# Messages
UNKNOWN_OP = 'unknown operation'
WRONG_ARGS = 'wrong arguments'

# Const values
INITIAL_ID = 1

# Events
DispatchTransferEvent = RegisterAction('transfer', 'from', 'to', 'amount')

def Main(operation, args):
    """
    This is the main entry point for the dApp
    :param operation: the operation to be performed
    :type operation: str
    :param args: an optional list of arguments
    :type args: list
    :return: indicating the successful execution of the dApp
    :rtype: str
    """

    # <<< USER CRUD METHODS >>>
    if operation == 'getUserList':
        if len(args) == 0:
            r = GetUserList()
            return r
        else:
            return WRONG_ARGS
    elif operation == 'setUserPubKey':
        if len(args) == 2:
            usr_adr = args[0]
            pub_key = args[1]
            r = SetUserPubKey(usr_adr, pub_key)
            return r
        else:
            return WRONG_ARGS
    elif operation == 'getUserPubKey':
        if len(args) == 1:
            usr_adr = args[0]
            r = GetUserPubKey(usr_adr)
            return r
        else:
            return WRONG_ARGS

    # <<< DATA RECORD CRUD METHODS >>>
    elif operation == 'getRecordList':
        if len(args) == 1:
            usr_adr = args[0]
            r = GetRecordList(usr_adr)
            return r
        else:
            return WRONG_ARGS

    elif operation == 'getRecordIdList':
        if len(args) == 1:
            usr_adr = args[0]
            r = GetRecordIdList(usr_adr)
            return r
        else:
            return WRONG_ARGS

    elif operation == 'createRecord':
        if len(args) == 4:
            creator_adr = args[0]
            usr_adr = args[1]
            data_pub_key = args[2]
            data_encr = args[3]
            r = InsertRecord(creator_adr, usr_adr, data_pub_key, data_encr)
            return r
        else:
            return WRONG_ARGS

    elif operation == 'verifyRecord':
        if len(args) == 1:
            record_id = args[0]
            r = VerifyRecord(record_id)
            return r
        else:
            return WRONG_ARGS

    if operation == 'getRecord':
        if len(args) == 1:
            record_id = args[0]
            r = GetRecord(record_id)
            return r
        else:
            return WRONG_ARGS

    elif operation == 'deleteRecord':
        if len(args) == 1:
            record_id = args[0]
            r = DeleteRecord(record_id)
            return r
        else:
            return WRONG_ARGS

    # <<< ORDER CRUD METHODS >>>
    elif operation == 'getOrderList':
        if len(args) == 0:
            r = GetOrderList()
            return r
        else:
            return WRONG_ARGS

    elif operation == 'getOrderIdList':
        if len(args) == 0:
            r = GetOrderIdList()
            return r
        else:
            return WRONG_ARGS

    elif operation == 'createOrder':
        if len(args) == 3:
            usr_adr = args[0]
            record_id_list = args[1]
            price = args[2]
            r = InsertOrder(usr_adr, record_id_list, price)
            return r
        else:
            return WRONG_ARGS

    if operation == 'getOrder':
        if len(args) == 1:
            order_id = args[0]
            r = GetOrder(order_id)
            return r
        else:
            return WRONG_ARGS

    elif operation == 'deleteOrder':
        if len(args) == 1:
            order_id = args[0]
            r = DeleteOrder(order_id)
            return r
        else:
            return WRONG_ARGS

    # <<< TRANSFER METHODS >>>
    elif operation == 'purchaseData':
        if len(args) == 2:
            order_id = args[0]
            pub_key = args[1]
            r = PurchaseData(order_id, pub_key)
            return r
        else:
            return WRONG_ARGS


# <<< MAIN METHODS >>>
def GetUserList():
    context = GetContext()
    users_serialized = Get(context, USR_ADR_LIST_KEY)
    if not users_serialized:
        return []
    users = deserialize_bytearray(users_serialized)
    return users


def SetUserPubKey(usr_adr, pub_key):
    if not check_permission(usr_adr):
        Log("Must be owner to set public key")
        return False

    usrpk_key = concat(USR_ADR_PUBKEY_PREFIX, usr_adr)
    context = GetContext()
    Put(context, usrpk_key, pub_key)
    return True


def GetUserPubKey(usr_adr):
    usrpk_key = concat(USR_ADR_PUBKEY_PREFIX, usr_adr)
    context = GetContext()
    pub_key = Get(context, usrpk_key)
    return pub_key


def GetRecordList(usr_adr):
    records_id = GetRecordIdList(usr_adr)
    records = []
    collection_len = len(records_id)
    for i in range(0, collection_len):
        id = records_id[i]
        single_record = GetRecord(id)
        records.append(single_record)
    return records


def GetRecordIdList(usr_adr):
    context = GetContext()
    record_id_list_key = concat(RECORD_ID_LIST_PREFIX, usr_adr)
    records_serialized = Get(context, record_id_list_key)
    if not records_serialized:
        return []
    records_id = deserialize_bytearray(records_serialized)
    return records_id


def InsertRecord(creator_adr, usr_adr, data_pub_key, data_encr):
    if not check_permission(creator_adr):
        Log("Wrong creator_adr")
        return False

    users = GetUserList()
    found = False
    for user in users:
        if user == usr_adr:
            found = True
    if not found:
        users.append(usr_adr)
        users_serialized = serialize_array(users)
        context = GetContext()
        Put(context, USR_ADR_LIST_KEY, users_serialized)
        msg = concat("New user: ", usr_adr)
        Log(msg)

    context = GetContext()
    record_meta = [usr_adr, data_pub_key, creator_adr, False]
    record_meta_serialized = serialize_array(record_meta)
    record_id = next_id(NEXT_RECORD_ID_KEY)
    record_meta_key = concat(RECORD_ID_META_PREFIX, record_id)
    record_data_key = concat(RECORD_ID_DATA_PREFIX, record_id)
    Put(context, record_meta_key, record_meta_serialized)
    Put(context, record_data_key, data_encr)

    records_id = GetRecordIdList(usr_adr)
    records_id.append(record_id)
    records_serialized = serialize_array(records_id)
    record_id_list_key = concat(RECORD_ID_LIST_PREFIX, usr_adr)
    Put(context, record_id_list_key, records_serialized)

    msg = concat("New record: ", record_id)
    Notify(msg)
    return record_id


def VerifyRecord(record_id):
    context = GetContext()
    record_meta_key = concat(RECORD_ID_META_PREFIX, record_id)
    record_meta_serialized = Get(context, record_meta_key)
    if not record_meta_serialized:
        Log("Record doesn't exist")
        return False

    record_meta = deserialize_bytearray(record_meta_serialized)
    usr_adr = record_meta[0]
    pub_key = record_meta[1]
    creator_adr = record_meta[2]
    if not check_permission(usr_adr):
        Log("Must be owner to verify a record")
        return False

    context = GetContext()
    record_meta_upd = [usr_adr, pub_key, creator_adr, True]
    record_meta_upd_serialized = serialize_array(record_meta_upd)
    record_meta_key = concat(RECORD_ID_META_PREFIX, record_id)
    Put(context, record_meta_key, record_meta_upd_serialized)
    return True


def GetRecord(record_id):
    context = GetContext()
    record_meta_key = concat(RECORD_ID_META_PREFIX, record_id)
    record_meta_serialized = Get(context, record_meta_key)
    if not record_meta_serialized:
        Log("Record doesn't exist")
        return False

    record_meta = deserialize_bytearray(record_meta_serialized)
    usr_adr = record_meta[0]
    pub_key = record_meta[1]
    creator_adr = record_meta[2]
    is_verified = record_meta[3]
    record_data_key = concat(RECORD_ID_DATA_PREFIX, record_id)
    record_data = Get(context, record_data_key)
    record = [usr_adr, pub_key, creator_adr, is_verified, record_data]
    return record


def DeleteRecord(record_id):
    record = GetRecord(record_id)
    if not record:
        Log("Record doesn't exist")
        return False

    usr_adr = record[0]
    if not check_permission(usr_adr):
        Log("Must be owner to delete a record")
        return False

    records_id = GetRecordIdList(usr_adr)
    found = False
    i = 0
    while i < len(records_id):
        if records_id[i] == record_id:
            found = True
            records_id.remove(i)  # pop by index
            i = len(records_id) + 1  # break
        i += 1
    if found:
        records_serialized = serialize_array(records_id)
        record_id_list_key = concat(RECORD_ID_LIST_PREFIX, usr_adr)
        context = GetContext()
        Put(context, record_id_list_key, records_serialized)

        record_key = concat(RECORD_ID_META_PREFIX, record_id)
        Delete(context, record_key)
        return True
    else:
        Log("Record doesn't exist")
        return False


def GetOrderList():
    orders_id = GetOrderIdList()
    orders = []
    collection_len = len(orders_id)
    for i in range(0, collection_len):
        id = orders_id[i]
        single_order = GetOrder(id)
        orders.append(single_order)
    return orders


def GetOrderIdList():
    context = GetContext()
    orders_serialized = Get(context, ORDER_ID_LIST_PREFIX)
    if not orders_serialized:
        return []
    orders_id = deserialize_bytearray(orders_serialized)
    return orders_id


def InsertOrder(usr_adr, record_id_list_str, price):
    if not check_permission(usr_adr):
        Log("Must be owner to create an order")
        return False

    if len(record_id_list_str) <= 0:
        Log("Empty record_id_list")
        return False

    # record_incorrect = False
    # for record_id in record_id_list:
    #     record = GetRecord(record_id)
    #     if (not record) or (record[0] != usr_adr):
    #         record_incorrect = True
    # if record_incorrect:
    #     Log("Incorrect record_id_list")
    #     return False

    if price <= 0:
        Log("Price should be positive")
        return False

    context = GetContext()
    order_data = [usr_adr, record_id_list_str, price, '']
    order_data_serialized = serialize_array(order_data)
    order_id = next_id(NEXT_ORDER_ID_KEY)
    order_key = concat(ORDER_ID_PREFIX, order_id)
    Put(context, order_key, order_data_serialized)

    orders_id = GetOrderIdList()
    orders_id.append(order_id)
    orders_serialized = serialize_array(orders_id)
    Put(context, ORDER_ID_LIST_PREFIX, orders_serialized)

    msg = concat("New order: ", order_id)
    Notify(msg)
    return order_id


def GetOrder(order_id):
    context = GetContext()
    order_key = concat(ORDER_ID_PREFIX, order_id)
    order_serialized = Get(context, order_key)
    if not order_serialized:
        Log("Order doesn't exist")
        return False
    order = deserialize_bytearray(order_serialized)
    return order


def DeleteOrder(order_id):
    order = GetOrder(order_id)
    if not order:
        Log("Order doesn't exist")
        return False

    usr_adr = order[0]
    if not check_permission(usr_adr):
        Log("Must be owner to delete an order")
        return False

    orders_id = GetOrderIdList()
    found = False
    i = 0
    while i < len(orders_id):
        if orders_id[i] == order_id:
            found = True
            orders_id.remove(i)  # pop by index
            i = len(orders_id) + 1  # break
        i += 1
    if found:

        orders_serialized = serialize_array(orders_id)
        context = GetContext()
        Put(context, ORDER_ID_LIST_PREFIX, orders_serialized)

        order_key = concat(ORDER_ID_PREFIX, order_id)
        Delete(context, order_key)
        return True
    else:
        Log("Order doesn't exist")
        return False


def PurchaseData(order_id, pub_key):
    order = GetOrder(order_id)

    if not order:
        Log("Order doesn't exist")
        return False

    if order[3] != '':
        Log("Already purchased")
        return False

    if pub_key == '':
        Log("Empty public key")
        return False

    tx = GetScriptContainer()
    references = tx.References
    if len(references) < 1:
        Log("No NEO attached")
        return False

    receiver_addr = GetExecutingScriptHash()
    received_NEO = 0
    for output in tx.Outputs:
        if output.ScriptHash == receiver_addr and output.AssetId == NEO_ASSET_ID:
            received_NEO += output.Value
    received_NEO /= 100000000

    Log("Received total NEO:")
    Log(received_NEO)
    price = order[2]
    if received_NEO < price:
        Log("Not enough NEO")
        return False

    Log("Rewriting order to new public key")
    context = GetContext()
    order[3] = pub_key
    order_data_serialized = serialize_array(order)
    order_key = concat(ORDER_ID_PREFIX, order_id)
    Put(context, order_key, order_data_serialized)

    Log("Payment to user")
    reference = references[0]
    sender = GetScriptHash(reference)
    usr_adr = order[0]
    DispatchTransferEvent(sender, usr_adr, price)
    return True


# <<< AUXILIARY METHODS >>>
def next_id(key):
    context = GetContext()
    id = Get(context, key)
    if not id:
        Log("Next id doesn't exist yet.")
        id = INITIAL_ID
    next_value = id + 1
    Put(context, key, next_value)
    return id


def check_permission(usr_adr):
    if CheckWitness(OWNER):
        return True
    if CheckWitness(usr_adr):
        return True
    return False


# <<< UTILS >>>
# def str_to_list(record_id_list_raw):
#     # TODO implement: "1:2:3" -> [1,2,3]
#     return record_id_list_raw


def deserialize_bytearray(data):

    # ok this is weird.  if you remove this print statement, it stops working :/
    print("deserializing data...")

    # get length of length
    collection_length_length = substr(data, 0, 1)

    # get length of collection
    collection_len = substr(data, 1, collection_length_length)

    # create a new collection
    new_collection = list(length=collection_len)

    # calculate offset
    offset = 1 + collection_length_length

    # trim the length data
    newdata = data[offset:]

    for i in range(0, collection_len):

        # get the data length length
        itemlen_len = substr(newdata, 0, 1)

        # get the length of the data
        item_len = substr(newdata, 1, itemlen_len)

        start = 1 + itemlen_len
        end = start + item_len

        # get the data
        item = substr(newdata, start, item_len)

        # store it in collection
        new_collection[i] = item

        # trim the data
        newdata = newdata[end:]

    return new_collection


def serialize_array(items):

    # serialize the length of the list
    itemlength = serialize_var_length_item(items)

    output = itemlength

    # now go through and append all your stuff
    for item in items:

        # get the variable length of the item
        # to be serialized
        itemlen = serialize_var_length_item(item)

        # add that indicator
        output = concat(output, itemlen)

        # now add the item
        output = concat(output, item)

    # return the stuff
    return output


def serialize_var_length_item(item):

    # get the length of your stuff
    stuff_len = len(item)

    # now we need to know how many bytes the length of the array
    # will take to store

    # this is one byte
    if stuff_len <= 255:
        byte_len = b'\x01'
    # two byte
    elif stuff_len <= 65535:
        byte_len = b'\x02'
    # hopefully 4 byte
    else:
        byte_len = b'\x04'

    out = concat(byte_len, stuff_len)

    return out