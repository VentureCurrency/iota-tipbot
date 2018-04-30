# -*- coding: utf-8 -*-
from iota import *
from telegram.ext import Updater
from telegram.ext import CommandHandler
import iota
import config
import dataset
import json
import logging
import requests
import uuid
import secrets
import string


# Create the updater, dispatcher and job queue
updater = Updater(token=config.api_token)
dispatcher = updater.dispatcher
# Set up logger
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
# Set up logging file handler
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler = logging.FileHandler('iota_tipbot.log')
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
logger.addHandler(handler)
# Setup node connection
node = config.node

# Setup the initial IOTA market statistics
market_data = requests.get('https://api.coinmarketcap.com/v1/ticker/iota/')
PriceInfo = market_data.json()


# Function to send an error stating that the user does not have a username.
def username_error(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text='Please set an username before starting. \n\n'
                                                          "IOTA tipbot can't identify users that don't have username.")


# Function to check if the username of a client has been registered in the database
def username_check(username):
    db = dataset.connect('sqlite:///' + config.db_name)
    user_table = db['user']
    return user_table.find_one(user_id=username)


def start(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text='Welcome to the IOTA Telegram Tipbot! \n\n'
                                                          'This bot can help you tipping people with feeless tranfer in IOTA.')
    help(bot, update)


def help(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text='Here are availabe commands: \n\n'
                                                          '/help - Show help message \n'
                                                          '/deposit - Show the deposit address you can store to tipbot \n'
                                                          '/balance - Check the balance you stored in the bot \n'
                                                          '/tip <username> <amount> - Tip others with some iota \n'
                                                          '/withdraw <address> <amount> - Withdraw your balance to your private wallet \n'
                                                          '/price - Show current IOTA market stats on CoinMarketCap\n'
                                                          '/donate - Support our work by donating to us\n')

def price(bot, update):
    # Display the currently storecd info from CoinMarketCap
    bot.send_message(chat_id=update.message.chat_id, text='The current IOTA market stats are: \n'
                                                          'Rank: ' + PriceInfo[0]['rank'] + '\n'
                                                          'Price (USD): $' + PriceInfo[0]['price_usd'] + '\n'
                                                          'Market Cap (USD): $' + PriceInfo[0]['market_cap_usd'] + '\n'
                                                          'Percent Change (24h): ' + PriceInfo[0]['percent_change_24h'] + '%')


def donate(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text='Thanks for supporting our work!\n\n'
                                                          'If you are interested in donating or just wanna buy us a coffee feel free to tip this bot:\n\n'
                                                          '/tip iota_tip_bot <amount> \n\n'
                                                          'or donate directly to:\n\n'
                                                          '<address> \n\n'
                                                          'Thanks for using our IOTA Tipbot!')


def deposit(bot, update):
    # Attempt to fetch the username of the client
    username = str(update.message.from_user.username)
    if username == 'None':
        # If the username is 'None', the client has not set a username and thus cannot register
        username_error(bot, update)
    else:
        user_info = username_check(username)
        # Connect to the database
        db = dataset.connect('sqlite:///' + config.db_name)
        user_table = db['user']

        if user_info:
            address = user_info['address']
            # If the user already exists in the database, retrieve their address from db
            bot.send_message(chat_id=update.message.chat_id, text='Your are already registered \n\n'
                                                                  'Here is your deposit address: ' +
                                                                  address)
        else:
            # The client has a username and they are not yet registered, so begin the registration process

            # Generate new seed
            seed = ''.join(secrets.choice(string.ascii_uppercase + "9") for _ in range(81))
            api = Iota('https://field.carriota.com:443', seed)
            gen_result = api.get_new_addresses(count = None, index = None, checksum = True)['addresses'][0]
            address = str(gen_result)
            # Create recovery key (UUID4 token)
            recoveryKey = str(uuid.uuid4())
            # Insert row containing username, account and recovery key into database
            logger.info('Registered user ' + username + ' with seed ' + seed + ' and recovery key ' + recoveryKey)
            user_table.insert(dict(user_id=username, seed=seed, recovery_key=recoveryKey))
            # Notify the user
            bot.send_message(chat_id=update.message.chat_id, text='This is your first time register! \n\n'
                                                                  'Your deposit address is: ' + address + '\n\n'
                                                                  'Your recovery key is: ' + recoveryKey + '\n\n'
                                                                  'IOTA Tipbot identifies user by their username. '
                                                                  'Please remember to withdraw your funds before changing name.'
                                                                  'If you lost your balance after changing name, pleas use /recover <recover key> to retrive your funds.')


