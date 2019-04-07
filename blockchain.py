import hashlib
import json
import sys
import requests
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from flask import Flask, jsonify, request, render_template

from firebase import firebase


class Blockchain(object):
    global firebase
    global node_identifier
    DEFAULT_COIN = 100

    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = [
            '127.0.0.1:8000',
            '127.0.0.1:8001',
            '127.0.0.1:8002'
        ]
        self.pending_transactions = []
        self.public_key = str(uuid4()).replace('-', '')
        self.private_key = str(uuid4()).replace('-', '')
        self.balance = self.DEFAULT_COIN
        # create genesis block
        self.new_block(previous_hash=1, proof=1)

    def register_node(self, address):
        """
        Add a new block to the list of nodes

        :param address: <str> Address of node
        :return: None
        """
        parsed_url = urlparse(address)
        self.nodes.append(parsed_url.netloc)

    def valid_chain(self, chain):
        """
        Deteermine given chain of blocks valid or nt
        :param chain: <list> A Blockchain
        :return: <bool> True if valid, False if not
        """
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            print("{}".format(last_block))
            print("{}".format(block))
            print("\n----------\n")
            # Check if hases are correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that PoW is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            last_block = block
            current_index += 1
        return True

    def resolve_conflicts(self):
        """
        This is our consensus Algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.

        :return: <bool> True if our chain was replaced, False if not replaced
        """
        neighbours = self.nodes
        new_chain = None

        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            if node == request.host:
                continue
            response = requests.get("http://{}/chains".format(node))
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True
        return False

    def new_block(self, proof, previous_hash):
        """
        creates a new block and add to chain
        :param proof:<int> proof given by PoW algo
        :param previous_hash: (Optional) <str> Hash of previous Block
        :return: <dict> new block
        """
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }

        # reset current list of transactions
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, reciever, amount):
        """
        Adds new transaction to list of transaction
        :param sender: <str> Address of sender
        :param reciever: <str> Addred of reciever
        :param amount: <int> Amount
        :return: <int> The index of the block that will held transaction
        """
        """
        self.current_transactions.append({
            'sender': sender,
            'reciever': reciever,
            'amount': amount,
        })
        """
        # self.resolve_conflicts()
        transaction_dict = {
            'sender': sender,
            'reciever': reciever,
            'amount': amount,
        }
        firebase.post("/pending_transactions", transaction_dict)
        return self.last_block['index'] + 1

    def get_balance(self):
        # default balance
        self.balance = self.DEFAULT_COIN
        for block in self.chain:
            for transaction in block['transactions']:
                if transaction['sender'] == self.public_key:
                    self.balance -= int(transaction['amount'])

                if transaction['reciever'] == self.public_key:
                    self.balance += int(transaction['amount'])

        return self.balance

    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a block
        :param block: Block
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        proof = 0
        while self.valid_proof(last_proof, proof) is not True:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Validates the proof: Does hash(last_proof, proof) has 4 leading zero
        """
        guess = ("{}{}".format(last_proof, proof)).encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def get_pending_transactions(self):
        return self.current_transactions

# connecting to firebase
firebase = firebase.FirebaseApplication('https://py-chain.firebaseio.com', None)

# Instantiate our Node
app = Flask(__name__, static_url_path='')

# Generate global unique identifier
node_identifier = str(uuid4()).replace('-', '')

# Instantiate Blockchain
blockchain = Blockchain()


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.register_node(node)
    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        response = {
            "message": "our chain was replaced",
            "new_chain": blockchain.chain
        }
    else:
        response = {
            'message': 'our chain in OK',
            'chain': blockchain.chain
        }
    return jsonify(response), 200


@app.route('/mine', methods=['GET'])
def mine():
    # blockchain.resolve_conflicts()
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # User recieve reward for finding PoW
    blockchain.new_transaction(
        sender="0",
        reciever=blockchain.public_key,
        amount=1,
    )
    previous_hash = blockchain.hash(last_block)
    pending_transactions_firebase = firebase.get("/pending_transactions", None)
    for transaction_id in pending_transactions_firebase:
        transaction = firebase.get("/pending_transactions", transaction_id)
        blockchain.current_transactions.append(transaction)

    block = blockchain.new_block(proof, previous_hash)
    firebase.delete('/pending_transactions', None)
    response = {
        'message': 'New block forged',
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return jsonify(response), 201


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'reciever', 'amount']
    for k in required:
        if k not in values:
            return 'Missing Values', 400

    # Create a new transaction
    index = blockchain.new_transaction(values['sender'], values['reciever'], values['amount'])
    response = {
        'message': 'Transaction will be added to Block {}'.format(index)}
    return jsonify(response), 201


@app.route('/chains', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/admin')
def index():
    # blockchain.resolve_conflicts()
    return render_template("index.html", blockchain=blockchain)


@app.route('/')
def welcome():
    return render_template("welcome.html")


@app.route('/wallet')
def wallet():
    return render_template("wallet.html")


@app.route('/dashboard')
def dashboard():
    # blockchain.resolve_conflicts()
    # update balance
    blockchain.get_balance()
    return render_template("dashboard.html", blockchain=blockchain)


@app.route('/send-rashi')
def send_rashi():
    return render_template("send-rashi.html", blockchain=blockchain)


@app.route('/purchase-rashi')
def purchase_rashi():
    return render_template("purchase-rashi.html", blockchain=blockchain)


@app.route('/payment-redirect')
def payment_redirect():
    return render_template("payment-redirect.html")


@app.route('/payment-successful')
def payment_successful():
    return render_template("payment-successful.html")


@app.route('/docs')
def docs():
    return render_template("info.html")


if __name__ == '__main__':
    try:
        port_no = sys.argv[1]
    except:
        port_no = 8000
    app.run(debug=True, port=port_no)


"""
{
    "sender" : "15adebe203754210b5d0ad04e7703b59",
    "reciever" : "98765432101234567899876543210123",
    "amount" : 250
}
"""
