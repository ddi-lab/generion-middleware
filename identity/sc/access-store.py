"""
Identity Smart Contract
===================================
Testing:

neo> build identity/sc/access-store.py test 0710 05 True False getRecord [1]
neo> build identity/sc/access-store.py test 0710 05 True False getUserList []
neo> build identity/sc/access-store.py test 0710 05 True False getRecordList ["ABC"]
neo> build identity/sc/access-store.py test 0710 05 True False getRecordIdList ["ABC"]
neo> build identity/sc/access-store.py test 0710 05 True False createRecord ["ABC","DATA_PUB_KEY","DATA_ENCR"]
neo> build identity/sc/access-store.py test 0710 05 True False deleteRecord ["ABC",1]


Importing:

neo> import contract identity/sc/access-store.avm 0710 05 True False
neo> contract search ...

Using:

neo> testinvoke b3bee941f4e5b0559384fe1528d314df9a52cd4d getRecord [1]
neo> testinvoke b3bee941f4e5b0559384fe1528d314df9a52cd4d getUserList []
neo> testinvoke b3bee941f4e5b0559384fe1528d314df9a52cd4d getRecordList ["ABC"]
neo> testinvoke b3bee941f4e5b0559384fe1528d314df9a52cd4d getRecordIdList ["ABC"]
neo> testinvoke b3bee941f4e5b0559384fe1528d314df9a52cd4d createRecord ["ABC","DATA_PUB_KEY","DATA_ENCR"]
neo> testinvoke b3bee941f4e5b0559384fe1528d314df9a52cd4d deleteRecord ["ABC",1]


"""
from boa.blockchain.vm.Neo.Runtime import Log, Notify
from boa.blockchain.vm.Neo.Runtime import CheckWitness
from boa.blockchain.vm.Neo.Storage import GetContext, Get, Put, Delete
from boa.code.builtins import concat, list, range, take, substr

# Script hash of the token owner
OWNER = b'\x04\x00A\xfb4\xd5\xa1\t\xce\xe7\x03\x1b\x7fD4\xc2\xec\xf9\xcd\xf4'

# Constants
USR_ADR_LIST = 'usr_adr_list'
RECORD_ID_LIST_PREFIX = 'rcd_id_list_'
RECORD_ID_PREFIX = 'rid_'
NEXT_ID_KEY = 'next_id'

# Messages
UNKNOWN_OP = 'unknown operation'
WRONG_ARGS = 'wrong arguments'

# Const values
INITIAL_ID = 1
SOME_VALUE = '?'


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
        if len(args) == 3:
            usr_adr = args[0]
            data_pub_key = args[1]
            data_encr = args[2]
            r = InsertRecord(usr_adr, data_pub_key, data_encr)
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
        if len(args) == 2:
            usr_adr = args[0]
            record_id = args[1]
            r = DeleteRecord(usr_adr, record_id)
            return r
        else:
            return WRONG_ARGS


# <<< MAIN METHODS >>>
def GetUserList():
    context = GetContext()
    users_serialized = Get(context, USR_ADR_LIST)
    if not users_serialized:
        return []
    users = deserialize_bytearray(users_serialized)
    return users


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


def InsertRecord(usr_adr, data_pub_key, data_encr):
    if not CheckWitness(OWNER):
        Log("Must be owner to insert a record")
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
        Put(context, USR_ADR_LIST, users_serialized)
        msg = concat("New user: ", usr_adr)
        Notify(msg)

    context = GetContext()
    record_data = [usr_adr, data_pub_key, data_encr]
    record_data_serialized = serialize_array(record_data)
    record_id = next_id()
    record_key = concat(RECORD_ID_PREFIX, record_id)
    Put(context, record_key, record_data_serialized)

    records_id = GetRecordIdList(usr_adr)
    records_id.append(record_id)
    records_serialized = serialize_array(records_id)
    record_id_list_key = concat(RECORD_ID_LIST_PREFIX, usr_adr)
    Put(context, record_id_list_key, records_serialized)

    msg = concat("New record: ", record_id)
    Notify(msg)
    return True


def GetRecord(record_id):
    context = GetContext()
    record_key = concat(RECORD_ID_PREFIX, record_id)
    record_serialized = Get(context, record_key)
    if not record_serialized:
        Log("Record doesn't exist")
        return False
    record = deserialize_bytearray(record_serialized)
    return record


def DeleteRecord(usr_adr, record_id):
    if not CheckWitness(OWNER):
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

        record_key = concat(RECORD_ID_PREFIX, record_id)
        Put(context, record_key, '')
        return True
    else:
        Log("Record doesn't exist")
        return False


# <<< AUXILIARY METHODS >>>
def next_id():
    context = GetContext()
    id = Get(context, NEXT_ID_KEY)
    if not id:
        Log("Next id doesn't exist yet.")
        id = INITIAL_ID
    next_value = id + 1
    Put(context, NEXT_ID_KEY, next_value)
    return id


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