def balance(bot, update):
    # Attempt to fetch the username of the client
    username = str(update.message.from_user.username)
    if username == 'None':
        # If the username is 'None', the client has not set a username and thus cannot register
        username_error(bot, update)
    else:
        user_info = username_check(username)
        if user_info:
            # The client has a valid username and they are already registered
            # Get address of client:
            seed = user_info['seed']
            # Get the account balance of the client:
            api = Iota('https://field.carriota.com:443', seed)
            gb_result = api.get_account_data()
            balance = gb_result['balance']
            # Send the account balance in IOTA to the user:
            bot.send_message(chat_id=update.message.chat_id, text='Your balance is: \n\n' +
                                                                  str(balance) + ' iota')
        else:
            # If the user does not exist in the database they must register before checking their balance
            bot.send_message(chat_id=update.message.chat_id, text='You have not deposit any fun to IOTA tipbot yet.\n\n'
                                                                  'Please use /deposit to generate your deposite address.')


def tip(bot, update):
    # Attempt to fetch the username of the client
    username = str(update.message.from_user.username)
    if username == 'None':
        # If the username is 'None', the client has not set a username and thus cannot register
        username_error(bot, update)
    else:
        user_info = username_check(username)

        if not user_info:
            # If the user does not exist in the database they must register before checking their balance
            bot.send_message(chat_id=update.message.chat_id, text='Tipbot can\'t identify your username.\n\n'
                                                                  'Either you haven\'t deposit yet or changed username.\n\n'
                                                                  'Please use /deposit to get the address that can store your funds.\n\n'
                                                                  'Or use /recover to retrieve your previous username\'s address.')
        else:
            # Check to ensure that the tip command has the correct format - "/tip username amount"
            # If the user has only entered /tip, notify them of the correct formatting:
            if len(update.message.text.split(' ')) == 1:
                bot.send_message(chat_id=update.message.chat_id, text='Incorrect format. \n\n'
                                                                      'Please use /tip <username> <amount> \n\n'
                                                                      'Example:\n'
                                                                      '/tip iota_tip_bot 1')
            elif len(update.message.text.split(' ')) != 3:
                bot.send_message(chat_id=update.message.chat_id, text='Incorrect format. \n\n'
                                                                      'Please use /tip <username> <amount> \n\n'
                                                                      'Example:\n'
                                                                      '/tip iota_tip_bot 1')
            else:
                # Check to see if the recipient is registered with the tip bot.
                recipient_username = update.message.text.split(' ')[1]
                if recipient_username == username:
                    # If the recipient username is the same as the sender username throw an error
                    bot.send_message(chat_id=update.message.chat_id, text='You can\'t tip yourself!')
                else:
                    # Get the amount to send:
                    amount = update.message.text.split(' ')[2]
                    recipient_info = username_check(recipient_username)

                    if not recipient_info:
                        # Flag this recipient as a new recipient
                        new_recipient = True
                        # Create an account for the new recipient
                        db = dataset.connect('sqlite:///' + config.db_name)
                        user_table = db['user']
                        # Create seed
                        seed = ''.join(secrets.choice(string.ascii_uppercase + "9") for _ in range(81))
                        # Create recovery key (UUID4 token)
                        recoveryKey = str(uuid.uuid4())
                        # Insert row containing username, account and recovery key into database
                        logger.info('Registered user ' + recipient_username + ' with seed ' + seed + ' and recovery key ' + recoveryKey)
                        user_table.insert(dict(user_id=recipient_username, seed=seed, recovery_key=recoveryKey))
                        # Refresh the recipient_info
                        recipient_info = username_check(recipient_username)

                    else:
                        new_recipient = False

                    # Get the address of the recipient
                    recipient_seed = recipient_info['seed']
                    api = Iota('https://field.carriota.com:443', recipient_seed)
                    gen_result = api.get_new_addresses(count = None, index = None, checksum = True)['addresses'][0]
                    recipient_address = str(gen_result)

                    # Get the balance of the client to ensure that they have enough IOTA in their account
                    send_seed = user_info['seed']
                    api = Iota('https://field.carriota.com:443', send_seed)
                    gb_result = api.get_account_data()

                    if int(amount) <= int(gb_result['balance']):
                        # Send transaction to recipient address
                        api = Iota('https://field.carriota.com:443', send_seed)
                        result = api.send_transfer(depth = 3, transfers = [ProposedTransaction(address = Address(gen_result,), value = int(amount), tag = Tag(b'IOTATIPBOT'), message = TryteString.from_string('This is a tip sent from IOTA Tipbot.'), ), ], )

                        # Notify the user that transaction is sent
                        logger.info('User ' + username + ' sent user ' + recipient_username + ' (address ' + recipient_address + ') ' + amount +' iota')
                        bot.send_message(chat_id=update.message.chat_id, text='You have successfully tipped @' + recipient_username + ' with ' + amount + ' iota\n\n'
                                                                              'Thank you for using the IOTA Tipbot! \n\n'
                                                                              'Let @' + recipient_username + ' know that you have tipped them by sending them the message below.')
                        bot.send_message(chat_id=update.message.chat_id, text='@' + recipient_username + ' has been tipped IOTA ' + amount + ' using the IOTA Tipbot (@iota_tip_bot) courtesy of @' + username + '.')
                    else:
                        bot.send_message(chat_id=update.message.chat_id, text='Not enough funds to send ' + amount + ' iota\n\n'
                                                                              'Please use /balance to check your current balance.')


