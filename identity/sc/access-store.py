"""
Identity Smart Contract
===================================
Testing:

neo> build identity/sc/access-store.py test 0710 05 True False createRecord ["ABC","data_store_adr","doc_pub","doc_pub"]
neo> build identity/sc/access-store.py test 0710 05 True False getRecord ["ABC"]
neo> build identity/sc/access-store.py test 0710 05 True False deleteRecord ["ABC"]
neo> build identity/sc/access-store.py test 0710 05 True False isRecord ["ABC"]
neo> build identity/sc/access-store.py test 0710 05 True False getRecordCount []
neo> build identity/sc/access-store.py test 0710 05 True False getRecordList []

Importing:

neo> import contract identity/sc/access-store.avm 0710 05 True False
neo> contract search ...

Using:

neo> testinvoke d63a0b437a16579288361ccb593570e5c5f71149 createRecord ["ABC","data_store_adr","doc_pub","doc_pub"]
neo> testinvoke d63a0b437a16579288361ccb593570e5c5f71149 getRecord ["ABC"]
neo> testinvoke d63a0b437a16579288361ccb593570e5c5f71149 deleteRecord ["ABC"]
neo> testinvoke d63a0b437a16579288361ccb593570e5c5f71149 isRecord ["ABC"]
neo> testinvoke d63a0b437a16579288361ccb593570e5c5f71149 getRecordCount []
neo> testinvoke d63a0b437a16579288361ccb593570e5c5f71149 getRecordList []

"""
from boa.blockchain.vm.Neo.Runtime import Log, Notify
from boa.blockchain.vm.Neo.Runtime import CheckWitness
from boa.blockchain.vm.Neo.Storage import GetContext, Get, Put, Delete
from boa.code.builtins import concat, list, range, take, substr

# Script hash of the token owner
OWNER = b'\xb6\xa5\xad\xa9\xb9[\xf9*\x10\xc34\x93\xd4V\xb8=\x1a\x91\x9f\xed'

# Constants
USR_ADR_LIST = 'usr_adr_list'
USR_ADR_PREFIX = 'usr_adr'

# Messages
UNKNOWN_OP = 'unknown operation'
WRONG_ARGS = 'wrong arguments'


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

    # <<< RECORD CRUD METHODS >>>
    if operation == 'createRecord':
        if len(args) == 4:
            usr_adr = args[0]
            data_store_adr = args[1]
            doc_pub = args[2]
            doc_key = args[3]
            r = InsertRecord(usr_adr, data_store_adr, doc_pub, doc_key)
            return r
        else:
            return WRONG_ARGS

    if operation == 'getRecord':
        if len(args) == 1:
            usr_adr = args[0]
            r = GetRecord(usr_adr)
            return r
        else:
            return WRONG_ARGS

    elif operation == 'deleteRecord':
        if len(args) == 1:
            usr_adr = args[0]
            r = DeleteRecord(usr_adr)
            return r
        else:
            return WRONG_ARGS

    elif operation == 'isRecord':
        if len(args) == 1:
            usr_adr = args[0]
            r = IsRecord(usr_adr)
            return r
        else:
            return WRONG_ARGS

    elif operation == 'getRecordCount':
        if len(args) == 0:
            r = GetRecordCount()
            return r
        else:
            return WRONG_ARGS

    elif operation == 'getRecordList':
        if len(args) == 0:
            r = GetRecordList()
            return r
        else:
            return WRONG_ARGS


# <<< RECORD CRUD METHODS >>>

def InsertRecord(usr_adr, data_store_adr, doc_pub, doc_key):
    if not CheckWitness(OWNER):
        Log("Must be owner to insert a record")
        return False
    if IsRecord(usr_adr):
        Log("Record already exists")
        return False
    context = GetContext()

    records = GetRecordList()
    records.append(usr_adr)
    records_serialized = serialize_array(records)
    Put(context, USR_ADR_LIST, records_serialized)

    record_data = [data_store_adr, doc_pub, doc_key]
    stored_address = concat(USR_ADR_PREFIX, usr_adr)
    record_data_serialized = serialize_array(record_data)
    Put(context, stored_address, record_data_serialized)
    msg = concat("New record: ", usr_adr)
    Notify(msg)
    return True


def GetRecord(usr_adr):
    context = GetContext()
    stored_address = concat(USR_ADR_PREFIX, usr_adr)
    record_serialized = Get(context, stored_address)
    if not record_serialized:
        Log("Record doesn't exist")
        return False
    record = deserialize_bytearray(record_serialized)
    return record


def DeleteRecord(usr_adr):
    if not CheckWitness(OWNER):
        Log("Must be owner to insert a record")
        return False
    if not IsRecord(usr_adr):
        Log("Record doesn't exist")
        return False
    records = GetRecordList()
    i = 0
    while i < len(records):
        if records[i] == usr_adr:
            records.remove(i)
        i += 1
    records_serialized = serialize_array(records)
    context = GetContext()
    Put(context, USR_ADR_LIST, records_serialized)
    stored_address = concat(USR_ADR_PREFIX, usr_adr)
    Put(context, stored_address, '')
    return True


def IsRecord(usr_adr):
    context = GetContext()
    stored_address = concat(USR_ADR_PREFIX, usr_adr)
    if not Get(context, stored_address):
        return False
    return True


def GetRecordList():
    context = GetContext()
    records_serialized = Get(context, USR_ADR_LIST)
    if not records_serialized:
        return []
    records = deserialize_bytearray(records_serialized)
    return records


def GetRecordCount():
    records = GetRecordList()
    length = len(records)
    return length


# <<< UTILS >>>

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