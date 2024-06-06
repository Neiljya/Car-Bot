import string
import json
import random

class MeowEncoderDecoder:
    def __init__(self):
        self.encoding_map, self.decoding_map = self.create_mapping()

    def create_mapping(self):
        alphabet = string.ascii_uppercase
        encoding_map = {}
        decoding_map = {}

        for i, char in enumerate(alphabet):
            num_e = (i // 3) + 1
            num_o = (i % 3) + 1
            meow_code = 'm' + 'e' * num_e + 'o' * num_o + 'w'
            encoding_map[char] = meow_code
            decoding_map[meow_code] = char
        return encoding_map, decoding_map

    def encode_message(self, message):
        encoded_message = []

        for char in message.upper():
            if char in self.encoding_map:
                encoded_message.append(self.encoding_map[char])
            else:
                encoded_message.append(char) # Leave non-alphabetic characters as they are

        return ' '.join(encoded_message)

    def decode_message(self, meow_message):
        meow_parts = meow_message.split()
        decoded_message = []

        for part in meow_parts:
            if part in self.decoding_map:
                decoded_message.append(self.decoding_map[part] + ' ')
            else:
                decoded_message.append(part)
        return ''.join(decoded_message)

class ConfigLoader:
    def __init__(self, config_directory):
        self.config_directory = config_directory

    def load_config(self):
        with open(self.config_directory, 'r') as f:
            return json.load(f)

def simulate_stock_price(current_price):
    change_percent = random.uniform(-0.05, 0.05)
    new_price = current_price * (1 + change_percent)
    return round(new_price, 2)

def load_initial_stocks(stock_data):
    with open(stock_data, 'r') as f:
        stocks = json.load(f)["stocks"]
    return {stock["symbol"]: {"price": stock["price"], "name": stock["name"]} for stock in stocks}