def withdraw(bot, update):
    # Attempt to fetch the username of the client
    username = str(update.message.from_user.username)
    if username == 'None':
        # If the username is 'None', the client has not set a username and thus cannot register
        username_error(bot, update)
    else:
        user_info = username_check(username)

        if not user_info:
            # If the user does not exist in the database they must register before checking their balance
            bot.send_message(chat_id=update.message.chat_id, text='Tipbot can\'t identify your username.\n\n'
                                                                  'Either you haven\'t deposit yet or changed username.\n\n'
                                                                  'Please use /deposit to get the address that can store your funds.\n\n'
                                                                  'Or use /recover to retrieve your previous username\'s address.')
        else:
            # If the user has only entered /withdraw, notify them of the correct formatting:
            if len(update.message.text.split(' ')) == 1:
                bot.send_message(chat_id=update.message.chat_id, text='Incorrect format. \n\n'
                                                                      'Please use /withdraw <address> <amount>')
            # Check to ensure that the withdraw command has the correct format - "/withdraw address amount"
            elif len(update.message.text.split(' ')) != 3:
                bot.send_message(chat_id=update.message.chat_id, text='Incorrect format. \n\n'
                                                                      'Please use /withdraw <address> <amount>')
            else:
                # Check to see if the withdraw address is valid
                withdraw_address = update.message.text.split(' ')[1]
                try:
                    recipient_address = Address(withdraw_address).with_valid_checksum()
                except:
                    bot.send_message(chat_id=update.message.chat_id, text='Incorrect format. \n\n'
                                                                          'Address you typed has invalid characters.')
                else:
                    # Get the balance of the client
                    send_seed = user_info['seed']
                    api = Iota('https://field.carriota.com:443', send_seed)
                    gb_result = api.get_account_data()
                    # Get the amount to send:
                    amount = update.message.text.split(' ')[2]

                    if int(amount) <= int(gb_result['balance']):
                        # Send transaction to recipient address
                        api = Iota('https://field.carriota.com:443', send_seed)
                        result = api.send_transfer(depth = 3, transfers = [ProposedTransaction(address = Address(recipient_address,), value = int(amount), tag = Tag(b'IOTATIPBOT'), message = TryteString.from_string('This is a withdraw sent from IOTA Tipbot.'), ), ], )

                        # Notify the user that transaction is sent
                        logger.info('User ' + username + ' withdraw ' + amount + 'iota to address ' + str(recipient_address))
                        bot.send_message(chat_id=update.message.chat_id, text='You have successfully withdrawed ' + amount + ' iota\n\n'
                                                                              'Thank you for using the IOTA Tipbot!')
                    else:
                        bot.send_message(chat_id=update.message.chat_id, text='Not enough funds to withdraw ' + amount + ' iota\n\n'
                                                                              'Please use /balance to check your current balance.')


def main():
    print ('Initializing...')

    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('help', help)
    price_handler = CommandHandler('price', price)
    donate_handler = CommandHandler('donate', donate)
    balance_handler = CommandHandler('balance', balance)
    deposit_handler = CommandHandler('deposit', deposit)
    tip_handler = CommandHandler('tip', tip)
    withdraw_handler = CommandHandler('withdraw', withdraw)

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(price_handler)
    dispatcher.add_handler(donate_handler)
    dispatcher.add_handler(balance_handler)
    dispatcher.add_handler(deposit_handler)
    dispatcher.add_handler(tip_handler)
    dispatcher.add_handler(withdraw_handler)

    print ('Done!')
    updater.start_polling()

if __name__ == '__main__':
    main()
