<p align="center">
  <img
    src="https://avatars2.githubusercontent.com/u/36809299?s=200&v=4"
    width="125px;">
</p>

<h1 align="center">Generion</h1>

### 1.	What is Generion?

Generion is blockchain-based, decentralized infrastructure for safe and anonymous storing, using and sharing personal data. The current MVP is aimed to healthcare domain. However, the architecture can be used in any sphere that accumulates and operates user’s personal information.

### 2.	Current problems

The majority of healthcare organizations have electronic databases with patient’s treatment history, but they are hardly ever synchronized with each other. Besides of the high level of bureaucracy in processing and storing medical data it can lead to far more serious problems.
According to the National Center for Health Statistics, medical error is the third leading cause of death in the United States after heart attack and cancer [[1]](https://hub.jhu.edu/2016/05/03/medical-errors-third-leading-cause-of-death/).
Thousands of lethal cases were caused by giving the patients wrong treatment after going from one hospital to another without learning patient's treatment history and allergic reactions. 

Another big issue in the field is security. During the last few years we have seen numerous cyber attacks and breaches of medical databases [[2]](http://www.healthcareitnews.com/slideshow/biggest-healthcare-breaches-2017-so-far?page=1).

### 3.	Solution

By using blockchain we can facilitate a secure way to medical records storing, sensitive data protection, and giving patients control over their personal information with just using the mobile app. Patients will be able to share their data to any healthcare organization they trust without asking their local clinic to send the data by mail. 
This ensures no one can rewrite the patient’s health record after one was created. 

Electronic health record market is very wide, it mostly covered by the interest of research and statistic purposes. Thousands of pharmacy sponsors all around the word are seeking the candidates for clinical trials.
Decentralized infrastructure will facilitate the aggregation process, that can automatically compile verified statistics and trial’s candidate selections, so medical institutions will not have to put so much effort to collect the info from scattered databases.

The mobile app is the first step in facilitating patients’ ability to monetize their data by having direct offers from interested parties.
Data sellers and buyers can execute smart contracts and transfer the specified data directly. Identity of the patient is never revealed to the data buyer without the patient’s agreement. As a result, buyers get accurate data from the direct source. 

### 4.	Technical

- [SmartContract](https://github.com/ddi-lab/generion-middleware/blob/master/identity/sc/access-store.py). Written in python. Compiled with neo-boa 0.2.2

- [Middleware](https://github.com/ddi-lab/generion-middleware/blob/master/identity/api.py). Written in python. Based on neo-python of dev branch version 0.4.7

- [DataSource](https://github.com/ddi-lab/generion-datasource). Written on Java + Cassandra

- [Mobile Application](https://github.com/ddi-lab/generion-mobileclient). [Youtube demo on COZ testnet](https://youtu.be/srqRs5rSh3k)

### 5.	 Smart – contract

The smart contract stores following records: {**usr_adr** (user address), **data_pub_key** (public key, with which data is encrypted), **data_encr** (the encrypted data itself, including the *data store address*, the *address of the document* in this store, and the *private key* with which you can decrypt it document)}.

Access to read records is available to all users, which allows you to track the history of changes and ensures transparency of ongoing operations. However, each user has *CREATE / DELETE* access only for his records, which guarantees the integrity of the data. Confidentiality is maintained by cryptography with public key, it is assumed that each user has a pair of keys: private and public. The public key encrypts the data in such a way that only he can decrypt the data, possessing a private key.

There is a possibility to sell data. To do this person can leave a request containing a list of records that he wants to sell, indicating at the same time the reward that he wants to receive. The party interested in purchasing the data can track the orders that are relevant for him, and buy the actual information by sending a transaction to blockchain with a token, containing a unique application identifier and a public key to which the data stored in the record that should be encrypted. The information about all the transactions carried out is stored in blockchain and is completely transparent to all. At the moment data sharing is implemented like a data purchase for 0 tokens, it will be reconstructed into a standalone mechanism in the nearest future.


### 6.	API 

- `getUserList []`	= Get list of all users having their records
- `getRecordList [usr_adr]` = Get list of the contents of all records of the specific user
- `getRecordIdList [usr_adr]` = Get list of the ids of all records of the specific user
- `createRecord [usr_adr, data_pub_key, data_encr]` = Create a new record (access restricted)
- `getRecord [record_id]` = Get the specific record
- `deleteRecord [record_id]` = Delete the specific record (access restricted)
- `getOrderList []` = Get list of contents of all orders in the system
- `getOrderIdList []` = Get list of ids of all orders in the system
- `createOrder [usr_adr, record_id_list, price]` = Create a new order (access restricted)
- `getOrder [order_id]` = Get the specific order)
- `deleteOrder [order_id]` = Delete the specific order (access restricted)
- `purchaseData [order_id, pub_key] –attach-neo={}` = Acquire the specific order and attach neo tokens

### 7.	Future

Our vision for this project is to become self-sustaining global network to achieve flawless transparency and independency.  

### 8.	Instructions

1. Install dependencies. Follow instructions from [neo-python](https://github.com/CityOfZion/neo-python)
2. Open CLI
```
python prompt.py -c protocol.coz.json
```
3. Open wallet, do wallet rebuild and wait until 100% synchronization
```
neo> open wallet ./identity-wallets/coz-test-wallet.db3
neo> wallet rebuild
```
4. You may invoke SmartContract methods from inside CLI
```
neo> testinvoke 99f7a7b998b8b5c792a1572d2f0caa250f17c7e8 getUserList []
```  
3. You can also run middleware to use REST API
``` 
python identity/api.py
```
